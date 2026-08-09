import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ActivityPage } from "./material-library";
import { clearModelingSession, saveModelingSession } from "./modeling-session-context";
import { recordDeliveryActivity } from "./solver-card-delivery";

const mocks = vi.hoisted(() => ({
  access: vi.fn(),
  principal: vi.fn(),
  reviews: vi.fn(),
  decision: vi.fn(),
  batches: vi.fn(),
  retryBatch: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    getEffectiveProductAccess: mocks.access,
    getAuthenticatedPrincipal: mocks.principal,
    listReviewRequests: mocks.reviews,
    createReviewDecision: mocks.decision,
    listCommonProcessingBatches: mocks.batches,
    retryFailedCommonProcessingBatch: mocks.retryBatch,
  };
});

const config = { baseUrl: "/api/v1", accessToken: "token" };
const pendingReview = {
  review_request_id: "review-1",
  classification: "internal" as const,
  aggregate_type: "catalog.material",
  aggregate_id: "material-1",
  revision_id: "material-r1",
  manifest_sha256: "a".repeat(64),
  required_role: "domain_reviewer" as const,
  requested_by: "person-1",
  requested_by_display_name: "Demo reviewer",
  requested_at: "2026-07-27T00:00:00Z",
  reason: "Check the uploaded tensile data",
  lifecycle_state: "review" as const,
  decision: null,
  links: {},
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((fulfill) => {
    resolve = fulfill;
  });
  return { promise, resolve };
}

