import { EngineeringApplicability } from "../../../shared/ui/EngineeringApplicability";
import { ReaderPreviewHeader } from "../../../shared/ui/ReaderPreviewHeader";
import * as React from "react";
import { ReaderSearch } from "../../../shared/ui/ReaderSearch";
import { modelFamilyLabel } from "../../../shared/model/engineering-labels";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { useMemo } from "react";
import { listModelsForMaterials, modelProcessingRelation, readMaterialModel, type MaterialModelRow } from "../api";
import { listAllMaterials, readMaterial, type MaterialDetail } from "../../materials/api";
import { authorizationScopeKey } from "../../../shared/api/http-client";
import { ReaderState } from "../../../shared/ui/ReaderState";
import { ReaderWorkspace, ReaderResultHeader, ReaderListError } from "../../../shared/ui/ReaderWorkspace";
import { useReaderReturnFocus } from "../../../shared/ui/useReaderReturnFocus";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

const PAGE_SIZE = 12;

export function ModelsReader() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const [searchDraft, setSearchDraft] = React.useState(query);
  React.useEffect(() => setSearchDraft(query), [query]);
  const stateId = params.get("state_id") ?? "";
  const stateRevisionId = params.get("state_revision_id") ?? "";
  const page = Math.max(0, Number(params.get("page") ?? "0") || 0);
  const selectedId = params.get("id");
  const selectedRevision = params.get("revision_id");
  const expanded = params.get("expanded") === "1";
  const previewClosed = params.get("preview") === "closed";
  const rememberReturn = useReaderReturnFocus(expanded, previewClosed);
  const materialsQuery = useQuery({ queryKey: ["connected-model-materials", authorizationScopeKey()], queryFn: ({ signal }) => listAllMaterials(signal) });
  const detailsQuery = useQuery({ queryKey: ["connected-model-material-details", authorizationScopeKey(), materialsQuery.data?.map((item) => item.id).join(",")], queryFn: ({ signal }) => Promise.all((materialsQuery.data ?? []).map((item) => readMaterial(item.id, signal))), enabled: Boolean(materialsQuery.data) });
  const modelsQuery = useQuery({ queryKey: ["connected-models", authorizationScopeKey(), detailsQuery.data?.map((item) => item.material.id).join(",")], queryFn: ({ signal }) => listModelsForMaterials(detailsQuery.data ?? [], signal), enabled: Boolean(detailsQuery.data) });
  const rows = useMemo(() => { const normalized = query.trim().toLocaleLowerCase(); return (modelsQuery.data ?? []).filter((row) => (!stateId || row.stateId === stateId) && (!stateRevisionId || row.stateRevisionId === stateRevisionId) && (!normalized || [humanModelFamily(row.family), row.family, Object.values(exactModelState(row, detailsQuery.data ?? []) ?? {}).join(" ")].join(" ").toLocaleLowerCase().includes(normalized))); }, [modelsQuery.data, detailsQuery.data, query, stateId, stateRevisionId]);
  const pageRows = rows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  const selected = (modelsQuery.data ?? []).find((row) => row.id === selectedId);
  const directResource = params.get("resource") ?? selected?.resourcePath ?? "material-models";
  const detailQuery = useQuery({ queryKey: ["connected-model-detail", authorizationScopeKey(), selectedId, selectedRevision, directResource], queryFn: ({ signal }) => readMaterialModel(selectedId as string, signal, directResource, selectedRevision as string), enabled: Boolean(selectedId && selectedRevision) });
  const update = (changes: Record<string, string | null>, closeSelection = false) => { const next = new URLSearchParams(params); for (const [key, value] of Object.entries(changes)) value ? next.set(key, value) : next.delete(key); if (closeSelection) { next.delete("id"); next.delete("revision_id"); next.delete("resource"); next.delete("expanded"); next.delete("preview"); } setParams(next); };
  const select = (row: MaterialModelRow, open = false) => { if (open) rememberReturn(row.id); update({ preview: null, id: row.id, revision_id: row.revisionId, resource: row.resourcePath, expanded: open ? "1" : null }); };
  const selectedForDetail = detailQuery.data ?? (selected && selected.revisionId === selectedRevision ? selected : undefined);
  const detailError = selectedId && !selectedRevision
    ? new Error("저장 자료의 연결 정보가 없습니다. 목록에서 다시 선택해 주세요.")
    : detailQuery.error as Error | null;
  const directRead = Boolean(selectedId && selectedRevision);
  const listError = materialsQuery.error ?? detailsQuery.error ?? modelsQuery.error;
  const loading = !directRead && !listError && (materialsQuery.isPending || detailsQuery.isPending || modelsQuery.isPending);
  const error = directRead ? null : listError;
  const retryList = () => {
    if (materialsQuery.isError) return void materialsQuery.refetch();
    if (detailsQuery.isError) return void detailsQuery.refetch();
    void modelsQuery.refetch();
  };
  const content = listError ? <ReaderListError title="모델 목록을 불러올 수 없습니다" description={listError.message} onAction={retryList} /> : <ModelResults materials={detailsQuery.data ?? []} rows={pageRows} selectedId={selectedId} total={rows.length} page={page} onSelect={select} onPage={(next) => update({ page: String(next) }, true)} />;
  return <ReaderWorkspace title="모델" explorer={<><div className={styles.explorerHeader}><strong>모델 분류</strong></div><div className={styles.explorerSection}><h2>모델 계열</h2><div className={styles.explorerList}><button type="button" className={`${styles.explorerButton} ${!query && !stateId ? styles.explorerButtonActive : ""}`} onClick={() => update({ q: null, state_id: null, state_revision_id: null, page: "0" }, true)}>전체 모델 계열</button>{[...new Set((modelsQuery.data ?? []).map((row) => humanModelFamily(row.family)))].sort().map((family) => <button type="button" className={styles.explorerButton} key={family} onClick={() => update({ q: family, state_id: null, state_revision_id: null, page: "0" }, true)}>{family}</button>)}</div></div></>} search={<ReaderSearch label="모델 검색" id="model-search" value={searchDraft} onDraftChange={setSearchDraft} placeholder="모델 계열 또는 소재 검색" onSearch={value => update({ q:value, page:"0" }, true)} />} filters={null} tools={null}>{error && !loading ? <ReaderListError title="모델을 불러올 수 없습니다" description={(error as Error).message} onAction={retryList} /> : null}{loading ? <ReaderState title="모델을 불러오는 중" /> : null}{!loading && !error ? <>{!expanded ? selectedId ? <div className={`${styles.resultsWithPreview} ${previewClosed ? styles.previewClosed : ""}`}><section data-reader-results="connected" className={styles.resultsRegion}>{content}</section>{!previewClosed ? <ModelPreview materials={detailsQuery.data ?? []} selected={selectedForDetail} requestedId={selectedId} requestedRevision={selectedRevision ?? undefined} detailError={detailError} onRetry={() => void detailQuery.refetch()} onOpen={() => { if (selectedForDetail) select(selectedForDetail, true); }} onClose={() => { if (detailError && !selectedForDetail) { update({}, true); return; } if (selectedId) rememberReturn(selectedId); update({ preview: "closed" }); }} /> : null} </div> : <section data-reader-results="connected" className={styles.resultsRegion}>{content}</section> : null}{expanded && (selectedForDetail || selectedId) ? <ModelExpanded materials={detailsQuery.data ?? []} selected={selectedForDetail} requestedId={selectedId ?? undefined} requestedRevision={selectedRevision ?? undefined} detailError={detailError} onRetry={() => void detailQuery.refetch()} onClose={() => update({ expanded: null })} /> : null}</> : null}</ReaderWorkspace>;
}

