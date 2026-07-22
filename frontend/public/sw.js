/* Service worker — exists to make the app installable and to make repeat
   loads instant. It is deliberately NOT a full offline implementation: this
   is a RAG chatbot, so every answer needs the API and the network. Offline,
   you get the shell and a failed request, which is the honest outcome.

   The one rule that matters here: never let a cache serve a stale app after a
   deploy. Two things guarantee that.
     1. Navigations are network-first. A new deploy's index.html always wins
        when the network is reachable; the cache is only a fallback.
     2. Only /assets/* is cache-first, and Vite content-hashes those
        filenames — a changed file is a different URL, so a cache hit is by
        definition the correct bytes.
   Bump VERSION to force every old cache to be dropped on activate. */
const VERSION = 'v1'
const SHELL = `shell-${VERSION}`
const ASSETS = `assets-${VERSION}`

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(['/', '/manifest.webmanifest'])),
  )
  // Take over immediately rather than waiting for every tab to close —
  // otherwise a user on a stale tab keeps the old worker alive indefinitely.
  self.skipWaiting()
})

/* The worker registers on window 'load', by which point the browser has
   already fetched this build's JS and CSS — so the fetch handler never sees
   them and they never reach the cache. Offline, the cached shell would boot
   and then fail on its own <script src>. The page posts its asset URLs here
   once registration completes, which closes that first-visit gap. */
self.addEventListener('message', (event) => {
  const { type, urls } = event.data || {}
  if (type !== 'CACHE_ASSETS' || !Array.isArray(urls)) return
  event.waitUntil(
    caches.open(ASSETS).then((cache) =>
      // Individually, not addAll: addAll is atomic, so one failed URL would
      // discard the whole set.
      Promise.all(urls.map((u) => cache.add(u).catch(() => {}))),
    ),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== SHELL && k !== ASSETS).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Only same-origin GETs are ours to handle. Everything else — the API on
  // Render, Google Fonts, any cross-origin request — goes straight to the
  // network untouched. Caching API responses here would silently serve
  // yesterday's answer.
  if (request.method !== 'GET' || url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return

  // Content-hashed build output: safe to serve from cache forever.
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((res) => {
            if (res.ok) {
              const copy = res.clone()
              caches.open(ASSETS).then((c) => c.put(request, copy))
            }
            return res
          }),
      ),
    )
    return
  }

  // Navigations: network first so deploys land, cache as the offline fallback.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone()
          caches.open(SHELL).then((c) => c.put('/', copy))
          return res
        })
        .catch(() => caches.match('/').then((hit) => hit || Response.error())),
    )
    return
  }

  // Icons, manifest, anything else static: cache with a network refresh.
  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((res) => {
          if (res.ok) {
            const copy = res.clone()
            caches.open(SHELL).then((c) => c.put(request, copy))
          }
          return res
        }),
    ),
  )
})
