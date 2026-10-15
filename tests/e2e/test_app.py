"""EVROSTAR end-to-end tests (headless Chromium, Firebase replaced by in-page fakes).

Run:  pip install playwright && python -m playwright install chromium
      python tests/e2e/test_app.py
Covers: app registration by SMS (phone -> code -> profile -> purchase code),
website without registration, checkout prefill + code in WhatsApp text,
admin panel customers list, and that a phone-registered customer cannot open admin.
"""
import asyncio, functools, http.server, os, sys, threading, urllib.parse
from playwright.async_api import async_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PORT = 8765
BASE = f'http://127.0.0.1:{PORT}'
APP_UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7; wv) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36 EVROSTARApp/2'

# Fake Firebase SDK. Behaviour is driven by window.__FAKE set in an init script.
FAKE_APP = "export const getApps=()=>[];export const initializeApp=()=>({});"
FAKE_AUTH = r"""
const F=window.__FAKE||(window.__FAKE={});const subs=[];
const auth={currentUser:F.user||null};
export const getAuth=()=>auth;
export class RecaptchaVerifier{constructor(a,id,o){this.o=o||{}}render(){setTimeout(()=>{F.captchaRendered=(F.captchaRendered||0)+1;if(!F.captchaUnticked)this.o.callback&&this.o.callback()},5);return Promise.resolve(1)}clear(){}}
export const onAuthStateChanged=(a,f)=>{subs.push(f);setTimeout(()=>f(auth.currentUser),10);return()=>{}};
const emit=()=>subs.forEach(f=>f(auth.currentUser));
export const signInWithPhoneNumber=async(a,phone)=>{F.sentTo=phone;return{confirm:async c=>{
  if(c!=='123456'){const e=new Error('bad');e.code='auth/invalid-verification-code';throw e}
  auth.currentUser={uid:'uidTEST1234567890',phoneNumber:phone,email:null,providerData:[{providerId:'phone'}]};emit()}}};
export const signInWithEmailAndPassword=async()=>{auth.currentUser={uid:'admin',email:'admin@example.com',providerData:[{providerId:'password'}]};emit()};
export const signOut=async()=>{auth.currentUser=null;emit()};
"""
FAKE_FS = r"""
const F=window.__FAKE||(window.__FAKE={});F.writes=F.writes||[];
export const getFirestore=()=>({});export const initializeFirestore=()=>({});
export const persistentLocalCache=()=>0;export const persistentMultipleTabManager=()=>0;
export const collection=(db,name)=>({name});export const doc=(db,name,id)=>({name:name&&name.name?name.name:name,id:id||'auto'+Math.random().toString(36).slice(2,8)});
export const query=(c)=>c;export const where=()=>0;export const limit=()=>0;export const orderBy=()=>0;export const serverTimestamp=()=>null;
const docs=n=>(F.data&&F.data[n]||[]).map((d,i)=>({id:d.id||String(i),data:()=>d}));
export const onSnapshot=(q,ok)=>{setTimeout(()=>ok({docs:docs(q.name)}),20);return()=>{}};
export const getDoc=async(r)=>{const d=(F.data&&F.data[r.name]||[]).find(x=>x.id===r.id);return{exists:()=>!!d,data:()=>d}};
export const setDoc=async(r,v)=>{F.writes.push({col:r.name,id:r.id,v})};
export const updateDoc=async()=>{};export const deleteDoc=async()=>{};export const addDoc=async()=>{};export const getDocs=async()=>({docs:[]});
"""

failures = []
def check(cond, label):
    print(('PASS ' if cond else 'FAIL ') + label)
    if not cond:
        failures.append(label)

