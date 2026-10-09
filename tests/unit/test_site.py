"""Unit-тесты генератора страниц отраслей и обязательных правил сайта (seo.mdc, design.mdc, structure.mdc).

Запуск из корня репозитория:  python3 -m unittest discover -s tests/unit -v
"""
import glob
import html
import importlib.util
import itertools
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOP_WORDS = ['широкий спектр', 'профессиональный подход', 'качественный ремонт',
              'индивидуальный подход', 'оперативн', 'команда профессионалов']


def load_generator():
    spec = importlib.util.spec_from_file_location('gen', os.path.join(ROOT, 'bot', 'build_industry_pages.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return f.read()


def indexable_pages():
    pages = ['index.html', 'contacts.html', 'cases.html', 'blocks.html'] + glob.glob('cases/*.html', root_dir=ROOT) \
        + glob.glob('services/*.html', root_dir=ROOT) + glob.glob('blocks/*.html', root_dir=ROOT)
    return sorted(pages)


def json_ld(page_html):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page_html, re.S)]


def text_shingles(page_html):
    """Смысловой текст страницы отрасли без шапки, фактов, формы и списка других отраслей."""
    t = page_html[page_html.index('<h1'):page_html.index('<section class="case-cta"')]
    t += page_html[page_html.index('Коротко для решения'):page_html.index('Другие отрасли')]
    t = re.sub(r'<section class="case-facts".*?</section>', '', t, flags=re.S)
    words = re.sub(r'<[^>]+>', ' ', t).lower().split()
    return {' '.join(words[i:i + 5]) for i in range(len(words) - 4)}


class GeneratorTests(unittest.TestCase):
    """Утилиты и данные генератора bot/build_industry_pages.py."""

    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.industries = cls.gen.INDUSTRIES

    def test_esc_escapes_html(self):
        self.assertEqual(self.gen.esc('<b>"Панамастер" & Co</b>'),
                         '&lt;b&gt;&quot;Панамастер&quot; &amp; Co&lt;/b&gt;')

    def test_slugs_unique_and_latin(self):
        slugs = [i['slug'] for i in self.industries]
        self.assertEqual(len(slugs), len(set(slugs)))
        for s in slugs:
            self.assertRegex(s, r'^[a-z0-9-]+$')

    def test_every_industry_has_required_content(self):
        for ind in self.industries:
            with self.subTest(ind['slug']):
                self.assertGreaterEqual(len(ind['lead']), 2)
                self.assertGreaterEqual(len(ind['downtime']), 2)
                self.assertGreaterEqual(len(ind['equipment']), 3)
                self.assertTrue(2 <= len(ind['faq']) <= 4)

    def test_generator_slugs_exist_in_dictionary(self):
        d = json.loads(read('bot/dictionaries/entities.json'))
        dict_slugs = {i.get('slug') for i in d['industries']}
        for ind in self.industries:
            self.assertIn(ind['slug'], dict_slugs, f'{ind["slug"]} нет в entities.json')

    def test_equipment_names_exist_in_dictionary(self):
        types = set(json.loads(read('bot/dictionaries/entities.json'))['equipment_types'])
        for ind in self.industries:
            for e in ind['equipment']:
                name = e[0] if isinstance(e, (list, tuple)) else e      # карточка с описанием: (название, текст[, ссылка])
                self.assertIn(name, types, f'{ind["slug"]}: «{name}» нет в справочнике')

    def test_descriptions_length_140_160(self):
        for ind in self.industries:
            self.assertTrue(140 <= len(ind['desc']) <= 160, f'{ind["slug"]}: {len(ind["desc"])} символов')

    def test_photos_exist_and_under_100kb(self):
        for ind in self.industries:
            ph = ind.get('photo')
            if not ph:
                continue
            path = os.path.join(ROOT, ph['src'].lstrip('/'))
            with self.subTest(ind['slug']):
                self.assertTrue(os.path.exists(path), path)
                self.assertLessEqual(os.path.getsize(path), 100 * 1024)


