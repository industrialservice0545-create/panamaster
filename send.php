<?php
// Приём заявок с форм сайта: запись в журнал заявок, сообщение в Telegram + письмо на info@panamaster.ru.
// Совместим с PHP 7.2+. Ответ: JSON для fetch, редирект обратно — без JS.
// Токен бота — в ~/panamaster.ru/lead-config.php (вне www и вне Git):
//   <?php return array('token' => '...', 'chat_id' => '...', 'proxy' => 'https://....workers.dev');

$to = 'info@panamaster.ru';

function sendTelegram($text, $buttons = null)
{
    $configFile = dirname(__DIR__) . '/lead-config.php';
    if (!is_file($configFile)) {
        return false;
    }
    $config = include $configFile;
    if (!is_array($config) || empty($config['token']) || empty($config['chat_id']) || empty($config['proxy'])) {
        return false;
    }
    $url = rtrim($config['proxy'], '/') . '/bot' . $config['token'] . '/sendMessage';
    $params = array('chat_id' => $config['chat_id'], 'text' => $text);
    if ($buttons !== null) {
        $params['reply_markup'] = json_encode(array('inline_keyboard' => $buttons), JSON_UNESCAPED_UNICODE);
    }
    $body = http_build_query($params);

    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, array(
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 8,
        ));
        $result = curl_exec($ch);
        curl_close($ch);
    } else {
        $context = stream_context_create(array('http' => array(
            'method' => 'POST',
            'header' => "Content-Type: application/x-www-form-urlencoded\r\n",
            'content' => $body,
            'timeout' => 8,
        )));
        $result = @file_get_contents($url, false, $context);
    }
    $data = is_string($result) ? json_decode($result, true) : null;
    return is_array($data) && !empty($data['ok']);
}

function respond($ok, $message)
{
    $wantsJson = isset($_SERVER['HTTP_ACCEPT']) && strpos($_SERVER['HTTP_ACCEPT'], 'application/json') !== false;
    if ($wantsJson) {
        http_response_code($ok ? 200 : 400);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(array('ok' => $ok, 'message' => $message), JSON_UNESCAPED_UNICODE);
        exit;
    }
    $back = '/';
    if (!empty($_SERVER['HTTP_REFERER'])) {
        $path = parse_url($_SERVER['HTTP_REFERER'], PHP_URL_PATH);
        // «//host» браузер считает другим доменом — такой путь не принимаем
        if (is_string($path) && preg_match('~^/(?!/)[A-Za-z0-9/_.-]*$~', $path)) {
            $back = $path;
        }
    }
    header('Location: ' . $back . '?sent=' . ($ok ? '1' : '0'), true, 303);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    respond(false, 'Метод не поддерживается');
}

// Заявки только с нашего сайта: браузер ставит Origin на POST с чужих страниц
if (!empty($_SERVER['HTTP_ORIGIN'])) {
    $originHost = parse_url($_SERVER['HTTP_ORIGIN'], PHP_URL_HOST);
    if (!in_array($originHost, array('panamaster.ru', 'www.panamaster.ru'), true)) {
        respond(false, 'Отправьте заявку с сайта panamaster.ru');
    }
}

// Ловушка для ботов: поле скрыто от людей
if (!empty($_POST['website'])) {
    respond(true, 'Заявка отправлена');
}

