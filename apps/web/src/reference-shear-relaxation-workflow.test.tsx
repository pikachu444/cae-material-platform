import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferenceShearRelaxationWorkflow } from "./reference-shear-relaxation-workflow";
import type { MaterialStateResponse } from "./types";

function response(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const stateId = "d1000000-0000-4000-8000-000000000001";
const state: MaterialStateResponse = {
  material_state_id: stateId,
  material_id: "d1000000-0000-4000-8000-000000000002",
  current_revision: {
    id: "d1000000-0000-4000-8000-000000000003",
    aggregate_id: stateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:material-state:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-15T00:00:00Z",
    created_by: "d1000000-0000-4000-8000-000000000004",
    change_reason: "fixture",
    organization_id: "d1000000-0000-4000-8000-000000000005",
    project_id: "d1000000-0000-4000-8000-000000000006",
    classification: "internal",
    lifecycle_state: "draft",
    content: {
      material_id: "d1000000-0000-4000-8000-000000000002",
      material_revision_id: "d1000000-0000-4000-8000-000000000007",
      name: "Reference polymer state",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance: {
      entity_type: "catalog.material_state.revision",
      reference_type: "catalog.material_state.revision",
      revision_id: "d1000000-0000-4000-8000-000000000003",
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-07-15T00:00:00Z",
      recorded_by: "d1000000-0000-4000-8000-000000000004",
    },
  },
  property_sets_url: `/api/v1/material-states/${stateId}/property-sets`,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Reference shear-relaxation workflow", () => {
  it("loads the scoped testing and Dataset records from the real API routes", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ReferenceShearRelaxationWorkflow
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        state={state}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open workflow" }));

    expect(await screen.findByText("Register shear-relaxation method")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
      `/api/v1/material-states/${stateId}/shear-relaxation-datasets`,
    );
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
      `/api/v1/material-states/${stateId}/linear-viscoelastic-models`,
    );
    expect(screen.getByText(/not silently fitted into Prony terms/i)).toBeTruthy();
    expect(screen.getByText("Observed-point time crop")).toBeTruthy();
    expect(screen.getByText(/separate processed Dataset identity/i)).toBeTruthy();
    expect(screen.getByText("no interpolation")).toBeTruthy();
  });
});