class GeneratedPagesTests(unittest.TestCase):
    """Готовые страницы services/industry-*.html совпадают с генератором и правилами SEO."""

    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.pages = {i['slug']: read(f'services/industry-{i["slug"]}.html') for i in cls.gen.INDUSTRIES}

    def test_page_exists_for_every_industry(self):
        for slug in self.pages:
            self.assertTrue(os.path.exists(os.path.join(ROOT, f'services/industry-{slug}.html')))

    def test_titles_50_to_60_and_unique(self):
        titles = [re.search(r'<title>(.*?)</title>', p).group(1) for p in self.pages.values()]
        for t in titles:
            self.assertTrue(50 <= len(html.unescape(t)) <= 60, f'{len(html.unescape(t))}: {t}')
        self.assertEqual(len(titles), len(set(titles)))

    def test_canonical_matches_url(self):
        for slug, p in self.pages.items():
            self.assertIn(f'<link rel="canonical" href="https://panamaster.ru/services/industry-{slug}.html">', p)

    def test_faq_json_ld_matches_visible_text(self):
        for slug, p in self.pages.items():
            graph = json_ld(p)[0]['@graph']
            faq = next(g for g in graph if g['@type'] == 'FAQPage')
            for q in faq['mainEntity']:
                with self.subTest(slug=slug, q=q['name']):
                    self.assertIn(html.escape(q['name'], quote=True), p)
                    self.assertIn(html.escape(q['acceptedAnswer']['text'], quote=True), p)

    def test_content_overlap_below_30_percent(self):
        sh = {s: text_shingles(p) for s, p in self.pages.items()}
        for a, b in itertools.combinations(sh, 2):
            overlap = len(sh[a] & sh[b]) / min(len(sh[a]), len(sh[b]))
            self.assertLess(overlap, 0.30, f'{a} ~ {b}: {overlap:.0%}')


class SiteRulesTests(unittest.TestCase):
    """Правила для всех индексируемых страниц."""

    def test_single_h1_per_page(self):
        for p in indexable_pages():
            self.assertEqual(read(p).count('<h1'), 1, p)

    def test_json_ld_is_valid(self):
        for p in indexable_pages():
            with self.subTest(p):
                self.assertTrue(json_ld(read(p)), 'нет JSON-LD')

    def test_internal_links_resolve(self):
        for p in indexable_pages():
            for href in set(re.findall(r'href="(/[^"#?]*)', read(p))):
                target = href.lstrip('/') or 'index.html'
                with self.subTest(page=p, href=href):
                    self.assertTrue(os.path.exists(os.path.join(ROOT, target)), href)

    def test_no_stop_words(self):
        for p in indexable_pages():
            text = re.sub(r'<[^>]+>', ' ', read(p)).lower()
            for w in STOP_WORDS:
                self.assertNotIn(w, text, f'{p}: «{w}»')

    def test_only_working_phone(self):
        for p in indexable_pages() + ['privacy.html', 'consent.html']:
            s = read(p)
            self.assertNotIn('525-05-45', s, p)
            self.assertNotIn('350-40-31', s, p)

    def test_all_pages_load_main_js_and_css(self):
        for p in indexable_pages() + ['privacy.html', 'consent.html']:
            s = read(p)
            with self.subTest(p):
                self.assertIn('<script src="/assets/js/main.js" defer></script>', s)
                self.assertIn('<link rel="stylesheet" href="/assets/css/main.css">', s)

    def test_metrika_counter_single_source(self):
        js = read('assets/js/main.js')
        self.assertRegex(js, r'const COUNTER_ID = \d+;')
        for p in indexable_pages():
            self.assertNotIn('mc.yandex.ru/metrika/tag.js', read(p), f'{p}: второй код Метрики')

    def test_htaccess_hides_service_paths(self):
        h = read('.htaccess')
        for rule in ['^/\\.(?!well-known/)', '^/bot/', 'assets/templates', '^/(tests|inbox)/']:
            self.assertIn(rule, h)

    def test_robots_txt(self):
        r = read('robots.txt')
        self.assertIn('Disallow: /bot/', r)
        self.assertIn('Sitemap: https://panamaster.ru/sitemap.xml', r)


