import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import { Button } from "./Button";
import styles from "./ReaderState.module.css";

export function ReaderState({
  title,
  description,
  actionLabel = "다시 시도",
  onAction,
  tone = "info",
}: {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  tone?: "info" | "error" | "empty";
}) {
  const Icon = tone === "error" ? AlertTriangle : tone === "empty" ? RefreshCw : WifiOff;
  return (
    <section className={`${styles.state} ${styles[tone]}`} role={tone === "error" ? "alert" : undefined}>
      <Icon size={22} aria-hidden="true" />
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
        {onAction ? <Button size="sm" onClick={onAction}><RefreshCw size={15} />{actionLabel}</Button> : null}
      </div>
    </section>
  );
}

export function LiveReaderState() {
  return (
    <div className={styles.page}>
      <div className={styles.pageHeading}><div><p className={styles.kicker}>Reader</p><h1>실험 데이터</h1></div></div>
      <ReaderState title="API-not-connected" description="B1 reader integration is not connected in ordinary mode. No fixture data is used here." />
    </div>
  );
}
