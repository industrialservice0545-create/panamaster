"""Раздел «Ремонт блоков в мастерской»: /blocks.html и /blocks/{type}.html.

Второе направление сайта (решение владельца 29.09.2026): компонентный ремонт снятых блоков —
для инженеров, которые сами сняли и привезли блок. Главная и отрасли остаются про выезд.
Тексты — bot/content/blocks.json (только подтверждённые владельцем факты), каркас — шапка,
подвал и форма с главной, компоненты — из утверждённых case.html/main.css.

Запуск из корня репозитория:  python3 bot/build_block_pages.py
"""
import glob
import html
import sys
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://panamaster.ru'

sys.path.insert(0, os.path.join(ROOT, 'bot'))
import build_case_pages as cases_gen   # карточки кейсов — та же разметка, что на главной и в отраслях


def load_content(name):
    """JSON из bot/content/ с подстановкой цен {PRICE_BLOCK} / {PRICE_VISIT} из build_case_pages."""
    raw = open(os.path.join(ROOT, 'bot', 'content', name), encoding='utf-8').read()
    return json.loads(raw.replace('{PRICE_BLOCK}', cases_gen.rub(cases_gen.PRICE_BLOCK))
                         .replace('{PRICE_VISIT}', cases_gen.rub(cases_gen.PRICE_VISIT)))


CONTENT = load_content('blocks.json')


def block_cases(type_slug, brand=None, model=None):
    """Кейсы для страницы вида / бренда / модели, свежие сверху: формата «блок» этого вида, а для страниц
    брендов сервоприводов — ещё и ремонты станков, где стоял привод этого бренда (поле servo)."""
    cases, industries, _ = cases_gen.load()
    own = [c for c in cases if c.get('format') == 'block' and c['equipment_type'] == type_slug]
    if brand:
        own = [c for c in own if any(m.lower() in c['brand'].lower() for m in brand['match'])]
        if brand.get('servo_brand'):
            own += [c for c in cases if c.get('format', 'machine') == 'machine'
                    and cases_gen.servo_brand(c.get('servo')) == brand['servo_brand']]
    if model:
        own = [c for c in own if model['match'].lower() in c['model'].lower()]
    return own, industries
HUB_NAME = 'Ремонт блоков в мастерской'


def ld_json(data):
    """JSON-LD для <script>: символы <, >, & заменяем на \\u-коды, чтобы текст кейса не закрыл тег script."""
    return (json.dumps(data, ensure_ascii=False, indent=2)
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))


def esc(s):
    return html.escape(s, quote=True)


def chrome():
    """Шапка, подвал, форма и данные организации — с главной, чтобы не расходились."""
    idx = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    header = idx[idx.index('<header class="site-header">'):idx.index('</header>') + 9].replace(' class="is-active">Главная', '>Главная')
    footer = idx[idx.index('<footer class="site-footer">'):idx.index('</footer>') + 9].replace(' id="kontakty"', '')
    start = idx.index('        <section class="case-cta" id="zayavka">')
    cta = idx[start:idx.index('        </section>', start) + len('        </section>')]
    cta = (cta.replace('<h2>Остановилась линия?</h2>', '<h2>Сняли блок?</h2>')
              .replace('Оставьте телефон — перезвоним и скажем, когда сможем выехать.',
                       'Оставьте телефон — перезвоним, скажем, берёмся ли за ремонт, и договоримся о приёме блока.')
              .replace('Отправьте нам модель и дефект', 'Пришлите фото шильдика и описание неисправности'))
    org = json.loads(re.search(r'ld\+json">(.*?)</script>', idx, re.S).group(1))
    org.pop('@context', None)
    return header, footer, cta, org


def facts_html():
    items = '\n'.join(f'''            <div class="fact">
                <p class="fact__label">{esc(k)}</p>
                <p class="fact__value">{esc(v)}</p>
            </div>''' for k, v in CONTENT['facts'])
    return f'        <section class="case-facts" aria-label="Сроки, оплата и гарантия">\n{items}\n        </section>'


def steps_html():
    items = '\n'.join(f'                <li><strong>{esc(k)}</strong><span>{esc(v)}</span></li>' for k, v in CONTENT['steps'])
    return f'''        <section class="case-block">
            <p class="section-label">Как сдать блок</p>
            <h2>От заявки до проверенного блока</h2>
            <ol class="steps-list">
{items}
            </ol>
        </section>'''


