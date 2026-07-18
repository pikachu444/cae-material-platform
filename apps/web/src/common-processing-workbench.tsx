import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createCommonMappingProfile,
  downloadCanonicalTestDataDocument,
  listCanonicalTestDataDocuments,
  listCommonMappingProfiles,
  listCommonProcessingMethods,
  previewCommonProcessing,
  reviseCommonMappingProfile,
  type ApiConfig,
} from "./api";
import type {
  CanonicalTestDataDocumentResponse,
  CommonCurveStage,
  CommonMappingProfileContent,
  CommonMappingProfileResponse,
  CommonProcessingMethod,
  CommonProcessingPreview,
  CommonProcessingStep,
  DataClassification,
} from "./types";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}

const DEFAULT_PROFILE: CommonMappingProfileContent = {
  profile_key: "normalized-tensile",
  label: "Normalized tensile channels",
  independent_quantity: "strain.engineering",
  missing_data_policy: "drop_any",
  bindings: [
    {
      channel_key: "engineering_strain",
      target_quantity: "strain.engineering",
      accepted_normalized_units: ["1"],
      required: true,
      scale: 1,
      offset: 0,
    },
    {
      channel_key: "engineering_stress",
      target_quantity: "stress.engineering",
      accepted_normalized_units: ["Pa"],
      required: true,
      scale: 1,
      offset: 0,
    },
  ],
  attribute_bindings: [],
};

const DEFAULT_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
];

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "The Processing Workbench operation failed.";
}

function defaultOptions(methodId: string): Record<string, unknown> {
  const options: Record<string, Record<string, unknown>> = {
    "rows.sort_unique": { duplicate_policy: "reject" },
    "curve.crop": { minimum: 0, maximum: 0.001 },
    "curve.scale_shift": { quantity: "stress.engineering", scale: 1, offset: 0 },
    "curve.resample_linear": { start: 0, end: 0.001, count: 21, extrapolation: "reject" },
    "curve.moving_average": { quantity: "stress.engineering", window: 3 },
    "curve.savitzky_golay": { quantity: "stress.engineering", window: 5, polynomial_order: 2 },
    "curve.smoothing_spline": { quantity: "stress.engineering", smoothing_factor: 0 },
  };
  return options[methodId] ?? {};
}

