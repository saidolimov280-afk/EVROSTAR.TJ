#!/usr/bin/env python3
"""EVROSTAR Telegram bot. Runs in GitHub Actions (.github/workflows/telegram-bot.yml).

Modes:
  watch     every ~15 min: binds the owner's chat (/start), sends alerts for new orders,
            reviews and "notify me when in stock" requests, answers /hisobot.
  digest    daily summary: the Instagram/TikTok text sent by the Claude scheduled task
            (workflow_dispatch input "report") + today's EVROSTAR numbers from Firestore.
  fallback  late evening: if no summary was sent today, send the EVROSTAR part alone.
  test      send a test message with today's EVROSTAR numbers.
  reset     forget the bound chat; the next /start binds again.

Secrets: TELEGRAM_BOT_TOKEN, FIREBASE_SERVICE_ACCOUNT (file in GOOGLE_APPLICATION_CREDENTIALS).
State: Firestore doc botState/telegram. firestore.rules closes it to everyone; the service
account bypasses rules. The repository and its Actions logs are public, so this script never
prints order details, counts, chat ids or the report text.
"""
import datetime as dt
import html
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

import requests

PROJECT = 'evrostar-c7c85'
DOCS = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents'
STATE = 'botState/telegram'
TZ = ZoneInfo('Asia/Dushanbe')
ADMIN = 'https://evrostarshop.com/admin.html'
FALLBACK_CRON = '45 16 * * *'   # must match the second cron in telegram-bot.yml
OPEN_STATUSES = ['new', 'confirmed', 'paid', 'shipped']
MAX_ALERTS = 15                 # per collection per run; the rest are summed up in one line
TG_LIMIT = 3900                 # Telegram allows 4096 characters per message


def note(kind, msg):
    print(f'::{kind}::{str(msg)[:500]}')


# ---------- small text helpers

def esc(s):
    return html.escape(str(s or ''), quote=False)


def cut(s, n):
    s = ' '.join(str(s or '').split())
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


def fit(text, n):
    """Escape plain text for Telegram HTML and keep it under n characters without breaking entities."""
    text = str(text or '').strip()
    while len(esc(text)) > n:
        text = text[:max(0, int(len(text) * 0.9) - 1)].rstrip() + '…'
    return esc(text)


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def money(v):
    return f'{num(v):,.0f}'.replace(',', ' ') + ' сомонӣ'


def wa_digits(phone):
    d = re.sub(r'\D', '', str(phone or ''))
    return '992' + d if len(d) == 9 else d


def parse_ts(s):
    """RFC 3339 from Firestore (may carry nanoseconds) -> aware datetime."""
    m = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)$', str(s or ''))
    if not m:
        return None
    base, frac, zone = m.groups()
    t = dt.datetime.fromisoformat(base + ('.' + (frac + '000000')[:6] if frac else '') + ('+00:00' if zone == 'Z' else zone))
    return t


def local(ts):
    t = parse_ts(ts)
    return t.astimezone(TZ).strftime('%d.%m %H:%M') if t else ''


def utc_iso(t):
    return t.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def today_local():
    return dt.datetime.now(TZ)


# ---------- Firestore (REST)

def load_key():
    """Copying the key on a phone sometimes drops the closing brace; repair that like firebase_setup.py does."""
    kp = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
    raw = open(kp, encoding='utf-8-sig').read().strip()
    try:
        json.loads(raw)
        return
    except json.JSONDecodeError:
        pass
    for tail in ('}', '"}', '\n}', '"\n}'):
        try:
            cand = json.loads(raw + tail)
        except json.JSONDecodeError:
            continue
        if cand.get('type') == 'service_account' and cand.get('private_key'):
            with open(kp, 'w', encoding='utf-8') as f:
                f.write(raw + tail)
            return
    raise SystemExit('::error::FIREBASE_SERVICE_ACCOUNT is not valid JSON.')


def firestore_session():
    load_key()
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/datastore'])
    return AuthorizedSession(creds)