class CasePagesTests(unittest.TestCase):
    """Страницы кейсов из генератора bot/build_case_pages.py."""

    def test_case_titles_and_descriptions(self):
        for p in glob.glob('cases/*.html', root_dir=ROOT):
            s = read(p)
            t = html.unescape(re.search(r'<title>(.*?)</title>', s).group(1))
            d = html.unescape(re.search(r'name="description" content="([^"]*)"', s).group(1))
            with self.subTest(p):
                self.assertTrue(50 <= len(t) <= 60, f'title {len(t)}: {t}')
                self.assertTrue(140 <= len(d) <= 160, f'description {len(d)}: {d}')
                # фраза не обрывается: перед заглавной буквой следующего предложения стоит точка
                self.assertNotRegex(d, r'[а-яa-z0-9] [А-Я][а-я]+ (за|блока)', f'обрыв фразы: {d}')

    def test_every_case_in_data_has_page_and_photos(self):
        for c in json.loads(read('assets/data/cases.json')):
            with self.subTest(c['slug']):
                self.assertTrue(os.path.exists(os.path.join(ROOT, 'cases', c['slug'] + '.html')))
                for ph in c['photos']:
                    path = os.path.join(ROOT, 'assets/img/cases', c['slug'], ph['file'])
                    self.assertTrue(os.path.exists(path), path)
                    self.assertLessEqual(os.path.getsize(path), 100 * 1024)

    def test_no_private_fields_in_public_data(self):
        for c in json.loads(read('assets/data/cases.json')):
            for field in ('company', 'address', 'chat_id'):
                self.assertNotIn(field, c)


class HubPagesTests(unittest.TestCase):
    """Посадочные бренда и вида оборудования (bot/content/hubs.json)."""

    def test_hub_pages_meta(self):
        for p in glob.glob('services/brand-*.html', root_dir=ROOT) + glob.glob('services/type-*.html', root_dir=ROOT):
            s = read(p)
            t = html.unescape(re.search(r'<title>(.*?)</title>', s).group(1))
            d = html.unescape(re.search(r'name="description" content="([^"]*)"', s).group(1))
            with self.subTest(p):
                self.assertTrue(50 <= len(t) <= 60, t)
                self.assertTrue(140 <= len(d) <= 160, d)
                self.assertEqual(s.count('<h1'), 1)

    def test_case_links_to_its_hubs(self):
        cms = read('cases/cms-br5-302.html')
        self.assertIn('/services/brand-cms.html', cms)
        self.assertIn('/services/type-thermoformer.html', cms)
        self.assertIn('/cases/cms-br5-302.html', read('services/brand-cms.html'))
        self.assertIn('/services/brand-cms.html', read('services/type-thermoformer.html'))
        self.assertIn('/services/type-thermoformer.html', read('services/brand-cms.html'))

    def test_hub_content_overlap(self):
        a, b = read('services/brand-cms.html'), read('services/type-thermoformer.html')
        def sh(s):
            s = s[s.index('<h1'):s.index('<section class="case-cta"')]
            w = re.sub(r'<[^>]+>', ' ', s).lower().split()
            return {' '.join(w[i:i + 5]) for i in range(len(w) - 4)}
        x, y = sh(a), sh(b)
        self.assertLess(len(x & y) / min(len(x), len(y)), 0.30)


class SitemapTests(unittest.TestCase):
    """sitemap.xml и llms.txt (bot/build_sitemap.py)."""

    @classmethod
    def setUpClass(cls):
        cls.sitemap = read('sitemap.xml')
        cls.locs = re.findall(r'<loc>(.*?)</loc>', cls.sitemap)

    def test_sitemap_contains_all_indexable_pages(self):
        for p in indexable_pages():
            url = 'https://panamaster.ru/' if p == 'index.html' else f'https://panamaster.ru/{p}'
            self.assertIn(url, self.locs, p)

    def test_sitemap_excludes_service_pages(self):
        for bad in ['privacy.html', 'consent.html', 'test.html', 'all-services.html']:
            self.assertFalse(any(l.endswith(bad) for l in self.locs), bad)

    def test_sitemap_urls_unique_with_lastmod(self):
        self.assertEqual(len(self.locs), len(set(self.locs)))
        self.assertEqual(len(re.findall(r'<lastmod>\d{4}-\d{2}-\d{2}</lastmod>', self.sitemap)), len(self.locs))

    def test_llms_txt_has_facts_and_links(self):
        t = read('llms.txt')
        for fact in ['+7 926 883-09-39', 'гарантия 3 месяца'.capitalize()[:8], '24 часов', 'https://panamaster.ru/cases.html']:
            self.assertIn(fact, t)


