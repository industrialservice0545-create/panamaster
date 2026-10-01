"""Генерация страниц кейсов из assets/data/cases.json.

Создаёт/пересобирает:
  cases/{slug}.html                 — страница кейса (утверждённый дизайн case.html)
  cases.html, cases-2.html…         — «Примеры работ», по 12 карточек, свежие сверху
  index.html                        — блок <!-- CASES_START -->…<!-- CASES_END --> (6 последних)
  services/industry-*.html          — блок <!-- CASES_START -->…<!-- CASES_END --> (кейсы отрасли)
  map.html                          — «Карта работ», если есть кейсы с координатами

Страницы брендов, видов оборудования и моделей появятся, когда по ним будет не меньше
MIN_CASES_FOR_HUB кейсов (одна страница на один кейс — это дубль страницы кейса).

Запуск из корня репозитория:  python3 bot/build_case_pages.py
Порядок полной сборки: build_industry_pages.py → build_case_pages.py → build_sitemap.py
"""
import html
import json
import math
import os
import re
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://panamaster.ru'
PER_PAGE = 12
HOME_CASES = 6
FAST_REPAIR_DAYS = 5          # срок показываем, только если ремонт действительно быстрый
MIN_CASES_FOR_HUB = 2
MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
          'августа', 'сентября', 'октября', 'ноября', 'декабря']


def ld_json(data):
    """JSON-LD для <script>: символы <, >, & заменяем на \\u-коды, чтобы текст кейса не закрыл тег script."""
    return (json.dumps(data, ensure_ascii=False, indent=2)
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))


def esc(s):
    return html.escape(str(s), quote=True)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path) or ROOT, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def load():
    cases = json.loads(read('assets/data/cases.json'))
    cases.sort(key=lambda c: (c['date'], c['slug']), reverse=True)
    d = json.loads(read('bot/dictionaries/entities.json'))
    industries = {i['slug']: i['human'] for i in d['industries']}
    types = {t['slug']: t['name'] for t in d['equipment_catalog']}
    return cases, industries, types


def load_hubs():
    return json.loads(read('bot/content/hubs.json'))


def brand_slug(brand, hubs):
    for slug, b in hubs['brands'].items():
        if brand.strip().upper() in [m.upper() for m in b['match']]:
            return slug
    return None


MONTHS_NOM = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль',
              'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']


def ru_date(iso):
    """«27 сентября 2026»; если известен только месяц (2026-06) — «июнь 2026», день не выдумываем."""
    parts = iso.split('-')
    if len(parts) == 2:
        return f'{MONTHS_NOM[int(parts[1]) - 1]} {parts[0]}'
    y, m, dd = parts
    return f'{int(dd)} {MONTHS[int(m) - 1]} {y}'


def fit(text, lo, hi):
    """Мета-текст в пределах lo..hi символов: обрезка по слову, без многоточия в середине фразы."""
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= hi:
        return text
    cut = text[:hi + 1].rsplit(' ', 1)[0].rstrip(',;:—-')
    return cut if len(cut) >= lo else text[:hi]


def first_sentence(text):
    m = re.match(r'(.+?[.!?])(\s|$)', text.strip())
    return (m.group(1) if m else text).strip()


def repair_days_text(c):
    n = c.get('repair_days')
    if not n or n > FAST_REPAIR_DAYS:
        return None
    word = 'рабочий день' if n == 1 else ('рабочих дня' if n in (2, 3, 4) else 'рабочих дней')
    return f'{n} {word}'


def title_of(c):
    """50–60 символов: сначала с сутью ремонта, для длинных моделей — «Ремонт {бренд} {модель}»."""
    bm = f'{c["brand"]} {c["model"]}'
    candidates = [f'{bm}: {c["headline"]} — Панамастер', f'{bm}: {c["headline"]}, Москва — Панамастер',
                  f'{bm}: {c["headline"]}', f'Ремонт {bm} в Москве — Панамастер',
                  f'Ремонт {bm} — Панамастер', f'Ремонт {bm} в Москве, гарантия 3 месяца',
                  f'Ремонт {bm}, Москва']
    for t in candidates:
        if 50 <= len(t) <= 60:
            return t
    fitting = [t for t in candidates if len(t) <= 60]
    return max(fitting, key=len) if fitting else fit(f'Ремонт {bm}', 20, 60)


