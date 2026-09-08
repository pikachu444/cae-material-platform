import { PronyTerms } from "../../../shared/ui/PronyTerms";
import { cardModelFamily } from "../model-family";
import { quantityLabel, modelFamilyLabel, unitLabel, solverLabel } from "../../../shared/model/engineering-labels";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { listNeutralMaterialCards } from "../api";
import { readExactNeutralMaterial } from "../../models";
import { authorizationScopeKey } from "../../../shared/api/http-client";
import { ReaderState } from "../../../shared/ui/ReaderState";
import { ReaderWorkspace } from "../../../shared/ui/ReaderWorkspace";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

export function parameterRows(parameters: Record<string, { value?: number; unit?: string }> | undefined) {
  const fields: Array<[string, string]> = [["c10_pa", "C10"], ["c01_pa", "C01"], ["c20_pa", "C20"], ["c30_pa", "C30"], ["mu_pa", "μ"], ["alpha", "α"], ["youngs_modulus", "탄성계수"], ["poisson_ratio", "포아송비"], ["initial_yield_stress", "초기 항복강도"]];
  return fields.map(([key, label]) => ({ key, label, item: parameters?.[key] })).filter((row): row is { key: string; label: string; item: { value?: number; unit?: string } } => typeof row.item?.value === "number").map(row => {
    if (row.item.unit !== "Pa") return row;
    const divisor = row.key === "youngs_modulus" ? 1e9 : row.key === "initial_yield_stress" || row.key.endsWith("_pa") ? 1e6 : null;
    return divisor ? { ...row, item: { value: row.item.value! / divisor, unit: row.key === "youngs_modulus" ? "GPa" : "MPa" } } : row;
  });
}

export function NeutralMaterialReader() {
  const [params] = useSearchParams();
  const neutralId = params.get("id") ?? "";
  const revisionId = params.get("revision_id") ?? "";
  const materialId = params.get("material_id") ?? undefined;
  const query = useQuery({
    queryKey: ["connected-neutral-material", authorizationScopeKey(), materialId, neutralId, revisionId],
    queryFn: ({ signal }) => readExactNeutralMaterial(materialId, neutralId, revisionId, signal),
    enabled: Boolean(neutralId && revisionId),
  });
  const cardsQuery = useQuery({
    queryKey: ["connected-neutral-cards", authorizationScopeKey(), materialId, neutralId, revisionId],
    queryFn: ({ signal }) => listNeutralMaterialCards(neutralId, signal),
    enabled: Boolean(neutralId && revisionId && query.data),
  });
  const readError = !neutralId || !revisionId
    ? new Error("저장된 모델 연결 정보가 없습니다. 목록에서 다시 선택해 주세요.")
    : query.error as Error | null;
  const read = query.data;
  const cards = (cardsQuery.data ?? []).filter((card) => card.neutralMaterialId === neutralId && card.neutralMaterialRevisionId === revisionId);
  const model = read?.document.material_model_ir;
  const sourceMaterial = read?.document.sources?.material;
  const sourceState = read?.document.sources?.material_state;
  const paramsRows = [...(typeof model?.density?.value === "number" ? [{ key: "density", label: "밀도", item: model.density }] : []), ...parameterRows(model?.constitutive_model?.parameters)];

  return <ReaderWorkspace
    title="소재 모델"
    explorer={<><div className={styles.explorerHeader}><strong>소재 모델</strong></div><div className={styles.explorerSection}><h2>저장된 연결 자료</h2><div className={styles.explorerList}>{sourceMaterial ? <Link className={styles.link} to={`/materials?id=${sourceMaterial.id}`}>연결된 소재 →</Link> : null}{sourceState ? <Link className={styles.link} to={`/models?state_id=${sourceState.id}&state_revision_id=${sourceState.revisionId}`}>연결된 소재 상태 →</Link> : null}{read?.sourceTestData ? <Link className={styles.link} to={`/test-data?id=${read.sourceTestData.id}&revision_id=${read.sourceTestData.revisionId}`}>사용한 실험 데이터 →</Link> : null}{read?.sourceOutput ? <Link className={styles.link} to={`/processing-outputs?id=${read.sourceOutput.id}&revision_id=${read.sourceOutput.revisionId}`}>사용한 처리 데이터 →</Link> : null}</div></div></>}
    filters={null}
  >
    {readError ? <ReaderState tone="error" title="소재 모델을 불러올 수 없습니다" description={readError.message} onAction={() => void query.refetch()} /> : null}
    {!readError && query.isPending ? <ReaderState title="소재 모델을 불러오는 중" /> : null}
    {read ? <section className={styles.expandedPanel} aria-labelledby="neutral-detail-heading"><div className={styles.panelHeading}><div><h2 id="neutral-detail-heading">{modelFamilyLabel(model?.model_family ?? "")}</h2></div><Link className={styles.button} to="/cards">‹ 솔버 카드 목록</Link></div><div className={styles.expandedBody}><div className={styles.expandedColumn}>{read.document.candidate_selection ? <dl className={styles.details}><dt>선택한 곡선</dt><dd>{read.document.candidate_selection?.selected_series ? read.document.candidate_selection.selected_series.split("+").map(series => <div key={series}>{quantityLabel(series)}</div>) : "미등록"}</dd>{read.document.candidate_selection?.primary_family ? <><dt>주 모델</dt><dd>{read.document.candidate_selection.primary_family}</dd></> : null}{read.document.candidate_selection?.secondary_family ? <><dt>보조 모델</dt><dd>{read.document.candidate_selection.secondary_family}</dd></> : null}</dl> : null}<div className={styles.section}><h3>저장된 모델 매개변수</h3>{paramsRows.length ? <table className={styles.valueTable}><thead><tr><th>매개변수</th><th>값</th><th>단위</th></tr></thead><tbody>{paramsRows.map(({ key, label, item }) => <tr key={key}><td>{label}</td><td>{item.value?.toLocaleString("ko-KR", { maximumSignificantDigits: 8 })}</td><td>{item.unit === "1" ? "—" : unitLabel(item.unit ?? "미등록")}</td></tr>)}</tbody></table> : <span className={styles.muted}>등록된 단일 값 매개변수가 없습니다.</span>}</div><PronyTerms terms={model?.constitutive_model?.prony_terms ?? model?.prony_overlay?.terms} /></div><div className={styles.expandedColumn}><div className={styles.section}><h3>이 모델로 만든 솔버 카드</h3>{cardsQuery.isPending ? <ReaderState title="솔버 카드를 불러오는 중" /> : cardsQuery.isError ? <ReaderState tone="error" title="솔버 카드 목록을 불러올 수 없습니다" onAction={() => void cardsQuery.refetch()} /> : cards.length ? <div className={styles.tree}>{cards.map((card) => <div className={styles.treeItem} key={`${card.id}-${card.revisionId}`}><strong>{card.title}</strong><dl className={styles.details}><dt>모델 계열</dt><dd>{cardModelFamily(card)}</dd><dt>솔버</dt><dd>{solverLabel(card.target.solver)}</dd></dl><Link className={styles.link} to={`/cards?id=${card.id}&revision_id=${card.revisionId}&card_family=${card.family}&expanded=1`}>저장된 솔버 카드 →</Link></div>)}</div> : <span className={styles.muted}>이 모델로 만든 솔버 카드가 없습니다.</span>}</div></div></div></section> : null}
  </ReaderWorkspace>;
}
