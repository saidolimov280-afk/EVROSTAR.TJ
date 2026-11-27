"""EVROSTAR end-to-end tests (headless Chromium, Firebase replaced by in-page fakes).

Run:  pip install playwright && python -m playwright install chromium
      python tests/e2e/test_app.py
Covers: app registration by SMS (phone -> code -> profile -> purchase code),
website without registration, checkout prefill + code in WhatsApp text,
admin panel customers list, and that a phone-registered customer cannot open admin.
Registration is switched off by default (window.EVRO_REGISTRATION in index.html):
the registration tests switch it on, test_app_without_registration checks the default.
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
export class RecaptchaVerifier{constructor(a,id,o){this.o=o||{};F.captchaSizes=(F.captchaSizes||[]).concat(this.o.size)}render(){setTimeout(()=>{F.captchaRendered=(F.captchaRendered||0)+1;if(!F.captchaUnticked)this.o.callback&&this.o.callback()},5);return Promise.resolve(1)}clear(){}}
export const onAuthStateChanged=(a,f)=>{subs.push(f);setTimeout(()=>f(auth.currentUser),10);return()=>{}};
const emit=()=>subs.forEach(f=>f(auth.currentUser));
export const signInWithPhoneNumber=async(a,phone,v)=>{if(F.failInvisible&&v.o.size==='invisible'){const e=new Error('captcha');e.code='auth/captcha-check-failed';throw e}F.sentTo=phone;return{confirm:async c=>{
  if(c!=='123456'){const e=new Error('bad');e.code='auth/invalid-verification-code';throw e}
  auth.currentUser={uid:'uidTEST1234567890',phoneNumber:phone,email:null,providerData:[{providerId:'phone'}]};emit()}}};
export const signInWithEmailAndPassword=async()=>{auth.currentUser={uid:'admin',email:'admin@example.com',providerData:[{providerId:'password'}]};emit()};
export const signOut=async()=>{auth.currentUser=null;emit()};
export const deleteUser=async()=>{F.deletedUser=true;auth.currentUser=null;emit()};
"""
FAKE_FS = r"""
const F=window.__FAKE||(window.__FAKE={});F.writes=F.writes||[];
export const getFirestore=()=>({});export const initializeFirestore=()=>({});
export const persistentLocalCache=()=>0;export const persistentMultipleTabManager=()=>0;
export const collection=(db,name)=>({name});export const doc=(a,b,c)=>(a&&a.name&&b===undefined)?{name:a.name,id:'auto'+Math.random().toString(36).slice(2,8)}:{name:b&&b.name?b.name:b,id:c||'auto'+Math.random().toString(36).slice(2,8)};
export const query=(c,...cs)=>({name:c.name,w:cs.filter(x=>x&&x.field)});export const where=(field,op,val)=>({field,val});export const limit=()=>0;export const orderBy=()=>0;export const serverTimestamp=()=>null;
const docs=n=>(F.data&&F.data[n]||[]).map((d,i)=>({id:d.id||String(i),data:()=>d}));
export const onSnapshot=(q,ok)=>{setTimeout(()=>ok({docs:docs(q.name)}),20);return()=>{}};
export const getDoc=async(r)=>{const d=(F.data&&F.data[r.name]||[]).find(x=>x.id===r.id);return{exists:()=>!!d,data:()=>d}};
export const setDoc=async(r,v)=>{F.writes.push({col:r.name,id:r.id,v})};
export const updateDoc=async()=>{};export const deleteDoc=async(r)=>{F.deletes=(F.deletes||[]).concat(r.name+'/'+r.id)};export const addDoc=async()=>{};export const getDocs=async(q)=>({docs:docs(q.name).filter(d=>(q.w||[]).every(w=>d.data()[w.field]===w.val))});
export const increment=n=>({__increment:n});
"""

failures = []
def check(cond, label):
    print(('PASS ' if cond else 'FAIL ') + label)
    if not cond:
        failures.append(label)

