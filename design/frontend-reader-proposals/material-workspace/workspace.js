'use strict';
// Review-only fixture and interaction code. No production API or engineering policy is implemented here.
const $ = selector => document.querySelector(selector);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const groups = [
  {id:'steel',name:'강재',parent:'금속',code:'ST',density:7850,modulus:210,nu:.30,strength:480,yield:310},
  {id:'aluminum',name:'알루미늄 합금',parent:'금속',code:'AL',density:2700,modulus:70,nu:.33,strength:320,yield:240},
  {id:'polymer',name:'열가소성 수지',parent:'고분자',code:'PA',density:1140,modulus:2.7,nu:.39,strength:68,yield:45}
];
const materials = groups.flatMap(g => Array.from({length:8},(_,i)=>({
  ...g, id:`mat-${g.code}-${i+1}`, code:`${g.code}-${String(i+1).padStart(3,'0')}`,category:g.id,
  name:i===3?`${g.name} ${g.code}-04 · 장기 보관 시편의 비교 평가를 위한 연구용 소재`: `${g.name} ${g.code}-${String(i+1).padStart(2,'0')}`,
  state:g.id==='polymer'?'사출 성형 · 건조 상태':i%2?'열처리 · 판재':'압연 · 판재',
  lot:`LOT-${g.code}-${String(i+1).padStart(2,'0')}`, revision:2,
  modulus:g.modulus*(1+i*.004), strength:g.strength+i*2
})));
const tests = materials.flatMap(m => Array.from({length:4},(_,i)=>({
  id:`test-${m.code}-${i+1}`,name:`${m.code} 인장 시험 ${String(i+1).padStart(2,'0')}`,materialId:m.id,
  code:`TD-${m.code}-${i+1}`,specimen:`SP-${m.code}-${i+1}`,temp:i===3?80:23,rate:i===3?.01:.001,
  direction:m.category==='polymer'?'유동 0°':'압연 0°', kind:'인장',factor:[.97,1,1.025,.88][i],end:i===0?12:15,file:`${m.code}_${i+1}_raw.csv`
})));
const nativeFile = '$ SYNTHETIC REVIEW FIXTURE - NOT QUALIFIED FOR SOLVER USE\n*KEYWORD\n*MAT_ELASTIC\n$ MID        RO          E        PR\n       1   7.85E-9     210000       0.3\n*END\n';
const cards = materials.slice(0,12).map((m,i)=>({id:`card-${m.code}`,name:`${m.code} 선형 탄성 카드`,code:`SC-${m.code}`,materialId:m.id,
  solver:i%2?'Abaqus':'LS-DYNA',model:'선형 탄성',units:'mm · tonne · s',available:i===0, content:i===0?nativeFile:null}));
const outputs = [{id:'output-ST-001',code:'PD-ST-001',name:'ST-001 반복 인장 대표 데이터',materialId:materials[0].id,type:'통계 데이터',members:tests.slice(0,3).map(t=>t.id),saved:true}];
const scopes = {materials:'소재',tests:'실험 데이터',results:'처리 데이터·모델',cards:'솔버 카드'};
const state = {scope:'materials',view:'tiles',category:'',materialId:'',specimen:'',query:'',temp:'',rate:'',available:'',page:1,selected:null,previewOpen:false,previewTab:'properties',expanded:false,scroll:0,focus:null,scenario:'normal',sort:'name',checked:new Set()};
const processState = {members:tests.slice(0,3).map(t=>t.id),points:151,result:null,saved:false,stale:false,error:false};
let lastRows=[];