def faq_html(faq, title='Коротко о ремонте блоков'):
    items = '\n'.join(f'''                <article>
                    <h3>{esc(q)}</h3>
                    <p>{esc(a)}</p>
                </article>''' for q, a in faq)
    return f'''        <section class="case-block">
            <p class="section-label">Вопросы</p>
            <h2>{esc(title)}</h2>
            <div class="faq">
{items}
            </div>
        </section>'''


BRIDGE = '''        <section class="case-block">
            <p class="section-label">Выезд на производство</p>
            <h2>Не можете снять блок или не знаете, что сломалось?</h2>
            <div class="case-summary">
                <p>Выедем на производство по Москве и Московской области в течение 24 часов, найдём неисправность на месте и запустим оборудование. Гарантия — 3 месяца на работы, 1 год на новые блоки и модули.</p>
                <p><a class="related-card__link" href="/services.html#na-obekte">Работы на вашем производстве</a></p>
            </div>
        </section>'''


def page_html(*, url, title, desc, crumbs, meta, h1, lead, body, faq, header, footer, cta, org, form_page, form_id,
              cases_html='<!-- CASES_START -->\n        <!-- CASES_END -->', facts_block=None, bridge=None,
              service_type='Ремонт промышленной электроники', faq_title='Коротко о ремонте блоков',
              min_price=cases_gen.PRICE_BLOCK, main_entity=None):
    crumbs_html = '\n'.join(
        (f'        <a href="{href}">{esc(name)}</a>\n        <span class="breadcrumbs__sep">→</span>' if href
         else f'        <span aria-current="page">{esc(name)}</span>') for name, href in crumbs)
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': name, 'item': SITE + (href or url[len(SITE):])}
            for i, (name, href) in enumerate(crumbs)]},
        main_entity or {'@type': 'Service', 'name': h1, 'serviceType': service_type,
         'areaServed': [{'@type': 'City', 'name': 'Москва'}, {'@type': 'Country', 'name': 'Россия'}],
         'provider': org, 'url': url,
         'offers': {'@type': 'Offer', 'priceCurrency': 'RUB',
                    'priceSpecification': {'@type': 'PriceSpecification', 'minPrice': min_price,
                                           'priceCurrency': 'RUB'}}},
        {'@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]},
    ]}
    page_cta = cta.replace('value="Главная"', f'value="{esc(form_page)}"').replace('home-phone', form_id)
    lead_html = '\n'.join(f'                    <p>{esc(p)}</p>' for p in lead)
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

    <meta property="og:type" content="website">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(desc)}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{SITE}/assets/img/cases/cms-br5-302/photo-2.webp">
    <meta property="og:locale" content="ru_RU">
    <meta property="og:site_name" content="Панамастер">
</head>
<body>

{header}

<nav class="breadcrumbs" aria-label="Хлебные крошки">
    <div class="container">
{crumbs_html}
    </div>
</nav>

<main>
    <div class="container">

        <section class="case-hero">
            <div class="case-hero__content">
                <p class="case-hero__meta">{esc(meta)}</p>
                <h1>{esc(h1)}</h1>
                <div class="case-summary">
{lead_html}
                </div>
                <div class="bottom-cta">
                    <a href="tel:+79268830939" class="btn btn--primary">Позвонить: +7 926 883-09-39</a>
                    <a href="#zayavka" class="btn btn--ghost">Оставить заявку</a>
                </div>
{cases_gen.PHOTO_CTA}
            </div>
        </section>

{facts_block if facts_block is not None else facts_html()}

{body}

{page_cta}

        {cases_html}

{faq_html(faq, faq_title)}

{BRIDGE if bridge is None else bridge}

    </div>
</main>

{footer}

<script type="application/ld+json">
{ld_json(ld)}
</script>

