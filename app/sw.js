/* Keep the interface available when the local server or internet is unavailable.
   API responses are deliberately excluded: the app owns dated roster snapshots. */
const CACHE = 'fantasy-workspace-actionable-v5';
const SHELL = ['/', '/index.html', '/styles.css', '/app.js', '/roster-import.js',
  '/players.html', '/season.js', '/draft-board-2026.html', '/board-data.js'];
const LOGOS = 'ari atl bal buf car chi cin cle dal den det gb hou ind jax kc lac lar lv mia min ne no nyg nyj phi pit sea sf tb ten wsh'.split(' ').map(team => '/assets/teams/' + team + '.png');
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(async cache => { await cache.addAll(SHELL); await Promise.allSettled(LOGOS.map(url => cache.add(url))); }).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('fantasy-workspace-') && key !== CACHE)
    .map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  const logo = /^\/assets\/teams\/[a-z]{2,3}\.png$/.test(url.pathname);
  if (!SHELL.includes(url.pathname) && !logo) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const key = url.pathname;
    const saved = await cache.match(key);
    if (logo && saved) return saved;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2000);
    try {
      const response = await fetch(event.request, {signal: controller.signal});
      if (!response.ok) throw new Error('Static asset unavailable');
      await cache.put(key, response.clone());
      return response;
    } catch {
      if (saved) return saved;
      return new Response('This page has not been saved yet. Start the local dashboard to load it once.',
        {status:503,headers:{'Content-Type':'text/plain'}});
    } finally { clearTimeout(timer); }
  })());
});
