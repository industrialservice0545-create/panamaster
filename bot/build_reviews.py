"""Блок «Отзывы» на главной: рейтинг Яндекс Карт и три цитаты из bot/content/reviews.json.

Пишет между <!-- REVIEWS_START --> и <!-- REVIEWS_END --> в index.html.
--refresh — обновить рейтинг и число отзывов из публичного виджета отзывов Яндекс Карт.
Запуск: python3 bot/build_reviews.py [--refresh]
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'bot', 'content', 'reviews.json')
INDEX = os.path.join(ROOT, 'index.html')


def esc(s):
    return html.escape(s, quote=True)


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def refresh(d):
    req = urllib.request.Request(f'https://yandex.ru/maps-reviews-widget/{d["org_id"]}?comments',
                                 headers={'User-Agent': 'Mozilla/5.0'})
    s = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
    t = html.unescape(re.sub(r'<[^>]+>', '\n', re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)))
    m = re.search(r'\n(\d,\d)\n\s*(\d+) отзыв', t)
    if not m:
        raise SystemExit('не нашёл рейтинг в виджете — блок не меняю')
    d['rating'], d['reviews_count'], d['checked'] = m.group(1), int(m.group(2)), dt.date.today().isoformat()
    with open(DATA, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')


def block(d):
    n = d['reviews_count']
    cards = '\n'.join(f'''                <article class="related-card">
                    <p class="related-card__meta">{esc(q["topic"])} · {esc(q["date"])}</p>
                    <p>«{esc(q["text"])}»</p>
                    <p class="related-card__time">{esc(q["author"])}, отзыв на Яндекс Картах</p>
                </article>''' for q in d['quotes'])
    return f'''<!-- REVIEWS_START -->
        <section class="case-block" id="otzyvy">
            <p class="section-label">Отзывы</p>
            <h2>{d["rating"]} на Яндекс Картах — {n} {plural(n, "отзыв", "отзыва", "отзывов")}</h2>
            <div class="related-grid related-grid--3">
{cards}
            </div>
            <div class="bottom-cta">
                <a href="{d["url"]}" class="btn btn--ghost" target="_blank" rel="noopener">Все отзывы на Яндекс Картах</a>
            </div>
        </section>
        <!-- REVIEWS_END -->'''


def main():
    d = json.load(open(DATA, encoding='utf-8'))
    if '--refresh' in sys.argv:
        refresh(d)
    s = open(INDEX, encoding='utf-8').read()
    new = block(d)
    if '<!-- REVIEWS_START -->' in s:
        s = re.sub(r'<!-- REVIEWS_START -->.*?<!-- REVIEWS_END -->', lambda _: new, s, flags=re.S)
    else:                                   # первый запуск: сразу после блока примеров работ
        s = s.replace('<!-- CASES_END -->', '<!-- CASES_END -->\n\n        ' + new, 1)
    open(INDEX, 'w', encoding='utf-8').write(s)
    print(f'index.html: отзывы {d["rating"]}, {d["reviews_count"]} (проверено {d["checked"]})')


if __name__ == '__main__':
    main()