async def new_page(browser, ua=None, fake=None, init='', reg=False, **ctx_args):
    ctx = await browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=ua or None, **ctx_args)
    page = await ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    await page.add_init_script(f'window.__FAKE={fake or "{}"};' + ('window.EVRO_REGISTRATION=true;' if reg else '') + init)

    async def route(r):
        u = r.request.url
        if u.startswith(BASE):
            await r.continue_(); return
        if 'gstatic.com/firebasejs' in u:
            body = FAKE_APP if 'firebase-app' in u else FAKE_AUTH if 'firebase-auth' in u else FAKE_FS if 'firestore' in u else ''
            await r.fulfill(status=200, content_type='application/javascript', body=body); return
        if 'wa.me' in u:
            await r.fulfill(status=204, body=''); return  # stay on the page so its state can be checked
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
    page, errors = await new_page(browser, APP_UA, reg=True)
    await page.goto(BASE + '/index.html')
    await page.wait_for_timeout(800)
    check(await page.locator('#evroGate:visible').count() == 0, 'gate waits for the welcome video')
    await skip_intro(page)
    check(await page.locator('#gPhoneStep:visible').count() == 1, 'app shows phone step')
    check(await page.evaluate('window.__FAKE.captchaSizes[0]') == 'invisible' and await page.locator('#gRecaptcha.gCaptchaOn').count() == 0,
          'no "I am not a robot" checkbox by default (invisible check)')
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
    page, errors = await new_page(browser, APP_UA, '{failInvisible:true,captchaUnticked:true}', reg=True)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.fill('#gPhone', '900000001')
    await page.click('#gSend')
    await page.wait_for_timeout(300)
    check(await page.locator('#gRecaptcha.gCaptchaOn').count() == 1 and 'робот' in (await page.inner_text('#gErr1')).lower(),
          'if the invisible check fails, the checkbox appears')
    await page.click('#gSend')
    await page.wait_for_timeout(200)
    check(not await page.evaluate('window.__FAKE.sentTo'), 'code is not sent until the checkbox is ticked')
    await page.context.close()

async def test_account_page(browser):
    fake = ('{user:{uid:"uidTEST1234567890",phoneNumber:"+992900000001",providerData:[{providerId:"phone"}]},'
            'data:{customers:[{id:"uidTEST1234567890",name:"Алӣ",phone:"+992900000001",city:"Ҳисор",code:"EVRO-ABCDEF"}],'
            'orders:[{id:"ord1",no:"AB12CD",uid:"uidTEST1234567890",status:"done",total:5000,items:[{name:"Инвертор 5кВт",qty:1}],createdAt:{seconds:1767225600},statusAt:{seconds:1767225600}},'
            '{id:"ord2",no:"ZZ99ZZ",uid:"someoneElse",status:"new",total:1,items:[{name:"Бегона",qty:1}]}]}}')
    page, errors = await new_page(browser, APP_UA, fake, reg=True)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.click('#g3AccountLink')  # home card replaces the floating chip on the home screen
    await page.wait_for_selector('#account:visible')
    await page.wait_for_selector('.accOrder')
    txt = await page.inner_text('#account')
    check('EVRO-ABCDEF' in txt and 'Алӣ' in txt, 'account shows profile and code')
    check('AB12CD' in txt and 'Расонида шуд' in txt, 'account lists own order with status')
    check('ZZ99ZZ' not in txt, 'account hides other customers orders')
    check('Кафолат то 01.01.2027' in txt, 'warranty end date shown for delivered order')
    await page.wait_for_timeout(900)
    check(await page.locator('#evroCodeChip:visible').count() == 0, 'code chip hidden on account page')
    await page.screenshot(path='/tmp/claude-0/-home-claude-evrostar-tj/b52afe6b-1fc9-5b08-9122-35f54a10a685/scratchpad/account.png') if os.environ.get('EVRO_SHOTS') else None
    check(await page.locator('#account a[href="/privacy.html"]').count() == 1, 'privacy link on account page')
    await page.click('#accDeleteBtn')
    check(not await page.evaluate('!!window.__FAKE.deletedUser'), 'first tap only asks to confirm deletion')
    await page.click('#accDeleteBtn')
    await page.wait_for_timeout(300)
    check(await page.evaluate('!!window.__FAKE.deletedUser') and 'customers/uidTEST1234567890' in await page.evaluate('window.__FAKE.deletes||[]'),
          'second tap deletes profile and account')
    await page.context.close()
    page, errors = await new_page(browser, APP_UA, fake, reg=True)
    await page.goto(BASE + '/index.html#account')
    await skip_intro(page)
    await page.wait_for_selector('#accLogoutBtn')
    await page.click('#accLogoutBtn')
    await page.wait_for_timeout(300)
    check(await page.locator('#evroCodeChip').count() == 0 and 'Ворид шудан' in await page.inner_text('#account'), 'logout clears the account')
    check(not errors, 'no page errors on account: ' + '; '.join(errors[:3]))
    await page.context.close()

