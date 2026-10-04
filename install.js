(() => {
let pending;
const installed=()=>matchMedia('(display-mode: standalone)').matches || navigator.standalone===true;
const buttons=()=>document.querySelectorAll('[data-install]');
const t=(key,ru,tg)=>window.evroT?window.evroT(key):(document.documentElement.lang==='tg'?tg:ru);
function sync(){buttons().forEach(b=>{b.textContent=installed()?t('open','Открыть EVROSTAR','Кушодани EVROSTAR'):t('download','Скачать EVROSTAR','Насб кардани EVROSTAR');});}
window.addEventListener('evrolanguagechange',sync);
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();pending=e;sync();});
window.addEventListener('appinstalled',()=>{pending=null;sync();document.getElementById('installHelp')?.close();});
document.addEventListener('DOMContentLoaded',()=>{
sync();
buttons().forEach(b=>b.addEventListener('click',async()=>{
if(/Android/i.test(navigator.userAgent)){location.href='/downloads/EVROSTAR.apk';return;}
if(installed()){location.href='/';return;}
if(pending){const prompt=pending;pending=null;await prompt.prompt();await prompt.userChoice;return;}
const help=document.getElementById('installHelp');
const msg=document.getElementById('installInstructions');
if(msg)msg.textContent=/iPad|iPhone|iPod/.test(navigator.userAgent)?(document.documentElement.lang==='tg'?'Дар iPhone: саҳифаро дар Safari кушоед → Мубодила ↑ → Ба экрани асосӣ → Илова кардан.':'На iPhone: откройте эту страницу в Safari → Поделиться ↑ → На экран «Домой» → Добавить.'):(document.documentElement.lang==='tg'?'Саҳифаро дар Google Chrome кушоед. Дар менюи ⋮ «Насб кардани барнома» ё «Илова ба экрани асосӣ»-ро интихоб кунед. Агар набошад, саҳифаро нав карда, боз кӯшиш кунед.':'Откройте эту страницу в Google Chrome. В меню ⋮ выберите «Установить приложение» или «Добавить на главный экран». Если пункта пока нет, обновите страницу и попробуйте снова.');
help?.showModal();
}));
document.getElementById('closeInstall')?.addEventListener('click',()=>document.getElementById('installHelp').close());
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
});
})();
