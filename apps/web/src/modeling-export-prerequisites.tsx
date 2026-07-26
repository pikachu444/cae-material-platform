import type { ExportPrerequisite } from "./modeling-export-eligibility";

export function ModelingExportPrerequisites({
  prerequisites,
}: {
  prerequisites: ExportPrerequisite[];
}) {
  const outputStatus = prerequisites.find((item) => item.label === "Processing Output")?.status;
  return (
    <section className="modeling-export-blocked" role="status" aria-label="Export prerequisites">
      <header>
        <div>
          <p className="workspace-caption">Exact Export</p>
          <h2>Export is unavailable</h2>
        </div>
        <span className="status-chip warning">Blocked</span>
      </header>
      <p>
        Native preview and delivery are withheld until the current source chain is proven by the server.
        A stale, different-material, or unverified output is never used as a fallback.
      </p>
      <ul className="modeling-export-prerequisite-list" aria-label="Exact Export prerequisite checklist">
        {prerequisites.map((item) => (
          <li key={item.label}>
            <span className={`mapping-status ${item.status}`}>{item.status.replaceAll("-", " ")}</span>
            <span><strong>{item.label}</strong><small>{item.detail}</small></span>
          </li>
        ))}
      </ul>
      <section className="modeling-export-lineage" aria-label="Exact Export lineage">
        <strong>Required lineage</strong>
        <ol>
          <li className={outputStatus === "current" ? "current" : outputStatus === "stale" ? "stale" : "missing"}>Processing Output</li>
          <li className="missing">Material Model IR</li>
          <li className="missing">Neutral representation</li>
          <li className="missing">Target mapping preflight</li>
          <li className="missing">Delivered native card</li>
        </ol>
        <small>Review and Release remain <strong>Not configured</strong>; they are not substituted for delivery proof.</small>
      </section>
    </section>
  );
}