function ModelResults({ materials, rows, selectedId, total, page, onSelect, onPage }: { materials: MaterialDetail[]; rows: MaterialModelRow[]; selectedId: string | null; total: number; page: number; onSelect: (row: MaterialModelRow, open?: boolean) => void; onPage: (page: number) => void }) { const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE)); return <section className={styles.panel} aria-labelledby="models-results-heading"><ReaderResultHeader headingId="models-results-heading"><span className={styles.muted}>{total}건</span></ReaderResultHeader>{rows.length === 0 ? <div className={styles.empty}>조건에 맞는 모델이 없습니다.</div> : <div className={styles.tableWrap} data-reader-scroll="connected"><table className={styles.table}><thead><tr><th>모델 계열</th><th>소재</th><th>소재 상태</th><th style={{ textAlign: "right" }}>탄성계수 (GPa)</th><th style={{ textAlign: "right" }}>기준 온도 (°C)</th><th>저장 시각</th><th>상세</th></tr></thead><tbody>{rows.map((row) => <tr className={row.id === selectedId ? styles.selectedRow : ""} key={row.id}><td><button data-result-row-id={row.id} className={styles.rowButton} type="button" onClick={() => onSelect(row)} onDoubleClick={() => onSelect(row, true)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); onSelect(row, true); } }}><strong>{humanModelFamily(row.family)}</strong></button></td><td>{exactModelState(row, materials)?.materialName ?? "확인 불가"}</td><td>{exactModelState(row, materials)?.stateName ?? "확인 불가"}</td><td style={{ textAlign: "right" }}>{modelParameterSummary(row).find(item => item.key === "youngs_modulus_pa" && item.unit === "GPa")?.value ?? "—"}</td><td style={{ textAlign: "right" }}>{modelParameterSummary(row).find(item => item.key === "reference_temperature_k" && item.unit === "°C")?.value ?? "—"}</td><td>{row.createdAt ? new Date(row.createdAt).toLocaleString("ko-KR", { hour12: false }) : "미등록"}</td><td><button className={styles.linkButton} type="button" onClick={() => onSelect(row, true)}>상세 ↗</button></td></tr>)}</tbody></table></div>}<div className={styles.pagination}><span>{total ? `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} / ${total}` : "0건"}</span><div className={styles.actions}><button className={styles.button} type="button" disabled={page === 0} onClick={() => onPage(page - 1)}>이전</button><button className={styles.button} type="button" disabled={page + 1 >= pageCount} onClick={() => onPage(page + 1)}>다음</button></div></div></section>; }

