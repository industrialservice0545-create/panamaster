'use strict';

const COUNTER_ID = 113105780;

// Яндекс Метрика
(function () {
  window.ym = window.ym || function () {
    (window.ym.a = window.ym.a || []).push(arguments);
  };
  window.ym.l = Date.now();

  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://mc.yandex.ru/metrika/tag.js?id=' + COUNTER_ID;
  document.head.appendChild(script);

  window.ym(COUNTER_ID, 'init', {
    ssr: true,
    referrer: document.referrer,
    url: window.location.href,
    webvisor: true,
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    ecommerce: 'dataLayer'
  });
})();

function reachGoal(name) {
  if (typeof window.ym === 'function') {
    window.ym(COUNTER_ID, 'reachGoal', name);
  }
}

// Мобильное меню
const menuToggle = document.querySelector('.site-header__toggle');
const siteNav = document.querySelector('.site-header__nav');
if (menuToggle && siteNav) {
  menuToggle.addEventListener('click', function () {
    const open = siteNav.classList.toggle('is-open');
    menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
}

// Подпись логотипа — по ширине названия
function fitLogo() {
  const logoTitle = document.querySelector('.logo-title');
  const logoSub = document.querySelector('.logo-sub');
  if (!logoTitle || !logoSub) return;
  const width = logoTitle.getComputedTextLength();
  if (!width) return;
  logoSub.setAttribute('textLength', String(width));
}
fitLogo();
window.addEventListener('load', fitLogo);

// Раскрытие e-mail
document.querySelectorAll('[data-mail]').forEach(function (el) {
  const email = 'info@panamaster.ru';
  if (el.tagName !== 'A') return;
  el.href = 'mailto:' + email;
  if (el.classList.contains('email-protected')) {
    el.textContent = email;
    el.classList.remove('email-protected');
  }
  const text = el.querySelector('[data-mail-text]');
  if (text) {
    text.textContent = email;
    text.classList.remove('email-protected');
  }
});

// Цели: звонок, мессенджеры, почта
document.addEventListener('click', function (event) {
  const link = event.target.closest('a[href]');
  if (!link) return;
  const href = link.getAttribute('href');
  if (href.indexOf('tel:') === 0) reachGoal('phone_click');
  else if (href.indexOf('https://wa.me/') === 0) reachGoal('whatsapp_click');
  else if (href.indexOf('https://t.me/') === 0) reachGoal('telegram_click');
  else if (href.indexOf('mailto:') === 0) reachGoal('email_click');
});

// Защита формы от ботов: ключ появляется только после действий человека на странице (без JS заявку не принимаем).
function formKey() {
  const t = Math.floor(Date.now() / 1000);
  let h = 7;
  const src = 'pm' + t;
  for (let i = 0; i < src.length; i++) h = (h * 31 + src.charCodeAt(i)) % 1000003;
  return t + '.' + h;
}

function addFormKey() {
  document.querySelectorAll('.cta-form').forEach(function (form) {
    if (form.querySelector('input[name="pm_key"]')) return;
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'pm_key';
    input.value = formKey();
    form.appendChild(input);
  });
}
['pointerdown', 'keydown', 'touchstart', 'focusin'].forEach(function (type) {
  document.addEventListener(type, addFormKey, { once: true, passive: true });
});

// Форма заявки. Поля скрыты от Вебвизора: телефон и комментарий не попадают в запись сессии.
document.querySelectorAll('.cta-form input, .cta-form textarea').forEach(function (field) {
  field.classList.add('ym-hide-content', 'ym-disable-keys');
});

function setFormStatus(form, text) {
  const label = form.querySelector('.cta-form__label');
  if (label) label.textContent = text;
}

document.querySelectorAll('.cta-form').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { Accept: 'application/json' }
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.ok) {
          setFormStatus(form, 'Заявка отправлена. Перезвоним в рабочее время: пн–пт, 09:00–19:00.');
          form.reset();
          reachGoal('form_submit');
        } else {
          setFormStatus(form, data.message);
        }
      })
      .catch(function () {
        setFormStatus(form, 'Не удалось отправить. Позвоните: +7 926 883-09-39');
      })
      .then(function () {
        if (button) button.disabled = false;
      });
  });
});

// Возврат после отправки без JS
if (/[?&]sent=1/.test(window.location.search)) {
  document.querySelectorAll('.cta-form').forEach(function (form) {
    setFormStatus(form, 'Заявка отправлена. Перезвоним в рабочее время: пн–пт, 09:00–19:00.');
  });
}

// API Яндекс Карт: грузится, когда блок карты близко к экрану. Ключ ограничивается доменом в кабинете разработчика.
const MAPS_KEY = 'c0c181c8-1669-4349-9f4e-2e5717b72076';

function whenNearScreen(el, callback) {
  if (!('IntersectionObserver' in window)) {
    callback();
    return;
  }
  const observer = new IntersectionObserver(function (entries) {
    if (entries[0].isIntersecting) {
      observer.disconnect();
      callback();
    }
  }, { rootMargin: '300px' });
  observer.observe(el);
}