async def new_page(browser, ua=None, fake=None, init=''):
    ctx = await browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=ua or None)
    page = await ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    await page.add_init_script(f'window.__FAKE={fake or "{}"};' + init)

    async def route(r):
        u = r.request.url
        if u.startswith(BASE):
            await r.continue_(); return
        if 'gstatic.com/firebasejs' in u:
            body = FAKE_APP if 'firebase-app' in u else FAKE_AUTH if 'firebase-auth' in u else FAKE_FS if 'firestore' in u else ''
            await r.fulfill(status=200, content_type='application/javascript', body=body); return
        await r.abort()
    await page.route('**/*', route)
    return page, errors

async def skip_intro(page):
    if await page.locator('#entrySkip').count():
        try:
            await page.click('#entrySkip', timeout=3000)
        except Exception:
            pass
    await page.wait_for_timeout(600)

async def test_app_registration(browser):
    page, errors = await new_page(browser, APP_UA)
    await page.goto(BASE + '/index.html')
    await page.wait_for_timeout(800)
    check(await page.locator('#evroGate:visible').count() == 0, 'gate waits for the welcome video')
    await skip_intro(page)
    check(await page.locator('#gPhoneStep:visible').count() == 1, 'app shows phone step')
    check(await page.evaluate('window.__FAKE.captchaRendered') >= 1, 'robot check shown on phone step')
    await page.fill('#gPhone', '12345')
    await page.click('#gSend')
    check('9' in await page.inner_text('#gErr1'), 'short number rejected')
    await page.fill('#gPhone', '90 000 0001')
    check(await page.input_value('#gPhone') == '900000001', 'phone field keeps digits only')
    await page.click('#gSend')
    await page.wait_for_selector('#gCodeStep:visible')
    check(await page.evaluate('window.__FAKE.sentTo') == '+992900000001', 'code sent to +992 number')
    await page.fill('#gCode', '111111')
    await page.wait_for_timeout(300)
    check(len(await page.inner_text('#gErr2')) > 0, 'wrong code rejected')
    await page.fill('#gCode', '123456')
    await page.wait_for_selector('#gProfileStep:visible')
    await page.click('#gFinish')
    check(await page.locator('#gProfileStep:visible').count() == 1
          and await page.evaluate("!document.getElementById('gName').checkValidity()"), 'profile requires a name')
    await page.fill('#gName', 'Алӣ Валиев')
    await page.select_option('#gCity', 'Ҳисор')
    await page.click('#gFinish')
    await page.wait_for_selector('#gDoneStep:visible')
    code = await page.inner_text('#gMyCode')
    check(bool(__import__('re').fullmatch(r'EVRO-[A-Z2-9]{6}', code)), f'purchase code issued ({code})')
    writes = await page.evaluate('window.__FAKE.writes.filter(w=>w.col==="customers")')
    check(len(writes) == 1 and writes[0]['v']['phone'] == '+992900000001' and writes[0]['v']['code'] == code, 'profile saved to customers')
    await page.click('#gToShop')
    await page.wait_for_timeout(300)
    check(await page.locator('#evroGate:visible').count() == 0, 'gate closes')
    check(code in await page.inner_text('#evroCodeChip'), 'code chip shown')
    check(await page.input_value('#customerName') == 'Алӣ Валиев', 'checkout name prefilled')
    check(await page.input_value('#customerPhone') == '+992900000001', 'checkout phone prefilled')
    check(not errors, 'no page errors in app: ' + '; '.join(errors[:3]))
    await page.context.close()

async def test_captcha_required(browser):
    page, errors = await new_page(browser, APP_UA, '{captchaUnticked:true}')
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.fill('#gPhone', '900000001')
    await page.click('#gSend')
    await page.wait_for_timeout(200)
    check('робот' in (await page.inner_text('#gErr1')).lower() and not await page.evaluate('window.__FAKE.sentTo'),
          'code is not sent until the robot check is ticked')
    await page.context.close()