def dec(v):
    if not isinstance(v, dict):
        return None
    if 'stringValue' in v:
        return v['stringValue']
    if 'integerValue' in v:
        return int(v['integerValue'])
    if 'doubleValue' in v:
        return float(v['doubleValue'])
    if 'booleanValue' in v:
        return v['booleanValue']
    if 'timestampValue' in v:
        return v['timestampValue']          # kept as the raw RFC 3339 string
    if 'mapValue' in v:
        return {k: dec(x) for k, x in (v['mapValue'].get('fields') or {}).items()}
    if 'arrayValue' in v:
        return [dec(x) for x in (v['arrayValue'].get('values') or [])]
    return None


def enc(v):
    if v is None:
        return {'nullValue': None}
    if isinstance(v, bool):
        return {'booleanValue': v}
    if isinstance(v, int):
        return {'integerValue': str(v)}
    return {'stringValue': str(v)}


def doc_data(d):
    out = {k: dec(v) for k, v in (d.get('fields') or {}).items()}
    out['_id'] = d.get('name', '').rsplit('/', 1)[-1]
    return out


def f_cmp(field, op, value):
    return {'fieldFilter': {'field': {'fieldPath': field}, 'op': op, 'value': value}}


def f_ts(field, op, ts):
    return f_cmp(field, op, {'timestampValue': ts})


def f_eq(field, s):
    return f_cmp(field, 'EQUAL', {'stringValue': s})


def f_in(field, values):
    return f_cmp(field, 'IN', {'arrayValue': {'values': [{'stringValue': v} for v in values]}})


class Store:
    def __init__(self, session):
        self.s = session

    def _ok(self, r, what):
        if r.status_code >= 300:
            raise RuntimeError(f'Firestore {what}: HTTP {r.status_code}')
        return r

    def query(self, collection, where, limit=50):
        q = {'from': [{'collectionId': collection}], 'where': where,
             'orderBy': [{'field': {'fieldPath': 'createdAt'}, 'direction': 'ASCENDING'}], 'limit': limit}
        r = self._ok(self.s.post(f'{DOCS}:runQuery', json={'structuredQuery': q}, timeout=30), 'query ' + collection)
        return [x['document'] for x in r.json() if 'document' in x]

    def count(self, collection, where):
        body = {'structuredAggregationQuery': {
            'structuredQuery': {'from': [{'collectionId': collection}], 'where': where},
            'aggregations': [{'alias': 'n', 'count': {}}]}}
        r = self._ok(self.s.post(f'{DOCS}:runAggregationQuery', json=body, timeout=30), 'count ' + collection)
        for x in r.json():
            if 'result' in x:
                return int(x['result']['aggregateFields']['n']['integerValue'])
        return 0

    def state(self):
        r = self.s.get(f'{DOCS}/{STATE}', timeout=30)
        if r.status_code == 404:
            return {}
        self._ok(r, 'read state')
        return {k: dec(v) for k, v in (r.json().get('fields') or {}).items()}

    def save(self, **fields):
        params = [('updateMask.fieldPaths', k) for k in fields]
        body = {'fields': {k: enc(v) for k, v in fields.items()}}
        self._ok(self.s.patch(f'{DOCS}/{STATE}', params=params, json=body, timeout=30), 'save state')


# ---------- Telegram

class TGError(Exception):
    def __init__(self, method, code, description):
        super().__init__(f'Telegram {method}: {code} {description}')
        self.code, self.description = code, description


class Telegram:
    def __init__(self, token):
        self.token = token
        self.base = f'https://api.telegram.org/bot{token}'

    def call(self, method, **params):
        try:
            r = requests.post(f'{self.base}/{method}', json=params, timeout=40)
        except requests.RequestException as e:
            # The URL holds the token; never let it reach the log.
            raise TGError(method, 'network', type(e).__name__) from None
        try:
            data = r.json()
        except ValueError:
            data = {}
        if not data.get('ok'):
            raise TGError(method, r.status_code, str(data.get('description', ''))[:200].replace(self.token, '***'))
        return data['result']

    def send(self, chat_id, text):
        text = text if len(text) <= 4096 else text[:4000] + '\n…'
        try:
            return self.call('sendMessage', chat_id=chat_id, text=text, parse_mode='HTML',
                             disable_web_page_preview=True)
        except TGError as e:
            if e.code != 400 or 'parse' not in e.description.lower():
                raise
            plain = html.unescape(re.sub(r'<[^>]+>', '', text))
            return self.call('sendMessage', chat_id=chat_id, text=plain, disable_web_page_preview=True)


# ---------- messages (Tajik)

