import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReferenceTensileWorkflow } from "./reference-tensile-workflow";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const state = {
  material_state_id: "00000000-0000-0000-0000-000000000001",
  material_id: "00000000-0000-0000-0000-000000000002",
  current_revision: {
    id: "00000000-0000-0000-0000-000000000003",
    aggregate_id: "00000000-0000-0000-0000-000000000001",
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:material-state:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-13T00:00:00Z",
    created_by: "00000000-0000-0000-0000-000000000004",
    change_reason: "demo",
    organization_id: "00000000-0000-0000-0000-000000000005",
    project_id: "00000000-0000-0000-0000-000000000006",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
    content: {
      material_id: "00000000-0000-0000-0000-000000000002",
      material_revision_id: "00000000-0000-0000-0000-000000000007",
      name: "As received",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance: {
      entity_type: "catalog.material_state.revision",
      reference_type: "catalog.material_state.revision",
      revision_id: "00000000-0000-0000-0000-000000000003",
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-07-13T00:00:00Z",
      recorded_by: "00000000-0000-0000-0000-000000000004",
    },
  },
  property_sets_url: "/api/v1/material-states/1/property-sets",
};

describe("Reference tensile Dataset workflow", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("keeps the test workflow lazy, then exposes explicit CSV mapping fields", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceTensileWorkflow
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
      />,
    );

    expect(screen.queryByText("1. Register a concrete Specimen")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Manage reference tensile data" }));

    expect(await screen.findByText("1. Register a concrete Specimen")).toBeTruthy();
    expect(screen.getByLabelText("Strain column")).toBeTruthy();
    expect(screen.getByLabelText("Stress column")).toBeTruthy();
    expect(screen.getByText(/Column names are never inferred/)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});
