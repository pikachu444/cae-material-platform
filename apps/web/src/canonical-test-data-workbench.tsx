import { useState, type ChangeEvent } from "react";

import { ApiError, validateCanonicalTestData, type ApiConfig } from "./api";
import type { CanonicalTestDataPreviewResponse } from "./types";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}

const SAMPLE = `{
  "document_type": "cmp.test-data",
  "schema_version": "1.0.0",
  "document_id": "DP600-TENSILE-01",
  "material": {"maker": "CMP Demo Metals", "grade": "DP600", "lot_batch": "LOT-2026-07"},
  "test": {"date": "2026-07-18", "operator": "Kim Tester", "laboratory": "CMP Laboratory", "method": "uniaxial tensile reference method", "equipment_maker": "Demo Instruments", "equipment_model": "UTM-01"},
  "specimen": {"specimen_id": "S-01", "description": "sheet coupon"},
  "conditions": [{"key": "temperature", "quantity_semantics": "temperature.test", "original_value": "23", "original_unit_string": "Cel", "normalized_value": "296.15", "normalized_unit": "K"}],
  "channels": [
    {"key": "engineering_strain", "name": "Engineering strain", "quantity_semantics": "mechanics.strain.engineering", "axis_role": "independent", "original_unit_string": "%", "normalized_unit": "1", "normalization": {"scale": "0.01", "offset": "0"}, "original_values": ["0", "0.1", null], "normalized_values": ["0", "0.001", null], "missing_reasons": [null, null, "instrument dropout"]},
    {"key": "engineering_stress", "name": "Engineering stress", "quantity_semantics": "mechanics.stress.engineering", "axis_role": "dependent", "original_unit_string": "MPa", "normalized_unit": "Pa", "normalization": {"scale": "1000000", "offset": "0"}, "original_values": ["0", "205", null], "normalized_values": ["0", "205000000", null], "missing_reasons": [null, null, "instrument dropout"]}
  ],
  "source": {"file_name": "dp600-tensile.csv", "media_type": "text/csv", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
}`;

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "The Test Data JSON could not be validated.";
}

export function CanonicalTestDataWorkbench({ config, onNavigate, onOpenConnection }: Props) {
  const [source, setSource] = useState(SAMPLE);
  const [fileName, setFileName] = useState("built-in DP600 example");
  const [preview, setPreview] = useState<CanonicalTestDataPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function chooseFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 25 * 1024 * 1024) {
      setError("A single JSON document is limited to 25 MiB; use the JSON+ZIP package path.");
      return;
    }
    setSource(await file.text());
    setFileName(file.name);
    setPreview(null);
    setError(null);
  }

  async function validate(): Promise<void> {
    setBusy(true);
    setError(null);
    setPreview(null);
    try {
      const parsed = JSON.parse(source) as Record<string, unknown>;
      const result = await validateCanonicalTestData(config, parsed);
      setPreview(result.data);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid JSON syntax: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="test-json-page">
      <section className="page-hero compact-hero">
        <div>
          <p className="eyebrow">T-52 · canonical exchange</p>
          <h1>Test Data JSON</h1>
          <p>Validate maker, test, specimen, quantity, original units, normalized units and missing evidence before immutable import.</p>
        </div>
        <div className="hero-actions">
          <button className="button secondary" type="button" onClick={() => onNavigate("/datasets")}>Dataset hub</button>
          <button className="button secondary" type="button" onClick={onOpenConnection}>Connection</button>
        </div>
      </section>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      <section className="test-json-grid">
        <article className="workbench-card json-source-card">
          <div className="section-heading"><div><p className="eyebrow">User exchange file</p><h2>JSON source</h2></div><span className="status-chip">{fileName}</span></div>
          <label className="file-picker">Choose `.json` file<input type="file" accept="application/json,.json" onChange={(event) => void chooseFile(event)} /></label>
          <label>Document<textarea className="json-editor" aria-label="Canonical Test Data JSON" value={source} onChange={(event) => { setSource(event.target.value); setPreview(null); }} spellCheck={false} /></label>
          <button className="button primary" type="button" disabled={busy} onClick={() => void validate()}>{busy ? "Validating…" : "Validate with server"}</button>
        </article>

        <article className="workbench-card json-preview-card">
          <p className="eyebrow">Semantic preview</p>
          <h2>{preview ? `${preview.material_maker} · ${preview.material_grade}` : "Awaiting validation"}</h2>
          {preview ? (
            <>
              <div className="preview-facts">
                <div><span>Status</span><strong>{preview.status}</strong></div>
                <div><span>Test date</span><strong>{preview.test_date}</strong></div>
                <div><span>Operator</span><strong>{preview.operator}</strong></div>
                <div><span>Specimen</span><strong>{preview.specimen_id}</strong></div>
                <div><span>Points</span><strong>{preview.point_count}</strong></div>
                <div><span>Conditions</span><strong>{preview.condition_count}</strong></div>
              </div>
              <p className="digest-line"><span>canonical SHA-256</span><code>{preview.document_sha256}</code></p>
              <h3>Channel semantics and units</h3>
              <div className="channel-preview-list">
                {preview.channels.map((channel) => (
                  <div className="channel-preview" key={channel.key}>
                    <div><strong>{channel.name}</strong><small>{channel.quantity_semantics}</small></div>
                    <span>{channel.original_unit_string} → {channel.normalized_unit}</span>
                    <span>{channel.axis_role}</span>
                    <span>{channel.missing_count} missing</span>
                  </div>
                ))}
              </div>
              <p className="mapping-note">Preview does not save data. Immutable import and exact Dataset links are the next action in this T-52 slice.</p>
            </>
          ) : <p className="muted">Choose a JSON file or use the example, then validate it against the real API.</p>}
        </article>
      </section>
    </main>
  );
}
