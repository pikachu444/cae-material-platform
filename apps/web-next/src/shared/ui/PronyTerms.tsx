import styles from "./ConnectedReaderPrimitives.module.css";

interface PronyTerm {
  ordinal?: number;
  g_ratio?: number;
  k_ratio?: number;
  relaxation_time_s?: number;
  relaxation_time?: { value?: number; unit?: string };
}

export function PronyTerms({ terms }: { terms: unknown }) {
  if (!Array.isArray(terms) || !terms.length) return null;
  const rows = terms.filter((term): term is PronyTerm => Boolean(term) && typeof term === "object");
  if (!rows.length) return null;
  const value = (number: number | undefined) => typeof number === "number"
    ? number.toLocaleString("ko-KR", { maximumSignificantDigits: 10 }) : "미등록";
  return <section className={styles.section}><h3>Prony 계수</h3>
    <table className={styles.valueTable}><thead><tr>
      <th className={styles.numeric}>항</th><th className={styles.numeric}>전단 비율 g</th><th className={styles.numeric}>체적 비율 k</th><th className={styles.numeric}>완화 시간 (s)</th>
    </tr></thead><tbody>{rows.map((term, index) => <tr key={index}>
      <td className={styles.numeric}>{term.ordinal ?? index + 1}</td><td className={styles.numeric}>{value(term.g_ratio)}</td>
      <td className={styles.numeric}>{value(term.k_ratio)}</td><td className={styles.numeric}>{value(term.relaxation_time_s ?? (term.relaxation_time?.unit === "s" ? term.relaxation_time.value : undefined))}</td>
    </tr>)}</tbody></table>
  </section>;
}
