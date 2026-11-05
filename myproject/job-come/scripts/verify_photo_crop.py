#!/usr/bin/env python3
"""Photo crop browser regression; isolated API fixtures, no DB writes/model calls."""
from __future__ import annotations
import asyncio
import copy
import importlib.util
import io
import sys
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from lib.bootstrap import ensure_project_env
ensure_project_env()
from PIL import Image
from playwright.async_api import async_playwright, expect

spec = importlib.util.spec_from_file_location('photo_fixtures', Path(__file__).with_name('verify_resume_steps.py'))
fixtures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixtures
spec.loader.exec_module(fixtures)

async def run(width):
    base = 'http://127.0.0.1:3000'
    profile = copy.deepcopy(fixtures.PROFILE)
    uploaded = []
    errors = []
    # Gradient makes location/scale mistakes visible in the exported pixels.
    src = Image.new('RGB',(600,1200))
    pixels = src.load()
    for y in range(1200):
        for x in range(600):
            pixels[x,y] = (x//3, y//5, 200-y//8)
    buf = io.BytesIO(); src.save(buf,format='PNG')
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width':width,'height':900},service_workers='block')
        async def api(route):
            url,method = route.request.url,route.request.method
            if '/photo?' in url and method == 'PUT':
                header = route.request.headers['content-type']
                message = BytesParser(policy=default).parsebytes(b'Content-Type: '+header.encode()+b'\r\n\r\n'+route.request.post_data_buffer)
                blob = next(part.get_payload(decode=True) for part in message.iter_parts() if part.get_param('name',header='content-disposition')=='file')
                uploaded.append(blob)
                profile['payload']['contact']['photo']={'storage_key':'crop.jpg','enabled':True,'download_url':base+'/fixture-photo.jpg'}
                profile['version']+=1
                await route.fulfill(json=profile)
            elif url.endswith('/profiles/'+fixtures.PROFILE_ID):
                await route.fulfill(json=profile)
            elif '/agent/sessions' in url:
                await route.fulfill(json={'sessions':[]})
            else:
                await route.fulfill(json=fixtures._route_payload(url,method))
        await context.route('**/api/v1/**',api)
        async def boundary(route):
            url=route.request.url
            if '/health/' in url:
                await route.fulfill(json={'llm_enabled':True,'llm_api_key_set':True})
            elif url.endswith('/fixture-photo.jpg'):
                await route.fulfill(body=uploaded[-1],content_type='image/jpeg')
            elif url.startswith(base): await route.fallback()
            else: await route.abort()
        await context.route('**/*',boundary)
        page=await context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        await page.goto(base+'/resume-agent')
        await page.wait_for_load_state('networkidle')
        photo_input=page.locator('input[type=file][accept*="image/jpeg"]').first
        await photo_input.set_input_files({'name':'gradient.png','mimeType':'image/png','buffer':buf.getvalue()})
        dialog=page.get_by_role('dialog',name='裁剪简历照片')
        await expect(dialog).to_be_visible()
        img=dialog.locator('img')
        await expect(img).to_be_visible()
        selection=dialog.locator('[data-crop-selection]')
        before=await selection.bounding_box()
        await page.mouse.move(before['x']+before['width']/2,before['y']+before['height']/2)
        await page.mouse.down(); await page.mouse.move(before['x']+before['width']/2+10,before['y']+before['height']/2+14,steps=8); await page.mouse.up()
        after=await selection.bounding_box()
        assert abs(after['x']-before['x']-10)<1 and abs(after['y']-before['y']-14)<1,(before,after)
        corner=dialog.locator('[data-crop-action="nw"]')
        box=await corner.bounding_box()
        await page.mouse.move(box['x']+12,box['y']+12); await page.mouse.down()
        await page.mouse.move(box['x']+44,box['y']+52,steps=8); await page.mouse.up()
        resized=await selection.bounding_box()
        assert resized['width']<after['width'] and abs(resized['width']/resized['height']-.8)<.005,resized
        slider=dialog.get_by_role('slider',name='缩放')
        await slider.fill('2')
        dims=await img.evaluate('(e)=>({w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height})')
        assert abs(dims['w']/dims['h']-.5)<1e-6,dims
        # Reproduce the old CSS defect independently: preflight caps width only.
        old=await img.evaluate('(e)=>{e.style.maxWidth="100%"; const r=e.getBoundingClientRect();e.style.maxWidth="none";return {w:r.width,h:r.height}}')
        assert abs(old['w']/old['h']-.5)>.1,old
        # Keyboard: selection moves, corner adjusts size without changing ratio.
        await selection.focus(); oldbox=await selection.bounding_box(); await selection.press('ArrowLeft')
        assert abs((await selection.bounding_box())['x']-oldbox['x']+8)<1
        await corner.focus(); await corner.press('ArrowRight')
        # Independent expected source crop from actual rendered geometry.
        ib=await img.bounding_box(); cb=await selection.bounding_box()
        rect=((cb['x']-ib['x'])*600/ib['width'],(cb['y']-ib['y'])*1200/ib['height'],cb['width']*600/ib['width'],cb['height']*1200/ib['height'])
        await page.screenshot(path=f'/tmp/jc-photo-selection-{width}.png')
        await dialog.get_by_role('button',name='保存照片',exact=True).click()
        await expect(dialog).not_to_be_visible()
        assert len(uploaded)==1
        out=Image.open(io.BytesIO(uploaded[0]))
        assert out.size==(819,1024),out.size
        expected=src.crop((rect[0],rect[1],rect[0]+rect[2],rect[1]+rect[3])).resize(out.size)
        for point in [(100,100),(409,512),(700,900)]:
            a,b=out.getpixel(point),expected.getpixel(point)
            assert max(abs(x-y) for x,y in zip(a,b))<5,(a,b,point,rect)
        thumb=page.get_by_alt_text('简历照片').first
        await expect(thumb).to_be_visible()
        assert await thumb.evaluate('(e)=>e.naturalWidth')==819
        assert not errors,errors
        await page.screenshot(path=f'/tmp/jc-photo-crop-{width}.png')
        print(f'PASS {width}px: drag, corner resize, equal-axis zoom, keyboard, multipart JPEG pixels, refreshed thumbnail; old CSS distortion reproduced')
        await browser.close()

async def main():
    await run(1440)
    await run(320)
if __name__=='__main__': asyncio.run(main())
