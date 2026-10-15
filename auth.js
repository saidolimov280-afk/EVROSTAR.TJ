// EVROSTAR: registration by phone number (SMS code) inside the app.
// Shown only in the Android app and the installed PWA, not on the public website (keeps SEO intact).
// Flow: phone → SMS code → name + city → personal purchase code (EVRO-XXXXXX).
import { initializeApp, getApps } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js';
import { getAuth, RecaptchaVerifier, signInWithPhoneNumber, onAuthStateChanged, signOut } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';
import { getFirestore, doc, getDoc, setDoc, serverTimestamp } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-firestore.js';

const cfg = {
  apiKey: 'AIzaSyA_zCecmxy5IYVzh2wESMDRZ_rZlFpWx6w',
  authDomain: 'evrostar-c7c85.firebaseapp.com',
  projectId: 'evrostar-c7c85',
  storageBucket: 'evrostar-c7c85.firebasestorage.app',
  messagingSenderId: '869866043004',
  appId: '1:869866043004:web:4b45a671f60d5faa04bbf9'
};

const ua = navigator.userAgent || '';
const isApp = /EVROSTARApp/.test(ua) ||
  (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true ||
  new URLSearchParams(location.search).has('register');

function lang() { try { return window.evroLang || localStorage.getItem('evrostar_language') || 'tg'; } catch { return 'tg'; } }
const T = {
  title: { tg: 'Хуш омадед ба EVROSTAR', ru: 'Добро пожаловать в EVROSTAR' },
  phoneLead: { tg: 'Барои харид бо рақами телефон регистратсия кунед. Ба рақами шумо SMS-код меояд.', ru: 'Для покупок зарегистрируйтесь по номеру телефона. На ваш номер придёт SMS-код.' },
  phone: { tg: 'Рақами телефон', ru: 'Номер телефона' },
  send: { tg: 'Гирифтани код', ru: 'Получить код' },
  codeLead: { tg: 'Коди 6-рақамаро, ки ба {p} фиристода шуд, ворид кунед.', ru: 'Введите 6-значный код, отправленный на {p}.' },
  code: { tg: 'Коди SMS', ru: 'Код из SMS' },
  verify: { tg: 'Тасдиқ', ru: 'Подтвердить' },
  resend: { tg: 'Кодро боз фиристед', ru: 'Отправить код снова' },
  resendIn: { tg: 'Боз фиристодан пас аз {s} с', ru: 'Повторно через {s} с' },
  change: { tg: 'Рақамро иваз кунед', ru: 'Изменить номер' },
  profileLead: { tg: 'Рақам тасдиқ шуд. Регистратсияро пурра кунед.', ru: 'Номер подтверждён. Завершите регистрацию.' },
  name: { tg: 'Ному насаб', ru: 'Имя и фамилия' },
  city: { tg: 'Шаҳр / ноҳия', ru: 'Город / район' },
  finish: { tg: 'Анҷоми регистратсия', ru: 'Завершить регистрацию' },
  doneTitle: { tg: 'Регистратсия анҷом ёфт!', ru: 'Регистрация завершена!' },
  doneLead: { tg: 'Ин коди шахсии харидори шумост. Ҳангоми фармоиш ӯ худкор илова мешавад.', ru: 'Это ваш личный код покупателя. При заказе он добавляется автоматически.' },
  copy: { tg: 'Нусхабардорӣ', ru: 'Скопировать' },
  copied: { tg: 'Нусха гирифта шуд', ru: 'Скопировано' },
  toShop: { tg: 'Ба мағоза', ru: 'В магазин' },
  badPhone: { tg: 'Рақамро дуруст ворид кунед: 9 рақам пас аз +992.', ru: 'Введите номер правильно: 9 цифр после +992.' },
  badCode: { tg: 'Код нодуруст аст. Аз нав санҷед.', ru: 'Неверный код. Попробуйте ещё раз.' },
  expired: { tg: 'Мӯҳлати код гузашт. Коди навро гиред.', ru: 'Срок кода истёк. Запросите новый.' },
  many: { tg: 'Кӯшишҳо зиёд шуданд. Каме дертар боз кӯшиш кунед.', ru: 'Слишком много попыток. Попробуйте позже.' },
  needName: { tg: 'Ному насабро нависед.', ru: 'Укажите имя и фамилию.' },
  needCity: { tg: 'Шаҳр ё ноҳияро интихоб кунед.', ru: 'Выберите город или район.' },
  net: { tg: 'Интернетро санҷед ва боз кӯшиш кунед.', ru: 'Проверьте интернет и попробуйте снова.' },
  unavailable: { tg: 'Регистратсия бо SMS ҳоло дастрас нест. Шумо метавонед бе регистратсия идома диҳед.', ru: 'Регистрация по SMS сейчас недоступна. Можно продолжить без регистрации.' },
  skip: { tg: 'Идома бе регистратсия', ru: 'Продолжить без регистрации' },
  wait: { tg: 'Лутфан интизор шавед…', ru: 'Пожалуйста, подождите…' },
  myCode: { tg: 'Коди ман', ru: 'Мой код' },
  logout: { tg: 'Баромадан', ru: 'Выйти' },
  other: { tg: 'Дигар', ru: 'Другое' }
};
const tr = (k, vars = {}) => (T[k]?.[lang()] || T[k]?.tg || k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '');
const CITIES = ['Ҳисор', 'Душанбе', 'Турсунзода', 'Шаҳринав', 'Ваҳдат', 'Рӯдакӣ', 'Бохтар', 'Кӯлоб', 'Хуҷанд', 'Истаравшан', 'Панҷакент', 'Хоруғ', 'Вахш', 'Данғара', 'Норак', 'Роғун', 'Файзобод'];

function codeFor(uid) {
  // Stable personal code derived from the account id: same customer always gets the same code.
  const A = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let out = '';
  for (let k = 0; k < 6; k++) {
    let h = (2166136261 ^ (k * 374761393)) >>> 0;
    for (const c of uid + ':' + k) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; }
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b) >>> 0; h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35) >>> 0; h ^= h >>> 16;
    out += A[(h >>> 0) % A.length];
  }
  return 'EVRO-' + out;
}

