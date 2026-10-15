"""Google Play phone screenshots (1080x1920) from the live site, Tajik and Russian.
Run in CI (needs internet): python play/screenshots.py OUTDIR"""
import asyncio, os, sys
from playwright.async_api import async_playwright
OUT = sys.argv[1] if len(sys.argv) > 1 else 'play/screenshots'
URL = 'https://evrostarshop.com/'

async def shoot(browser, lang):
    ctx = await browser.new_context(viewport={'width': 360, 'height': 640}, device_scale_factor=3,
                                    user_agent='Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36')
    await ctx.add_init_script(f"try{{localStorage.setItem('evrostar_language','{lang}')}}catch(e){{}}")
    page = await ctx.new_page()
    await page.goto(URL, wait_until='networkidle')
    try:
        await page.click('#entrySkip', timeout=4000)
    except Exception:
        pass
    await page.wait_for_timeout(2500)
    os.makedirs(OUT, exist_ok=True)
    async def snap(name):
        await page.wait_for_timeout(1200)
        await page.screenshot(path=f'{OUT}/{lang}-{name}.png')
    await snap('1-home')
    await page.evaluate("location.hash='#catalog'"); await snap('2-catalog')
    try:
        await page.click('#products .productCard .details', timeout=5000)
        await page.wait_for_selector('#detail[open]', timeout=5000)
        await snap('3-product')
        await page.evaluate("document.getElementById('detail').close()")
    except Exception as e:
        print('product detail skipped:', e)
    await page.evaluate("location.hash='#calculator'"); await snap('4-calculator')
    await page.evaluate("location.hash='#kits'"); await snap('5-kits')
    await page.evaluate("location.hash='#service'"); await snap('6-service')
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for lang in ('ru', 'tg'):
            await shoot(b, lang)
        await b.close()
    print('\n'.join(sorted(os.listdir(OUT))))

asyncio.run(main())
