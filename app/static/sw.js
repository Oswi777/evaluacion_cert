self.addEventListener("install", (e)=> self.skipWaiting());
self.addEventListener("activate", (e)=> self.clients.claim());
self.addEventListener("fetch", (e)=> {
  // Passthrough por ahora. Luego: cache-first para estáticos.
});
