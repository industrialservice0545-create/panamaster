<?php
// Бот приёма кейсов Панамастер (PHP 8.4, запуск cron раз в минуту).
//
// Диалог: /add_case → отрасль → вид оборудования → бренд → модель → стойка → сервосистема →
// дефект → ремонт → заголовок → результат → срок → адрес → фото → подтверждение.
// Готовая заявка кладётся в inbox/{id}/ рабочей копии репозитория и отправляется в GitHub;
// страницы собирает GitHub Actions (bot/process_inbox.py).
//
// Приватные данные (компания, точный адрес) в репозиторий не попадают — только в DATA_DIR/private.jsonl.
//
// Конфиг: ~/panamaster.ru/bot-config.php (вне www и вне Git) или путь из CASEBOT_CONFIG:
//   return ['token' => '…', 'proxy' => 'https://….workers.dev', 'owners' => [1958544230],
//           'repo_dir' => '/home/…/panamaster-build', 'data_dir' => '/home/…/panamaster-data',
//           'dry_run' => false];

declare(strict_types=1);

const TEXT_MIN = 30;
const TEXT_MAX = 500;
const MAX_PHOTO_BYTES = 5 * 1024 * 1024;
const STATE_TTL = 24 * 3600;
const SUGGEST = 6;

$CFG = require (getenv('CASEBOT_CONFIG') ?: (getenv('HOME') ?: '/home/u550586') . '/panamaster.ru/bot-config.php');
$DICT = json_decode((string) file_get_contents($CFG['repo_dir'] . '/bot/dictionaries/entities.json'), true);
@mkdir($CFG['data_dir'] . '/state', 0700, true);

// ---------- Telegram ----------

function tg(string $method, array $params = []): ?array
{
    global $CFG;
    if (!empty($CFG['dry_run'])) {
        file_put_contents($CFG['data_dir'] . '/dry_run.log', json_encode([$method, $params], JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND);
        return ['ok' => true, 'result' => []];
    }
    foreach ($params as $k => $v) {
        if (is_array($v)) {
            $params[$k] = json_encode($v, JSON_UNESCAPED_UNICODE);
        }
    }
    $ch = curl_init("{$CFG['proxy']}/bot{$CFG['token']}/$method");
    curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_POSTFIELDS => $params,
        CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 25]);
    $res = curl_exec($ch);
    curl_close($ch);
    return is_string($res) ? json_decode($res, true) : null;
}

function send(int $chat, string $text, ?array $buttons = null): void
{
    $p = ['chat_id' => $chat, 'text' => $text];
    if ($buttons !== null) {
        $p['reply_markup'] = ['inline_keyboard' => $buttons];
    }
    tg('sendMessage', $p);
}

function logline(string $msg): void
{
    global $CFG;
    file_put_contents($CFG['data_dir'] . '/case_bot.log', date('c') . " $msg\n", FILE_APPEND);
}

// ---------- состояние диалога (flock) ----------

function state_path(int $chat): string
{
    global $CFG;
    return "{$CFG['data_dir']}/state/$chat.json";
}

function with_state(int $chat, callable $fn): void
{
    $fh = fopen(state_path($chat), 'c+');
    flock($fh, LOCK_EX);
    $raw = stream_get_contents($fh);
    $st = $raw ? (json_decode($raw, true) ?: []) : [];
    if ($st && time() - ($st['updated_at'] ?? 0) > STATE_TTL) {
        $st = [];
    }
    $st = $fn($st);
    ftruncate($fh, 0);
    rewind($fh);
    if ($st) {
        $st['updated_at'] = time();
        fwrite($fh, json_encode($st, JSON_UNESCAPED_UNICODE));
    }
    flock($fh, LOCK_UN);
    fclose($fh);
}

// ---------- справочник ----------

function industries(): array
{
    global $DICT;
    return $DICT['industries'];
}

function industry_name(string $slug): string
{
    foreach (industries() as $i) {
        if ($i['slug'] === $slug) {
            return $i['human'];
        }
    }
    return $slug;
}

function norm(string $s): string
{
    return mb_strtolower(str_replace('ё', 'е', trim($s)));
}