def description_of(c):
    days = repair_days_text(c)
    if days:
        tail = f' Ремонт за {days}, гарантия 3 месяца.'
    elif c.get('format') == 'block':
        tail = ' Ремонт блока в мастерской, гарантия 3 месяца.'
    else:
        tail = ' Выезд за 24 часа, гарантия 3 месяца.'
    body = f'{c["brand"]} {c["model"]}: {c["headline"]}. {first_sentence(c["solution"])}'
    text = fit(body, 60, 160 - len(tail)) + tail
    if len(text) < 140:
        text = text[:-1] + ' с момента пусконаладки.'
    return fit(text, 140, 160)


def page_parts():
    idx = read('index.html')
    header = idx[idx.index('<header class="site-header">'):idx.index('</header>') + 9]
    header = header.replace(' class="is-active">Главная', '>Главная')
    footer = idx[idx.index('<footer class="site-footer">'):idx.index('</footer>') + 9].replace(' id="kontakty"', '')
    cta = idx[idx.index('        <section class="case-cta" id="zayavka">'):
              idx.index('        </section>', idx.index('class="case-cta"')) + len('        </section>')]
    return header, footer, cta


def head(title, desc, url, og_type, og_image):
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(desc)}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{url}">
    <link rel="stylesheet" href="/assets/css/main.css">
    <script src="/assets/js/main.js" defer></script>
    <link rel="icon" href="/favicon.ico" sizes="32x32">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">

    <meta property="og:type" content="{og_type}">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(desc)}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:locale" content="ru_RU">
    <meta property="og:site_name" content="Панамастер">
