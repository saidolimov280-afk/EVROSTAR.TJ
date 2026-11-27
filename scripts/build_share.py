"""Share pages and photos for every product, so a product link sent in WhatsApp or Telegram
shows the photo, name and price, and Google gets a real photo for each product.

For every product it writes:
  p/<id>.jpg   the product photo (JPEG, at most 800 px)
  p/<id>.html  a small page with Open Graph tags; people are sent on to /?product=<id> at once
  p/pages.json the list of products that have a page, and their photo URLs
               (read by the app for its share buttons and by scripts/build-seo.mjs for Google)
Pages of deleted products are removed.

Runs every day in GitHub Actions (.github/workflows/seo-products.yml), before build-seo.mjs.
Run:  python scripts/build_share.py                 (reads Firestore)
      SHARE_DATA_FILE=x.json python scripts/build_share.py
          (local test: {"products": [{...}], "productImages": {"<id>": "<data URL or https URL>"}})
      SHARE_OUT_DIR=dir   writes somewhere else than p/ (tests)
"""
import base64
import hashlib
import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

SITE = 'https://evrostarshop.com/'
PROJECT = 'evrostar-c7c85'
API_KEY = 'AIzaSyA_zCecmxy5IYVzh2wESMDRZ_rZlFpWx6w'  # public web key, same as in index.html
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get('SHARE_OUT_DIR') or ROOT / 'p')
MAX_SIDE = 800
MAX_DOWNLOAD = 15 * 1024 * 1024
ID_OK = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def fs_value(v):
    if not isinstance(v, dict):
        return v
    if 'stringValue' in v:
        return v['stringValue']
    if 'integerValue' in v:
        return int(v['integerValue'])
    if 'doubleValue' in v:
        return float(v['doubleValue'])
    if 'booleanValue' in v:
        return v['booleanValue']
    if 'timestampValue' in v:
        return v['timestampValue']
    if 'arrayValue' in v:
        return [fs_value(x) for x in v['arrayValue'].get('values', [])]
    if 'mapValue' in v:
        return {k: fs_value(x) for k, x in v['mapValue'].get('fields', {}).items()}
    return None


def list_collection(name):
    docs, token = [], ''
    while True:
        url = (f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/{name}'
               f'?pageSize=100&key={API_KEY}' + (f'&pageToken={urllib.parse.quote(token)}' if token else ''))
        with urllib.request.urlopen(url, timeout=60) as res:
            data = json.load(res)
        for d in data.get('documents', []):
            item = {k: fs_value(x) for k, x in d.get('fields', {}).items()}
            item['id'] = d['name'].rsplit('/', 1)[-1]
            docs.append(item)
        token = data.get('nextPageToken', '')
        if not token:
            return docs


def load():
    if os.environ.get('SHARE_DATA_FILE'):
        data = json.loads(Path(os.environ['SHARE_DATA_FILE']).read_text(encoding='utf-8'))
        return data.get('products', []), data.get('productImages', {})
    products = list_collection('products')
    images = {d['id']: d.get('image') for d in list_collection('productImages')}
    return products, images


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def short(s, n):
    s = clean(s)
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


def price_num(v):
    try:
        n = float(re.sub(r'[^\d.]', '', str(v).replace(',', '.')))
    except ValueError:
        return None
    return n if n > 0 else None


def money(n):
    whole = int(round(n)) if abs(n - round(n)) < 0.005 else None
    text = f'{whole:,}'.replace(',', ' ') if whole is not None else f'{n:,.2f}'.replace(',', ' ')
    return text + ' сомонӣ'


def image_bytes(src):
    src = str(src or '')
    if src.startswith('data:image/'):
        return base64.b64decode(src.split(',', 1)[1])
    if src.startswith('https://'):
        with urllib.request.urlopen(src, timeout=60) as res:
            data = res.read(MAX_DOWNLOAD + 1)
        if len(data) > MAX_DOWNLOAD:
            raise ValueError('photo is too large')
        return data
    return None


def to_jpeg(raw):
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.getchannel('A'))
        im = bg
    else:
        im = im.convert('RGB')
    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, 'JPEG', quality=82, optimize=True, progressive=True)
    return out.getvalue(), im.size