async def test_returning_customer(browser):
    fake = ('{user:{uid:"uidTEST1234567890",phoneNumber:"+992900000001",providerData:[{providerId:"phone"}]},'
            'data:{customers:[{id:"uidTEST1234567890",name:"Алӣ",phone:"+992900000001",code:"EVRO-ABCDEF"}],'
            'products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"}],'
            'orders:[{id:"ord1",no:"AB12CD",uid:"uidTEST1234567890",status:"done",total:5000,items:[{name:"Инвертор 5кВт",qty:1}],createdAt:{seconds:1767225600},statusAt:{seconds:1767225600}},'
            '{id:"ord2",no:"ZZ99ZZ",uid:"someoneElse",status:"new",total:1,items:[{name:"Бегона",qty:1}]}]}}')
    cart = "try{localStorage.setItem('evrostar_cart',JSON.stringify([{id:'p1',name:'Панели офтобӣ 630W',price:950,qty:1}]))}catch(e){}"
    page, errors = await new_page(browser, APP_UA, fake, cart, reg=True)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.wait_for_timeout(400)
    check(await page.locator('#evroGate:visible').count() == 0, 'registered customer is not asked again')
    check('EVRO-ABCDEF' in await page.inner_text('#evroCodeChip'), 'saved code shown to returning customer')
    check((await page.inner_text('#g3Code')) == 'EVRO-ABCDEF' and await page.locator('#g3Guest').is_hidden(), 'home card shows purchase code')
    check(await page.locator('.g3Cat.promo-open').count() == 9, 'home shows 9 category buttons')
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
    ow = await page.evaluate('window.__FAKE.writes.filter(w=>w.col==="orders").map(w=>w.v)')
    check(bool(ow) and ow[-1].get('uid') == 'uidTEST1234567890' and ow[-1].get('customerCode') == 'EVRO-ABCDEF', 'order saved with customer uid and code')
    await page.context.close()

async def test_privacy_page(browser):
    page, errors = await new_page(browser)
    r = await page.goto(BASE + '/privacy.html')
    txt = await page.inner_text('body')
    check(r.ok and 'Сиёсати махфият' in txt and 'Политика конфиденциальности' in txt and 'Нест кардани аккаунт' in txt,
          'privacy policy page (tg + ru, account deletion section)')
    check(not errors, 'no page errors on privacy page')
    await page.context.close()
    page, errors = await new_page(browser, APP_UA, reg=True)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    check(await page.locator('#evroGate .gConsent a[href^="/privacy.html"]').count() == 1, 'registration shows privacy consent link')
    await page.context.close()

