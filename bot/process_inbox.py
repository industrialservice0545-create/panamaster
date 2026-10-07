"""Обработка заявок бота: inbox/{id}/request.json + фото → assets/data/cases.json + фото кейса.

Формат кейса (format): machine — ремонт станка/линии на объекте (по умолчанию), block — ремонт блока в мастерской
(кейс показывается на страницах /blocks/ своего вида, бренда и модели). photo_alts — подписи к фото по порядку.

Для каждой заявки:
  - новый вид оборудования (equipment_type_new) добавляется в справочник;
  - slug «бренд-модель» (при занятости — с -2, -3…);
  - фото: кадр 3:2 по центру, 1200×800, стиль сайта (монохром, тёплые тона 15–45° сохраняются), WebP ≤100 КБ,
    без метаданных → assets/img/cases/{slug}/photo-N.webp;
  - запись добавляется в cases.json, папка заявки удаляется.
Итог пишется в inbox_report.json (для отчёта в Telegram).

Запуск из корня репозитория:  python3 bot/process_inbox.py   (нужен Pillow)
"""
import glob
import json
import os
import re
import shutil
import sys

from PIL import Image, ImageChops, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BYTES = 100 * 1024
SIZE = (1200, 800)
HUE_KEEP = (11, 32)          # 15–45° в шкале Pillow 0–255: оранжевые и коричневые тона
TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
                     'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))


def slugify(text):
    s = ''.join(TRANSLIT.get(ch, ch) for ch in text.lower())
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'[^a-z0-9-]', '', s)
    return re.sub(r'-{2,}', '-', s).strip('-')[:80].strip('-')


def lower_first(text):
    """Заголовок идёт после «Бренд Модель:» — первая буква строчная, если это не аббревиатура."""
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


def sentence(text):
    """Пробелы и точка в конце."""
    text = ' '.join(text.split())
    return text if text.endswith(('.', '!', '?')) else text + '.'