class BlockPagesTests(unittest.TestCase):
    """Раздел «Ремонт блоков в мастерской» (/blocks.html, /blocks/*.html)."""

    @classmethod
    def setUpClass(cls):
        cls.content = json.loads(read('bot/content/blocks.json'))
        cls.pages = ['blocks.html'] + [f'blocks/{p["slug"]}.html' for p in cls.content['pages']]

    def test_pages_exist_with_meta(self):
        titles = set()
        for p in self.pages:
            s = read(p)
            t = html.unescape(re.search(r'<title>(.*?)</title>', s).group(1))
            d = html.unescape(re.search(r'name="description" content="([^"]*)"', s).group(1))
            with self.subTest(p):
                self.assertTrue(50 <= len(t) <= 60, t)
                self.assertTrue(140 <= len(d) <= 160, d)
                self.assertIn(f'<link rel="canonical" href="https://panamaster.ru/{p}">', s)
                titles.add(t)
        self.assertEqual(len(titles), len(self.pages))

    def test_slugs_from_dictionary(self):
        slugs = {t['slug'] for t in json.loads(read('bot/dictionaries/entities.json'))['equipment_catalog']}
        for p in self.content['pages']:
            self.assertIn(p['slug'], slugs)

    def test_confirmed_facts_on_every_page(self):
        for p in self.pages:
            s = read(p)
            with self.subTest(p):
                for fact in ('Бесплатно в мастерской, 1–3 дня', 'оплата после проверки', 'от 10\u00a0000 ₽', '3 месяца',
                             'Искры, 31к1', 'транспортной компанией'):
                    self.assertIn(fact, s)

    def test_free_diagnostics_only_with_workshop_condition(self):
        # Решение владельца 01.10.2026: бесплатна только диагностика блока, привезённого в мастерскую; выезд платный
        for p in self.pages:
            text = re.sub(r'<[^>]+>', ' ', read(p))
            for m in re.finditer(r'[^.!?\n]*[Бб]есплатн[^.!?\n]*', text):
                with self.subTest(page=p, phrase=m.group(0).strip()[:80]):
                    self.assertRegex(m.group(0), r'мастерск|привез')

    def test_faq_json_ld_matches_visible_text(self):
        for p in self.pages:
            s = read(p)
            faq = next(g for g in json_ld(s)[0]['@graph'] if g['@type'] == 'FAQPage')
            for q in faq['mainEntity']:
                with self.subTest(page=p, q=q['name']):
                    self.assertIn(html.escape(q['name'], quote=True), s)
                    self.assertIn(html.escape(q['acceptedAnswer']['text'], quote=True), s)

    def test_bridges_between_directions(self):
        idx = read('index.html')
        self.assertGreaterEqual(idx.count('href="/blocks.html"'), 2)
        for p in self.pages:
            self.assertIn('Работы на вашем производстве', read(p), p)

    def test_in_sitemap(self):
        sm = read('sitemap.xml')
        for p in self.pages:
            self.assertIn(f'<loc>https://panamaster.ru/{p}</loc>', sm)

    def test_form_marks_direction(self):
        for p in self.pages:
            self.assertIn('name="page" value="Ремонт блоков в мастерской', read(p), p)


if __name__ == '__main__':
    unittest.main()


