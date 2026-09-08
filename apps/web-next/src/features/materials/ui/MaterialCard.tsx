import type { MaterialDetail, MaterialRow } from "../api";
import { materialPropertyRows, propertyApplicability } from "./material-property-display";
import styles from "./MaterialCard.module.css";

interface MaterialCardProps {
  material: MaterialRow;
  detail?: MaterialDetail;
  failed: boolean;
  selected: boolean;
  onSelect: (expanded?: boolean) => void;
}

export function MaterialCard({ material, detail, failed, selected, onSelect }: MaterialCardProps) {
  const propertySets = detail?.propertySets ?? [];
  const single = propertySets.length === 1 ? propertySets[0] : undefined;
  const stateName = (stateId: string) => detail?.states.find(state => state.id === stateId)?.name ?? "소재 상태 미등록";

  return <article className={`${styles.card} ${selected ? styles.selected : ""}`}
    data-result-row-id={material.id} tabIndex={0} aria-label={`${material.name} 선택`} aria-current={selected || undefined}
    onClick={() => onSelect()}
    onDoubleClick={event => { if (!(event.target as HTMLElement).closest("button")) onSelect(true); }}
    onKeyDown={event => {
      if (event.target !== event.currentTarget) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onSelect(event.key === "Enter");
      }
    }}>
    <header>
      <h3>{material.name}</h3>
    </header>
    <div className={styles.properties}>
      {detail ? propertySets.length ? propertySets.map(propertySet => {
        const conditions = propertyApplicability(propertySet);
        return <section key={propertySet.id}>
          {!single ? <h4>{stateName(propertySet.stateId)}</h4> : null}
          <dl className={styles.values}>
            {materialPropertyRows(propertySet, true).map(({ key, label, value, unit, exactValue }) =>
              <div key={key}><dt>{label}</dt><dd title={exactValue}>{value}</dd><dd className={styles.unit}>{unit}</dd></div>)}
            {conditions.temperature ? <div><dt>적용 온도</dt><dd className={styles.conditionValue}>{conditions.temperature}</dd></div> : null}
            {conditions.strainRate ? <div><dt>변형률 속도</dt><dd className={styles.conditionValue}>{conditions.strainRate}</dd></div> : null}
          </dl>
        </section>;
      }) : <p className={styles.status}>등록된 물성이 없습니다.</p> :
        <p className={styles.status}>{failed ? "물성을 불러올 수 없습니다" : "물성을 불러오는 중…"}</p>}
    </div>
    <footer>
      <button type="button" onClick={event => { event.stopPropagation(); onSelect(); }}>미리보기 →</button>
    </footer>
  </article>;
}
