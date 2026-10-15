"""Configure Firebase for EVROSTAR from CI with a service account.
- Firebase Auth: enable Phone sign-in, test number, authorized domains, SMS only to Tajikistan
- Firestore: publish firestore.rules
Env: GOOGLE_APPLICATION_CREDENTIALS -> service account JSON. Prints ::notice/::error lines for GitHub."""
import json, os, sys
import google.auth
from google.auth.transport.requests import AuthorizedSession

PROJECT = 'evrostar-c7c85'
DOMAINS = ['evrostarshop.com', 'www.evrostarshop.com']
TEST_NUMBERS = {'+992900000001': '123456'}
creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/firebase'])
s = AuthorizedSession(creds)
ok = True

def note(kind, title, msg):
    print(f'::{kind} title={title}::{str(msg)[:900]}')

# ---- 1. Firebase Auth config
base = f'https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}/config'
r = s.get(base)
if r.status_code != 200:
    ok = False; note('error', 'auth-config-read', f'{r.status_code} {r.text}')
else:
    cfg = r.json()
    domains = list(dict.fromkeys(cfg.get('authorizedDomains', []) + DOMAINS))
    phone = (cfg.get('signIn') or {}).get('phoneNumber') or {}
    tests = dict(phone.get('testPhoneNumbers') or {}); tests.update(TEST_NUMBERS)
    body = {'authorizedDomains': domains, 'signIn': {'phoneNumber': {'enabled': True, 'testPhoneNumbers': tests}}}
    mask = 'authorizedDomains,signIn.phoneNumber.enabled,signIn.phoneNumber.testPhoneNumbers'
    r = s.patch(base, params={'updateMask': mask}, json=body)
    if r.status_code != 200:
        ok = False; note('error', 'auth-config-update', f'{r.status_code} {r.text}')
    else:
        c = r.json()
        note('notice', 'auth-config', 'phone=%s domains=%s testNumbers=%s' % (
            c.get('signIn', {}).get('phoneNumber', {}).get('enabled'), c.get('authorizedDomains'),
            list((c.get('signIn', {}).get('phoneNumber', {}).get('testPhoneNumbers') or {}).keys())))
    # SMS only to Tajikistan (protects against SMS fraud costs). Separate call: not critical if unavailable.
    r = s.patch(base, params={'updateMask': 'smsRegionConfig'}, json={'smsRegionConfig': {'allowlistOnly': {'allowedRegions': ['TJ']}}})
    note('notice' if r.status_code == 200 else 'warning', 'sms-region', 'TJ only' if r.status_code == 200 else f'{r.status_code} {r.text}')

# ---- 2. Firestore rules
src = open(os.path.join(os.path.dirname(__file__), '..', 'firestore.rules'), encoding='utf-8').read()
rr = 'https://firebaserules.googleapis.com/v1'
r = s.post(f'{rr}/projects/{PROJECT}/rulesets', json={'source': {'files': [{'name': 'firestore.rules', 'content': src}]}})
if r.status_code != 200:
    ok = False; note('error', 'rules-compile', f'{r.status_code} {r.text}')
else:
    ruleset = r.json()['name']
    rel = f'projects/{PROJECT}/releases/cloud.firestore'
    r = s.patch(f'{rr}/{rel}', json={'release': {'name': rel, 'rulesetName': ruleset}})
    if r.status_code == 404:
        r = s.post(f'{rr}/projects/{PROJECT}/releases', json={'name': rel, 'rulesetName': ruleset})
    if r.status_code != 200:
        ok = False; note('error', 'rules-release', f'{r.status_code} {r.text}')
    else:
        note('notice', 'firestore-rules', f'published {ruleset}')

# ---- 3. Check: can a code be requested for the test number now?
key = 'AIzaSyA_zCecmxy5IYVzh2wESMDRZ_rZlFpWx6w'
import requests
r = requests.post(f'https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key={key}',
                  headers={'Referer': 'https://evrostarshop.com/'}, json={'phoneNumber': '+992900000001'})
msg = (r.json().get('error') or {}).get('message', 'OK')
# Without a reCAPTCHA token the expected answer is a reCAPTCHA error — that means phone sign-in itself is on.
note('notice', 'phone-check', msg)
sys.exit(0 if ok else 1)