function css() {
  const s = document.createElement('style');
  s.textContent = `
#evroGate{position:fixed;inset:0;z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px;overflow:auto;
 background:radial-gradient(circle at 85% 8%,#ffb53a55 0,#ffb53a00 38%),linear-gradient(160deg,#071b2c 0%,#0d3550 55%,#125d73 100%);color:#fff;font-family:Arial,sans-serif}
#evroGate .gCard{width:100%;max-width:420px;background:#ffffff12;border:1px solid #ffffff26;border-radius:22px;padding:26px 22px;backdrop-filter:blur(8px);box-shadow:0 20px 50px #0006}
#evroGate .gLogo{font-weight:900;font-size:30px;color:#ff9f1c;letter-spacing:.5px;margin:0 0 4px}
#evroGate h2{margin:6px 0 10px;font-size:21px}
#evroGate p{margin:0 0 16px;line-height:1.45;color:#d9e6f0}
#evroGate label{display:block;font-size:14px;margin:0 0 6px;color:#c9d8e4}
#evroGate .gRow{display:flex;gap:8px;margin-bottom:14px}
#evroGate .gPre{display:flex;align-items:center;padding:0 12px;border-radius:12px;background:#ffffff1c;font-weight:700}
#evroGate input,#evroGate select{width:100%;min-height:50px;padding:12px 14px;border-radius:12px;border:1px solid #ffffff40;background:#fff;color:#142033;font-size:18px;margin-bottom:14px}
#evroGate .gRow input{margin:0}
#evroGate #gCode{letter-spacing:8px;text-align:center;font-size:24px;font-weight:700}
#evroGate button{width:100%;min-height:50px;border:0;border-radius:12px;font-size:17px;font-weight:800;cursor:pointer}
#evroGate .gMain{background:#ff9f1c;color:#102033}
#evroGate .gMain:disabled{opacity:.6}
#evroGate .gLink{background:transparent;color:#ffd08a;font-weight:700;min-height:44px;margin-top:6px}
#evroGate .gLink:disabled{color:#9fb3c3}
#evroGate .gErr{color:#ffb4a8;min-height:20px;margin:0 0 10px;font-size:15px}
#evroGate .gCodeBox{font-size:30px;font-weight:900;letter-spacing:2px;text-align:center;background:#fff;color:#071b2c;border-radius:14px;padding:16px;margin:0 0 12px;border:3px dashed #ff9f1c}
#evroGate .gSun{width:64px;height:64px;margin:0 auto 10px;display:block}
#evroGate [hidden]{display:none!important}
#evroCodeChip{position:fixed;left:14px;bottom:calc(88px + env(safe-area-inset-bottom));z-index:25;background:#071b2c;color:#fff;border:2px solid #ff9f1c;border-radius:999px;padding:8px 14px;font:700 14px Arial,sans-serif;box-shadow:0 6px 18px #0004;cursor:pointer}
body.evroLocked{overflow:hidden}`;
  document.head.appendChild(s);
}

