// Прокси к api.telegram.org для хостинга, откуда Telegram недоступен.
// Пускает только методы, которые нужны сайту и боту, и скачивание файлов.
// Если в Worker задана переменная PROXY_SECRET, запрос должен нести заголовок X-Proxy-Secret с тем же значением.
const METHODS = new Set(['sendMessage', 'getUpdates', 'getFile', 'answerCallbackQuery', 'sendMediaGroup', 'getMe']);
const BOT_PATH = /^\/bot\d+:[A-Za-z0-9_-]+\/([A-Za-z]+)$/;
const FILE_PATH = /^\/file\/bot\d+:[A-Za-z0-9_-]+\/[A-Za-z0-9_\/.-]+$/;

export default {
  async fetch(request, env) {
    if (env.PROXY_SECRET && request.headers.get('X-Proxy-Secret') !== env.PROXY_SECRET) {
      return new Response('Forbidden', { status: 403 });
    }

    const url = new URL(request.url);
    const method = url.pathname.match(BOT_PATH);
    const isFile = FILE_PATH.test(url.pathname) && request.method === 'GET';
    if (!(method && METHODS.has(method[1])) && !isFile) {
      return new Response('Not found', { status: 404 });
    }

    const headers = new Headers(request.headers);
    headers.delete('X-Proxy-Secret');
    const init = { method: request.method, headers: headers };
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      init.body = request.body;
    }

    return fetch(`https://api.telegram.org${url.pathname}${url.search}`, init);
  }
};
