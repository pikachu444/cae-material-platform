import { FlaskConical, Layers3, Table2 } from "lucide-react";
import { NavLink, useSearchParams } from "react-router";
import { useEffect, useState, type PropsWithChildren } from "react";
import type { PrototypeScenario } from "../features/test-data/model/test-data-types";
import { connectDemoSession } from "../shared/api/http-client";
import styles from "./AppShell.module.css";

export type ReaderLayout = "A" | "B";

const scenarios: Array<{ value: PrototypeScenario; label: string }> = [
  { value: "normal", label: "Normal" },
  { value: "dense", label: "Dense 10,000" },
  { value: "empty", label: "Empty" },
  { value: "error", label: "503 error" },
  { value: "unsupported", label: "Unsupported mapping" },
  { value: "long-name", label: "Long names" },
];

export function AppShell({ mode, children }: PropsWithChildren<{ mode: "prototype" | "live" }>) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [demoConnected, setDemoConnected] = useState(() => {
    try { return Boolean(window.sessionStorage.getItem("cmp-access-token")); } catch { return false; }
  });
  useEffect(() => { const expired = () => setDemoConnected(false); window.addEventListener("cmp-session-expired", expired); return () => window.removeEventListener("cmp-session-expired", expired); }, []);
  const layout = searchParams.get("layout") === "B" ? "B" : "A";
  const scenario = (scenarios.some((item) => item.value === searchParams.get("scenario"))
    ? searchParams.get("scenario")
    : "normal") as PrototypeScenario;

  const updateSearchParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  const resetFixture = () => {
    const next = new URLSearchParams();
    next.set("layout", layout);
    next.set("scenario", "normal");
    setSearchParams(next);
  };

  return (
    <div className={styles.app} data-mode={mode} data-layout={layout}>
      <header className={styles.topbar}>
        <a className={styles.brandBlock} href="/materials"><b className={styles.brandMark}>CAE</b><span className={styles.brand}>Material Platform</span></a>
        {mode === "live" ? (
          <button type="button" className={styles.resetButton} onClick={async () => { if (await connectDemoSession()) { setDemoConnected(true); window.location.reload(); } }}>
            {demoConnected ? "로컬 데모 연결됨" : "로컬 데모 연결"}
          </button>
        ) : null}
      </header>

      {mode === "prototype" ? (
        <div className={styles.prototypeToolbar} aria-label="Prototype review controls">
          <span className={styles.banner}>화면 검토용 예시 데이터</span>
          <label>
            Scenario
            <select aria-label="Prototype scenario" value={scenario} onChange={(event) => updateSearchParam("scenario", event.target.value)}>
              {scenarios.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <div className={styles.layoutControl} role="group" aria-label="Reader layout">
            <span>Reader layout</span>
            <button type="button" className={layout === "A" ? styles.selectedControl : ""} onClick={() => updateSearchParam("layout", "A")}>A · table first</button>
            <button type="button" className={layout === "B" ? styles.selectedControl : ""} onClick={() => updateSearchParam("layout", "B")}>B · curve focus</button>
          </div>
          <button type="button" className={styles.resetButton} onClick={resetFixture}>예시 초기화</button>
        </div>
      ) : null}

      <div className={styles.body}>
        <aside className={styles.nav} aria-label="주요 업무">
          <div className={styles.navTitle}>데이터</div>
          <NavItem to="/materials" icon={<Layers3 size={19} />} label="소재·데이터" />
          <NavItem to="/intake" icon={<Table2 size={19} />} label="데이터 등록" interactive={false} />
          <div className={styles.navTitle}>분석</div>
          <NavItem to="/process" icon={<FlaskConical size={19} />} label="처리·통계" interactive={false} />
        </aside>
        <main className={styles.main}>{children}</main>
      </div>
    </div>
  );
}

function NavItem({ to, icon, label, interactive = true }: { to: string; icon: React.ReactNode; label: string; interactive?: boolean }) {
  if (!interactive) return <span className={`${styles.navItem} ${styles.disabledNavItem}`} aria-disabled="true" title="준비 중">{icon}<span>{label}</span></span>;
  return (
    <NavLink className={({ isActive }) => `${styles.navItem} ${isActive || to === "/materials" ? styles.active : ""}`} to={to}>
      {icon}<span>{label}</span>
    </NavLink>
  );
}
