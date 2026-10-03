(() => {
let pending;
const installed=()=>matchMedia('(display-mode: standalone)').matches || navigator.standalone===true;
const buttons=()=>document.querySelectorAll('[data-install]');
function sync(){buttons().forEach(b=>{b.textContent=installed()?'Открыть EVROSTAR':'Скачать EVROSTAR';});}
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();pending=e;sync();});
window.addEventListener('appinstalled',()=>{pending=null;sync();document.getElementById('installHelp')?.close();});
document.addEventListener('DOMContentLoaded',()=>{
sync();
buttons().forEach(b=>b.addEventListener('click',async()=>{
if(installed()){location.href='/';return;}
if(pending){const prompt=pending;pending=null;await prompt.prompt();await prompt.userChoice;return;}
const help=document.getElementById('installHelp');
const msg=document.getElementById('installInstructions');
if(msg)msg.textContent=/iPad|iPhone|iPod/.test(navigator.userAgent)?'На iPhone: откройте эту страницу в Safari → Поделиться ↑ → На экран «Домой» → Добавить.':'Откройте эту страницу в Google Chrome. В меню ⋮ выберите «Установить приложение» или «Добавить на главный экран». Если пункта пока нет, обновите страницу и попробуйте снова.';
help?.showModal();
}));
document.getElementById('closeInstall')?.addEventListener('click',()=>document.getElementById('installHelp').close());
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
});
})();
