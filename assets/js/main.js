'use strict';

// Яндекс Метрика
(function () {
  const COUNTER_ID = 113092843;

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
