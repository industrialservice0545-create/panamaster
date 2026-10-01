"""Раздел «Ремонт блоков в мастерской»: /blocks.html и /blocks/{type}.html.

Второе направление сайта (решение владельца 29.09.2026): компонентный ремонт снятых блоков —
для инженеров, которые сами сняли и привезли блок. Главная и отрасли остаются про выезд.
Тексты — bot/content/blocks.json (только подтверждённые владельцем факты), каркас — шапка,
подвал и форма с главной, компоненты — из утверждённых case.html/main.css.

Запуск из корня репозитория:  python3 bot/build_block_pages.py
"""
import html
import sys
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://panamaster.ru'
CONTENT = json.load(open(os.path.join(ROOT, 'bot', 'content', 'blocks.json'), encoding='utf-8'))

sys.path.insert(0, os.path.join(ROOT, 'bot'))
import build_case_pages as cases_gen   # карточки кейсов — та же разметка, что на главной и в отраслях


def block_cases(type_slug, brand=None, model=None):
    """Кейсы формата «блок» для страницы вида / бренда / модели, свежие сверху."""
    cases, industries, _ = cases_gen.load()
    own = [c for c in cases if c.get('format') == 'block' and c['equipment_type'] == type_slug]
    if brand:
        own = [c for c in own if any(m.lower() in c['brand'].lower() for m in brand['match'])]
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


def faq_html(faq):
    items = '\n'.join(f'''                <article>
                    <h3>{esc(q)}</h3>
                    <p>{esc(a)}</p>
                </article>''' for q, a in faq)
    return f'''        <section class="case-block">
            <p class="section-label">Вопросы</p>
            <h2>Коротко о ремонте блоков</h2>
            <div class="faq">
{items}
            </div>
        </section>'''


BRIDGE = '''        <section class="case-block">
            <p class="section-label">Выезд на производство</p>
            <h2>Не можете снять блок или не знаете, что сломалось?</h2>
            <div class="case-summary">
                <p>Выедем на производство по Москве и Московской области в течение 24 часов, найдём неисправность на месте и запустим оборудование. Гарантия — 3 месяца.</p>
                <p><a class="related-card__link" href="/">Ремонт оборудования с выездом</a></p>
            </div>
        </section>'''


def page_html(*, url, title, desc, crumbs, meta, h1, lead, body, faq, header, footer, cta, org, form_page, form_id,
              cases_html='<!-- CASES_START -->\n        <!-- CASES_END -->'):
    crumbs_html = '\n'.join(
        (f'        <a href="{href}">{esc(name)}</a>\n        <span class="breadcrumbs__sep">→</span>' if href
         else f'        <span aria-current="page">{esc(name)}</span>') for name, href in crumbs)
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': name, 'item': SITE + (href or url[len(SITE):])}
            for i, (name, href) in enumerate(crumbs)]},
        {'@type': 'Service', 'name': h1, 'serviceType': 'Ремонт промышленной электроники',
         'areaServed': [{'@type': 'City', 'name': 'Москва'}, {'@type': 'Country', 'name': 'Россия'}],
         'provider': org, 'url': url},
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
            </div>
        </section>

{facts_html()}

{body}

{page_cta}

        {cases_html}

{faq_html(faq)}

{BRIDGE}

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
    brands = '\n'.join(f'''                <article class="related-card">
                    <h3>{esc(k)}</h3>
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


def build():
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
    for rel, s in pages.items():
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as f:
            f.write(s)
    return pages


if __name__ == '__main__':
    for rel, s in build().items():
        title = html.unescape(re.search(r'<title>(.*?)</title>', s).group(1))
        desc = html.unescape(re.search(r'name="description" content="([^"]*)"', s).group(1))
        print(f'{rel:34} title {len(title)} desc {len(desc)}')
