// E2E: ключевые сценарии посетителя. Внешние сервисы (Метрика, Карты, send.php) подменяются.
const { test, expect } = require('@playwright/test');

const INDUSTRIES = ['metalworking', 'food', 'pharma', 'chemical', 'woodworking',
  'printing', 'plastics', 'textile', 'packaging', 'electrical-equipment', 'building-materials'];

// Отключаем внешние скрипты и записываем вызовы ym(), чтобы проверять цели Метрики
test.beforeEach(async ({ page }) => {
  await page.route(/mc\.yandex\.ru|api-maps\.yandex\.ru/, route => route.fulfill({ status: 204, body: '' }));
  await page.addInitScript(() => {
    window.__goals = [];
    window.ym = function () {
      if (arguments[1] === 'reachGoal') window.__goals.push(arguments[2]);
    };
  });
});

test('главная: заголовок, телефон и 9 отраслей', async ({ page }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page).toHaveTitle(/Панамастер/);
  await expect(page.locator('h1')).toHaveCount(1);
  await expect(page.locator('a[href="tel:+79268830939"]').first()).toBeVisible();
  await expect(page.locator('a[href^="/services/industry-"]')).toHaveCount(9);
  expect(errors).toEqual([]);
});

test('меню ведёт на «Примеры работ» и «Контакты»', async ({ page, isMobile }) => {
  await page.goto('/');
  if (isMobile) await page.click('.site-header__toggle');
  await page.click('.site-header__nav >> text=Примеры работ');
  await expect(page).toHaveURL(/\/cases\.html$/);
  await expect(page.locator('h1')).toHaveText('Примеры работ');
  if (isMobile) await page.click('.site-header__toggle');
  await page.click('.site-header__nav >> text=Контакты');
  await expect(page).toHaveURL(/\/contacts\.html$/);
});

test('мобильное меню открывается и закрывается', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'бургер только на мобильном');
  await page.goto('/');
  const toggle = page.locator('.site-header__toggle');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.site-header__nav')).toHaveClass(/is-open/);
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
});

test('почта раскрывается из защищённой записи', async ({ page }) => {
  await page.goto('/contacts.html');
  await expect(page.locator('[data-mail-text]')).toHaveText('info@panamaster.ru');
  await expect(page.locator('.site-footer [data-mail]')).toHaveText('info@panamaster.ru');
});

test('форма: успешная заявка показывает подтверждение и цель form_submit', async ({ page }) => {
  let posted = null;
  await page.route('**/send.php', async route => {
    posted = route.request().postData();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, message: 'Заявка отправлена' }) });
  });
  await page.goto('/');
  await page.fill('#home-phone', '+7 926 000-00-00');
  await page.click('#zayavka button[type=submit]');
  await expect(page.locator('#zayavka .cta-form__label')).toContainText('Заявка отправлена');
  expect(posted).toContain('name="page"');
  expect(posted).toContain('+7 926 000-00-00');
  expect(await page.evaluate(() => window.__goals)).toContain('form_submit');
  await expect(page.locator('#home-phone')).toHaveValue('');
});

test('форма: ошибка сервера показывает сообщение', async ({ page }) => {
  await page.route('**/send.php', route => route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ ok: false, message: 'Проверьте номер телефона' }) }));
  await page.goto('/contacts.html');
  await page.fill('#zayavka input[type=tel]', '123');
  await page.click('#zayavka button[type=submit]');
  await expect(page.locator('#zayavka .cta-form__label')).toHaveText('Проверьте номер телефона');
});

test('форма: нет сети — предлагаем позвонить', async ({ page }) => {
  await page.route('**/send.php', route => route.abort());
  await page.goto('/');
  await page.fill('#home-phone', '+7 926 000-00-00');
  await page.click('#zayavka button[type=submit]');
  await expect(page.locator('#zayavka .cta-form__label')).toContainText('+7 926 883-09-39');
});

test('форма требует телефон (HTML-валидация)', async ({ page }) => {
  let called = false;
  await page.route('**/send.php', route => { called = true; route.abort(); });
  await page.goto('/');
  await page.click('#zayavka button[type=submit]');
  expect(await page.locator('#home-phone').evaluate(el => el.validity.valueMissing)).toBe(true);
  expect(called).toBe(false);
});

test('клики по телефону и мессенджерам отправляют цели Метрики', async ({ page, context }) => {
  await context.route(/t\.me|wa\.me/, route => route.fulfill({ status: 204, body: '' }));
  await page.goto('/contacts.html');
  await page.evaluate(() => {
    // не уходить со страницы по tel:/внешним ссылкам
    document.addEventListener('click', e => e.preventDefault());
  });
  await page.click('.data-table--contacts a[href^="tel:"]');
  await page.click('.data-table--contacts a[href^="https://t.me/"]');
  await page.click('.data-table--contacts a[href^="https://wa.me/"]');
  await page.click('.data-table--contacts a[href^="mailto:"]');
  expect(await page.evaluate(() => window.__goals)).toEqual(['phone_click', 'telegram_click', 'whatsapp_click', 'email_click']);
});

for (const slug of INDUSTRIES) {
  test(`отрасль ${slug}: страница, фото и заявка`, async ({ page }) => {
    const res = await page.goto(`/services/industry-${slug}.html`);
    expect(res.status()).toBe(200);
    await expect(page.locator('h1')).toContainText('ремонт');
    const img = page.locator('.case-hero__photo img');
    await expect(img).toBeVisible();
    expect(await img.evaluate(el => el.naturalWidth)).toBeGreaterThan(0);
    await expect(page.locator('#zayavka input[name=page]')).toHaveValue(/^Отрасль: /);
    await expect(page.locator('.breadcrumbs')).toContainText('Главная');
  });
}

test('кейс CODIMAG: фото загружены, ссылка на отрасль работает', async ({ page }) => {
  await page.goto('/cases.html');
  await page.click('text=CODIMAG VIVA 340: устранено смещение рапорта');
  await expect(page).toHaveURL(/codimag-viva-340\.html$/);
  for (const img of await page.locator('.case-photo img').all()) {
    await img.scrollIntoViewIfNeeded();
    await expect.poll(() => img.evaluate(el => el.complete && el.naturalWidth)).toBeGreaterThan(0);
  }
  await page.click('text=Ремонт оборудования: полиграфия');
  await expect(page).toHaveURL(/industry-printing\.html$/);
});

test('контакты: блок карты и адрес мастерской', async ({ page }) => {
  await page.goto('/contacts.html');
  await expect(page.locator('#map.map')).toHaveAttribute('data-lat', /55\.86/);
  await expect(page.locator('main')).toContainText('улица Искры, дом 31, корпус 1');
  await expect(page.locator('main')).not.toContainText('Лубянск');
});

test('нет горизонтальной прокрутки на ключевых страницах', async ({ page }) => {
  for (const url of ['/', '/contacts.html', '/cases.html', '/services/industry-food.html', '/cases/codimag-viva-340.html']) {
    await page.goto(url);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, url).toBeLessThanOrEqual(1);
  }
});