function ModelPreview({ materials, selected, requestedId, requestedRevision, detailError, onRetry, onOpen, onClose }: { materials: MaterialDetail[]; selected?: MaterialModelRow; requestedId?: string; requestedRevision?: string; detailError: Error | null; onRetry: () => void; onOpen: () => void; onClose: () => void }) {
  if (!selected) return <section className={styles.previewPanel} aria-labelledby="model-preview-heading"><ReaderPreviewHeader headingId="model-preview-heading" title="선택한 소재 모델" closeLabel="모델 미리보기 접기" onClose={onClose} /><div className={styles.previewBody}>{detailError ? <ErrorPanel title="모델을 불러오지 못했습니다" error={detailError} onRetry={onRetry} requestedId={requestedId} /> : <ReaderState title="소재 모델을 불러오는 중" />}</div></section>;
  return <section className={styles.previewPanel} aria-labelledby="model-preview-heading"><ReaderPreviewHeader headingId="model-preview-heading" title={humanModelFamily(selected.family)} closeLabel="모델 미리보기 접기" onClose={onClose} onExpand={onOpen} /><div className={styles.panelBody}>{detailError ? <ErrorPanel title="모델을 불러오지 못했습니다" error={detailError} onRetry={onRetry} /> : <><ModelContext model={selected} materials={materials} /><ModelParameters model={selected} /></>}</div></section>;
}

function ModelExpanded({ materials, selected, requestedId, requestedRevision, detailError, onRetry, onClose }: { materials: MaterialDetail[]; selected?: MaterialModelRow; requestedId?: string; requestedRevision?: string; detailError: Error | null; onRetry: () => void; onClose: () => void }) {
  if (!selected && detailError) return <section className={styles.expandedPanel}><div className={styles.panelHeading}><div><h2>선택한 소재 모델</h2></div><button className={styles.button} type="button" onClick={onClose}>‹ 목록 보기</button></div><div className={styles.panelBody}><ErrorPanel title="모델을 불러오지 못했습니다" error={detailError} onRetry={onRetry} requestedId={requestedId} /></div></section>;
  if (!selected) return <section className={styles.expandedPanel}><div className={styles.panelHeading}><h2>선택한 소재 모델</h2><button className={styles.button} type="button" onClick={onClose}>‹ 목록 보기</button></div><ReaderState title="소재 모델을 불러오는 중" /></section>;
  const processing = modelProcessingRelation(selected);
  return <section className={styles.expandedPanel} aria-labelledby="model-detail-heading"><div className={styles.panelHeading}><div><h2 id="model-detail-heading">{humanModelFamily(selected.family)}</h2></div><div className={styles.actions}><button className={styles.button} type="button" onClick={onClose}>‹ 목록 보기</button><Link className={styles.link} to={`/cards?model_id=${selected.id}&model_revision_id=${selected.revisionId}`}>이 모델로 만든 솔버 카드 →</Link></div></div><div className={styles.expandedBody}><div className={styles.expandedColumn}><ModelContext model={selected} materials={materials} /><ModelParameters model={selected} /><EngineeringApplicability content={selected.content} /></div><div className={styles.expandedColumn}><div className={styles.section}><h3>저장된 연결 자료</h3><div className={styles.actions}><Link className={styles.link} to={`/cards?model_id=${selected.id}&model_revision_id=${selected.revisionId}`}>이 모델로 만든 솔버 카드 →</Link>{processing ? <Link className={styles.link} to={`/processing-outputs?id=${processing.id}&revision_id=${processing.revisionId}`}>사용한 처리 데이터 →</Link> : <span className={styles.muted}>사용한 처리 데이터 연결 정보가 없습니다.</span>}</div></div></div></div></section>;
}

