import type { EngineeringPropertyRow, TestCondition } from "../model/reader-contracts";
import styles from "./EngineeringValue.module.css";

export function UnitValue({ value, unit }: { value: string; unit: string }) {
  return <span className={styles.value}><strong>{value}</strong><small>{unit}</small></span>;
}

export function ConditionSummary({ condition }: { condition: TestCondition }) {
  return <dl className={styles.condition}><div><dt>Temperature</dt><dd>{condition.temperature}</dd></div><div><dt>Rate</dt><dd>{condition.rate}</dd></div><div><dt>Environment</dt><dd>{condition.environment}</dd></div></dl>;
}

export function PropertyTable({ rows, caption = "Engineering properties" }: { rows: EngineeringPropertyRow[]; caption?: string }) {
  return <div className={styles.propertyTableWrap}>
    <table className={styles.propertyTable}>
      <caption>{caption}</caption>
      <thead><tr><th scope="col">Item</th><th scope="col">Value</th><th scope="col">Unit</th><th scope="col">Condition / scope</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.key}>
        <th scope="row">{row.label}</th>
        <td className={`${styles.propertyValue} ${row.value === null ? styles.unknown : ""}`}>{row.value ?? "Unknown"}</td>
        <td className={styles.propertyUnit}>{row.unit ?? "—"}</td>
        <td>{row.conditionOrScope ?? "—"}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}
