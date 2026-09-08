import styles from "./ConnectedReaderPrimitives.module.css";

// Stored applicability is shared by the model and its exported card. No defaults are inferred.
export function EngineeringApplicability({ content }: { content: Record<string, unknown> }) {
  const applicability = content.applicability as {
    temperature_min_k?: number | null; temperature_max_k?: number | null;
    strain_rate_min_per_s?: number | null; strain_rate_max_per_s?: number | null; note?: string;
  } | undefined;
  const rows: Array<[string, number, string]> = [];
  for (const [key, label, unit] of [
    ["characterized_max_true_plastic_strain", "실험으로 확인한 최대 소성 변형률", "—"],
    ["extension_max_true_plastic_strain", "외삽 최대 소성 변형률", "—"],
  ]) if (typeof content[key] === "number") rows.push([label, content[key] as number, unit]);
  if (applicability) {
    for (const [key, label, unit, offset] of [
      ["temperature_min_k", "적용 최저 온도", "°C", -273.15],
      ["temperature_max_k", "적용 최고 온도", "°C", -273.15],
      ["strain_rate_min_per_s", "적용 최소 변형률 속도", "s⁻¹", 0],
      ["strain_rate_max_per_s", "적용 최대 변형률 속도", "s⁻¹", 0],
    ] as const) {
      const value = applicability[key];
      if (typeof value === "number") rows.push([label, value + offset, unit]);
    }
  }
  const policy = content.post_necking_extension_policy;
  const extension = policy === "selected_fitted_bounded_extrapolation" ? "선택한 경화 모델로 범위 내 외삽"
    : policy === "approved_constant_true_stress" ? "진응력을 일정하게 유지하여 연장" : null;
  if (!rows.length && !extension && !applicability?.note && content.non_production !== true) return null;
  return <section className={styles.section}>
    <h3>적용 범위</h3>
    {content.non_production === true ? <p className={styles.notice}>검증용 자료입니다. 실제 해석 적용은 검증되지 않았습니다.</p> : null}
    {rows.length ? <table className={styles.valueTable}><thead><tr><th>항목</th><th>값</th><th>단위</th></tr></thead>
      <tbody>{rows.map(([label, value, unit]) => <tr key={label}><td>{label}</td><td>{Number(value.toPrecision(12)).toLocaleString("ko-KR", { maximumSignificantDigits: 12 })}</td><td>{unit}</td></tr>)}</tbody></table> : null}
    {extension ? <dl className={styles.details}><dt>네킹 이후</dt><dd>{extension}</dd></dl> : null}
    {applicability?.note && applicability.note !== "Synthetic reference conditions; not validated for engineering use." ? <p>{applicability.note}</p> : null}
    {applicability?.note === "Synthetic reference conditions; not validated for engineering use." && content.non_production !== true ? <p className={styles.notice}>합성 참고 조건입니다. 공학적 적용은 검증되지 않았습니다.</p> : null}
  </section>;
}
