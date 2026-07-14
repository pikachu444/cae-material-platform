import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewWorkbench } from "./review-workbench";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 201,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const reviewRequest = {
  review_request_id: "00000000-0000-0000-0000-000000000011",
  classification: "internal",
  aggregate_type: "catalog.material",
  aggregate_id: "00000000-0000-0000-0000-000000000001",
  revision_id: "00000000-0000-0000-0000-000000000002",
  manifest_sha256: "a".repeat(64),
  required_role: "domain_reviewer",
  requested_by: "00000000-0000-0000-0000-000000000003",
  requested_at: "2026-07-14T00:00:00Z",
  reason: "Request domain review",
  lifecycle_state: "review",
  decision: null,
  links: { self: "/api/v1/review-requests/11", decisions: "/api/v1/review-requests/11/decisions" },
};

describe("Review lifecycle workbench", () => {
  it("submits a digest-pinned request through the protected API", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(reviewRequest));
    vi.stubGlobal("fetch", fetchMock);

    render(<ReviewWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} />);
    fireEvent.change(screen.getByLabelText("Aggregate ID"), {
      target: { value: reviewRequest.aggregate_id },
    });
    fireEvent.change(screen.getByLabelText("Revision ID"), {
      target: { value: reviewRequest.revision_id },
    });
    fireEvent.change(screen.getByLabelText("Manifest SHA-256"), {
      target: { value: reviewRequest.manifest_sha256 },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit for review" }));

    expect(await screen.findByRole("heading", { name: "review" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/review-requests",
      expect.objectContaining({ method: "POST", headers: expect.anything() }),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      aggregate_type: "catalog.material",
      manifest_sha256: "a".repeat(64),
    });
  });
});
