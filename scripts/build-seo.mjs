// Fills index.html and sitemap.xml with the current product list from Firestore,
// so Google sees products without running JavaScript.
// Run: node scripts/build-seo.mjs            (reads Firestore)
//      SEO_PRODUCTS_FILE=x.json node ...      (reads a local JSON array, for testing)
import { readFile, writeFile } from 'node:fs/promises';

const SITE = 'https://evrostarshop.com/';
const PROJECT = 'evrostar-c7c85';
const API_KEY = 'AIzaSyA_zCecmxy5IYVzh2wESMDRZ_rZlFpWx6w'; // public web key, same as in index.html
const PHONE = '+992405555530';

function fsValue(v) {
  if (!v || typeof v !== 'object') return v;
  if ('stringValue' in v) return v.stringValue;
  if ('integerValue' in v) return Number(v.integerValue);
  if ('doubleValue' in v) return v.doubleValue;
  if ('booleanValue' in v) return v.booleanValue;
  if ('nullValue' in v) return null;
  if ('timestampValue' in v) return { seconds: Math.floor(Date.parse(v.timestampValue) / 1000) };
  if ('arrayValue' in v) return (v.arrayValue.values || []).map(fsValue);
  if ('mapValue' in v) return Object.fromEntries(Object.entries(v.mapValue.fields || {}).map(([k, x]) => [k, fsValue(x)]));
  return null;
}

async function loadProducts() {
  if (process.env.SEO_PRODUCTS_FILE) return JSON.parse(await readFile(process.env.SEO_PRODUCTS_FILE, 'utf8'));
  const out = [];
  let pageToken = '';
  do {
    const url = `https://firestore.googleapis.com/v1/projects/${PROJECT}/databases/(default)/documents/products?pageSize=300&key=${API_KEY}` + (pageToken ? `&pageToken=${encodeURIComponent(pageToken)}` : '');
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Firestore ${res.status}: ${(await res.text()).slice(0, 300)}`);
    const data = await res.json();
    for (const d of data.documents || []) {
      const p = Object.fromEntries(Object.entries(d.fields || {}).map(([k, v]) => [k, fsValue(v)]));
      p.id = d.name.split('/').pop();
      out.push(p);
    }
    pageToken = data.nextPageToken || '';
  } while (pageToken);
  return out;
}

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const clean = s => String(s ?? '').replace(/\s+/g, ' ').trim();
const short = (s, n) => { s = clean(s); return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s; };
const priceNum = p => { const n = Number(String(p ?? '').replace(/[^\d.,]/g, '').replace(',', '.')); return Number.isFinite(n) && n > 0 ? n : null; };
const nameOf = p => clean(p.nameTg || p.name || p.nameRu);
const descOf = p => clean(p.descTg || p.desc || p.descRu);
const productUrl = p => `${SITE}?product=${encodeURIComponent(p.id)}`;
const isWebImage = s => typeof s === 'string' && /^https:\/\//.test(s);
const availability = p => ({ in_stock: 'InStock', out_of_stock: 'OutOfStock', on_order: 'PreOrder' })[p.availability] || null;

function replaceBlock(text, name, content) {
  const start = `<!--${name}_START-->`, end = `<!--${name}_END-->`;
  const a = text.indexOf(start), b = text.indexOf(end);
  if (a < 0 || b < a) throw new Error(`Markers ${name} not found`);
  return text.slice(0, a + start.length) + content + text.slice(b);
}

const products = (await loadProducts())
  .filter(p => p && p.id && nameOf(p) && p.hidden !== true)
  .sort((a, b) => (b.createdAt?.seconds || 0) - (a.createdAt?.seconds || 0));
if (!products.length) { console.log('No products found, leaving files unchanged.'); process.exit(0); }

// 1. Plain HTML list inside the catalog (replaced by the live catalog once JS loads)
const listHtml = '<ul class="seoProducts">' + products.map(p => {
  const price = priceNum(p.price);
  return `<li><a href="${esc(productUrl(p))}">${esc(nameOf(p))}</a>${price ? ` — ${price} сомонӣ` : ''}${descOf(p) ? `<br><small>${esc(short(descOf(p), 160))}</small>` : ''}</li>`;
}).join('') + '</ul>';

// 2. Structured data for Google
const ld = {
  '@context': 'https://schema.org',
  '@type': 'ItemList',
  name: 'EVROSTAR — каталоги молҳо',
  itemListElement: products.map((p, i) => {
    const item = { '@type': 'Product', name: nameOf(p), url: productUrl(p) };
    if (descOf(p)) item.description = short(descOf(p), 300);
    if (isWebImage(p.image)) item.image = p.image;
    if (p.category) item.category = String(p.category);
    const price = priceNum(p.price);
    if (price) {
      item.offers = { '@type': 'Offer', price: String(price), priceCurrency: 'TJS', url: productUrl(p), seller: { '@type': 'Organization', name: 'EVROSTAR', telephone: PHONE } };
      const av = availability(p);
      if (av) item.offers.availability = `https://schema.org/${av}`;
    }
    return { '@type': 'ListItem', position: i + 1, item };
  }),
};
const ldHtml = `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, '\\u003c')}</script>`;

let html = await readFile('index.html', 'utf8');
const before = html;
html = replaceBlock(html, 'SEO_JSONLD', ldHtml);
html = replaceBlock(html, 'SEO_PRODUCTS', listHtml);
if (html !== before) await writeFile('index.html', html);

// 3. Sitemap with a link per product
const today = new Date().toISOString().slice(0, 10);
const urls = [`  <url>\n    <loc>${SITE}</loc>\n    <changefreq>daily</changefreq>\n    <priority>1.0</priority>\n  </url>`]
  .concat(products.map(p => `  <url>\n    <loc>${esc(productUrl(p))}</loc>\n    <priority>0.8</priority>\n  </url>`));
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`;
const oldMap = await readFile('sitemap.xml', 'utf8').catch(() => '');
if (oldMap.replace(/<lastmod>[^<]*<\/lastmod>\s*/g, '') !== sitemap) await writeFile('sitemap.xml', sitemap.replace('<changefreq>daily', `<lastmod>${today}</lastmod>\n    <changefreq>daily`));

console.log(`Products: ${products.length}. index.html ${html !== before ? 'updated' : 'unchanged'}.`);