// Не больше 3 заявок за 10 минут с одного IP и 50 за сутки всего — защита от заливки спамом.
// Счётчики — в ~/panamaster.ru/lead-rate/ (вне www).
function rateLimited($ip)
{
    $dir = dirname(__DIR__) . '/lead-rate';
    if (!is_dir($dir) && !@mkdir($dir, 0700)) {
        return false; // нет папки — не теряем настоящие заявки
    }
    $now = time();
    $rules = array(
        'ip-' . md5($ip) => array(600, 3),
        'all-' . gmdate('Ymd', $now + 3 * 3600) => array(86400, 50),
    );
    foreach ($rules as $name => $rule) {
        $file = $dir . '/' . $name;
        $fh = @fopen($file, 'c+');
        if (!$fh) {
            continue;
        }
        flock($fh, LOCK_EX);
        $times = array_filter(array_map('intval', explode(',', (string) stream_get_contents($fh))),
            function ($t) use ($now, $rule) { return $t > $now - $rule[0]; });
        $over = count($times) >= $rule[1];
        if (!$over) {
            $times[] = $now;
            ftruncate($fh, 0);
            rewind($fh);
            fwrite($fh, implode(',', $times));
        }
        flock($fh, LOCK_UN);
        fclose($fh);
        if ($over) {
            return true;
        }
    }
    // Старые счётчики чистим изредка
    if (mt_rand(1, 50) === 1) {
        foreach ((array) glob($dir . '/*') as $f) {
            if (is_file($f) && filemtime($f) < $now - 86400) {
                @unlink($f);
            }
        }
    }
    return false;
}

if (rateLimited(isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '')) {
    respond(false, 'Слишком много заявок подряд. Позвоните: +7 926 883-09-39');
}

// Производители оборудования (/manufacturers.html, /en/, /zh/): контакт — e-mail, WeChat или WhatsApp, а не российский телефон
$isMaker = isset($_POST['audience']) && $_POST['audience'] === 'manufacturer';
$lang = isset($_POST['lang']) && in_array($_POST['lang'], array('ru', 'en', 'zh'), true) ? $_POST['lang'] : 'ru';
$makerField = function ($name, $len) {
    return isset($_POST[$name]) ? mb_substr(trim((string) $_POST[$name]), 0, $len) : '';
};
if ($isMaker) {
    $contact = $makerField('contact', 200);
    $company = $makerField('company', 200);
    if (mb_strlen($contact) < 4 || $company === '') {
        respond(false, $lang === 'zh' ? '请填写公司名称和联系方式' : ($lang === 'en' ? 'Please enter your company and a contact' : 'Укажите компанию и контакт'));
    }
    $phone = $contact;
    $digits = substr(preg_replace('/\D+/', '', $contact), -4) ?: 'mkr';
} else {
    $phone = isset($_POST['phone']) ? trim((string) $_POST['phone']) : '';
    $digits = preg_replace('/\D+/', '', $phone);
    if (strlen($digits) < 10 || strlen($digits) > 12) {
        respond(false, 'Проверьте номер телефона');
    }
}

$page = isset($_POST['page']) ? mb_substr(trim((string) $_POST['page']), 0, 200) : '';
$comment = isset($_POST['comment']) ? mb_substr(trim((string) $_POST['comment']), 0, 1000) : '';

// Ключ формы ставит assets/js/main.js после действий человека на странице. Без верного ключа заявку
// не шлём в Telegram и на почту, а только пишем в журнал как подозрительную — реальная заявка не потеряется.
function formKeyValid($key)
{
    if (!preg_match('~^(\d{9,11})\.(\d{1,7})$~', (string) $key, $m)) {
        return false;
    }
    $t = (int) $m[1];
    if ($t > time() + 60 || $t < time() - 6 * 3600 || time() - $t < 2) {
        return false;
    }
    $src = 'pm' . $t;
    $h = 7;
    for ($i = 0; $i < strlen($src); $i++) {
        $h = ($h * 31 + ord($src[$i])) % 1000003;
    }
    return (int) $m[2] === $h;
}

