import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CatalogGenealogyWorkbench } from "./catalog-genealogy-workbench";
import type { MaterialStateResponse } from "./types";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const stateId = "e1000000-0000-4000-8000-000000000001";
const stateRevisionId = "e1000000-0000-4000-8000-000000000002";
const materialId = "e1000000-0000-4000-8000-000000000003";
const materialRevisionId = "e1000000-0000-4000-8000-000000000004";
const processId = "e1000000-0000-4000-8000-000000000005";
const processRevisionId = "e1000000-0000-4000-8000-000000000006";
const lotId = "e1000000-0000-4000-8000-000000000007";
const lotRevisionId = "e1000000-0000-4000-8000-000000000008";

const metadata = {
  id: stateRevisionId,
  aggregate_id: stateId,
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:catalog:fixture:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-16T00:00:00Z",
  created_by: "e1000000-0000-4000-8000-000000000009",
  change_reason: "fixture",
  organization_id: "e1000000-0000-4000-8000-00000000000a",
  project_id: "e1000000-0000-4000-8000-00000000000b",
  classification: "internal" as const,
  lifecycle_state: "draft" as const,
};

const provenance = {
  entity_type: "catalog.revision",
  reference_type: "catalog.revision",
  revision_id: stateRevisionId,
  content_sha256: metadata.content_hash,
  based_on_revision_id: null,
  recorded_at: metadata.created_at,
  recorded_by: metadata.created_by,
};

const state: MaterialStateResponse = {
  material_state_id: stateId,
  material_id: materialId,
  current_revision: {
    ...metadata,
    content: {
      material_id: materialId,
      material_revision_id: materialRevisionId,
      name: "Q&T state",
      manufacturing_route: "legacy route text",
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance,
  },
  property_sets_url: `/api/v1/material-states/${stateId}/property-sets`,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CatalogGenealogyWorkbench", () => {
  it("submits exact Process and Lot revision IDs instead of latest aliases", async () => {
    let submitted: Record<string, unknown> | null = null;
    const process = {
      process_definition_id: processId,
      current_revision: {
        ...metadata,
        id: processRevisionId,
        aggregate_id: processId,
        content: {
          process_code: "HT-QT-01",
          name: "Quench and temper",
          kind: "heat_treatment",
          description: null,
        },
        provenance,
      },
    };
    const lot = {
      material_lot_id: lotId,
      material_id: materialId,
      current_revision: {
        ...metadata,
        id: lotRevisionId,
        aggregate_id: lotId,
        content: {
          material_id: materialId,
          material_revision_id: materialRevisionId,
          lot_code: "HEAT-001",
          kind: "batch",
          manufacturer: null,
          supplier: null,
          description: null,
        },
        provenance,
      },
    };
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/process-definitions")) {
        return response({ items: [process] });
      }
      if (url.endsWith(`/materials/${materialId}/lots`)) {
        return response({ items: [lot] });
      }
      if (url.endsWith(`/material-states/${stateId}/genealogy`)) {
        if (init?.method === "POST") {
          submitted = JSON.parse(String(init.body)) as Record<string, unknown>;
          return response({}, 201);
        }
        return response(null);
      }
      return response({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CatalogGenealogyWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        state={state}
      />,
    );

    await screen.findByText(/Quench and temper/);
    fireEvent.change(screen.getByLabelText("Heat-treatment process"), {
      target: { value: processId },
    });
    fireEvent.change(screen.getByLabelText("Lot / Batch"), {
      target: { value: lotId },
    });
    fireEvent.click(screen.getByRole("button", { name: "Establish genealogy" }));

    await waitFor(() => expect(submitted).not.toBeNull());
    const content = (submitted as unknown as { content: Record<string, unknown> }).content;
    expect(content.material_state_revision_id).toBe(stateRevisionId);
    expect(content.heat_treatment_process_revision_id).toBe(processRevisionId);
    expect(content.material_lot_revision_id).toBe(lotRevisionId);
  });
});
