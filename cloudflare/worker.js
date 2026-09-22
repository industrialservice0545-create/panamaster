export default {
  async fetch(request) {
    const url = new URL(request.url);
    const telegramUrl = `https://api.telegram.org${url.pathname}${url.search}`;

    const init = {
      method: request.method,
      headers: request.headers,
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body;
    }

    return fetch(telegramUrl, init);
  }
};