if (!formKeyValid(isset($_POST['pm_key']) ? $_POST['pm_key'] : '')) {
    @file_put_contents(dirname(__DIR__) . '/leads.jsonl', json_encode(array(
        'ts' => date('c'), 'type' => 'lead_suspect', 'reason' => 'no_js_key', 'source' => 'site_form',
        'page' => $page, 'phone' => mb_substr($phone, 0, 40), 'comment' => $comment,
        'ip' => isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '',
    ), JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND | LOCK_EX);
    respond(true, 'Заявка отправлена');
}

// Признаки бота у заявок, прошедших проверку: показываем владельцу, но не блокируем
$botSigns = array();
if (empty($_SERVER['HTTP_ORIGIN'])) {
    $botSigns[] = 'нет Origin';
}
if (!$isMaker && stripos(isset($_SERVER['HTTP_ACCEPT_LANGUAGE']) ? $_SERVER['HTTP_ACCEPT_LANGUAGE'] : '', 'ru') === false) {
    $botSigns[] = 'язык браузера не русский';
}

$lines = $isMaker ? array(
    '🏭 ПРОИЗВОДИТЕЛЬ ОБОРУДОВАНИЯ — заявка на сотрудничество (' . $lang . ')',
    '',
    'Компания: ' . $makerField('company', 200),
    'Страна: ' . ($makerField('country', 100) ?: '—'),
    'Оборудование: ' . ($makerField('equipment', 200) ?: '—'),
    'Контакт: ' . $phone,
    'Страница: ' . ($page !== '' ? $page : '—'),
) : array(
    // Кандидаты со страницы «Карьера и обучение» — отдельной пометкой, не путать с заявкой на ремонт
    $page === 'Карьера и обучение' ? '👷 КАНДИДАТ — отклик со страницы «Карьера и обучение»' : 'Новая заявка с сайта panamaster.ru',
    '',
    'Телефон: ' . mb_substr($phone, 0, 40),
    'Страница: ' . ($page !== '' ? $page : '—'),
);
if ($comment !== '') {
    $lines[] = 'Комментарий: ' . $comment;
}
$lines[] = 'Время (МСК): ' . gmdate('d.m.Y H:i', time() + 3 * 3600);
$lines[] = 'IP: ' . (isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '—');
if ($botSigns) {
    $lines[] = '⚠️ Возможен спам: ' . implode(', ', $botSigns);
}

$subject = '=?UTF-8?B?' . base64_encode(($isMaker ? 'Производитель оборудования: ' . $makerField('company', 80) : 'Заявка с сайта: ' . $digits)) . '?=';
$headers = implode("\r\n", array(
    'From: =?UTF-8?B?' . base64_encode('Сайт Панамастер') . '?= <noreply@panamaster.ru>',
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=utf-8',
    'Content-Transfer-Encoding: 8bit',
));

// Журнал заявок: ~/panamaster.ru/leads.jsonl (вне www и вне Git). Оценку «целевая / нет / спам»
// владелец ставит кнопкой в Telegram — её записывает bot/case_bot.php.
$leadId = gmdate('ymd-His', time() + 3 * 3600) . '-' . substr($digits, -4);
@file_put_contents(dirname(__DIR__) . '/leads.jsonl', json_encode(array(
    'ts' => date('c'), 'type' => 'lead', 'id' => $leadId, 'source' => 'site_form',
    'page' => $page, 'phone' => mb_substr($phone, 0, 40), 'comment' => $comment,
    'audience' => $isMaker ? 'manufacturer' : ($page === 'Карьера и обучение' ? 'candidate' : 'owner'), 'lang' => $lang,
), JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND | LOCK_EX);
$lines[] = 'Заявка: ' . $leadId;

$text = implode("\n", $lines);
$telegramSent = sendTelegram($text, array(array(
    array('text' => '✅ Целевая', 'callback_data' => 'lead:' . $leadId . ':t'),
    array('text' => '❌ Нецелевая', 'callback_data' => 'lead:' . $leadId . ':n'),
    array('text' => '🚫 Спам', 'callback_data' => 'lead:' . $leadId . ':s'),
)));
$mailSent = mail($to, $subject, $text, $headers, '-fnoreply@panamaster.ru');
$sent = $telegramSent || $mailSent;

$failText = $lang === 'zh' ? '发送失败，请发邮件至 info@panamaster.ru' : ($lang === 'en' ? 'Sending failed. Please e-mail info@panamaster.ru' : 'Не удалось отправить. Позвоните: +7 926 883-09-39');
respond($sent, $sent ? 'Заявка отправлена' : $failText);