</body>
</html>
'''


def type_body(p):
    what = '\n'.join(f'''                <article class="related-card">
                    <h3>{esc(k)}</h3>
                    <p>{esc(v)}</p>
                </article>''' for k, v in p['what'])
    faults = '\n'.join(f'                <li>{esc(f)}</li>' for f in p['faults'])
    def brand_title(name):
        for b in p.get('brand_pages', []):
            if ',' not in name and any(m.lower() in name.lower() for m in b['match']):
                return f'<a href="/blocks/{p["slug"]}/{b["slug"]}.html">{esc(name)}</a>'
        return esc(name)
    brands = '\n'.join(f'''                <article class="related-card">
                    <h3>{brand_title(k)}</h3>
                    <p>{esc(v)}</p>
                </article>''' for k, v in p['brands'])
    others = '\n'.join(f'                <a href="/blocks/{o["slug"]}.html">{esc(o["name"])}</a>'
                       for o in CONTENT['pages'] if o is not p)
    return f'''        <section class="case-block">
            <p class="section-label">Что ремонтируем</p>
            <h2>Компонентный ремонт, а не замена плат</h2>
            <div class="related-grid related-grid--3">
{what}
            </div>
        </section>

        <section class="case-block">
            <p class="section-label">Неисправности</p>
            <h2>С чем приносят в ремонт</h2>
            <ul class="hub-list">
{faults}
            </ul>
        </section>

        <section class="case-block">
            <p class="section-label">Производители</p>
            <h2>Марки и серии</h2>
            <div class="related-grid related-grid--3">
{brands}
            </div>
        </section>

{brand_links_html(p)}{steps_html()}

        <section class="case-block case-services">
            <h2 class="section-label">Другие блоки</h2>
            <div class="services-tags">
                <a href="/blocks.html">Все виды блоков</a>
{others}
            </div>
        </section>'''


def brand_links_html(p):
    if not p.get('brand_pages'):
        return ''
    links = '\n'.join(f'                <a href="/blocks/{p["slug"]}/{b["slug"]}.html">{esc(b["h1"])}</a>'
                      for b in p['brand_pages'])
    return f'''        <section class="case-block case-services">
            <h2 class="section-label">Ремонт по брендам</h2>
            <div class="services-tags">
{links}
            </div>
        </section>

'''


def up_links(items):
    links = '\n'.join(f'                <a href="{href}">{esc(name)}</a>' for href, name in items)
    return f'''        <section class="case-block case-services">
            <h2 class="section-label">Смотрите также</h2>
            <div class="services-tags">
{links}
            </div>
        </section>'''


def faults_html(faults):
    items = '\n'.join(f'                <li>{esc(f)}</li>' for f in faults)
    return f'''        <section class="case-block">
            <p class="section-label">Неисправности</p>
            <h2>С чем приносят в ремонт</h2>
            <ul class="hub-list">
{items}
            </ul>
        </section>'''


def brand_body(p, b):
    series = '\n'.join(f'''                <article class="related-card">
                    <h3>{esc(k)}</h3>
                    <p>{esc(v)}</p>
                </article>''' for k, v in b['series'])
    models = [(f'/blocks/{p["slug"]}/{b["slug"]}/{m["slug"]}.html', m['h1']) for m in b.get('models', [])]
    return f'''        <section class="case-block">
            <p class="section-label">Серии</p>
            <h2>Что ремонтируем у {esc(b["name"])}</h2>
            <div class="related-grid related-grid--3">
{series}
            </div>
        </section>

{faults_html(b["faults"])}

{steps_html()}

{up_links(models + [(f'/blocks/{p["slug"]}.html', p['h1']), ('/blocks.html', 'Все виды блоков')])}'''


def model_body(p, b, m):
    return f'''{faults_html(m["faults"])}

{steps_html()}

{up_links([(f'/blocks/{p["slug"]}/{b["slug"]}.html', b['h1']), (f'/blocks/{p["slug"]}.html', p['h1']), ('/blocks.html', 'Все виды блоков')])}'''


def hub_body():
    cards = '\n'.join(f'''                <article class="related-card">
                    <h3><a href="/blocks/{p["slug"]}.html">{esc(p["name"])}</a></h3>
                    <p>{esc(p["card"])}</p>
                </article>''' for p in CONTENT['pages'])
    return f'''        <section class="case-block">
            <p class="section-label">Что принимаем</p>
            <h2>Какие блоки ремонтируем</h2>
            <div class="related-grid related-grid--3">
{cards}
                <article class="related-card">
                    <h3>Блоки питания и платы</h3>
                    <p>Импульсные источники питания, платы управления и силовые модули.</p>
                </article>
            </div>
            <p class="case-cta__sub">{esc(CONTENT['hub']['brands'])}</p>
        </section>

