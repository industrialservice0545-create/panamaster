'use strict';

const COUNTER_ID = 113092843;

// Яндекс Метрика
(function () {
  window.ym = window.ym || function () {
    (window.ym.a = window.ym.a || []).push(arguments);
  };
  window.ym.l = Date.now();

  const script = document.createElement('script');
  script.async = true;
  script.src = 'https://mc.yandex.ru/metrika/tag.js';
  document.head.appendChild(script);

  window.ym(COUNTER_ID, 'init', {
    ssr: true,
    webvisor: true,
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true
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

// Форма заявки
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

// Карта на странице контактов: ч/б подложка (CSS), оранжевая метка. Грузится, когда блок близко к экрану.
const mapEl = document.getElementById('map');
if (mapEl) {
  const MAPS_KEY = 'c0c181c8-1669-4349-9f4e-2e5717b72076';

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

  const loadMap = function () {
    const script = document.createElement('script');
    script.src = 'https://api-maps.yandex.ru/2.1/?apikey=' + MAPS_KEY + '&lang=ru_RU';
    script.async = true;
    script.onload = function () { window.ymaps.ready(initMap); };
    document.head.appendChild(script);
  };

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) {
        observer.disconnect();
        loadMap();
      }
    }, { rootMargin: '300px' });
    observer.observe(mapEl);
  } else {
    loadMap();
  }
}