async def test_app_without_registration(browser):
    # Default setting: registration is off, the app opens straight to the shop.
    fake = '{data:{products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"}]}}'
    cart = "try{localStorage.setItem('evrostar_cart',JSON.stringify([{id:'p1',name:'Панели офтобӣ 630W',price:950,qty:1}]))}catch(e){}"
    page, errors = await new_page(browser, APP_UA, fake, cart)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.wait_for_timeout(600)
    check(await page.locator('#evroGate').count() == 0, 'app does not ask to register when registration is off')
    check(await page.locator('#evroCodeChip').count() == 0, 'no purchase code chip when registration is off')
    card = await page.inner_text('#g3Card')
    check('Ҳама чиз барои барқи офтобӣ' in card and 'ворид' not in card.lower(), 'home card has no sign-in text')
    check(await page.get_attribute('#g3GetApp', 'href') == '#catalog' and 'каталог' in (await page.inner_text('#g3GetApp')).lower(),
          'home card button opens the catalog')
    await page.evaluate("location.hash='#account'")
    await page.wait_for_selector('#account:visible')
    check('Ворид шудан' not in await page.inner_text('#account') and (await page.inner_text('#accountTitle')).strip() == 'Профил',
          'profile page has no login')
    wa = []
    page.on('request', lambda r: wa.append(r.url) if 'wa.me' in r.url else None)
    await page.evaluate("location.hash='#cart'")
    await page.wait_for_selector('#customerAddress:visible')
    await page.fill('#customerName', 'Алӣ')
    await page.fill('#customerPhone', '+992 900 000 001')
    await page.fill('#customerAddress', 'Ҳисор, кӯчаи 1')
    await page.evaluate("document.getElementById('order').click()")
    await page.wait_for_timeout(5000)
    text = urllib.parse.unquote(wa[-1]) if wa else ''
    check(bool(text) and 'EVRO-' not in text and 'Коди харидор' not in text and 'Алӣ' in text, 'WhatsApp order works and has no purchase code')
    check(not errors, 'no page errors in app without registration: ' + '; '.join(errors[:3]))
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

async def test_empty_categories_and_stock_warning(browser):
    # Shop: a category without products is hidden, so customers never open an empty list.
    fake = ('{data:{products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"},'
            '{id:"p2",name:"Аккумулятор 12V",price:300,category:"battery"}]}}')
    page, errors = await new_page(browser, None, fake)
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.wait_for_timeout(400)
    hidden = lambda sel: page.locator(sel + '.catEmpty').count()
    check(await hidden('.categoryChip[data-category="stabilizer"]') == 1 and await hidden('.g3Cat[data-category="stabilizer"]') == 1,
          'empty category (stabilizers) is hidden')
    check(await hidden('.categoryChip[data-category="battery"]') == 0 and await hidden('.categoryChip[data-category="panels"]') == 0,
          'categories with products stay visible')
    check(await hidden('.categoryChip[data-category="all"]') == 0, '"all" chip is never hidden')
    check(not errors, 'no page errors with hidden categories: ' + '; '.join(errors[:3]))
    await page.context.close()
    # Admin: products without a stock status are flagged.
    page, errors = await new_page(browser, None, fake)
    await page.goto(BASE + '/admin.html')
    await page.fill('#email', 'admin@example.com')
    await page.fill('#password', 'x')
    await page.click('#loginBtn')
    await page.wait_for_selector('#listBox:visible')
    await page.wait_for_timeout(200)
    txt = await page.inner_text('#productList')
    check('Наличие не указано у 1' in txt, 'admin flags products without stock status')
    check(not errors, 'no page errors in admin product list: ' + '; '.join(errors[:3]))
    await page.context.close()