WELCOME = ('✅ <b>Бот пайваст шуд!</b>\n'
           'Ман ба шумо хабар медиҳам:\n'
           '🛒 фармоиши нав дар EVROSTAR — зуд (дар 15–30 дақиқа)\n'
           '⭐ отзыви нав ва 🔔 «вақте мол омад, хабар деҳ»\n'
           '📊 ҳар шом — ҳисобот: Instagram, TikTok ва EVROSTAR\n\n'
           'Фармон: /hisobot — ҳисоботи EVROSTAR барои имрӯз.')
HELP = ('Хабарҳо худкор меоянд.\n'
        '/hisobot — ҳисоботи EVROSTAR барои имрӯз (ҷавоб дар 15–30 дақиқа).')
PRIVATE = 'Ин бот хусусӣ аст. / Это личный бот.'
SOCIAL_MISSING = '📸 Instagram/TikTok: ҳисоботи имрӯза наомад.'


def order_items(o):
    items = o.get('items')
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def order_kind(o):
    ids = {str(i.get('id', '')) for i in order_items(o)}
    return 'kit' if 'kit' in ids else 'service' if 'service' in ids else 'order'


def fmt_order(o):
    items = order_items(o)
    no = cut(o.get('no'), 12) or o['_id'][:6].upper()
    head = {'order': '🛒 <b>Фармоиши нав №{}</b>',
            'kit': '☀️ <b>Дархости комплект №{}</b>',
            'service': '🛠 <b>Дархости сервис №{}</b>'}[order_kind(o)].format(esc(no))
    lines = [head]
    name, phone = cut(o.get('name'), 80), cut(o.get('phone'), 30)
    if name or phone:
        contact = '👤 ' + esc(name or '—')
        if phone:
            contact += ' · 📞 ' + esc(phone)
        digits = wa_digits(phone)
        if digits:
            contact += f' · <a href="https://wa.me/{digits}">WhatsApp</a>'
        lines.append(contact)
    else:
        lines.append('👤 Контакт — дар WhatsApp бо рақами фармоиш')
    if o.get('address'):
        lines.append('📍 ' + esc(cut(o['address'], 200)))
    for i in items[:20]:
        if str(i.get('id')) in ('kit', 'service'):
            lines.append('• ' + esc(cut(i.get('name'), 150)))
        else:
            price = num(i.get('price'))
            qty = int(num(i.get('qty'), 1)) or 1
            lines.append('• {} × {} — {}'.format(esc(cut(i.get('name'), 120)), qty,
                                                 money(price) if price > 0 else 'нарх бо дархост'))
    if len(items) > 20:
        lines.append(f'• … ва боз {len(items) - 20}')
    if num(o.get('total')) > 0:
        lines.append('💰 <b>Ҷамъ: {}</b>'.format(money(o['total'])))
    if o.get('customerCode'):
        lines.append('🆔 Коди харидор: ' + esc(cut(o['customerCode'], 20)))
    lines.append(f'🕒 {local(o.get("createdAt"))} · <a href="{ADMIN}">admin</a>')
    return '\n'.join(lines)


def fmt_review(r):
    rating = int(num(r.get('rating'))) if 1 <= num(r.get('rating')) <= 5 else 0
    lines = ['⭐ <b>Отзыви нав</b>' + (f' — {rating}/5 ' + '★' * rating + '☆' * (5 - rating) if rating else '')]
    if r.get('productName'):
        lines.append('📦 ' + esc(cut(r['productName'], 150)))
    if r.get('text'):
        lines.append('💬 «' + esc(cut(r['text'], 500)) + '»')
    if r.get('name'):
        lines.append('👤 ' + esc(cut(r['name'], 60)))
    lines.append(f'Интизори санҷиш — <a href="{ADMIN}">admin</a>')
    return '\n'.join(lines)


def fmt_alert(a):
    lines = ['🔔 <b>Мунтазири мол</b> («вақте омад, хабар деҳ»)']
    if a.get('productName'):
        lines.append('📦 ' + esc(cut(a['productName'], 150)))
    contact = '👤 ' + esc(cut(a.get('name'), 80) or '—')
    if a.get('phone'):
        contact += ' · 📞 ' + esc(cut(a['phone'], 30))
        digits = wa_digits(a['phone'])
        if digits:
            contact += f' · <a href="https://wa.me/{digits}">WhatsApp</a>'
    lines.append(contact)
    return '\n'.join(lines)