class JsonLdEscapeTest(unittest.TestCase):
    """Текст кейса не должен закрывать <script type="application/ld+json">."""

    def test_generators_escape_script_close(self):
        for name in ('build_industry_pages', 'build_case_pages', 'build_block_pages'):
            spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, 'bot', name + '.py'))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            out = mod.ld_json({'name': '</script><script>alert(1)</script> & co'})
            self.assertNotIn('<', out, name)
            self.assertEqual(json.loads(out)['name'], '</script><script>alert(1)</script> & co', name)

    def test_built_pages_have_no_raw_lt_in_json_ld(self):
        for path in glob.glob(os.path.join(ROOT, '**', '*.html'), recursive=True):
            if '/assets/templates/' in path or '/tests/' in path:
                continue
            text = open(path, encoding='utf-8').read()
            for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
                self.assertNotIn('<', block, path)


class PricesAuthorNoJsTest(unittest.TestCase):
    """Цены и автор (владелец 02.10.2026); смысл страницы — в HTML без JS (AI-краулеры JS не исполняют)."""

    def text_without_js(self, rel):
        s = read(rel)
        return re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>', ' ', s, flags=re.S)

    def test_prices_visible_without_js(self):
        for rel, price in (('index.html', '15&nbsp;000 ₽'), ('services/modernization.html', 'от 15\u00a0000 ₽'),
                           ('blocks/drives-servo.html', 'от 10\u00a0000 ₽'),
                           ('services/industry-food.html', 'от 15&nbsp;000 ₽')):
            with self.subTest(rel):
                self.assertIn(price, self.text_without_js(rel))

    def test_key_content_without_js(self):
        for rel, phrase in (('blocks/drives-servo.html', 'Компонентный ремонт'),
                            ('services/modernization.html', 'Что модернизируем'),
                            ('index.html', '+7 926 883-09-39')):
            with self.subTest(rel):
                self.assertIn(phrase, self.text_without_js(rel))

    def test_case_author(self):
        for rel in glob.glob(os.path.join(ROOT, 'cases', '*.html')):
            s = open(rel, encoding='utf-8').read()
            with self.subTest(rel):
                self.assertIn('Вячеслав Бондаренко, сервисный инженер', s)
                self.assertIn('"@type": "Person"', s)


class ReviewsBlockTest(unittest.TestCase):
    """Отзывы с Яндекс Карт на главной (bot/build_reviews.py): рейтинг, ссылка, без названий компаний клиентов."""

    def test_reviews_block(self):
        s = read('index.html')
        block = s[s.index('<!-- REVIEWS_START -->'):s.index('<!-- REVIEWS_END -->')]
        self.assertRegex(block, r'\d,\d на Яндекс Картах — \d+ отзыв')
        self.assertIn('yandex.ru/maps/org/panamaster/1153146831/reviews', block)
        self.assertEqual(block.count('class="related-card"'), 3)
        self.assertNotIn('ВЕРТЬЕ', block)


class SearchAndMenuTest(unittest.TestCase):
    """Поиск по сайту (build_sitemap.py → search.json + search.html) и меню с «О компании» и «Поиском»."""

    def test_search_index_covers_sitemap(self):
        index = json.load(open(os.path.join(ROOT, 'assets', 'search.json'), encoding='utf-8'))
        urls = {p['u'] for p in index}
        for loc in re.findall(r'<loc>https://panamaster\.ru(/[^<]*)</loc>', read('sitemap.xml')):
            self.assertIn(loc, urls)
        self.assertTrue(all(p['t'] and p['x'] for p in index))

    def test_search_page_noindex(self):
        s = read('search.html')
        self.assertIn('noindex', s)
        self.assertIn('id="site-search"', s)
        self.assertNotIn('search.html', read('sitemap.xml'))

    def test_menu_on_every_page(self):
        for p in indexable_pages() + ['search.html', 'contacts.html']:
            with self.subTest(p):
                nav = re.search(r'<nav class="site-header__nav".*?</nav>', read(p), re.S).group(0)
                self.assertIn('href="/about.html"', nav)
                self.assertIn('href="/search.html"', nav)


