import { useEffect, useRef, useState } from "react";

import { ApiError, createReviewRequest, listReviewRequests, type ApiConfig } from "./api";
import type { DataClassification, ReviewRequestResponse } from "./types";

export interface ReviewSubject {
  aggregateType: "catalog.material" | "exporting.solver_card" | "exporting.neutral_solver_card";
  aggregateId: string;
  revisionId: string;
  manifestSha256: string;
  classification: DataClassification;
  lifecycleState: string;
}

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "The review request could not be sent.";
}

function statusFor(request: ReviewRequestResponse): string {
  if (request.decision?.decision === "approved") return "Approved";
  if (request.decision?.decision === "changes_requested" || request.lifecycle_state === "changes_requested") return "Changes requested";
  return "Waiting for review";
}

/** Submits only the immutable revision already loaded by its enclosing workspace. */
export function ReviewRequestAction({ config, subject }: { config: ApiConfig; subject: ReviewSubject | null }) {
  const [reason, setReason] = useState("");
  const [existing, setExisting] = useState<ReviewRequestResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(subject));
  const [submitting, setSubmitting] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const requestSequence = useRef(0);

  useEffect(() => {
    const sequence = ++requestSequence.current;
    setExisting(null);
    setExpanded(false);
    setLoadError(null);
    setSubmitError(null);
    setLoading(Boolean(subject));
    if (!subject) return;
    void listReviewRequests(config, {
      aggregate_type: subject.aggregateType,
      aggregate_id: subject.aggregateId,
      revision_id: subject.revisionId,
      limit: 10,
    }).then((result) => {
      if (sequence !== requestSequence.current) return;
      setExisting(result.data.items.find((item) => item.aggregate_type === subject.aggregateType && item.aggregate_id === subject.aggregateId && item.revision_id === subject.revisionId) ?? null);
    }).catch((cause: unknown) => {
      if (sequence === requestSequence.current) setLoadError(messageFor(cause));
    }).finally(() => {
      if (sequence === requestSequence.current) setLoading(false);
    });
    return () => { requestSequence.current += 1; };
  }, [config.baseUrl, config.accessToken, subject?.aggregateType, subject?.aggregateId, subject?.revisionId, reload]);

  async function submit(): Promise<void> {
    const trimmed = reason.trim();
    if (!subject || existing || !trimmed) {
      if (!trimmed) setSubmitError("Add a reason before requesting review.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await createReviewRequest(config, {
        classification: subject.classification,
        aggregate_type: subject.aggregateType,
        aggregate_id: subject.aggregateId,
        revision_id: subject.revisionId,
        manifest_sha256: subject.manifestSha256,
        reason: trimmed,
      });
      setExisting(result.data);
      setReason("");
    } catch (cause) {
      setSubmitError(messageFor(cause));
    } finally {
      setSubmitting(false);
    }
  }

  if (!subject) return null;
  if (loading) return <div className="review-request-control"><span className="review-request-state" role="status">Checking review status…</span></div>;
  if (existing) return <div className="review-request-control"><span className="review-request-state" role="status">{statusFor(existing)}</span></div>;
  if (loadError) return <div className="review-request-control"><span className="review-request-load-error" role="alert">Review status unavailable. <button className="ux-button tertiary" type="button" onClick={() => setReload((value) => value + 1)}>Retry status</button></span></div>;
  if (subject.lifecycleState !== "draft") return <div className="review-request-control"><span className="review-request-state" role="status">{subject.lifecycleState.replaceAll("_", " ")}</span></div>;
  if (!expanded) return <div className="review-request-control"><button className="ux-button" type="button" onClick={() => setExpanded(true)}>Request review</button></div>;
  return <div className="review-request-control"><form className="review-request-action" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
    <label>Review reason<textarea aria-label="Review request reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="What should the reviewer check?" disabled={submitting} /></label>
    {submitError ? <p role="alert">{submitError} {submitting ? "" : "Correct the reason or Retry."}</p> : null}
    <button className="ux-button" type="submit" disabled={submitting}>{submitting ? "Sending…" : submitError ? "Retry request" : "Send request"}</button>
    <button className="ux-button tertiary" type="button" disabled={submitting} onClick={() => { setExpanded(false); setReason(""); setSubmitError(null); }}>Cancel</button>
  </form></div>;
}
