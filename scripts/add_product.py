"""Add a product to the shop from a JSON file in catalog/new/ (or update it if that name already exists).

Fields: name, nameRu, price, oldPrice, category, availability, image (https), desc, descRu.
A product with the same name (any letter case / spacing) is updated, never added a second time.
Without APPLY=yes it only prints what it would do.

env: GOOGLE_APPLICATION_CREDENTIALS (service account JSON), FILE=catalog/new/x.json, APPLY=yes|no
"""
import datetime as dt
import json
import os
import sys

from remove_duplicates import DOCS, all_products, session, text

FIELDS = ('name', 'nameRu', 'price', 'oldPrice', 'category', 'availability', 'image', 'desc', 'descRu')
CATEGORIES = {'panels', 'inverters', 'battery', 'camera', 'internet', 'stabilizer', 'solar', 'tv', 'other'}
AVAILABILITY = {'in_stock', 'out_of_stock', 'on_order', 'unknown'}


def enc(v):
    if v is None:
        return {'nullValue': None}
    if isinstance(v, bool):
        return {'booleanValue': v}
    if isinstance(v, int):
        return {'integerValue': str(v)}
    if isinstance(v, float):
        return {'doubleValue': v}
    if isinstance(v, dt.datetime):
        return {'timestampValue': v.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
    return {'stringValue': str(v)}


def load(path):
    p = json.load(open(path, encoding='utf-8'))
    unknown = set(p) - set(FIELDS)
    errors = []
    if unknown:
        errors.append('unknown fields: ' + ', '.join(sorted(unknown)))
    if not str(p.get('name', '')).strip():
        errors.append('name is required')
    if p.get('price') is not None and (not isinstance(p['price'], (int, float)) or p['price'] < 0):
        errors.append('price must be a number ≥ 0')
    if p.get('category') and p['category'] not in CATEGORIES:
        errors.append('category must be one of ' + ', '.join(sorted(CATEGORIES)))
    if p.get('availability') and p['availability'] not in AVAILABILITY:
        errors.append('availability must be one of ' + ', '.join(sorted(AVAILABILITY)))
    if p.get('image') and not str(p['image']).startswith('https://'):
        errors.append('image must be an https:// link')
    if errors:
        raise SystemExit('::error::' + '; '.join(errors))
    return p


def main():
    path = os.environ.get('FILE', '').strip()
    if not path.startswith('catalog/new/') or not path.endswith('.json') or '..' in path:
        raise SystemExit('::error::FILE must be a .json file in catalog/new/')
    apply = os.environ.get('APPLY', '').strip().lower() == 'yes'
    p = load(path)
    s = session()
    key = ' '.join(p['name'].lower().split())
    existing = next((d for d in all_products(s)
                     if key in (' '.join(text(d, 'name').lower().split()), ' '.join(text(d, 'nameRu').lower().split()))), None)
    now = dt.datetime.now(dt.timezone.utc)
    if existing:
        doc_id = existing['name'].rsplit('/', 1)[-1]
        fields = {k: p[k] for k in FIELDS if k in p}
        fields['updatedAt'] = now
        print(f'Update «{p["name"]}» [{doc_id}]: {", ".join(k for k in fields if k != "updatedAt")}')
        if apply:
            params = [('updateMask.fieldPaths', k) for k in fields]
            r = s.patch(f'{DOCS}/products/{doc_id}', params=params,
                        json={'fields': {k: enc(v) for k, v in fields.items()}}, timeout=30)
            r.raise_for_status()
    else:
        fields = {'name': p['name'], 'price': p.get('price') or 0, 'oldPrice': p.get('oldPrice'),
                  'category': p.get('category') or 'other', 'availability': p.get('availability') or 'unknown',
                  'image': p.get('image') or '', 'desc': p.get('desc') or '', 'createdAt': now, 'updatedAt': now}
        for k in ('nameRu', 'descRu'):
            if p.get(k):
                fields[k] = p[k]
        print(f'Add «{p["name"]}» — {fields["price"]} сомонӣ, {fields["category"]}, {fields["availability"]}')
        if apply:
            r = s.post(f'{DOCS}/products', json={'fields': {k: enc(v) for k, v in fields.items()}}, timeout=30)
            r.raise_for_status()
            doc_id = r.json()['name'].rsplit('/', 1)[-1]
            print(f'Added as {doc_id}: https://evrostarshop.com/?product={doc_id}')
    if not apply:
        print('Dry run only. Run again with APPLY=yes to save.')


if __name__ == '__main__':
    sys.exit(main())
