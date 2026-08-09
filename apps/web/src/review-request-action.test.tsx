import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewRequestAction } from "./review-request-action";

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn() }));
vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  listReviewRequests: mocks.list,
  createReviewRequest: mocks.create,
}));

const config = { baseUrl: "/api/v1", accessToken: "token" };
const subject = { aggregateType: "catalog.material" as const, aggregateId: "material-1", revisionId: "revision-1", manifestSha256: "a".repeat(64), classification: "internal" as const, lifecycleState: "draft" };
const request = { review_request_id: "review-1", classification: "internal" as const, aggregate_type: subject.aggregateType, aggregate_id: subject.aggregateId, revision_id: subject.revisionId, manifest_sha256: subject.manifestSha256, required_role: "domain_reviewer" as const, requested_by: "person-1", requested_at: "2026-07-27T00:00:00Z", reason: "Check source", lifecycle_state: "review" as const, decision: null, links: {} };

describe("immutable review request action", () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("submits only the loaded exact revision and requires a reason", async () => {
    mocks.list.mockResolvedValue({ data: { items: [] } });
    mocks.create.mockResolvedValue({ data: request });
    render(<ReviewRequestAction config={config} subject={subject} />);
    fireEvent.click(await screen.findByRole("button", { name: "Request review" }));
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Add a reason");
    fireEvent.change(screen.getByLabelText("Review request reason"), { target: { value: "Check source" } });
    fireEvent.click(screen.getByRole("button", { name: "Retry request" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(config, {
      classification: "internal", aggregate_type: "catalog.material", aggregate_id: "material-1", revision_id: "revision-1", manifest_sha256: "a".repeat(64), reason: "Check source",
    }));
    expect((await screen.findByRole("status")).textContent).toContain("Waiting for review");
  });

  it("submits once without submitting an enclosing record form", async () => {
    mocks.list.mockResolvedValue({ data: { items: [] } });
    mocks.create.mockResolvedValue({ data: request });
    const recordSubmit = vi.fn();
    render(<form onSubmit={recordSubmit}><ReviewRequestAction config={config} subject={subject} /></form>);
    fireEvent.click(await screen.findByRole("button", { name: "Request review" }));
    fireEvent.change(screen.getByLabelText("Review request reason"), { target: { value: "Check source" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    expect(recordSubmit).not.toHaveBeenCalled();
  });

  it.each([["review", null, "Waiting for review"], ["approved", { decision: "approved" }, "Approved"], ["changes_requested", { decision: "changes_requested" }, "Changes requested"]] as const)("does not duplicate an existing %s request", async (lifecycle, decision, label) => {
    mocks.list.mockResolvedValue({ data: { items: [{ ...request, lifecycle_state: lifecycle, decision: decision ? { ...request, ...decision } : null }] } });
    render(<ReviewRequestAction config={config} subject={subject} />);
    expect((await screen.findByRole("status")).textContent).toContain(label);
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("keeps a failed submit recoverable with Retry", async () => {
    mocks.list.mockResolvedValue({ data: { items: [] } });
    mocks.create.mockRejectedValueOnce(new Error("Service unavailable"));
    render(<ReviewRequestAction config={config} subject={subject} />);
    fireEvent.click(await screen.findByRole("button", { name: "Request review" }));
    fireEvent.change(screen.getByLabelText("Review request reason"), { target: { value: "Check source" } });
    fireEvent.click(screen.getByRole("button", { name: "Send request" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Service unavailable");
    expect(screen.getByRole("button", { name: "Retry request" })).toBeTruthy();
  });

  it("blocks submission until a failed duplicate check is retried", async () => {
    mocks.list.mockRejectedValueOnce(new Error("Review status unavailable")).mockResolvedValueOnce({ data: { items: [request] } });
    render(<ReviewRequestAction config={config} subject={subject} />);
    expect((await screen.findByRole("alert")).textContent).toContain("Review status unavailable");
    expect(screen.queryByRole("button", { name: "Request review" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry status" }));
    expect((await screen.findByRole("status")).textContent).toContain("Waiting for review");
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it("does not offer a new request for a non-draft immutable revision", async () => {
    mocks.list.mockResolvedValue({ data: { items: [] } });
    render(<ReviewRequestAction config={config} subject={{ ...subject, lifecycleState: "released" }} />);
    expect((await screen.findByRole("status")).textContent).toContain("released");
    expect(screen.queryByRole("button", { name: "Request review" })).toBeNull();
  });
});
