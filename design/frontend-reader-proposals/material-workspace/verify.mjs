import {chromium, expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
const dir=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(dir,'../../..');
const out=path.join(root,'.artifacts/material-workspace-review');
fs.mkdirSync(out,{recursive:true});
const url=pathToFileURL(path.join(dir,'index.html')).href;
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1,acceptDownloads:true});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const checks=[];
const done=name=>{checks.push(name);console.log('PASS',name);};
const visit=async query=>{await page.goto(url+(query?'?'+query:''));await page.locator('#page-title').waitFor({state:'attached'});};
async function capture(name){await page.screenshot({path:path.join(out,name+'.png')});}
async function downloaded(action){const event=page.waitForEvent('download');await action();const d=await event;return {name:d.suggestedFilename(),content:fs.readFileSync(await d.path(),'utf8')};}
try {
  await visit();
  await expect(page.locator('#total')).toHaveText('24건');
  await expect(page.locator('[data-select].material-tile')).toHaveCount(12);
  await page.locator('[data-select="mat-ST-1"]').first().click();
  await expect(page.locator('#preview')).toBeVisible();
  await page.locator('#collapse').click();
  await expect(page.locator('#preview')).toBeHidden();
  await expect(page.locator('[data-select="mat-ST-1"]').first()).toHaveClass(/selected/);
  await page.reload();await expect(page.locator('#preview')).toBeHidden();
  await expect(page.locator('[data-select="mat-ST-1"]').first()).toHaveClass(/selected/);
  done('선택과 미리보기 접기 분리, URL 재조회');

  await page.locator('#next').click();
  const selected=page.locator('.material-tile').last();
  const selectedId=await selected.getAttribute('data-select');
  await selected.scrollIntoViewIfNeeded();await selected.click();
  const scroll=await page.locator('#result-scroll').evaluate(el=>el.scrollTop);
  await page.locator('#expand').click();await expect(page.locator('.results')).toBeHidden();
  await page.locator('#return').click();
  await expect(page.locator('#page-count')).toHaveText('2 / 2');
  await expect(page.locator(`[data-select="${selectedId}"]`).first()).toBeFocused();
  expect(Math.abs(await page.locator('#result-scroll').evaluate(el=>el.scrollTop)-scroll)).toBeLessThan(2);
  await page.locator('[data-view="table"]').click();
  await expect(page.locator('#page-count')).toHaveText('2 / 2');
  await expect(page.locator(`tr[data-select="${selectedId}"]`)).toHaveClass(/selected/);
  await page.locator(`tr[data-select="${selectedId}"]`).press('Enter');
  await expect(page.locator('.results')).toBeHidden();await page.locator('#return').click();
  await page.locator(`tr[data-select="${selectedId}"]`).dblclick();
  await expect(page.locator('.results')).toBeHidden();await page.locator('#return').click();
  done('페이지·선택·스크롤·초점 복귀, 카드/표 전환, Enter·더블클릭');

  await visit();
  const materialTree=page.locator('details').filter({has:page.locator('summary.material-node').filter({hasText:/^ST-001$/})}).last();
  await materialTree.locator('summary').first().press('Enter');
  await page.locator('[data-specimen="SP-ST-001-1"]').click();
  await expect(page.locator('#total')).toHaveText('1건');
  await expect(page.locator('#page-title')).toHaveText('실험 데이터');
  await page.locator('#temperature').selectOption('23');await page.locator('#rate').selectOption('0.001');
  await page.locator('#filters button[type=submit]').click();await expect(page.locator('#total')).toHaveText('1건');
  await page.locator('#temperature').selectOption('80');await page.locator('#filters button[type=submit]').click();
  await expect(page.locator('#total')).toHaveText('0건');
  await expect(page.locator('.empty-state h2')).toHaveText('조건에 맞는 데이터가 없습니다');
  await page.locator('[data-reset]').click();await expect(page.locator('#total')).toHaveText('96건');
  await page.locator('#search').fill('ST-001');await page.locator('#search-form button').click();
  await expect(page.locator('#total')).toHaveText('4건');
  await page.locator('#scenario').selectOption('error');await expect(page.locator('#total')).toBeHidden();
  await expect(page.locator('#range')).toHaveText('조회 실패');
  await page.locator('[data-retry]').click();await expect(page.locator('#total')).toHaveText('4건');
  done('실제 트리 키보드·시편 탐색, 교집합 조건, 빈 결과·오류·조건 보존 재시도');

  await visit('scope=cards&view=table');
  await page.locator('[data-select="card-ST-001"]').click();
  const card=await downloaded(()=>page.locator('[data-download-card]').click());
  expect(card.name).toBe('SC-ST-001.k');expect(card.content).toBe(await page.evaluate(()=>nativeFile));
  await page.locator('[data-select="card-ST-002"]').click();
  await expect(page.locator('#preview button:disabled')).toHaveText('다운로드할 파일 없음');
  await visit('scope=results&view=table');await page.locator('[data-select="output-ST-001"]').click();
  const stored=await downloaded(()=>page.locator('[data-download-stored]').click());
  expect(stored.name).toBe('synthetic-processed-statistics.csv');expect(stored.content.split('\n')).toHaveLength(152);
  await expect(page.locator('#process')).toBeHidden();
  done('직접 저장 카드 bytes 다운로드, 파일 없음 차단, 저장 처리 CSV도 재계산 없이 다운로드');

  await page.locator('[data-task="process"]').click();await page.locator('#calculate').click();
  const numerical=await page.evaluate(()=>{
    const r=processState.result;
    return {end:r.end,n:r.rows.length,finite:r.rows.every(v=>Object.values(v).every(Number.isFinite)),ordered:r.rows.every((v,i)=>i===0||v.x>r.rows[i-1].x),bounds:r.rows.every(v=>v.min<=v.mean&&v.mean<=v.max&&v.sd>=0&&v.n===3),origin:r.rows[0].mean,elastic:curve(tests[1])[1]};
  });
  expect(numerical).toMatchObject({end:12,n:151,finite:true,ordered:true,bounds:true,origin:0});
  expect(numerical.elastic[1]/numerical.elastic[0]).toBeCloseTo(2100,8);
  await page.locator('#save-result').click();await page.reload();await page.locator('[data-task="process"]').click();
  await expect(page.locator('.result-head')).toContainText('브라우저에 예시 저장됨');
  const result=await downloaded(()=>page.locator('#download-result').click());expect(result.content).toBe(stored.content);
  await page.locator('[data-member="test-ST-001-3"]').uncheck();
  await expect(page.locator('#save-result')).toBeDisabled();await expect(page.locator('#download-result')).toBeDisabled();
  await expect(page.locator('.error-notice')).toContainText('이전 입력의 결과');
  await page.locator('#calculate').click();await expect(page.locator('#download-result')).toBeEnabled();
  await page.locator('[data-member="test-ST-001-4"]').check();await expect(page.locator('#calculate')).toBeDisabled();
  await visit('scope=tests&view=table&selected=test-ST-001-1');
  await page.locator('[data-process-material]').click();
  const memberIds=await page.locator('[data-member]:checked').evaluateAll(els=>els.map(el=>el.dataset.member));
  for(const id of memberIds)await page.locator(`[data-member="${id}"]`).uncheck();
  await expect(page.locator('#process-plot')).toContainText('선택한 실험이 없습니다');
  await page.locator('[data-member="test-ST-001-1"]').check();await page.locator('[data-member="test-ST-001-2"]').check();
  await page.locator('.process-inputs summary').click();await page.locator('#points').fill('3');await page.locator('#points').press('Tab');
  await page.locator('#calculate').click();await expect(page.locator('.error-notice').last()).toContainText('결과를 만들지 못했습니다');
  done('공통 관측 구간·수치 단위 fixture 확인, 저장 후 재조회, 변경 결과 차단, 혼합 조건·잘못된 설정·빈 선택');

  // Live legacy baseline from unchanged source; no regeneration of the old index.
  const beforeFile=path.join(out,'before.html');
  fs.writeFileSync(beforeFile,'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:16px">'+fs.readFileSync(path.join(dir,'../workspaces.html'),'utf8')+'</body></html>');
  const tiers=[[1366,768],[1440,900],[1920,1080],[2560,1440],[3840,2160]];
  const geometry=[];
  for(const [width,height] of tiers){
    await page.setViewportSize({width,height});
    await page.goto(pathToFileURL(beforeFile).href);await page.locator('[data-open="1"]').first().click();
    await capture(`before-${width}`);
    await visit('scope=materials&selected=mat-ST-1');
    const list=await page.locator('.results').boundingBox(),preview=await page.locator('#preview').boundingBox();
    expect(preview.x).toBeGreaterThanOrEqual(list.x+list.width-1);expect(Math.abs(preview.y-list.y)).toBeLessThan(2);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await capture(`materials-${width}`);
    await page.locator('[data-view="table"]').click();await capture(`table-${width}`);
    await visit('scope=tests&view=table&selected=test-ST-001-1');await capture(`tests-${width}`);
    await page.locator('.plot').screenshot({path:path.join(out,`plot-crop-${width}.png`)});
    await page.locator('.topbar').screenshot({path:path.join(out,`header-crop-${width}.png`)});
    await page.locator('.explorer').screenshot({path:path.join(out,`navigator-crop-${width}.png`)});
    await page.locator('.result-tools').screenshot({path:path.join(out,`controls-crop-${width}.png`)});
    const tableBox=await page.locator('.data-table').boundingBox();
    await page.screenshot({path:path.join(out,`table-controls-crop-${width}.png`),clip:{x:tableBox.x,y:tableBox.y,width:Math.min(tableBox.width,list.width-16),height:Math.min(150,height-tableBox.y)}});
    await page.locator('#expand').click();await capture(`detail-${width}`);
    geometry.push({width,height,list,preview,devicePixelRatio:await page.evaluate(()=>devicePixelRatio)});
  }
  await page.setViewportSize({width:1920,height:1080});
  await visit('scope=cards&view=table&selected=card-ST-001');await capture('card-1920');
  await page.locator('[data-select="card-ST-002"]').click();await capture('card-missing-1920');
  await page.locator('#scenario').selectOption('empty');await capture('empty-1920');
  await page.locator('#scenario').selectOption('error');await capture('error-1920');
  await visit('scope=materials&selected=mat-ST-4');await capture('long-name-1920');
  await page.locator('[data-task="process"]').click();
  await page.evaluate(()=>{processState.members=tests.slice(0,3).map(t=>t.id);processState.points=151;calculate();});
  await capture('statistics-1920');await page.locator('[data-member="test-ST-001-3"]').uncheck();await capture('statistics-stale-1920');
  for(const width of [1024,960,760]){
    await page.setViewportSize({width,height:900});await visit('scope=tests&view=table&selected=test-ST-001-1');await capture(`narrow-${width}`);
    if(width===760){await expect(page.locator('.results')).toBeHidden();await page.locator('#return').click();await expect(page.locator('.results')).toBeVisible();}
    else {const a=await page.locator('.results').boundingBox(),b=await page.locator('#preview').boundingBox();expect(b.x).toBeGreaterThanOrEqual(a.x+a.width-1);}
  }
  done('다섯 viewport 원본·영역 crop·기존 화면 비교, 좁은 화면 명시적 복귀');
  expect(errors).toEqual([]);
  const source=Object.fromEntries(['index.html','workspace.css','workspace.js','verify.mjs'].map(f=>[f,crypto.createHash('sha256').update(fs.readFileSync(path.join(dir,f))).digest('hex')]));
  fs.writeFileSync(path.join(out,'verification.json'),JSON.stringify({created:new Date().toISOString(),node:process.version,browser:browser.version(),checks,geometry,errors,source,limitations:['synthetic only','no production API or solver qualification','physical high DPI not verified']},null,2));
  console.log('Artifacts:',out);
} finally {await browser.close();}