class CatalogPagesTest(unittest.TestCase):
    """Каталоги /services.html и /industries.html: ссылки на все услуги и отрасли, пункт меню «Услуги»."""

    def test_services_catalog_links_all_services(self):
        s = read('services.html')
        for sp in json.loads(read('bot/content/services.json'))['pages']:
            if not sp.get('kind'):   # страницы с kind (about, career) — не услуги, в каталоге их нет
                self.assertIn(f'href="/services/{sp["slug"]}.html"', s)
        self.assertIn('href="/blocks.html"', s)

    def test_industries_catalog_links_all_industries(self):
        s = read('industries.html')
        for i in json.loads(read('bot/content/industries.json'))['industries']:
            self.assertIn(f'href="/services/industry-{i["slug"]}.html"', s)

    def test_menu_services_points_to_catalog(self):
        for p in indexable_pages():
            with self.subTest(p):
                nav = re.search(r'<nav class="site-header__nav".*?</nav>', read(p), re.S).group(0)
                self.assertIn('href="/services.html"', nav)
                self.assertNotIn('/#uslugi', nav)


class RubricCatalogsTest(unittest.TestCase):
    """Виды оборудования, производители оборудования и производители электроники — без пересечений."""

    def links(self, rel):
        s = read(rel)
        body = s[s.index('<main'):s.index('Другие разделы')]
        return set(re.findall(r'<h3><a href="(/[^"]+)"', body))

    def test_rubrics_cover_their_pages_without_overlap(self):
        eq, br, el = self.links('equipment.html'), self.links('brands.html'), self.links('electronics-brands.html')
        self.assertEqual(eq, {'/' + r for r in glob.glob('services/type-*.html', root_dir=ROOT)})
        self.assertEqual(br, {'/' + r for r in glob.glob('services/brand-*.html', root_dir=ROOT)})
        self.assertTrue(el and all(u.startswith('/blocks/') for u in el))
        self.assertFalse(eq & br or eq & el or br & el)

    def test_hub_breadcrumbs_point_to_rubrics(self):
        for r in glob.glob('services/brand-*.html', root_dir=ROOT):
            self.assertIn('<a href="/brands.html">Бренды производителей</a>', read(r), r)
        for r in glob.glob('services/type-*.html', root_dir=ROOT):
            self.assertIn('<a href="/equipment.html">Виды оборудования</a>', read(r), r)


class EquipmentCatalogTest(unittest.TestCase):
    """Каталог видов оборудования: все виды из equipment_catalog.json, у каждого — описание электроники."""

    def test_all_types_listed_with_electronics(self):
        cat = json.loads(read('bot/content/equipment_catalog.json'))
        items = [x for c in cat['industries'] for x in c['items']]
        s = read('equipment.html')
        self.assertEqual(s.count('<li><strong>'), len(items))
        for x in items:
            self.assertTrue(x['electronics'].strip(), x['name'])
        for c in cat['industries']:
            self.assertIn(f'id="{c["slug"]}"', s)
            self.assertTrue(os.path.exists(os.path.join(ROOT, 'services', f'industry-{c["slug"]}.html')), c['slug'])


class AutoTypeHubTest(unittest.TestCase):
    """Новый кейс с видом оборудования без ручной страницы — автоматическая страница вида с метой в норме."""

    def test_auto_type_hub_meta(self):
        import importlib, sys
        sys.path.insert(0, os.path.join(ROOT, 'bot'))
        b = importlib.import_module('build_case_pages')
        d = json.loads(read('bot/dictionaries/entities.json'))
        types = {t['slug']: t['name'] for t in d['equipment_catalog']}
        case = {'brand': 'TESTBRAND', 'model': 'X1', 'equipment_type': 'press-brake', 'industry': 'metalworking',
                'headline': 'восстановление платы', 'defect': 'Станок не включался.', 'solution': 'Отремонтировали плату.'}
        h = b.auto_type_hub('press-brake', [case], types, {'metalworking': 'Металлообработка'}, {})
        self.assertTrue(50 <= len(h['title']) <= 60, h['title'])
        self.assertTrue(140 <= len(h['desc']) <= 160, h['desc'])
        self.assertIn('любых', h['lead'][0])
        self.assertTrue(h['auto'])
