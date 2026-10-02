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
