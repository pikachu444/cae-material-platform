import { createContext, useContext, useState, type ReactNode } from "react";
import { ReaderState } from "./ReaderState";
import { NavLink, useLocation, useSearchParams } from "react-router";
import styles from "./ConnectedReaderPrimitives.module.css";
const ResultsContext = createContext<{ title: string; search?: ReactNode; tools?: ReactNode }>({ title: "" });
export function ReaderResultHeader({ children, headingId }: { children?: ReactNode; headingId?: string }) {
  const { title, search, tools } = useContext(ResultsContext);
  const [params, setParams] = useSearchParams();
  const filtered = ["q", "class", "material", "type", "temperature", "family", "solver", "units", "stage", "state_id", "source_document_id", "model_id"].some(key => Boolean(params.get(key)));
  return <><header className={styles.resultHeading}><h2 id={headingId}>{title}</h2>{children}</header>
    {search ? <div className={styles.searchbar}>{search}</div> : null}
    {tools || filtered ? <div className={styles.resultTools}>{tools}{filtered ? <button className={styles.linkButton} onClick={() => { const next = new URLSearchParams(); if (params.has("view")) next.set("view", params.get("view")!); setParams(next); }}>조건 초기화</button> : null}</div> : null}</>;
}
export function ReaderListError({ title, description, onAction }: { title: string; description: string; onAction: () => void }) {
  return <section className={`${styles.panel} ${styles.listFailure}`}><ReaderResultHeader />
    <ReaderState tone="error" title={title} description={description} onAction={onAction} /></section>;
}
export function ReaderWorkspace({ title, explorer, filters, search, tools, children }: {
  title: string;
  explorer: ReactNode; filters: ReactNode; search?: ReactNode; tools?: ReactNode; children: ReactNode;
}) {
  const { pathname } = useLocation();
  const [explorerHidden, setExplorerHidden] = useState(false);
  const models = pathname === "/models" || pathname === "/neutral-materials";
  const outputs = pathname === "/processing-outputs";
  return <ResultsContext.Provider value={{ title, search, tools }}><div className={styles.workspacePage} data-reader-workspace="connected">
    <h1 className="sr-only">{title}</h1>
    <nav className={styles.scopeTabs} aria-label="조회 대상">
      <NavLink className={styles.scopeTab} to="/materials">소재</NavLink>
      <NavLink className={styles.scopeTab} to="/test-data">실험 데이터</NavLink>
      <NavLink className={`${styles.scopeTab} ${models || outputs ? styles.scopeTabActive : ""}`} to="/processing-outputs">처리 데이터·모델</NavLink>
      <NavLink className={styles.scopeTab} to="/cards">솔버 카드</NavLink>
      <button className={styles.explorerToggle} aria-expanded={!explorerHidden} aria-controls="reader-explorer" onClick={() => setExplorerHidden(value => !value)}>{explorerHidden ? "탐색·필터 열기" : "탐색·필터 접기"}</button>
    </nav>
    <div className={`${styles.workspaceBody} ${explorerHidden ? styles.explorerHidden : ""}`}>
      <aside id="reader-explorer" className={styles.explorer} hidden={explorerHidden}>{models || outputs ? <nav className={styles.collectionTabs} aria-label="저장 자료 종류"><NavLink to="/processing-outputs">처리 데이터</NavLink><NavLink to="/models">모델</NavLink></nav> : null}<div className={styles.explorerContent}>{explorer}</div>{filters ? <section className={styles.filterSection}><h2>조건 필터</h2><div className={styles.filterBar}>{filters}</div></section> : null}</aside>
      <div className={styles.workspaceMain}>{children}</div>
    </div>
  </div></ResultsContext.Provider>;
}