async def test_returning_customer(browser):
    fake = ('{user:{uid:"uidTEST1234567890",phoneNumber:"+992900000001",providerData:[{providerId:"phone"}]},'
            'data:{customers:[{id:"uidTEST1234567890",name:"Алӣ",phone:"+992900000001",code:"EVRO-ABCDEF"}],'
            'products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"}]}}')
    cart = "try{localStorage.setItem('evrostar_cart',JSON.stringify([{id:'p1',name:'Панели офтобӣ 630W',price:950,qty:1}]))}catch(e){}"
    page, errors = await new_page(browser, APP_UA, fake, cart)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.wait_for_timeout(400)
    check(await page.locator('#evroGate:visible').count() == 0, 'registered customer is not asked again')
    check('EVRO-ABCDEF' in await page.inner_text('#evroCodeChip'), 'saved code shown to returning customer')
    # Checkout: the WhatsApp order text carries the purchase code and the verified phone.
    wa = []
    page.on('request', lambda r: wa.append(r.url) if 'wa.me' in r.url else None)
    await page.evaluate("location.hash='#cart'")
    await page.wait_for_selector('#customerAddress:visible')
    await page.fill('#customerAddress', 'Ҳисор, кӯчаи 1')
    await page.evaluate("document.getElementById('order').click()")
    await page.wait_for_timeout(5000)
    text = urllib.parse.unquote(wa[-1]) if wa else ''
    check('EVRO-ABCDEF' in text and '+992900000001' in text, 'WhatsApp order includes purchase code')
    await page.context.close()

async def test_website_has_no_gate(browser):
    page, errors = await new_page(browser)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.wait_for_timeout(500)
    check(await page.locator('#evroGate').count() == 0, 'public website does not ask to register')
    bg = await page.evaluate('getComputedStyle(document.body).backgroundImage')
    check('gradient' in bg, 'new background applied')
    check(not errors, 'no page errors on website: ' + '; '.join(errors[:3]))
    await page.context.close()

async def test_admin(browser):
    fake = ('{data:{customers:[{id:"u1",name:"Алӣ",phone:"+992900000001",city:"Ҳисор",code:"EVRO-ABCDEF"},'
            '{id:"u2",name:"Бобо",phone:"+992900000002",city:"Душанбе",code:"EVRO-ZZZZZZ"}]}}')
    page, errors = await new_page(browser, None, fake)
    await page.goto(BASE + '/admin.html')
    await page.fill('#email', 'admin@example.com')
    await page.fill('#password', 'x')
    await page.click('#loginBtn')
    await page.wait_for_selector('#customersBox:visible')
    await page.wait_for_timeout(200)
    txt = await page.inner_text('#customerList')
    check('EVRO-ABCDEF' in txt and 'EVRO-ZZZZZZ' in txt, 'admin sees registered customers')
    await page.fill('#customerSearch', 'zzzz')
    txt = await page.inner_text('#customerList')
    check('EVRO-ZZZZZZ' in txt and 'EVRO-ABCDEF' not in txt, 'admin search by code')
    check(not errors, 'no page errors in admin: ' + '; '.join(errors[:3]))
    await page.context.close()

    fake2 = '{user:{uid:"c1",phoneNumber:"+992900000001",email:null,providerData:[{providerId:"phone"}]}}'
    page, errors = await new_page(browser, None, fake2)
    await page.goto(BASE + '/admin.html')
    await page.wait_for_timeout(500)
    check(await page.locator('#adminBox:visible').count() == 0 and await page.locator('#customersBox:visible').count() == 0,
          'phone-registered customer cannot open admin')
    await page.context.close()

async def main():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for t in (test_app_registration, test_captcha_required, test_returning_customer, test_website_has_no_gate, test_admin):
            try:
                await t(browser)
            except Exception as e:
                check(False, f'{t.__name__} crashed: {e}')
        await browser.close()
    srv.shutdown()
    print(f'\n{len(failures)} failed' if failures else '\nall passed')
    sys.exit(1 if failures else 0)

asyncio.run(main())
