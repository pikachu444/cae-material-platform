import { useReaderReturnFocus } from "../../../shared/ui/useReaderReturnFocus";
import { ReaderPreviewHeader } from "../../../shared/ui/ReaderPreviewHeader";
import * as React from "react";
import { ReaderSearch } from "../../../shared/ui/ReaderSearch";
import { quantityLabel, unitLabel } from "../../../shared/model/engineering-labels";
import { TestDataTree } from "./TestDataTree";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { useMemo, useState } from "react";
import { downloadTestData, listTestData, readTestData, type TestDataRow } from "../api";
import { authorizationScopeKey, saveBytes } from "../../../shared/api/http-client";
import { CurvePlot } from "../../../shared/ui/CurvePlot";
import { ReaderState } from "../../../shared/ui/ReaderState";
import { ReaderWorkspace, ReaderResultHeader, ReaderListError } from "../../../shared/ui/ReaderWorkspace";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

const PAGE_SIZE = 12;

export function ConnectedTestDataReader() {
  const [params, setParams] = useSearchParams();
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const query = params.get("q") ?? "";
  const [searchDraft, setSearchDraft] = React.useState(query);
  React.useEffect(() => setSearchDraft(query), [query]);
  const material = params.get("material") ?? "";
  const temperature = params.get("temperature") ?? "";
  const testType = params.get("type") ?? "";
  const sortBy = params.get("sort") === "date" ? "date" : "document";
  const sortDirection = params.get("direction") === "descending" ? "descending" : "ascending";
  const page = Math.max(0, Number(params.get("page") ?? "0") || 0);
  const selectedId = params.get("id");
  const selectedRevision = params.get("revision_id");
  const expanded = params.get("expanded") === "1";
  const previewClosed = params.get("preview") === "closed";
  const rememberReturn = useReaderReturnFocus(expanded, previewClosed);
  const dependentKey = params.get("dependent") ?? undefined;
  const view = params.get("view") === "cards" ? "cards" : "table";
  const listQuery = useQuery({ queryKey: ["connected-test-data", authorizationScopeKey()], queryFn: ({ signal }) => listTestData(signal) });
  const rows = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    const filtered = (listQuery.data ?? []).filter((row) => {
      const haystack = [row.documentKey, row.materialGrade, row.materialMaker, row.method, row.specimenId].join(" ").toLocaleLowerCase();
      return (!normalized || haystack.includes(normalized)) && (!material || row.materialId === material) && (!testType || row.method === testType) && (!temperature || testTemperature(row) === temperature);
    });
    return [...filtered].sort((left, right) => {
      const leftValue = sortBy === "date" ? left.testDate : left.documentKey;
      const rightValue = sortBy === "date" ? right.testDate : right.documentKey;
      const result = leftValue.localeCompare(rightValue) || left.id.localeCompare(right.id);
      return sortDirection === "descending" ? -result : result;
    });
  }, [listQuery.data, material, query, sortBy, sortDirection, testType, temperature]);
  const pageRows = rows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  const selected = (listQuery.data ?? []).find((row) => row.id === selectedId);
  const detailQuery = useQuery({
    queryKey: ["connected-test-data-detail", authorizationScopeKey(), selectedId, selectedRevision],
    queryFn: ({ signal }) => readTestData(selectedId as string, selectedRevision as string, signal),
    enabled: Boolean(selectedId && selectedRevision),
  });
  const detailError = selectedId && !selectedRevision
    ? new Error("저장 자료의 연결 정보가 없습니다. 목록에서 다시 선택해 주세요.")
    : detailQuery.error as Error | null;
  const update = (changes: Record<string, string | null>, closeSelection = false) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) value ? next.set(key, value) : next.delete(key);
    if (closeSelection) { next.delete("id"); next.delete("revision_id"); next.delete("expanded"); next.delete("preview"); }
    setParams(next);
    setDownloadError(null);
  };
  const select = (row: TestDataRow, open = false) => {
    if (open) rememberReturn(row.id);
    update({ preview: null, id: row.id, revision_id: row.revisionId, expanded: open ? "1" : null });
  };
  const facets = [...new Map((listQuery.data ?? []).filter((row) => row.materialId).map((row) => [row.materialId as string, row.materialGrade])).entries()];
  const testTypes = [...new Set((listQuery.data ?? []).map((row) => row.method))].sort();
  const selectedForDetail = detailQuery.data?.row ?? (selected && selected.revisionId === selectedRevision ? selected : undefined);
  const content = listQuery.isError ? <ReaderListError title="실험 데이터 목록을 불러올 수 없습니다" description={(listQuery.error as Error).message} onAction={() => void listQuery.refetch()} /> : <TestDataResult rows={pageRows} selectedId={selectedId} view={view} total={rows.length} page={page} onSelect={select} onPage={(next) => update({ page: String(next) }, true)} />;

  return <ReaderWorkspace
    title="실험 데이터"
    explorer={<TestDataTree rows={listQuery.data ?? []} selectedId={selectedId} onSelect={row => select(row)} />}
    search={<ReaderSearch label="실험 데이터 검색" id="test-data-search" value={searchDraft} onDraftChange={setSearchDraft} placeholder="실험명, 소재, 시험 방법 또는 시편 검색" onSearch={value => update({ q:value, page:"0" }, true)} />} filters={<><label>시험 온도<select aria-label="시험 온도" className={styles.select} value={temperature} onChange={event => update({ temperature: event.target.value, page: "0" }, true)}><option value="">전체</option>{[...new Set((listQuery.data ?? []).map(testTemperature))].sort().map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>소재<select aria-label="연결 소재" className={styles.select} value={material} onChange={(event) => update({ material: event.target.value, page: "0" }, true)}><option value="">전체 소재</option>{facets.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label><label>시험 방법<select aria-label="시험 유형" className={styles.select} value={testType} onChange={(event) => update({ type: event.target.value, page: "0" }, true)}><option value="">전체 시험 유형</option>{testTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label></>} tools={<><select aria-label="실험 데이터 정렬" className={styles.select} value={`${sortBy}:${sortDirection}`} onChange={(event) => { const [nextSort, nextDirection] = event.target.value.split(":"); update({ sort: nextSort, direction: nextDirection, page: "0" }, true); }}><option value="document:ascending">이름 오름차순</option><option value="document:descending">이름 내림차순</option><option value="date:ascending">오래된 시험순</option><option value="date:descending">최근 시험순</option></select><div className={styles.actions} role="group" aria-label="실험 목록 보기"><button className={`${styles.button} ${view === "table" ? styles.buttonPrimary : ""}`} type="button" aria-pressed={view === "table"} onClick={() => update({ view: "table" })}>표</button><button className={`${styles.button} ${view === "cards" ? styles.buttonPrimary : ""}`} type="button" aria-pressed={view === "cards"} onClick={() => update({ view: "cards" })}>카드</button></div></>}
  >
    {detailQuery.data && selected && detailQuery.data.row.revisionId !== selected.revisionId ? <div className={styles.notice}>이전 입력: 저장된 결과에 사용한 실험 데이터입니다. 현재 실험 데이터는 변경되었습니다.</div> : null}
    {listQuery.isError && !listQuery.data && !selectedId ? <ReaderListError title="실험 데이터를 불러올 수 없습니다" description={(listQuery.error as Error).message} onAction={() => void listQuery.refetch()} /> : null}
    {listQuery.isPending && !selectedId ? <ReaderState title="실험 데이터를 불러오는 중" /> : null}
    {(!listQuery.isPending || Boolean(selectedId)) && (!listQuery.isError || Boolean(selectedId)) ? <>
      {!expanded ? selectedId ? <div className={`${styles.resultsWithPreview} ${previewClosed ? styles.previewClosed : ""}`}><section data-reader-results="connected" className={styles.resultsRegion}>{content}</section>{!previewClosed ? <TestDataPreview selected={selectedForDetail} requestedRevisionId={selectedRevision ?? undefined} detail={detailQuery.data} detailError={detailError} dependentKey={dependentKey} onDependentChange={(value) => update({ dependent: value })} onOpen={() => { if (selectedForDetail) select(selectedForDetail, true); }} onClose={() => { if (detailError && !selectedForDetail) { update({}, true); return; } if (selectedId) rememberReturn(selectedId); update({ preview: "closed" }); }} downloadError={downloadError} onRetry={() => void detailQuery.refetch()} onDownload={async () => { if (!detailQuery.data) return; try { const file = await downloadTestData(detailQuery.data.row.id, detailQuery.data.row.revisionId); saveBytes(file.bytes, file.fileName, file.contentType); setDownloadError(null); } catch (error) { setDownloadError((error as Error).message); } }} /> : null} </div> : <section data-reader-results="connected" className={styles.resultsRegion}>{content}</section> : null}
      {expanded && (selectedForDetail || selectedId) ? <TestDataExpanded selected={selectedForDetail} detail={detailQuery.data} detailError={detailError} dependentKey={dependentKey} onDependentChange={(value) => update({ dependent: value })} onClose={() => update({ expanded: null })} downloadError={downloadError} onRetry={() => void detailQuery.refetch()} onDownload={async () => { if (!detailQuery.data) return; try { const file = await downloadTestData(detailQuery.data.row.id, detailQuery.data.row.revisionId); saveBytes(file.bytes, file.fileName, file.contentType); setDownloadError(null); } catch (error) { setDownloadError((error as Error).message); } }} /> : null}
    </> : null}
  </ReaderWorkspace>;
}

function TestDataResult({ rows, selectedId, view, total, page, onSelect, onPage }: { rows: TestDataRow[]; selectedId: string | null; view: "table" | "cards"; total: number; page: number; onSelect: (row: TestDataRow, open?: boolean) => void; onPage: (page: number) => void }) {
  const rowAction = (row: TestDataRow) => ({ "data-result-row-id": row.id, onClick: () => onSelect(row), onDoubleClick: () => onSelect(row, true), onKeyDown: (event: React.KeyboardEvent) => { if (event.key === "Enter") { event.preventDefault(); onSelect(row, true); } } });
  return <section className={styles.panel} aria-labelledby="test-data-results-heading"><ReaderResultHeader headingId="test-data-results-heading"><span className={styles.muted}>{total}건</span></ReaderResultHeader>{rows.length === 0 ? <div className={styles.empty}>조건에 맞는 실험 데이터가 없습니다.</div> : view === "cards" ? <div className={styles.cardGrid} data-reader-scroll="connected">{rows.map((row) => <article className={`${styles.materialCard} ${row.id === selectedId ? styles.selectedRow : ""}`} key={row.id}><button className={styles.rowButton} type="button" {...rowAction(row)}><h3>{row.documentKey}</h3><dl className={styles.testCardConditions}><div><dt>소재</dt><dd>{row.materialGrade}</dd></div><div><dt>시편</dt><dd>{row.specimenId || "미등록"}</dd></div><div><dt>시험 온도</dt><dd>{testTemperature(row)}</dd></div><div><dt>시험 방법</dt><dd>{row.method}</dd></div><div><dt>시험일</dt><dd>{row.testDate}</dd></div></dl></button><button type="button" className={styles.linkButton} onClick={() => onSelect(row, true)}>상세 ↗</button></article>)}</div> : <div className={styles.tableWrap} data-reader-scroll="connected"><table className={`${styles.table} ${styles.testTable}`}><thead><tr><th>실험 데이터</th><th>소재</th><th>시험 온도</th><th>시편</th><th>시험 방법</th><th>기타 조건</th><th>상세</th></tr></thead><tbody>{rows.map((row) => <tr className={row.id === selectedId ? styles.selectedRow : ""} key={row.id}><td><button className={styles.rowButton} type="button" {...rowAction(row)}><strong>{row.documentKey}</strong><small>{row.testDate}</small></button></td><td>{row.materialGrade}</td><td>{testTemperature(row)}</td><td>{row.specimenId || "미등록"}</td><td>{row.method}</td><td>{(row.conditions ?? []).filter(condition => !["temperature.test", "temperature"].includes(condition.quantity_semantics)).length ? <dl className={styles.conditionList}>{(row.conditions ?? []).filter(condition => !["temperature.test", "temperature"].includes(condition.quantity_semantics)).map(condition => <div key={condition.key}><dt>{quantityLabel(condition.quantity_semantics)}</dt><dd>{condition.original_value} {unitLabel(condition.original_unit_string)}</dd></div>)}</dl> : "미등록"}</td><td><button type="button" className={styles.linkButton} onClick={() => onSelect(row, true)}>상세 ↗</button></td></tr>)}</tbody></table></div>}<Pagination page={page} total={total} onPage={onPage} /></section>;
}

function Pagination({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) { const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE)); return <div className={styles.pagination}><span>{total ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} / ${total}` : "0건"}</span><div className={styles.actions}><button className={styles.button} type="button" disabled={page === 0} onClick={() => onPage(page - 1)}>이전</button><button className={styles.button} type="button" disabled={page + 1 >= pageCount} onClick={() => onPage(page + 1)}>다음</button></div></div>; }

function TestDataPreview({ selected, requestedRevisionId, detail, detailError, dependentKey, onDependentChange, onOpen, onClose, onRetry, onDownload, downloadError }: { selected?: TestDataRow; requestedRevisionId?: string; detail?: Awaited<ReturnType<typeof readTestData>>; detailError: Error | null; dependentKey?: string; onDependentChange: (value: string) => void; onOpen: () => void; onClose: () => void; onRetry: () => void; onDownload: () => void; downloadError: string | null }) {
  if (!selected) return <section className={styles.previewPanel} aria-labelledby="test-data-preview-heading"><ReaderPreviewHeader headingId="test-data-preview-heading" title="선택한 실험 데이터" closeLabel="실험 미리보기 접기" onClose={onClose} /><div className={styles.previewBody}>{detailError ? <ErrorPanel title="실험 데이터를 불러오지 못했습니다" error={detailError} onRetry={onRetry} /> : <ReaderState title="실험 데이터를 불러오는 중" />}</div></section>;
  const additionalConditions = (detail?.conditions ?? []).filter(condition => !["temperature.test", "temperature"].includes(condition.quantity_semantics));
  const definition = detail?.curve?.curve_metadata?.definition ?? null;
  const series = detail?.curve?.curve_series ?? null;
  const dependentKeys = definition?.channels.filter((channel) => channel.axis_role === "dependent") ?? [];
  const selectedDependent = dependentKey && dependentKeys.some((channel) => channel.key === dependentKey) ? dependentKey : dependentKeys[0]?.key;

  return <section className={styles.previewPanel} aria-labelledby="test-data-preview-heading"><ReaderPreviewHeader headingId="test-data-preview-heading" title={detail?.row.documentKey ?? selected.documentKey} closeLabel="실험 미리보기 접기" onClose={onClose} onExpand={onOpen} disabled={!detail} />{downloadError ? <div className={styles.error} role="alert">다운로드 실패: {downloadError}. 연결을 확인한 뒤 다시 시도하세요.</div> : null}<div className={styles.previewBody}><dl className={styles.details}><dt>소재</dt><dd>{selected.materialGrade}</dd><dt>시험 온도</dt><dd>{testTemperature(selected)}</dd><dt>시험 방법</dt><dd>{selected.method}</dd><dt>시험일</dt><dd>{selected.testDate}</dd></dl>{detailError ? <ErrorPanel title="실험 데이터를 불러오지 못했습니다" error={detailError} onRetry={onRetry} /> : detail ? <><div className={styles.section}><h3>측정 곡선</h3>{dependentKeys.length > 1 ? <label className={styles.inlineField}>물리량<select className={styles.select} value={selectedDependent} onChange={(event) => onDependentChange(event.target.value)}>{dependentKeys.map((channel) => <option key={channel.key} value={channel.key}>{quantityLabel(channel.quantity_semantics)} ({unitLabel(channel.display_unit)})</option>)}</select></label> : null}<CurvePlot definition={definition} series={series} dependentKey={selectedDependent} /></div><dl className={styles.details}><dt>시편</dt><dd>{detail.row.specimenId}</dd><dt>데이터 점</dt><dd>{detail.row.pointCount.toLocaleString()}</dd><dt>원본 파일</dt><dd>{detail.source?.file_name ?? "저장된 실험 파일"}</dd></dl>{additionalConditions.length ? <div className={styles.section}><h3>기타 시험 조건</h3><table className={styles.valueTable}><tbody>{additionalConditions.map((condition) => <tr key={condition.key}><th>{quantityLabel(condition.quantity_semantics)}</th><td>{condition.original_value} {unitLabel(condition.original_unit_string)}</td></tr>)}</tbody></table></div> : null}<div className={styles.downloadAction}><button className={styles.button} onClick={onDownload}>실험 데이터 JSON 다운로드</button></div></> : <ReaderState title="실험 데이터를 불러오는 중" />}</div></section>;
}

function TestDataExpanded({ selected, detail, detailError, dependentKey, onDependentChange, onClose, onRetry, onDownload, downloadError }: { selected?: TestDataRow; detail?: Awaited<ReturnType<typeof readTestData>>; detailError: Error | null; dependentKey?: string; onDependentChange: (value: string) => void; onClose: () => void; onRetry: () => void; onDownload: () => void; downloadError: string | null }) {
  const definition = detail?.curve?.curve_metadata?.definition ?? null;
  const series = detail?.curve?.curve_series ?? null;
  const dependentKeys = definition?.channels.filter((channel) => channel.axis_role === "dependent") ?? [];
  const selectedDependent = dependentKey && dependentKeys.some((channel) => channel.key === dependentKey) ? dependentKey : dependentKeys[0]?.key;
  return <section className={styles.expandedPanel} aria-labelledby="test-data-detail-heading"><div className={styles.panelHeading}><div><h2 id="test-data-detail-heading">{detail?.row.documentKey ?? selected?.documentKey ?? "선택한 실험 데이터"}</h2></div><div className={styles.actions}><button className={styles.button} type="button" onClick={onClose}>‹ 목록 보기</button>{detail ? <button className={`${styles.button} ${styles.buttonPrimary}`} type="button" onClick={onDownload}>실험 데이터 JSON 다운로드</button> : null}</div></div>{downloadError ? <div className={styles.error} role="alert">다운로드 실패: {downloadError} 연결을 확인한 뒤 다시 시도하세요.</div> : null}{detailError ? <ErrorPanel title="실험 데이터를 불러오지 못했습니다" error={detailError} onRetry={onRetry} /> : !detail ? <ReaderState title="실험 데이터를 불러오는 중" /> : <div className={styles.expandedBody}><div className={styles.expandedColumn}><dl className={styles.details}><dt>소재</dt><dd>{detail.row.materialGrade}</dd>
      <dt>제조사</dt><dd>{detail.row.materialMaker}</dd>
      <dt>시험 방법</dt><dd>{detail.row.method}</dd>
      <dt>시험일</dt><dd>{detail.row.testDate}</dd>
      <dt>시편</dt><dd>{detail.row.specimenId}</dd>
      {detail.specimenDescription ? <><dt>시편 설명</dt><dd>{detail.specimenDescription}</dd></> : null}<dt>원본</dt><dd>{detail.source?.file_name ?? "미등록"}</dd></dl><div className={styles.section}><h3>시험 조건</h3>{detail.conditions.length ? <table className={styles.valueTable}><thead><tr><th>물리량</th><th>원문</th><th>정규화</th></tr></thead><tbody>{detail.conditions.map((condition) => <tr key={condition.key}><td>{quantityLabel(condition.quantity_semantics)}</td><td>{condition.original_value} {unitLabel(condition.original_unit_string)}</td><td>{condition.normalized_value} {condition.normalized_unit}</td></tr>)}</tbody></table> : <span className={styles.muted}>등록된 시험 조건이 없습니다.</span>}</div><div className={styles.section}><h3>측정 채널</h3><table className={styles.valueTable}><thead><tr><th>채널</th><th>역할</th><th>원래 단위</th><th>정규화 단위</th></tr></thead><tbody>{detail.channels.map((channel) => <tr key={channel.key}><td>{quantityLabel(channel.quantity_semantics)}</td><td>{channel.axis_role === "independent" ? "독립 변수" : channel.axis_role === "dependent" ? "종속 변수" : "보조 변수"}</td><td>{channel.original_unit_string}</td><td>{channel.normalized_unit}</td></tr>)}</tbody></table></div><div className={styles.section}><h3>저장된 연결 자료</h3><div className={styles.actions}><Link className={styles.link} to={`/processing-outputs?source_document_id=${detail.row.id}&source_document_revision_id=${detail.row.revisionId}`}>이 실험을 사용한 처리 데이터 →</Link>{detail.row.materialId ? <Link className={styles.link} to={`/materials?id=${detail.row.materialId}`}>연결된 소재 →</Link> : <span className={styles.muted}>연결된 소재가 없습니다.</span>}</div></div></div><div className={styles.expandedColumn}><div className={styles.section}><h3>측정 곡선</h3>{dependentKeys.length > 1 ? <label className={styles.inlineField}>곡선 물리량<select className={styles.select} value={selectedDependent} onChange={(event) => onDependentChange(event.target.value)}>{dependentKeys.map((channel) => <option key={channel.key} value={channel.key}>{quantityLabel(channel.quantity_semantics)} ({unitLabel(channel.display_unit)})</option>)}</select></label> : null}<CurvePlot definition={definition} series={series} dependentKey={selectedDependent} /></div></div></div>}</section>;
}

function ErrorPanel({ title, error, onRetry }: { title: string; error: Error; onRetry: () => void }) { return <div className={styles.error} role="alert"><strong>{title}</strong><p>{error.message}</p><button className={styles.button} type="button" onClick={onRetry}>다시 시도</button></div>; }

function testTemperature(row: TestDataRow): string {
  const values = (row.conditions ?? []).filter(condition => ["temperature.test", "temperature"].includes(condition.quantity_semantics));
  if (!values.length) return "미등록";
  return values.map(condition => condition.normalized_unit === "K" && Number.isFinite(Number(condition.normalized_value))
    ? `${Number((Number(condition.normalized_value) - 273.15).toPrecision(12))} °C`
    : `${condition.original_value} ${unitLabel(condition.original_unit_string)}`).join(" / ");
}
