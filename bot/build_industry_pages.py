"""Генерация страниц отраслей /services/industry-{slug}.html из общего каркаса сайта.
Временный генератор (до PHP-конвейера). Запуск из корня репозитория."""
import json, re, html

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://panamaster.ru'

INDUSTRIES = json.load(open(os.path.join(ROOT, 'bot', 'content', 'industries.json'), encoding='utf-8'))['industries']


_DICT = json.load(open(os.path.join(ROOT, 'bot', 'dictionaries', 'entities.json'), encoding='utf-8'))
TYPE_SLUGS = {t['name']: t['slug'] for t in _DICT['equipment_catalog']}
HUB_TYPES = set(json.load(open(os.path.join(ROOT, 'bot', 'content', 'hubs.json'), encoding='utf-8'))['types'])


def equip_card(e):
    """Карточка оборудования с описанием: (название, текст[, ссылка])."""
    name, text, href = (list(e) + [None])[:3]
    title = f'<a href="{href}">{esc(name)}</a>' if href else esc(name)
    return f'''                <article class="related-card">
                    <h3>{title}</h3>
                    <p>{esc(text)}</p>
                </article>'''


def ld_json(data):
    """JSON-LD для <script>: символы <, >, & заменяем на \\u-коды, чтобы текст кейса не закрыл тег script."""
    return (json.dumps(data, ensure_ascii=False, indent=2)
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))


def esc(s):
    return html.escape(s, quote=True)


def main():
    idx = open(f'{ROOT}/index.html').read()
    header = idx[idx.index('<header class="site-header">'):idx.index('</header>') + 9].replace(' class="is-active">Главная', '>Главная')
    footer = idx[idx.index('<footer class="site-footer">'):idx.index('</footer>') + 9].replace(' id="kontakty"', '')
    facts = idx[idx.index('        <section class="case-facts" aria-label="Сроки и гарантия">'):idx.index('</section>', idx.index('aria-label="Сроки и гарантия"')) + 10]
    cta = idx[idx.index('        <section class="case-cta" id="zayavka">'):idx.index('        </section>', idx.index('class="case-cta"')) + len('        </section>')]
    ld_org = json.loads(re.search(r'ld\+json">(.*?)</script>', idx, re.S).group(1))
    ld_org.pop('@context', None)

    for ind in INDUSTRIES:
        url = f'{SITE}/services/industry-{ind["slug"]}.html'
        title = ind.get('title') or f'{ind["name"]}: ремонт оборудования — Панамастер'
        if len(title) > 60:
            title = f'{ind["name"]}: ремонт — Панамастер'
        h1 = f'{ind["name"]}: ремонт оборудования'
        others = [o for o in INDUSTRIES if o is not ind]
        page_cta = cta.replace('value="Главная"', f'value="Отрасль: {esc(ind["name"])}"').replace('home-phone', f'ind-phone')
        lead = '\n'.join(f'                        <p>{esc(p)}</p>' for p in ind['lead'])
        downtime = '\n'.join(f'                <p>{esc(p)}</p>' for p in ind['downtime'])
        example = f'\n                <p>{esc(ind["example"])}</p>' if ind['example'] else ''
        if ind.get('example_link'):
            example += f'\n                <p><a class="related-card__link" href="{ind["example_link"]}">Подробнее о ремонте CODIMAG VIVA 340</a></p>'
        equip = '\n'.join(equip_card(e) if isinstance(e, (list, tuple)) else
            f'                <article class="related-card"><h3><a href="/services/type-{TYPE_SLUGS[e]}.html">{esc(e)}</a></h3></article>'
            if TYPE_SLUGS.get(e) in HUB_TYPES and os.path.exists(os.path.join(ROOT, 'services', f'type-{TYPE_SLUGS[e]}.html'))
            else f'                <article class="related-card"><h3>{esc(e)}</h3></article>' for e in ind['equipment'])
        faq = '\n'.join(f'''                <article>
                    <h3>{esc(q)}</h3>
                    <p>{esc(a)}</p>
                </article>''' for q, a in ind['faq'])
        env_html = prevention_html = ''
        if ind.get('environment'):
            env = ind['environment']
            cards = '\n'.join(f'''                <article class="related-card">
                    <h3>{esc(k)}</h3>
                    <p>{esc(v)}</p>
                </article>''' for k, v in env['cards'])
            fails = '\n'.join(f'                <li>{esc(x)}</li>' for x in env.get('failures', []))
            env_html = f'''
        <section class="case-block">
            <p class="section-label">Условия цеха</p>
            <h2>{esc(env['title'])}</h2>
            <div class="related-grid related-grid--3">
{cards}
            </div>
        </section>
''' + (f'''
        <section class="case-block">
            <p class="section-label">Типовые отказы</p>
            <h2>{esc(env['failures_title'])}</h2>
            <ul class="hub-list">
{fails}
            </ul>
        </section>
''' if fails else '')
        if ind.get('prevention'):
            items = '\n'.join(f'                <li>{esc(x)}</li>' for x in ind['prevention']['items'])
            prevention_html = f'''
        <section class="case-block">
            <p class="section-label">Профилактика</p>
            <h2>{esc(ind['prevention']['title'])}</h2>
            <ul class="hub-list">
{items}
            </ul>
        </section>
'''
        ph = ind.get('photo')
        hero_open = '\n            <div class="case-hero__inner">' if ph else ''
        hero_photo = (f'''
                <figure class="case-photo case-hero__photo">
                    <img src="{ph['src']}" alt="{esc(ph['alt'])}" width="{ph['w']}" height="{ph['h']}" decoding="async" fetchpriority="high">
                </figure>
            </div>''') if ph else ''
        og_image = f"{SITE}{ph['src']}" if ph else f"{SITE}/assets/img/cases/codimag-viva-340/photo-2.webp"
        links = '\n'.join(f'                <a href="/services/industry-{o["slug"]}.html">{esc(o["name"])}</a>' for o in others)
        ld = {
            '@context': 'https://schema.org',
            '@graph': [
                {'@type': 'BreadcrumbList', 'itemListElement': [
                    {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': f'{SITE}/'},
                    {'@type': 'ListItem', 'position': 2, 'name': 'Услуги', 'item': f'{SITE}/#uslugi'},
                    {'@type': 'ListItem', 'position': 3, 'name': ind['name'], 'item': url}]},
                {'@type': 'Service', 'name': h1, 'serviceType': 'Ремонт промышленного оборудования',
                 'areaServed': [{'@type': 'City', 'name': 'Москва'}, {'@type': 'AdministrativeArea', 'name': 'Московская область'}],
                 'provider': ld_org, 'url': url},
                {'@type': 'FAQPage', 'mainEntity': [
                    {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in ind['faq']]},
            ]}
        page = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(ind["desc"])}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{url}">
    <link rel="stylesheet" href="/assets/css/main.css">
    <script src="/assets/js/main.js" defer></script>
    <link rel="icon" href="/favicon.ico" sizes="32x32">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">

    <meta property="og:type" content="website">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(ind["desc"])}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:locale" content="ru_RU">
    <meta property="og:site_name" content="Панамастер">
