import type { TestDataRow } from "../api";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

function groupTests(rows: TestDataRow[], key: (row: TestDataRow) => string) {
  const groups = new Map<string, TestDataRow[]>();
  for (const row of rows) { const value = key(row); groups.set(value, [...(groups.get(value) ?? []), row]); }
  return groups;
}

export function TestDataTree({ rows, selectedId, onSelect }: { rows: TestDataRow[]; selectedId: string | null; onSelect: (row: TestDataRow) => void }) {
  const materials = groupTests(rows, row => row.materialId ?? "unlinked");
  return <><div className={styles.explorerHeader}><strong>실험 분류</strong></div>
    <div className={styles.explorerSection}>{[...materials].map(([materialId, materialTests]) => <details key={materialId} className={styles.materialTree} open={materialTests.some(row => row.id === selectedId) || undefined}>
      <summary className={styles.treeSummary}><span>{materialId === "unlinked" ? "소재 미연결" : materialTests[0].materialGrade || "이름 없는 소재"}</span></summary>
      <div className={styles.treeChildren}>{[...groupTests(materialTests, row => JSON.stringify([row.materialStateId, row.materialStateRevisionId, row.specimenId]))].map(([key, specimenTests]) => <details key={key} className={styles.treeNode} open={specimenTests.some(row => row.id === selectedId) || undefined}>
        <summary><span>{specimenTests[0].specimenId || "이름 없는 시편"}</span></summary><div className={styles.treeChildren}>{specimenTests.map(row => <button key={row.id} className={`${styles.explorerButton} ${row.id === selectedId ? styles.explorerButtonActive : ""}`} onClick={() => onSelect(row)}>{row.documentKey}</button>)}</div>
      </details>)}</div>
    </details>)}</div>
  </>;
}