function materialOf(record){return materials.find(m=>m.id===record.materialId)||record;}
function collection(){return {materials,tests,results:outputs,cards}[state.scope];}
function selectedRecord(){return collection().find(r=>r.id===state.selected);}
function queryRows(){
  if(state.scenario==='empty')return [];
  return collection().filter(r=>{
    const m=materialOf(r);
    return (!state.category||m.category===state.category)&&(!state.materialId||m.id===state.materialId)
      &&(!state.specimen||r.specimen===state.specimen)
      &&(!state.query||`${r.name} ${r.code} ${m.name}`.toLowerCase().includes(state.query.toLowerCase()))
      &&(state.scope!=='tests'||(!state.temp||r.temp===Number(state.temp))&&(!state.rate||r.rate===Number(state.rate)))
      &&(!state.available||state.scope!=='cards'||r.available);
  }).sort((a,b)=>(state.sort==='id'?a.code:a.name).localeCompare(state.sort==='id'?b.code:b.name,'ko',{numeric:true}));
}
function writeURL(){
  const p=new URLSearchParams();
  for(const k of ['scope','view','category','materialId','specimen','query','temp','rate','available','page','selected','sort'])if(state[k])p.set(k,state[k]);
  if(state.expanded)p.set('detail','1');
  if(state.selected&&!state.previewOpen)p.set('preview','closed');
  history.replaceState(null,'',`${location.pathname}?${p}`);
}
function restoreURL(){
  const p=new URLSearchParams(location.search);
  for(const k of ['scope','view','category','materialId','specimen','query','temp','rate','available','selected','sort'])if(p.has(k))state[k]=p.get(k);
  if(!scopes[state.scope])state.scope='materials';
  if(!['tiles','table'].includes(state.view))state.view='table';
  state.page=Math.max(1,Number(p.get('page'))||1);state.expanded=p.get('detail')==='1';
  if(!collection().some(r=>r.id===state.selected)){state.selected=null;state.expanded=false;}
  state.previewOpen=!!state.selected&&p.get('preview')!=='closed';
  if(state.selected){const index=queryRows().findIndex(r=>r.id===state.selected);if(index<0)resetSelection();else state.page=Math.floor(index/12)+1;}
}
function resetSelection(){state.selected=null;state.previewOpen=false;state.expanded=false;state.checked.clear();}
function changeScope(scope,materialId=''){
  state.scope=scope;state.materialId=materialId;state.specimen='';state.category='';state.query='';state.temp='';state.rate='';state.available='';state.page=1;
  state.view=scope==='materials'?'tiles':'table';resetSelection();showTask('browse');render();
}
function showTask(task){
  for(const id of ['browse','process','intake'])$('#'+id).hidden=id!==task;
  document.querySelectorAll('[data-task]').forEach(b=>b.classList.toggle('active',b.dataset.task===task));
  if(task==='process')renderProcess();
}
function renderTree(){
  const previous=new Map([...$('#tree').querySelectorAll('details')].map(el=>[el.querySelector('summary').textContent,el.open]));
  const treeScroll=$('.explorer').scrollTop;
  const node=(label,attrs,active,count)=>`<button ${attrs} class="${active?'active':''}" aria-pressed="${active}"><span>${esc(label)}</span><span class="tree-count">${count}</span></button>`;
  $('#tree').innerHTML=node('전체 소재','data-category=""',!state.category&&!state.materialId,materials.length)+['금속','고분자'].map(parent=>`<details open><summary>${parent}</summary><div class="branch">${groups.filter(g=>g.parent===parent).map(g=>`<details ${parent==='금속'?'open':''}><summary>${g.name}</summary>${node(`${g.name} 전체`,`data-category="${g.id}"`,state.category===g.id,8)}${materials.filter(m=>m.category===g.id).map(m=>`<details ${m.id===state.materialId?'open':''}><summary class="material-node">${m.code}</summary>${node('소재 정보',`data-material="${m.id}"`,state.materialId===m.id&&state.scope==='materials','')}${tests.filter(t=>t.materialId===m.id).map(t=>node(t.specimen,`data-specimen="${t.specimen}" data-mat="${m.id}"`,state.specimen===t.specimen,'')).join('')}</details>`).join('')}</details>`).join('')}</div></details>`).join('');
  $('#tree').querySelectorAll('details').forEach(el=>{const key=el.querySelector('summary').textContent;if(previous.has(key))el.open=previous.get(key);});
  $('.explorer').scrollTop=treeScroll;
}
function materialProperties(m){return [['밀도',m.density.toLocaleString('en-US'),'kg/m³'],['탄성계수',m.modulus.toFixed(1),'GPa'],['포아송비',m.nu.toFixed(2),'—'],['항복강도',m.yield,'MPa'],['인장강도',m.strength,'MPa']];}
function properties(m){return `<dl class="property-list">${materialProperties(m).map(([k,v,u])=>`<div class="property-row"><dt>${k}</dt><dd>${v}</dd><dd class="unit">${u}</dd></div>`).join('')}</dl>`;}
function materialTiles(rows){return `<div class="tiles">${rows.map(m=>`<article class="material-tile ${state.selected===m.id?'selected':''}" data-select="${m.id}" tabindex="0" aria-label="${esc(m.name)} 선택"><header><div class="identity">${m.code} <span>· ${m.parent}</span></div><h2>${esc(m.name)}</h2><span class="small">${m.state}</span></header>${properties(m)}<footer><span>23 °C · 소재 정보 r${m.revision}</span><button data-select="${m.id}">미리보기 →</button></footer></article>`).join('')}</div>`;}
function dataTable(rows){
  const columns={materials:['소재명','상태','밀도<br>kg/m³','탄성계수<br>GPa','인장강도<br>MPa'],tests:['선택','실험 데이터','시편','온도<br>°C','속도<br>s⁻¹','방향','파일'],results:['처리 데이터·모델','종류','입력 실험','저장 상태'],cards:['솔버 카드','솔버','모델','단위계','파일']};
  return `<table class="data-table ${state.scope==='tests'?'test-table':''}"><thead><tr>${columns[state.scope].map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>{
    const m=materialOf(r);const name=`<td><span class="row-name">${esc(r.name)}</span><small>${esc(r.code)}</small></td>`;
    let cells=state.scope==='materials'?name+`<td>${m.state}</td><td class="numeric">${m.density.toLocaleString('en-US')}</td><td class="numeric">${m.modulus.toFixed(1)}</td><td class="numeric">${m.strength}</td>`:
      state.scope==='tests'?`<td><input type="checkbox" data-check="${r.id}" aria-label="${esc(r.code)} 처리 대상으로 선택" ${state.checked.has(r.id)?'checked':''}></td>`+name+`<td>${r.specimen}</td><td class="numeric">${r.temp}</td><td class="numeric">${r.rate}</td><td>${r.direction}</td><td>raw CSV</td>`:
      state.scope==='cards'?name+`<td>${r.solver}</td><td>${r.model}</td><td>${r.units}</td><td>${r.available?'다운로드 가능':'파일 없음'}</td>`:
      name+`<td>${r.type}</td><td class="numeric">${r.members.length}회</td><td>저장됨</td>`;
    return `<tr data-select="${r.id}" tabindex="0" class="${state.selected===r.id?'selected':''}" aria-label="${esc(r.name)} 선택">${cells}</tr>`;
  }).join('')}</tbody></table>`;
}
function renderResults(){
  const rows=queryRows();lastRows=rows;state.page=Math.min(state.page,Math.max(1,Math.ceil(rows.length/12)));
  const slice=rows.slice((state.page-1)*12,state.page*12);const m=materials.find(m=>m.id===state.materialId);
  $('#page-title').textContent=scopes[state.scope];$('#total').textContent=`${rows.length.toLocaleString()}건`;
  $('#breadcrumb').textContent=m?`소재 / ${m.code} / ${m.name}`:state.category?`전체 소재 / ${groups.find(g=>g.id===state.category)?.name||''}`:'전체 데이터베이스';
  $('#search').value=state.query;$('#search').placeholder=`${scopes[state.scope]} 이름 또는 식별자로 검색`;
  for(const [id,key] of [['temperature','temp'],['rate','rate'],['availability','available'],['sort','sort']])$('#'+id).value=state[key];
  $('#temperature').disabled=$('#rate').disabled=state.scope!=='tests';$('#availability').disabled=state.scope!=='cards';
  $('#view-switch').hidden=state.scope!=='materials';
  document.querySelectorAll('[data-scope]').forEach(b=>b.classList.toggle('active',b.dataset.scope===state.scope));
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===state.view)));
  $('#result-content').innerHTML=state.scenario==='error'?`<div class="empty-state"><h2>목록을 불러오지 못했습니다</h2><p>검색 조건은 유지했습니다. 다시 시도해주세요.</p><button class="primary" data-retry>다시 시도</button></div>`:
    !rows.length?`<div class="empty-state"><h2>조건에 맞는 데이터가 없습니다</h2><p>검색어나 선택한 조건을 줄여보세요.</p><button data-reset>조건 초기화</button></div>`:
    state.scope==='materials'&&state.view==='tiles'?materialTiles(slice):dataTable(slice);
  const failed=state.scenario==='error';$('#total').hidden=failed;$('#range').textContent=failed?'조회 실패':rows.length?`${(state.page-1)*12+1}–${Math.min(state.page*12,rows.length)} / ${rows.length}건`:'0건';
  $('#page-count').textContent=failed?'—':`${state.page} / ${Math.max(1,Math.ceil(rows.length/12))}`;
  $('#previous').disabled=failed||state.page===1;$('#next').disabled=failed||state.page*12>=rows.length;
  updateChecked();
}
function updateChecked(){const b=$('#process-selected');b.hidden=state.scope!=='tests'||!state.checked.size;b.textContent=`선택한 ${state.checked.size}개 처리`;}
function section(title,body){return `<section><h3 class="section-title">${title}</h3>${body}</section>`;}
function relatedList(m,scope,label){const rows={tests,cards,results:outputs}[scope].filter(r=>r.materialId===m.id);return `<button class="linked-item" data-related="${scope}" data-mat="${m.id}"><span><strong>${label}</strong><small>${scope==='tests'?'시편 · 온도 · 속도별로 보기':scope==='cards'?'저장된 파일과 적용 범위 확인':'실험에서 만든 결과와 모델'}</small></span><span>${rows.length} →</span></button>`;}
function materialDetail(m){
  return `<div class="record-code">${m.code} · 소재 정보 r${m.revision}</div><h2>${esc(m.name)}</h2><p class="small">${m.state}</p><div class="detail-tabs" role="group" aria-label="소재 상세 정보">${[['properties','물성'],['tests','실험'],['results','처리·모델'],['cards','솔버 카드']].map(([key,label])=>`<button data-tab="${key}" class="${state.previewTab===key?'active':''}">${label}</button>`).join('')}</div>`+
    (state.previewTab==='properties'?`<div class="detail-columns"><div>${section('기본 물성 <span class="small">23 °C</span>',`<table class="detail-table"><thead><tr><th>항목</th><th class="numeric">값</th><th>단위</th></tr></thead><tbody>${materialProperties(m).map(([k,v,u])=>`<tr><td>${k}</td><td class="numeric">${v}</td><td>${u}</td></tr>`).join('')}</tbody></table>`)}${section('소재 상태',`<dl class="fact-grid"><dt>형태·제조 상태</dt><dd>${m.state}</dd><dt>로트</dt><dd>${m.lot}</dd><dt>물성 적용 조건</dt><dd>23 °C · 검토용 값</dd></dl>`)}</div><div>${section('연결된 데이터',`<div class="linked-items">${relatedList(m,'tests','실험 데이터')}${relatedList(m,'results','처리 데이터·모델')}${relatedList(m,'cards','솔버 카드')}</div>`)}${section('인장 응답',`<div class="plot" data-plot="${tests.find(t=>t.materialId===m.id).id}"></div><div class="plot-key"><span>실험 01 · 23 °C</span></div><p class="small">공칭 응력–공칭 변형률 · 합성 실험</p>`)}</div></div>`:
      `<div class="linked-items">${relatedList(m,state.previewTab,scopes[state.previewTab])}</div><p class="small" style="margin-top:16px">소재 연결을 유지한 채 목록을 열어 조건별로 비교합니다.</p>`);
}
function testDetail(t){const m=materialOf(t);return `<div class="record-code">${t.code}</div><h2>${esc(t.name)}</h2><p class="small">${m.name} · ${t.specimen}</p><div class="detail-columns"><div>${section('시험 조건',`<dl class="fact-grid"><dt>시험</dt><dd>인장</dd><dt>온도</dt><dd>${t.temp} °C</dd><dt>변형률 속도</dt><dd>${t.rate} s⁻¹</dd><dt>방향</dt><dd>${t.direction}</dd><dt>데이터 구분</dt><dd>원본 실험 데이터</dd></dl>`)}${section('원본 파일',`<p class="small">${t.file}</p><p class="small">합성 자료 · 원본 다운로드는 API 연결 단계에서 검증</p>`)}<div class="detail-footer"><button data-open-material="${m.id}">소재 정보</button><button data-related="cards" data-mat="${m.id}">소재의 솔버 카드</button><button class="primary" data-process-material="${m.id}">반복 실험 처리 시안</button></div></div><div>${section('응력–변형률 곡선',`<div class="plot" data-plot="${t.id}"></div><div class="plot-key"><span>${t.specimen}</span></div>`)}</div></div>`;}
function cardDetail(c){const m=materialOf(c);return `<div class="record-code">${c.code}</div><h2>${esc(c.name)}</h2><p class="small">${m.name}</p><div class="detail-columns"><div>${section('출력 정보',`<dl class="fact-grid"><dt>솔버</dt><dd>${c.solver}</dd><dt>모델</dt><dd>${c.model}</dd><dt>단위계</dt><dd>${c.units}</dd><dt>적용 범위</dt><dd>선형 탄성 · 검토용</dd><dt>검증 상태</dt><dd>해석 검증 전 합성 예시</dd></dl>`)}${section('연결',`<button data-open-material="${m.id}">소재 정보 보기</button><p class="small" style="margin-top:10px">이 카드의 소재 연결입니다. 동일 소재의 모든 실험이 카드 생성에 사용된 것은 아닙니다.</p>`)}</div><div>${section('파일 미리보기',c.available?`<pre class="native">${esc(c.content)}</pre><div class="detail-footer"><button class="primary" data-download-card="${c.id}">예시 카드 다운로드</button></div>`:`<div class="notice">이 검토 자료에는 카드 파일이 없습니다. 기존 파일 확인·연결이 필요합니다.</div><button disabled style="margin-top:16px">다운로드할 파일 없음</button>`)}</div></div>`;}
function outputDetail(r){return `<div class="record-code">${r.code}</div><h2>${r.name}</h2><p class="small">통계 데이터 · 저장된 예시</p>${section('사용한 실험',`<div class="linked-items">${r.members.map(id=>{const t=tests.find(x=>x.id===id);return `<button class="linked-item" data-open-test="${id}"><span>${t.code}</span><span>${t.temp} °C →</span></button>`;}).join('')}</div>`)}${section('대표 데이터',`<dl class="fact-grid"><dt>구간</dt><dd>관측 공통 구간</dd><dt>격자</dt><dd>151점 · 선형 보간</dd><dt>산포</dt><dd>표준편차 · 최소·최대</dd><dt>출력 의미</dt><dd>처리 데이터 · 솔버 카드 아님</dd></dl><div class="detail-footer"><button class="primary" data-download-stored="${r.id}">저장된 처리 데이터 CSV</button><button data-process-material="${r.materialId}">새 처리 시작</button></div>`)}`;}
function renderPreview(){
  $('#preview').dataset.scope=state.scope;
  const r=selectedRecord();const shown=!!r&&state.previewOpen&&state.scenario==='normal';$('#preview').hidden=!shown;
  $('#reader').classList.toggle('has-preview',shown);$('#reader').classList.toggle('expanded',shown&&state.expanded);
  $('#expand').hidden=state.expanded;$('#collapse').hidden=state.expanded;$('#return').hidden=!state.expanded;
  $('#preview-mode').textContent=state.expanded?'상세 보기':'미리보기';
  if(!shown){$('#preview-content').innerHTML='';return;}
  $('#preview-content').innerHTML=state.scope==='materials'?materialDetail(r):state.scope==='tests'?testDetail(r):state.scope==='cards'?cardDetail(r):outputDetail(r);
  drawPlots();
}
function render(){renderTree();renderResults();renderPreview();writeURL();}
function select(id,focus){state.selected=id;state.previewOpen=true;state.previewTab='properties';state.focus=focus||`[data-select="${id}"]`;state.expanded=false;document.querySelectorAll('[data-select]').forEach(el=>el.classList.toggle('selected',el.dataset.select===id));renderPreview();writeURL();$('#announce').textContent=`${selectedRecord()?.name} 미리보기`;
}
function expand(){if(!state.selected)return;state.scroll=$('#result-scroll').scrollTop;state.expanded=true;renderPreview();writeURL();$('#return').focus();}
function returnToList(){state.expanded=false;if(innerWidth<=760)state.previewOpen=false;renderPreview();$('#result-scroll').scrollTop=state.scroll;document.querySelector(state.focus||'[data-select]')?.focus({preventScroll:true});writeURL();}
function openRecord(scope,id){changeScope(scope);state.selected=id;state.previewOpen=true;state.expanded=true;state.scroll=0;state.page=Math.floor(queryRows().findIndex(r=>r.id===id)/12)+1;renderResults();state.focus=`[data-select="${id}"]`;renderPreview();writeURL();}
function download(name,content,type='text/plain'){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

function curve(t){const m=materialOf(t);const yieldX=m.yield/(m.modulus*10);const xs=[...new Set([0,yieldX/2,yieldX,...Array.from({length:76},(_,i)=>t.end*i/75)])].sort((a,b)=>a-b);return xs.map(x=>{const y=x<yieldX?x*m.modulus*10:m.yield+(m.strength-m.yield)*(1-Math.exp(-(x-yieldX)*.23));return [x,y*t.factor];});}
// The drawing uses real container dimensions, so axes and text never stretch with a viewBox.
function plot(el,series,result=null){
  if(!series.length){el.innerHTML='<div class="empty-state">선택한 실험이 없습니다</div>';return;}
  const w=Math.max(220,el.clientWidth),h=Math.max(180,el.clientHeight),font=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--small'));
  const left=font*4.3,right=20,top=font*2.1,bottom=font*3.4;const pw=w-left-right,ph=h-top-bottom;
  const xmax=Math.max(...series.map(s=>s.points.at(-1)[0]));const maxY=Math.max(...series.flatMap(s=>s.points.map(p=>p[1])));const ymax=Math.ceil(maxY/100)*100;
  const x=v=>left+v/xmax*pw,y=v=>top+ph-v/ymax*ph;let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" role="img" aria-label="공칭 응력 MPa와 공칭 변형률 퍼센트 곡선" style="font-family:Segoe UI,Malgun Gothic,sans-serif;font-size:${font}px">`;
  for(let i=0;i<=4;i++){const v=ymax*i/4;svg+=`<line x1="${left}" x2="${w-right}" y1="${y(v)}" y2="${y(v)}" stroke="#e1e6eb" stroke-width="1"/><text x="${left-10}" y="${y(v)+font*.35}" text-anchor="end" fill="#637182">${v}</text>`;}
  for(let i=0;i<=4;i++){const v=xmax*i/4;svg+=`<line x1="${x(v)}" x2="${x(v)}" y1="${top}" y2="${h-bottom}" stroke="#edf0f3"/><text x="${x(v)}" y="${h-bottom+font*1.55}" text-anchor="middle" fill="#637182">${Number(v.toFixed(2))}</text>`;}
  svg+=`<line x1="${left}" x2="${w-right}" y1="${h-bottom}" y2="${h-bottom}" stroke="#82909e"/><line x1="${left}" x2="${left}" y1="${top}" y2="${h-bottom}" stroke="#82909e"/><text x="${left}" y="${font}" fill="#475867">공칭 응력 [MPa]</text><text x="${left+pw/2}" y="${h-5}" text-anchor="middle" fill="#475867">공칭 변형률 [%]</text>`;
  if(result){const pts=result.rows.map(v=>[v.x,v.mean,v.sd]);svg+=`<path d="M${pts.map(p=>`${x(p[0])},${y(p[1]+p[2])}`).join(' L')} L${pts.toReversed().map(p=>`${x(p[0])},${y(p[1]-p[2])}`).join(' L')} Z" fill="#e0e8f1"/>`;series=[...series,{points:pts.map(p=>[p[0],p[1]]),color:'#295f91',thick:true}];}
  for(const s of series)svg+=`<path d="M${s.points.map(p=>`${x(p[0]).toFixed(2)},${y(p[1]).toFixed(2)}`).join(' L')}" stroke="${s.color||'#356791'}" stroke-width="${s.thick?2.4:1.5}" fill="none"/>`;
  el.innerHTML=svg+'</svg>';
}
function interpolate(points,x){const index=points.findIndex(p=>p[0]>=x);if(index===0)return points[0][1];if(index<0)throw Error('Out of observed range');const a=points[index-1],b=points[index];return a[1]+(b[1]-a[1])*(x-a[0])/(b[0]-a[0]);}
function drawPlots(){document.querySelectorAll('[data-plot]').forEach(el=>{const t=tests.find(t=>t.id===el.dataset.plot);if(t)plot(el,[{points:curve(t)}]);});const p=$('#process-plot');if(p){const r=processState.result;const ids=r?r.members:processState.members;plot(p,ids.map((id,i)=>({points:curve(tests.find(t=>t.id===id)),color:['#b1bbc6','#7d96aa','#8a9b97'][i%3]})),r);}}
new ResizeObserver(()=>requestAnimationFrame(drawPlots)).observe($('#reader'));
window.addEventListener('resize',()=>requestAnimationFrame(drawPlots));

function processValid(){const ts=processState.members.map(id=>tests.find(t=>t.id===id));return ts.length>=2&&ts.every(t=>t.materialId===ts[0].materialId&&t.temp===ts[0].temp&&t.rate===ts[0].rate);}
function markProcessChanged(){if(processState.result)processState.stale=true;processState.saved=false;processState.error=false;renderProcess();}
function renderProcess(){
  const m=materialOf(tests.find(t=>t.id===processState.members[0])||tests[0]);const available=tests.filter(t=>t.materialId===m.id||processState.members.includes(t.id));const valid=processValid();const r=processState.result;
  $('#process').innerHTML=`<div class="breadcrumb">${m.code} / 실험 데이터 / 처리·통계</div><div class="process-heading"><h1>반복 실험 대표 데이터</h1><button data-related="tests" data-mat="${m.id}">‹ 실험 목록</button></div><div class="process-grid"><aside class="process-inputs"><h2>1. 실험 선택</h2><p class="small" style="margin-top:8px">${m.name}</p>${available.map(t=>`<label class="replicate"><input type="checkbox" data-member="${t.id}" ${processState.members.includes(t.id)?'checked':''}><span>${t.code}<br><span class="muted">${t.temp} °C · ${t.rate} s⁻¹</span></span></label>`).join('')}<h2 style="margin-top:24px">2. 정렬·통계</h2><dl class="fact-grid"><dt>기본 구간</dt><dd>모두 관측된 구간</dd><dt>보간</dt><dd>선형</dd><dt>외삽</dt><dd>사용하지 않음</dd></dl><details><summary>고급 설정</summary><label>공통 격자점 수<input id="points" type="number" min="10" max="1000" value="${processState.points}"></label><p class="small">이 시안의 범위는 10–1,000점입니다. 실제 허용 범위와 기본값은 수치 검증 후 결정합니다.</p></details><p class="small" style="margin:20px 0 12px">합성 자료로 흐름을 확인하는 계산 예시입니다.</p><button class="primary" id="calculate" ${valid?'':'disabled'}>예시 결과 계산</button>${!valid?'<p class="small" style="margin-top:10px">동일 소재·온도·속도의 실험을 2개 이상 선택해주세요.</p>':''}</aside><section class="process-output"><div class="result-head"><h2>3. 결과 확인</h2><span class="small">${processState.stale?'입력 변경됨':processState.saved?'브라우저에 예시 저장됨':r?'계산됨 · 저장 전':'계산 전'}</span></div>${processState.stale?'<div class="notice error-notice">입력이 바뀌었습니다. 아래는 이전 입력의 결과이며 현재 결과로 저장·다운로드할 수 없습니다. 다시 계산해주세요.</div>':''}${processState.error?'<div class="notice error-notice">선택한 입력으로 결과를 만들지 못했습니다. 실험과 격자 설정을 확인한 뒤 다시 계산해주세요.</div>':''}<div class="plot" id="process-plot"></div><div class="plot-key"><span style="--key:#8b9bac">개별 실험</span>${r?'<span>평균</span><span class="band">평균 ± 표준편차</span>':''}</div><p class="small">관측 공통 구간에서 계산합니다. 먼저 파단된 실험 이후를 연장하지 않습니다.</p>${r?`<div class="summary-grid"><div><span class="small">독립 실험 수</span><b>${r.members.length}회</b></div><div><span class="small">공통 변형률 구간</span><b>0–${r.end} %</b></div><div><span class="small">공통 격자</span><b>${r.rows.length}점</b></div></div><table><thead><tr><th>공칭 변형률 %</th><th class="numeric">평균 MPa</th><th class="numeric">표준편차 MPa</th><th class="numeric">최소 MPa</th><th class="numeric">최대 MPa</th><th>n</th></tr></thead><tbody>${[0,Math.floor(r.rows.length/2),r.rows.length-1].map(i=>{const a=r.rows[i];return `<tr><td>${a.x.toFixed(2)}</td><td class="numeric">${a.mean.toFixed(2)}</td><td class="numeric">${a.sd.toFixed(2)}</td><td class="numeric">${a.min.toFixed(2)}</td><td class="numeric">${a.max.toFixed(2)}</td><td>${a.n}</td></tr>`;}).join('')}</tbody></table><div class="detail-footer"><button id="save-result" class="primary" ${processState.stale?'disabled':''}>예시 결과 저장</button><button id="download-result" ${processState.stale?'disabled':''}>처리 데이터 CSV</button><span class="small">솔버 카드 파일과 별개입니다.</span></div>`:'<div class="notice">실험과 설정을 확인하고 예시 결과를 계산해주세요. 계산 결과는 저장하기 전까지 임시 결과입니다.</div>'}<p class="small" style="margin-top:18px">관측 최소·최대와 산포를 제공합니다. 설계 허용 하한이나 95% 신뢰구간은 이 시안에서 제공하지 않습니다.</p></section></div>`;
  drawPlots();
}
function statistics(members,count){
  const series=members.map(id=>curve(tests.find(t=>t.id===id)));const end=Math.min(...series.map(s=>s.at(-1)[0]));const rows=Array.from({length:count},(_,i)=>{const x=end*i/(count-1),values=series.map(s=>interpolate(s,x)),mean=values.reduce((a,b)=>a+b,0)/values.length;return {x,mean,sd:Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/(values.length-1)),min:Math.min(...values),max:Math.max(...values),n:values.length};});
  return {members:[...members],points:count,end,rows};
}
function calculate(){const count=processState.points;if(!processValid()||!Number.isInteger(count)||count<10||count>1000){processState.error=true;renderProcess();return;}
  processState.result=statistics(processState.members,count);processState.stale=false;processState.saved=false;processState.error=false;renderProcess();
}
const storedStatistics=statistics(outputs[0].members,151);
function downloadStatistics(r){download('synthetic-processed-statistics.csv','engineering_strain_percent,mean_MPa,sd_MPa,min_MPa,max_MPa,n\n'+r.rows.map(v=>[v.x,v.mean,v.sd,v.min,v.max,v.n].join(',')).join('\n'),'text/csv');}
function startProcessing(materialId){processState.members=tests.filter(t=>t.materialId===materialId&&t.temp===23).map(t=>t.id);processState.result=null;processState.saved=false;processState.stale=false;showTask('process');}

