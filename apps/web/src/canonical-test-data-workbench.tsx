import { useEffect, useState, type ChangeEvent } from "react";

import {
  ApiError,
  getAuthenticatedPrincipal,
  type ApiConfig,
} from "./shared/api";
import {
  convertTabularToCanonicalTestData,
  downloadCanonicalTestDataDocument,
  downloadCanonicalTestDataPackage,
  importCanonicalTestData,
  listCanonicalTestDataDocuments,
  reviseCanonicalTestData,
  validateCanonicalTestData,
} from "./features/test-data";
import type {
  CanonicalTestDataDocumentResponse,
  CanonicalTestDataPreviewResponse,
  DataClassification,
} from "./types";
import { DomainWorkflowLinks } from "./domain-workflow-links";
import { modelingFamilyFromQuantities, saveModelingSession } from "./features/modeling";
import { ReviewRequestAction } from "./review-request-action";
import { appendActivityFailure, appendActivityOutcome } from "./activity-recovery";
import "./features/test-data/ui/canonical-test-data-workbench.css";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
  locationSearch?: string;
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

const TABULAR_ADAPTER_SAMPLE = `{
  "document_id": "DP600-CSV-01",
  "material": {"maker": "CMP Demo Metals", "grade": "DP600", "lot_batch": null},
  "test": {"date": "2026-07-18", "operator": "Kim Tester", "laboratory": "CMP Laboratory", "method": "uniaxial tensile reference method", "equipment_maker": null, "equipment_model": null},
  "specimen": {"specimen_id": "CSV-S-01", "description": null},
  "conditions": [],
  "profile": {
    "profile_label": "DP600 strain-stress CSV",
    "data_schema": "monotonic_tension",
    "file_format": "csv",
    "sheet_name": null,
    "header_row": 1,
    "encoding": "utf-8",
    "delimiter": ",",
    "decimal_separator": ".",
    "channels": [
      {"ordinal": 0, "source_column": "strain", "source_quantity": "engineering_strain", "original_unit": "1", "axis_role": "independent"},
      {"ordinal": 1, "source_column": "stress", "source_quantity": "engineering_stress", "original_unit": "MPa", "axis_role": "dependent"}
    ],
    "initial_gauge_length_m": null,
    "initial_cross_section_area_m2": null,
    "approval_kind": "human_confirmed"
  }
}`;

async function fileBase64(file: File): Promise<string> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read the tabular file."));
    reader.readAsDataURL(file);
  });
  return dataUrl.slice(dataUrl.indexOf(",") + 1);
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "The Test Data JSON operation failed.";
}

async function recordTestDataRecovery(
  config: ApiConfig,
  context: { documentId?: string; documentRevisionId?: string; path: string },
  status: "failed" | "succeeded",
  message: string,
): Promise<void> {
  try {
    const principal = await getAuthenticatedPrincipal(config);
    const args = [
      principal.data.principal_id,
      principal.data.organization_id,
      principal.data.project_id,
      "activity" as const,
      { kind: "test_data_json" as const, ...context },
      message,
    ] as const;
    if (status === "failed") appendActivityFailure(...args);
    else appendActivityOutcome(...args);
  } catch {
    // A local recovery fact never blocks the exact server download.
  }
}