function loadMaps(onReady) {
  const script = document.createElement('script');
  script.src = 'https://api-maps.yandex.ru/2.1/?apikey=' + MAPS_KEY + '&lang=ru_RU';
  script.async = true;
  script.onload = function () { window.ymaps.ready(onReady); };
  document.head.appendChild(script);
}

// Карта на странице контактов: ч/б подложка (CSS), оранжевая метка
const mapEl = document.getElementById('map');
if (mapEl) {

  const initMap = function () {
    const center = [Number(mapEl.dataset.lat), Number(mapEl.dataset.lon)];
    const map = new window.ymaps.Map(mapEl, {
      center: center,
      zoom: 16,
      controls: ['zoomControl']
    });
    map.behaviors.disable('scrollZoom');
    map.geoObjects.add(new window.ymaps.Placemark(center, {
      iconCaption: 'Панамастер',
      balloonContentHeader: 'Панамастер — сервис промышленного оборудования',
      balloonContentBody: 'Москва, улица Искры, дом 31, корпус 1, 1 подъезд, офис 103А<br>+7 926 883-09-39'
    }, {
      preset: 'islands#dotIcon',
      iconColor: '#FFA933'
    }));
  };

  whenNearScreen(mapEl, function () { loadMaps(initMap); });
}

// «Карта работ»: только точки мест работ, без сведений об оборудовании; ч/б подложка, оранжевые метки
const worksMap = document.getElementById('works-map');
if (worksMap) {
  const points = JSON.parse(worksMap.dataset.points || '[]');
  whenNearScreen(worksMap, function () {
    loadMaps(function () {
      const map = new window.ymaps.Map(worksMap, { center: [55.75, 37.62], zoom: 9, controls: ['zoomControl'] });
      map.behaviors.disable('scrollZoom');
      points.forEach(function (p) {
        map.geoObjects.add(new window.ymaps.Placemark([p.lat, p.lon], {},
          { preset: 'islands#dotIcon', iconColor: '#FFA933', hasBalloon: false, hasHint: false }));
      });
      if (points.length > 1) {
        map.setBounds(map.geoObjects.getBounds(), { checkZoomRange: true, zoomMargin: 40 });
      }
    });
  });
}

// Поиск по сайту (search.html): индекс страниц собирает bot/build_sitemap.py в /assets/search.json (не в assets/data — она закрыта в .htaccess)
const searchForm = document.getElementById('site-search');
if (searchForm) {
  const input = document.getElementById('search-q');
  const results = document.getElementById('search-results');
  const status = document.getElementById('search-status');
  const norm = function (s) { return (s || '').toLowerCase().replace(/ё/g, 'е'); };
  const escHtml = function (s) {
    return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  };
  let pages = null;

  // Слово запроса совпадает и по началу основы: «сервопривод» найдёт «сервоприводов», «частотник» — «частотников»
  const stem = function (w) { return w.length > 5 ? w.slice(0, w.length - 2) : w; };

  const run = function () {
    const q = norm(input.value).trim();
    const words = q.split(/[^0-9a-zа-я]+/i).filter(function (w) { return w.length > 1; }).map(stem);
    results.innerHTML = '';
    if (!words.length) { status.textContent = 'Начните вводить запрос.'; return; }
    const found = pages.map(function (p) {
      const t = norm(p.t), d = norm(p.d), h = norm(p.h), x = norm(p.x);
      let score = 0;
      for (const w of words) {
        const s = (t.includes(w) ? 6 : 0) + (d.includes(w) ? 3 : 0) + (h.includes(w) ? 2 : 0) + (x.includes(w) ? 1 : 0);
        if (!s) return null;               // все слова запроса должны найтись на странице
        score += s;
      }
      return { p: p, score: score };
    }).filter(Boolean).sort(function (a, b) { return b.score - a.score; }).slice(0, 20);
    status.textContent = found.length ? 'Найдено страниц: ' + found.length : 'Ничего не нашли — попробуйте другое слово или позвоните нам.';
    results.innerHTML = found.map(function (r) {
      return '<article><h3><a href="' + r.p.u + '">' + escHtml(r.p.t) + '</a></h3><p>' + escHtml(r.p.d) + '</p></article>';
    }).join('');
    if (found.length) reachGoal('site_search');
  };

  searchForm.addEventListener('submit', function (event) {
    event.preventDefault();
    const url = new URL(window.location.href);
    url.searchParams.set('q', input.value);
    history.replaceState(null, '', url);
    if (pages) run();
  });

  fetch('/assets/search.json')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      pages = data;
      input.value = new URLSearchParams(window.location.search).get('q') || '';
      input.addEventListener('input', run);
      run();
      input.focus();
    })
    .catch(function () { status.textContent = 'Поиск временно недоступен. Позвоните: +7 926 883-09-39'; });
}
