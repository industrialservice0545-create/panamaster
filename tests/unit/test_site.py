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
    pages = ['index.html', 'contacts.html', 'cases.html'] + glob.glob('cases/*.html', root_dir=ROOT) \
        + glob.glob('services/*.html', root_dir=ROOT)
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
                self.assertIn(e, types, f'{ind["slug"]}: «{e}» нет в справочнике')

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

    def test_titles_max_60_and_unique(self):
        titles = [re.search(r'<title>(.*?)</title>', p).group(1) for p in self.pages.values()]
        for t in titles:
            self.assertLessEqual(len(html.unescape(t)), 60, t)
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
        for rule in ['^/\\.(?!well-known/)', '^/bot/', 'assets/templates', '^/tests/']:
            self.assertIn(rule, h)

    def test_robots_txt(self):
        r = read('robots.txt')
        self.assertIn('Disallow: /bot/', r)
        self.assertIn('Sitemap: https://panamaster.ru/sitemap.xml', r)


if __name__ == '__main__':
    unittest.main()