{steps_html()}'''


def add_auto_servo_brands():
    """Страницы «Ремонт сервоприводов [бренд]» по кейсам станков, где известен привод (поле servo).
    Только факты из кейсов; ручные страницы из blocks.json (Rexroth) не трогаем."""
    page = next((p for p in CONTENT['pages'] if p['slug'] == 'drives-servo'), None)
    if not page:
        return
    cases, _, _ = cases_gen.load()
    page.setdefault('brand_pages', [])
    have = {b['slug'] for b in page['brand_pages']}
    have_names = {m.lower() for b in page['brand_pages'] for m in b['match']}
    by_brand = {}
    for c in cases:
        name = cases_gen.servo_brand(c.get('servo')) if c.get('format', 'machine') == 'machine' else None
        if name and name.lower() not in have_names:
            by_brand.setdefault(name, []).append(c)
    for name, own in sorted(by_brand.items()):
        slug = cases_gen.slug_of(name)
        if slug in have:
            continue
        servos = sorted({c['servo'] for c in own})
        page['brand_pages'].append({
            'slug': slug, 'name': name, 'match': [name], 'servo_brand': name, 'auto': True,
            'title': cases_gen.fit(f'Ремонт сервоприводов {name} в Москве — Панамастер', 30, 60),
            'h1': f'Ремонт сервоприводов {name}',
            'desc': cases_gen.fit(f'Ремонт сервоприводов {name} ({", ".join(servos)}): компонентный ремонт и настройка '
                                  'на станке. Диагностика в мастерской бесплатно, гарантия 3 месяца.', 120, 160),
            'lead': [f'Ремонтируем сервоприводы {name} ({", ".join(servos)}) на уровне компонентов: силовую часть, '
                     'платы управления и питания, цепи обратной связи. При необходимости настраиваем привод на станке.',
                     'Привезите блок в мастерскую на ул. Искры, 31к1 или отправьте транспортной компанией. '
                     'Если блок не снять — выедем на производство.'],
            'series': [[v, f'Работали на {c["brand"]} {c["model"]}'] for c in own for v in [c['servo']]],
            'faults': [f'{c["brand"]} {c["model"]}: {c["headline"]}.' for c in own],
            'faq': [[f'Ремонтируете сервоприводы {name}?',
                     f'Да. Например, {servos[0]} на {own[0]["brand"]} {own[0]["model"]} — пример ниже на странице.']],
            'models': [],
        })


SERVICES = load_content('services.json')


def service_body(sp):
    """Тело посадочной из services.json. Разделы «Признаки / Услуга / Порядок работ / Выбор» —
    подписи и заголовки из JSON; steps, repair и отзывы (reviews: true) — необязательные."""
    def card(item):
        k, v, href = (list(item) + [None])[:3]
        title = f'<a href="{href}">{esc(k)}</a>' if href else esc(k)
        return f'''                <article class="related-card">
                    <h3>{title}</h3>
                    <p>{esc(v)}</p>
                </article>'''
    when = '\n'.join(f'                <li>{esc(x)}</li>' for x in sp['when'])
    what = '\n'.join(card(x) for x in sp['what'])
    links = '\n'.join(f'                <a href="{href}">{esc(name)}</a>' for href, name in sp['links'])
    parts = [f'''        <section class="case-block">
            <p class="section-label">{esc(sp.get("when_label", "Признаки"))}</p>
            <h2>{esc(sp["when_title"])}</h2>
            <ul class="hub-list">
{when}
            </ul>
        </section>''', f'''        <section class="case-block">
            <p class="section-label">{esc(sp.get("what_label", "Услуга"))}</p>
            <h2>{esc(sp["what_title"])}</h2>
            <div class="related-grid related-grid--3">
{what}
            </div>
        </section>''']
    if sp.get('steps'):
        steps = '\n'.join(f'                <li><strong>{esc(k)}</strong><span>{esc(v)}</span></li>' for k, v in sp['steps'])
        parts.append(f'''        <section class="case-block">
            <p class="section-label">Порядок работ</p>
            <h2>{esc(sp["steps_title"])}</h2>
            <ol class="steps-list">
{steps}
            </ol>
        </section>''')
    if sp.get('repair'):
        repair = '\n'.join(f'                <p>{esc(x)}</p>' for x in sp['repair'])
        parts.append(f'''        <section class="case-block">
            <p class="section-label">{esc(sp.get("repair_label", "Выбор"))}</p>
            <h2>{esc(sp["repair_title"])}</h2>
            <div class="case-summary">
{repair}
            </div>
        </section>''')
    if sp.get('reviews'):
        import build_reviews
        parts.append('        ' + build_reviews.block(json.load(open(build_reviews.DATA, encoding='utf-8')), about_link=False))
    parts.append(f'''        <section class="case-block case-services">
            <h2 class="section-label">Смотрите также</h2>
            <div class="services-tags">
{links}
            </div>
        </section>''')
    return '\n\n'.join(parts)


def service_facts(sp):
    items = '\n'.join(f'''            <div class="fact">
                <p class="fact__label">{esc(k)}</p>
                <p class="fact__value">{esc(v)}</p>
            </div>''' for k, v in sp['facts'])
    return f'        <section class="case-facts" aria-label="Условия работы">\n{items}\n        </section>'


def build_service_pages(common):
    """Посадочные услуг из bot/content/services.json (модернизация и др.) → services/{slug}.html."""
    pages = {}
    for sp in SERVICES['pages']:
        cta = common['cta'].replace('<h2>Сняли блок?</h2>', f'<h2>{esc(sp["cta_title"])}</h2>').replace(
            'Оставьте телефон — перезвоним, скажем, берёмся ли за ремонт, и договоримся о приёме блока.',
            esc(sp['cta_text']))
        rel = sp.get('path', f'services/{sp["slug"]}.html')
        url = f'{SITE}/{rel}'
        about = {'@type': 'AboutPage', 'name': sp['h1'], 'url': url, 'about': common['org']} \
            if sp.get('kind') == 'about' else None
        pages[rel] = page_html(
            url=url, title=sp['title'], desc=sp['desc'], main_entity=about,
            crumbs=[('Главная', '/'), (sp['name'], None)], meta=sp['meta'], h1=sp['h1'], lead=sp['lead'],
            body=service_body(sp), faq=sp['faq'], form_page=sp['name'], form_id=f'service-{sp["slug"]}-phone',
            facts_block=service_facts(sp), bridge='', service_type=sp['name'], faq_title=sp['faq_title'],
            min_price=cases_gen.PRICE_VISIT,
            header=common['header'], footer=common['footer'], cta=cta, org=common['org'])
    return pages


def catalog_cards(items):
    """Карточки каталога: (название, текст, ссылка) — заголовок карточки и есть ссылка."""
    return '\n'.join(f'''                <article class="related-card">
                    <h3><a href="{href}">{esc(name)}</a></h3>
                    <p>{esc(text)}</p>
                </article>''' for name, text, href in items)


def catalog_section(label, title, items, anchor=None, grid='related-grid related-grid--3'):
    aid = f' id="{anchor}"' if anchor else ''
    return f'''        <section class="case-block"{aid}>
            <p class="section-label">{esc(label)}</p>
            <h2>{esc(title)}</h2>
            <div class="{grid}">
{catalog_cards(items)}
            </div>
        </section>'''


def build_catalog_pages(common):
    """Каталоги /services.html (все услуги) и /industries.html (все отрасли): ссылки на существующие страницы."""
    pages = {}
    on_site = [(sp['name'], sp['desc'], f'/services/{sp["slug"]}.html') for sp in SERVICES['pages'] if sp.get('kind') != 'about']
    order = ['emergency', 'cnc-repair', 'commissioning', 'modernization', 'plc-programming']
    on_site.sort(key=lambda x: next((i for i, o in enumerate(order) if x[2].endswith(f'/{o}.html')), 99))
    workshop = [(HUB_NAME, CONTENT['hub']['desc'], '/blocks.html')] + \
        [(p['name'], p['desc'], f'/blocks/{p["slug"]}.html') for p in CONTENT['pages']]
    body = '\n\n'.join([
        catalog_section('На вашем производстве', 'Выезд инженера на производство', on_site, 'na-obekte'),
        catalog_section('В мастерской', 'Ремонт снятых электронных блоков', workshop, 'v-masterskoy'),
        '''        <section class="case-block case-services">
            <h2 class="section-label">Ещё разделы</h2>
            <div class="bottom-cta">
                <a href="/equipment.html" class="btn btn--ghost">Виды оборудования</a>
                <a href="/brands.html" class="btn btn--ghost">Производители оборудования</a>
                <a href="/electronics-brands.html" class="btn btn--ghost">Производители электроники</a>
                <a href="/industries.html" class="btn btn--ghost">Отрасли</a>
            </div>
        </section>'''])
    url = f'{SITE}/services.html'
    cta = common['cta'].replace('<h2>Сняли блок?</h2>', '<h2>Не знаете, что выбрать?</h2>').replace(
        'Оставьте телефон — перезвоним, скажем, берёмся ли за ремонт, и договоримся о приёме блока.',
        'Оставьте телефон — перезвоним и подскажем: нужен выезд или ремонт блока в мастерской.')
    pages['services.html'] = page_html(
        url=url, title='Услуги: ремонт электроники оборудования — Панамастер',
        desc='Все услуги Панамастер: аварийный выезд, ремонт станков с ЧПУ, пусконаладка, модернизация, программирование ПЛК и ремонт электронных блоков в мастерской.',
        crumbs=[('Главная', '/'), ('Услуги', None)], meta='Москва и Московская область · с 2006 года',
        h1='Услуги Панамастер', lead=[
            'Ремонтируем и настраиваем электронику промышленного оборудования двумя способами: инженер выезжает на ваше производство или вы привозите снятый блок в мастерскую.',
            'Выберите, что нужно сделать, или позвоните — подскажем по фото шильдика и ошибки.'],
        body=body, facts_block='', bridge='', cases_html='', form_page='Услуги', form_id='services-phone',
        faq=[('Чем отличается ремонт на объекте от ремонта в мастерской?',
              'На объекте инженер приезжает на производство, находит причину и ремонтирует электронику станка или линии; выезд платный. В мастерскую вы привозите или присылаете снятый блок; диагностика блока бесплатная.'),
             ('Не знаете, какая услуга нужна?', 'Позвоните или пришлите в мессенджер фото шильдика и экрана с ошибкой — подскажем, что нужно: выезд или ремонт блока.')],
        faq_title='Коротко об услугах', main_entity={'@type': 'CollectionPage', 'name': 'Услуги Панамастер', 'url': url, 'about': common['org']},
        cta=cta, **{k: common[k] for k in ('header', 'footer', 'org')})
    inds = json.load(open(os.path.join(ROOT, 'bot', 'content', 'industries.json'), encoding='utf-8'))['industries']
    url = f'{SITE}/industries.html'
    body = catalog_section('Отрасли', 'В каких отраслях работаем',
                           [(i['name'], i['desc'], f'/services/industry-{i["slug"]}.html') for i in inds]) + \
        '''

        <section class="case-block case-services">
            <h2 class="section-label">Смотрите также</h2>
            <div class="services-tags">
                <a href="/services.html">Все услуги</a>
                <a href="/blocks.html">Ремонт блоков в мастерской</a>
                <a href="/cases.html">Примеры работ</a>
                <a href="/map.html">Карта работ</a>
            </div>
        </section>'''
    cta = common['cta'].replace('<h2>Сняли блок?</h2>', '<h2>Остановилось оборудование?</h2>').replace(
        'Оставьте телефон — перезвоним, скажем, берёмся ли за ремонт, и договоримся о приёме блока.',
        'Оставьте телефон — перезвоним, уточним оборудование и договоримся о выезде.')
    pages['industries.html'] = page_html(
        url=url, title='Отрасли: ремонт электроники производств — Панамастер',
        desc='Ремонт электроники оборудования по отраслям: металлообработка, полиграфия, упаковка, пищевая, фармацевтика, пластмассы, деревообработка и другие. Москва и МО.',
        crumbs=[('Главная', '/'), ('Отрасли', None)], meta='Москва и Московская область · с 2006 года',
        h1='Отрасли, в которых работаем', lead=[
            'У каждого производства своя среда: пыль, влага, масляный туман, агрессивные пары, вибрация, старые сети. Она по-своему выводит из строя электронику оборудования.',
            'Выберите свою отрасль — расскажем, что ломается чаще всего, какое оборудование ремонтируем и как продлить жизнь электронике.'],
        body=body, facts_block='', bridge='', cases_html='', form_page='Отрасли', form_id='industries-phone',
        faq=[('Вашей отрасли нет в списке?', 'Ремонтируем электронику оборудования и в других отраслях. Позвоните или пришлите фото шильдика — скажем, берёмся ли.')],
        faq_title='Коротко об отраслях', main_entity={'@type': 'CollectionPage', 'name': 'Отрасли', 'url': url, 'about': common['org']},
        cta=cta, **{k: common[k] for k in ('header', 'footer', 'org')})
    def page_meta(rel):
        t = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        title = html.unescape(re.search(r'<h1[^>]*>(.*?)</h1>', t, re.S).group(1))
        title = re.sub(r'<[^>]+>', ' ', title)
        desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', t).group(1))
        return re.sub(r'\s+', ' ', title).strip(), desc

    note = ('Мы независимый сервис: ремонтируем электронику оборудования этих производителей. '
            'Официальными представителями производителей не являемся.')
    rubrics = [
        ('equipment.html', 'Виды оборудования', 'Виды оборудования: ремонт электроники — Панамастер',
         'Ремонт электроники по видам оборудования: термоформеры и другие машины. Что ломается, как ищем причину, примеры работ. Москва и Московская область.',
         'Виды оборудования',
         ['Страницы по видам машин: какая электроника стоит, что в ней чаще всего ломается и как мы ищем причину.',
          'Раздел пополняется по мере появления кейсов.'],
         [page_meta(r) + ('/' + r,) for r in sorted(glob.glob('services/type-*.html', root_dir=ROOT))]),
        ('brands.html', 'Производители оборудования', 'Сервисные центры по производителям оборудования — Панамастер',
         'Сервисные центры Панамастер по производителям оборудования: CMS, CODIMAG, LVD и другие. Ремонт электроники станков и машин, примеры работ. Москва и МО.',
         'Сервисные центры: производители оборудования',
         ['Производители станков и машин, электронику которых мы ремонтируем, — с примерами работ.', note],
         [page_meta(r) + ('/' + r,) for r in sorted(glob.glob('services/brand-*.html', root_dir=ROOT))]),
    ]
    eb = {}
    for p in CONTENT['pages']:
        for b in p.get('brand_pages', []):
            eb.setdefault(b['name'], []).append((p['name'], f'/blocks/{p["slug"]}/{b["slug"]}.html', b['desc']))
    rubrics.append(('electronics-brands.html', 'Производители электроники', 'Сервисные центры по производителям электроники — Панамастер',
         'Ремонт электронных блоков по производителям: Rexroth Indramat, B&R, Parker, Baldor и другие. Сервоприводы, частотники, ПЛК. Мастерская в Москве.',
         'Сервисные центры: производители электроники',
         ['Производители приводов, контроллеров и другой электроники, блоки которых мы ремонтируем в мастерской.', note],
         [(name, '; '.join(f'{t}' for t, _, _ in items) + '. ' + items[0][2], items[0][1]) for name, items in sorted(eb.items())]))
    for rel, crumb, title, desc, h1, lead, items in rubrics:
        url = f'{SITE}/{rel}'
        others = [(c, f'/{r}') for r, c, *_ in rubrics if r != rel] + [('Отрасли', '/industries.html'), ('Все услуги', '/services.html')]
        tags = '\n'.join(f'                <a href="{h}">{esc(n)}</a>' for n, h in others)
        pick = {'equipment.html': 'Выберите вид оборудования', 'brands.html': 'Выберите производителя оборудования',
                'electronics-brands.html': 'Выберите производителя электроники'}[rel]
        body = catalog_section(crumb, pick, items) + f'''

        <section class="case-block case-services">
            <h2 class="section-label">Другие разделы</h2>
            <div class="services-tags">
{tags}
            </div>
        </section>'''
        pages[rel] = page_html(
            url=url, title=title, desc=desc, crumbs=[('Главная', '/'), (crumb, None)],
            meta='Москва и Московская область · с 2006 года', h1=h1, lead=lead,
            body=body, facts_block='', bridge='', cases_html='', form_page=crumb, form_id=rel.replace('.html', '') + '-phone',
            faq=[('Вашего производителя нет в списке?', 'Ремонтируем электронику и других производителей. Пришлите фото шильдика — скажем, берёмся ли.')],
            faq_title='Коротко', main_entity={'@type': 'CollectionPage', 'name': h1, 'url': url, 'about': common['org']},
            cta=common['cta'] if rel == 'electronics-brands.html' else common['cta'].replace(
                '<h2>Сняли блок?</h2>', '<h2>Остановилось оборудование?</h2>').replace(
                'Оставьте телефон — перезвоним, скажем, берёмся ли за ремонт, и договоримся о приёме блока.',
                'Оставьте телефон — перезвоним, уточним оборудование и договоримся о выезде.'),
            **{k: common[k] for k in ('header', 'footer', 'org')})
    return pages


def build():
    add_auto_servo_brands()
    header, footer, cta, org = chrome()
    hub = CONTENT['hub']
    os.makedirs(os.path.join(ROOT, 'blocks'), exist_ok=True)
    common = dict(header=header, footer=footer, cta=cta, org=org)
    pages = {'blocks.html': page_html(
        url=f'{SITE}/blocks.html', title=hub['title'], desc=hub['desc'],
        crumbs=[('Главная', '/'), (HUB_NAME, None)],
        meta='Мастерская · Москва и вся Россия', h1=hub['h1'], lead=hub['lead'], body=hub_body(),
        faq=hub['faq'] + CONTENT['common_faq'], form_page=HUB_NAME, form_id='blocks-phone', **common)}
    for p in CONTENT['pages']:
        own, industries = block_cases(p['slug'])
        pages[f'blocks/{p["slug"]}.html'] = page_html(
            url=f'{SITE}/blocks/{p["slug"]}.html', title=p['title'], desc=p['desc'],
            crumbs=[('Главная', '/'), (HUB_NAME, '/blocks.html'), (p['name'], None)],
            meta='Ремонт в мастерской · Москва и вся Россия', h1=p['h1'], lead=p['lead'], body=type_body(p),
            faq=p['faq'] + CONTENT['common_faq'], form_page=f'{HUB_NAME}: {p["name"]}',
            form_id=f'blocks-{p["slug"]}-phone',
            cases_html=cases_gen.cases_block(own[:6], industries, 'Отремонтированные блоки', more=False), **common)
        type_crumbs = [('Главная', '/'), (HUB_NAME, '/blocks.html'), (p['name'], f'/blocks/{p["slug"]}.html')]
        for b in p.get('brand_pages', []):
            os.makedirs(os.path.join(ROOT, 'blocks', p['slug'], b['slug']), exist_ok=True)
            own, industries = block_cases(p['slug'], b)
            pages[f'blocks/{p["slug"]}/{b["slug"]}.html'] = page_html(
                url=f'{SITE}/blocks/{p["slug"]}/{b["slug"]}.html', title=b['title'], desc=b['desc'],
                crumbs=type_crumbs + [(b['name'], None)],
                meta='Ремонт в мастерской · Москва и вся Россия', h1=b['h1'], lead=b['lead'], body=brand_body(p, b),
                faq=b['faq'] + CONTENT['common_faq'], form_page=f'{HUB_NAME}: {p["name"]}: {b["name"]}',
                form_id=f'blocks-{p["slug"]}-{b["slug"]}-phone',
                cases_html=cases_gen.cases_block(own[:6], industries, f'Ремонты {b["name"]}', more=False), **common)
            for m in b.get('models', []):
                own, industries = block_cases(p['slug'], b, m)
                pages[f'blocks/{p["slug"]}/{b["slug"]}/{m["slug"]}.html'] = page_html(
                    url=f'{SITE}/blocks/{p["slug"]}/{b["slug"]}/{m["slug"]}.html', title=m['title'], desc=m['desc'],
                    crumbs=type_crumbs + [(b['name'], f'/blocks/{p["slug"]}/{b["slug"]}.html'), (m['name'], None)],
                    meta='Ремонт в мастерской · Москва и вся Россия', h1=m['h1'], lead=m['lead'], body=model_body(p, b, m),
                    faq=m['faq'] + CONTENT['common_faq'], form_page=f'{HUB_NAME}: {b["name"]} {m["name"]}',
                    form_id=f'blocks-{b["slug"]}-{m["slug"]}-phone',
                    cases_html=cases_gen.cases_block(own[:6], industries, f'Ремонты {b["name"]} {m["name"]}', more=False),
                    **common)
    pages.update(build_service_pages(common))
    pages.update(build_catalog_pages(common))
    for rel, s in pages.items():
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
            f.write(s)
    return pages


if __name__ == '__main__':
    for rel, s in build().items():
        title = html.unescape(re.search(r'<title>(.*?)</title>', s).group(1))
        desc = html.unescape(re.search(r'name="description" content="([^"]*)"', s).group(1))
        print(f'{rel:34} title {len(title)} desc {len(desc)}')
