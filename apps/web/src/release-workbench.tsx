import { type FormEvent, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  getAuthenticatedPrincipal,
} from "./shared/api";
import {
  createRelease,
  downloadRelease,
  getReleaseImpact,
  listReleases,
  supersedeRelease,
  withdrawRelease,
} from "./features/activity";
import type {
  DataClassification,
  ReleaseCreateInput,
  ReleaseImpactResponse,
  ReleaseResponse,
} from "./types";
import { appendActivityFailure, appendActivityOutcome } from "./activity-recovery";

const classifications: DataClassification[] = [
  "internal",
  "confidential",
  "restricted",
  "export_controlled",
];

const textFields = [
  "release_code",
  "title",
  "material_id",
  "material_revision_id",
  "material_state_id",
  "material_state_revision_id",
  "property_set_id",
  "property_set_revision_id",
  "material_model_id",
  "material_model_revision_id",
  "material_model_content_sha256",
  "solver_card_id",
  "solver_card_revision_id",
  "solver_card_content_sha256",
  "mapping_report_sha256",
  "card_sha256",
  "validation_result_id",
  "validation_result_sha256",
  "review_request_id",
  "review_manifest_sha256",
  "provenance_snapshot_sha256",
  "reason",
] as const satisfies ReadonlyArray<Exclude<keyof ReleaseCreateInput, "classification">>;

type TextField = (typeof textFields)[number];

const emptyInput: ReleaseCreateInput = {
  classification: "internal",
  release_code: "reference-release",
  title: "Reference release",
  material_id: "",
  material_revision_id: "",
  material_state_id: "",
  material_state_revision_id: "",
  property_set_id: "",
  property_set_revision_id: "",
  material_model_id: "",
  material_model_revision_id: "",
  material_model_content_sha256: "",
  solver_card_id: "",
  solver_card_revision_id: "",
  solver_card_content_sha256: "",
  mapping_report_sha256: "",
  card_sha256: "",
  validation_result_id: "",
  validation_result_sha256: "",
  review_request_id: "",
  review_manifest_sha256: "",
  provenance_snapshot_sha256: "",
  reason: "Release the approved reference candidate",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Release request failed.";
}

async function recordReleaseRecovery(
  config: ApiConfig,
  releaseId: string,
  status: "failed" | "succeeded",
  message: string,
): Promise<void> {
  try {
    const principal = await getAuthenticatedPrincipal(config);
    const context = { kind: "release_manifest" as const, path: `/releases/${releaseId}/download`, releaseId };
    const args = [
      principal.data.principal_id,
      principal.data.organization_id,
      principal.data.project_id,
      "activity" as const,
      context,
      message,
    ] as const;
    if (status === "failed") appendActivityFailure(...args);
    else appendActivityOutcome(...args);
  } catch {
    // Local recovery is optional; release state and package digest remain server-authoritative.
  }
}

function labelFor(field: TextField): string {
  return field
    .replaceAll("_sha256", " SHA-256")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (value) => value.toUpperCase());
}

