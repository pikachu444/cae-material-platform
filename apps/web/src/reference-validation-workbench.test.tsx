import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReferenceValidationWorkbench } from "./reference-validation-workbench";
import type { MaterialStateResponse } from "./features/materials/contracts";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const materialStateId = "27000000-0000-4000-8000-000000000201";
const modelId = "27000000-0000-4000-8000-000000000202";
const modelRevisionId = "27000000-0000-4000-8000-000000000203";
const cardId = "27000000-0000-4000-8000-000000000204";
const cardRevisionId = "27000000-0000-4000-8000-000000000205";
const datasetId = "27000000-0000-4000-8000-000000000206";
const datasetRevisionId = "27000000-0000-4000-8000-000000000207";
const selectionId = "27000000-0000-4000-8000-000000000208";
const selectionRevisionId = "27000000-0000-4000-8000-000000000209";
const templateId = "27000000-0000-4000-8000-00000000020a";
const templateRevisionId = "27000000-0000-4000-8000-00000000020b";
const planId = "27000000-0000-4000-8000-00000000020c";
const planRevisionId = "27000000-0000-4000-8000-00000000020d";
const runId = "27000000-0000-4000-8000-00000000020e";
const validationResultId = "28000000-0000-4000-8000-00000000020f";

const state = {
  material_state_id: materialStateId,
  material_id: "27000000-0000-4000-8000-00000000020f",
  current_revision: {
    id: "27000000-0000-4000-8000-000000000210",
    aggregate_id: materialStateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:material-state:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-21T00:00:00Z",
    created_by: "27000000-0000-4000-8000-000000000211",
    change_reason: "demo",
    organization_id: "27000000-0000-4000-8000-000000000212",
    project_id: "27000000-0000-4000-8000-000000000213",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
    content: {
      material_id: "27000000-0000-4000-8000-00000000020f",
      material_revision_id: "27000000-0000-4000-8000-000000000214",
      name: "As received",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance: {
      entity_type: "catalog.material_state.revision",
      reference_type: "catalog.material_state.revision",
      revision_id: "27000000-0000-4000-8000-000000000210",
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-07-21T00:00:00Z",
      recorded_by: "27000000-0000-4000-8000-000000000211",
    },
  },
  property_sets_url: "/api/v1/material-states/example/property-sets",
} satisfies MaterialStateResponse;

function revision(id: string, aggregateId: string, content: object) {
  return {
    ...state.current_revision,
    id,
    aggregate_id: aggregateId,
    content,
  };
}

describe("Reference validation workbench", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("pins a Template, IR, Card, and experiment selection before collecting immutable mock evidence", async () => {
    const template = {
      validation_template_id: templateId,
      current_revision: revision(templateRevisionId, templateId, {
        template_label: "Reference tensile virtual specimen",
        template_kind: "reference_uniaxial_tensile_virtual_specimen",
      }),
      links: {},
    };
    const plan = {
      validation_plan_id: planId,
      current_revision: revision(planRevisionId, planId, {
        plan_label: "Reference tensile validation",
        plan_kind: "reference_uniaxial_tensile_validation",
      }),
      links: {},
    };
    const model = {
      material_model_id: modelId,
      material_state_id: materialStateId,
      current_revision: revision(modelRevisionId, modelId, {
        material_state_id: materialStateId,
        non_production: true,
      }),
      links: {},
    };
    const card = {
      solver_card_id: cardId,
      material_model_id: modelId,
      solver_material_id: 1,
      current_revision: revision(cardRevisionId, cardId, {}),
      links: {},
    };
    const dataset = {
      dataset_id: datasetId,
      current_revision: revision(datasetRevisionId, datasetId, {}),
      links: {},
    };
    const selection = {
      selection_id: selectionId,
      selection_label: "Normalized tensile curve",
      current_revision: revision(selectionRevisionId, selectionId, {}),
      links: {},
    };
    const queuedRun = {
      validation_run_id: runId,
      status: "queued",
      deck: { artifact_id: "27000000-0000-4000-8000-000000000215", sha256: "b".repeat(64) },
      runner_version: "1.0.0",
      failure_code: null,
      result_manifest: null,
      validation_result: null,
    };
    const terminalRun = {
      ...queuedRun,
      status: "succeeded",
      result_manifest: {
        solver_termination: "normal",
        native_result_state: "available",
        manifest_sha256: "c".repeat(64),
        deck: queuedRun.deck,
        stdout: { artifact_id: "27000000-0000-4000-8000-000000000216", sha256: "d".repeat(64) },
        stderr: { artifact_id: "27000000-0000-4000-8000-000000000217", sha256: "e".repeat(64) },
        native_result: { artifact_id: "27000000-0000-4000-8000-000000000218", sha256: "f".repeat(64) },
        manifest_artifact: { artifact_id: "27000000-0000-4000-8000-000000000219", sha256: "1".repeat(64) },
      },
    };
    const evaluatedRun = {
      ...terminalRun,
      validation_result: {
        validation_result_id: validationResultId,
        verdict: "passed",
        relative_root_mean_squared_error: 0,
        relative_rmse_threshold: 0.05,
        root_mean_squared_error_pa: 0,
        compared_point_count: 3,
        holdout_independence: "independent_selection",
        reason_code: null,
        response_extraction: {
          normalized_response: {
            artifact_id: "28000000-0000-4000-8000-000000000220",
            sha256: "2".repeat(64),
          },
        },
        numerical_health_report: {
          status: "healthy",
          report_artifact: {
            artifact_id: "28000000-0000-4000-8000-000000000221",
            sha256: "3".repeat(64),
          },
        },
        result_artifact: {
          artifact_id: "28000000-0000-4000-8000-000000000222",
          sha256: "4".repeat(64),
        },
      },
    };
    const curve = {
      validation_result_id: validationResultId,
      verdict: "passed",
      response_point_count: 3,
      returned_response_point_count: 3,
      response_sampled: false,
      response_points: [
        { engineering_strain: 0, engineering_stress_pa: 0 },
        { engineering_strain: 0.01, engineering_stress_pa: 2_100_000_000 },
        { engineering_strain: 0.02, engineering_stress_pa: 4_200_000_000 },
      ],
      comparison_point_count: 3,
      returned_comparison_point_count: 3,
      comparison_sampled: false,
      comparison_points: [
        {
          engineering_strain: 0,
          observed_engineering_stress_pa: 0,
          simulated_engineering_stress_pa: 0,
          residual_engineering_stress_pa: 0,
        },
        {
          engineering_strain: 0.01,
          observed_engineering_stress_pa: 2_100_000_000,
          simulated_engineering_stress_pa: 2_100_000_000,
          residual_engineering_stress_pa: 0,
        },
        {
          engineering_strain: 0.02,
          observed_engineering_stress_pa: 4_200_000_000,
          simulated_engineering_stress_pa: 4_200_000_000,
          residual_engineering_stress_pa: 0,
        },
      ],
    };
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/validation-templates?limit=100") && method === "GET") {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith("/validation-plans?limit=100") && method === "GET") {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith(`/material-states/${materialStateId}/material-models`)) {
        return Promise.resolve(jsonResponse({ items: [model] }));
      }
      if (url.endsWith(`/material-states/${materialStateId}/datasets`)) {
        return Promise.resolve(jsonResponse({ items: [dataset] }));
      }
      if (url.endsWith(`/material-models/${modelId}/solver-cards`)) {
        return Promise.resolve(jsonResponse({ items: [card] }));
      }
      if (url.endsWith(`/dataset-revisions/${datasetRevisionId}/selections`)) {
        return Promise.resolve(jsonResponse({ items: [selection] }));
      }
      if (url.endsWith("/validation-templates") && method === "POST") {
        return Promise.resolve(jsonResponse(template, 201));
      }
      if (url.endsWith("/validation-plans") && method === "POST") {
        return Promise.resolve(jsonResponse(plan, 201));
      }
      if (url.endsWith("/validation-runs") && method === "POST") {
        return Promise.resolve(jsonResponse(queuedRun, 202));
      }
      if (url.endsWith(`/validation-runs/${runId}:poll`) && method === "POST") {
        return Promise.resolve(jsonResponse(terminalRun));
      }
      if (url.endsWith(`/validation-runs/${runId}:evaluate`) && method === "POST") {
        return Promise.resolve(jsonResponse(evaluatedRun));
      }
      if (url.endsWith(`/validation-results/${validationResultId}/curve?maximum_points=1000`)) {
        return Promise.resolve(jsonResponse(curve));
      }
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ReferenceValidationWorkbench config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }} state={state} />);

    fireEvent.click(screen.getByRole("button", { name: "Open validation workbench" }));
    await screen.findByText("1. Create a reference virtual-specimen Template");
    await screen.findByRole("option", { name: /MAT\/ELAST\/1/ });
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Template" }));
    await screen.findByRole("option", { name: /Reference tensile virtual specimen/ });
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Validation Plan" }));
    await screen.findByRole("option", { name: /Reference tensile validation/ });
    fireEvent.click(screen.getByRole("button", { name: "Submit Validation Run" }));
    await screen.findByText(/Validation Run 27000000/);
    fireEvent.click(screen.getByRole("button", { name: "Collect mock outcome" }));
    await screen.findByText(/Termination: normal/);
    fireEvent.click(screen.getByRole("button", { name: "Extract response and evaluate" }));
    await screen.findByText("Reference result interpretation");
    await screen.findByRole("img", { name: "Observed and reference simulated engineering stress-strain curves" });

    await waitFor(() => {
      const planCall = fetchMock.mock.calls.find(([url, init]) => (
        String(url).endsWith("/validation-plans") && init?.method === "POST"
      ));
      expect(planCall).toBeTruthy();
      expect(JSON.parse(String(planCall?.[1]?.body))).toMatchObject({
        classification: "internal",
        content: {
          validation_template_id: templateId,
          validation_template_revision_id: templateRevisionId,
          material_model_id: modelId,
          material_model_revision_id: modelRevisionId,
          solver_card_id: cardId,
          solver_card_revision_id: cardRevisionId,
          experimental_selection_id: selectionId,
          experimental_selection_revision_id: selectionRevisionId,
        },
      });
      const pollCall = fetchMock.mock.calls.find(([url, init]) => (
        String(url).endsWith(`/validation-runs/${runId}:poll`) && init?.method === "POST"
      ));
      expect(pollCall).toBeTruthy();
      expect(JSON.parse(String(pollCall?.[1]?.body))).toMatchObject({ outcome: "succeeded" });
      const evaluateCall = fetchMock.mock.calls.find(([url, init]) => (
        String(url).endsWith(`/validation-runs/${runId}:evaluate`) && init?.method === "POST"
      ));
      expect(evaluateCall).toBeTruthy();
      expect(JSON.parse(String(evaluateCall?.[1]?.body))).toMatchObject({
        change_reason: expect.stringContaining("assess numerical health"),
      });
    });
  });
});