function el(html) { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }

let auth, db, gate, recaptcha, confirmation, resendTimer, fullPhone = '';

function start() {
  css();
  const app = getApps()[0] || initializeApp(cfg);
  auth = getAuth(app);
  auth.languageCode = lang() === 'ru' ? 'ru' : 'tg';
  db = getFirestore(app);
  onAuthStateChanged(auth, async user => {
    if (!user) { window.evroCustomer = null; if (!skippedRecently()) showGate('phone'); return; }
    try {
      const snap = await getDoc(doc(db, 'customers', user.uid));
      if (snap.exists() && snap.data().name) { ready(snap.data()); hideGate(); }
      else { fullPhone = user.phoneNumber || fullPhone; showGate('profile'); }
    } catch (e) {
      console.warn('customers read', e);
      // Profile not readable (rules not set yet or offline): do not block shopping for a verified phone.
      ready({ phone: user.phoneNumber, code: codeFor(user.uid), name: '' }); hideGate();
    }
  });
}

function build() {
  if (gate) return;
  const opts = CITIES.map(c => `<option>${c}</option>`).join('') + `<option value="other">${tr('other')}</option>`;
  gate = el(`<div id="evroGate" role="dialog" aria-modal="true" aria-labelledby="gTitle"><div class="gCard">
  <svg class="gSun" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="12" fill="#ff9f1c"/><g stroke="#ff9f1c" stroke-width="4" stroke-linecap="round"><path d="M32 6v8M32 50v8M6 32h8M50 32h8M13.6 13.6l5.7 5.7M44.7 44.7l5.7 5.7M13.6 50.4l5.7-5.7M44.7 19.3l5.7-5.7"/></g></svg>
  <div class="gLogo" style="text-align:center">EVROSTAR</div>
  <form id="gPhoneStep"><h2 id="gTitle">${tr('title')}</h2><p>${tr('phoneLead')}</p>
   <label for="gPhone">${tr('phone')}</label>
   <div class="gRow"><span class="gPre">+992</span><input id="gPhone" type="tel" inputmode="numeric" autocomplete="tel-national" maxlength="12" placeholder="00 000 0000" required></div>
   <p class="gErr" id="gErr1" role="alert"></p><button class="gMain" id="gSend" type="submit">${tr('send')}</button>
   <button class="gLink" id="gSkip" type="button" hidden>${tr('skip')}</button></form>
  <form id="gCodeStep" hidden><h2>${tr('code')}</h2><p id="gCodeLead"></p>
   <label for="gCode">${tr('code')}</label><input id="gCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required>
   <p class="gErr" id="gErr2" role="alert"></p><button class="gMain" id="gVerify" type="submit">${tr('verify')}</button>
   <button class="gLink" id="gResend" type="button" disabled></button><button class="gLink" id="gChange" type="button">${tr('change')}</button></form>
  <form id="gProfileStep" hidden><h2>${tr('title')}</h2><p>${tr('profileLead')}</p>
   <label for="gName">${tr('name')}</label><input id="gName" autocomplete="name" maxlength="100" required>
   <label for="gCity">${tr('city')}</label><select id="gCity" required><option value=""></option>${opts}</select>
   <input id="gCityOther" maxlength="60" hidden placeholder="${tr('city')}">
   <p class="gErr" id="gErr3" role="alert"></p><button class="gMain" id="gFinish" type="submit">${tr('finish')}</button></form>
  <div id="gDoneStep" hidden><h2>${tr('doneTitle')}</h2><p>${tr('doneLead')}</p><div class="gCodeBox" id="gMyCode"></div>
   <button class="gLink" id="gCopy" type="button">${tr('copy')}</button><button class="gMain" id="gToShop" type="button">${tr('toShop')}</button></div>
  <div id="gRecaptcha"></div></div></div>`);
  document.body.appendChild(gate);
  const $ = id => gate.querySelector('#' + id);
  $('gPhone').addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 9); });
  $('gCode').addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 6); if (e.target.value.length === 6) $('gCodeStep').requestSubmit(); });
  $('gCity').addEventListener('change', e => { $('gCityOther').hidden = e.target.value !== 'other'; });
  $('gPhoneStep').addEventListener('submit', sendCode);
  $('gCodeStep').addEventListener('submit', verifyCode);
  $('gProfileStep').addEventListener('submit', saveProfile);
  $('gResend').addEventListener('click', () => sendCode());
  $('gChange').addEventListener('click', () => showGate('phone'));
  $('gSkip').addEventListener('click', () => { try { localStorage.setItem(SKIP_KEY, String(Date.now())); } catch {} hideGate(); });
  $('gCopy').addEventListener('click', () => { const c = $('gMyCode').textContent; navigator.clipboard?.writeText(c).then(() => { $('gCopy').textContent = tr('copied'); }).catch(() => {}); });
  $('gToShop').addEventListener('click', () => hideGate());
}