const humanModelFamily = modelFamilyLabel;
export function modelParameterSummary(row: MaterialModelRow): Array<{ key: string; label: string; value: string; unit: string }> {
  const sources: Record<string, unknown>[] = [row.content, row.ir];
  const payload = row.ir.payload; if (payload && typeof payload === "object") sources.push(payload as Record<string, unknown>);
  const fields: Array<[string, string, string]> = [["density_kg_per_m3", "밀도", "kg/m³"], ["youngs_modulus_pa", "탄성계수", "Pa"], ["poisson_ratio", "포아송비", "1"], ["yield_stress_pa", "항복강도", "Pa"], ["source_yield_stress_pa", "항복강도", "Pa"], ["initial_yield_stress_pa", "초기 항복강도", "Pa"], ["reference_temperature_k", "기준 온도", "K"], ["law62_poisson_ratio", "포아송비", "1"]];
  const result: Array<{ key: string; label: string; value: string; unit: string }> = [];
  for (const [key, label, fallbackUnit] of fields) {
    for (const source of sources) {
      const value = source[key]; const item = typeof value === "object" && value !== null ? value as { value?: unknown; unit?: unknown } : { value };
      if (typeof item.value === "number" && Number.isFinite(item.value)) {
        let value = item.value; let unit = typeof item.unit === "string" ? item.unit : fallbackUnit;
        if (unit === "Pa" && key === "youngs_modulus_pa") { value /= 1e9; unit = "GPa"; }
        else if (unit === "Pa" && key.includes("yield_stress_pa")) { value /= 1e6; unit = "MPa"; }
        else if (unit === "K" && key === "reference_temperature_k") { value -= 273.15; unit = "°C"; }
        result.push({ key, label, value: Number(value.toPrecision(12)).toLocaleString(), unit }); break;
      }
    }
  }
  return result;
}
function ErrorPanel({ title, error, onRetry, requestedId }: { title: string; error: Error; onRetry: () => void; requestedId?: string }) { return <div className={styles.error} role="alert"><strong>{title}</strong><p>{error.message}</p><button className={styles.button} type="button" onClick={onRetry}>다시 시도</button></div>; }

function ModelParameters({ model }: { model: MaterialModelRow }) {
  const summary = modelParameterSummary(model);
  return <section className={styles.section}>
    <h3>저장된 매개변수</h3>
    {summary.length ? <table className={styles.valueTable}>
      <thead><tr><th>물성</th><th>값</th><th>단위</th></tr></thead>
      <tbody>{summary.map(item => <tr key={item.key}><td>{item.label}</td><td>{item.value}</td><td>{item.unit === "1" ? "—" : item.unit}</td></tr>)}</tbody>
    </table> : <span className={styles.muted}>등록된 단일 값 매개변수가 없습니다.</span>}
  </section>;
}
export function exactModelState(row: MaterialModelRow, materials: MaterialDetail[]): { materialName: string; stateName: string } | null {
  for (const material of materials) {
    const state = material.states.find(state => state.id === row.stateId && state.revisionId === row.stateRevisionId);
    if (state) return { materialName: material.material.name, stateName: state.name };
  }
  return null;
}

function ModelContext({ model, materials }: { model: MaterialModelRow; materials: MaterialDetail[] }) {
  const context = exactModelState(model, materials);
  return <dl className={styles.details}><dt>소재</dt><dd>{context?.materialName ?? "사용한 소재 확인 불가"}</dd>
    <dt>소재 상태</dt><dd>{context?.stateName ?? "사용한 상태 확인 불가"}</dd>
    <dt>저장 시각</dt><dd>{model.createdAt ? new Date(model.createdAt).toLocaleString("ko-KR", { hour12: false }) : "미등록"}</dd></dl>;
}
