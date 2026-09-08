import type { MaterialDetail, MaterialPropertySet } from "../api";
import { materialPropertyRows, propertyApplicability } from "./material-property-display";
import styles from "../../../shared/ui/ConnectedReaderPrimitives.module.css";

export function PropertySetValues({ propertySet, stateName }: { propertySet: MaterialPropertySet; stateName: string }) {
  const applicability = propertyApplicability(propertySet);
  return <section className={styles.propertySet}>
    <h3>기본 물성</h3>
    <dl className={styles.propertyConditions}><dt>소재 상태</dt><dd>{stateName}</dd></dl>
    <table className={styles.valueTable}>
      <thead><tr><th>물성</th><th>값</th><th>단위</th></tr></thead>
      <tbody>{materialPropertyRows(propertySet).map(({ key, label, value, unit }) => <tr key={key}>
        <td>{label}</td><td>{value}</td><td>{unit}</td>
      </tr>)}</tbody>
    </table>
    <dl className={styles.propertyConditions}>
      <dt>물성 적용 온도</dt><dd>{applicability.temperature ?? "미등록"}</dd>
      <dt>적용 변형률 속도</dt><dd>{applicability.strainRate ?? "미등록"}</dd>
    </dl>
    {typeof applicability.note === "string" && applicability.note ? <p className={styles.muted}>{applicability.note === "Synthetic reference conditions; not validated for engineering use." ? "합성 참고 조건입니다. 공학적 적용은 검증되지 않았습니다." : applicability.note}</p> : null}
  </section>;
}

export function MaterialProperties({ detail }: { detail: MaterialDetail }) {
  return detail.propertySets.length ? <>{detail.propertySets.map(propertySet =>
    <PropertySetValues key={propertySet.id} propertySet={propertySet}
      stateName={detail.states.find(state => state.id === propertySet.stateId)?.name ?? "이름 없는 소재 상태"} />
  )}</> : <p className={styles.muted}>등록된 물성이 없습니다.</p>;
}