</head>
<body>

{header}

<nav class="breadcrumbs" aria-label="Хлебные крошки">
    <div class="container">
        <a href="/">Главная</a>
        <span class="breadcrumbs__sep">→</span>
        <a href="/#uslugi">Услуги</a>
        <span class="breadcrumbs__sep">→</span>
        <span aria-current="page">{esc(ind["name"])}</span>
    </div>
</nav>

<main>
    <div class="container">

        <section class="case-hero">{hero_open}
            <div class="case-hero__content">
                <p class="case-hero__meta">Отрасль · Москва и Московская область</p>
                <h1>{esc(h1)}</h1>
                <div class="case-summary">
{lead}
                </div>
                <div class="bottom-cta">
                    <a href="tel:+79268830939" class="btn btn--primary">Позвонить: +7 926 883-09-39</a>
                    <a href="#zayavka" class="btn btn--ghost">Оставить заявку</a>
                </div>
            </div>{hero_photo}
        </section>

{facts}

        <section class="case-block">
            <p class="section-label">Почему важна скорость</p>
            <h2>Чем опасен простой</h2>
            <div class="case-summary">
{downtime}{example}
            </div>
        </section>
{env_html}
        <section class="case-block">
            <p class="section-label">Оборудование</p>
            <h2>Что ремонтируем в отрасли</h2>
            <div class="related-grid">
{equip}
            </div>
        </section>
{prevention_html}
{page_cta}

        <!-- CASES_START -->
        <!-- CASES_END -->

        <section class="case-block">
            <p class="section-label">Вопросы</p>
            <h2>Коротко для решения</h2>
            <div class="faq">
{faq}
            </div>
        </section>

        <section class="case-block case-services">
            <h2 class="section-label">Другие отрасли</h2>
            <div class="services-tags">
{links}
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
        open(f'{ROOT}/services/industry-{ind["slug"]}.html', 'w').write(page)
        print(f'{ind["slug"]:22} title {len(title)} desc {len(ind["desc"])}')


if __name__ == '__main__':
    main()