def style_photo(src, dst):
    """Кадр 3:2, 1200×800, монохром с сохранением тёплых тонов, WebP ≤100 КБ. Возвращает (w, h)."""
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
    if im.height > im.width:   # вертикальное фото: вписываем целиком на светло-серый фон, а не режем середину
        canvas = Image.new('RGB', SIZE, (226, 226, 226))
        fg = im.resize((round(im.width * SIZE[1] / im.height), SIZE[1]), Image.LANCZOS)
        canvas.paste(fg, ((SIZE[0] - fg.width) // 2, 0))
        im = canvas
    im = ImageOps.fit(im, SIZE, Image.LANCZOS) if im.width >= SIZE[0] and im.height >= SIZE[1] \
        else ImageOps.fit(im, (im.width, round(im.width * 2 / 3)) if im.width * 2 / 3 <= im.height
                          else (round(im.height * 3 / 2), im.height), Image.LANCZOS)
    h, s, v = im.convert('HSV').split()
    keep = h.point(lambda x: 255 if HUE_KEEP[0] <= x <= HUE_KEEP[1] else 0)
    s = ImageChops.multiply(s, keep)
    out = Image.merge('HSV', (h, s, v)).convert('RGB')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for size in (out.size, (1000, 667), (900, 600)):
        img = out if size == out.size else out.resize(size, Image.LANCZOS)
        for q in (85, 75, 65, 55, 45):
            img.save(dst, 'WEBP', quality=q, method=6)
            if os.path.getsize(dst) <= MAX_BYTES:
                return img.size
    return img.size


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return json.load(f)


def save_json(rel, data):
    with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def ensure_type(req, dictionary):
    """Слаг вида оборудования; новый вид добавляется в справочник."""
    if req.get('equipment_type'):
        return req['equipment_type']
    name = (req.get('equipment_type_new') or '').strip()
    if not name:
        raise ValueError('не указан вид оборудования')
    for t in dictionary['equipment_catalog']:
        if t['name'].lower() == name.lower():
            return t['slug']
    slug = slugify(name) or 'equipment'
    taken = {t['slug'] for t in dictionary['equipment_catalog']}
    base, n = slug, 2
    while slug in taken:
        slug, n = f'{base}-{n}', n + 1
    dictionary['equipment_catalog'].append({'name': name, 'slug': slug, 'synonyms': [name.lower()],
                                            'industries': [req['industry']]})
    dictionary['equipment_types'].append(name)
    return slug


def unique_slug(brand, model, taken):
    base = slugify(f'{brand} {model}') or 'case'
    slug, n = base, 2
    while slug in taken:
        slug, n = f'{base}-{n}', n + 1
    return slug


def process():
    cases = load_json('assets/data/cases.json')
    dictionary = load_json('bot/dictionaries/entities.json')
    type_names = {t['slug']: t['name'] for t in dictionary['equipment_catalog']}
    report = []
    for req_path in sorted(glob.glob(os.path.join(ROOT, 'inbox', '*', 'request.json'))):
        folder = os.path.dirname(req_path)
        with open(req_path, encoding='utf-8') as f:
            req = json.load(f)
        for field in ('industry', 'brand', 'model', 'defect', 'solution', 'headline'):
            if not str(req.get(field) or '').strip():
                raise ValueError(f'{req.get("id")}: пустое поле {field}')
        type_slug = ensure_type(req, dictionary)
        type_names = {t['slug']: t['name'] for t in dictionary['equipment_catalog']}
        slug = unique_slug(req['brand'], req['model'], {c['slug'] for c in cases})
        name = f'{req["brand"]} {req["model"]}'
        photos = []
        for i, fname in enumerate(req.get('photos') or [], start=1):
            src = os.path.join(folder, fname)
            if not os.path.exists(src):
                continue
            w, h = style_photo(src, os.path.join(ROOT, 'assets', 'img', 'cases', slug, f'photo-{i}.webp'))
            alts = req.get('photo_alts') or []
            alt = alts[i - 1] if i <= len(alts) and alts[i - 1] else (
                f'{type_names.get(type_slug, "Оборудование")} {name}' if i == 1 else f'Шкаф управления {name} после ремонта')
            photos.append({'file': f'photo-{i}.webp', 'w': w, 'h': h, 'alt': alt})
        record = {
            'slug': slug, 'date': req['date'], 'industry': req['industry'], 'equipment_type': type_slug,
            'format': req.get('format') if req.get('format') in ('machine', 'block') else 'machine',
            'brand': req['brand'].strip(), 'model': re.sub(r'\s+', ' ', req['model']).strip(),
            'rack': req.get('rack'), 'servo': req.get('servo'),
            'headline': lower_first(req['headline'].strip().rstrip('.')),
            'defect': sentence(req['defect']), 'solution': sentence(req['solution']),
            'result': (req.get('result') or 'Оборудование работает в штатном режиме, дефект устранён.').strip(),
            'repair_days': req.get('repair_days'), 'area': req.get('area'), 'lat': req.get('lat'), 'lon': req.get('lon'),
            'photos': photos, 'request_id': req.get('id'),
        }
        if not record['result'].endswith(('.', '!')):
            record['result'] += '.'
        cases.append(record)
        shutil.rmtree(folder)
        report.append({'id': req.get('id'), 'slug': slug, 'title': f'{record["brand"]} {record["model"]}: {record["headline"]}',
                       'photos': len(photos), 'new_type': req.get('equipment_type_new'), 'chat_id': req.get('chat_id')})
    if report:
        save_json('assets/data/cases.json', cases)
        save_json('bot/dictionaries/entities.json', dictionary)
    save_json('inbox_report.json', report)
    return report


if __name__ == '__main__':
    r = process()
    print(f'обработано заявок: {len(r)}')
    for x in r:
        print(f'  {x["slug"]}: {x["title"]} (фото {x["photos"]})')
    sys.exit(0)
