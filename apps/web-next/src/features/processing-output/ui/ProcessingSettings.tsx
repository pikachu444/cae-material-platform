import type { ProcessingOutputRow } from "../api";
import { quantityLabel } from "../../../shared/model/engineering-labels";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

const labels: Record<string, string> = {
  duplicate_policy: "중복 처리", strain_quantity: "변형률", stress_quantity: "응력", plastic_strain_quantity: "소성 변형률",
  youngs_modulus_pa: "탄성계수", necking_policy: "네킹 경계", manual_necking_index: "네킹 시작 점 (0부터)",
  negative_plastic_policy: "음의 소성 변형률", families: "비교 모델", primary_family: "주 모델", secondary_family: "보조 모델",
  primary_weight: "주 모델 가중치", fit_minimum_strain: "피팅 최소 변형률", fit_maximum_strain: "피팅 최대 변형률",
  extrapolation_maximum_strain: "외삽 최대 변형률", output_point_count: "출력 점 수", normalization_stress_pa: "정규화 응력",
  maximum_function_evaluations: "최대 함수 평가 횟수", selection_reason: "선택 사유", equation_contract: "사용한 방정식",
  minimum: "최솟값", maximum: "최댓값", point_count: "점 수", dependent_quantities: "처리 물리량",
};
const values: Record<string, string> = {
  reject: "허용하지 않음", first: "첫 값 사용", mean: "평균값 사용", manual_index: "사용자가 지정한 점",
  observed_full_domain: "관측 범위 전체", retain: "유지", clip_zero: "0으로 치환", drop: "제외",
  voce: "Voce", swift: "Swift", hockett_sherby: "Hockett–Sherby", ghosh: "Ghosh",
  "altair-material-modeler-2025-v1": "Altair Material Modeler 2025",
};
const methods: Record<string, string> = {
  "rows.sort_unique": "입력 정렬 및 중복 처리", "metal.engineering_to_true_plastic": "진응력·소성 변형률 변환",
  "metal.hardening_fit_extrapolate": "경화 곡선 피팅", "polymer.log_time_resample": "로그 시간 재표본화", "curve.crop": "범위 자르기",
};

export function ProcessingSettings({ steps }: { steps: ProcessingOutputRow["steps"] }) {
  return <section className={styles.section}><h3>사용한 처리 설정</h3>{steps.map((step, index) => {
    const entries = Object.entries(step.options);
    const known = entries.filter(([key]) => key in labels);
    return <details className={styles.section} key={index}>
      <summary>{index + 1}. {methods[step.method_id] ?? "처리 설정"}</summary>
      {known.length ? <table className={styles.valueTable}><thead><tr><th>항목</th><th>값</th><th>단위</th></tr></thead><tbody>{known.flatMap(([key, value]) => (Array.isArray(value) ? value : [value]).map((item, i) => {
        const divisor = key === "youngs_modulus_pa" ? 1e9 : key === "normalization_stress_pa" ? 1e6 : 1;
        const display = typeof item === "number" ? (item / divisor).toLocaleString("ko-KR", { maximumSignificantDigits: 12 })
          : item === null ? "미지정" : values[String(item)] ?? quantityLabel(String(item));
        return <tr key={`${key}-${i}`}><td>{labels[key]}</td><td>{display}</td><td>{divisor === 1e9 ? "GPa" : divisor === 1e6 ? "MPa" : "—"}</td></tr>;
      }))}</tbody></table> : null}
      {!entries.length ? <p className={styles.muted}>별도로 저장된 설정이 없습니다.</p> : entries.length !== known.length ? <p className={styles.notice}>일부 처리 설정은 아직 화면에서 표시하지 못합니다.</p> : null}
    </details>;
  })}</section>;
}
