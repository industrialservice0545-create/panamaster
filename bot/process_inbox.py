"""Обработка заявок бота: inbox/{id}/request.json + фото → assets/data/cases.json + фото кейса.

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


def style_photo(src, dst):
    """Кадр 3:2, 1200×800, монохром с сохранением тёплых тонов, WebP ≤100 КБ. Возвращает (w, h)."""
    im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
    im = ImageOps.fit(im, SIZE, Image.LANCZOS) if im.width >= SIZE[0] and im.height >= SIZE[1] \
        else ImageOps.fit(im, (im.width, round(im.width * 2 / 3)) if im.width * 2 / 3 <= im.height
                          else (round(im.height * 3 / 2), im.height), Image.LANCZOS)
    h, s, v = im.convert('HSV').split()
    keep = h.point(lambda x: 255 if HUE_KEEP[0] <= x <= HUE_KEEP[1] else 0)
    s = ImageChops.multiply(s, keep)
    out = Image.merge('HSV', (h, s, v)).convert('RGB')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for q in (85, 75, 65, 55, 45):
        out.save(dst, 'WEBP', quality=q, method=6)
        if os.path.getsize(dst) <= MAX_BYTES:
            break
    return out.size


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
            alt = f'{type_names.get(type_slug, "Оборудование")} {name}' if i == 1 else f'Шкаф управления {name} после ремонта'
            photos.append({'file': f'photo-{i}.webp', 'w': w, 'h': h, 'alt': alt})
        record = {
            'slug': slug, 'date': req['date'], 'industry': req['industry'], 'equipment_type': type_slug,
            'brand': req['brand'].strip(), 'model': re.sub(r'\s+', ' ', req['model']).strip(),
            'rack': req.get('rack'), 'servo': req.get('servo'),
            'headline': req['headline'].strip().rstrip('.'),
            'defect': req['defect'].strip(), 'solution': req['solution'].strip(),
            'result': (req.get('result') or 'Оборудование работает в штатном режиме, дефект устранён.').strip(),
            'repair_days': req.get('repair_days'), 'area': None, 'lat': None, 'lon': None,
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