describe("Activity Modeling resume", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.access.mockResolvedValue({ data: { product_role: "user", feature_grants: [], legacy_compatible: false }, etag: null });
    mocks.principal.mockResolvedValue({ data: { principal_id: "person-1", principal_type: "user", display_name: "Demo user", organization_id: "organization-1", project_id: "project-1", groups: [], scopes: [], request_id: "request-1", trace_id: "00-00000000000000000000000000000000-0000000000000000-00" }, etag: null });
    mocks.reviews.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.batches.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.retryBatch.mockResolvedValue({ data: { items: [] }, etag: null });
  });

  afterEach(() => {
    cleanup();
    clearModelingSession();
    window.sessionStorage.clear();
  });

  it("resumes the exact stage, family, Test Data revision, and curve selection", () => {
    saveModelingSession({
      materialFamily: "metal",
      objective: "Calibrate DP780",
      material: { id: "material-1", revisionId: "material-r1", label: "DP780", revisionNo: 1 },
      testData: { id: "test-1", revisionId: "test-r3", label: "DP780 tensile", revisionNo: 3 },
      workspace: {
        activeStage: "fit",
        selectedDocumentIds: ["curve-1", "curve-2"],
        selectedTestDataRefs: [
          { id: "curve-1", revisionId: "curve-1-r2", label: "DP780 tensile 1", revisionNo: 2 },
          { id: "curve-2", revisionId: "curve-2-r4", label: "DP780 tensile 2", revisionNo: 4 },
        ],
        visibleTestDataKeys: ["curve-1:curve-1-r2", "curve-2:curve-2-r4"],
        selectedStepIndex: 4,
        selectedStageOrdinal: 5,
        plotView: "pipeline",
        settingsOpen: true,
      },
    });
    const navigate = vi.fn();

    render(<ActivityPage config={config} onNavigate={navigate} />);

    expect(screen.getByTestId("recent-modeling-session").textContent).toContain("metal · Fit · DP780 tensile r3 · 2 selected curves");
    fireEvent.click(screen.getByRole("button", { name: "Resume Fit" }));
    expect(navigate).toHaveBeenCalledWith("/modeling?stage=fit&family=metal");
  });

  it("states explicitly when this browser has no Modeling session", async () => {
    const navigate = vi.fn();

    render(<ActivityPage config={config} onNavigate={navigate} />);

    const empty = await screen.findByRole("status", { name: "No work in progress" });
    expect(empty.textContent).toContain("Start a Modeling session");
    expect(screen.queryByRole("button", { name: /^Resume / })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Start Modeling" }));
    expect(navigate).toHaveBeenCalledWith("/modeling");
  });

  it("uses the role-correct saved-view default and switches one active tabpanel at a time", async () => {
    mocks.access.mockResolvedValue({ data: { product_role: "reviewer", feature_grants: ["model_approval"], legacy_compatible: false }, etag: null });
    mocks.reviews.mockResolvedValue({ data: { items: [pendingReview] }, etag: null });

    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    const needsAttention = await screen.findByRole("tab", { name: "Needs attention" });
    await waitFor(() => expect(needsAttention.getAttribute("aria-selected")).toBe("true"));
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
    fireEvent.click(screen.getByRole("tab", { name: "Recent outcomes" }));
    expect(screen.getByRole("tab", { name: "Recent outcomes" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
    expect(screen.getByRole("tabpanel").getAttribute("id")).toBe("section-recent-outcomes");
    expect(screen.getByLabelText("Scrollable Activity queue")).toBeTruthy();
  });

  it("reopens a Solver Card while retaining its exact revision in recent activity", () => {
    recordDeliveryActivity({
      action: "download",
      materialId: "material-1",
      materialRevisionId: "material-r2",
      materialLabel: "DP780",
      cardId: "card-1",
      cardRevisionId: "card-r3",
      cardLabel: "DP780 OpenRadioss native card",
      solver: "OpenRadioss",
      extension: ".rad",
    });
    const navigate = vi.fn();

    render(<ActivityPage config={config} onNavigate={navigate} />);

    fireEvent.click(screen.getByRole("tab", { name: "Recent outcomes" }));
    expect(screen.getByTestId("recent-solver-card-activity").textContent).toContain("Downloaded solver card · DP780 OpenRadioss native card");
    fireEvent.click(screen.getByRole("button", { name: "Open card" }));
    expect(navigate).toHaveBeenCalledWith("/materials/material-1/cards/card-1");
  });

  it("reads exact validation context from the Modeling deep link", () => {
    const navigate = vi.fn();
    render(<ActivityPage
      config={config}
      onNavigate={navigate}
      locationSearch="?candidate_id=candidate-1&candidate_revision_id=candidate-r2&validation_result_id=result-3&solver_card_id=card-4&solver_card_revision_id=card-r5"
    />);

    const context = screen.getByRole("region", { name: "Modeling review context" });
    expect(context.textContent).toContain("candidate-1 · revision candidate-r2");
    expect(context.textContent).toContain("result-3");
    expect(context.textContent).toContain("card-4 · revision card-r5");
    fireEvent.click(screen.getByRole("button", { name: "Resume validation" }));
    expect(navigate).toHaveBeenCalledWith("/modeling?stage=validate&family=metal");
  });

  it("shows a User's submitted review in progress without decision controls", async () => {
    mocks.reviews.mockResolvedValue({ data: { items: [
      pendingReview,
      { ...pendingReview, review_request_id: "review-other", requested_by: "person-2", reason: "Another user's private work item" },
    ] }, etag: null });

    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    expect(await screen.findByText("Material data review")).toBeTruthy();
    expect(screen.getByRole("row", { name: /Check the uploaded tensile data/ }).textContent).toContain("Check the uploaded tensile data");
    expect(screen.queryByText(/Another user's private work item/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Review" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });

  it("labels a material-model request as a selected model review", async () => {
    mocks.reviews.mockResolvedValue({ data: { items: [
      { ...pendingReview, aggregate_type: "modeling.material_model", reason: "Review the selected DP780 model" },
    ] }, etag: null });

    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    expect(await screen.findByText("Selected model review")).toBeTruthy();
    expect(screen.queryByText("Material data review")).toBeNull();
  });

  it("shows typed provenance and exact table/output pins in reviewer evidence", async () => {
    mocks.access.mockResolvedValue({ data: { product_role: "reviewer", feature_grants: ["model_approval"], legacy_compatible: false }, etag: null });
    mocks.reviews.mockResolvedValue({ data: { items: [{
      ...pendingReview,
      evidence: {
        subject_type: "catalog.material",
        subject_id: "material-1",
        subject_revision_id: "material-r1",
        label: "DP780",
        classification: "internal",
        schema: { ref: "cmp.material", version: "1.0.0" },
        server_manifest: { sha256: "a".repeat(64) },
        source_artifact: { state: "unattached", id: null, sha256: null },
        validation: { status: "valid", summary: "Current revision verified." },
        created: { by: "person-1", at: "2026-07-27T00:00:00Z" },
        change_reason: "Review exact material",
        exact_input_use: ["catalog.material:material-1:material-r1"],
        affected_materials: { record_id: "record-1", record_revision_id: "record-r1", path: "/materials/material-1" },
        affected_table_id: "table-1",
        affected_table_revision_id: "table-r1",
        output_artifact_sha256: "b".repeat(64),
        neutral: { material_id: null, material_revision_id: null, artifact_sha256: null },
      },
    }] }, etag: null });
    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Review" }));
    expect(screen.getByText("/materials/material-1")).toBeTruthy();
    expect(screen.getByText("table-1 · table-r1")).toBeTruthy();
    expect(screen.getByText("Review exact material")).toBeTruthy();
    expect(screen.getByText("catalog.material:material-1:material-r1")).toBeTruthy();
    expect(screen.getByText("b".repeat(64))).toBeTruthy();
  });

  it("keeps resolver technical labels in Advanced evidence instead of the Activity task title", async () => {
    mocks.reviews.mockResolvedValue({ data: { items: [
      { ...pendingReview, aggregate_type: "modeling.material_model", evidence: { label: "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0" } },
    ] }, etag: null });

    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    expect(await screen.findByText("Selected model review")).toBeTruthy();
    expect(screen.queryByText("urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0")).toBeNull();
  });

  it("lets a Reviewer record an approval and moves the returned immutable request to outcomes", async () => {
    mocks.access.mockResolvedValue({ data: { product_role: "reviewer", feature_grants: ["model_approval"], legacy_compatible: false }, etag: null });
    mocks.reviews.mockResolvedValue({ data: { items: [pendingReview] }, etag: null });
    const approved = { ...pendingReview, lifecycle_state: "approved" as const, decision: { review_decision_id: "decision-1", review_request_id: "review-1", aggregate_type: "catalog.material", aggregate_id: "material-1", revision_id: "material-r1", manifest_sha256: "a".repeat(64), decision: "approved" as const, decided_by: "reviewer-1", decided_at: "2026-07-27T01:00:00Z", reason: "Units and source are complete" } };
    mocks.decision.mockResolvedValue({ data: approved, etag: null });

    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    await screen.findByRole("button", { name: "Review" });
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    fireEvent.change(screen.getByLabelText("Review reason"), { target: { value: "Units and source are complete" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(mocks.decision).toHaveBeenCalledWith(config, "review-1", expect.objectContaining({ decision: "approved", expected_manifest_sha256: "a".repeat(64) })));
    expect(await screen.findByRole("heading", { name: "Recent outcomes" })).toBeTruthy();
    expect(screen.getByText("Approved")).toBeTruthy();
  });

  it("records a change request only with an entered reason", async () => {
    mocks.access.mockResolvedValue({ data: { product_role: "reviewer", feature_grants: ["model_approval"], legacy_compatible: false }, etag: null });
    mocks.reviews.mockResolvedValue({ data: { items: [pendingReview] }, etag: null });
    const changed = { ...pendingReview, lifecycle_state: "changes_requested" as const, decision: { review_decision_id: "decision-2", review_request_id: "review-1", aggregate_type: "catalog.material", aggregate_id: "material-1", revision_id: "material-r1", manifest_sha256: "a".repeat(64), decision: "changes_requested" as const, decided_by: "administrator-1", decided_at: "2026-07-27T01:00:00Z", reason: "Add the test condition" } };
    mocks.decision.mockResolvedValue({ data: changed, etag: null });

    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Review" }));
    fireEvent.click(screen.getByRole("button", { name: "Request changes" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Add a reason");
    fireEvent.change(screen.getByLabelText("Review reason"), { target: { value: "Add the test condition" } });
    fireEvent.click(screen.getByRole("button", { name: "Request changes" }));

    await waitFor(() => expect(mocks.decision).toHaveBeenCalledWith(config, "review-1", expect.objectContaining({ decision: "changes_requested", reason: "Add the test condition" })));
    expect(screen.getByText("Changes requested")).toBeTruthy();
  });

  it("keeps a review loading failure recoverable", async () => {
    mocks.reviews.mockRejectedValueOnce(new Error("Review service is unavailable.")).mockResolvedValue({ data: { items: [] }, etag: null });

    render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    expect((await screen.findByRole("alert")).textContent).toContain("Review service is unavailable.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mocks.reviews).toHaveBeenCalledTimes(2));
  });

  it("does not let an older workspace request replace the latest Activity queue", async () => {
    const older = deferred<{ data: { items: (typeof pendingReview)[] }; etag: null }>();
    const latestReview = { ...pendingReview, review_request_id: "review-latest", reason: "Latest workspace request" };
    mocks.reviews
      .mockReturnValueOnce(older.promise)
      .mockResolvedValueOnce({ data: { items: [latestReview] }, etag: null });
    const { rerender } = render(<ActivityPage config={config} onNavigate={vi.fn()} />);

    rerender(<ActivityPage config={{ ...config, accessToken: "new-workspace-token" }} onNavigate={vi.fn()} />);
    expect(await screen.findByText(/Latest workspace request/)).toBeTruthy();

    older.resolve({ data: { items: [{ ...pendingReview, reason: "Older workspace request" }] }, etag: null });
    await waitFor(() => expect(mocks.reviews).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/Older workspace request/)).toBeNull();
    expect(screen.getByText(/Latest workspace request/)).toBeTruthy();
  });

  it("recovers a failed Processing Batch with a durable retry readback", async () => {
    const failedBatch = {
      batch_id: "batch-160",
      classification: "internal" as const,
      label: "DP780 tensile process",
      recipe_id: "recipe-160",
      recipe_revision_id: "recipe-160-r2",
      recipe_sha256: "b".repeat(64),
      status: "failed" as const,
      members: [{ member_id: "member-160", ordinal: 0, source: { document_id: "test-160", revision_id: "test-160-r3" }, source_document_sha256: "c".repeat(64) }],
      attempts: [{ attempt_id: "attempt-160-1", member_id: "member-160", attempt_no: 1, status: "failed" as const, output_id: null, output_revision_id: null, error_code: "processing_failed", error_detail: "Mapping Profile source channel is unavailable", started_at: "2026-07-27T00:00:00Z", completed_at: "2026-07-27T00:01:00Z" }],
      created_at: "2026-07-27T00:00:00Z",
      created_by: "person-1",
    };
    const recoveredBatch = {
      ...failedBatch,
      status: "succeeded" as const,
      attempts: [
        ...failedBatch.attempts,
        { ...failedBatch.attempts[0], attempt_id: "attempt-160-2", attempt_no: 2, status: "succeeded" as const, error_code: null, error_detail: null, output_id: "output-160", output_revision_id: "output-160-r1", completed_at: "2026-07-27T00:03:00Z" },
      ],
    };
    mocks.batches.mockResolvedValueOnce({ data: { items: [failedBatch] }, etag: null }).mockResolvedValue({ data: { items: [recoveredBatch] }, etag: null });
    mocks.retryBatch.mockResolvedValue({ data: recoveredBatch, etag: null });

    const navigate = vi.fn();
    render(<ActivityPage config={config} onNavigate={navigate} />);

    const needsAttentionTab = await screen.findByRole("tab", { name: "Needs attention" });
    await waitFor(() => expect(needsAttentionTab.getAttribute("aria-selected")).toBe("false"));
    fireEvent.click(needsAttentionTab);
    await waitFor(() => expect(needsAttentionTab.getAttribute("aria-selected")).toBe("true"));
    expect(await screen.findByText("DP780 tensile process")).toBeTruthy();
    expect(await screen.findByText(/Mapping Profile source channel is unavailable/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry failed" }));
    await waitFor(() => expect(mocks.retryBatch).toHaveBeenCalledWith(config, "batch-160"));
    expect(await screen.findByText("Processing outcomes")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry failed" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(mocks.batches).toHaveBeenCalledTimes(2));
    expect(screen.getByText("DP780 tensile process")).toBeTruthy();
  });
});
