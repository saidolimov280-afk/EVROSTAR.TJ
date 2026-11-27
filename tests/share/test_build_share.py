"""Tests for scripts/build_share.py (product share pages and photos). Needs Pillow.
Run: pip install pillow && python tests/share/test_build_share.py
"""
import base64
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
failures = []


def check(cond, label):
    print(('PASS ' if cond else 'FAIL ') + label)
    if not cond:
        failures.append(label)


def data_url(fmt, size, mode='RGB', color=(30, 120, 200)):
    im = Image.new(mode, size, color if mode == 'RGB' else (*color, 120))
    out = io.BytesIO()
    im.save(out, fmt)
    return f'data:image/{fmt.lower()};base64,' + base64.b64encode(out.getvalue()).decode()


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    out = tmp / 'p'
    out.mkdir()
    (out / 'gone123.html').write_text('old')
    (out / 'gone123.jpg').write_bytes(b'old')
    data = {
        'products': [
            {'id': 'panel630', 'name': 'Панели офтобӣ 630W', 'price': 1200, 'oldPrice': 1350, 'desc': 'Моно, 630 Вт. ' * 30,
             'image': data_url('WEBP', (400, 300))},
            {'id': 'battery1', 'name': 'Аккумулятор <12V>', 'price': '420', 'image': data_url('PNG', (1600, 1200), 'RGBA')},
            {'id': 'noPhoto', 'name': 'Кабел 6 мм', 'price': 0},
            {'id': 'hiddenOne', 'name': 'Пинҳон', 'price': 5, 'hidden': True},
            {'id': '../evil', 'name': 'Бад', 'price': 1},
        ],
        'productImages': {'panel630': data_url('JPEG', (1400, 1050))},
    }
    src = tmp / 'data.json'
    src.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    env = {**os.environ, 'SHARE_DATA_FILE': str(src), 'SHARE_OUT_DIR': str(out)}
    run = lambda: subprocess.run([sys.executable, str(ROOT / 'scripts/build_share.py')], env=env, capture_output=True, text=True)
    r = run()
    print(r.stdout.strip(), r.stderr.strip())
    check(r.returncode == 0, 'script runs')

    im = Image.open(out / 'panel630.jpg')
    check(im.format == 'JPEG' and max(im.size) == 800 and im.size == (800, 600), 'full photo from productImages, JPEG at most 800 px')
    page = (out / 'panel630.html').read_text(encoding='utf-8')
    check('property="og:image" content="https://evrostarshop.com/p/panel630.jpg?v=' in page, 'share page has og:image with version')
    check('og:title" content="Панели офтобӣ 630W — 1 200 сомонӣ (пештар 1 350 сомонӣ)"' in page, 'title has name, price and old price')
    check('location.replace("/?product=panel630")' in page and 'url=/?product=panel630' in page, 'people are sent on to the shop')
    check('og:width' not in page and 'og:image:width" content="800"' in page, 'image size given')
    b = Image.open(out / 'battery1.jpg')
    check(b.mode == 'RGB' and b.size == (800, 600), 'transparent PNG becomes JPEG on white')
    check('Аккумулятор &lt;12V&gt;' in (out / 'battery1.html').read_text(encoding='utf-8'), 'names are escaped')
    no = (out / 'noPhoto.html').read_text(encoding='utf-8')
    check('og:image' not in no and 'Нархро пурсед' in no and not (out / 'noPhoto.jpg').exists(), 'product without photo/price still gets a page')
    check(not (out / 'hiddenOne.html').exists() and not list(out.glob('*evil*')), 'hidden products and bad ids are skipped')
    check(not (out / 'gone123.html').exists() and not (out / 'gone123.jpg').exists(), 'pages of deleted products are removed')
    pages = json.loads((out / 'pages.json').read_text(encoding='utf-8'))
    check(pages['ids'] == ['battery1', 'noPhoto', 'panel630'] and set(pages['images']) == {'battery1', 'panel630'}, 'pages.json lists pages and photos')

    before = {f.name: f.read_bytes() for f in out.iterdir()}
    run()
    check(before == {f.name: f.read_bytes() for f in out.iterdir()}, 'second run changes nothing (no daily commits)')

    empty = tmp / 'empty.json'
    empty.write_text('{"products": []}')
    r = subprocess.run([sys.executable, str(ROOT / 'scripts/build_share.py')], env={**env, 'SHARE_DATA_FILE': str(empty)}, capture_output=True, text=True)
    check(r.returncode == 0 and (out / 'panel630.html').exists(), 'empty product list (e.g. a read error) keeps the pages')

print(f'\n{len(failures)} failed' if failures else '\nall passed')
sys.exit(1 if failures else 0)