// When SMS is not available yet and the customer chose to continue, do not ask again for a day.
const SKIP_KEY = 'evrostar_reg_skip';
function skippedRecently() { try { return Date.now() - Number(localStorage.getItem(SKIP_KEY) || 0) < 864e5; } catch { return false; } }
function splashOn() { return !!document.getElementById('welcomeSplash'); }
let waiting = null;
function showGate(step) {
  // Let the welcome video finish first, then ask to register.
  if (splashOn()) {
    if (!waiting) window.addEventListener('evroentryfinished', () => { const s = waiting; waiting = null; showGate(s); }, { once: true });
    waiting = step; return;
  }
  build();
  document.body.classList.add('evroLocked');
  gate.hidden = false;
  for (const id of ['gPhoneStep', 'gCodeStep', 'gProfileStep', 'gDoneStep']) gate.querySelector('#' + id).hidden = true;
  const map = { phone: 'gPhoneStep', code: 'gCodeStep', profile: 'gProfileStep', done: 'gDoneStep' };
  gate.querySelector('#' + map[step]).hidden = false;
  const focus = { phone: 'gPhone', code: 'gCode', profile: 'gName' }[step];
  if (focus) setTimeout(() => gate.querySelector('#' + focus)?.focus(), 50);
}
function hideGate() { waiting = null; if (gate) gate.hidden = true; document.body.classList.remove('evroLocked'); }

function errText(e) {
  const c = String(e?.code || '');
  if (c.includes('invalid-phone-number')) return tr('badPhone');
  if (c.includes('invalid-verification-code')) return tr('badCode');
  if (c.includes('code-expired')) return tr('expired');
  if (c.includes('too-many-requests') || c.includes('quota-exceeded')) return tr('many');
  if (c.includes('network-request-failed')) return tr('net');
  return null;
}
// Firebase not set up for SMS yet (provider off, no billing, region blocked, domain not authorized):
// let the customer keep shopping instead of locking the app.
function setupProblem(e) {
  const c = String(e?.code || '');
  return /operation-not-allowed|billing-not-enabled|unauthorized-domain|invalid-app-credential|captcha-check-failed|app-not-authorized|internal-error|admin-restricted|argument-error/.test(c);
}