/** Виды оборудования, подходящие под ввод; сначала — из выбранной отрасли. */
function suggest_types(string $query, string $industry): array
{
    global $DICT;
    $q = norm($query);
    $scored = [];
    foreach ($DICT['equipment_catalog'] as $i => $t) {
        $score = 0;
        $name = norm($t['name']);
        if ($q !== '' && str_contains($name, $q)) {
            $score = 3;
        }
        foreach ($t['synonyms'] as $syn) {
            $syn = norm($syn);
            if ($q !== '' && (str_contains($q, $syn) || str_contains($syn, $q))) {
                $score = max($score, 2);
            }
        }
        if ($q === '' || $score > 0) {
            $score += in_array($industry, $t['industries'], true) ? 1 : 0;
            if ($q === '' && !in_array($industry, $t['industries'], true)) {
                continue;
            }
            $scored[] = [$score, $i];
        }
    }
    usort($scored, fn($a, $b) => $b[0] <=> $a[0] ?: $a[1] <=> $b[1]);
    return array_slice(array_map(fn($x) => $x[1], $scored), 0, SUGGEST);
}

// ---------- шаги ----------

const STEPS = [
    'company'  => ['Компания и её направление (на сайте не показывается). Например: «Типография “Альфа”, печать упаковки».', false],
    'industry' => ['Выберите отрасль:', false],
    'type'     => ['Вид оборудования — напишите, как называете (например: «офсетная машина», «частотник», «фрезерный»). Я предложу варианты.', false],
    'brand'    => ['Бренд (производитель), как на шильдике:', false],
    'model'    => ['Модель:', false],
    'rack'     => ['Стойка / система управления: бренд и модель.', true],
    'servo'    => ['Сервосистема: бренд и модель.', true],
    'defect'   => ['Что было не так (дефект), 30–500 символов:', false],
    'solution' => ['Что сделали (ремонт), 30–500 символов:', false],
    'headline' => ['Суть в 3–7 словах для заголовка. Например: «устранено смещение рапорта».', false],
    'result'   => ['Результат после ремонта одной фразой. Например: «Линия работает в штатном режиме».', true],
    'days'     => ['Срок ремонта в рабочих днях (числом). Покажем на сайте, только если ремонт был быстрым — до 5 дней.', true],
    'address'  => ['Адрес объекта (на сайте — только район или город):', false],
    'photo1'   => ['Фото: общий план оборудования.', false],
    'photo2'   => ['Фото: шкаф управления.', true],
];

function ask(int $chat, string $step, array $st): void
{
    [$question, $skippable] = STEPS[$step];
    $buttons = [];
    if ($step === 'industry') {
        foreach (array_chunk(industries(), 2, true) as $pair) {
            $row = [];
            foreach ($pair as $i => $ind) {
                $row[] = ['text' => $ind['human'], 'callback_data' => "ind:$i"];
            }
            $buttons[] = $row;
        }
    }
    if ($skippable) {
        $buttons[] = [['text' => 'Пропустить', 'callback_data' => 'skip']];
    }
    $buttons[] = [['text' => 'Отменить заявку', 'callback_data' => 'cancel']];
    $n = array_search($step, array_keys(STEPS), true) + 1;
    send($chat, "Шаг $n из " . count(STEPS) . ". $question", $buttons);
}

function next_step(string $step): ?string
{
    $keys = array_keys(STEPS);
    $i = array_search($step, $keys, true);
    return $keys[$i + 1] ?? null;
}

function validate(string $step, string $text): ?string
{
    $len = mb_strlen($text);
    return match ($step) {
        'defect', 'solution' => ($len < TEXT_MIN || $len > TEXT_MAX || count(preg_split('/\s+/u', $text)) < 5)
            ? 'Нужно 30–500 символов и хотя бы 5 слов. Напишите ещё раз.' : null,
        'headline' => ($len < 10 || $len > 60) ? 'Нужно 10–60 символов. Напишите короче или подробнее.' : null,
        'model' => ($len < 1 || $len > 100) ? 'Модель — до 100 символов.' : null,
        'brand' => ($len < 2 || $len > 60) ? 'Бренд — от 2 до 60 символов.' : null,
        'days' => (!ctype_digit($text) || (int) $text < 1 || (int) $text > 90) ? 'Нужно целое число от 1 до 90.' : null,
        'company', 'address' => ($len < 3 || $len > 200) ? 'Нужно от 3 до 200 символов.' : null,
        default => $len > 200 ? 'Слишком длинно — до 200 символов.' : null,
    };
}

