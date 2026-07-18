import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  commitCommonProcessingOutput,
  createCommonMappingProfile,
  downloadCanonicalTestDataDocument,
  downloadCommonProcessingOutput,
  listCanonicalTestDataDocuments,
  listCommonMappingProfiles,
  listCommonProcessingOutputs,
  listCommonProcessingMethods,
  listCommonProcessingEnsembleMethods,
  previewCommonProcessing,
  previewCommonProcessingEnsemble,
  reviseCommonMappingProfile,
  type ApiConfig,
} from "./api";
import type {
  CanonicalTestDataDocumentResponse,
  CommonCurveStage,
  CommonEnsemblePreview,
  CommonMappingProfileContent,
  CommonMappingProfileResponse,
  CommonProcessingMethod,
  CommonProcessingOutputResponse,
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
  return xyPoints(x, y, width, height, bounds);
}

function xyPoints(
  x: number[],
  y: number[],
  width: number,
  height: number,
  bounds: { xMin: number; xMax: number; yMin: number; yMax: number },
): string {
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
  const [ensembleMethods, setEnsembleMethods] = useState<CommonProcessingMethod[]>([]);
  const [outputs, setOutputs] = useState<CommonProcessingOutputResponse[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [document, setDocument] = useState<Record<string, unknown> | null>(null);
  const [profileText, setProfileText] = useState(JSON.stringify(DEFAULT_PROFILE, null, 2));
  const [stepsText, setStepsText] = useState(JSON.stringify(DEFAULT_STEPS, null, 2));
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [changeReason, setChangeReason] = useState("Save reusable channel mapping");
  const [outputLabel, setOutputLabel] = useState("Processed tensile curve");
  const [outputReason, setOutputReason] = useState("Commit reviewed processing stages");
  const [preview, setPreview] = useState<CommonProcessingPreview | null>(null);
  const [selectedStage, setSelectedStage] = useState(0);
  const [ensembleDocumentIds, setEnsembleDocumentIds] = useState<string[]>([]);
  const [ensemblePointCount, setEnsemblePointCount] = useState(21);
  const [ensemblePreview, setEnsemblePreview] = useState<CommonEnsemblePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([
      listCanonicalTestDataDocuments(config),
      listCommonMappingProfiles(config),
      listCommonProcessingMethods(config),
      listCommonProcessingOutputs(config),
      listCommonProcessingEnsembleMethods(config),
    ])
      .then(([documentResult, profileResult, methodResult, outputResult, ensembleMethodResult]) => {
        setDocuments(documentResult.data.items);
        setProfiles(profileResult.data.items);
        setMethods(methodResult.data.items);
        setOutputs(outputResult.data.items);
        setEnsembleMethods(ensembleMethodResult.data.items);
        setSelectedDocumentId((current) => current || documentResult.data.items[0]?.test_data_document_id || "");
        setEnsembleDocumentIds((current) => current.length ? current : documentResult.data.items.slice(0, 2).map((item) => item.test_data_document_id));
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

  async function commitOutput(): Promise<void> {
    const source = documents.find((item) => item.test_data_document_id === selectedDocumentId);
    const profile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
    if (!preview || !source || !profile) {
      setError("Preview an exact Test Data revision with a saved Mapping Profile before commit.");
      return;
    }
    if (preview.mapping_profile_sha256 !== profile.current_revision.content_hash) {
      setError("The preview differs from the selected exact input/profile. Save changes and preview again.");
      return;
    }
    if (source.current_revision.classification !== profile.current_revision.classification) {
      setError("Exact Test Data and Mapping Profile revisions must share classification.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await commitCommonProcessingOutput(config, {
        classification: source.current_revision.classification as DataClassification,
        label: outputLabel,
        source_document: {
          aggregate_id: source.test_data_document_id,
          revision_id: source.current_revision.id,
        },
        mapping_profile: {
          aggregate_id: profile.mapping_profile_id,
          revision_id: profile.current_revision.id,
        },
        steps: JSON.parse(stepsText) as CommonProcessingStep[],
        change_reason: outputReason,
      });
      const refreshed = await listCommonProcessingOutputs(config);
      setOutputs(refreshed.data.items);
      setNotice(
        `Committed immutable Processing Output ${result.data.processing_output_id} · ${result.data.output_sha256.slice(0, 12)}…`,
      );
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid step JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function downloadOutput(output: CommonProcessingOutputResponse): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const result = await downloadCommonProcessingOutput(config, output.processing_output_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded exact Processing Output ${output.output_sha256.slice(0, 12)}…`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function toggleEnsembleDocument(id: string): void {
    setEnsembleDocumentIds((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : current.length < 100 ? [...current, id] : current);
    setEnsemblePreview(null);
  }

  async function runEnsemblePreview(): Promise<void> {
    const selected = documents.filter((item) => ensembleDocumentIds.includes(item.test_data_document_id));
    if (selected.length < 2) {
      setError("Select at least two exact Test Data documents for replicate statistics.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const downloads = await Promise.all(selected.map((item) =>
        downloadCanonicalTestDataDocument(config, item.test_data_document_id, item.current_revision.id)));
      const canonicalDocuments = await Promise.all(downloads.map(async (item) =>
        JSON.parse(await item.data.blob.text()) as Record<string, unknown>));
      const result = await previewCommonProcessingEnsemble(config, {
        documents: canonicalDocuments,
        mapping_profile: JSON.parse(profileText) as CommonMappingProfileContent,
        preprocessing_steps: JSON.parse(stepsText) as CommonProcessingStep[],
        alignment: {
          point_count: ensemblePointCount,
          domain_policy: "intersection",
          extrapolation: "reject",
        },
      });
      setEnsemblePreview(result.data);
      setNotice(`Aligned ${result.data.members.length} immutable curves; every member remains visible.`);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid ensemble JSON: ${caught.message}` : errorMessage(caught));
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
  const ensembleStatistic = ensemblePreview?.statistics[0] ?? null;
  const ensembleBounds = useMemo(() => {
    if (!ensemblePreview || !ensembleStatistic) return null;
    const values = [
      ...ensemblePreview.members.flatMap((member) =>
        member.stage.series.find((series) => series.quantity === ensembleStatistic.quantity)?.values ?? []),
      ...ensembleStatistic.confidence_95_lower,
      ...ensembleStatistic.confidence_95_upper,
    ];
    return {
      xMin: Math.min(...ensemblePreview.grid),
      xMax: Math.max(...ensemblePreview.grid),
      yMin: Math.min(...values),
      yMax: Math.max(...values),
    };
  }, [ensemblePreview, ensembleStatistic]);

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

      <section className="workbench-card processing-output-card">
        <div className="section-heading"><div><p className="eyebrow">5 · immutable output</p><h2>Commit reviewed result</h2></div><span className="status-chip">{outputs.length} committed</span></div>
        <p className="mapping-note">Commit recomputes the selected exact Test Data and saved Mapping Profile on the server. Preview arrays are never accepted as authoritative output.</p>
        <div className="processing-output-form"><label>Output label<input value={outputLabel} onChange={(event) => setOutputLabel(event.target.value)} /></label><label>Change reason<input value={outputReason} onChange={(event) => setOutputReason(event.target.value)} /></label><button className="button primary" type="button" disabled={busy || !preview || !selectedProfileId || !outputLabel.trim() || !outputReason.trim()} onClick={() => void commitOutput()}>Commit immutable output</button></div>
        {outputs.length ? <div className="processing-output-list">{outputs.map((output) => <article key={output.processing_output_id}><div><strong>{output.label}</strong><small>r{output.current_revision.revision_no} · {output.final_point_count} points · {output.stage_count} stages</small><code>{output.output_sha256}</code></div><button className="button secondary" type="button" disabled={busy} onClick={() => void downloadOutput(output)}>Download JSON</button></article>)}</div> : <p className="muted">No committed common Processing Output is visible yet.</p>}
      </section>

      <section className="workbench-card ensemble-card">
        <div className="section-heading"><div><p className="eyebrow">6 · replicate evidence</p><h2>Alignment and pointwise statistics</h2></div><span className="status-chip warning">Preview · members retained</span></div>
        <p className="mapping-note">Select multiple exact Test Data heads. Alignment uses only their observed domain intersection and rejects extrapolation; no raw curve or outlier is deleted.</p>
        <div className="ensemble-methods">{ensembleMethods.map((method) => <article key={method.method_id}><strong>{method.label}</strong><code>{method.method_id} · {method.version}</code><small>{method.description}</small></article>)}</div>
        <div className="ensemble-controls"><fieldset><legend>Exact Test Data members</legend>{documents.map((item) => <label key={item.test_data_document_id}><input type="checkbox" checked={ensembleDocumentIds.includes(item.test_data_document_id)} onChange={() => toggleEnsembleDocument(item.test_data_document_id)} />{item.document_key} · r{item.current_revision.revision_no}</label>)}</fieldset><label>Common grid points<input type="number" min="2" max="100000" value={ensemblePointCount} onChange={(event) => { setEnsemblePointCount(Number(event.target.value)); setEnsemblePreview(null); }} /></label><button className="button primary" type="button" disabled={busy || ensembleDocumentIds.length < 2} onClick={() => void runEnsemblePreview()}>Align and calculate</button></div>
        {ensemblePreview && ensembleStatistic && ensembleBounds ? <div className="ensemble-results"><svg className="processing-curve ensemble-curve" role="img" aria-label="Aligned replicate curves with pointwise mean and confidence interval" viewBox={`0 0 ${chart.width} ${chart.height}`}><line x1="28" y1={chart.height - 24} x2={chart.width - 20} y2={chart.height - 24} className="chart-axis"/><line x1="28" y1="20" x2="28" y2={chart.height - 24} className="chart-axis"/>{ensemblePreview.members.map((member) => { const values = member.stage.series.find((series) => series.quantity === ensembleStatistic.quantity)?.values ?? []; return <polyline key={member.ordinal} points={xyPoints(ensemblePreview.grid, values, chart.width, chart.height, ensembleBounds)} className="curve-line ensemble-member"/>; })}<polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.confidence_95_lower, chart.width, chart.height, ensembleBounds)} className="curve-line confidence"/><polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.confidence_95_upper, chart.width, chart.height, ensembleBounds)} className="curve-line confidence"/><polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.mean, chart.width, chart.height, ensembleBounds)} className="curve-line ensemble-mean"/></svg><div className="curve-legend"><span><i className="ensemble-member"/>Members ({ensemblePreview.members.length})</span><span><i className="ensemble-mean"/>Mean</span><span><i className="confidence"/>95% mean CI</span></div><div className="statistics-grid"><article><span>Quantity</span><strong>{ensembleStatistic.quantity}</strong><small>{ensembleStatistic.unit}</small></article><article><span>Last mean</span><strong>{ensembleStatistic.mean.at(-1)?.toPrecision(6)}</strong></article><article><span>Sample SD</span><strong>{ensembleStatistic.standard_deviation.at(-1)?.toPrecision(6)}</strong></article><article><span>MAD</span><strong>{ensembleStatistic.mad.at(-1)?.toPrecision(6)}</strong></article><article><span>IQR</span><strong>{ensembleStatistic.q1.at(-1)?.toPrecision(4)} – {ensembleStatistic.q3.at(-1)?.toPrecision(4)}</strong></article></div><div className="stage-diagnostics">{ensemblePreview.diagnostics.map((item) => <p key={item}>{item}</p>)}</div></div> : <p className="muted">At least two imported Test Data identities are required. Import each replicate separately so its exact revision remains addressable.</p>}
      </section>
    </main>
  );
}
