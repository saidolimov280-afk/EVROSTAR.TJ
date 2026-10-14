// EVROSTAR service worker: opens the shop fast and without internet.
// Pages: network first, cached copy when offline. Images and Firebase code: cached.
const VERSION='evrostar-v2';
const SHELL=['/','/index.html','/manifest.webmanifest','/icon-192.png','/icon-512.png','/favicon.ico','/install.js','/assets/solar-banner.webp','/assets/battery-banner.webp','/assets/camera-aov.webp'];
const OFFLINE='<!doctype html><html lang="tg"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>EVROSTAR</title><body style="font-family:Arial;padding:30px;background:#071b2c;color:white"><h1>EVROSTAR</h1><p>Барои каталог ва фармоиш пайвасти Интернет лозим аст.</p><p>Для каталога и заказов нужно подключение к интернету.</p><button onclick="location.reload()">Аз нав кӯшиш кардан / Попробовать снова</button></body></html>';
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(VERSION).then(c=>Promise.all(SHELL.map(u=>c.add(u).catch(()=>{})))))});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
function put(req,res){if(res&&res.ok&&(res.type==='basic'||res.type==='cors')){const copy=res.clone();caches.open(VERSION).then(c=>c.put(req,copy)).catch(()=>{})}return res}
self.addEventListener('fetch',e=>{
 const req=e.request;if(req.method!=='GET')return;
 const url=new URL(req.url);
 if(req.mode==='navigate'){
  e.respondWith(fetch(req).then(res=>{if(url.origin===location.origin&&(url.pathname==='/'||url.pathname==='/index.html'))put('/index.html',res.clone());return res}).catch(()=>caches.match(url.pathname==='/admin.html'?req:'/index.html').then(r=>r||new Response(OFFLINE,{headers:{'Content-Type':'text/html; charset=utf-8'}}))));
  return;
 }
 // Versioned Firebase SDK files never change: cache first.
 if(url.hostname==='www.gstatic.com'&&url.pathname.startsWith('/firebasejs/')){
  e.respondWith(caches.match(req).then(r=>r||fetch(req).then(res=>put(req,res))));return;
 }
 // Own images, icons, scripts: show cached copy at once, refresh in background. Videos are skipped (range requests).
 if(url.origin===location.origin&&/\.(webp|png|jpg|jpeg|svg|ico|js|webmanifest)$/i.test(url.pathname)&&!url.pathname.endsWith('/sw.js')){
  e.respondWith(caches.match(req).then(cached=>{const net=fetch(req).then(res=>put(req,res)).catch(()=>cached);return cached||net}));
 }
});