def write_if_changed(path, data):
    data = data if isinstance(data, bytes) else data.encode('utf-8')
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


def page(p, photo):
    pid = p['id']
    name = clean(p.get('nameTg') or p.get('name') or p.get('nameRu'))
    price, old = price_num(p.get('price')), price_num(p.get('oldPrice'))
    price_text = money(price) if price else 'Нархро пурсед'
    if price and old and old > price:
        price_text += f' (пештар {money(old)})'
    desc = short(p.get('descTg') or p.get('desc') or p.get('descRu'), 150)
    description = (desc + ' · ' if desc else '') + 'EVROSTAR, Ҳисор. Фармоиш дар WhatsApp: +992 405 555 530'
    target = '/?product=' + urllib.parse.quote(pid)
    e = lambda s: html.escape(str(s), quote=True)
    meta = [
        ('property', 'og:type', 'product'), ('property', 'og:site_name', 'EVROSTAR'),
        ('property', 'og:title', f'{name} — {price_text}'), ('property', 'og:description', description),
        ('property', 'og:url', f'{SITE}p/{pid}.html'), ('property', 'og:locale', 'tg_TJ'),
    ]
    if photo:
        meta += [('property', 'og:image', photo['url']), ('property', 'og:image:type', 'image/jpeg'),
                 ('property', 'og:image:width', photo['width']), ('property', 'og:image:height', photo['height']),
                 ('property', 'og:image:alt', name), ('name', 'twitter:card', 'summary_large_image')]
    if price:
        meta += [('property', 'product:price:amount', f'{price:g}'), ('property', 'product:price:currency', 'TJS')]
    tags = '\n'.join(f'<meta {k}="{e(n)}" content="{e(v)}">' for k, n, v in meta)
    return f'''<!doctype html>
<html lang="tg"><head><meta charset="utf-8">
<title>{e(name)} — {e(price_text)} | EVROSTAR</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{e(SITE + target.lstrip('/'))}">
{tags}
<meta http-equiv="refresh" content="0;url={e(target)}">
<script>location.replace({json.dumps(target)})</script>
</head><body style="font-family:Arial,sans-serif;padding:24px"><p><a href="{e(target)}">{e(name)} — {e(price_text)}</a></p></body></html>
'''


def main():
    products, images = load()
    products = [p for p in products if p and ID_OK.match(str(p.get('id', ''))) and p.get('hidden') is not True
                and clean(p.get('nameTg') or p.get('name') or p.get('nameRu'))]
    if not products:
        print('No products found, leaving share pages unchanged.')
        return
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, made, failed = {}, 0, []
    for p in products:
        pid, photo = p['id'], None
        for src in (images.get(pid), p.get('image')):
            try:
                raw = image_bytes(src)
                if not raw:
                    continue
                jpeg, (w, h) = to_jpeg(raw)
            except Exception as err:  # a broken or unreachable photo must not stop the other products
                failed.append(f'{pid}: {type(err).__name__}')
                continue
            write_if_changed(OUT / f'{pid}.jpg', jpeg)
            version = hashlib.sha256(jpeg).hexdigest()[:10]
            photo = {'url': f'{SITE}p/{pid}.jpg?v={version}', 'width': w, 'height': h}
            made += 1
            break
        if not photo and (OUT / f'{pid}.jpg').exists():
            (OUT / f'{pid}.jpg').unlink()
        write_if_changed(OUT / f'{pid}.html', page(p, photo))
        manifest[pid] = photo['url'] if photo else None
    keep = set(manifest)
    for f in OUT.iterdir():
        if f.suffix in ('.jpg', '.html') and f.stem not in keep:
            f.unlink()
    pages = {'ids': sorted(keep), 'images': {k: v for k, v in sorted(manifest.items()) if v}}
    write_if_changed(OUT / 'pages.json', json.dumps(pages, ensure_ascii=False, indent=1) + '\n')
    print(f'Share pages: {len(keep)}, photos: {made}' + (f', photos that failed: {len(failed)} ({"; ".join(failed[:5])})' if failed else ''))


if __name__ == '__main__':
    main()
    sys.exit(0)
