self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
if(event.request.mode==='navigate')event.respondWith(fetch(event.request).catch(()=>new Response('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>EVROSTAR</title><body style="font-family:Arial;padding:30px;background:#071b2c;color:white"><h1>EVROSTAR</h1><p>Для каталога и заказов нужно подключение к интернету.</p><button onclick="location.reload()">Попробовать снова</button></body></html>',{headers:{'Content-Type':'text/html; charset=utf-8'}})));
});