function summary(array $d): string
{
    $lines = [
        'Проверьте заявку:',
        'Отрасль: ' . industry_name($d['industry']),
        'Оборудование: ' . $d['type_name'] . (!empty($d['type_new']) ? ' (новый вид — добавлю в справочник)' : ''),
        "Бренд и модель: {$d['brand']} {$d['model']}",
    ];
    foreach (['rack' => 'Стойка', 'servo' => 'Сервосистема', 'days' => 'Срок, дней'] as $k => $label) {
        if (!empty($d[$k])) {
            $lines[] = "$label: {$d[$k]}";
        }
    }
    $lines[] = "Заголовок: {$d['brand']} {$d['model']}: {$d['headline']}";
    $lines[] = 'Фото: ' . count($d['photos'] ?? []);
    return implode("\n", $lines);
}

// ---------- фото ----------

function download_photo(array $msg, string $dest): ?string
{
    global $CFG;
    $file_id = null;
    $size = 0;
    if (!empty($msg['photo'])) {
        $p = end($msg['photo']);
        $file_id = $p['file_id'];
        $size = $p['file_size'] ?? 0;
    } elseif (!empty($msg['document']) && str_starts_with($msg['document']['mime_type'] ?? '', 'image/')) {
        $file_id = $msg['document']['file_id'];
        $size = $msg['document']['file_size'] ?? 0;
    }
    if (!$file_id) {
        return 'Нужна фотография. Отправьте фото (можно файлом).';
    }
    if ($size > MAX_PHOTO_BYTES) {
        return 'Фото больше 5 МБ. Отправьте фото поменьше.';
    }
    if (!empty($CFG['dry_run'])) {
        file_put_contents($dest, 'dry-run');
        return null;
    }
    $info = tg('getFile', ['file_id' => $file_id]);
    $path = $info['result']['file_path'] ?? null;
    if (!$path) {
        return 'Не получилось скачать фото из Telegram. Отправьте ещё раз.';
    }
    $bin = @file_get_contents("{$CFG['proxy']}/file/bot{$CFG['token']}/$path");
    if ($bin === false || strlen($bin) > MAX_PHOTO_BYTES) {
        return 'Не получилось скачать фото из Telegram. Отправьте ещё раз.';
    }
    file_put_contents($dest, $bin);
    return null;
}

// ---------- публикация заявки ----------