</head>
<body>
'''


def menu(header, active):
    h = header
    if active:
        h = h.replace(f'<a href="{active}">', f'<a href="{active}" class="is-active">', 1)
    return h


def photo_url(c, i):
    return f'/assets/img/cases/{c["slug"]}/{c["photos"][i]["file"]}'


def card(c, industries):
    ph = c['photos'][-1] if c['photos'] else None
    img = ''
    if ph:
        img = f'''
                    <a class="related-card__photo" href="/cases/{c["slug"]}.html" tabindex="-1" aria-hidden="true">
                        <figure class="case-photo">
                            <img src="/assets/img/cases/{c["slug"]}/{ph["file"]}" alt="{esc(ph["alt"])}" width="{ph["w"]}" height="{ph["h"]}" loading="lazy" decoding="async">
                        </figure>
                    </a>'''
    days = repair_days_text(c)
    time_line = f'\n                    <p class="related-card__time">{days}</p>' if days else ''
    return f'''<article class="related-card">{img}
                    <p class="related-card__meta">{esc(industries.get(c["industry"], ""))}</p>
                    <h3><a href="/cases/{c["slug"]}.html">{esc(c["brand"])} {esc(c["model"])}: {esc(c["headline"])}</a></h3>
                    <p>{esc(first_sentence(c["solution"]))}</p>{time_line}
                    <a class="related-card__link" href="/cases/{c["slug"]}.html">Читать кейс</a>
                </article>'''


def related_cases(c, cases):
    """Смежные: та же модель → тот же бренд → тот же вид → та же отрасль."""
    others = [o for o in cases if o['slug'] != c['slug']]
    keys = [lambda o: o['brand'] == c['brand'] and o['model'] == c['model'],
            lambda o: o['brand'] == c['brand'],
            lambda o: o['equipment_type'] == c['equipment_type'],
            lambda o: o['industry'] == c['industry']]
    picked = []
    for k in keys:
        for o in others:
            if k(o) and o not in picked:
                picked.append(o)
    return picked[:3]


def block_page_links(c):
    """Страницы раздела ремонта блоков (/blocks/), к которым относится кейс формата block: вид → бренд → модель."""
    path = os.path.join(ROOT, 'bot', 'content', 'blocks.json')
    links = []
    for p in json.load(open(path, encoding='utf-8'))['pages']:
        if p['slug'] != c['equipment_type']:
            continue
        links.append((f'/blocks/{p["slug"]}.html', f'Ремонт блоков: {p["name"].lower()}'))
        for b in p.get('brand_pages', []):
            if not any(m.lower() in c['brand'].lower() for m in b['match']):
                continue
            links.append((f'/blocks/{p["slug"]}/{b["slug"]}.html', b['h1']))
            for m in b.get('models', []):
                if m['match'].lower() in c['model'].lower():
                    links.append((f'/blocks/{p["slug"]}/{b["slug"]}/{m["slug"]}.html', m['h1']))
    return links


def render_case(c, cases, industries, types, parts):
    header, footer, cta = parts
    visit_fact = ('<p class="fact__label">Мастерская</p>\n                <p class="fact__value">Москва, ул. Искры, 31к1</p>'
                  if c.get('format') == 'block' else
                  '<p class="fact__label">Выезд</p>\n                <p class="fact__value">По Москве и МО</p>')
    url = f'{SITE}/cases/{c["slug"]}.html'
    title, desc = title_of(c), description_of(c)
    name = f'{c["brand"]} {c["model"]}'
    ind_name = industries.get(c['industry'], '')
    type_name = types.get(c['equipment_type'], '')
    days = repair_days_text(c)
    p1 = c['photos'][0] if c['photos'] else None
    p2 = c['photos'][1] if len(c['photos']) > 1 else None
    og = f'{SITE}{photo_url(c, len(c["photos"]) - 1)}' if c['photos'] else f'{SITE}/assets/img/industries/{c["industry"]}.webp'

    hero_photo = f'''
                <figure class="case-photo case-hero__photo">
                    <img src="{photo_url(c, 0)}"
                         alt="{esc(p1["alt"])}"
                         width="{p1["w"]}"
                         height="{p1["h"]}"
                         decoding="async"
                         fetchpriority="high">
                </figure>''' if p1 else ''

    rows = [('Производитель', c['brand'] + (f' ({c["brand_note"]})' if c.get('brand_note') else '')),
            ('Модель', c['model']), ('Вид оборудования', type_name), ('Отрасль', ind_name)]
    if c.get('rack'):
        rows.append(('Система управления', c['rack']))
    if c.get('servo'):
        rows.append(('Сервоприводы', c['servo']))
    if days:
        rows.append(('Срок ремонта', days))
    table = '\n'.join(f'                            <tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k, v in rows if v)
    specs_photo = f'''
                <figure class="case-photo case-specs__photo">
                    <img src="{photo_url(c, 1)}"
                         alt="{esc(p2["alt"])}"
                         width="{p2["w"]}"
                         height="{p2["h"]}"
                         loading="lazy"
                         decoding="async">
                </figure>''' if p2 else ''

    faq = [(f'{name} снова работает в штатном режиме?', f'Да. {c["result"]}'),
           ('Какая гарантия на этот ремонт?', '3 месяца с момента пусконаладки.'),
           ('Как оформляется работа?', 'Официальный договор, любая форма оплаты и полный комплект закрывающих документов.'),
           ('Как быстро можете выехать на похожую поломку?', 'По Москве и Московской области — в течение 24 часов. В другие регионы — по договорённости.')]
    if c.get('format') == 'block':
        faq[-1] = ('Можно привезти похожий блок в ремонт?',
                   'Да. Блоки принимаем в мастерской на ул. Искры, 31к1, по договорённости, из регионов — транспортной компанией. '
                   'Диагностика блока, привезённого в мастерскую, бесплатная.')
    if days:
        faq.insert(1, ('Сколько занял ремонт?', f'{days[0].upper()}{days[1:]} с момента диагностики до пусконаладки.'))
    faq_html = '\n'.join(f'''                <article>
                    <h3>{esc(q)}</h3>
                    <p>{esc(a)}</p>
                </article>''' for q, a in faq)

    rel = related_cases(c, cases)
    rel_html = ''
    if rel:
        rel_html = f'''
        <section class="case-block">
            <p class="section-label">Рядом по теме</p>
            <h2>Смежные примеры</h2>
            <div class="related-grid related-grid--cases">
                {chr(10).join('                ' + card(o, industries) for o in rel).strip()}
            </div>
        </section>
