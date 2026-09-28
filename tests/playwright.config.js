// E2E-тесты Панамастер. Сайт раздаётся локально из корня репозитория, браузер — установленный Google Chrome.
// Запуск: cd tests && npx playwright test
const { defineConfig, devices } = require('@playwright/test');

const PORT = 18090;

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 30000,
  fullyParallel: true,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: 'chrome',
  },
  webServer: {
    command: `python3 -m http.server ${PORT} --bind 127.0.0.1 --directory ..`,
    url: `http://127.0.0.1:${PORT}/index.html`,
    reuseExistingServer: true,
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'], channel: 'chrome' } },
  ],
});
