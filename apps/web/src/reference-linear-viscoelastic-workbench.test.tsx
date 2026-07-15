import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferenceLinearViscoelasticWorkbench } from "./reference-linear-viscoelastic-workbench";
import type {
  LinearViscoelasticModelResponse,
  MaterialStateResponse,
  PropertySetResponse,
} from "./types";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const stateId = "b1000000-0000-4000-8000-000000000001";
const propertyRevisionId = "b1000000-0000-4000-8000-000000000002";
const modelId = "b1000000-0000-4000-8000-000000000003";
const modelRevisionId = "b1000000-0000-4000-8000-000000000004";
const actor = "b1000000-0000-4000-8000-000000000005";
const organization = "b1000000-0000-4000-8000-000000000006";
const project = "b1000000-0000-4000-8000-000000000007";

const revision = {
  id: "b1000000-0000-4000-8000-000000000008",
  aggregate_id: stateId,
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-15T00:00:00Z",
  created_by: actor,
  change_reason: "fixture",
  organization_id: organization,
  project_id: project,
  classification: "internal" as const,
  lifecycle_state: "draft" as const,
};

const provenance = {
  entity_type: "catalog.revision",
  reference_type: "catalog.revision",
  revision_id: revision.id,
  content_sha256: revision.content_hash,
  based_on_revision_id: null,
  recorded_at: revision.created_at,
  recorded_by: actor,
};

const state: MaterialStateResponse = {
  material_state_id: stateId,
  material_id: "b1000000-0000-4000-8000-000000000009",
  current_revision: {
    ...revision,
    content: {
      material_id: "b1000000-0000-4000-8000-000000000009",
      material_revision_id: "b1000000-0000-4000-8000-00000000000a",
      name: "Polymer, conditioned",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance,
  },
  property_sets_url: `/api/v1/material-states/${stateId}/property-sets`,
};

const propertySet: PropertySetResponse = {
  property_set_id: "b1000000-0000-4000-8000-00000000000b",
  material_state_id: stateId,
  current_revision: {
    ...revision,
    id: propertyRevisionId,
    content: {
      material_state_id: stateId,
      material_state_revision_id: revision.id,
      density_kg_per_m3: 1200,
      density_source: { kind: "manual", reference: null },
      youngs_modulus_pa: 3_000_000_000,
      youngs_modulus_source: { kind: "manual", reference: null },
      poisson_ratio: 0.35,
      poisson_ratio_source: { kind: "manual", reference: null },
      yield_stress_pa: null,
      yield_stress_source: null,
      applicability: {
        temperature_min_k: null,
        temperature_max_k: null,
        strain_rate_min_per_s: null,
        strain_rate_max_per_s: null,
        note: null,
      },
    },
    provenance,
  },
};

const model: LinearViscoelasticModelResponse = {
  material_model_id: modelId,
  material_state_id: stateId,
  current_revision: {
    ...revision,
    id: modelRevisionId,
    aggregate_id: modelId,
    content: {
      model_family_id: "urn:cmp:reference:isotropic-linear-viscoelastic-prony:1.0.0",
      model_schema_version: "1.0.0",
      model_schema_digest: `sha256:${"b".repeat(64)}`,
      material_id: state.material_id,
      material_revision_id: state.current_revision.content.material_revision_id,
      material_state_id: stateId,
      material_state_revision_id: state.current_revision.id,
      property_set_id: propertySet.property_set_id,
      property_set_revision_id: propertyRevisionId,
      density_kg_per_m3: 1200,
      youngs_modulus_pa: 3_000_000_000,
      poisson_ratio: 0.35,
      elastic_moduli_convention: "instantaneous",
      bulk_relaxation_status: "not_characterized",
      terms: [
        { ordinal: 1, g_ratio: 0.2, k_ratio: 0, relaxation_time_s: 0.1 },
        { ordinal: 2, g_ratio: 0.3, k_ratio: 0, relaxation_time_s: 10 },
      ],
      reference_temperature_k: 293.15,
      non_production: true,
    },
    ir: {},
  },
  links: {},
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ReferenceLinearViscoelasticWorkbench", () => {
  it("creates a typed Prony IR and plots the backend relaxation response", async () => {
    let created = false;
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      if (url.endsWith(`/material-states/${stateId}/linear-viscoelastic-models`)) {
        if (init?.method === "POST") {
          created = true;
          return Promise.resolve(response(model, 201));
        }
        return Promise.resolve(response({ items: created ? [model] : [] }));
      }
      if (url.endsWith(`/linear-viscoelastic-models/${modelId}/response`)) {
        return Promise.resolve(response({
          material_model_id: modelId,
          material_model_revision_id: modelRevisionId,
          elastic_moduli_convention: "instantaneous",
          time_unit: "s",
          modulus_unit: "Pa",
          points: [
            { time_s: 0, shear_modulus_pa: 1_111_111_111, bulk_modulus_pa: 3_333_333_333 },
            { time_s: 1000, shear_modulus_pa: 555_555_555, bulk_modulus_pa: 3_333_333_333 },
          ],
        }));
      }
      return Promise.resolve(response({ items: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceLinearViscoelasticWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        state={state}
        propertySet={propertySet}
      />,
    );

    expect(await screen.findByText("No Prony IR exists for this Material State yet.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Prony IR" }));

    expect(await screen.findByRole("img", { name: "Shear relaxation modulus curve" })).toBeTruthy();
    expect(screen.getByText("not characterized")).toBeTruthy();
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
      expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
        property_set_revision_id: propertyRevisionId,
        bulk_relaxation_status: "not_characterized",
        terms: [
          { g_ratio: 0.2, k_ratio: 0, relaxation_time_s: 0.1 },
          { g_ratio: 0.3, k_ratio: 0, relaxation_time_s: 10 },
        ],
      });
    });
  });
});
