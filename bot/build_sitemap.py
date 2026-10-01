"""Генерация sitemap.xml и llms.txt по страницам сайта.

sitemap.xml — все индексируемые страницы (meta robots index), lastmod = дата последнего коммита файла.
llms.txt   — краткое описание компании и список страниц для AI-поиска (Алиса, Нейро, ChatGPT, Perplexity).
Не входят: privacy.html, consent.html, all-services.html, test.html и страницы с noindex.

Запуск из корня репозитория:  python3 bot/build_sitemap.py
"""
import glob
import html
import os
import re
import subprocess
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://panamaster.ru'
EXCLUDE = {'privacy.html', 'consent.html', 'all-services.html', 'test.html'}


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def pages():
    """Индексируемые страницы в порядке важности: главная, разделы, отрасли, кейсы."""
    result = []
    for rel in ['index.html', 'cases.html', 'contacts.html', 'map.html', 'blocks.html'] + sorted(glob.glob('blocks/**/*.html', root_dir=ROOT, recursive=True)) \
            + sorted(glob.glob('services/*.html', root_dir=ROOT)) \
            + sorted(glob.glob('cases/*.html', root_dir=ROOT)):
        if rel in EXCLUDE or not os.path.exists(os.path.join(ROOT, rel)):
            continue
        if re.search(r'<meta name="robots" content="noindex', read(rel)):
            continue
        result.append(rel)
    return result


def url_of(rel):
    return f'{SITE}/' if rel == 'index.html' else f'{SITE}/{rel}'


def lastmod(rel):
    """Дата последнего коммита файла; для незакоммиченного файла — сегодня."""
    try:
        out = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', rel], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        out = ''
    dirty = subprocess.run(['git', 'status', '--porcelain', '--', rel], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return date.today().isoformat() if (dirty or not out) else out


def priority(rel):
    if rel == 'index.html':
        return '1.0'
    if rel in ('cases.html', 'contacts.html', 'blocks.html'):
        return '0.8'
    if rel.startswith(('services/', 'blocks/')):
        return '0.7'
    return '0.6'


def build_sitemap(rels):
    items = '\n'.join(
        f'  <url>\n    <loc>{url_of(r)}</loc>\n    <lastmod>{lastmod(r)}</lastmod>\n    <priority>{priority(r)}</priority>\n  </url>'
        for r in rels)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n'


def meta(rel):
    s = read(rel)
    title = html.unescape(re.search(r'<title>(.*?)</title>', s).group(1)).replace(' — Панамастер', '')
    desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', s).group(1))
    return title, desc


def build_llms(rels):
    industries = [r for r in rels if r.startswith('services/industry-')]
    hubs = [r for r in rels if r.startswith(('services/brand-', 'services/type-'))]
    blocks = [r for r in rels if r == 'blocks.html' or r.startswith('blocks/')]
    cases = [r for r in rels if r.startswith('cases/')]
    line = lambda r: '- [{0}]({1}): {2}'.format(*meta(r)[:1], url_of(r), meta(r)[1])
    return f'''# Панамастер

> Ремонт промышленного оборудования в Москве и Московской области с выездом и гарантией 3 месяца. Работаем с 2006 года.

- Выезд: в течение 24 часов по Москве и МО, в другие регионы — по договорённости.
- Диагностика: 1 рабочий день. Типовой ремонт: 3–5 рабочих дней.
- Гарантия: 3 месяца с момента пусконаладки под нагрузкой.
- Клиенты: компании и частные клиенты. Договор, любая форма оплаты (безналичный расчёт без НДС, наличные, карта), закрывающие документы.
- Ремонт: станки с ЧПУ, частотные преобразователи, сервоприводы, ПЛК, панели оператора, источники питания.
- Мастерская: Москва, ул. Искры, 31к1, офис 103А (приём блоков — по предварительной договорённости). Пн–пт 09:00–19:00.
- Ремонт снятых блоков (частотники, сервоприводы, ПЛК, панели, стойки ЧПУ): диагностика в мастерской бесплатно, в том числе для блоков, присланных транспортной компанией (1–3 дня), ремонт обычно до 3 дней, оплата после проверки блока, гарантия 3 месяца, приём со всей России транспортной компанией.
- Выезд на диагностику станка или линии — платный.
- Телефон, Telegram, WhatsApp: +7 926 883-09-39. Почта: info@panamaster.ru.
- Исполнитель: ООО «Интел-Сервис», ИНН 7723582307.

## Основные страницы

- [Главная]({SITE}/): услуги, сроки, отрасли, заявка.
- [Примеры работ]({SITE}/cases.html): реальные ремонты — что сломалось, что сделали, результат.
- [Контакты]({SITE}/contacts.html): телефон, мессенджеры, адрес мастерской, реквизиты.

## Отрасли

{chr(10).join(line(r) for r in industries)}

## Ремонт блоков в мастерской

{chr(10).join(line(r) for r in blocks)}

## Производители и виды оборудования

{chr(10).join(line(r) for r in hubs)}

## Кейсы

{chr(10).join(line(r) for r in cases)}
'''


def main():
    rels = pages()
    with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(build_sitemap(rels))
    with open(os.path.join(ROOT, 'llms.txt'), 'w', encoding='utf-8') as f:
        f.write(build_llms(rels))
    print(f'sitemap.xml: {len(rels)} страниц; llms.txt готов')


if __name__ == '__main__':
    main()