'''
    hubs = load_hubs()
    b_slug = brand_slug(c['brand'], hubs)
    tags = []
    if b_slug:
        tags.append(f'<a href="/services/brand-{b_slug}.html">Сервисный центр {esc(hubs["brands"][b_slug]["name"])}</a>')
    if c['equipment_type'] in hubs['types']:
        tags.append(f'<a href="/services/type-{c["equipment_type"]}.html">Ремонт: {esc(type_name.lower())}</a>')
    block_links = block_page_links(c) if c.get('format') == 'block' else []
    tags.extend(f'<a href="{href}">{esc(text)}</a>' for href, text in block_links)
    if os.path.exists(os.path.join(ROOT, 'services', f'industry-{c["industry"]}.html')):
        tags.append(f'<a href="/services/industry-{c["industry"]}.html">Ремонт оборудования: {esc(ind_name.lower())}</a>')
    model = hubs['models'].get(c['slug'])
    model_html = ''
    if model:
        paras = '\n'.join(f'                <p>{esc(p)}</p>' for p in model['about'])
        fails = '\n'.join(f'                <li>{esc(f)}</li>' for f in model['failures'])
        brand_link = f' Подробнее о ремонте оборудования производителя — на странице <a href="/services/brand-{b_slug}.html">сервисного центра {esc(hubs["brands"][b_slug]["name"])}</a>.' if b_slug else ''
        model_html = f'''
        <section class="case-block">
            <p class="section-label">Специализация</p>
            <h2>Ремонт {esc(name)}</h2>
            <div class="case-summary">
                <p>Ремонтируем электронику {esc(name)} и других машин этой серии: выезд в течение 24 часов по Москве и Московской области, диагностика — 1 рабочий день, гарантия — 3 месяца.{brand_link}</p>
            </div>
            <h3 class="hub-subtitle">{esc(model["about_title"])}</h3>
            <div class="case-summary">
{paras}
            </div>
            <h3 class="hub-subtitle">{esc(model["failures_title"])}</h3>
            <ul class="hub-list">
{fails}
            </ul>
        </section>
'''

    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': f'{SITE}/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Примеры работ', 'item': f'{SITE}/cases.html'},
            {'@type': 'ListItem', 'position': 3, 'name': name, 'item': url}]},
        {'@type': 'TechArticle', 'headline': f'{name}: {c["headline"]}', 'description': desc,
         'datePublished': c['date'], 'dateModified': c.get('updated') or c['date'], 'image': og,
         'author': {'@type': 'Organization', 'name': 'Панамастер', 'url': SITE},
         'publisher': {'@type': 'Organization', 'name': 'Панамастер',
                       'logo': {'@type': 'ImageObject', 'url': f'{SITE}/assets/img/logo.svg'}},
         'mainEntityOfPage': {'@type': 'WebPage', '@id': url}},
        {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q,
                                              'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]}]}

    page_cta = cta.replace('value="Главная"', f'value="{esc(name)} (кейс)"').replace('home-phone', 'case-phone') \
        .replace('<h2>Остановилась линия?</h2>', '<h2>Похожая поломка?</h2>')
    if c.get('format') == 'block':
        page_cta = (page_cta.replace('Оставьте телефон — перезвоним и скажем, когда сможем выехать.',
                                     'Оставьте телефон — перезвоним, скажем, берёмся ли за ремонт, и договоримся о приёме блока.')
                    .replace('Отправьте нам модель и дефект', 'Пришлите фото шильдика и описание неисправности'))
    return head(title, desc, url, 'article', og) + f'''
{menu(header, '/cases.html')}

<nav class="breadcrumbs" aria-label="Хлебные крошки">
    <div class="container">
        <a href="/">Главная</a>
        <span class="breadcrumbs__sep">→</span>
        <a href="/cases.html">Примеры работ</a>
        <span class="breadcrumbs__sep">→</span>
        <span aria-current="page">{esc(name)}</span>
    </div>
</nav>

<main>
    <div class="container">

        <section class="case-hero">
            <div class="case-hero__inner">
                <div class="case-hero__content">
                    <p class="case-hero__meta"><time datetime="{c["date"]}">{ru_date(c["date"])}</time></p>
                    <h1><span class="case-hero__line">{esc(name)}:</span><span class="case-hero__line">{esc(c["headline"])}</span></h1>
                    <div class="case-summary">
                        <p>{esc(c["defect"])}</p>
                        <p>{esc(c["solution"])}</p>
                        <p>Результат: {esc(c["result"][0].lower() + c["result"][1:])}</p>
                    </div>
                </div>{hero_photo}
            </div>
        </section>

