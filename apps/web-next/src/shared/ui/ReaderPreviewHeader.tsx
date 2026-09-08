import type { ReactNode } from "react";
import { Maximize2, X } from "lucide-react";
import styles from "./ConnectedReaderPrimitives.module.css";

export function ReaderPreviewHeader({ headingId, title, identity, subtitle, closeLabel, onClose, onExpand, disabled = false }: {
  headingId: string;
  title: string;
  identity?: ReactNode;
  subtitle?: ReactNode;
  closeLabel: string;
  onClose: () => void;
  onExpand?: () => void;
  disabled?: boolean;
}) {
  return <>
    <div className={styles.detailToolbar}>
      <span>미리보기</span>
      <div className={styles.actions}>
        {onExpand ? <button className={styles.button} disabled={disabled} onClick={onExpand}>
          확대 상세 <Maximize2 size={13} aria-hidden="true" />
        </button> : null}
        <button className={styles.button} aria-label={closeLabel} onClick={onClose}><X size={16} aria-hidden="true" /></button>
      </div>
    </div>
    <header className={styles.detailIdentity}>
      {identity ? <div className={styles.identityLine}>{identity}</div> : null}
      <h2 id={headingId}>{title}</h2>
      {subtitle ? <p>{subtitle}</p> : null}
    </header>
  </>;
}
