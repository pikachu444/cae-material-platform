import styles from "./ConnectedReaderPrimitives.module.css";
export function ReaderSearch({ id, value, placeholder, label, onDraftChange, onSearch }: { id:string; value:string; placeholder:string; label:string; onDraftChange:(value:string)=>void; onSearch:(value:string)=>void }) {
  return <form className={styles.searchForm} role="search" onSubmit={event => { event.preventDefault(); onSearch(value); }}>
    <label className="sr-only" htmlFor={id}>{label}</label>
    <input id={id} name="q" autoComplete="off" spellCheck={false} type="search" className={styles.search} value={value} placeholder={placeholder} onChange={event => onDraftChange(event.target.value)} />
    <button className={`${styles.button} ${styles.buttonPrimary}`} type="submit">검색</button>
  </form>;
}
