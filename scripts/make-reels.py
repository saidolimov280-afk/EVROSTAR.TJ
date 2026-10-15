#!/usr/bin/env python3
"""Makes vertical Instagram Reels (1080x1920, 12 s) for EVROSTAR products.

Reads the product list from Firestore (or a local JSON file), draws each
product with its price and a WhatsApp call to action, and writes:
  reels/<NN>-<slug>.mp4, reels/<NN>-<slug>.jpg (cover) and reels/reels.json
  (caption for every video, used for scheduling in Metricool).

Run: python3 scripts/make-reels.py               (reads Firestore)
     PRODUCTS_FILE=products.json python3 ...     (reads a saved Firestore response)
Needs Pillow and ffmpeg.
"""
import base64, io, json, math, os, re, subprocess, sys, urllib.request
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PROJECT = 'evrostar-c7c85'
API_KEY = 'AIzaSyA_zCecmxy5IYVzh2wESMDRZ_rZlFpWx6w'  # public web key, same as in index.html
PHONE = '+992 405 555 530'
W, H, FPS, SECONDS = 1080, 1920, 30, 12
OUT = os.path.join(os.path.dirname(__file__), '..', 'reels')
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
NAVY, ORANGE, WHITE, GREEN = (7, 27, 44), (238, 155, 27), (255, 255, 255), (32, 174, 105)

HOOKS = {
    'solar': ['Барқ хомӯш шуд?', 'Барқи худатонро гиред!'],
    'battery': ['Аккумулятори боэътимод', 'Энергия барои шабу рӯз'],
    'camera': ['Хонаатонро муҳофизат кунед', 'Назорат 24/7 аз телефон'],
    'internet': ['Интернети тез дар ҳама ҷо', 'Wi‑Fi барои хона ва роҳ'],
    'other': ['Нав дар EVROSTAR', 'Шабона ҳам равшан'],
}
TAGS = {
    'solar': '#панелиофтобӣ #инвертор #солнечныепанели #инвертор',
    'battery': '#аккумулятор #АКБ #LiFePO4 #аккумуляторы',
    'camera': '#камера #видеонаблюдение #камераофтобӣ #безопасность',
    'internet': '#роутер #wifi #4G #интернет',
    'other': '#прожектор #офтобӣ #фонарь #энергия',
}


def fs_value(v):
    if not isinstance(v, dict):
        return v
    for k in ('stringValue', 'booleanValue', 'doubleValue'):
        if k in v:
            return v[k]
    if 'integerValue' in v:
        return int(v['integerValue'])
    if 'arrayValue' in v:
        return [fs_value(x) for x in v['arrayValue'].get('values', [])]
    return None


def load_products():
    if os.environ.get('PRODUCTS_FILE'):
        data = json.load(open(os.environ['PRODUCTS_FILE']))
    else:
        url = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/products?pageSize=300&key={API_KEY}'
        data = json.load(urllib.request.urlopen(url))
    out = []
    for d in data.get('documents', []):
        p = {k: fs_value(v) for k, v in d.get('fields', {}).items()}
        p['id'] = d['name'].split('/')[-1]
        if p.get('name') and p.get('image') and p.get('price') and p.get('availability', 'in_stock') == 'in_stock':
            out.append(p)
    return out


def load_image(src):
    if src.startswith('data:'):
        raw = base64.b64decode(src.split(',', 1)[1])
    else:
        raw = urllib.request.urlopen(src).read()
    return Image.open(io.BytesIO(raw)).convert('RGBA')


def clean(text):
    # DejaVu has no emoji; drop them and tidy spaces.
    text = re.sub(r'[\U0001F000-\U0001FFFF☀-➿️]', '', text)
    return re.sub(r'\s+', ' ', text.replace('‑', '-')).strip()


def bullets(p, n=3):
    if p.get('_wrong_desc'):
        return []
    desc = p.get('desc') or ''
    parts = [re.sub(r'^Хусусиятҳо:\s*', '', clean(x).lstrip('•-– ')).rstrip('.;') for x in re.split(r'[•\n]', desc)]
    skip = ('ном', 'модел', 'тавсиф', 'эҳтиёт', 'доставка', 'расонидан', 'навъ:')
    good = [x for x in parts if 4 < len(x) <= 44 and not x.endswith(':') and not x.lower().startswith(skip)
            and clean(p['name']).lower() not in x.lower()]
    return good[:n]


