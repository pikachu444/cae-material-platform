import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createBulkExportJob,
  createBulkExportSelection,
  downloadBulkExportBundle,
  listBulkExportBundles,
  listBulkExportCandidates,
  listBulkExportJobs,
  listMaterials,
} from "./api";
import type {
  BulkExportBundleResponse,
  BulkExportCandidate,
  BulkExportMemberKind,
  BulkExportJobResponse,
  DataClassification,
  MaterialResponse,
} from "./types";

const kindLabels: Record<BulkExportMemberKind, string> = {
  raw_original: "Raw original",
  dataset_parquet: "Dataset · Parquet",
  dataset_csv: "Dataset · readable CSV",
  model_ir_json: "Material Model IR",
  model_ir_schema: "IR JSON Schema",
  solver_mapping_report: "Solver mapping report",
  solver_card_native: "Native Solver Card",
};

const rank: Record<DataClassification, number> = {
  internal: 0,
  confidential: 1,
  restricted: 2,
  export_controlled: 3,
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "The immutable export request could not be completed.";
}

function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function maximumClassification(values: BulkExportCandidate[]): DataClassification {
  return values.reduce<DataClassification>(
    (maximum, item) => rank[item.classification] > rank[maximum] ? item.classification : maximum,
    "internal",
  );
}

