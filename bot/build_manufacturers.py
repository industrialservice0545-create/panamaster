"""Раздел «Производителям оборудования» (владелец 09.10.2026): manufacturers.html, en/manufacturers.html, zh/manufacturers.html.

Содержание — bot/content/manufacturers.json (три версии, каждая адаптирована под свой рынок). Русская версия — в общей
шапке и подвале сайта (те же функции, что у посадочных услуг); английская и китайская — своя короткая шапка и подвал на языке
страницы. Между версиями — hreflang; у каждой свой canonical. Отдельная форма для производителей (audience=manufacturer):
контакт — e-mail, WeChat или WhatsApp вместо российского телефона; send.php помечает такие заявки отдельно.
Запуск: python3 bot/build_manufacturers.py (после build_block_pages; без аргументов).
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_block_pages as bb  # noqa: E402

ROOT, SITE, esc = bb.ROOT, bb.SITE, bb.esc
DATA = json.load(open(os.path.join(ROOT, 'bot', 'content', 'manufacturers.json'), encoding='utf-8'))
LANGS = {'ru': 'ru', 'en': 'en', 'zh': 'zh-CN'}
LABEL = {'ru': 'Русский', 'en': 'English', 'zh': '中文'}
FORM_CSS = '''    <style>
        .partner-form { display: grid; gap: 12px; max-width: 640px; }
        .partner-form .cta-form__input { width: 100%; box-sizing: border-box; }
        .partner-form textarea.cta-form__input { min-height: 96px; resize: vertical; font: inherit; }
        .lang-switch { display: flex; gap: 14px; flex-wrap: wrap; font-size: 15px; }
        .lang-switch a[aria-current] { font-weight: 600; text-decoration: none; }
    </style>'''


def url(lang):
    return f'{SITE}/{DATA["pages"][lang]["path"]}'


def hreflang():
    links = [f'    <link rel="alternate" hreflang="{LANGS[l]}" href="{url(l)}">' for l in DATA['pages']]
    links.append(f'    <link rel="alternate" hreflang="x-default" href="{url("en")}">')
    return '\n'.join(links)


def lang_switch(cur):
    return '<div class="lang-switch">' + ''.join(
        f'<a href="/{DATA["pages"][l]["path"]}" hreflang="{LANGS[l]}"' + (' aria-current="page"' if l == cur else '') + f'>{LABEL[l]}</a>'
        for l in DATA['pages']) + '</div>'


def contacts(lang):
    wechat = DATA.get('wechat')
    items = [('E-mail', '<a href="mailto:info@panamaster.ru">info@panamaster.ru</a>'),
             ('WhatsApp', '<a href="https://wa.me/79268830939" target="_blank" rel="noopener">+7 926 883-09-39</a>'),
             ('Telegram', '<a href="https://t.me/+79268830939" target="_blank" rel="noopener">+7 926 883-09-39</a>')]
    if wechat:
        items.insert(1, ('WeChat', esc(wechat)))
    return '\n'.join(f'                <p><strong>{k}:</strong> {v}</p>' for k, v in items)


def form(lang):
    p = DATA['pages'][lang]
    f = p['form']
    fid = f'mf-{lang}'
    field = lambda name, label, req=False: (
        f'                <label class="cta-form__label" for="{fid}-{name}">{esc(label)}</label>\n'
        f'                <input id="{fid}-{name}" class="cta-form__input" name="{name}" type="text"{" required" if req else ""} maxlength="200">')
    return f'''        <section class="case-cta" id="zayavka">
            <h2>{esc(f["title"])}</h2>
            <p class="case-cta__sub">{esc(f["text"])}</p>
            <form class="cta-form partner-form" action="/send.php" method="post" data-ok="{esc(f["ok"])}">
                <input type="hidden" name="audience" value="manufacturer">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="page" value="Производителям оборудования ({lang})">
                <input type="text" name="website" hidden tabindex="-1" autocomplete="off">
                <p class="cta-form__label" role="status"></p>
{field("company", f["company"], True)}
{field("country", f["country"])}
{field("equipment", f["equipment"])}
{field("contact", f["contact"], True)}
                <label class="cta-form__label" for="{fid}-comment">{esc(f["comment"])}</label>
                <textarea id="{fid}-comment" class="cta-form__input" name="comment" maxlength="1000"></textarea>
                <button type="submit" class="btn btn--primary">{esc(f["button"])}</button>
                <p class="cta-form__consent">{f["consent"]}</p>
            </form>
            <div class="case-summary">
{contacts(lang)}
            </div>
        </section>'''


def card(item):
    k, v = item[:2]
    return f'''                <article class="related-card">
                    <h3>{esc(k)}</h3>
                    <p>{esc(v)}</p>
                </article>'''


def facts(p):
    return '        <section class="case-facts">\n' + '\n'.join(f'''            <div class="fact">
                <p class="fact__label">{esc(k)}</p>
                <p class="fact__value">{esc(v)}</p>
            </div>''' for k, v in p['facts']) + '\n        </section>'


def faq(p):
    items = '\n'.join(f'''                <article>
                    <h3>{esc(q)}</h3>
                    <p>{esc(a)}</p>
                </article>''' for q, a in p['faq'])
    return f'''        <section class="case-block">
            <h2>{esc(p["faq_title"])}</h2>
            <div class="faq">
{items}
            </div>
        </section>'''


def ld(lang, org):
    p = DATA['pages'][lang]
    return json.dumps({'@context': 'https://schema.org', '@graph': [
        {'@type': 'Service', 'name': p['h1'], 'serviceType': p['meta'].split('·')[0].strip(), 'url': url(lang),
         'inLanguage': LANGS[lang], 'provider': org, 'areaServed': {'@type': 'Country', 'name': 'Russia'}},
        {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}}
                                            for q, a in p['faq']]}]}, ensure_ascii=False)


def build_ru(common):
    p = DATA['pages']['ru']
    body = '\n\n'.join(bb.section_html(s, card) for s in p['sections'])
    page = bb.page_html(
        url=url('ru'), title=p['title'], desc=p['desc'], crumbs=[('Главная', '/'), ('Производителям оборудования', None)],
        meta=p['meta'], h1=p['h1'], lead=p['lead'], body=body, faq=p['faq'], form_page='Производителям оборудования',
        form_id='mf-ru-phone', facts_block=facts(p), bridge='', service_type='Сервис для производителей оборудования',
        faq_title=p['faq_title'], min_price=None, cta_button=p['cta_button'], photo_hint=p['photo_hint'],
        header=common['header'], footer=common['footer'], cta=form('ru'), org=common['org'])
    page = re.sub(r'(<link rel="canonical"[^>]*>)', lambda m: m.group(1) + '\n' + hreflang() + '\n' + FORM_CSS, page, count=1)
    page = page.replace('<p class="case-hero__meta">', f'{lang_switch("ru")}\n                <p class="case-hero__meta">', 1)
    return page


def build_foreign(lang, org):
    p = DATA['pages'][lang]
    t = {'en': {'home': 'Panamaster', 'sub': 'INDUSTRIAL EQUIPMENT SERVICE', 'call': 'Call', 'nav': 'Contact us',
                'addr': 'Moscow, Iskry street 31 bld. 1, office 103A', 'legal': 'Intel-Service LLC (Panamaster)',
                'hours': 'Mon–Fri, 09:00–19:00 (Moscow time)'},
         'zh': {'home': 'Panamaster', 'sub': '工业设备服务', 'call': '电话', 'nav': '联系我们',
                'addr': '莫斯科 Iskry 街 31号 1栋 103A办公室', 'legal': 'Intel-Service 有限责任公司（Panamaster）',
                'hours': '周一至周五 09:00–19:00（莫斯科时间）'}}[lang]
    body = '\n\n'.join(bb.section_html(s, card) for s in p['sections'])
    lead = '\n'.join(f'                    <p>{esc(x)}</p>' for x in p['lead'])
    return f'''<!DOCTYPE html>
<html lang="{LANGS[lang]}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{esc(p["title"])}</title>
    <meta name="description" content="{esc(p["desc"])}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{url(lang)}">
{hreflang()}
    <link rel="stylesheet" href="/assets/css/main.css">
{FORM_CSS}
    <script src="/assets/js/main.js" defer></script>
    <link rel="icon" href="/favicon.ico" sizes="32x32">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <meta property="og:type" content="website">
    <meta property="og:title" content="{esc(p["title"])}">
    <meta property="og:description" content="{esc(p["desc"])}">
    <meta property="og:url" content="{url(lang)}">
    <meta property="og:locale" content="{p["locale"]}">
    <meta property="og:site_name" content="Panamaster">
    <script type="application/ld+json">{ld(lang, org)}</script>
</head>
<body>

<header class="site-header">
    <div class="container site-header__inner">
        <a href="/{p["path"]}" class="site-header__logo" aria-label="Panamaster">
            <svg viewBox="0 0 260 58" role="img" aria-hidden="true">
                <text class="logo-title" x="0" y="24">PANAMASTER</text>
                <text class="logo-sub" x="0" y="48" textLength="186.87" lengthAdjust="spacingAndGlyphs">{esc(t["sub"])}</text>
            </svg>
        </a>
        <nav class="site-header__nav" aria-label="Language">
            <a href="#zayavka">{esc(t["nav"])}</a>
        </nav>
        <a href="tel:+79268830939" class="site-header__phone" aria-label="+7 926 883-09-39">
            <span class="site-header__phone-text">+7 926 883-09-39</span>
        </a>
    </div>
</header>

<main>
    <div class="container">

        <section class="case-hero">
            <div class="case-hero__content">
                {lang_switch(lang)}
                <p class="case-hero__meta">{esc(p["meta"])}</p>
                <h1>{esc(p["h1"])}</h1>
                <div class="case-summary">
{lead}
                </div>
                <div class="bottom-cta">
                    <a href="#zayavka" class="btn btn--primary">{esc(p["cta_button"])}</a>
                    <a href="mailto:info@panamaster.ru" class="btn btn--ghost">info@panamaster.ru</a>
                </div>
            </div>
        </section>

{facts(p)}

{body}

{faq(p)}

{form(lang)}

    </div>
</main>

<footer class="site-footer">
    <div class="container">
        <div class="site-footer__bottom">
            <p>{esc(t["legal"])} · {esc(t["addr"])} · {esc(t["hours"])}</p>
            <p><a href="mailto:info@panamaster.ru">info@panamaster.ru</a> · <a href="tel:+79268830939">+7 926 883-09-39</a> · <a href="/manufacturers.html" hreflang="ru">Русская версия</a></p>
        </div>
    </div>
</footer>
</body>
</html>
'''


def main():
    common = bb.common_parts() if hasattr(bb, 'common_parts') else None
    if common is None:
        header, footer, cta, org = bb.chrome()
        common = {'header': header, 'footer': footer, 'cta': cta, 'org': org}
    out = {'manufacturers.html': build_ru(common)}
    for lang in ('en', 'zh'):
        out[DATA['pages'][lang]['path']] = build_foreign(lang, common['org'])
    for rel, text in out.items():
        path = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print('ok', rel, len(text))


if __name__ == '__main__':
    main()