function curvePoints(
  stage: CommonCurveStage,
  independentQuantity: string,
  width: number,
  height: number,
  bounds: { xMin: number; xMax: number; yMin: number; yMax: number },
): string {
  const x = stage.series.find((item) => item.quantity === independentQuantity)?.values ?? [];
  const y = stage.series.find((item) => item.quantity !== independentQuantity)?.values ?? [];
  if (x.length < 2 || y.length !== x.length) return "";
  const { xMin, xMax, yMin, yMax } = bounds;
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  return x
    .map((value, index) => {
      const px = 28 + ((value - xMin) / xRange) * (width - 48);
      const py = height - 24 - ((y[index] - yMin) / yRange) * (height - 44);
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .join(" ");
}

function curveBounds(
  stages: CommonCurveStage[],
  independentQuantity: string,
): { xMin: number; xMax: number; yMin: number; yMax: number } {
  const x = stages.flatMap(
    (stage) => stage.series.find((item) => item.quantity === independentQuantity)?.values ?? [],
  );
  const y = stages.flatMap(
    (stage) => stage.series.find((item) => item.quantity !== independentQuantity)?.values ?? [],
  );
  return {
    xMin: Math.min(...x),
    xMax: Math.max(...x),
    yMin: Math.min(...y),
    yMax: Math.max(...y),
  };
}

export function CommonProcessingWorkbench({ config, onNavigate, onOpenConnection }: Props) {
  const [documents, setDocuments] = useState<CanonicalTestDataDocumentResponse[]>([]);
  const [profiles, setProfiles] = useState<CommonMappingProfileResponse[]>([]);
  const [methods, setMethods] = useState<CommonProcessingMethod[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [document, setDocument] = useState<Record<string, unknown> | null>(null);
  const [profileText, setProfileText] = useState(JSON.stringify(DEFAULT_PROFILE, null, 2));
  const [stepsText, setStepsText] = useState(JSON.stringify(DEFAULT_STEPS, null, 2));
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [changeReason, setChangeReason] = useState("Save reusable channel mapping");
  const [preview, setPreview] = useState<CommonProcessingPreview | null>(null);
  const [selectedStage, setSelectedStage] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([
      listCanonicalTestDataDocuments(config),
      listCommonMappingProfiles(config),
      listCommonProcessingMethods(config),
    ])
      .then(([documentResult, profileResult, methodResult]) => {
        setDocuments(documentResult.data.items);
        setProfiles(profileResult.data.items);
        setMethods(methodResult.data.items);
        setSelectedDocumentId((current) => current || documentResult.data.items[0]?.test_data_document_id || "");
      })
      .catch((caught: unknown) => setError(errorMessage(caught)));
  }, [config]);

  async function loadDocument(id: string): Promise<void> {
    setSelectedDocumentId(id);
    setPreview(null);
    const item = documents.find((candidate) => candidate.test_data_document_id === id);
    if (!item) {
      setDocument(null);
      return;
    }
    setBusy(true);
    try {
      const result = await downloadCanonicalTestDataDocument(
        config,
        item.test_data_document_id,
        item.current_revision.id,
      );
      setDocument(JSON.parse(await result.data.blob.text()) as Record<string, unknown>);
      setNotice(`Loaded exact Test Data revision ${item.current_revision.revision_no}.`);
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function selectProfile(id: string): void {
    setSelectedProfileId(id);
    const item = profiles.find((candidate) => candidate.mapping_profile_id === id);
    if (item) setProfileText(JSON.stringify(item.content, null, 2));
  }

  function addMethod(method: CommonProcessingMethod): void {
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      steps.push({ method_id: method.method_id, method_version: method.version, options: defaultOptions(method.method_id) });
      setStepsText(JSON.stringify(steps, null, 2));
      setError(null);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? caught.message : errorMessage(caught));
    }
  }

  async function saveProfile(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const content = JSON.parse(profileText) as CommonMappingProfileContent;
      const selected = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
      const result = selected
        ? await reviseCommonMappingProfile(
            config,
            selected.mapping_profile_id,
            `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`,
            { content, change_reason: changeReason },
          )
        : await createCommonMappingProfile(config, { classification, content, change_reason: changeReason });
      setSelectedProfileId(result.data.mapping_profile_id);
      const refreshed = await listCommonMappingProfiles(config);
      setProfiles(refreshed.data.items);
      setNotice(`Saved Mapping Profile revision ${result.data.current_revision.revision_no}.`);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid profile JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function runPreview(): Promise<void> {
    if (!document) {
      setError("Load one exact Test Data revision before previewing processing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await previewCommonProcessing(config, {
        document,
        mapping_profile: JSON.parse(profileText) as CommonMappingProfileContent,
        steps: JSON.parse(stepsText) as CommonProcessingStep[],
      });
      setPreview(result.data);
      setSelectedStage(result.data.stages.length - 1);
      setNotice("Preview completed. It is ephemeral and cannot be promoted or released.");
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid Workbench JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  const activeStage = preview?.stages[selectedStage] ?? null;
  const baseStage = preview?.stages[0] ?? null;
  const overlayBounds = useMemo(
    () => preview && activeStage && baseStage
      ? curveBounds([baseStage, activeStage], preview.independent_quantity)
      : null,
    [activeStage, baseStage, preview],
  );
  const chart = useMemo(() => ({ width: 620, height: 250 }), []);

  return (
    <main className="processing-workbench-page">
      <section className="page-hero compact-hero processing-hero">
        <div><p className="eyebrow">T-53 · configurable processing</p><h1>Processing Workbench</h1><p>Pin Test Data, reuse a Mapping Profile, compose versioned methods, and inspect every curve stage before commit.</p></div>
        <div className="hero-actions"><button className="button secondary" type="button" onClick={() => onNavigate("/datasets/test-json")}>Test Data JSON</button><button className="button secondary" type="button" onClick={onOpenConnection}>Connection</button></div>
      </section>
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {notice ? <div className="success-banner" role="status">{notice}</div> : null}

      <section className="processing-setup-grid">
        <article className="workbench-card processing-input-card">
          <p className="eyebrow">1 · exact input</p><h2>Test Data revision</h2>
          <label>Imported document<select aria-label="Test Data revision" value={selectedDocumentId} onChange={(event) => void loadDocument(event.target.value)}><option value="">Choose a document</option>{documents.map((item) => <option key={item.test_data_document_id} value={item.test_data_document_id}>{item.document_key} · r{item.current_revision.revision_no}</option>)}</select></label>
          <button className="button secondary" type="button" disabled={!selectedDocumentId || busy} onClick={() => void loadDocument(selectedDocumentId)}>Load exact JSON</button>
          {document ? <p className="mapping-note">Loaded <code>{String(document.document_id)}</code>. Original and normalized arrays remain unchanged.</p> : <p className="muted">Import Test Data JSON first, then load its exact revision.</p>}
        </article>

        <article className="workbench-card mapping-profile-card">
          <div className="section-heading"><div><p className="eyebrow">2 · reusable contract</p><h2>Mapping Profile</h2></div><span className="status-chip">{profiles.length} saved</span></div>
          <label>Saved profile<select aria-label="Saved Mapping Profile" value={selectedProfileId} onChange={(event) => selectProfile(event.target.value)}><option value="">New profile</option>{profiles.map((item) => <option key={item.mapping_profile_id} value={item.mapping_profile_id}>{item.content.label} · r{item.current_revision.revision_no}</option>)}</select></label>
          <label>Profile JSON<textarea className="mapping-profile-editor" aria-label="Mapping Profile JSON" value={profileText} onChange={(event) => setProfileText(event.target.value)} spellCheck={false} /></label>
          <div className="profile-save-row"><label>Classification<select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}><option value="internal">Internal</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option><option value="export_controlled">Export controlled</option></select></label><label>Change reason<input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} /></label><button className="button primary" type="button" disabled={busy || !changeReason.trim()} onClick={() => void saveProfile()}>{selectedProfileId ? "Append profile revision" : "Save new profile"}</button></div>
        </article>
      </section>

      <section className="workbench-card method-builder-card">
        <div className="section-heading"><div><p className="eyebrow">3 · ordered methods</p><h2>Pipeline builder</h2></div><button className="button primary" type="button" disabled={busy} onClick={() => void runPreview()}>{busy ? "Working…" : "Preview all stages"}</button></div>
        <div className="method-registry-strip">{methods.map((method) => <button type="button" className="method-pill" key={method.method_id} onClick={() => addMethod(method)} title={method.description}><strong>{method.label}</strong><small>{method.method_id} · {method.version}</small></button>)}</div>
        <label>Ordered step JSON<textarea className="pipeline-editor" aria-label="Ordered processing steps" value={stepsText} onChange={(event) => { setStepsText(event.target.value); setPreview(null); }} spellCheck={false} /></label>
        <p className="mapping-note">Methods are deterministic. The common resampler declares <code>extrapolation: reject</code>; unsupported or hidden policies fail before calculation.</p>
      </section>

      <section className="processing-result-grid">
        <article className="workbench-card stage-list-card">
          <p className="eyebrow">4 · immutable stage view</p><h2>Stage history</h2>
          {preview ? <div className="stage-list">{preview.stages.map((stage) => <button className={selectedStage === stage.ordinal ? "stage-item active" : "stage-item"} type="button" key={`${stage.ordinal}-${stage.method_id}`} onClick={() => setSelectedStage(stage.ordinal)}><span>{stage.ordinal}</span><div><strong>{stage.method_id}</strong><small>{stage.point_count} points · {stage.method_version}</small></div></button>)}</div> : <p className="muted">Run a preview to preserve and compare the mapped and processed stages.</p>}
        </article>
        <article className="workbench-card curve-overlay-card">
          <div className="section-heading"><div><p className="eyebrow">Curve overlay</p><h2>{activeStage?.method_id ?? "Awaiting preview"}</h2></div>{preview ? <span className="status-chip warning">Preview only · not promotable</span> : null}</div>
          {preview && activeStage && baseStage && overlayBounds ? <><svg className="processing-curve" role="img" aria-label="Mapped and selected processing stage curve overlay" viewBox={`0 0 ${chart.width} ${chart.height}`}><line x1="28" y1={chart.height - 24} x2={chart.width - 20} y2={chart.height - 24} className="chart-axis"/><line x1="28" y1="20" x2="28" y2={chart.height - 24} className="chart-axis"/><polyline points={curvePoints(baseStage, preview.independent_quantity, chart.width, chart.height, overlayBounds)} className="curve-line source"/><polyline points={curvePoints(activeStage, preview.independent_quantity, chart.width, chart.height, overlayBounds)} className="curve-line processed"/></svg><div className="curve-legend"><span><i className="source"/>Mapped input</span><span><i className="processed"/>Selected stage</span></div><div className="stage-diagnostics">{activeStage.diagnostics.map((item) => <p key={item}>{item}</p>)}</div><p className="digest-line"><span>Mapping SHA-256</span><code>{preview.mapping_profile_sha256}</code></p></> : <p className="muted">The overlay uses the actual server result. No browser-only curve is treated as evidence.</p>}
        </article>
      </section>
    </main>
  );
}
