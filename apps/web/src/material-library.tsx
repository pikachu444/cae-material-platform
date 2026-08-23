import { Fragment, type FormEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  createReviewDecision,
  getAuthenticatedPrincipal,
  getEffectiveProductAccess,
  listCanonicalTestDataDocuments,
  listCommonProcessingBatches,
  listMaterials,
  listReviewRequests,
  retryFailedCommonProcessingBatch,
  type ApiConfig,
} from "./api";
import type {
  CanonicalTestDataDocumentResponse,
  CommonProcessingBatchResponse,
  MaterialResponse,
  ProductRole,
  ReviewRequestResponse,
} from "./types";
import { MaterialsScrollRegion } from "./materials-scroll-rail";
import { publishWorkspaceStatus } from "./design/application-shell";
import { loadModelingSession } from "./modeling-session-context";
import { loadDeliveryActivities } from "./solver-card-delivery";
import {
  appendActivityFailure,
  appendActivityOutcome,
  readActivityRecoveries,
  type ActivityRecoveryContext,
  type ActivityRecoveryFact,
} from "./activity-recovery";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
}
function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "The Activity workspace could not be loaded.";
}

type ActivityView = "needs-attention" | "in-progress" | "recent-outcomes";

const ACTIVITY_VIEWS: Array<{ id: ActivityView; label: string }> = [
  { id: "needs-attention", label: "Needs attention" },
  { id: "in-progress", label: "In progress" },
  { id: "recent-outcomes", label: "Recent outcomes" },
];