def make_xlsx(rows):
    """A minimal real .xlsx (zip + XML, deflate) with shared strings, like Excel writes."""
    import io, zipfile
    from xml.sax.saxutils import escape
    strings = []
    def cell(ref, v):
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"><v>{v}</v></c>'
        strings.append(v)
        return f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>'
    sheet_rows = ''.join(f'<row r="{i + 1}">' + ''.join(cell(chr(65 + j) + str(i + 1), v) for j, v in enumerate(r)) + '</row>'
                         for i, r in enumerate(rows))
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    files = {
        '[Content_Types].xml': '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        'xl/workbook.xml': f'<?xml version="1.0"?><workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="Товары" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': f'<?xml version="1.0"?><worksheet xmlns="{ns}"><sheetData>{sheet_rows}</sheetData></worksheet>',
        'xl/sharedStrings.xml': f'<?xml version="1.0"?><sst xmlns="{ns}">' + ''.join(f'<si><t>{escape(s)}</t></si>' for s in strings) + '</sst>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()

async def test_admin_import(browser):
    fake = '{data:{products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"}]}}'
    page, errors = await new_page(browser, None, fake)
    await page.goto(BASE + '/admin.html')
    await page.fill('#email', 'admin@example.com')
    await page.fill('#password', 'x')
    await page.click('#loginBtn')
    await page.wait_for_selector('#importBox:visible')
    await page.wait_for_timeout(200)
    # Rows pasted from Excel (tab-separated): one new, one existing (price/stock update), one broken.
    await page.fill('#importText', 'Название\tЦена\tКатегория\tНаличие\n'
                                   'Стабилизатор 10 кВт\t1 200\tСтабилизаторы\tесть\n'
                                   'панели офтобӣ 630W\t990\t\tнет\n'
                                   '\tабв\t\t\n')
    await page.click('#importCheck')
    txt = await page.inner_text('#importPreview')
    check('Новых: 1' in txt and 'обновится: 1' in txt and 'с ошибкой: 1' in txt, 'import preview: 1 new, 1 update, 1 error')
    await page.click('#importSave')
    await page.wait_for_timeout(300)
    new = await page.evaluate('window.__FAKE.writes.filter(w=>w.col==="products").map(w=>w.v)')
    check(len(new) == 1 and new[0]['name'] == 'Стабилизатор 10 кВт' and new[0]['price'] == 1200
          and new[0]['category'] == 'stabilizer' and new[0]['availability'] == 'in_stock', 'import saves the new product with parsed fields')
    check('Добавлено: 1, обновлено: 1' in await page.inner_text('#importStatus'), 'import reports added and updated')
    # A real .xlsx file.
    data = make_xlsx([['Название', 'Цена', 'Категория', 'Количество'],
                      ['Камера AOV 4G', 550, 'Камеры', 3], ['Телевизор 43"', 2500, 'ТВ / Электроника', 0]])
    await page.set_input_files('#importFile', files=[{'name': 'tovary.xlsx', 'mimeType': 'application/octet-stream', 'buffer': data}])
    await page.wait_for_timeout(500)
    txt = await page.inner_text('#importPreview')
    check('Новых: 2' in txt and 'Камера AOV 4G' in txt and 'TV / Электроника\tнет' in txt and 'Камеры\tесть' in txt,
          'import reads .xlsx (categories and stock from quantity)')
    check(not errors, 'no page errors in admin import: ' + '; '.join(errors[:3]))
    await page.context.close()

async def test_share_links(browser):
    fake = ('{data:{products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"},'
            '{id:"p2",name:"Аккумулятор 12V",price:300,category:"battery"}]}}')
    page, errors = await new_page(browser, None, fake)
    # Only p1 has a share page (made by scripts/build_share.py); p2 was added today.
    await page.route('**/p/pages.json', lambda r: r.fulfill(status=200, content_type='application/json', body='{"ids":["p1"],"images":{}}'))
    await page.goto(BASE + '/index.html#catalog')
    await skip_intro(page)
    await page.wait_for_timeout(500)
    await page.evaluate("location.hash='#catalog'")
    await page.wait_for_selector('#products button.details.productName[data-id="p1"]')
    await page.click('#products button.details.productName[data-id="p1"]')
    await page.wait_for_selector('#detailBody .productShare a')
    wa = await page.get_attribute('#detailBody .productShare a[href*="wa.me"]', 'href') or ''
    check('%2Fp%2Fp1.html' in wa, 'WhatsApp share uses the product page with photo and price')
    await page.evaluate("document.getElementById('detail').close()")
    await page.click('#products button.details.productName[data-id="p2"]')
    await page.wait_for_timeout(200)
    wa2 = await page.get_attribute('#detailBody .productShare a[href*="wa.me"]', 'href') or ''
    check('product%3Dp2' in wa2 and '%2Fp%2Fp2.html' not in wa2, 'product without a page yet shares the normal link')
    check(not errors, 'no page errors with share links: ' + '; '.join(errors[:3]))
    await page.context.close()
    # GitHub Pages answers a missing /p/<id>.html with 404.html, which opens the product in the shop.
    page, errors = await new_page(browser, None, fake)
    body = open(os.path.join(ROOT, '404.html'), encoding='utf-8').read()
    await page.route('**/p/zz9.html', lambda r: r.fulfill(status=404, content_type='text/html', body=body))
    await page.goto(BASE + '/p/zz9.html')
    await page.wait_for_url('**/?product=zz9', timeout=5000)
    check(page.url.endswith('/?product=zz9'), 'missing share page opens the product in the shop')
    await page.context.close()

async def test_visit_stats(browser):
    fake = '{data:{products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"}]}}'
    # Service workers off: after a reload the page's fake Firebase must still be used.
    page, errors = await new_page(browser, APP_UA, fake, service_workers='block')
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.wait_for_timeout(500)
    stats = lambda: page.evaluate('(window.__FAKE.writes||[]).filter(w=>w.col==="stats").map(w=>Object.keys(w.v)[0])')
    s = await stats()
    check(s.count('visits') == 1 and s.count('app') == 1, 'visit from the app counted once')
    check(s.count('appNew') == 1, 'first open of the installed app counted (new install)')
    await page.evaluate("location.hash='#catalog'")
    for _ in range(2):
        await page.click('#products button.details.productName[data-id="p1"]')
        await page.wait_for_timeout(200)
        await page.evaluate("document.getElementById('detail').close()")
    check((await stats()).count('views') == 1, 'product view counted once per visit')
    await page.evaluate("document.querySelector('a[href*=\"wa.me/992405555530\"]').click()")
    await page.wait_for_timeout(300)
    check((await stats()).count('wa') == 1, 'tap on the shop WhatsApp counted')
    day = await page.evaluate('window.__FAKE.writes.find(w=>w.col==="stats").id') or ''
    check(len(day) == 10 and day[4] == '-' and day[7] == '-', 'counters are kept per day')
    await page.reload()
    await skip_intro(page)
    await page.wait_for_selector('#products button.details.productName[data-id="p1"]', state='attached')  # database loaded
    await page.wait_for_timeout(300)
    check(await page.evaluate('Array.isArray(window.__FAKE.writes)') and (await stats()).count('visits') == 0,
          'second visit the same day is not counted again')
    check((await stats()).count('appNew') == 0, 'the same phone is not counted as a new install again')
    check(not errors, 'no page errors with visit counters: ' + '; '.join(errors[:3]))
    await page.context.close()

TG_SDK = ("window.__TG={calls:[],back:false};window.Telegram={WebApp:{"
          "ready(){__TG.calls.push('ready')},expand(){__TG.calls.push('expand')},disableVerticalSwipes(){},"
          "setHeaderColor(c){__TG.calls.push('header:'+c)},setBackgroundColor(){},setBottomBarColor(){},"
          "openLink(u){__TG.calls.push('link:'+u)},openTelegramLink(u){__TG.calls.push('tglink:'+u)},"
          "BackButton:{show(){__TG.back=true},hide(){__TG.back=false},onClick(f){__TG.onBack=f}}}};")
TG_UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0 Mobile Safari/537.36'

async def test_telegram_mini_app(browser):
    fake = '{data:{products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"}]}}'
    cart = "try{localStorage.setItem('evrostar_cart',JSON.stringify([{id:'p1',name:'Панели офтобӣ 630W',price:950,qty:1}]))}catch(e){}"
    page, errors = await new_page(browser, TG_UA, fake, cart, service_workers='block')
    await page.route('https://telegram.org/js/telegram-web-app.js',
                     lambda r: r.fulfill(status=200, content_type='application/javascript', body=TG_SDK))
    navigations = []
    page.on('request', lambda r: navigations.append(r.url) if 'wa.me' in r.url else None)
    await page.goto(BASE + '/index.html?tg=1#tgWebAppData=query_id%3DAAA%26auth_date%3D1&tgWebAppVersion=8.0'
                    '&tgWebAppPlatform=android&tgWebAppThemeParams=%7B%22bg_color%22%3A%22%23000000%22%7D')
    await skip_intro(page)
    await page.wait_for_timeout(600)
    params = await page.evaluate("JSON.parse(sessionStorage.getItem('__telegram__initParams')||'{}')")
    check('tgWebApp' not in page.url and params.get('tgWebAppPlatform') == 'android'
          and params.get('tgWebAppData', '').startswith('query_id=AAA'), 'Telegram launch data kept for its script, address cleared')
    calls = await page.evaluate('window.__TG.calls')
    check('ready' in calls and 'expand' in calls and 'header:#06110d' in calls, 'mini app is opened full height in shop colours')
    check('EVROSTAR.apk' in (await page.get_attribute('#g3GetApp', 'href') or ''), 'Telegram on Android: home card button downloads the app')
    await page.evaluate("document.getElementById('g3GetApp').click()")
    await page.evaluate("document.querySelector('.installStrip [data-install]').click()")
    await page.wait_for_timeout(300)
    apk = [c for c in await page.evaluate('window.__TG.calls') if c.startswith('link:') and c.endswith('EVROSTAR.apk')]
    check(len(apk) == 2 and await page.locator('.installStrip').is_visible(), 'app download opens outside Telegram (home card and install strip)')
    check(await page.evaluate("(()=>{const l=[...document.querySelectorAll('.tgBotLink')];return l.length>0&&l.every(e=>getComputedStyle(e).display==='none')})()"),
          'link to the bot is hidden inside the bot')
    await page.evaluate("location.hash='#catalog'")
    await page.wait_for_timeout(200)
    on_catalog = await page.evaluate('window.__TG.back')
    await page.evaluate('window.__TG.onBack()')
    await page.wait_for_timeout(300)
    check(on_catalog and not await page.evaluate('window.__TG.back'), "Telegram's back button goes back to the home page")
    await page.evaluate("document.querySelector('a[href*=\"wa.me/992405555530\"]').click()")
    await page.wait_for_timeout(300)
    calls = await page.evaluate('window.__TG.calls')
    check(any(c.startswith('link:https://wa.me/992405555530') for c in calls) and not navigations,
          'WhatsApp link opens outside Telegram')
    await page.evaluate("location.hash='#cart'")
    await page.wait_for_selector('#customerAddress:visible')
    await page.fill('#customerName', 'Алӣ')
    await page.fill('#customerPhone', '+992 900 000 001')
    await page.fill('#customerAddress', 'Ҳисор, кӯчаи 1')
    await page.evaluate("document.getElementById('order').click()")
    await page.wait_for_timeout(1500)
    calls = await page.evaluate('window.__TG.calls')
    order = [urllib.parse.unquote(c) for c in calls if c.startswith('link:https://wa.me/992405555530?text=')]
    check(bool(order) and 'Алӣ' in order[-1] and not navigations, 'order from Telegram opens WhatsApp with the order text')
    check(not errors, 'no page errors in Telegram: ' + '; '.join(errors[:3]))
    await page.context.close()
    # A normal browser is not affected: no Telegram script, links work as before.
    page, errors = await new_page(browser, None, fake)
    asked = []
    page.on('request', lambda r: asked.append(r.url) if 'telegram.org' in r.url else None)
    await page.goto(BASE + '/index.html')
    await page.wait_for_timeout(600)
    check(not asked and await page.evaluate('window.evroInTelegram === false'), 'website outside Telegram does not load Telegram code')
    check(await page.locator('a[href="https://t.me/evrostar_tj_bot"]').count() >= 2, 'website links to the Telegram bot (shop card in Profile and contacts)')
    await page.context.close()
    # Telegram on iPhone: nothing to install, the home card opens the catalog.
    ios = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
    page, errors = await new_page(browser, ios, fake, service_workers='block')
    await page.route('https://telegram.org/js/telegram-web-app.js',
                     lambda r: r.fulfill(status=200, content_type='application/javascript', body=TG_SDK))
    await page.goto(BASE + '/index.html?tg=1#tgWebAppPlatform=ios&tgWebAppVersion=8.0')
    await skip_intro(page)
    await page.wait_for_timeout(500)
    check(await page.get_attribute('#g3GetApp', 'href') == '#catalog' and not await page.locator('.installStrip').is_visible(),
          'Telegram on iPhone: no app offer, home card opens the catalog')
    await page.context.close()

IOS_SAFARI = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
              'Version/17.0 Mobile/15E148 Safari/604.1')

