"""Remove products that were added twice (same name), e.g. when the whole catalogue was imported again.

From every group of products with the same name one stays: the one with a photo, else the oldest.
A copy is only deleted when it has no photo and was created within the last DAYS days, so older
products are never touched. Without APPLY=yes it only prints the plan (dry run).

env: GOOGLE_APPLICATION_CREDENTIALS (service account JSON), APPLY=yes|no, DAYS (default 3)
"""
import datetime as dt
import os
import sys

PROJECT = 'evrostar-c7c85'
DOCS = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents'


def load_key():
    """Copying the key on a phone sometimes drops the closing brace; repair it like telegram_bot.py does."""
    import json
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


def session():
    load_key()
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/datastore'])
    return AuthorizedSession(creds)


def all_products(s):
    out, token = [], None
    while True:
        params = {'pageSize': 300}
        if token:
            params['pageToken'] = token
        r = s.get(f'{DOCS}/products', params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        out += data.get('documents', [])
        token = data.get('nextPageToken')
        if not token:
            return out


def text(doc, field):
    v = (doc.get('fields') or {}).get(field) or {}
    return v.get('stringValue', '')


def when(doc):
    return dt.datetime.fromisoformat(doc['createTime'].replace('Z', '+00:00'))


def plan(docs, days, now):
    groups = {}
    for d in docs:
        key = ' '.join(text(d, 'name').lower().split())
        if key:
            groups.setdefault(key, []).append(d)
    keep_delete = []
    for key, lst in groups.items():
        if len(lst) < 2:
            continue
        lst.sort(key=lambda d: (0 if text(d, 'image') else 1, when(d)))
        keep = lst[0]
        for d in lst[1:]:
            fresh = now - when(d) <= dt.timedelta(days=days)
            if not text(d, 'image') and fresh and when(d) > when(keep):
                keep_delete.append((keep, d))
            else:
                print(f'  left alone (has a photo or is old): {text(d, "name")} [{d["name"].rsplit("/", 1)[-1]}]')
    return keep_delete


def main():
    apply = os.environ.get('APPLY', '').strip().lower() == 'yes'
    days = int(os.environ.get('DAYS', '3') or 3)
    s = session()
    docs = all_products(s)
    now = dt.datetime.now(dt.timezone.utc)
    todo = plan(docs, days, now)
    print(f'Products: {len(docs)}. Copies to delete: {len(todo)}. Mode: {"DELETE" if apply else "dry run"}.')
    for keep, d in todo:
        print(f'  - {text(d, "name")}: delete {d["name"].rsplit("/", 1)[-1]} '
              f'(created {d["createTime"][:16]}), keep {keep["name"].rsplit("/", 1)[-1]}')
    if not apply:
        print('Dry run only. Run again with APPLY=yes to delete.')
        return
    failed = 0
    for _, d in todo:
        doc_id = d['name'].rsplit('/', 1)[-1]
        r = s.delete(f'{DOCS}/products/{doc_id}', timeout=30)
        if r.status_code >= 300:
            failed += 1
            print(f'::error::could not delete {doc_id}: HTTP {r.status_code}')
            continue
        s.delete(f'{DOCS}/productImages/{doc_id}', timeout=30)  # a copy's large photo, if any
    left = len(all_products(s))
    print(f'Deleted: {len(todo) - failed}. Failed: {failed}. Products now: {left}.')
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
