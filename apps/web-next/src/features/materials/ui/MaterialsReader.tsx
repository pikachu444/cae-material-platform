import { MaterialsTable } from "./MaterialsTable";
import { materialClassLabel } from "../../../shared/model/engineering-labels";
import { ReaderPreviewHeader } from "../../../shared/ui/ReaderPreviewHeader";
import * as React from "react";
import { ReaderSearch } from "../../../shared/ui/ReaderSearch";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { listMaterials, readMaterial, type MaterialDetail, type MaterialRow } from "../api";
import { listTestData, type TestDataRow } from "../../test-data/api";
import { authorizationScopeKey } from "../../../shared/api/http-client";
import { ReaderState } from "../../../shared/ui/ReaderState";
import { ReaderWorkspace, ReaderResultHeader, ReaderListError } from "../../../shared/ui/ReaderWorkspace";
import { useReaderReturnFocus } from "../../../shared/ui/useReaderReturnFocus";
import { MaterialProperties } from "./MaterialProperties";
import { MaterialCard } from "./MaterialCard";
import cardStyles from "./MaterialCard.module.css";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

const PAGE_SIZE = 12;
export function MaterialsReader() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const [searchDraft, setSearchDraft] = React.useState(query);
  React.useEffect(() => setSearchDraft(query), [query]);
  const materialClass = params.get("class") ?? "";
  const sortBy = params.get("sort") === "material_class" ? "material_class" : "name";
  const sortDirection = params.get("direction") === "descending" ? "descending" : "ascending";
  const page = Math.max(0, Number(params.get("page")) || 0);
  const selectedId = params.get("id");
  const expanded = params.get("expanded") === "1";
  const previewClosed = params.get("preview") === "closed";
  const detailTab = params.get("detail_tab") ?? "properties";
  const view = params.get("view") === "table" ? "table" : "cards";
  const rememberReturn = useReaderReturnFocus(expanded, previewClosed);
  const auth = authorizationScopeKey();
  const list = useQuery({ queryKey: ["connected-materials", auth, query, materialClass, page, sortBy, sortDirection],
    queryFn: ({ signal }) => listMaterials({ query, materialClass: materialClass || undefined, offset: page * PAGE_SIZE, limit: PAGE_SIZE, sortBy, sortDirection }, signal) });
  const rows = list.data?.items ?? [];
  const details = useQueries({ queries: rows.map(row => ({ queryKey: ["connected-material-detail", auth, row.id], queryFn: ({ signal }: { signal: AbortSignal }) => readMaterial(row.id, signal) })) });
  const detail = useQuery({ queryKey: ["connected-material-detail", auth, selectedId], queryFn: ({ signal }) => readMaterial(selectedId!, signal), enabled: Boolean(selectedId) });
  const tests = useQuery({ queryKey: ["connected-test-data", auth], queryFn: ({ signal }) => listTestData(signal) });
  const update = (changes: Record<string, string | null>, close = false) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) value ? next.set(key, value) : next.delete(key);
    if (close) { next.delete("id"); next.delete("expanded"); next.delete("preview"); }
    setParams(next);
  };
  const select = (row: MaterialRow, open = false) => { if (open) rememberReturn(row.id); update({ preview: null, id: row.id, expanded: open ? "1" : null }); };
  const total = list.data?.totalCount ?? 0;
  const selected = detail.data?.material ?? rows.find(row => row.id === selectedId);
  const result = list.isError ? <ReaderListError title="소재 목록을 불러올 수 없습니다" description={list.error.message} onAction={() => void list.refetch()} /> : <section className={styles.panel} aria-labelledby="materials-results-heading">
    <ReaderResultHeader headingId="materials-results-heading"><span className={styles.muted}>{total}건</span></ReaderResultHeader>
    {!rows.length ? <div className={styles.empty}>조건에 맞는 소재가 없습니다.</div> : view === "cards" ?
      <div className={cardStyles.grid} data-reader-scroll="connected">{rows.map((row, index) =>
        <MaterialCard key={row.id} material={row} detail={details[index]?.data} failed={details[index]?.isError ?? false}
          selected={selectedId === row.id} onSelect={expanded => select(row, expanded)} />
      )}</div> : <MaterialsTable rows={rows} details={details} selectedId={selectedId} onSelect={select} />}
    <div className={styles.pagination}><span>{total ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} / ${total}` : "0건"}</span><div className={styles.actions}>
      <button className={styles.button} disabled={page === 0} onClick={() => update({ page: String(page - 1) }, true)}>이전</button>
      <button className={styles.button} disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => update({ page: String(page + 1) }, true)}>다음</button>
    </div></div>
  </section>;
  const preview = selectedId ? <section className={expanded ? styles.expandedPanel : styles.previewPanel} aria-labelledby={expanded ? "material-detail-heading" : "material-preview-heading"}>
    {expanded ? <div className={styles.panelHeading}>
      <div><h2 id="material-detail-heading">{selected?.name ?? "소재"}</h2></div>
      <button className={styles.button} onClick={() => update({ expanded: null })}>‹ 목록 보기</button>
    </div> : <ReaderPreviewHeader headingId="material-preview-heading" title={selected?.name ?? "소재"}
      closeLabel="소재 미리보기 접기"
      onClose={() => { if (selectedId) rememberReturn(selectedId); update({ preview: "closed" }); }} onExpand={() => selected && select(selected, true)} disabled={!detail.data} />}
    <div className={styles.panelBody}>{detail.isError ? <ReaderState tone="error" title="소재를 불러올 수 없습니다" description={detail.error.message} onAction={() => void detail.refetch()} /> : detail.data ? <>
      <nav className={styles.detailTabs} aria-label="소재 연결 자료">{[["properties", "물성"], ["tests", "실험"], ["models", "처리·모델"], ["cards", "솔버 카드"]].map(([key,label]) => <button key={key} aria-pressed={detailTab === key} className={detailTab === key ? styles.detailTabActive : ""} onClick={() => update({ detail_tab:key })}>{label}</button>)}</nav>
      {detailTab === "properties" ? <div className={expanded ? styles.expandedBody : undefined}>
        <div><MaterialProperties detail={detail.data} /></div>
        <section className={styles.section}><h3>연결된 데이터</h3>
          <Link className={styles.linkedItem} to={`/test-data?material=${selectedId}`}>실험 데이터 <span>→</span></Link>
          <button className={styles.linkedItem} onClick={() => update({ detail_tab: "models" })}>처리 데이터·모델 <span>→</span></button>
          <Link className={styles.linkedItem} to={`/cards?material=${selectedId}`}>솔버 카드 <span>→</span></Link>
        </section>
      </div> : null}
      {detailTab === "tests" ? <div className={styles.section}><Link className={styles.link} to={`/test-data?material=${selectedId}`}>이 소재에 연결된 실험 데이터 →</Link></div> : null}
      {detailTab === "models" ? <div className={styles.linkedItems}><h3>소재 상태별 모델</h3>{detail.data.states.map(state => <Link className={styles.link} key={state.id} to={`/models?state_id=${state.id}&state_revision_id=${state.revisionId}`}>{state.name} →</Link>)}<h3>실험별 처리 데이터</h3>{(tests.data ?? []).filter(test => test.materialId === selectedId).map(test => <Link className={styles.link} key={test.id} to={`/processing-outputs?source_document_id=${test.id}&source_document_revision_id=${test.revisionId}`}>{test.documentKey}을 사용한 결과 →</Link>)}{tests.isError ? <p className={styles.muted}>현재 권한으로 입력 실험을 조회할 수 없습니다.</p> : null}</div> : null}
      {detailTab === "cards" ? <div className={styles.section}><Link className={styles.link} to={`/cards?material=${selectedId}`}>이 소재에 연결된 솔버 카드 →</Link></div> : null}
      <section className={styles.section}><h3>소재 정보</h3><dl className={styles.details}><dt>소재 코드</dt><dd>{detail.data.material.code || "미등록"}</dd><dt>분류</dt><dd>{detail.data.material.family || materialClassLabel(detail.data.material.materialClass)}</dd><dt>소재 리비전</dt><dd>r{detail.data.material.revision.revision_no}</dd></dl></section>
    </> : <ReaderState title="소재를 불러오는 중" />}</div>
  </section> : null;
  return <ReaderWorkspace title="소재"
    explorer={<><div className={styles.explorerHeader}><strong>소재 분류</strong></div><div className={styles.explorerSection}>
      {rows.map((row, index) => <MaterialTree key={row.id} row={row} detail={details[index]?.data} tests={tests.data ?? []} testsError={tests.isError} selected={selectedId === row.id} onSelect={() => select(row)} />)}
    </div></>}
    search={<ReaderSearch label="소재 검색" id="material-search" value={searchDraft} onDraftChange={setSearchDraft} placeholder="소재명 또는 식별자로 검색" onSearch={value => update({ q:value, page:"0" }, true)} />} filters={<label>소재 분류<select aria-label="소재 분류" className={styles.select} value={materialClass} onChange={event => update({ class: event.target.value, page: "0" }, true)}><option value="">전체 분류</option>{list.data?.facets.map(facet => <option key={facet.materialClass} value={facet.materialClass}>{materialClassLabel(facet.materialClass)} ({facet.count}건)</option>)}</select></label>} tools={<><select aria-label="소재 정렬" className={styles.select} value={`${sortBy}:${sortDirection}`} onChange={event => { const [sort, direction] = event.target.value.split(":"); update({ sort, direction, page: "0" }, true); }}><option value="name:ascending">이름 오름차순</option><option value="name:descending">이름 내림차순</option><option value="material_class:ascending">분류 오름차순</option><option value="material_class:descending">분류 내림차순</option></select><div className={styles.actions} role="group" aria-label="소재 목록 보기">{(["cards", "table"] as const).map(item => <button key={item} aria-pressed={view === item} className={`${styles.button} ${view === item ? styles.buttonPrimary : ""}`} onClick={() => update({ view: item })}>{item === "cards" ? "카드" : "표"}</button>)}</div>
    </>}>
    {list.isPending && !selectedId ? <ReaderState title="소재를 불러오는 중" /> : list.isError && !selectedId ? <ReaderListError title="소재 목록을 불러올 수 없습니다" description={list.error.message} onAction={() => void list.refetch()} /> : expanded ? preview : selectedId ?
      <div className={`${styles.resultsWithPreview} ${previewClosed ? styles.previewClosed : ""}`}><section className={styles.resultsRegion} data-reader-results="connected">{result}</section>{!previewClosed ? preview : null}</div> : <section className={styles.resultsRegion} data-reader-results="connected">{result}</section>}
  </ReaderWorkspace>;
}

function MaterialTree({ row, detail, tests, testsError, selected, onSelect }: { row: MaterialRow; detail?: MaterialDetail; tests: TestDataRow[]; testsError: boolean; selected: boolean; onSelect: () => void }) {
  return <details className={styles.materialTree} open={selected || undefined}>
    <summary className={styles.treeSummary}><span>{row.name}</span></summary>
    <div className={styles.treeChildren}>
      <button className={styles.linkButton} onClick={onSelect}>물성 보기</button>
      {!detail ? <span className={styles.muted}>소재 상태를 불러오는 중…</span> : detail.states.map(state => {
        const linked = tests.filter(test => test.materialId === row.id && test.materialStateId === state.id && test.materialStateRevisionId === state.revisionId);
        return <details className={styles.treeNode} key={state.id}><summary><span>{state.name}</span></summary><div className={styles.treeChildren}>
          <Link className={styles.link} to={`/models?state_id=${state.id}&state_revision_id=${state.revisionId}`}>모델 →</Link>
          {linked.map(test => <Link className={styles.treeDataLink} key={test.id} to={`/test-data?id=${test.id}&revision_id=${test.revisionId}`}><strong>{test.specimenId || "이름 없는 시편"}</strong><small>{test.documentKey}</small></Link>)}
          {!linked.length ? <span className={styles.muted}>{testsError ? "실험 데이터를 불러올 수 없습니다" : "연결된 실험 데이터 없음"}</span> : null}
        </div></details>;
      })}
    </div>
  </details>;
}