async def test_iphone(browser):
    fake = '{data:{products:[{id:"p1",name:"Панели офтобӣ 630W",price:950,availability:"in_stock",category:"solar"}]}}'
    # Safari on iPhone: «Насб кардан» explains how to put the EVROSTAR icon on the home screen.
    page, errors = await new_page(browser, IOS_SAFARI, fake, service_workers='block')
    await page.goto(BASE + '/index.html')
    await skip_intro(page)
    await page.wait_for_timeout(500)
    check(await page.locator('link[rel="apple-touch-icon"][href="/apple-touch-icon.png"]').count() == 1
          and await page.locator('meta[name="apple-mobile-web-app-capable"]').count() == 1, 'iPhone home-screen icon and app mode')
    await page.click('#g3GetApp')
    await page.wait_for_selector('#installHelp[open]')
    help_text = await page.inner_text('#installInstructions')
    check('Safari' in help_text and 'Домой' in help_text and page.url.endswith('/index.html'), 'iPhone: install button shows the home-screen steps')
    stats = await page.evaluate('(window.__FAKE.writes||[]).filter(w=>w.col==="stats").map(w=>Object.keys(w.v)[0])')
    check(stats.count('install') == 1, 'tap on install is counted')
    check(not errors, 'no page errors on iPhone: ' + '; '.join(errors[:3]))
    await page.context.close()
    # Telegram on iPhone (Bot API 8.0+): the strip offers «add to home screen» through Telegram.
    sdk = TG_SDK.replace("BackButton:", "isVersionAtLeast(v){return true},addToHomeScreen(){__TG.calls.push('homescreen')},"
                                         "checkHomeScreenStatus(f){f('missed')},onEvent(){},BackButton:")
    page, errors = await new_page(browser, IOS_SAFARI, fake, service_workers='block')
    await page.route('https://telegram.org/js/telegram-web-app.js',
                     lambda r: r.fulfill(status=200, content_type='application/javascript', body=sdk))
    await page.goto(BASE + '/index.html?tg=1#tgWebAppPlatform=ios&tgWebAppVersion=8.0')
    await skip_intro(page)
    await page.wait_for_timeout(600)
    btn = page.locator('.installStrip [data-home-screen]')
    check(await page.locator('.installStrip').is_visible() and (await btn.inner_text()).strip() == 'Ба экрани асосӣ илова кардан',
          'Telegram on iPhone: offer to add EVROSTAR to the home screen')
    await btn.click()
    await page.wait_for_timeout(200)
    check('homescreen' in await page.evaluate('window.__TG.calls') and not await page.locator('#installHelp[open]').count(),
          'Telegram adds the icon (no Safari steps inside Telegram)')
    check(not errors, 'no page errors in Telegram on iPhone: ' + '; '.join(errors[:3]))
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
        for t in (test_app_registration, test_captcha_required, test_account_page, test_returning_customer, test_privacy_page, test_app_without_registration, test_website_has_no_gate, test_admin, test_empty_categories_and_stock_warning, test_admin_import, test_share_links, test_visit_stats, test_telegram_mini_app, test_iphone):
            try:
                await t(browser)
            except Exception as e:
                check(False, f'{t.__name__} crashed: {e}')
        await browser.close()
    srv.shutdown()
    print(f'\n{len(failures)} failed' if failures else '\nall passed')
    sys.exit(1 if failures else 0)

asyncio.run(main())