function submit(int $chat, array $d): string
{
    global $CFG;
    $id = date('Ymd-His') . "-$chat";
    $tmp = "{$CFG['data_dir']}/state/$chat-photos";
    $inbox = "{$CFG['repo_dir']}/inbox/$id";
    // приватная часть — только на сервере
    file_put_contents("{$CFG['data_dir']}/private.jsonl", json_encode([
        'id' => $id, 'company' => $d['company'], 'address' => $d['address'], 'at' => date('c'),
    ], JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND);

    $public = [
        'id' => $id, 'date' => date('Y-m-d'), 'industry' => $d['industry'],
        'equipment_type' => $d['type_slug'] ?? null, 'equipment_type_new' => $d['type_new'] ?? null,
        'brand' => $d['brand'], 'model' => $d['model'], 'rack' => $d['rack'] ?? null, 'servo' => $d['servo'] ?? null,
        'defect' => $d['defect'], 'solution' => $d['solution'], 'headline' => $d['headline'],
        'result' => $d['result'] ?? null, 'repair_days' => isset($d['days']) ? (int) $d['days'] : null,
        'photos' => array_values($d['photos'] ?? []), 'chat_id' => $chat,
    ];
    if (!empty($CFG['dry_run'])) {
        @mkdir($inbox, 0755, true);
        file_put_contents("$inbox/request.json", json_encode($public, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
        return $id;
    }
    $repo = escapeshellarg($CFG['repo_dir']);
    $out = shell_exec("cd $repo && git pull --rebase -q origin main 2>&1");
    logline("pull $id: " . trim((string) $out));
    @mkdir($inbox, 0755, true);
    foreach ($public['photos'] as $f) {
        rename("$tmp/$f", "$inbox/$f");
    }
    file_put_contents("$inbox/request.json", json_encode($public, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    $msg = escapeshellarg("inbox: $id");
    $out = shell_exec("cd $repo && git add inbox && git -c user.name='Case Bot' -c user.email='bot@panamaster.ru' commit -q -m $msg && git push -q origin main 2>&1; echo EXIT=\$?");
    logline("push $id: " . trim((string) $out));
    if (!str_contains((string) $out, 'EXIT=0')) {
        throw new RuntimeException('git push failed');
    }
    return $id;
}

// ---------- обработка сообщений ----------

function handle_text(int $chat, string $text, array $msg): void
{
    if (in_array($text, ['/start', '/add_case'], true)) {
        with_state($chat, fn() => ['step' => 'company', 'data' => []]);
        send($chat, 'Новый кейс. Отвечайте на вопросы по очереди. Отменить в любой момент — /cancel.');
        ask($chat, 'company', []);
        return;
    }
    if ($text === '/cancel') {
        with_state($chat, fn() => []);
        send($chat, 'Заявка отменена. Начать заново — /add_case.');
        return;
    }
    if ($text === '/help') {
        send($chat, "/add_case — новый кейс\n/cancel — отменить\n/status — где я в анкете");
        return;
    }
    with_state($chat, function (array $st) use ($chat, $text, $msg) {
        if (!$st) {
            send($chat, 'Чтобы добавить кейс, отправьте /add_case.');
            return [];
        }
        $step = $st['step'];
        if ($text === '/status') {
            ask($chat, $step, $st);
            return $st;
        }
        if ($step === 'industry') {
            send($chat, 'Выберите отрасль кнопкой выше.');
            return $st;
        }
        if ($step === 'confirm') {
            send($chat, 'Нажмите «Опубликовать» или «Отменить» под сводкой.');
            return $st;
        }
        if (in_array($step, ['photo1', 'photo2'], true)) {
            global $CFG;
            $dir = "{$CFG['data_dir']}/state/$chat-photos";
            @mkdir($dir, 0700, true);
            $name = $step === 'photo1' ? 'photo-1.jpg' : 'photo-2.jpg';
            $err = download_photo($msg, "$dir/$name");
            if ($err) {
                send($chat, $err);
                return $st;
            }
            $st['data']['photos'][$step] = $name;
            return advance($chat, $st);
        }
        if ($step === 'type') {
            $st['data']['type_query'] = $text;
            $found = suggest_types($text, $st['data']['industry']);
            global $DICT;
            $buttons = array_map(fn($i) => [['text' => $DICT['equipment_catalog'][$i]['name'], 'callback_data' => "type:$i"]], $found);
            $buttons[] = [['text' => "Нет в списке — добавить «" . mb_substr($text, 0, 40) . "»", 'callback_data' => 'type:new']];
            $buttons[] = [['text' => 'Отменить заявку', 'callback_data' => 'cancel']];
            send($chat, $found ? 'Выберите вид оборудования:' : 'Похожего вида в справочнике нет.', $buttons);
            return $st;
        }
        if ($err = validate($step, $text)) {
            send($chat, $err);
            return $st;
        }
        $st['data'][$step] = $text;
        return advance($chat, $st);
    });
}

function advance(int $chat, array $st): array
{
    $next = next_step($st['step']);
    if ($next === null) {
        $st['step'] = 'confirm';
        send($chat, summary($st['data']), [[['text' => 'Опубликовать', 'callback_data' => 'publish']],
            [['text' => 'Отменить заявку', 'callback_data' => 'cancel']]]);
        return $st;
    }
    $st['step'] = $next;
    ask($chat, $next, $st);
    return $st;
}

function handle_callback(int $chat, string $data, string $cb_id): void
{
    tg('answerCallbackQuery', ['callback_query_id' => $cb_id]);
    if ($data === 'cancel') {
        with_state($chat, fn() => []);
        send($chat, 'Заявка отменена. Начать заново — /add_case.');
        return;
    }
    with_state($chat, function (array $st) use ($chat, $data) {
        global $DICT;
        if (!$st) {
            return [];
        }
        $step = $st['step'];
        if ($data === 'skip' && (STEPS[$step][1] ?? false)) {
            return advance($chat, $st);
        }
        if ($step === 'industry' && str_starts_with($data, 'ind:')) {
            $ind = industries()[(int) substr($data, 4)] ?? null;
            if ($ind) {
                $st['data']['industry'] = $ind['slug'];
                return advance($chat, $st);
            }
        }
        if ($step === 'type' && str_starts_with($data, 'type:')) {
            $key = substr($data, 5);
            if ($key === 'new') {
                $name = trim($st['data']['type_query'] ?? '');
                $st['data']['type_new'] = mb_strtoupper(mb_substr($name, 0, 1)) . mb_substr($name, 1);
                $st['data']['type_name'] = $st['data']['type_new'];
            } elseif (isset($DICT['equipment_catalog'][(int) $key])) {
                $t = $DICT['equipment_catalog'][(int) $key];
                $st['data']['type_slug'] = $t['slug'];
                $st['data']['type_name'] = $t['name'];
            }
            if (!empty($st['data']['type_name'])) {
                return advance($chat, $st);
            }
        }
        if ($step === 'confirm' && $data === 'publish') {
            try {
                $id = submit($chat, $st['data']);
                send($chat, "Принял, заявка $id. Страницы соберутся и опубликуются в течение 10 минут — пришлю отчёт со ссылками.");
                logline("submitted $id");
                return [];
            } catch (Throwable $e) {
                logline('submit error: ' . $e->getMessage());
                send($chat, 'Не получилось отправить заявку. Данные сохранены — попробуйте «Опубликовать» ещё раз через минуту.');
                return $st;
            }
        }
        return $st;
    });
}

// ---------- главный цикл ----------

function run(array $updates): void
{
    global $CFG;
    foreach ($updates as $u) {
        $msg = $u['message'] ?? null;
        $cb = $u['callback_query'] ?? null;
        $from = $msg['from']['id'] ?? $cb['from']['id'] ?? null;
        $chat = $msg['chat']['id'] ?? $cb['message']['chat']['id'] ?? null;
        if (!$chat) {
            continue;
        }
        if (!in_array($from, $CFG['owners'], true)) {
            send((int) $chat, 'Доступ только для сотрудников Панамастер.');
            continue;
        }
        try {
            if ($cb) {
                handle_callback((int) $chat, (string) $cb['data'], (string) $cb['id']);
            } else {
                handle_text((int) $chat, trim((string) ($msg['text'] ?? $msg['caption'] ?? '')), $msg);
            }
        } catch (Throwable $e) {
            logline('error: ' . $e->getMessage());
            send((int) $chat, 'Что-то пошло не так. Повторите последний ответ или /cancel.');
        }
    }
}

if (PHP_SAPI === 'cli' && realpath($_SERVER['argv'][0]) === __FILE__) {
    if (!empty($CFG['dry_run']) && isset($_SERVER['argv'][1])) {
        run(json_decode((string) file_get_contents($_SERVER['argv'][1]), true));   // тест: обновления из файла
        exit;
    }
    $lock = fopen($CFG['data_dir'] . '/poll.lock', 'c');
    if (!flock($lock, LOCK_EX | LOCK_NB)) {
        exit;
    }
    $offset_file = $CFG['data_dir'] . '/offset.txt';
    $offset = (int) @file_get_contents($offset_file);
    $res = tg('getUpdates', ['offset' => $offset + 1, 'timeout' => 20, 'allowed_updates' => ['message', 'callback_query']]);
    if (!($res['ok'] ?? false)) {
        logline('getUpdates failed');
        exit;
    }
    foreach ($res['result'] as $u) {
        run([$u]);
        file_put_contents($offset_file, (string) $u['update_id']);
    }
}
