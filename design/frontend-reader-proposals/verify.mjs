import { chromium, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const dir=path.dirname(fileURLToPath(import.meta.url));
const output=path.resolve(process.env.CMP_READER_EVIDENCE || path.join(dir,'../../.artifacts/reader-proposals'));
fs.mkdirSync(output,{recursive:true});
const fragment=fs.readFileSync(path.join(dir,'workspaces.html'),'utf8');
const standalone='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CAE reader proposals — unselected</title><body style="margin:16px">'+fragment+'</body></html>';
fs.writeFileSync(path.join(output,'preview.html'),standalone);
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1920,height:1080},acceptDownloads:true});
const errors=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));
const assert=(ok,name)=>{if(!ok)throw Error(name);checks.push(name);};
const snap=async(name)=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:path.join(output,name+'.png')});};
try {
 await page.goto(pathToFileURL(path.join(output,'preview.html')).href);
 const root=page.locator('#cae-independent'),mount=root.locator('.mount');
 await mount.locator('section').first().waitFor();
 for(const design of ['a','b','c','d','e','f']){
  await page.setViewportSize({width:1920,height:1080});
  await root.locator('.proposal select').selectOption(design);
  await root.locator('[data-task="tests"]').click();
  assert(await mount.getAttribute('data-mode')==='list',design+' initial unselected');
  await snap(design+'-list');
  const first=root.locator('[data-open="1"]');
  const handle=await first.elementHandle();
  await first.click();
  assert(await mount.getAttribute('data-mode')==='preview',design+' single click preview');
  assert(await handle.evaluate(el=>el.isConnected),design+' result DOM preserved');
  assert(await root.locator('.reader-preview .facts').innerText().then(t=>t.includes('23 °C')&&t.includes('0.001')),design+' preview conditions');
  assert(await first.getAttribute('aria-pressed')==='true',design+' selected identity');
  await snap(design+'-preview');
  await page.screenshot({path:path.join(output,design+'-preview-full.png'),fullPage:true});
  await root.locator('[data-collapse]').click();
  assert(await mount.getAttribute('data-mode')==='list'&&await first.getAttribute('aria-pressed')==='true',design+' collapse retains selection');
  await root.locator('[data-reopen]').click();
  await root.locator('[data-expand]').click();
  assert(await mount.getAttribute('data-mode')==='detail',design+' visible detail action');
  assert(await root.locator('[data-open]').count()===0,design+' full detail owns screen');
  await snap(design+'-detail');
  await root.locator('[data-close]').click();
  assert(await first.getAttribute('aria-pressed')==='true',design+' return selection');
  await first.dblclick();
  assert(await mount.getAttribute('data-mode')==='detail',design+' native double click');
  await root.locator('[data-close]').click();
  await first.focus();await first.press('Enter');
  assert(await mount.getAttribute('data-mode')==='detail',design+' keyboard detail');
  await page.keyboard.press('Escape');
  await expect(first).toBeFocused();
  assert(await first.evaluate(el=>document.activeElement===el),design+' keyboard focus restored');

  // Search and second-page return, including nested list scroll and ordinary identity.
  await root.locator('[data-query]').fill('Reference');await root.locator('[data-search]').click();
  const next=design==='f'?'[data-mpage="1"]':'[data-page="1"]';
  await root.locator(next).click();const id=design==='f'?7:13;
  const secondPage=root.locator(`[data-open="${id}"]`);await secondPage.click();
  const scroller=root.locator(design==='f'?'.f-matrix':'.result-scroll').first();
  await scroller.evaluate(el=>{el.scrollTop=65;el.scrollLeft=20});
  const scroll=await scroller.evaluate(el=>[el.scrollTop,el.scrollLeft]);
  await root.locator('[data-expand]').click();await root.locator('[data-close]').click();
  await expect(secondPage).toBeFocused();
  assert(await root.locator('[data-query]').inputValue()==='Reference'&&await secondPage.getAttribute('aria-pressed')==='true',design+' query page return');
  assert(await scroller.evaluate((el,v)=>Math.abs(el.scrollTop-v[0])<2&&Math.abs(el.scrollLeft-v[1])<2,scroll),design+' list scroll restored');
  await secondPage.click();await root.locator(next).click();
  assert(await root.locator('.reader-preview').count()===0&&await root.locator('[data-open][aria-pressed=true]').count()===0,design+' page clears stale preview');
  await root.locator('[data-query]').fill('no-such-record');await root.locator('[data-search]').click();
  assert(await root.locator('.empty').isVisible(),design+' empty result');
  await root.locator('[data-reset]').last().click();

  // Stored card is a direct entry; no generation step, native bytes remain exact.
  await root.locator('[data-task="cards"]').click();await first.dblclick();
  assert(await root.locator('.properties').innerText().then(t=>t.includes('7850')&&t.includes('210')&&t.includes('0.30')),design+' individual saved properties');
  await snap(design+'-card');
  if(design==='b'){
   const download=page.waitForEvent('download');await root.locator('[data-download]').click();const file=await download;
   const bytes=fs.readFileSync(await file.path());
   assert(createHash('sha256').update(bytes).digest('hex').toUpperCase()==='FE8873B1F6978D5BF30D4936EADBEE9FB3B3BF5CD086E4C827BDF2E6105829A1','exact native download');
  }
  await root.locator('[data-related]').click();assert(await root.locator('.facts').innerText().then(t=>t.includes('td-00042')),design+' exact relation');
  await root.locator('[data-return-related]').click();assert(await root.locator('.properties').count()===1,design+' related return');
  await root.locator('[data-close]').click();await root.locator('[data-open="2"]').dblclick();
  assert(await root.getByText('다운로드할 파일 없음',{exact:true}).isDisabled(),design+' missing artifact');
  await root.locator('[data-task="tests"]').click();
  for(const [width,height] of [[1366,768],[1440,900],[2560,1440],[3840,2160],[1024,900],[360,900]]){
   await page.setViewportSize({width,height});await first.click();
   assert(await root.evaluate(el=>el.scrollWidth<=el.clientWidth+2),design+' containment '+width);
   const header=await root.locator('.reader-preview>header').boundingBox();
   assert(header.y>=-1&&header.y+header.height<=height+1,design+' preview header visible '+width);
   await snap(design+'-preview-'+width);
   await root.locator('[data-collapse]').click();
   await first.scrollIntoViewIfNeeded();const box=await first.boundingBox();
   await page.mouse.dblclick(box.x+Math.min(12,box.width/2),box.y+box.height/2,{delay:120});
   assert(await mount.getAttribute('data-mode')==='detail',design+' physical double click after preview scroll '+width);
   await root.locator('[data-close]').click();await expect(first).toBeFocused();
  }
 }
 assert(errors.length===0,'no browser runtime errors');
 fs.writeFileSync(path.join(output,'checks.json'),JSON.stringify({sourceSha256:createHash('sha256').update(fragment).digest('hex'),checks,errors,limitations:['Synthetic 48/8 records, no production API or asynchronous response simulation','No reload persistence or physical high-DPI acceptance']},null,2));
 console.log(JSON.stringify({checks:checks.length,errors,evidence:output}));
} finally {await browser.close();}