async function sendCode(ev) {
  ev?.preventDefault();
  const $ = id => gate.querySelector('#' + id);
  const digits = $('gPhone').value.replace(/\D/g, '');
  const err = $('gErr1'), btn = $('gSend');
  if (!ev) { $('gResend').disabled = true; }
  if (digits.length !== 9) { err.textContent = tr('badPhone'); return; }
  fullPhone = '+992' + digits;
  err.textContent = ''; btn.disabled = true; btn.textContent = tr('wait');
  try {
    if (!recaptcha) recaptcha = new RecaptchaVerifier(auth, 'gRecaptcha', { size: 'invisible' });
    confirmation = await signInWithPhoneNumber(auth, fullPhone, recaptcha);
    $('gCodeLead').textContent = tr('codeLead', { p: fullPhone });
    $('gCode').value = ''; $('gErr2').textContent = '';
    showGate('code'); countdown(60);
  } catch (e) {
    console.error('sendCode', e);
    try { recaptcha?.clear(); } catch {} recaptcha = null; gate.querySelector('#gRecaptcha').innerHTML = '';
    if (setupProblem(e)) { err.textContent = tr('unavailable'); $('gSkip').hidden = false; }
    else err.textContent = errText(e) || tr('net');
    if (!ev) showGate('phone');
  } finally { btn.disabled = false; btn.textContent = tr('send'); }
}

function countdown(sec) {
  const b = gate.querySelector('#gResend');
  clearInterval(resendTimer); b.disabled = true;
  const tick = () => { if (sec <= 0) { clearInterval(resendTimer); b.disabled = false; b.textContent = tr('resend'); return; } b.textContent = tr('resendIn', { s: sec-- }); };
  tick(); resendTimer = setInterval(tick, 1000);
}

async function verifyCode(ev) {
  ev.preventDefault();
  const $ = id => gate.querySelector('#' + id);
  const code = $('gCode').value.trim(), btn = $('gVerify'), err = $('gErr2');
  if (!/^\d{6}$/.test(code) || !confirmation) { err.textContent = tr('badCode'); return; }
  btn.disabled = true; btn.textContent = tr('wait'); err.textContent = '';
  try { await confirmation.confirm(code); /* onAuthStateChanged continues to the profile step */ }
  catch (e) { console.error('verify', e); err.textContent = errText(e) || tr('badCode'); }
  finally { btn.disabled = false; btn.textContent = tr('verify'); }
}

async function saveProfile(ev) {
  ev.preventDefault();
  const $ = id => gate.querySelector('#' + id);
  const user = auth.currentUser, err = $('gErr3'), btn = $('gFinish');
  if (!user) { showGate('phone'); return; }
  const name = $('gName').value.trim();
  const city = $('gCity').value === 'other' ? $('gCityOther').value.trim() : $('gCity').value;
  if (name.length < 2) { err.textContent = tr('needName'); return; }
  if (!city) { err.textContent = tr('needCity'); return; }
  const profile = { name: name.slice(0, 100), city: city.slice(0, 60), phone: user.phoneNumber || fullPhone, code: codeFor(user.uid), lang: lang(), createdAt: serverTimestamp() };
  btn.disabled = true; btn.textContent = tr('wait'); err.textContent = '';
  try {
    await setDoc(doc(db, 'customers', user.uid), profile, { merge: true });
  } catch (e) { console.warn('customers write', e); /* still give the code; it is derived from the account */ }
  finally { btn.disabled = false; btn.textContent = tr('finish'); }
  ready(profile);
  $('gMyCode').textContent = profile.code;
  showGate('done');
}

function ready(p) {
  const user = auth.currentUser;
  const c = { name: p.name || '', phone: p.phone || user?.phoneNumber || '', city: p.city || '', code: p.code || (user ? codeFor(user.uid) : ''), uid: user?.uid || '' };
  window.evroCustomer = c;
  const fill = (id, v) => { const i = document.getElementById(id); if (i && !i.value && v) i.value = v; };
  fill('customerName', c.name); fill('customerPhone', c.phone); fill('customerAddress', c.city);
  fill('svcName', c.name); fill('svcPhone', c.phone);
  let chip = document.getElementById('evroCodeChip');
  if (!chip && c.code) {
    chip = el(`<button id="evroCodeChip" type="button" aria-label="${tr('myCode')}"></button>`);
    chip.addEventListener('click', () => {
      if (confirm(`${tr('myCode')}: ${c.code}\n\n${tr('logout')}?`)) signOut(auth).catch(() => {});
    });
    document.body.appendChild(chip);
  }
  if (chip) chip.textContent = `${tr('myCode')}: ${c.code}`;
  window.dispatchEvent(new CustomEvent('evrocustomer', { detail: c }));
}

// Start last, after all declarations above are initialised.
if (!isApp) window.evroCustomer = null; else start();
