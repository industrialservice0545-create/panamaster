"""Пост о кейсе для Telegram-канала: assets/data/cases.json → альбом из фото с подписью.

По умолчанию отправляет черновик владельцу (TELEGRAM_OWNER_CHAT_ID), с --channel — в канал.
Токен и chat_id — из ~/.config/panamaster/telegram.env (вне Git).

Запуск из корня репозитория:
  python3 bot/tg_post.py codimag-viva-340              # черновик владельцу
  python3 bot/tg_post.py codimag-viva-340 --channel    # публикация в @panamaster_msk
  python3 bot/tg_post.py codimag-viva-340 --print      # только показать текст
"""
import html
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import uuid

try:
    from PIL import Image
except ImportError:
    Image = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNEL = '@panamaster_msk'
SITE = 'https://panamaster.ru'
PHONE = '+7 926 883-09-39'
UTM = 'utm_source=telegram&utm_medium=social&utm_campaign=cases'
CAPTION_MAX = 1024


def load_env(path=os.path.expanduser('~/.config/panamaster/telegram.env')):
    env = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.strip().split('=', 1)
                env[k] = v.strip('"\'')
    return env


def find_case(slug):
    with open(os.path.join(ROOT, 'assets/data/cases.json'), encoding='utf-8') as f:
        for case in json.load(f):
            if case['slug'] == slug:
                return case
    sys.exit(f'Кейс {slug} не найден в cases.json')


def caption(case):
    e = html.escape
    url = f"{SITE}/cases/{case['slug']}.html?{UTM}"
    parts = [
        f"🔧 <b>{e(case['brand'])} {e(case['model'])}: {e(case['headline'])}</b>",
        e(case['defect']),
        e(case['solution']),
        f"✅ {e(case['result'])} Гарантия 3 месяца.",
        f"Похожая поломка? Напишите модель и дефект: {PHONE}\n"
        f"<a href=\"{e(url)}\">Подробнее о ремонте на сайте</a>",
    ]
    if case.get('format') == 'block':
        parts[-1] = (f"Похожий блок? Привезите его в мастерскую или отправьте транспортной компанией — "
                     f"диагностика бесплатно. Пишите: {PHONE}\n"
                     f"<a href=\"{e(url)}\">Подробнее о ремонте на сайте</a>")
    text = '\n\n'.join(parts)
    if len(text) > CAPTION_MAX:
        sys.exit(f'Подпись {len(text)} символов, лимит Telegram {CAPTION_MAX}')
    return text


def jpeg(path):
    """Telegram не принимает WebP как фото — перекодируем в JPEG (Pillow, на Mac без него — sips)."""
    if Image:
        buf = io.BytesIO()
        Image.open(path).convert('RGB').save(buf, 'JPEG', quality=90)
        return buf.getvalue()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'photo.jpg')
        subprocess.run(['sips', '-s', 'format', 'jpeg', path, '--out', out], check=True, capture_output=True)
        with open(out, 'rb') as f:
            return f.read()


def send_album(token, chat_id, case, text):
    boundary = uuid.uuid4().hex
    media, files = [], []
    for i, photo in enumerate(case['photos']):
        name = f'p{i}'
        item = {'type': 'photo', 'media': f'attach://{name}'}
        if i == 0:
            item.update(caption=text, parse_mode='HTML')
        media.append(item)
        files.append((name, jpeg(os.path.join(ROOT, 'assets/img/cases', case['slug'], photo['file']))))

    body = io.BytesIO()
    def field(name, value, filename=None, ctype=None):
        body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'.encode())
        if filename:
            body.write(f'; filename="{filename}"\r\nContent-Type: {ctype}'.encode())
        body.write(b'\r\n\r\n')
        body.write(value if isinstance(value, bytes) else str(value).encode())
        body.write(b'\r\n')
    field('chat_id', chat_id)
    field('media', json.dumps(media, ensure_ascii=False))
    for name, data in files:
        field(name, data, f'{name}.jpg', 'image/jpeg')
    body.write(f'--{boundary}--\r\n'.encode())

    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/sendMediaGroup', data=body.getvalue(),
                                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)
    if not res.get('ok'):
        sys.exit(f'Telegram: {res}')
    return res['result'][0]['message_id']


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 1:
        sys.exit(__doc__)
    case = find_case(args[0])
    text = caption(case)
    if '--print' in sys.argv:
        print(text)
        return
    env = load_env()
    chat = CHANNEL if '--channel' in sys.argv else env['TELEGRAM_OWNER_CHAT_ID']
    msg_id = send_album(env['TELEGRAM_BOT_TOKEN'], chat, case, text)
    print(f'Отправлено в {chat}, message_id {msg_id}')


if __name__ == '__main__':
    main()