export function CanonicalTestDataWorkbench({ config, onNavigate, locationSearch = "" }: Props) {
  const [source, setSource] = useState(SAMPLE);
  const [fileName, setFileName] = useState("built-in DP600 example");
  const [tabularFile, setTabularFile] = useState<File | null>(null);
  const [tabularSettings, setTabularSettings] = useState(TABULAR_ADAPTER_SAMPLE);
  const [preview, setPreview] = useState<CanonicalTestDataPreviewResponse | null>(null);
  const [documents, setDocuments] = useState<CanonicalTestDataDocumentResponse[]>([]);
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [changeReason, setChangeReason] = useState("Initial canonical Test Data import");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void loadDocuments();
  }, [config.baseUrl, config.accessToken, locationSearch]);

  async function loadDocuments(): Promise<void> {
    try {
      const result = await listCanonicalTestDataDocuments(config);
      setDocuments(result.data.items);
      const query = new URLSearchParams(locationSearch);
      const documentId = query.get("document_id");
      const revisionId = query.get("revision_id");
      if (documentId && revisionId) {
        const content = await downloadCanonicalTestDataDocument(config, documentId, revisionId);
        setSource(await content.data.blob.text());
        setFileName(`${documentId} · exact revision ${revisionId}`);
        setPreview(null);
        setNotice(`Loaded exact Test Data revision ${revisionId}. Validate the source, then append a revised immutable version.`);
        setError(null);
      }
      else setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

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
    setNotice(null);
  }

  async function validate(): Promise<void> {
    setBusy(true);
    setError(null);
    setNotice(null);
    setPreview(null);
    try {
      const parsed = JSON.parse(source) as Record<string, unknown>;
      const result = await validateCanonicalTestData(config, parsed);
      setPreview(result.data);
      setNotice("Validation passed. Review semantic and unit evidence before importing.");
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid JSON syntax: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function convertTabular(): Promise<void> {
    if (!tabularFile) {
      setError("Choose a CSV, TSV, or XLSX source file first.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const settings = JSON.parse(tabularSettings) as Record<string, unknown>;
      const result = await convertTabularToCanonicalTestData(config, {
        ...settings,
        source_file_name: tabularFile.name,
        source_base64: await fileBase64(tabularFile),
      });
      setSource(JSON.stringify(result.data.canonical_document, null, 2));
      setFileName(`${tabularFile.name} → cmp.test-data`);
      setPreview(result.data);
      setNotice("Tabular mapping converted successfully. Review both original and normalized evidence.");
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid adapter settings JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function importDocument(): Promise<void> {
    if (!preview) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const documentKey = String(preview.canonical_document.document_id ?? "");
      const current = documents.find((item) => item.document_key === documentKey);
      const result = current
        ? await reviseCanonicalTestData(
            config,
            current.test_data_document_id,
            `"revision:${current.current_revision.revision_no}:sha256:${current.current_revision.content_hash}"`,
            { document: preview.canonical_document, change_reason: changeReason },
          )
        : await importCanonicalTestData(config, {
            classification,
            document: preview.canonical_document,
            change_reason: changeReason,
          });
      setNotice(`Imported ${result.data.document_key} as immutable revision ${result.data.current_revision.revision_no}.`);
      await loadDocuments();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  const previewDocumentKey = preview ? String(preview.canonical_document.document_id ?? "") : "";
  const matchingDocument = documents.find((item) => item.document_key === previewDocumentKey);

  async function downloadDocument(item: CanonicalTestDataDocumentResponse): Promise<void> {
    setError(null);
    try {
      const result = await downloadCanonicalTestDataDocument(
        config,
        item.test_data_document_id,
        item.current_revision.id,
      );
      const url = URL.createObjectURL(result.data.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.data.filename;
      link.click();
      URL.revokeObjectURL(url);
      void recordTestDataRecovery(
        config,
        {
          documentId: item.test_data_document_id,
          documentRevisionId: item.current_revision.id,
          path: `/datasets/test-data/${item.test_data_document_id}/revisions/${item.current_revision.id}`,
        },
        "succeeded",
        `Downloaded exact Test Data revision ${item.current_revision.revision_no}.`,
      );
    } catch (caught) {
      setError(errorMessage(caught));
      void recordTestDataRecovery(
        config,
        {
          documentId: item.test_data_document_id,
          documentRevisionId: item.current_revision.id,
          path: `/datasets/test-data/${item.test_data_document_id}/revisions/${item.current_revision.id}`,
        },
        "failed",
        errorMessage(caught),
      );
    }
  }

  async function downloadPackage(): Promise<void> {
    setError(null);
    try {
      const result = await downloadCanonicalTestDataPackage(
        config,
        documents.map((item) => ({
          document_id: item.test_data_document_id,
          revision_id: item.current_revision.id,
        })),
      );
      const url = URL.createObjectURL(result.data.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.data.filename;
      link.click();
      URL.revokeObjectURL(url);
      void recordTestDataRecovery(
        config,
        { path: "/datasets/test-data" },
        "succeeded",
        `Downloaded the current JSON+ZIP package for ${documents.length} Test Data documents.`,
      );
    } catch (caught) {
      setError(errorMessage(caught));
      void recordTestDataRecovery(
        config,
        { path: "/datasets/test-data" },
        "failed",
        errorMessage(caught),
      );
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
          <button className="button secondary" type="button" onClick={() => onNavigate("/modeling")}>Material Modeling</button>
        </div>
      </section>

      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {notice ? <div className="success-banner" role="status">{notice}</div> : null}
      <details className="workbench-card tabular-adapter-card">
        <summary><span><strong>CSV / TSV / XLSX adapter</strong><small>Reuse the governed mapping contract and produce the same canonical JSON.</small></span></summary>
        <div className="tabular-adapter-grid">
          <label className="file-picker">Choose tabular source<input aria-label="Tabular source file" type="file" accept=".csv,.tsv,.xlsx,text/csv,text/tab-separated-values,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => setTabularFile(event.target.files?.[0] ?? null)} /></label>
          <label>Metadata and mapping profile JSON<textarea className="adapter-settings-editor" aria-label="Tabular adapter settings" value={tabularSettings} onChange={(event) => setTabularSettings(event.target.value)} spellCheck={false} /></label>
          <div className="hero-actions"><button className="button primary" type="button" disabled={busy} onClick={() => void convertTabular()}>{busy ? "Converting…" : "Convert to canonical preview"}</button><button className="button secondary" type="button" onClick={() => onNavigate("/datasets/import")}>Open governed mapping workbench</button></div>
        </div>
      </details>
      <section className="test-json-grid">
        <article className="workbench-card json-source-card">
          <div className="section-heading"><div><p className="eyebrow">User exchange file</p><h2>JSON source</h2></div><span className="status-chip">{fileName}</span></div>
          <label className="file-picker">Choose `.json` file<input type="file" accept="application/json,.json" onChange={(event) => void chooseFile(event)} /></label>
          <label>Document<textarea className="json-editor" aria-label="Canonical Test Data JSON" value={source} onChange={(event) => { setSource(event.target.value); setPreview(null); }} spellCheck={false} /></label>
          <button className="button primary" type="button" disabled={busy} onClick={() => void validate()}>{busy ? "Working…" : "Validate with server"}</button>
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
              <div className="import-controls">
                <label>Classification<select aria-label="Classification" value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}><option value="internal">Internal</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option><option value="export_controlled">Export controlled</option></select></label>
                <label>Change reason<input aria-label="Change reason" value={changeReason} onChange={(event) => setChangeReason(event.target.value)} /></label>
                <button className="button primary" type="button" disabled={busy || changeReason.trim().length === 0} onClick={() => void importDocument()}>{busy ? "Saving…" : matchingDocument ? "Append immutable revision" : "Import immutable revision"}</button>
              </div>
              <p className="mapping-note">Import writes a stable Test Data identity, an immutable revision, canonical JSON evidence, and a normalized Parquet artifact. Existing evidence is never overwritten.</p>
            </>
          ) : <p className="muted">Choose a JSON file or use the example, then validate it against the real API.</p>}
        </article>
      </section>

      <section className="workbench-card saved-test-documents">
        <div className="section-heading"><div><p className="eyebrow">Revision-pinned evidence</p><h2>Imported Test Data</h2></div><div className="hero-actions"><span className="status-chip">{documents.length} documents</span><button className="button secondary" type="button" disabled={documents.length === 0} onClick={() => void downloadPackage()}>Download current JSON+ZIP</button></div></div>
        {documents.length === 0 ? <p className="muted">No canonical Test Data has been imported in this project.</p> : (
          <div className="document-list">
            {documents.map((item) => (
              <article className="document-row" key={item.test_data_document_id}>
                <div><strong>{item.material_maker} · {item.material_grade}</strong><small>{item.document_key} · specimen {item.specimen_id} · {item.point_count} points</small></div>
                <div><span>Revision {item.current_revision.revision_no}</span><code title={item.canonical_sha256}>{item.canonical_sha256.slice(0, 12)}…</code></div>
                <button className="button secondary" type="button" onClick={() => void downloadDocument(item)}>Download exact JSON</button>
                <button className="button secondary" type="button" onClick={() => {
                  saveModelingSession({
                    materialFamily: modelingFamilyFromQuantities(item.channels.map((channel) => channel.quantity_semantics)),
                    objective: "Prepare imported test curves and create a material card",
                    testData: {
                      id: item.test_data_document_id,
                      revisionId: item.current_revision.id,
                      label: item.document_key,
                      revisionNo: item.current_revision.revision_no,
                    },
                  });
                  onNavigate("/modeling");
                }}>Open in Material Modeling</button>
                <ReviewRequestAction
                  config={config}
                  subject={{
                    aggregateType: "datasets.test_data_document",
                    aggregateId: item.test_data_document_id,
                    revisionId: item.current_revision.id,
                    manifestSha256: item.current_revision.content_hash,
                    classification: item.current_revision.classification,
                    lifecycleState: item.current_revision.lifecycle_state,
                  }}
                />
                <DomainWorkflowLinks
                  compact
                  config={config}
                  target={{
                    kind: "test_data",
                    objectId: item.test_data_document_id,
                    revisionId: item.current_revision.id,
                    label: `${item.document_key} r${item.current_revision.revision_no}`,
                  }}
                />
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