export function ActivityPage({
  config,
  onNavigate,
  locationSearch = "",
}: Pick<Props, "config" | "onNavigate"> & { locationSearch?: string }) {
  const modelingSession = useMemo(() => loadModelingSession(), []);
  const deliveryActivities = useMemo(() => loadDeliveryActivities(), []);
  const [role, setRole] = useState<ProductRole | null>(null);
  const [principalId, setPrincipalId] = useState<string | null>(null);
  const [reviewRequests, setReviewRequests] = useState<ReviewRequestResponse[]>([]);
  const [processingBatches, setProcessingBatches] = useState<CommonProcessingBatchResponse[]>([]);
  const [processingBatchContexts, setProcessingBatchContexts] = useState<Record<string, ProcessingBatchMaterialContext>>({});
  const [processingBatchError, setProcessingBatchError] = useState<string | null>(null);
  const [recoveryFacts, setRecoveryFacts] = useState<ActivityRecoveryFact[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [retryingBatchId, setRetryingBatchId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActivityView>("in-progress");
  const initializedRole = useRef<ProductRole | null>(null);
  const activityViewButtons = useRef<Partial<Record<ActivityView, HTMLButtonElement>>>({});
  const requestSequence = useRef(0);
  const governedContext = useMemo(() => {
    const query = new URLSearchParams(locationSearch);
    return [
      ["Candidate", query.get("candidate_id"), query.get("candidate_revision_id")],
      ["Validation result", query.get("validation_result_id"), null],
      ["Solver Card", query.get("solver_card_id"), query.get("solver_card_revision_id")],
    ].filter((entry): entry is [string, string, string | null] => Boolean(entry[1]));
  }, [locationSearch]);
  useEffect(() => publishWorkspaceStatus({ selection: "Current workspace activity", revision: "Current user", jobs: "No active job", warnings: "0 warnings", connection: "online" }), []);

  async function loadQueue(): Promise<void> {
    const sequence = ++requestSequence.current;
    setLoadingQueue(true);
    setQueueError(null);
    setProcessingBatchError(null);
    try {
      const [accessResult, principalResult, requestsResult, batchResult, documentsResult, metalMaterials, polymerMaterials, elastomerMaterials] = await Promise.all([
        getEffectiveProductAccess(config),
        getAuthenticatedPrincipal(config),
        listReviewRequests(config, { limit: 50 }),
        listCommonProcessingBatches(config)
          .then((result) => ({ result, error: null as string | null }))
          .catch((cause: unknown) => ({ result: null, error: messageFor(cause) })),
        listCanonicalTestDataDocuments(config).catch(() => null),
        listMaterials(config, "", "metal").catch(() => null),
        listMaterials(config, "", "polymer").catch(() => null),
        listMaterials(config, "", "elastomer").catch(() => null),
      ]);
      if (sequence !== requestSequence.current) return;
      const nextRole = accessResult.data.product_role;
      // Seed the role default in the same render as the access result so a
      // reviewer never sees the User/Admin panel during the access handshake.
      // The effect below still handles a later role change without overriding
      // a tab the user has already selected.
      if (initializedRole.current === null) {
        initializedRole.current = nextRole;
        setActiveView(nextRole === "reviewer" ? "needs-attention" : "in-progress");
      }
      setRole(nextRole);
      setPrincipalId(principalResult.data.principal_id);
      setReviewRequests(requestsResult.data.items);
      setProcessingBatches(batchResult.result?.data.items ?? []);
      setProcessingBatchError(batchResult.error);
      const documents = documentsResult?.data.items ?? [];
      const materialsByFamily = {
        metal: metalMaterials?.data.items ?? [],
        polymer: polymerMaterials?.data.items ?? [],
        elastomer: elastomerMaterials?.data.items ?? [],
      } satisfies Record<ProcessingBatchMaterialContext["family"], MaterialResponse[]>;
      setProcessingBatchContexts(Object.fromEntries(
        (batchResult.result?.data.items ?? []).flatMap((batch) => {
          const context = processingBatchMaterialContext(batch, documents, materialsByFamily);
          return context ? [[batch.batch_id, context] as const] : [];
        }),
      ));
      setRecoveryFacts(readActivityRecoveries(
        principalResult.data.principal_id,
        principalResult.data.organization_id,
        principalResult.data.project_id,
      ));
    } catch (cause) {
      if (sequence !== requestSequence.current) return;
      setQueueError(messageFor(cause));
    } finally {
      if (sequence === requestSequence.current) setLoadingQueue(false);
    }
  }

  useEffect(() => {
    void loadQueue();
    return () => { requestSequence.current += 1; };
  }, [config.baseUrl, config.accessToken]);

  useEffect(() => {
    if (!role || initializedRole.current === role) return;
    initializedRole.current = role;
    setActiveView(role === "reviewer" ? "needs-attention" : "in-progress");
  }, [role]);

  async function decide(request: ReviewRequestResponse, decision: "approved" | "changes_requested"): Promise<void> {
    const reason = decisionReason.trim();
    if (!reason) {
      setDecisionError("Add a reason before recording this review decision.");
      return;
    }
    setDecidingId(request.review_request_id);
    setDecisionError(null);
    try {
      const result = await createReviewDecision(config, request.review_request_id, {
        expected_manifest_sha256: request.manifest_sha256,
        decision,
        reason,
      });
      setReviewRequests((items) => items.map((item) => item.review_request_id === result.data.review_request_id ? result.data : item));
      setReviewingId(null);
      setDecisionReason("");
      setActiveView("recent-outcomes");
    } catch (cause) {
      setDecisionError(messageFor(cause));
    } finally {
      setDecidingId(null);
    }
  }

  async function retryFailedBatch(batch: CommonProcessingBatchResponse): Promise<void> {
    setRetryingBatchId(batch.batch_id);
    try {
      const result = await retryFailedCommonProcessingBatch(config, batch.batch_id);
      setProcessingBatches((items) => items.map((item) => item.batch_id === result.data.batch_id ? result.data : item));
      setActiveView("recent-outcomes");
    } catch (cause) {
      setQueueError(messageFor(cause));
    } finally {
      setRetryingBatchId(null);
    }
  }

  function processingBatchPath(batch: CommonProcessingBatchResponse): string {
    const context = processingBatchContexts[batch.batch_id];
    const query = new URLSearchParams({
      stage: "process",
      batch_id: batch.batch_id,
      classification: batch.classification,
      recipe_id: batch.recipe_id,
      recipe_revision_id: batch.recipe_revision_id,
    });
    if (context) {
      query.set("family", context.family);
      query.set("material_id", context.materialId);
      query.set("material_revision_id", context.materialRevisionId);
      query.set("material_state_id", context.materialStateId);
      query.set("material_state_revision_id", context.materialStateRevisionId);
    }
    batch.members.forEach((member) => {
      query.append("source_document_id", member.source.document_id);
      query.append("source_revision_id", member.source.revision_id);
    });
    return `/modeling?${query.toString()}`;
  }

  const resumePath = modelingSession ? `/modeling?stage=${modelingSession.workspace.activeStage}&family=${modelingSession.materialFamily}` : "/modeling";
  const stageLabel = modelingSession ? `${modelingSession.workspace.activeStage[0].toUpperCase()}${modelingSession.workspace.activeStage.slice(1)}` : null;
  // Visibility is server/RLS scoped. Keep a defensive owner filter for non-reviewers
  // so an accidentally over-broad response cannot expose another user's request;
  // Reviewer queues remain the server-authorized decision surface.
  const canDecide = role === "reviewer";
  const visibleRequests = canDecide
    ? reviewRequests
    : reviewRequests.filter((request) => request.requested_by === principalId);
  const pendingRequests = visibleRequests.filter((request) => request.decision === null);
  const decidedRequests = visibleRequests.filter((request) => request.decision !== null);
  const failedBatches = processingBatches.filter((batch) => batch.status === "failed" || batch.status === "partial");
  const recoveredBatches = processingBatches.filter((batch) => batch.status === "succeeded" && batch.attempts.some((attempt) => attempt.attempt_no > 1));
  const activeRecoveryFacts = recoveryFacts.filter((fact) => fact.status === "failed");
  const recoveryOutcomes = recoveryFacts.filter((fact) => fact.status === "succeeded");
  const needsAttention = canDecide ? pendingRequests : [];
  const inProgress = canDecide ? [] : pendingRequests;
  const roleLabel = role === "reviewer" ? "Reviewer queue" : role ? "User queue" : "Activity queue";
  const roleDescription = role === "reviewer"
    ? "Requests awaiting a decision, plus local work and outcomes."
    : "Your pending requests and browser-local work.";
  const activateView = (view: ActivityView, focus = false) => {
    setActiveView(view);
    if (focus) window.requestAnimationFrame(() => activityViewButtons.current[view]?.focus());
  };
  const handleViewKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, current: ActivityView) => {
    const index = ACTIVITY_VIEWS.findIndex((view) => view.id === current);
    const next = event.key === "ArrowRight" || event.key === "ArrowDown"
      ? ACTIVITY_VIEWS[(index + 1) % ACTIVITY_VIEWS.length].id
      : event.key === "ArrowLeft" || event.key === "ArrowUp"
        ? ACTIVITY_VIEWS[(index - 1 + ACTIVITY_VIEWS.length) % ACTIVITY_VIEWS.length].id
        : event.key === "Home"
          ? ACTIVITY_VIEWS[0].id
          : event.key === "End"
            ? ACTIVITY_VIEWS[ACTIVITY_VIEWS.length - 1].id
            : null;
    if (!next) return;
    event.preventDefault();
    activateView(next, true);
  };
  const reviewAction = canDecide
    ? (request: ReviewRequestResponse) => <button className="ux-button primary" type="button" aria-expanded={reviewingId === request.review_request_id} onClick={() => { setReviewingId(request.review_request_id); setDecisionReason(""); setDecisionError(null); }}>Review</button>
    : undefined;
  const reviewExpanded = canDecide
    ? (request: ReviewRequestResponse) => <ReviewAction request={request} reviewing={true} deciding={decidingId === request.review_request_id} reason={decisionReason} error={reviewingId === request.review_request_id ? decisionError : null} onOpen={() => undefined} onCancel={() => { setReviewingId(null); setDecisionReason(""); setDecisionError(null); }} onReasonChange={setDecisionReason} onDecide={(decision) => void decide(request, decision)} />
    : undefined;
  const recoveryNeeds = <>
    {!loadingQueue && activeRecoveryFacts.length ? <section className="activity-recovery-group" aria-labelledby="activity-recovery-needed"><div className="activity-section-heading"><h3 id="activity-recovery-needed">Recovery needed</h3><p>Failed work keeps its exact selection until it succeeds or you resolve it.</p></div><ul className="activity-list activity-recovery-list">{activeRecoveryFacts.map((fact) => <li key={fact.id}><span><strong>{activityRecoveryLabel(fact.context.kind)}</strong><small className="ux-meta">{fact.message} · Failed · {formatActivityTime(fact.occurredAt)}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(fact.context.path)}>Open exact selection</button></li>)}</ul></section> : null}
    {!loadingQueue && failedBatches.length ? <div className="activity-batch-recovery"><div className="activity-section-heading"><h3>Processing recovery</h3><p>Failed and partial batches retain their exact Recipe and Test Data revisions until the failed members succeed.</p></div><ul className="activity-list activity-job-list">{failedBatches.map((batch) => { const context = processingBatchContexts[batch.batch_id]; const failedAttempt = [...batch.attempts].reverse().find((attempt) => attempt.status === "failed"); return <li key={batch.batch_id}><span><strong>{batch.label}</strong><small className="ux-meta">Process · {processingBatchStatusLabel(batch.status)} · {batch.members.length} exact Test Data source{batch.members.length === 1 ? "" : "s"} · {batch.attempts.filter((attempt) => attempt.status === "failed").length} failed attempt{batch.attempts.filter((attempt) => attempt.status === "failed").length === 1 ? "" : "s"}</small><small className="ux-meta">{failedAttempt?.error_detail ?? "Retry the failed members to continue."}</small>{context?.reason ? <small className="ux-meta">{context.reason}</small> : !context ? <small className="ux-meta">Governed Material context is unavailable; exact reopening is blocked.</small> : null}<details className="ux-disclosure"><summary>Exact revision evidence</summary><dl className="evidence-grid"><dt>Recipe</dt><dd><code>{batch.recipe_id} · {batch.recipe_revision_id}</code></dd><dt>Test Data</dt><dd><code>{batch.members.map((member) => `${member.source.document_id} · ${member.source.revision_id}`).join("; ")}</code></dd>{context ? <><dt>Material context</dt><dd><code>{context.materialId} · {context.materialRevisionId}</code></dd><dt>Material State</dt><dd><code>{context.materialStateId} · {context.materialStateRevisionId}</code></dd></> : null}</dl></details></span><span className="activity-row-actions"><button className="ux-button" type="button" disabled={!context?.exact} onClick={() => onNavigate(processingBatchPath(batch))}>{context?.exact ? "Open exact Process" : "Exact context unavailable"}</button><button className="ux-button" type="button" disabled={retryingBatchId === batch.batch_id} onClick={() => void retryFailedBatch(batch)}>{retryingBatchId === batch.batch_id ? "Retrying…" : "Retry failed"}</button></span></li>; })}</ul></div> : null}
  </>;
  const needsPanel = <ActivityQueueSection id="section-needs-attention" title="Needs attention" description={canDecide ? "Submitted work waiting for your review." : "Failed Processing batches and recovery actions that need attention."} loading={loadingQueue} emptyMessage={activeRecoveryFacts.length || failedBatches.length ? "No review requests need attention." : "Nothing needs your attention."} items={needsAttention} action={reviewAction} expandedId={reviewingId} expanded={reviewExpanded} extra={recoveryNeeds} />;
  const inProgressPanel = <section id="section-in-progress" className="activity-section" role="tabpanel" tabIndex={0} aria-labelledby="activity-in-progress-heading"><div className="activity-section-heading"><div><h2 id="activity-in-progress-heading">In progress</h2><p>Work you can resume and review requests still awaiting a decision.</p></div><span className="activity-section-count">{loadingQueue ? "Loading…" : `${inProgress.length + (modelingSession ? 1 : 0)} ${inProgress.length + (modelingSession ? 1 : 0) === 1 ? "item" : "items"}`}</span></div>
    {modelingSession ? <ActivityWorkTable caption="In progress work" rows={[{ key: "modeling-session", task: modelingSession.material?.label ?? modelingSession.objective ?? "Material modeling session", reason: `${modelingSession.materialFamily} · ${stageLabel} · ${modelingSession.testData ? `${modelingSession.testData.label} r${modelingSession.testData.revisionNo}` : "No exact Test Data"} · ${modelingSession.workspace.selectedDocumentIds.length} selected curves`, status: "Local session", updated: "This browser", action: <button className="ux-button" type="button" onClick={() => onNavigate(resumePath)}>{`Resume ${stageLabel}`}</button>, testId: "recent-modeling-session" }]} /> : null}
    {!loadingQueue && inProgress.length ? <ActivityRows items={inProgress} caption="In progress review requests" /> : null}
    {!modelingSession && !loadingQueue && !inProgress.length ? <section className="activity-empty-state" role="status" aria-label="No work in progress"><div><strong>No work in progress</strong><p>Start a Modeling session or submit an available item for review from its workspace.</p></div><button className="ux-button" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button></section> : null}
    {loadingQueue && !modelingSession ? <ActivityQueueLoading /> : null}
  </section>;
  const recentPanel = <section id="section-recent-outcomes" className="activity-section" role="tabpanel" tabIndex={0} aria-labelledby="activity-recent-outcomes-heading"><div className="activity-section-heading"><div><h2 id="activity-recent-outcomes-heading">Recent outcomes</h2><p>Completed review decisions and solver cards opened in this browser.</p></div><span className="activity-section-count">{loadingQueue ? "Loading…" : `${decidedRequests.length + deliveryActivities.length + recoveryOutcomes.length + recoveredBatches.length} ${decidedRequests.length + deliveryActivities.length + recoveryOutcomes.length + recoveredBatches.length === 1 ? "item" : "items"}`}</span></div>
    {!loadingQueue && decidedRequests.length ? <ActivityRows items={decidedRequests} caption="Recent review outcomes" action={(request) => { const action = request.decision?.decision === "changes_requested" ? reviewRevisionAction(request) : null; return action ? <button className="ux-button" type="button" onClick={() => onNavigate(action.path)}>{action.label}</button> : undefined; }} /> : null}
    {deliveryActivities.length ? <ActivityWorkTable caption="Recent solver card outcomes" rows={deliveryActivities.map((activity) => ({ key: `${activity.action}:${activity.cardId}`, task: `${activity.action === "download" ? "Downloaded solver card" : "Previewed solver card"} · ${activity.cardLabel}`, reason: `${activity.materialLabel} · ${activity.solver} ${activity.extension}`, status: "Delivered", updated: formatActivityTime(activity.occurredAt), action: <button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${activity.materialId}/cards/${activity.cardId}`)}>Open card</button>, testId: "recent-solver-card-activity" }))} /> : null}
    {!loadingQueue && !decidedRequests.length && !deliveryActivities.length && !recoveryOutcomes.length && !recoveredBatches.length ? <p className="activity-empty-line" role="status">No recent outcomes yet.</p> : null}
    {!loadingQueue && recoveryOutcomes.length ? <section className="activity-recovery-group" aria-labelledby="activity-recovery-outcomes"><div className="activity-section-heading"><h3 id="activity-recovery-outcomes">Recovery outcomes</h3><p>Successful retries remain in history while their matching failure is resolved.</p></div><ul className="activity-list activity-recovery-list">{recoveryOutcomes.map((fact) => <li key={fact.id}><span><strong>{activityRecoveryLabel(fact.context.kind)}</strong><small className="ux-meta">{fact.message} · Succeeded · {formatActivityTime(fact.occurredAt)}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(fact.context.path)}>Open exact selection</button></li>)}</ul></section> : null}
    {!loadingQueue && recoveredBatches.length ? <section className="activity-recovery-group" aria-labelledby="activity-processing-outcomes"><div className="activity-section-heading"><h3 id="activity-processing-outcomes">Processing outcomes</h3><p>Successful retries remain in the server projection with their append-only attempts.</p></div><ul className="activity-list activity-recovery-list">{recoveredBatches.map((batch) => <li key={batch.batch_id}><span><strong>{batch.label}</strong><small className="ux-meta">Process · Succeeded · {batch.members.length} exact Test Data source{batch.members.length === 1 ? "" : "s"} · {batch.attempts.length} attempts recorded</small><details className="ux-disclosure"><summary>Exact revision evidence</summary><dl className="evidence-grid"><dt>Recipe</dt><dd><code>{batch.recipe_id} · {batch.recipe_revision_id}</code></dd><dt>Test Data</dt><dd><code>{batch.members.map((member) => `${member.source.document_id} · ${member.source.revision_id}`).join("; ")}</code></dd></dl></details></span><button className="ux-button" type="button" onClick={() => onNavigate(processingBatchPath(batch))}>Open exact Process</button></li>)}</ul></section> : null}
    {loadingQueue ? <ActivityQueueLoading /> : null}
  </section>;
  const activePanel = activeView === "needs-attention" ? needsPanel : activeView === "in-progress" ? inProgressPanel : recentPanel;
  return <div className="ux-page"><div className="activity-shell"><div className="activity-content">
    <header className="activity-heading"><div><div className="activity-heading-line"><h1>Activity</h1><span className="activity-role-context">{roleLabel}</span></div><p>{roleDescription}</p></div><div className="activity-heading-actions"><span className="activity-queue-status" role="status" aria-live="polite">{loadingQueue ? "Loading…" : queueError ? "Queue unavailable" : "Ready"}</span><button className="ux-button tertiary" type="button" onClick={() => void loadQueue()} disabled={loadingQueue}>{loadingQueue ? "Refreshing…" : "Refresh"}</button></div></header>
    {queueError ? <div className="activity-queue-error" role="alert"><span>{queueError}</span><button className="ux-button" type="button" onClick={() => void loadQueue()}>Retry</button></div> : null}
    {processingBatchError ? <div className="activity-queue-error" role="alert"><span>Processing recovery unavailable: {processingBatchError}</span><button className="ux-button" type="button" onClick={() => void loadQueue()}>Retry Processing recovery</button></div> : null}
    <nav className="activity-saved-views" role="tablist" aria-label="Activity saved views">{ACTIVITY_VIEWS.map((view) => <button key={view.id} ref={(button) => { if (button) activityViewButtons.current[view.id] = button; }} id={`view-${view.id}`} className={`activity-saved-view${activeView === view.id ? " is-active" : ""}`} type="button" role="tab" aria-controls={`section-${view.id}`} aria-selected={activeView === view.id} tabIndex={activeView === view.id ? 0 : -1} onClick={() => activateView(view.id)} onKeyDown={(event) => handleViewKeyDown(event, view.id)}>{view.label}</button>)}</nav>
    <div className="activity-queue-region"><MaterialsScrollRegion id="activity-queue-scroll" className="activity-queue-scroll" shellClassName="activity-queue-scroll-shell" aria-label="Scrollable Activity queue">{activePanel}</MaterialsScrollRegion></div>
    {governedContext.length ? <section className="activity-context-line" aria-label="Modeling review context"><span>A modeling review or validation context is available.</span><button className="ux-button" type="button" onClick={() => onNavigate(`/modeling?stage=validate&family=${modelingSession?.materialFamily ?? "metal"}`)}>Resume validation</button><details className="ux-disclosure"><summary>Advanced context</summary><dl className="evidence-grid">{governedContext.map(([label, id, revisionId]) => <div key={label}><dt>{label}</dt><dd>{id}{revisionId ? ` · revision ${revisionId}` : ""}</dd></div>)}</dl></details></section> : null}
    <details className="ux-disclosure activity-advanced"><summary>Advanced activity evidence</summary><p>Immutable IDs and revisions remain available here for audit and exact re-opening.</p><button className="ux-button" type="button" onClick={() => onNavigate("/exports")}>Open export packages</button></details>
  </div></div></div>;
}

function reviewTaskLabel(aggregateType: string): string {
  const normalized = aggregateType.toLowerCase();
  if (normalized === "modeling.material_model") return "Selected model review";
  if (normalized.includes("solver") || normalized.includes("card")) return "Solver card review";
  if (normalized.includes("test") || normalized.includes("dataset")) return "Test data review";
  return "Material data review";
}

function reviewStatus(request: ReviewRequestResponse): string {
  if (request.decision?.decision === "approved") return "Approved";
  if (request.decision?.decision === "changes_requested") return "Changes requested";
  return request.lifecycle_state === "changes_requested" ? "Changes requested" : "Waiting for review";
}

function reviewRevisionAction(request: ReviewRequestResponse): { path: string; label: string } | null {
  const params = new URLSearchParams({
    record_id: request.evidence?.affected_materials.record_id ?? request.aggregate_id,
    record_revision_id: request.evidence?.affected_materials.record_revision_id ?? request.revision_id,
    material_revision_id: request.revision_id,
  });
  if (request.aggregate_type === "catalog.material") {
    return { path: `/materials/${request.aggregate_id}?${params.toString()}`, label: "Return to material" };
  }
  if (request.aggregate_type === "catalog.configurable_record") {
    return { path: `/catalog/records?record_id=${encodeURIComponent(request.aggregate_id)}&revision_id=${encodeURIComponent(request.revision_id)}`, label: "Revise and resubmit" };
  }
  if (request.aggregate_type === "datasets.test_data_document") {
    return { path: `/datasets/test-json?document_id=${encodeURIComponent(request.aggregate_id)}&revision_id=${encodeURIComponent(request.revision_id)}`, label: "Revise and resubmit" };
  }
  return request.evidence?.affected_materials.path ? { path: request.evidence.affected_materials.path, label: "Review exact revision" } : null;
}

function formatActivityTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function ActivityQueueLoading() {
  return <div className="activity-queue-loading" aria-busy="true" aria-label="Loading activity queue"><span /><span /><span /></div>;
}

interface ActivityTableRow {
  key: string;
  task: string;
  reason: string;
  status: string;
  updated: string;
  action?: ReactNode;
  testId?: string;
}

function ActivityTable({
  caption,
  rows,
  expandedKey,
  expanded,
}: {
  caption: string;
  rows: ActivityTableRow[];
  expandedKey?: string | null;
  expanded?: (row: ActivityTableRow) => ReactNode;
}) {
  return <table className="activity-table"><caption className="visually-hidden">{caption}</caption><colgroup><col className="activity-column-task" /><col className="activity-column-reason" /><col className="activity-column-status" /><col className="activity-column-updated" /><col className="activity-column-action" /></colgroup><thead><tr><th scope="col">Task</th><th scope="col">Request/recovery reason</th><th scope="col">Status</th><th scope="col">Updated</th><th scope="col">Action</th></tr></thead><tbody>{rows.map((row) => <Fragment key={row.key}>
    <tr key={row.key} data-testid={row.testId}>
      <td className="activity-cell-task"><strong>{row.task}</strong></td>
      <td className="activity-cell-reason">{row.reason}</td>
      <td className="activity-cell-status"><strong>{row.status}</strong></td>
      <td className="activity-cell-updated"><time>{row.updated}</time></td>
      <td className="activity-cell-action">{row.action ?? <span className="activity-row-state" role="img" aria-label="No available action">—</span>}</td>
    </tr>
    {expandedKey === row.key && expanded ? <tr key={`${row.key}:expanded`} className="activity-decision-row"><td colSpan={5}><div className="activity-decision-panel">{expanded(row)}</div></td></tr> : null}
  </Fragment>)}</tbody></table>;
}

function ActivityRows({
  items,
  action,
  caption = "Activity requests",
  expandedId,
  expanded,
}: {
  items: ReviewRequestResponse[];
  action?: (request: ReviewRequestResponse) => ReactNode;
  caption?: string;
  expandedId?: string | null;
  expanded?: (request: ReviewRequestResponse) => ReactNode;
}) {
  const rows = items.map((request) => {
    const requester = (request as ReviewRequestResponse & { requested_by_display_name?: string }).requested_by_display_name ?? "Requester name unavailable";
    return {
      key: request.review_request_id,
      task: reviewTaskLabel(request.aggregate_type),
      reason: `${request.reason || "No request reason was provided."}${request.decision ? ` · Decision: ${request.decision.reason || "No decision reason was provided."}` : ""} · Requested by: ${requester}`,
      status: reviewStatus(request),
      updated: formatActivityTime(request.decision?.decided_at ?? request.requested_at),
      action: action ? action(request) : undefined,
    } satisfies ActivityTableRow;
  });
  return <ActivityTable caption={caption} rows={rows} expandedKey={expandedId} expanded={expanded ? (row) => {
    const request = items.find((item) => item.review_request_id === row.key);
    return request ? expanded(request) : null;
  } : undefined} />;
}

function ActivityWorkTable({ caption, rows }: { caption: string; rows: ActivityTableRow[] }) {
  return <ActivityTable caption={caption} rows={rows} />;
}

function activityRecoveryLabel(kind: ActivityRecoveryContext["kind"]): string {
  if (kind === "test_data_json") return "Test Data download";
  if (kind === "selected_model_json") return "Selected model download";
  if (kind === "solver_card") return "Solver card delivery";
  if (kind === "csv_blob") return "CSV download";
  if (kind === "receipt_json") return "Delivery receipt download";
  return "Release manifest download";
}

function processingBatchStatusLabel(status: CommonProcessingBatchResponse["status"]): string {
  if (status === "partial") return "Partly completed";
  if (status === "failed") return "Failed";
  if (status === "succeeded") return "Succeeded";
  if (status === "running") return "Running";
  return "Planned";
}

interface ProcessingBatchMaterialContext {
  family: "metal" | "polymer" | "elastomer";
  materialId: string;
  materialRevisionId: string;
  materialStateId: string;
  materialStateRevisionId: string;
  exact: boolean;
  reason?: string;
}

function processingBatchMaterialContext(
  batch: CommonProcessingBatchResponse,
  documents: CanonicalTestDataDocumentResponse[],
  materialsByFamily: Record<ProcessingBatchMaterialContext["family"], MaterialResponse[]>,
): ProcessingBatchMaterialContext | null {
  const sources = batch.members.map((member) => {
    const document = documents.find((item) => item.test_data_document_id === member.source.document_id);
    return { member, document };
  });
  const first = sources[0]?.document?.governed_source;
  if (!first) return null;
  if (sources.some(({ member, document }) => !document || document.current_revision.id !== member.source.revision_id)) {
    return {
      family: "metal",
      materialId: first.material.aggregate_id,
      materialRevisionId: first.material.revision_id,
      materialStateId: first.material_state.aggregate_id,
      materialStateRevisionId: first.material_state.revision_id,
      exact: false,
      reason: "One or more Test Data revisions are no longer current; the batch is preserved as evidence and cannot be reopened silently.",
    };
  }
  if (sources.some(({ document }) => {
    const source = document?.governed_source;
    return !source
      || source.material.aggregate_id !== first.material.aggregate_id
      || source.material.revision_id !== first.material.revision_id
      || source.material_state.aggregate_id !== first.material_state.aggregate_id
      || source.material_state.revision_id !== first.material_state.revision_id;
  })) {
    return {
      family: "metal",
      materialId: first.material.aggregate_id,
      materialRevisionId: first.material.revision_id,
      materialStateId: first.material_state.aggregate_id,
      materialStateRevisionId: first.material_state.revision_id,
      exact: false,
      reason: "Batch members do not share one governed Material and Material State context.",
    };
  }
  const familyEntry = (Object.entries(materialsByFamily) as Array<[ProcessingBatchMaterialContext["family"], MaterialResponse[]]>).find(([, items]) => items.some((item) => item.material_id === first.material.aggregate_id));
  const material = familyEntry?.[1].find((item) => item.material_id === first.material.aggregate_id);
  if (!familyEntry || !material || material.current_revision.id !== first.material.revision_id) {
    return {
      family: familyEntry?.[0] ?? "metal",
      materialId: first.material.aggregate_id,
      materialRevisionId: first.material.revision_id,
      materialStateId: first.material_state.aggregate_id,
      materialStateRevisionId: first.material_state.revision_id,
      exact: false,
      reason: "The governed Material revision is no longer the current selectable head.",
    };
  }
  return {
    family: familyEntry[0],
    materialId: first.material.aggregate_id,
    materialRevisionId: first.material.revision_id,
    materialStateId: first.material_state.aggregate_id,
    materialStateRevisionId: first.material_state.revision_id,
    exact: true,
  };
}

function ActivityQueueSection({ id, title, description, loading, emptyMessage, items, action, expandedId, expanded, extra }: { id: string; title: string; description: string; loading: boolean; emptyMessage: string; items: ReviewRequestResponse[]; action?: (request: ReviewRequestResponse) => ReactNode; expandedId?: string | null; expanded?: (request: ReviewRequestResponse) => ReactNode; extra?: ReactNode }) {
  const headingId = `activity-${id.replace(/^section-/, "")}-heading`;
  return <section id={id} className="activity-section" role="tabpanel" tabIndex={0} aria-labelledby={headingId}><div className="activity-section-heading"><div><h2 id={headingId}>{title}</h2><p>{description}</p></div><span className="activity-section-count">{loading ? "Loading…" : `${items.length} ${items.length === 1 ? "item" : "items"}`}</span></div>{loading ? <ActivityQueueLoading /> : items.length ? <ActivityRows items={items} action={action} expandedId={expandedId} expanded={expanded} /> : <p className="activity-empty-line" role="status">{emptyMessage}</p>}{extra}</section>;
}

function ReviewAction({ request, reviewing, deciding, reason, error, onOpen, onCancel, onReasonChange, onDecide }: { request: ReviewRequestResponse; reviewing: boolean; deciding: boolean; reason: string; error: string | null; onOpen: () => void; onCancel: () => void; onReasonChange: (value: string) => void; onDecide: (decision: "approved" | "changes_requested") => void }) {
  if (!reviewing) return <button className="ux-button primary" type="button" onClick={onOpen}>Review</button>;
  return <form className="activity-review-form" onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); onDecide("approved"); }}><label>Review reason<textarea value={reason} onChange={(event) => onReasonChange(event.target.value)} placeholder="Explain the approval or requested change" required disabled={deciding} /></label>{request.evidence ? <details className="activity-review-evidence"><summary>Evidence and affected Materials</summary><dl className="evidence-grid"><div><dt>Schema</dt><dd>{request.evidence.schema.ref} · {request.evidence.schema.version}</dd></div><div><dt>Validation</dt><dd>{request.evidence.validation.status} · {request.evidence.validation.summary}</dd></div><div><dt>Materials path</dt><dd>{request.evidence.affected_materials.path ?? "Not attached"}</dd></div><div><dt>Record table</dt><dd><code>{request.evidence.affected_table_id && request.evidence.affected_table_revision_id ? `${request.evidence.affected_table_id} · ${request.evidence.affected_table_revision_id}` : "Not attached"}</code></dd></div><div><dt>Source Artifact</dt><dd>{request.evidence.source_artifact.state}{request.evidence.source_artifact.sha256 ? ` · ${request.evidence.source_artifact.sha256}` : ""}</dd></div><div><dt>Output Artifact</dt><dd><code>{request.evidence.output_artifact_sha256 ?? "Not provided"}</code></dd></div><div><dt>Created</dt><dd>{request.evidence.created.at} · {request.evidence.created.by}</dd></div><div><dt>Change reason</dt><dd>{request.evidence.change_reason}</dd></div><div><dt>Exact input use</dt><dd><ul className="activity-evidence-list">{request.evidence.exact_input_use.map((item) => <li key={item}><code>{item}</code></li>)}</ul></dd></div><div><dt>Requester ID</dt><dd><code>{request.requested_by}</code></dd></div><div><dt>Exact identity</dt><dd><code>{request.evidence.subject_id} · {request.evidence.subject_revision_id}</code></dd></div></dl></details> : null}{error ? <p role="alert">{error}</p> : null}<div><button className="ux-button primary" type="submit" disabled={deciding}>{deciding ? "Saving…" : "Approve"}</button><button className="ux-button" type="button" disabled={deciding} onClick={() => onDecide("changes_requested")}>Request changes</button><button className="ux-button tertiary" type="button" disabled={deciding} onClick={onCancel}>Cancel</button></div></form>;
}

async function recordActivityRecovery(
  config: ApiConfig,
  context: ActivityRecoveryContext,
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
      context,
      message,
    ] as const;
    if (status === "failed") appendActivityFailure(...args);
    else appendActivityOutcome(...args);
  } catch {
    // Recovery telemetry is best-effort; the server Activity queue remains authoritative.
  }
}
