import type { TargetPreviewResponse } from "./features/modeling/contracts";

export function TargetPreviewResult({ preview }: { preview: TargetPreviewResponse }) {
  return <div className="target-preview-result">
    <section aria-label="Target mapping preflight">
      <h3>Target mapping</h3>
      <ul>{preview.mapping.items.map((item) => <li key={`${item.name}-${item.ir_path}`}><span className={`mapping-status ${item.status}`}>{item.status}</span><span><strong>{item.name}</strong><small>{item.detail}</small></span></li>)}</ul>
      {preview.acknowledgement_identity ? <>
        <p className="ux-notice" role="status">Acknowledgement required before delivery. This preview only identifies the required UXC-06C2 delivery input; it does not record an acknowledgement.</p>
        <details><summary>Evidence</summary><code>{preview.acknowledgement_identity}</code></details>
      </> : null}
    </section>
    <section aria-label="Native preview"><h3>{preview.filename}</h3><pre>{preview.native_text}</pre></section>
  </div>;
}