document.addEventListener('click',event=>{
  const b=event.target.closest('button');const row=event.target.closest('[data-select]');
  if(event.target.closest('[data-check]'))return;
  if(b?.dataset.task){showTask(b.dataset.task);return;}
  if(b?.dataset.scope){changeScope(b.dataset.scope);return;}
  if(b?.dataset.view){state.scroll=$('#result-scroll').scrollTop;state.view=b.dataset.view;renderResults();$('#result-scroll').scrollTop=state.scroll;writeURL();return;}
  if(b?.hasAttribute('data-category')){state.category=b.dataset.category;state.materialId='';state.specimen='';state.page=1;resetSelection();render();return;}
  if(b?.dataset.material){changeScope('materials',b.dataset.material);return;}
  if(b?.dataset.specimen){changeScope('tests',b.dataset.mat);state.specimen=b.dataset.specimen;render();return;}
  if(b?.dataset.related){changeScope(b.dataset.related,b.dataset.mat);return;}
  if(b?.dataset.tab){state.previewTab=b.dataset.tab;renderPreview();return;}
  if(b?.dataset.openMaterial){openRecord('materials',b.dataset.openMaterial);return;}
  if(b?.dataset.openTest){openRecord('tests',b.dataset.openTest);return;}
  if(b?.dataset.processMaterial){startProcessing(b.dataset.processMaterial);return;}
  if(b?.dataset.downloadStored){downloadStatistics(storedStatistics);return;}
  if(b?.dataset.downloadCard){const c=cards.find(c=>c.id===b.dataset.downloadCard);if(c?.available)download(`${c.code}.k`,c.content);return;}
  if(b?.hasAttribute('data-retry')){state.scenario='normal';$('#scenario').value='normal';render();return;}
  if(b?.hasAttribute('data-reset')||b?.id==='reset'){Object.assign(state,{category:'',materialId:'',specimen:'',query:'',temp:'',rate:'',available:'',page:1,scenario:'normal'});$('#scenario').value='normal';resetSelection();render();return;}
  if(b?.id==='expand'){expand();return;}if(b?.id==='return'){returnToList();return;}
  if(b?.id==='collapse'){state.previewOpen=false;state.expanded=false;renderPreview();document.querySelector(state.focus||'[data-select]')?.focus({preventScroll:true});writeURL();return;}
  if(b?.id==='previous'||b?.id==='next'){state.page+=b.id==='next'?1:-1;resetSelection();render();$('#result-scroll').scrollTop=0;return;}
  if(b?.id==='process-selected'){processState.members=[...state.checked];processState.result=null;processState.stale=false;processState.saved=false;processState.error=false;showTask('process');return;}
  if(b?.id==='calculate'){calculate();return;}
  if(b?.id==='save-result'&&!processState.stale){try{sessionStorage.setItem('cae-review-statistics',JSON.stringify(processState.result));processState.saved=true;renderProcess();}catch{processState.error=true;renderProcess();}return;}
  if(b?.id==='download-result'&&!processState.stale){downloadStatistics(processState.result);return;}
  if(row){select(row.dataset.select,`[data-select="${row.dataset.select}"]`);}
});
document.addEventListener('dblclick',event=>{const row=event.target.closest('[data-select]');if(row&&!event.target.closest('input'))expand();});
document.addEventListener('keydown',event=>{const row=event.target.closest('[data-select]');if(row&&event.key==='Enter'&&!event.target.closest('input')){event.preventDefault();select(row.dataset.select);expand();}if(event.key==='Escape'&&state.selected){if(state.expanded)returnToList();else $('#collapse').click();}});
document.addEventListener('change',event=>{
  const t=event.target;if(t.dataset.check){if(t.checked)state.checked.add(t.dataset.check);else state.checked.delete(t.dataset.check);updateChecked();}
  if(t.dataset.member){if(t.checked)processState.members.push(t.dataset.member);else processState.members=processState.members.filter(id=>id!==t.dataset.member);markProcessChanged();}
  if(t.id==='points'){processState.points=Number(t.value);markProcessChanged();}
  if(t.id==='scenario'){state.scenario=t.value;resetSelection();render();}
  if(t.id==='sort'){state.sort=t.value;state.page=1;resetSelection();render();}
  if(t.id==='input-file')$('#file-name').textContent=t.files[0]?.name||'선택된 파일 없음';
});
$('#search-form').addEventListener('submit',e=>{e.preventDefault();state.query=$('#search').value;state.page=1;resetSelection();render();});
$('#filters').addEventListener('submit',e=>{e.preventDefault();state.temp=$('#temperature').value;state.rate=$('#rate').value;state.available=$('#availability').value;state.page=1;resetSelection();render();});
$('#intake-form').addEventListener('submit',e=>{e.preventDefault();$('#intake-next').hidden=false;});
window.addEventListener('popstate',()=>{restoreURL();render();});
restoreURL();render();

// Reopen only this tab's explicitly saved review result; never imply server persistence.
try{const saved=JSON.parse(sessionStorage.getItem('cae-review-statistics'));if(saved&&Array.isArray(saved.members)&&saved.members.length>=2&&saved.members.every(id=>tests.some(t=>t.id===id))&&Number.isInteger(saved.points)&&saved.points>=10&&saved.points<=1000&&Array.isArray(saved.rows)&&saved.rows.length===saved.points){Object.assign(processState,{members:saved.members,points:saved.points,result:saved,saved:true});}}catch{}