{page_cta}

        <section class="case-specs">
            <div class="case-specs__inner">{specs_photo}
                <div class="case-specs__content">
                    <p class="section-label">Оборудование</p>
                    <h2>Характеристики</h2>
                    <table class="data-table">
                        <tbody>
{table}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <section class="case-facts" aria-label="Условия работы">
            <div class="fact">
                <p class="fact__label">Клиенты</p>
                <p class="fact__value">Компании и частные клиенты</p>
            </div>
            <div class="fact">
                <p class="fact__label">Документы</p>
                <p class="fact__value">Договор, любая форма оплаты</p>
            </div>
            <div class="fact">
                {visit_fact}
            </div>
            <div class="fact">
                <p class="fact__label">Гарантия</p>
                <p class="fact__value">3 месяца</p>
            </div>
        </section>

        <section class="case-result">
            <span class="case-result__check" aria-hidden="true"></span>
            <div class="case-result__content">
                <div class="case-result__row case-result__row--title">
                    <h2>Результат</h2>
                    <p class="case-result__figure">3 месяца</p>
                </div>
                <div class="case-result__row case-result__row--body">
                    <p>{esc(c["result"])}</p>
                    <p class="case-result__note">гарантия с момента пусконаладки</p>
                </div>
            </div>
        </section>

{model_html}
        <section class="case-block">
            <p class="section-label">Вопросы</p>
            <h2>Коротко для решения</h2>
            <div class="faq">
{faq_html}
            </div>
        </section>
{rel_html}
        <section class="case-block case-services">
            <h2 class="section-label">Связанные направления</h2>
            <div class="services-tags">
                {' '.join(tags)}
            </div>
            <div class="bottom-cta">
                <a href="/cases.html" class="btn btn--ghost">Смотреть все примеры работ</a>
                <a href="#zayavka" class="btn btn--primary">Оставить заявку</a>
            </div>
        </section>

    </div>
</main>

{footer}

<script type="application/ld+json">
{ld_json(ld)}
</script>

</body>
</html>
'''


def render_cases_list(page_cases, n, total, industries, parts):
    header, footer, cta = parts
    rel = 'cases.html' if n == 1 else f'cases-{n}.html'
    url = f'{SITE}/{rel}'
    title = 'Примеры работ по ремонту оборудования — Панамастер' if n == 1 else \
        f'Примеры работ по ремонту оборудования, стр. {n} — Панамастер'
    desc = 'Примеры ремонта промышленного оборудования Панамастер: что сломалось, что сделали и результат. Выезд за 24 часа по Москве и МО, гарантия 3 месяца.'
    if n > 1:
        desc = fit(f'Страница {n}. ' + desc, 140, 160)
    cards = '\n                '.join(card(c, industries) for c in page_cases)
    global MAP_LINK
    MAP_LINK = '''
                <div class="bottom-cta"><a href="/map.html" class="btn btn--ghost">Смотреть на карте</a></div>''' \
        if os.path.exists(os.path.join(ROOT, 'map.html')) else ''
    nav = ''
    if total > 1:
        prev_ = '' if n == 1 else f'<a href="/{"cases.html" if n == 2 else f"cases-{n - 1}.html"}" class="btn btn--ghost">Назад</a>'
        next_ = '' if n == total else f'<a href="/cases-{n + 1}.html" class="btn btn--ghost">Вперёд</a>'
        nav = f'\n            <div class="bottom-cta">{prev_}{next_}</div>'
    ld = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': f'{SITE}/'},
        {'@type': 'ListItem', 'position': 2, 'name': 'Примеры работ', 'item': f'{SITE}/cases.html'}]}
    og = f'{SITE}{photo_url(page_cases[0], len(page_cases[0]["photos"]) - 1)}' if page_cases and page_cases[0]['photos'] \
        else f'{SITE}/assets/img/industries/printing.webp'
    list_cta = cta.replace('value="Главная"', 'value="Примеры работ"').replace('home-phone', 'cases-phone')
    return head(title, desc, url, 'website', og) + f'''
{menu(header, '/cases.html')}

<nav class="breadcrumbs" aria-label="Хлебные крошки">
    <div class="container">
        <a href="/">Главная</a>
        <span class="breadcrumbs__sep">→</span>
        <span aria-current="page">Примеры работ</span>
    </div>
