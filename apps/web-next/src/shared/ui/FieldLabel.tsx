import type { PropsWithChildren } from "react";
import styles from "./FieldLabel.module.css";

export function FieldLabel({ htmlFor, children, hint }: PropsWithChildren<{ htmlFor: string; hint?: string }>) {
  return (
    <label className={styles.label} htmlFor={htmlFor}>
      <span>{children}</span>
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}
