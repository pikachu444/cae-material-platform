import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GovernanceEvidenceWorkbench } from "./governance-evidence-workbench";

const entityId = "00000000-0000-0000-0000-000000000001";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

describe("Governance evidence workbench", () => {
  it("loads an immutable entity, bounded lineage, and audit integrity through protected APIs", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock
      .mockResolvedValueOnce(jsonResponse({
        entity_id: entityId,
        organization_id: "00000000-0000-0000-0000-000000000002",
        project_id: "00000000-0000-0000-0000-000000000003",
        classification: "internal",
        entity_type: "exporting.solver_card.revision",
        reference: {
          kind: "revision",
          type: "exporting.solver_card.revision",
          id: "00000000-0000-0000-0000-000000000004",
          sha256: "a".repeat(64),
        },
        generation_requirement: "primary",
        generation_activity_id: null,
        created_at: "2026-07-25T00:00:00Z",
        recorded_at: "2026-07-25T00:00:00Z",
        recorded_by: "00000000-0000-0000-0000-000000000005",
        completeness: { state: "complete", issues: [] },
        links: { self: "", lineage: "", impact: "", completeness: "" },
      }))
      .mockResolvedValueOnce(jsonResponse({
        root_entity_id: entityId,
        direction: "upstream",
        max_depth: 10,
        limit: 100,
        target_entity_type: null,
        nodes: [],
        next_cursor: null,
        graph_truncated: false,
        total_discovered: 0,
      }))
      .mockResolvedValueOnce(jsonResponse({
        state: "valid",
        event_count: 4,
        last_sequence_no: 4,
        segment_count: 0,
        sealed_through_sequence_no: 0,
        unsealed_event_count: 4,
        issues: [],
      }));
    vi.stubGlobal("fetch", fetchMock);

    render(<GovernanceEvidenceWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} />);
    fireEvent.change(screen.getByLabelText("Provenance Entity ID"), { target: { value: entityId } });
    fireEvent.click(screen.getByRole("button", { name: "Inspect entity" }));
    expect(await screen.findByText("exporting.solver_card.revision")).toBeTruthy();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/provenance/entities/${entityId}`);

    fireEvent.click(screen.getByRole("button", { name: "Load upstream lineage" }));
    expect(await screen.findByText("Upstream lineage")).toBeTruthy();
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain(`/provenance/entities/${entityId}/lineage`);
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain("direction=upstream");

    fireEvent.click(screen.getByRole("button", { name: "Verify chain" }));
    expect(await screen.findByText("Audit integrity")).toBeTruthy();
    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/v1/audit/integrity");
  });

  it("resolves a revision reference before opening the evidence path", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      entity_id: entityId,
      organization_id: "00000000-0000-0000-0000-000000000002",
      project_id: "00000000-0000-0000-0000-000000000003",
      classification: "internal",
      entity_type: "exporting.solver_card.revision",
      reference: {
        kind: "revision",
        type: "exporting.solver_card.revision",
        id: "00000000-0000-0000-0000-000000000004",
        sha256: "a".repeat(64),
      },
      generation_requirement: "primary",
      generation_activity_id: null,
      created_at: "2026-07-25T00:00:00Z",
      recorded_at: "2026-07-25T00:00:00Z",
      recorded_by: "00000000-0000-0000-0000-000000000005",
      completeness: { state: "complete", issues: [] },
      links: { self: "", lineage: "", impact: "", completeness: "" },
    }));
    vi.stubGlobal("fetch", fetchMock);

    render(<GovernanceEvidenceWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} />);
    fireEvent.change(screen.getByLabelText("Typed reference ID"), {
      target: { value: "00000000-0000-0000-0000-000000000004" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Resolve typed reference" }));

    expect(await screen.findByText("exporting.solver_card.revision")).toBeTruthy();
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/provenance/entities/by-reference?");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("reference_type=exporting.solver_card.revision");
    expect(screen.getByDisplayValue(entityId)).toBeTruthy();
  });
});