def slug(text):
    t = text.lower().translate(str.maketrans('абвгдеёжзийклмнопрстуфхцчшщъыьэюяӣҳҷқӯғ',
                                             'abvgdeejziiklmnoprstufhccss_y_eyaihjqug'))
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')[:40]


def wrap(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        test = (line + ' ' + word).strip()
        if draw.textlength(test, font=font) <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def background():
    bg = Image.new('RGB', (W, H), NAVY)
    glow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(glow).ellipse((-200, 1150, W + 200, 2350), fill=150)
    ImageDraw.Draw(glow).ellipse((600, -300, 1400, 500), fill=60)
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    bg.paste(Image.new('RGB', (W, H), ORANGE), (0, 0), glow)
    return bg


def text_center(draw, y, text, font, fill, alpha=255):
    x = (W - draw.textlength(text, font=font)) / 2
    draw.text((x, y), text, font=font, fill=fill + (alpha,))


def make_frames(p, hook):
    f_brand = ImageFont.truetype(BOLD, 64)
    f_hook = ImageFont.truetype(BOLD, 78)
    f_name = ImageFont.truetype(BOLD, 54)
    f_price = ImageFont.truetype(BOLD, 86)
    f_bul = ImageFont.truetype(REG, 42)
    f_cta = ImageFont.truetype(BOLD, 58)
    f_small = ImageFont.truetype(REG, 40)

    bg = background()
    img = load_image(p['image'])
    scale = min(760 / img.width, 760 / img.height)
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    card = Image.new('RGBA', (img.width + 60, img.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((0, 0, card.width - 1, card.height - 1), 44, fill=(255, 255, 255, 255))
    card.alpha_composite(img, (30, 30))
    shadow = Image.new('RGBA', (card.width + 120, card.height + 120), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((60, 80, card.width + 60, card.height + 80), 44, fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))

    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    hook_lines = wrap(probe, hook, f_hook, W - 140)
    name_lines = wrap(probe, clean(p['name']), f_name, W - 140)[:3]
    buls = bullets(p)
    price = f"{p['price']:,}".replace(',', ' ') + ' сомонӣ'
    old = p.get('oldPrice')

    for i in range(FPS * SECONDS):
        t = i / FPS
        fr = bg.copy().convert('RGBA')
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        # brand
        text_center(d, 70, 'EVROSTAR', f_brand, WHITE)
        d.ellipse((W / 2 + 205, 82, W / 2 + 245, 122), fill=ORANGE + (255,))

        cta = t >= 8.5
        if not cta:
            # hook, slides down from top
            a = ease(t / 0.6)
            y = 190 - 60 * (1 - a)
            for line in hook_lines:
                text_center(d, y, line, f_hook, (255, 189, 89), int(255 * a))
                y += 92
            # product card: pops in, then breathes slowly
            s = 0.75 + 0.25 * ease((t - 0.3) / 0.7) + 0.03 * math.sin(t * 1.4)
            cw, ch = int(card.width * s), int(card.height * s)
            cx, cy = (W - cw) // 2, 420 + (760 + 60 - ch) // 2 + int(8 * math.sin(t * 2))
            if t > 0.3:
                sh = shadow.resize((int(shadow.width * s), int(shadow.height * s)))
                fr.alpha_composite(sh, (cx - int(60 * s), cy - int(60 * s)))
                fr.alpha_composite(card.resize((cw, ch), Image.LANCZOS), (cx, cy))
            # name
            a = ease((t - 1.2) / 0.6)
            y = 1290 + 40 * (1 - a)
            for line in name_lines:
                text_center(d, y, line, f_name, WHITE, int(255 * a))
                y += 66
            # price badge
            if t >= 2.5:
                k = ease((t - 2.5) / 0.4)
                pw = d.textlength(price, font=f_price) + 90
                px, py = (W - pw) / 2, max(y + 24, 1500)
                pop = 1 + 0.12 * math.sin(min(1, (t - 2.5) / 0.4) * math.pi)
                bw, bh = pw * pop, 130 * pop
                d.rounded_rectangle((W / 2 - bw / 2, py + 65 - bh / 2, W / 2 + bw / 2, py + 65 + bh / 2), 65, fill=GREEN + (int(255 * k),))
                text_center(d, py + 18, price, f_price, WHITE, int(255 * k))
                if old and old > p['price']:
                    o = f"{old} сомонӣ"
                    text_center(d, py + 160, o, f_small, (200, 210, 220), int(255 * k))
                    ow = d.textlength(o, font=f_small)
                    d.line(((W - ow) / 2, py + 184, (W + ow) / 2, py + 184), fill=(255, 90, 90, int(255 * k)), width=4)
                by = py + 175 + (50 if old and old > p['price'] else 0)
                for j, b in enumerate(buls):
                    k2 = ease((t - 4 - j * 0.9) / 0.5)
                    if k2 > 0:
                        text_center(d, by + j * 58, '✓ ' + b, f_bul, (220, 232, 240), int(255 * k2))
        else:
            # call to action
            a = ease((t - 8.5) / 0.6)
            small = card.resize((int(card.width * 0.55), int(card.height * 0.55)), Image.LANCZOS)
            fr.alpha_composite(small, ((W - small.width) // 2, 230))
            y = 290 + small.height
            text_center(d, y, price, f_price, (255, 189, 89), int(255 * a))
            y += 160
            d.rounded_rectangle((90, y, W - 90, y + 300), 50, fill=GREEN + (int(255 * a),))
            text_center(d, y + 50, 'Фармоиш дар WhatsApp', f_cta, WHITE, int(255 * a))
            text_center(d, y + 160, PHONE, f_hook, WHITE, int(255 * a))
            y += 360
            text_center(d, y, 'Ҳисор, Бозори Калони Ҳисор', f_small, WHITE, int(255 * a))
            text_center(d, y + 60, 'Расонидан дар Тоҷикистон', f_small, (200, 210, 220), int(255 * a))
            text_center(d, y + 150, 'evrostarshop.com', f_cta, (255, 189, 89), int(255 * a))
        fr.alpha_composite(layer)
        yield fr.convert('RGB')


def render(p, hook, path):
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-shortest',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
           '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    cover = None
    for i, frame in enumerate(make_frames(p, hook)):
        if i == FPS * 5:
            cover = frame
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait():
        sys.exit(f'ffmpeg failed for {path}')
    cover.save(path[:-4] + '.jpg', quality=88)


def caption(p, hook):
    cat = p.get('category') or 'other'
    lines = [f"{hook} ☀", '', clean(p['name']), f"💰 Нарх: {p['price']} сомонӣ"]
    lines += ['✅ ' + b for b in bullets(p)]
    lines += ['', f'📲 Фармоиш дар WhatsApp: {PHONE}', '📍 Ҳисор, Бозори Калони Ҳисор',
              '🚚 Расонидан дар тамоми Тоҷикистон', '🛒 Каталог: evrostarshop.com', '',
              f"#EVROSTAR #Ҳисор #Тоҷикистон #Душанбе #Таджикистан {TAGS.get(cat, TAGS['other'])}"]
    return '\n'.join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    products = load_products()
    # A description that names another product was copied by mistake; show no specs for it.
    for p in products:
        others = [clean(q['name']) for q in products if q is not p]
        p['_wrong_desc'] = any(o in clean(p.get('desc') or '') for o in others)
    # Alternate categories so neighbouring days show different goods.
    by_cat = {}
    for p in sorted(products, key=lambda p: -p['price']):
        by_cat.setdefault(p.get('category') or 'other', []).append(p)
    order = []
    while any(by_cat.values()):
        for cat in sorted(by_cat):
            if by_cat[cat]:
                order.append(by_cat[cat].pop(0))
    only = int(os.environ.get('LIMIT', '0')) or len(order)
    meta = []
    for n, p in enumerate(order[:only], 1):
        cat = p.get('category') or 'other'
        hook = HOOKS.get(cat, HOOKS['other'])[n % 2]
        name = f'{n:02d}-{slug(clean(p["name"]))}'
        path = os.path.join(OUT, name + '.mp4')
        print(f'[{n}/{only}] {name}', flush=True)
        render(p, hook, path)
        meta.append({'n': n, 'id': p['id'], 'file': name + '.mp4', 'cover': name + '.jpg', 'caption': caption(p, hook)})
    json.dump(meta, open(os.path.join(OUT, 'reels.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