WATCHED = (('orders', 'ordersSince', fmt_order, 'фармоиш', '🛒 <b>Фармоиши нав</b>'),
           ('reviews', 'reviewsSince', fmt_review, 'отзыв', '⭐ <b>Отзыви нав</b>'),
           ('stockAlerts', 'alertsSince', fmt_alert, 'дархост', '🔔 <b>Дархости нав: мунтазири мол</b>'))


def evrostar_block(db):
    start = today_local().replace(hour=0, minute=0, second=0, microsecond=0)
    orders = [doc_data(d) for d in db.query('orders', f_ts('createdAt', 'GREATER_THAN_OR_EQUAL', utc_iso(start)), limit=300)]
    total = sum(num(o.get('total')) for o in orders)
    reviews = len(db.query('reviews', f_ts('createdAt', 'GREATER_THAN_OR_EQUAL', utc_iso(start)), limit=300))
    lines = ['🛒 <b>Барномаи EVROSTAR</b>',
             f'• Фармоишҳои имрӯза: {len(orders)}' + (f' (ҷамъ {money(total)})' if total > 0 else ''),
             f'• Нав, ҳанӯз кор нашуда: {db.count("orders", f_eq("status", "new"))}',
             f'• Дар кор (иҷро нашуда): {db.count("orders", f_in("status", OPEN_STATUSES))}',
             f'• Отзывҳо: имрӯз {reviews}, интизори санҷиш {db.count("reviews", f_eq("status", "pending"))}',
             f'• Мунтазири мол: {db.count("stockAlerts", f_eq("status", "waiting"))}',
             f'<a href="{ADMIN}">admin.html</a>']
    return '\n'.join(lines)


def safe_block(db):
    try:
        return evrostar_block(db)
    except Exception as e:  # keep the rest of the message
        note('warning', f'EVROSTAR numbers: {e}')
        return '🛒 EVROSTAR: маълумот ҳозир гирифта нашуд.'


def header():
    return f'📊 <b>EVROSTAR — {today_local():%d.%m.%Y}</b>'


# ---------- modes

def watch(db, tg, st):
    owner = st.get('chatId')
    offset = int(st.get('updateOffset') or 0)
    wants_report = False
    updates = tg.call('getUpdates', offset=offset, timeout=0, allowed_updates=['message'])
    for u in updates:
        offset = max(offset, int(u['update_id']) + 1)
        m = u.get('message') or {}
        chat = m.get('chat') or {}
        if chat.get('type') != 'private':
            continue
        cid, text = chat.get('id'), (m.get('text') or '').strip()
        cmd = text.split()[0].split('@')[0].lower() if text else ''
        if not owner and cmd == '/start':
            owner = cid
            now = utc_iso(dt.datetime.now(dt.timezone.utc))
            db.save(chatId=cid, ordersSince=now, reviewsSince=now, alertsSince=now)
            st.update(chatId=cid, ordersSince=now, reviewsSince=now, alertsSince=now)
            try:
                tg.call('setMyCommands', commands=[{'command': 'hisobot', 'description': 'Ҳисоботи имрӯза'}])
            except TGError:
                pass
            tg.send(cid, WELCOME + '\n\n' + safe_block(db))
            note('notice', 'Owner chat bound.')
        elif cid == owner:
            if cmd == '/start':
                tg.send(cid, WELCOME)
            elif cmd in ('/hisobot', '/today', '/report'):
                wants_report = True
            else:
                tg.send(cid, HELP)
        else:
            tg.send(cid, PRIVATE)
    if offset != int(st.get('updateOffset') or 0):
        db.save(updateOffset=offset)
    if not owner:
        note('notice', 'No chat bound yet: open the bot in Telegram and press Start.')
        return
    if wants_report:
        tg.send(owner, header() + '\n\n' + safe_block(db))
    for coll, key, fmt, word, title in WATCHED:
        since = st.get(key)
        if not since:
            db.save(**{key: utc_iso(dt.datetime.now(dt.timezone.utc))})
            continue
        docs = db.query(coll, f_ts('createdAt', 'GREATER_THAN', since), limit=50)
        for d in docs[:MAX_ALERTS]:
            try:
                text = fmt(doc_data(d))
            except Exception as e:  # odd data must not block the alerts that follow
                note('warning', f'format {coll}: {type(e).__name__}')
                text = f'{title} — <a href="{ADMIN}">admin</a>'
            tg.send(owner, text)
            db.save(**{key: d['fields']['createdAt']['timestampValue']})
        if len(docs) > MAX_ALERTS:
            tg.send(owner, f'… ва боз {len(docs) - MAX_ALERTS} {word} — <a href="{ADMIN}">admin</a>')
            db.save(**{key: docs[-1]['fields']['createdAt']['timestampValue']})