function candidateKey(candidate: BulkExportCandidate): string {
  return `${candidate.source.kind}:${candidate.default_archive_path}`;
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function BulkExportCenter({
  config,
  onOpenConnection,
}: {
  config: ApiConfig;
  onOpenConnection: () => void;
}) {
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [materialId, setMaterialId] = useState("");
  const [candidates, setCandidates] = useState<BulkExportCandidate[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bundles, setBundles] = useState<BulkExportBundleResponse[]>([]);
  const [jobs, setJobs] = useState<BulkExportJobResponse[]>([]);
  const [busy, setBusy] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!config.accessToken.trim()) return;
    let live = true;
    void Promise.all([
      listMaterials(config, ""),
      listBulkExportBundles(config),
      listBulkExportJobs(config),
    ])
      .then(([materialResult, bundleResult, jobResult]) => {
        if (!live) return;
        setMaterials(materialResult.data.items);
        setBundles(bundleResult.data.items);
        setJobs(jobResult.data.items);
        setMaterialId((current) => current || materialResult.data.items[0]?.material_id || "");
      })
      .catch((cause) => live && setError(errorMessage(cause)));
    return () => { live = false; };
  }, [config]);

  useEffect(() => {
    if (
      !config.accessToken.trim()
      || !jobs.some((job) => [
        "queued", "running", "reconciliation_required", "reconciling",
      ].includes(job.state))
    ) return;
    const timer = window.setInterval(() => {
      void Promise.all([listBulkExportJobs(config), listBulkExportBundles(config)])
        .then(([jobResult, bundleResult]) => {
          setJobs(jobResult.data.items);
          setBundles(bundleResult.data.items);
        })
        .catch((cause) => setError(errorMessage(cause)));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [config, jobs]);

  useEffect(() => {
    if (!materialId || !config.accessToken.trim()) {
      setCandidates([]);
      setSelected(new Set());
      return;
    }
    let live = true;
    setDiscovering(true);
    setError(null);
    void listBulkExportCandidates(config, materialId)
      .then((result) => {
        if (!live) return;
        setCandidates(result.data.items);
        setSelected(new Set());
      })
      .catch((cause) => live && setError(errorMessage(cause)))
      .finally(() => live && setDiscovering(false));
    return () => { live = false; };
  }, [config, materialId]);

  const chosen = useMemo(
    () => candidates.filter((candidate) => selected.has(candidateKey(candidate))),
    [candidates, selected],
  );
  const grouped = useMemo(() => {
    const result = new Map<BulkExportMemberKind, BulkExportCandidate[]>();
    for (const candidate of candidates) {
      result.set(candidate.source.kind, [...(result.get(candidate.source.kind) ?? []), candidate]);
    }
    return [...result.entries()];
  }, [candidates]);
  const selectedMaterial = materials.find((material) => material.material_id === materialId);

  function toggle(candidate: BulkExportCandidate): void {
    const key = candidateKey(candidate);
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  async function assemble(): Promise<void> {
    if (!chosen.length || !selectedMaterial) return;
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const label = `${selectedMaterial.current_revision.content.name} governed transfer`;
      const selection = await createBulkExportSelection(config, {
        classification: maximumClassification(chosen),
        selection_label: label,
        members: chosen.map((candidate, index) => ({
          ordinal: index + 1,
          source: candidate.source,
          required: true,
          archive_path: candidate.default_archive_path,
        })),
        change_reason: "Assemble an explicit user-selected Material transfer bundle",
      });
      const job = await createBulkExportJob(config, selection.data.export_selection_id);
      const [refreshedJobs, refreshedBundles] = await Promise.all([
        listBulkExportJobs(config),
        listBulkExportBundles(config),
      ]);
      setJobs(refreshedJobs.data.items);
      setBundles(refreshedBundles.data.items);
      setSuccess(job.data.state === "succeeded"
        ? `Bundle ${job.data.bundle_id?.slice(0, 8)} assembled from ${chosen.length} exact revisions.`
        : `Assembly job ${job.data.export_job_id.slice(0, 8)} queued for the external worker.`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function download(bundle: BulkExportBundleResponse): Promise<void> {
    setDownloading(bundle.export_bundle_id);
    setError(null);
    try {
      const result = await downloadBulkExportBundle(config, bundle.export_bundle_id);
      saveBlob(result.data.blob, result.data.filename);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setDownloading(null);
    }
  }

  if (!config.accessToken.trim()) {
    return (
      <section className="content-card empty-state">
        <p className="eyebrow">Governed transfer</p>
        <h1>Bulk Export Center</h1>
        <p>Connect to the protected API to assemble immutable Material transfer bundles.</p>
        <button className="button primary" type="button" onClick={onOpenConnection}>Connection</button>
      </section>
    );
  }

  return (
    <div className="page-stack bulk-export-center">
      <section className="page-heading export-hero">
        <div>
          <p className="eyebrow">Material → neutral data → Solver Card</p>
          <h1>Bulk Export Center</h1>
          <p className="muted">
            Choose exact immutable revisions. Every ZIP includes a manifest, SHA-256 checksums,
            classification, and explicit omissions. Transfer authorization is not a Release approval.
          </p>
        </div>
        <span className="revision-chip">T-45 · deterministic bundle</span>
      </section>

      {error ? <p className="error-notice" role="alert">{error}</p> : null}
      {success ? <p className="success-notice" role="status">{success}</p> : null}

      <section className="content-card export-builder">
        <div className="section-heading">
          <div>
            <p className="eyebrow">1. Source scope</p>
            <h2>Select a Material</h2>
          </div>
          <label className="compact-field">
            Material
            <select value={materialId} onChange={(event) => setMaterialId(event.target.value)}>
              {materials.map((material) => (
                <option key={material.material_id} value={material.material_id}>
                  {material.current_revision.content.name} · {material.current_revision.content.material_code}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="export-toolbar">
          <div>
            <strong>{chosen.length}</strong> of {candidates.length} exact representations selected
            <small>{bytes(chosen.reduce((total, item) => total + item.source_size_bytes, 0))} expected</small>
          </div>
          <div className="card-actions">
            <button className="text-button" type="button" onClick={() => setSelected(new Set(candidates.map(candidateKey)))}>
              Select all
            </button>
            <button className="text-button" type="button" onClick={() => setSelected(new Set())}>
              Clear
            </button>
            <button className="button primary" type="button" disabled={!chosen.length || busy} onClick={() => void assemble()}>
              {busy ? "Assembling…" : "Create immutable ZIP"}
            </button>
          </div>
        </div>

        {discovering ? <p className="muted">Discovering visible exact revisions…</p> : null}
        {!discovering && !candidates.length ? (
          <p className="muted">No governed Dataset, Material Model IR, or Solver Card revision is available for this Material yet.</p>
        ) : null}
        <div className="export-groups">
          {grouped.map(([kind, items]) => (
            <section key={kind} className="export-group" aria-label={kindLabels[kind]}>
              <div className="export-group-title">
                <h3>{kindLabels[kind]}</h3><span>{items.length}</span>
              </div>
              {items.map((candidate) => {
                const key = candidateKey(candidate);
                return (
                  <label className="export-candidate" key={key}>
                    <input type="checkbox" checked={selected.has(key)} onChange={() => toggle(candidate)} />
                    <span>
                      <strong>{candidate.label}</strong>
                      <small>{candidate.default_archive_path}</small>
                    </span>
                    <span className={`classification-badge ${candidate.classification}`}>
                      {candidate.classification}
                    </span>
                    <small className="export-size">{bytes(candidate.source_size_bytes)}</small>
                  </label>
                );
              })}
            </section>
          ))}
        </div>
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">2. Durable assembly</p>
            <h2>Jobs and committed output</h2>
          </div>
          <span className="revision-chip">{jobs.length} recorded</span>
        </div>
        {!jobs.length ? <p className="muted">No Bundle assembly job has been submitted.</p> : null}
        <div className="bundle-list">
          {jobs.map((job) => (
            <article className="bundle-row" key={job.export_job_id}>
              <div>
                <strong>Job {job.export_job_id.slice(0, 8)}</strong>
                <small>
                  {job.state.replaceAll("_", " ")} · attempt {job.attempt_count} · {new Date(job.submitted_at).toLocaleString()}
                </small>
                {job.committed_output ? (
                  <>
                    <small>Immutable output committed · {bytes(job.committed_output.archive_size_bytes)}</small>
                    <code>{job.committed_output.archive_sha256}</code>
                  </>
                ) : null}
                {job.lease_expires_at ? (
                  <small>
                    Worker heartbeat {job.heartbeat_at ? new Date(job.heartbeat_at).toLocaleTimeString() : "pending"}
                    {" · "}recoverable after {new Date(job.lease_expires_at).toLocaleTimeString()}
                  </small>
                ) : null}
                {job.failure_detail ? <small className="error-text">{job.failure_detail}</small> : null}
              </div>
              <div className="card-actions">
                <span className="revision-chip">{job.state}</span>
                {job.state === "reconciliation_required" ? (
                  <span className="classification-badge restricted">output preserved</span>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div><p className="eyebrow">3. Governed output</p><h2>Immutable bundles</h2></div>
          <span className="revision-chip">{bundles.length} available</span>
        </div>
        {!bundles.length ? <p className="muted">No bundle has been assembled in this project.</p> : null}
        <div className="bundle-list">
          {bundles.map((bundle) => (
            <article className="bundle-row" key={bundle.export_bundle_id}>
              <div>
                <strong>Bundle {bundle.export_bundle_id.slice(0, 8)}</strong>
                <small>{bundle.component_count} components · {bytes(bundle.archive_size_bytes)} · {new Date(bundle.created_at).toLocaleString()}</small>
                <code>{bundle.archive_sha256}</code>
              </div>
              <div className="card-actions">
                <span className={`classification-badge ${bundle.classification}`}>{bundle.classification}</span>
                <button className="button secondary" type="button" disabled={downloading === bundle.export_bundle_id} onClick={() => void download(bundle)}>
                  {downloading === bundle.export_bundle_id ? "Authorizing…" : "Download ZIP"}
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
