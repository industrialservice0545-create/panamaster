"""Генерация sitemap.xml и llms.txt по страницам сайта.

sitemap.xml — все индексируемые страницы (meta robots index), lastmod = дата последнего коммита файла.
llms.txt   — краткое описание компании и список страниц для AI-поиска (Алиса, Нейро, ChatGPT, Perplexity).
search.html + assets/search.json — поиск по сайту: индекс тех же страниц (заголовок, описание,
             подзаголовки, текст), ищет assets/js/main.js в браузере. search.html — noindex.
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
EXCLUDE = {'privacy.html', 'consent.html', 'all-services.html', 'test.html', 'search.html'}


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def pages():
    """Индексируемые страницы в порядке важности: главная, разделы, отрасли, кейсы."""
    result = []
    for rel in ['index.html', 'cases.html', 'cases-machines.html', 'cases-blocks.html', 'services.html', 'industries.html', 'equipment.html', 'brands.html', 'electronics-brands.html', 'contacts.html', 'about.html', 'map.html', 'blocks.html', 'manufacturers.html', 'en/manufacturers.html', 'zh/manufacturers.html'] + sorted(glob.glob('blocks/**/*.html', root_dir=ROOT, recursive=True)) \
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
    if rel in ('services.html', 'industries.html', 'equipment.html', 'brands.html', 'electronics-brands.html', 'cases.html', 'contacts.html', 'about.html', 'blocks.html'):
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
    services = [r for r in rels if r.startswith('services/') and r not in industries and r not in hubs]
    blocks = [r for r in rels if r == 'blocks.html' or r.startswith('blocks/')]
    cases = [r for r in rels if r.startswith('cases/')]
    line = lambda r: '- [{0}]({1}): {2}'.format(*meta(r)[:1], url_of(r), meta(r)[1])
    return f'''# Панамастер

> Ремонт и настройка электроники промышленного оборудования в Москве и Московской области: станки с ЧПУ, производственные линии, электронные блоки. Выезд, гарантия 3 месяца. Работаем с 2006 года.

- Выезд: в течение 24 часов по Москве и МО, в другие регионы — по договорённости.
- Диагностика: 1 рабочий день. Типовой ремонт: 3–5 рабочих дней.
- Гарантия: на работы — 3 месяца с момента пусконаладки под нагрузкой; на установленные новые блоки и модули — 1 год.
- Клиенты: производства и организации. Договор, любая форма оплаты (безналичный расчёт без НДС, наличные, карта), закрывающие документы.
- Ремонт: станки с ЧПУ, частотные преобразователи, сервоприводы, ПЛК, панели оператора, источники питания.
- Мастерская: Москва, ул. Искры, 31к1, офис 103А (приём блоков — по предварительной договорённости). Пн–пт 09:00–19:00.
- Ремонт снятых блоков (частотники, сервоприводы, ПЛК, панели, стойки ЧПУ): диагностика в мастерской бесплатно, в том числе для блоков, присланных транспортной компанией (1–3 дня), ремонт обычно до 3 дней, оплата после проверки блока, гарантия 3 месяца, приём со всей России транспортной компанией.
- Выезд на диагностику станка или линии — платный.
- Телефон, Telegram, WhatsApp: +7 926 883-09-39. Почта: info@panamaster.ru.
- Исполнитель: ООО «Интел-Сервис», ИНН 7723582307.

## Основные страницы

- [Главная]({SITE}/): услуги, сроки, отрасли, заявка.
- [Услуги]({SITE}/services.html): все работы на объекте и ремонт блоков в мастерской.
- [Отрасли]({SITE}/industries.html): как среда каждого производства влияет на электронику.
- [Виды оборудования]({SITE}/equipment.html), [производители оборудования]({SITE}/brands.html), [производители электроники]({SITE}/electronics-brands.html): каталоги без пересечений.
- [Примеры работ]({SITE}/cases.html): реальные ремонты — что сломалось, что сделали, результат.
- [Контакты]({SITE}/contacts.html): телефон, мессенджеры, адрес мастерской, реквизиты.
- [О компании]({SITE}/about.html): с 2006 года, специализация, принципы работы, опыт, отзывы.

## Услуги

{chr(10).join(line(r) for r in services)}

## Отрасли

{chr(10).join(line(r) for r in industries)}

## Ремонт блоков в мастерской

{chr(10).join(line(r) for r in blocks)}

## Производители и виды оборудования

{chr(10).join(line(r) for r in hubs)}

## Кейсы

{chr(10).join(line(r) for r in cases)}
'''


def page_text(rel):
    """Видимый текст основной части страницы — для поиска по сайту."""
    s = read(rel)
    s = s[s.find('<main'):s.find('</main>')] if '<main' in s else s
    s = re.sub(r'<script.*?</script>|<style.*?</style>|<svg.*?</svg>|<form.*?</form>', ' ', s, flags=re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def build_search(rels):
    """assets/data/search.json и страница search.html (шапка и подвал — с главной)."""
    import json
    index = []
    for r in rels:
        title, desc = meta(r)
        heads = [html.unescape(re.sub(r'<[^>]+>', '', h)).strip()
                 for h in re.findall(r'<h[23][^>]*>(.*?)</h[23]>', read(r), re.S)]
        index.append({'u': '/' if r == 'index.html' else '/' + r, 't': title, 'd': desc,
                      'h': ' · '.join(h for h in heads if h)[:600], 'x': page_text(r)[:2500]})
    with open(os.path.join(ROOT, 'assets', 'search.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, separators=(',', ':'))
    idx = read('index.html')
    head = idx[:idx.index('<header class="site-header">')]
    head = re.sub(r'<title>.*?</title>', '<title>Поиск по сайту — Панамастер</title>', head, flags=re.S)
    head = re.sub(r'<meta name="description"[^>]*>', '<meta name="description" content="Поиск по сайту Панамастер.">', head)
    head = re.sub(r'<meta name="robots"[^>]*>', '<meta name="robots" content="noindex, follow">', head)
    head = re.sub(r'<link rel="canonical"[^>]*>', f'<link rel="canonical" href="{SITE}/search.html">', head)
    head = re.sub(r'\s*<meta property="og:[^>]*>', '', head)
    head = re.sub(r'\s*<script type="application/ld\+json">.*?</script>', '', head, flags=re.S)
    header = idx[idx.index('<header class="site-header">'):idx.index('</header>') + 9] \
        .replace(' class="is-active">Главная', '>Главная').replace('<a href="/search.html">', '<a href="/search.html" class="is-active">')
    footer = idx[idx.index('<footer class="site-footer">'):idx.index('</footer>') + 9]
    page = f'''{head}{header}

<main>
    <div class="container">

        <section class="case-hero">
            <div class="case-hero__content">
                <h1>Поиск по сайту</h1>
                <form class="search-form" id="site-search" action="/search.html" method="get" role="search">
                    <label class="cta-form__label" for="search-q">Оборудование, бренд, модель или неисправность</label>
                    <div class="cta-form__row">
                        <input id="search-q" type="search" class="cta-form__input" name="q"
                               placeholder="Например: сервопривод Rexroth" autocomplete="off">
                        <button type="submit" class="btn btn--primary">Найти</button>
                    </div>
                </form>
                <p class="messengers__lead" id="search-status">Начните вводить запрос.</p>
            </div>
        </section>

        <section class="case-block">
            <div class="faq" id="search-results"></div>
        </section>

        <section class="case-block case-services">
            <h2 class="section-label">Не нашли?</h2>
            <p>Позвоните <a href="tel:+79268830939">+7 926 883-09-39</a> или пришлите фото шильдика в мессенджер — скажем, берёмся ли за ремонт.</p>
        </section>

    </div>
</main>

{footer}

</body>
</html>
'''
    with open(os.path.join(ROOT, 'search.html'), 'w', encoding='utf-8') as f:
        f.write(page)


def main():
    rels = pages()
    with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(build_sitemap(rels))
    with open(os.path.join(ROOT, 'llms.txt'), 'w', encoding='utf-8') as f:
        f.write(build_llms(rels))
    build_search(rels)
    print(f'sitemap.xml: {len(rels)} страниц; llms.txt и поиск готовы')
    stage_extra_pages()


def stage_extra_pages():
    """В GitHub Actions шаг «Commit pages» добавляет в коммит только свой список путей, а затем делает
    git pull --rebase: любой другой изменённый файл ломает сборку. Карту работ, «О компании» и страницы фильтра
    «Примеров работ» генераторы тоже пересобирают — добавляем их в индекс сами (только в CI)."""
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    extra = ['map.html', 'about.html', 'services.html', 'industries.html', 'equipment.html', 'brands.html', 'electronics-brands.html', 'search.html', 'assets/search.json'] + sorted(glob.glob('cases-*.html', root_dir=ROOT))
    import subprocess
    subprocess.run(['git', '-C', ROOT, 'add', '-A', '--'] + extra, check=False)


if __name__ == '__main__':
    main()