</nav>

<main>
    <div class="container">

        <section class="case-hero">
            <div class="case-hero__content">
                <h1>{"Примеры работ" if n == 1 else f"Примеры работ — страница {n}"}</h1>
                <div class="case-summary">
                    <p>Реальные ремонты: какое оборудование остановилось, что нашли на диагностике, что сделали и как машина работает после пусконаладки.</p>
                </div>{MAP_LINK}
            </div>
        </section>

        <section class="case-block">
            <div class="related-grid related-grid--cases">
                {cards}
            </div>{nav}
        </section>

{list_cta}

    </div>
</main>

{footer}

<script type="application/ld+json">
{ld_json(ld)}
</script>

</body>
</html>
'''


def render_hub(kind, slug, h, cases, industries, types, parts):
    """Посадочная бренда (kind='brand') или вида оборудования (kind='type')."""
    header, footer, cta = parts
    hubs = load_hubs()
    rel = f'services/{kind}-{slug}.html'
    url = f'{SITE}/{rel}'
    if kind == 'brand':
        own = [c for c in cases if brand_slug(c['brand'], hubs) == slug]
    else:
        own = [c for c in cases if c['equipment_type'] == slug]
    og = f'{SITE}{photo_url(own[0], len(own[0]["photos"]) - 1)}' if own and own[0]['photos'] else f'{SITE}/assets/img/industries/plastics.webp'
    lead = '\n'.join(f'                        <p>{esc(p)}</p>' for p in h['lead'])
    about = '\n'.join(f'                <p>{esc(p)}</p>' for p in h['about'])
    lines = '\n'.join(f'                <article class="related-card"><h3>{esc(a)}</h3><p>{esc(b)}</p></article>' for a, b in h['lines'])
    elec = '\n'.join(f'                <li>{esc(e)}</li>' for e in h['electronics'])
    faq = h['faq']
    faq_html = '\n'.join(f"""                <article>
                    <h3>{esc(q)}</h3>
                    <p>{esc(a)}</p>
                </article>""" for q, a in faq)
    cases_html = ''
    if own:
        cards = '\n                '.join(card(c, industries) for c in own[:6])
        cases_html = f"""
        <section class="case-block">
            <p class="section-label">Примеры работ</p>
            <h2>Выполненные ремонты</h2>
            <div class="related-grid related-grid--cases">
                {cards}
            </div>
        </section>
"""
    brands_html = ''
    if kind == 'type' and h.get('brands_text'):
        brand_links = ''.join(f' <a href="/services/brand-{b}.html">Сервисный центр {esc(v["name"])}</a>'
                              for b, v in hubs['brands'].items()
                              if any(brand_slug(c['brand'], hubs) == b for c in own))
        brands_html = f"""
        <section class="case-block">
            <p class="section-label">Производители</p>
            <h2>{esc(h["brands_title"])}</h2>
            <div class="case-summary"><p>{esc(h["brands_text"])}</p></div>{f'<div class="services-tags">{brand_links}</div>' if brand_links else ''}
        </section>
"""
    links = []
    if kind == 'brand':
        for t in sorted({c['equipment_type'] for c in own}):
            if t in hubs['types']:
                links.append(f'<a href="/services/type-{t}.html">Ремонт: {esc(types.get(t, t).lower())}</a>')
        for i in sorted({c['industry'] for c in own}):
            links.append(f'<a href="/services/industry-{i}.html">{esc(industries.get(i, i))}</a>')
    else:
        for i in h.get('industries', []):
            links.append(f'<a href="/services/industry-{i}.html">{esc(industries.get(i, i))}</a>')
    crumb = h['name'] if kind == 'brand' else h['name']
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': f'{SITE}/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Услуги', 'item': f'{SITE}/#uslugi'},
            {'@type': 'ListItem', 'position': 3, 'name': crumb, 'item': url}]},
        {'@type': 'Service', 'name': h['h1'], 'serviceType': 'Ремонт промышленного оборудования', 'url': url,
         'areaServed': [{'@type': 'City', 'name': 'Москва'}, {'@type': 'AdministrativeArea', 'name': 'Московская область'}],
         'provider': {'@type': 'ProfessionalService', 'name': 'Панамастер', 'url': f'{SITE}/', 'telephone': '+7-926-883-09-39'}},
        {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]}]}
    page_cta = cta.replace('value="Главная"', f'value="{esc(h["h1"])}"').replace('home-phone', f'{kind}-phone')
    html_ = head(h['title'], h['desc'], url, 'website', og) + f"""
{menu(header, None)}

<nav class="breadcrumbs" aria-label="Хлебные крошки">
    <div class="container">
        <a href="/">Главная</a>
        <span class="breadcrumbs__sep">→</span>
        <a href="/#uslugi">Услуги</a>
        <span class="breadcrumbs__sep">→</span>
        <span aria-current="page">{esc(crumb)}</span>
    </div>
</nav>

<main>
    <div class="container">

        <section class="case-hero">
            <div class="case-hero__content">
                <p class="case-hero__meta">{"Производитель" if kind == "brand" else "Вид оборудования"} · Москва и Московская область</p>
                <h1>{esc(h["h1"])}</h1>
                <div class="case-summary">
{lead}
                </div>
                <div class="bottom-cta">
                    <a href="tel:+79268830939" class="btn btn--primary">Позвонить: +7 926 883-09-39</a>
                    <a href="#zayavka" class="btn btn--ghost">Оставить заявку</a>
                </div>
            </div>
        </section>

        <section class="case-block">
            <p class="section-label">{esc(h["about_title"])}</p>
            <div class="case-summary">
{about}
            </div>
        </section>

        <section class="case-block">
            <p class="section-label">Оборудование</p>
            <h2>{esc(h["lines_title"])}</h2>
            <div class="related-grid related-grid--3">
{lines}
            </div>
        </section>

        <section class="case-block">
            <p class="section-label">Неисправности</p>
            <h2>{esc(h["electronics_title"])}</h2>
            <ul class="hub-list">
{elec}
            </ul>
        </section>
{brands_html}{cases_html}
{page_cta}

        <section class="case-block">
            <p class="section-label">Вопросы</p>
            <h2>Коротко для решения</h2>
            <div class="faq">
{faq_html}
            </div>
        </section>

        <section class="case-block case-services">
            <h2 class="section-label">Связанные направления</h2>
            <div class="services-tags">
                {" ".join(links)}
            </div>
        </section>

    </div>
</main>

{footer}

<script type="application/ld+json">
{ld_json(ld)}
</script>

</body>
</html>
"""
    write(rel, html_)
    return rel


def render_map(cases, industries, parts):
    """«Карта работ»: метки кейсов с координатами (округлены до ~1 км), ссылки на кейсы."""
    header, footer, cta = parts
    pts = [c for c in cases if c.get('lat') and c.get('lon')]
    # только координаты: на карте нет сведений об оборудовании (решение владельца 28.09.2026)
    points = [{'lat': c['lat'], 'lon': c['lon']} for c in pts]
    areas = sorted({c.get('area') for c in pts if c.get('area')})
    title = 'Карта работ: ремонты оборудования в Москве и МО — Панамастер'
    if len(title) > 60:
        title = 'Карта работ по ремонту оборудования — Панамастер'
    n = len(pts)
    word = 'объект' if n % 10 == 1 and n % 100 != 11 else 'объекта' if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else 'объектов'
    desc = fit(f'Карта выполненных ремонтов промышленного оборудования Панамастер в Москве и Московской области: {n} {word}. Выезд за 24 часа, гарантия 3 месяца.', 140, 160)
    cards = '\n                '.join(card(c, industries) for c in pts)
    ld = {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': f'{SITE}/'},
        {'@type': 'ListItem', 'position': 2, 'name': 'Примеры работ', 'item': f'{SITE}/cases.html'},
        {'@type': 'ListItem', 'position': 3, 'name': 'Карта работ', 'item': f'{SITE}/map.html'}]}
    area_text = ''
    return head(title, desc, f'{SITE}/map.html', 'website', f'{SITE}/assets/img/industries/metalworking.webp') + f"""
{menu(header, '/cases.html')}

<nav class="breadcrumbs" aria-label="Хлебные крошки">
    <div class="container">
        <a href="/">Главная</a>
        <span class="breadcrumbs__sep">→</span>
        <a href="/cases.html">Примеры работ</a>
        <span class="breadcrumbs__sep">→</span>
        <span aria-current="page">Карта работ</span>
    </div>
</nav>

<main>
    <div class="container">

        <section class="case-hero">
            <div class="case-hero__content">
                <h1>Карта работ</h1>
                <div class="case-summary">
                    <p>Где мы ремонтировали оборудование: {len(pts)} {"объект" if len(pts) == 1 else "объекта" if len(pts) in (2, 3, 4) else "объектов"} в Москве и Московской области.{esc(area_text)} Каждая точка — место, где мы восстановили работу оборудования.</p>
                </div>
            </div>
            <div class="map map--works" id="works-map" role="region" aria-label="Карта выполненных ремонтов"
                 data-points="{esc(json.dumps(points, ensure_ascii=False))}"></div>
        </section>

        <section class="case-block">
            <div class="bottom-cta">
                <a href="/cases.html" class="btn btn--ghost">Примеры работ</a>
            </div>
        </section>

{cta.replace('value="Главная"', 'value="Карта работ"').replace('home-phone', 'map-phone')}

    </div>
</main>

{footer}

<script type="application/ld+json">
{ld_json(ld)}
</script>

</body>
</html>
"""


def replace_block(text, block):
    a = text.index('<!-- CASES_START -->')
    b = text.index('<!-- CASES_END -->') + len('<!-- CASES_END -->')
    return text[:a] + block + text[b:]


def cases_block(items, industries, title, more=True):
    if not items:
        return '<!-- CASES_START -->\n        <!-- CASES_END -->'
    cards = '\n                '.join(card(c, industries) for c in items)
    more_html = '''
            <div class="bottom-cta">
                <a href="/cases.html" class="btn btn--ghost">Все примеры работ</a>
            </div>''' if more else ''
    return f'''<!-- CASES_START -->
        <section class="case-block">
            <p class="section-label">Примеры работ</p>
            <h2>{title}</h2>
            <div class="related-grid related-grid--cases">
                {cards}
            </div>{more_html}
        </section>
        <!-- CASES_END -->'''


def build():
    cases, industries, types = load()
    parts = page_parts()
    written = []
    for c in cases:
        write(f'cases/{c["slug"]}.html', render_case(c, cases, industries, types, parts))
        written.append(f'cases/{c["slug"]}.html')

    if any(c.get('lat') for c in cases):
        write('map.html', render_map(cases, industries, parts))
        written.append('map.html')

    elif os.path.exists(os.path.join(ROOT, 'map.html')):
        os.remove(os.path.join(ROOT, 'map.html'))

    pages = max(1, math.ceil(len(cases) / PER_PAGE))
    for n in range(1, pages + 1):
        rel = 'cases.html' if n == 1 else f'cases-{n}.html'
        write(rel, render_cases_list(cases[(n - 1) * PER_PAGE:n * PER_PAGE], n, pages, industries, parts))
        written.append(rel)
    n = pages + 1
    while os.path.exists(os.path.join(ROOT, f'cases-{n}.html')):   # лишние страницы пагинации
        os.remove(os.path.join(ROOT, f'cases-{n}.html'))
        n += 1

    hubs = load_hubs()
    for slug, h in hubs['brands'].items():
        if any(brand_slug(c['brand'], hubs) == slug for c in cases):
            written.append(render_hub('brand', slug, h, cases, industries, types, parts))
    for slug, h in hubs['types'].items():
        if any(c['equipment_type'] == slug for c in cases):
            written.append(render_hub('type', slug, h, cases, industries, types, parts))

    write('index.html', replace_block(read('index.html'), cases_block(cases[:HOME_CASES], industries, 'Последние ремонты')))
    written.append('index.html')

    for slug in industries:
        rel = f'services/industry-{slug}.html'
        if not os.path.exists(os.path.join(ROOT, rel)):
            continue
        t = read(rel)
        if '<!-- CASES_START -->' not in t:
            continue
        own = [c for c in cases if c['industry'] == slug]
        write(rel, replace_block(t, cases_block(own[:6], industries, 'Ремонты в отрасли', more=True)))
        written.append(rel)
    return written


if __name__ == '__main__':
    out = build()
    print(f'готово: {len(out)} файлов ({date.today().isoformat()})')