function shortId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-8)}` : value;
}

export function ReleaseWorkbench({ config }: { config: ApiConfig }) {
  const [input, setInput] = useState<ReleaseCreateInput>(emptyInput);
  const [releases, setReleases] = useState<ReleaseResponse[]>([]);
  const [selected, setSelected] = useState<ReleaseResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [successorReleaseId, setSuccessorReleaseId] = useState("");
  const [transitionReason, setTransitionReason] = useState("Replace this release with the approved successor");
  const [impact, setImpact] = useState<ReleaseImpactResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function setTextField(field: TextField, value: string): void {
    setInput((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await createRelease(config, {
        ...input,
        release_code: input.release_code.trim(),
        title: input.title.trim(),
        reason: input.reason.trim(),
      });
      setSelected(result.data);
      setImpact(null);
      setReleases((items) => [result.data, ...items.filter((item) => item.release_id !== result.data.release_id)]);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function loadRecent(): Promise<void> {
    setLoadingRecent(true);
    setError(null);
    try {
      const result = await listReleases(config, 10);
      setReleases(result.data.items);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoadingRecent(false);
    }
  }

  async function downloadSelected(): Promise<void> {
    if (!selected || selected.lifecycle_state !== "released") return;
    setDownloading(true);
    setError(null);
    try {
      const result = await downloadRelease(config, selected.release_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      anchor.click();
      URL.revokeObjectURL(url);
      void recordReleaseRecovery(config, selected.release_id, "succeeded", "Downloaded the exact released package manifest.");
    } catch (cause) {
      setError(errorMessage(cause));
      void recordReleaseRecovery(config, selected.release_id, "failed", errorMessage(cause));
    } finally {
      setDownloading(false);
    }
  }

  function updateRelease(value: ReleaseResponse): void {
    setSelected(value);
    setReleases((items) => [value, ...items.filter((item) => item.release_id !== value.release_id)]);
  }

  async function supersedeSelected(): Promise<void> {
    if (!selected || selected.lifecycle_state !== "released" || !successorReleaseId.trim()) return;
    setTransitioning(true);
    setError(null);
    try {
      const result = await supersedeRelease(config, selected.release_id, {
        successor_release_id: successorReleaseId.trim(),
        reason: transitionReason.trim(),
      });
      updateRelease(result.data);
      setImpact(null);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setTransitioning(false);
    }
  }

  async function withdrawSelected(): Promise<void> {
    if (!selected || selected.lifecycle_state !== "released") return;
    setTransitioning(true);
    setError(null);
    try {
      const result = await withdrawRelease(config, selected.release_id, {
        reason: transitionReason.trim(),
      });
      updateRelease(result.data);
      setImpact(null);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setTransitioning(false);
    }
  }

  async function loadImpact(): Promise<void> {
    if (!selected) return;
    setError(null);
    try {
      const result = await getReleaseImpact(config, selected.release_id);
      setImpact(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  return (
    <section className="content-card release-workbench" aria-labelledby="release-workbench-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Governance · reference channel</p>
          <h2 id="release-workbench-title">Release completeness gate</h2>
        </div>
        <button className="text-button" type="button" onClick={() => void loadRecent()} disabled={loadingRecent}>
          {loadingRecent ? "Loading…" : "Load recent releases"}
        </button>
      </div>
      <p className="muted">
        Publish one digest-fixed package only after the Material Model, Solver Card, passed Validation Result,
        approved Review decision, and provenance snapshot all identify the same candidate. Draft, approximated,
        unsupported or incompatible inputs are rejected before release.
      </p>
      <form className="form-stack" onSubmit={submit}>
        <div className="form-grid">
          <label>
            Classification
            <select
              value={input.classification}
              onChange={(event) => setInput((current) => ({ ...current, classification: event.target.value as DataClassification }))}
            >
              {classifications.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          {textFields.slice(0, 2).map((field) => (
            <label key={field}>
              {labelFor(field)}
              <input value={input[field]} onChange={(event) => setTextField(field, event.target.value)} required />
            </label>
          ))}
        </div>
        <details>
          <summary>Candidate component identities and digests</summary>
          <div className="form-grid release-component-grid">
            {textFields.slice(2).map((field) => (
              <label key={field}>
                {labelFor(field)}
                <input
                  value={input[field]}
                  onChange={(event) => setTextField(field, event.target.value)}
                  placeholder={field.includes("sha256") || field === "mapping_report_sha256" || field === "card_sha256" ? "64 lowercase hexadecimal characters" : "UUID"}
                  required
                />
              </label>
            ))}
          </div>
        </details>
        {error ? <p className="error-notice" role="alert">{error}</p> : null}
        <div className="form-actions">
          <button className="button primary" type="submit" disabled={busy}>
            {busy ? "Checking completeness…" : "Create immutable Release"}
          </button>
        </div>
      </form>
      {selected ? (
        <article className="release-result">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">{selected.lifecycle_state} · {selected.channel}</p>
              <h3>{selected.title}</h3>
            </div>
            <span className="revision-chip">{selected.release_code}</span>
          </div>
          <dl className="state-meta">
            <div><dt>Release</dt><dd>{shortId(selected.release_id)}</dd></div>
            <div><dt>Manifest</dt><dd>{shortId(selected.manifest.manifest_sha256)}</dd></div>
            <div><dt>Package</dt><dd>{selected.manifest.package_size_bytes.toLocaleString()} bytes</dd></div>
            <div><dt>Lifecycle</dt><dd>{selected.lifecycle_state}</dd></div>
          </dl>
          <button
            className="button secondary"
            type="button"
            onClick={() => void downloadSelected()}
            disabled={downloading || selected.lifecycle_state !== "released"}
          >
            {downloading ? "Preparing package…" : "Download release package"}
          </button>
          <div className="form-actions">
            <button className="button secondary" type="button" onClick={() => void loadImpact()}>
              View impact
            </button>
          </div>
          {selected.lifecycle_state === "released" ? (
            <div className="release-transition-panel">
              <label>
                Successor Release ID
                <input
                  value={successorReleaseId}
                  onChange={(event) => setSuccessorReleaseId(event.target.value)}
                  placeholder="UUID for explicit supersede"
                />
              </label>
              <label>
                Transition reason
                <input value={transitionReason} onChange={(event) => setTransitionReason(event.target.value)} />
              </label>
              <div className="form-actions">
                <button className="button secondary" type="button" onClick={() => void supersedeSelected()} disabled={transitioning || !successorReleaseId.trim()}>
                  Supersede
                </button>
                <button className="button danger" type="button" onClick={() => void withdrawSelected()} disabled={transitioning}>
                  Withdraw
                </button>
              </div>
            </div>
          ) : (
            <p className="warning-notice">This Release is terminal. Its immutable package remains available for audit, but it cannot be downloaded or consumed for new work.</p>
          )}
          {impact ? (
            <div className="release-impact" aria-live="polite">
              <p className="eyebrow">Lifecycle impact</p>
              {impact.warning ? <p className="warning-notice">{impact.warning}</p> : <p className="muted">No lifecycle warning.</p>}
              <p className="muted">Predecessor: {impact.predecessor_release_id ? shortId(impact.predecessor_release_id) : "none"} · Successor: {impact.successor_release_id ? shortId(impact.successor_release_id) : "none"}</p>
              <p className="muted">Recorded usage events: {impact.usages.length} · Lifecycle transitions: {impact.transitions.length}</p>
            </div>
          ) : null}
        </article>
      ) : null}
      {releases.length ? (
        <div className="review-list">
          <p className="eyebrow">Recent immutable Releases</p>
          {releases.map((item) => (
            <button className="review-list-item" type="button" key={item.release_id} onClick={() => setSelected(item)}>
              <span>{item.release_code}</span>
              <small>{item.title} · {shortId(item.manifest.manifest_sha256)}</small>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
