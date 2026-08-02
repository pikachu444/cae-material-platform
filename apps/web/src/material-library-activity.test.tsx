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
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    getEffectiveProductAccess: mocks.access,
    getAuthenticatedPrincipal: mocks.principal,
    listReviewRequests: mocks.reviews,
    createReviewDecision: mocks.decision,
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
    expect(screen.getByRole("heading", { name: "In progress" }).parentElement?.parentElement?.textContent).toContain("Check the uploaded tensile data");
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
    mocks.access.mockResolvedValue({ data: { product_role: "administrator", feature_grants: ["model_approval"], legacy_compatible: false }, etag: null });
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
});
