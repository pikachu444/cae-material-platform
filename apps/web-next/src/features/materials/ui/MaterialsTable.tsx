import type { MaterialDetail, MaterialRow } from "../api";
import { materialPropertyRows, propertyApplicability } from "./material-property-display";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

export function MaterialsTable({ rows, details, selectedId, onSelect }: {
  rows: MaterialRow[];
  details: { data?: MaterialDetail; isError: boolean }[];
  selectedId: string | null;
  onSelect: (row: MaterialRow, expanded?: boolean) => void;
}) {
  return <div className={styles.tableWrap} data-reader-scroll="connected">
    <table className={`${styles.table} ${styles.materialTable}`}>
      <thead><tr><th>소재</th><th>소재 상태</th><th className={styles.numeric}>밀도<br />kg/m³</th>
        <th className={styles.numeric}>탄성계수<br />GPa</th><th className={styles.numeric}>포아송비</th>
        <th className={styles.numeric}>항복강도<br />MPa</th><th>적용 온도</th><th>상세</th></tr></thead>
      <tbody>{rows.flatMap((row, index) => {
        const detail = details[index]?.data;
        const sets = detail?.propertySets.length ? detail.propertySets : [undefined];
        return sets.map((set, setIndex) => <tr key={`${row.id}:${set?.id ?? "empty"}`} className={row.id === selectedId ? styles.selectedRow : ""}>
          <td><button data-result-row-id={setIndex === 0 ? row.id : undefined} className={styles.rowButton}
            aria-current={row.id === selectedId || undefined} onClick={() => onSelect(row)} onDoubleClick={() => onSelect(row, true)}
            onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); onSelect(row, true); } }}>{row.name}</button></td>
          <td>{set ? detail?.states.find(state => state.id === set.stateId)?.name ?? "미등록" : "—"}</td>
          {set ? materialPropertyRows(set, true).map(value => <td key={value.key} className={styles.numeric} title={value.exactValue}>{value.value}</td>) :
            <td colSpan={4}>{details[index]?.isError ? "물성 조회 실패" : detail ? "등록된 물성 없음" : "물성을 불러오는 중…"}</td>}
          <td>{set ? propertyApplicability(set).temperature ?? "미등록" : "—"}</td>
          <td><button className={styles.linkButton} onClick={() => onSelect(row, true)}>상세 ↗</button></td>
        </tr>);
      })}</tbody>
    </table>
  </div>;
}
