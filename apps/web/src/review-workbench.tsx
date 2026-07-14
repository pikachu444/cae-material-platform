import { type FormEvent, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  createReviewDecision,
  createReviewRequest,
  listReviewRequests,
} from "./api";
import type {
  DataClassification,
  ReviewDecisionKind,
  ReviewRequestResponse,
} from "./types";

const classifications: DataClassification[] = [
  "internal",
  "confidential",
  "restricted",
  "export_controlled",
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Review request failed.";
}

function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-8)}` : value;
}

export function ReviewWorkbench({ config }: { config: ApiConfig }) {
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [aggregateType, setAggregateType] = useState("catalog.material");
  const [aggregateId, setAggregateId] = useState("");
  const [revisionId, setRevisionId] = useState("");
  const [manifestSha256, setManifestSha256] = useState("");
  const [reason, setReason] = useState("Request domain review");
  const [decision, setDecision] = useState<ReviewDecisionKind>("approved");
  const [decisionReason, setDecisionReason] = useState("Reviewed immutable manifest");
  const [request, setRequest] = useState<ReviewRequestResponse | null>(null);
  const [recent, setRecent] = useState<ReviewRequestResponse[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitRequest(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await createReviewRequest(config, {
        classification,
        aggregate_type: aggregateType.trim(),
        aggregate_id: aggregateId.trim(),
        revision_id: revisionId.trim(),
        manifest_sha256: manifestSha256.trim(),
        reason: reason.trim(),
      });
      setRequest(result.data);
      setRecent((items) => [result.data, ...items.filter((item) => item.review_request_id !== result.data.review_request_id)]);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function submitDecision(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!request) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createReviewDecision(config, request.review_request_id, {
        expected_manifest_sha256: request.manifest_sha256,
        decision,
        reason: decisionReason.trim(),
      });
      setRequest(result.data);
      setRecent((items) => items.map((item) => item.review_request_id === result.data.review_request_id ? result.data : item));
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
      const result = await listReviewRequests(config, { limit: 10 });
      setRecent(result.data.items);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoadingRecent(false);
    }
  }

  return (
    <section className="content-card review-workbench">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Governance</p>
          <h2>Review lifecycle</h2>
        </div>
        <button className="text-button" type="button" onClick={() => void loadRecent()} disabled={loadingRecent}>
          {loadingRecent ? "Loading…" : "Load recent reviews"}
        </button>
      </div>
      <p className="muted">
        Pin a concrete revision and its SHA-256 manifest before requesting review. Decisions are append-only;
        the API enforces tenant scope, stale-manifest checks, and reviewer separation of duties.
      </p>
      <form className="form-stack" onSubmit={submitRequest}>
        <div className="form-grid">
          <label>
            Classification
            <select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}>
              {classifications.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Aggregate type
            <input value={aggregateType} onChange={(event) => setAggregateType(event.target.value)} required />
          </label>
          <label>
            Aggregate ID
            <input value={aggregateId} onChange={(event) => setAggregateId(event.target.value)} placeholder="UUID" required />
          </label>
          <label>
            Revision ID
            <input value={revisionId} onChange={(event) => setRevisionId(event.target.value)} placeholder="UUID" required />
          </label>
        </div>
        <label>
          Manifest SHA-256
          <input value={manifestSha256} onChange={(event) => setManifestSha256(event.target.value)} minLength={64} maxLength={64} pattern="[0-9a-f]{64}" placeholder="64 lowercase hexadecimal characters" required />
        </label>
        <label>
          Request reason
          <input value={reason} onChange={(event) => setReason(event.target.value)} required />
        </label>
        {error ? <p className="error-notice" role="alert">{error}</p> : null}
        <div className="form-actions">
          <button className="button primary" type="submit" disabled={busy}>{busy ? "Submitting…" : "Submit for review"}</button>
        </div>
      </form>
      {request ? (
        <article className="review-request-card">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">Pinned request</p>
              <h3>{request.lifecycle_state.replaceAll("_", " ")}</h3>
            </div>
            <span className={`revision-chip ${request.lifecycle_state}`}>{request.required_role}</span>
          </div>
          <dl className="state-meta">
            <div><dt>Request</dt><dd>{shortId(request.review_request_id)}</dd></div>
            <div><dt>Revision</dt><dd>{shortId(request.revision_id)}</dd></div>
            <div><dt>Manifest</dt><dd>{shortId(request.manifest_sha256)}</dd></div>
          </dl>
          {request.decision ? (
            <p className="muted">Decision: <strong>{request.decision.decision.replaceAll("_", " ")}</strong> — {request.decision.reason}</p>
          ) : request.lifecycle_state === "review" ? (
            <form className="form-stack review-decision-form" onSubmit={submitDecision}>
              <label>
                Decision
                <select value={decision} onChange={(event) => setDecision(event.target.value as ReviewDecisionKind)}>
                  <option value="approved">Approve</option>
                  <option value="changes_requested">Request changes</option>
                </select>
              </label>
              <label>
                Decision reason
                <input value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} required />
              </label>
              <div className="form-actions"><button className="button secondary" type="submit" disabled={busy}>Record decision</button></div>
            </form>
          ) : null}
        </article>
      ) : null}
      {recent.length ? (
        <div className="review-list">
          <p className="eyebrow">Recent requests</p>
          {recent.map((item) => (
            <button className="review-list-item" type="button" key={item.review_request_id} onClick={() => setRequest(item)}>
              <span>{item.lifecycle_state.replaceAll("_", " ")}</span>
              <small>{item.aggregate_type} · {shortId(item.revision_id)}</small>
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}
