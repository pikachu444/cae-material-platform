import { PronyTerms } from "../../../shared/ui/PronyTerms";
import type { SolverCardDetail } from "../api";
import { EngineeringApplicability } from "../../../shared/ui/EngineeringApplicability";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

const mappingLabels: Record<string, string> = {
  instantaneous_isotropic_elasticity: "순간 등방성 탄성", shear_prony_terms: "전단 Prony 계수", bulk_relaxation: "체적 완화",
  ogden_term: "Ogden 계수", volumetric_response: "체적 응답", constitutive_parameters: "구성 모델 계수",
  density: "밀도", isotropic_elasticity: "등방성 탄성", initial_yield: "초기 항복",
  isotropic_hardening_curve: "경화 곡선", post_necking_extension: "네킹 이후 연장",
  temperature_dependence: "온도 의존성", strain_rate_dependence: "변형률 속도 의존성", unit_system: "단위계",
  linear_viscoelasticity: "선형 점탄성", relaxation_spectrum: "완화 스펙트럼", hyperelasticity: "초탄성",
};
const mappingStatuses: Record<string, string> = {
  exact: "그대로 반영", transformed: "변환하여 반영", approximated: "근사 적용",
  ignored: "출력에서 제외", unsupported: "미지원", not_applicable: "해당 없음",
};

export function CardEngineeringDetails({ detail }: { detail: SolverCardDetail }) {
  const revision = detail.payload.current_revision as { content?: Record<string, unknown> } | undefined;
  const content = revision?.content;
  if (!content) return null;
  const constitutive = content.constitutive_model as { parameters?: Record<string, unknown>; prony_terms?: unknown } | undefined;
  const values: Record<string, unknown> = { ...constitutive?.parameters, ...content };
  const fields: Array<[string, string, number, string]> = [
    ["density_kg_per_m3", "밀도", 1, "kg/m³"], ["youngs_modulus_pa", "탄성계수", 1e9, "GPa"],
    ["ogden_mu_pa", "Ogden μ", 1e6, "MPa"], ["ogden_alpha", "Ogden α", 1, "—"],
    ["mu_pa", "μ", 1e6, "MPa"], ["alpha", "α", 1, "—"],
    ["c10_pa", "C10", 1e6, "MPa"], ["c01_pa", "C01", 1e6, "MPa"],
    ["c20_pa", "C20", 1e6, "MPa"], ["c30_pa", "C30", 1e6, "MPa"],
    ["law62_poisson_ratio", "LAW62 포아송비", 1, "—"],
    ["poisson_ratio", "포아송비", 1, "—"], ["initial_yield_stress_pa", "초기 항복강도", 1e6, "MPa"],
  ];
  for (const [key] of fields) {
    const item = values[key];
    if (item && typeof item === "object" && "value" in item && typeof item.value === "number") values[key] = item.value;
  }
  const properties = fields.filter(([key]) => typeof values[key] === "number");
  const mappings = content.mapping_statuses && typeof content.mapping_statuses === "object"
    ? Object.entries(content.mapping_statuses) : [];
  return <>
    {typeof content.solver_material_id === "number" ? <dl className={styles.details}><dt>솔버 내 소재 번호</dt><dd>{content.solver_material_id}</dd></dl> : null}
    {properties.length ? <section className={styles.section}><h3>카드에 반영된 물성</h3>
      <table className={styles.valueTable}><thead><tr><th>물성</th><th>값</th><th>단위</th></tr></thead><tbody>
        {properties.map(([key, label, divisor, unit]) => <tr key={key}><td>{label}</td><td>{((values[key] as number) / divisor).toLocaleString("ko-KR", { maximumSignificantDigits: 8 })}</td><td>{unit}</td></tr>)}
      </tbody></table></section> : null}
    <PronyTerms terms={content.terms ?? content.prony_terms ?? constitutive?.prony_terms} />
    <EngineeringApplicability content={content} />
    {mappings.length ? <section className={styles.section}><h3>솔버 반영 방식</h3>
      <table className={styles.valueTable}><thead><tr><th>항목</th><th>반영 방식</th></tr></thead><tbody>
        {mappings.map(([key, status]) => <tr key={key}><td>{mappingLabels[key] ?? key.replaceAll("_", " ")}</td><td>{mappingStatuses[String(status)] ?? "확인 필요"}</td></tr>)}
      </tbody></table></section> : null}
  </>;
}
