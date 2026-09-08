import type { PropsWithChildren } from "react";
import styles from "./StatusTag.module.css";

export function StatusTag({ tone = "neutral", children }: PropsWithChildren<{ tone?: "neutral" | "success" | "warning" | "error" | "info" }>) {
  return <span className={`${styles.tag} ${styles[tone]}`}>{children}</span>;
}