class NotBound(Exception):
    pass


def digest(db, tg, st, report, fallback=False):
    owner = st.get('chatId')
    if not owner:
        raise NotBound()
    today = f'{today_local():%Y-%m-%d}'
    if fallback:
        if st.get('lastDigestDate') == today:
            return
        tg.send(owner, header() + '\n\n' + SOCIAL_MISSING + '\n\n' + safe_block(db))
        db.save(lastDigestDate=today)
        return
    social = fit(report, 2500) if report.strip() else SOCIAL_MISSING
    if st.get('lastDigestDate') == today:
        # The evening fallback already went out; send the late social part on its own.
        tg.send(owner, header() + '\n\n' + social)
    else:
        tg.send(owner, header() + '\n\n' + social + '\n\n' + safe_block(db))
        db.save(lastDigestDate=today)


def warn_owner(db, tg, st, err):
    """Once a day, tell the owner in Telegram that the order check is failing."""
    try:
        today = f'{today_local():%Y-%m-%d}'
        if st.get('chatId') and st.get('lastErrorDate') != today:
            tg.send(st['chatId'], f'⚠️ Бот фармоишҳоро санҷида натавонист ({esc(type(err).__name__)}). '
                                  'Ҳар 15 дақиқа боз кӯшиш мекунад.')
            db.save(lastErrorDate=today)
    except Exception:
        pass


def event():
    try:
        with open(os.environ.get('GITHUB_EVENT_PATH', ''), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def pick_mode(ev):
    if os.environ.get('GITHUB_EVENT_NAME') == 'schedule':
        return 'fallback' if ev.get('schedule') == FALLBACK_CRON else 'watch'
    mode = str((ev.get('inputs') or {}).get('mode') or os.environ.get('BOT_MODE') or 'test').strip().lower()
    return mode if mode in ('watch', 'digest', 'test', 'reset') else 'test'


def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        note('warning', 'Secret TELEGRAM_BOT_TOKEN is not set yet.')
        return 0
    ev = event()
    mode = pick_mode(ev)
    print(f'mode={mode}')
    tg = Telegram(token)
    db = st = None
    try:
        db = Store(firestore_session())
        st = db.state()
        if mode == 'reset':
            db.save(chatId=None)
            note('notice', 'Chat binding cleared. Press Start in the bot again.')
        elif mode == 'watch':
            watch(db, tg, st)
        elif mode == 'test':
            was_bound = bool(st.get('chatId'))
            if not was_bound:
                watch(db, tg, st)          # binds now if the owner already pressed Start
            if not st.get('chatId'):
                raise NotBound()
            if was_bound:                  # a fresh binding already got the welcome message
                tg.send(st['chatId'], '🧪 Санҷиш: бот кор мекунад.\n\n' + header() + '\n\n' + safe_block(db))
        else:
            report = str((ev.get('inputs') or {}).get('report') or '')
            digest(db, tg, st, report, fallback=(mode == 'fallback'))
    except NotBound:
        note('error', 'No chat bound yet: open the bot in Telegram and press Start.')
        return 1
    except TGError as e:
        if e.code == 401:
            note('error', 'Telegram does not accept TELEGRAM_BOT_TOKEN (Unauthorized). Copy the token from @BotFather again.')
        elif e.code == 403:
            note('error', 'The bot is blocked in Telegram. Open the bot and press Start (Restart).')
        else:
            note('error', str(e))
        return 0 if mode == 'watch' else 1
    except Exception as e:
        note('error', f'{type(e).__name__}: {e}')
        if mode == 'watch' and db and st:
            warn_owner(db, tg, st, e)
        return 0 if mode == 'watch' else 1
    print('done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
