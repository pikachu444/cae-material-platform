import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferenceElastoplasticWorkbench } from "./reference-elastoplastic-workbench";
import type { MaterialStateResponse, PropertySetResponse } from "./types";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

function textResponse(body: string): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "text/plain" }),
    text: async () => body,
  } as Response;
}

const stateId = "a1000000-0000-4000-8000-000000000001";
const propertySetRevisionId = "a1000000-0000-4000-8000-000000000002";
const datasetRevisionId = "a1000000-0000-4000-8000-000000000003";
const modelId = "a1000000-0000-4000-8000-000000000004";
const modelRevisionId = "a1000000-0000-4000-8000-000000000005";
const cardId = "a1000000-0000-4000-8000-000000000006";
const cardRevisionId = "a1000000-0000-4000-8000-000000000007";

const revision = {
  id: "a1000000-0000-4000-8000-000000000010",
  aggregate_id: stateId,
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-14T00:00:00Z",
  created_by: "a1000000-0000-4000-8000-000000000011",
  change_reason: "reference fixture",
  organization_id: "a1000000-0000-4000-8000-000000000012",
  project_id: "a1000000-0000-4000-8000-000000000013",
  classification: "internal" as const,
  lifecycle_state: "draft" as const,
};

const provenance = {
  entity_type: "catalog.material_state.revision",
  reference_type: "catalog.material_state.revision",
  revision_id: revision.id,
  content_sha256: revision.content_hash,
  based_on_revision_id: null,
  recorded_at: revision.created_at,
  recorded_by: revision.created_by,
};

const state = {
  material_state_id: stateId,
  material_id: "a1000000-0000-4000-8000-000000000014",
  current_revision: {
    ...revision,
    content: {
      material_id: "a1000000-0000-4000-8000-000000000014",
      material_revision_id: "a1000000-0000-4000-8000-000000000015",
      name: "DP600 as received",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance,
  },
  property_sets_url: `/api/v1/material-states/${stateId}/property-sets`,
} satisfies MaterialStateResponse;

const source = {
  kind: "literature" as const,
  reference: "Public reference fixture",
};

const propertySet = {
  property_set_id: "a1000000-0000-4000-8000-000000000016",
  material_state_id: stateId,
  current_revision: {
    ...revision,
    id: propertySetRevisionId,
    aggregate_id: "a1000000-0000-4000-8000-000000000016",
    content: {
      material_state_id: stateId,
      material_state_revision_id: revision.id,
      density_kg_per_m3: 7850,
      density_source: source,
      youngs_modulus_pa: 210_000_000_000,
      youngs_modulus_source: source,
      poisson_ratio: 0.3,
      poisson_ratio_source: source,
      yield_stress_pa: 355_000_000,
      yield_stress_source: source,
      applicability: {
        temperature_min_k: null,
        temperature_max_k: null,
        strain_rate_min_per_s: null,
        strain_rate_max_per_s: null,
        note: "Ambient quasi-static reference only",
      },
    },
    provenance: { ...provenance, revision_id: propertySetRevisionId },
  },
} satisfies PropertySetResponse;

function modelFixture() {
  return {
    material_model_id: modelId,
    material_state_id: stateId,
    current_revision: {
      ...revision,
      id: modelRevisionId,
      aggregate_id: modelId,
      content: {
        model_family_id: "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0",
        model_schema_version: "1.0.0",
        model_schema_digest: "b".repeat(64),
        material_id: state.material_id,
        material_revision_id: state.current_revision.content.material_revision_id,
        material_state_id: stateId,
        material_state_revision_id: revision.id,
        property_set_id: propertySet.property_set_id,
        property_set_revision_id: propertySetRevisionId,
        source_dataset_id: "a1000000-0000-4000-8000-000000000017",
        source_dataset_revision_id: datasetRevisionId,
        density_kg_per_m3: 7850,
        youngs_modulus_pa: 210_000_000_000,
        poisson_ratio: 0.3,
        initial_yield_stress_pa: 355_000_000,
        hardening_curve: {
          artifact_id: "a1000000-0000-4000-8000-000000000018",
          sha256: "c".repeat(64),
          schema_ref: "urn:cmp:modeling:reference-true-stress-plastic-strain-parquet:1.0.0",
          point_count: 4,
          independent_quantity: "true_plastic_strain",
          independent_unit: "1",
          dependent_quantity: "true_yield_stress",
          dependent_unit: "Pa",
        },
        source_point_count: 6,
        pre_yield_excluded_point_count: 3,
        post_necking_excluded_point_count: 1,
        necking_source_point_index: 4,
        transformation_profile_id:
          "urn:cmp:processing:reference-pre-necking-true-plastic-reduction:1.0.0",
        transformation_profile_version: "1.0.0",
        transformation_profile_digest: "d".repeat(64),
        necking_engineering_strain: 0.12,
        characterized_max_true_plastic_strain: 0.08,
        extension_max_true_plastic_strain: 0.25,
        post_necking_extension_policy: "approved_constant_true_stress",
        post_necking_approximation_acknowledged: true,
        applicability: propertySet.current_revision.content.applicability,
        reference_temperature_k: 293.15,
        non_production: true,
      },
      ir: {},
      provenance: {},
    },
    links: {},
  };
}

describe("Reference elastoplastic workbench", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("derives a pinned curve and exports an explicitly acknowledged Abaqus card", async () => {
    const model = modelFixture();
    const dataset = {
      dataset_id: "a1000000-0000-4000-8000-000000000017",
      test_run_id: "a1000000-0000-4000-8000-000000000019",
      current_revision: {
        ...revision,
        id: datasetRevisionId,
        content: { representation: "processed", point_count: 6 },
      },
      links: {},
    };
    const curve = {
      material_model_id: modelId,
      material_model_revision_id: modelRevisionId,
      artifact_id: model.current_revision.content.hardening_curve.artifact_id,
      artifact_sha256: "c".repeat(64),
      points: [
        { true_plastic_strain: 0, true_yield_stress_pa: 355_000_000, origin: "catalog_yield_anchor" },
        { true_plastic_strain: 0.01, true_yield_stress_pa: 420_000_000, origin: "pre_necking_observation" },
        { true_plastic_strain: 0.08, true_yield_stress_pa: 535_000_000, origin: "pre_necking_observation" },
        { true_plastic_strain: 0.25, true_yield_stress_pa: 535_000_000, origin: "approved_constant_extension" },
      ],
    };
    const target = { solver: "abaqus", version: "2025", unit_system: "kg_m_s" };
    const mapping = {
      material_model_id: modelId,
      material_model_revision_id: modelRevisionId,
      model_schema_digest: "b".repeat(64),
      target,
      items: [
        {
          name: "post_necking_extension",
          ir_path: "/transformation/post_necking_extension_policy",
          target_representation: "*PLASTIC, EXTRAPOLATION=CONSTANT",
          status: "approximated",
          detail: "Explicitly acknowledged constant-stress extension.",
        },
      ],
      exporter_id: "cmp.reference.abaqus-isotropic-plasticity",
      exporter_version: "1.0.0",
      exporter_digest: "e".repeat(64),
      mapping_report_sha256: "f".repeat(64),
      exportable: true,
      non_production: true,
    };
    const card = {
      solver_card_id: cardId,
      material_model_id: modelId,
      target,
      solver_material_id: 101,
      material_name: "DP600_as_received",
      current_revision: {
        ...revision,
        id: cardRevisionId,
        aggregate_id: cardId,
        content: {
          hardening_curve_point_count: 4,
          card_sha256: "1".repeat(64),
        },
        provenance: {},
      },
      links: {},
    };
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith(`/material-states/${stateId}/datasets`)) {
        return Promise.resolve(jsonResponse({ items: [dataset] }));
      }
      if (url.endsWith(`/material-states/${stateId}/tabulated-plasticity-models`)) {
        return Promise.resolve(
          jsonResponse(method === "POST" ? model : { items: [] }, method === "POST" ? 201 : 200),
        );
      }
      if (url.endsWith(`/tabulated-plasticity-models/${modelId}/hardening-curve`)) {
        return Promise.resolve(jsonResponse(curve));
      }
      if (url.endsWith(`/tabulated-plasticity-models/${modelId}/mapping-preflight`)) {
        return Promise.resolve(jsonResponse(mapping));
      }
      if (url.endsWith(`/tabulated-plasticity-models/${modelId}/solver-cards`)) {
        return Promise.resolve(
          jsonResponse(method === "POST" ? { card, mapping_report: mapping } : { items: [] }),
        );
      }
      if (url.endsWith(`/elastoplastic-solver-cards/${cardId}/preview`)) {
        return Promise.resolve(
          textResponse("*MATERIAL, NAME=DP600_as_received\n*PLASTIC, HARDENING=ISOTROPIC\n"),
        );
      }
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceElastoplasticWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
        propertySet={propertySet}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Build an elastoplastic Solver Card" }));
    await screen.findByText("1. Select concrete Dataset and Property Set revisions");
    fireEvent.click(
      screen.getByRole("checkbox", { name: /constant true-stress extension/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Create elastoplastic IR" }));

    await screen.findByText(/Source points: 6/);
    expect(screen.getByText(/post-necking excluded: 1/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus" } });
    fireEvent.click(screen.getByRole("button", { name: "Run mapping preflight" }));

    expect(await screen.findByText("approximated")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Generate Abaqus .inp" }));
    await screen.findByText("*MATERIAL / *PLASTIC");
    expect(screen.getByRole("button", { name: "Download .inp" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText(/\*MATERIAL, NAME=DP600_as_received/)).toBeTruthy();

    await waitFor(() => {
      const modelCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith(`/material-states/${stateId}/tabulated-plasticity-models`) &&
          init?.method === "POST",
      );
      expect(JSON.parse(String(modelCall?.[1]?.body))).toMatchObject({
        property_set_revision_id: propertySetRevisionId,
        dataset_revision_id: datasetRevisionId,
        acknowledge_post_necking_approximation: true,
      });
      const cardCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith(`/tabulated-plasticity-models/${modelId}/solver-cards`) &&
          init?.method === "POST",
      );
      expect(JSON.parse(String(cardCall?.[1]?.body))).toMatchObject({
        material_model_revision_id: modelRevisionId,
        target,
        expected_mapping_report_sha256: mapping.mapping_report_sha256,
      });
    });
  });

  it("promotes one exact selected hardening output without hiding its lineage", async () => {
    const outputId = "a1000000-0000-4000-8000-000000000030";
    const outputRevisionId = "a1000000-0000-4000-8000-000000000031";
    const output = {
      processing_output_id: outputId,
      current_revision: { ...revision, id: outputRevisionId, aggregate_id: outputId },
      label: "DP600 selected Swift + Voce hardening",
      source_document: {
        aggregate_id: "a1000000-0000-4000-8000-000000000032",
        revision_id: "a1000000-0000-4000-8000-000000000033",
      },
      source_document_sha256: "1".repeat(64),
      source_canonical_artifact_sha256: "2".repeat(64),
      mapping_profile: {
        aggregate_id: "a1000000-0000-4000-8000-000000000034",
        revision_id: "a1000000-0000-4000-8000-000000000035",
      },
      mapping_profile_sha256: "3".repeat(64),
      steps: [
        {
          method_id: "metal.hardening_fit_extrapolate",
          method_version: "1.0.0",
          options: {},
        },
      ],
      independent_quantity: "strain.true_plastic",
      stage_count: 2,
      final_point_count: 21,
      output_artifact_id: "a1000000-0000-4000-8000-000000000036",
      output_sha256: "4".repeat(64),
    };
    const processedModel = modelFixture();
    Object.assign(processedModel.current_revision.content, {
      source_dataset_id: null,
      source_dataset_revision_id: null,
      necking_engineering_strain: null,
      post_necking_extension_policy: "selected_fitted_bounded_extrapolation",
      source_point_count: null,
      pre_yield_excluded_point_count: null,
      post_necking_excluded_point_count: null,
      necking_source_point_index: null,
      processing_projection: {
        output_id: outputId,
        output_revision_id: outputRevisionId,
        output_sha256: "sha256:" + "4".repeat(64),
        source_test_data_id: output.source_document.aggregate_id,
        source_test_data_revision_id: output.source_document.revision_id,
        mapping_profile_id: output.mapping_profile.aggregate_id,
        mapping_profile_revision_id: output.mapping_profile.revision_id,
        candidate_families: ["voce", "swift"],
        primary_family: "swift",
        secondary_family: "voce",
        primary_weight: 0.5,
        fit_minimum_true_plastic_strain: 0.0001,
        recipe_batch: {
          processing_recipe: {
            id: "a1000000-0000-4000-8000-000000000050",
            revision_id: "a1000000-0000-4000-8000-000000000051",
            sha256: "sha256:" + "7".repeat(64),
          },
          processing_batch_id: "a1000000-0000-4000-8000-000000000052",
          batch_member_id: "a1000000-0000-4000-8000-000000000053",
          batch_attempt_id: "a1000000-0000-4000-8000-000000000054",
          batch_attempt_no: 1,
        },
      },
    });
    const curve = {
      material_model_id: modelId,
      material_model_revision_id: modelRevisionId,
      artifact_id: processedModel.current_revision.content.hardening_curve.artifact_id,
      artifact_sha256: "c".repeat(64),
      points: Array.from({ length: 21 }, (_, ordinal) => ({
        true_plastic_strain: ordinal / 40,
        true_yield_stress_pa: 250_000_000 + ordinal * 5_000_000,
        origin: "processing_selected_sample",
      })),
    };
    let resolveHistoricalCandidates: ((response: Response) => void) | null = null;
    const historicalCandidates = new Promise<Response>((resolve) => {
      resolveHistoricalCandidates = resolve;
    });
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith(`/material-states/${stateId}/datasets`)) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith("/processing-outputs")) {
        return Promise.resolve(jsonResponse({ items: [output] }));
      }
      if (url.endsWith(`/material-states/${stateId}/tabulated-plasticity-models`)) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith(`/processing-outputs/${outputId}/tabulated-plasticity-models`)) {
        return Promise.resolve(jsonResponse(processedModel, method === "POST" ? 201 : 200));
      }
      if (url.endsWith("/neutral-materials:promote-metal")) {
        return Promise.resolve(jsonResponse({
          neutral_material_id: "a1000000-0000-4000-8000-000000000040",
          neutral_material_revision_id: "a1000000-0000-4000-8000-000000000041",
          revision_no: 1,
          content_hash: "5".repeat(64),
          document_artifact: { artifact_id: "a1000000-0000-4000-8000-000000000042", sha256: "6".repeat(64) },
          document: {},
          links: {},
        }, 201));
      }
      if (url.endsWith(`/tabulated-plasticity-models/${modelId}/hardening-curve`)) {
        return Promise.resolve(jsonResponse(curve));
      }
      if (url.endsWith(`/tabulated-plasticity-models/${modelId}/solver-cards`)) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.includes("/bulk-export-candidates?")) {
        return historicalCandidates;
      }
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const view = render(
      <ReferenceElastoplasticWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
        propertySet={propertySet}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Build an elastoplastic Solver Card" }));
    await screen.findByText("1B. Promote a fitted metal Processing Output (recommended)");
    expect(
      (screen.getByLabelText("Exact Processing Output revision") as HTMLSelectElement).value,
    ).toBe(outputId);
    fireEvent.click(screen.getByRole("checkbox", { name: /reviewed the candidate blend/i }));
    fireEvent.click(screen.getByRole("button", { name: "Promote fitted output to IR" }));

    expect(
      await screen.findByText("Origin: selected fitted hardening Processing Output"),
    ).toBeTruthy();
    view.rerender(
      <ReferenceElastoplasticWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
        propertySet={propertySet}
        preferredProcessingOutputId={outputId}
      />,
    );
    await waitFor(() => {
      const modelListCalls = fetchMock.mock.calls.filter(([url, init]) =>
        String(url).endsWith(`/material-states/${stateId}/tabulated-plasticity-models`)
        && (init?.method ?? "GET") === "GET",
      );
      expect(modelListCalls.length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("Origin: selected fitted hardening Processing Output")).toBeTruthy();
    });
    expect(await screen.findByText(/Published Recipe revision:/)).toBeTruthy();
    expect(await screen.findByText(/Successful Batch attempt #1/)).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Open Recipe library and Batch monitor" }).getAttribute("href"),
    ).toBe("/datasets/processing");
    expect(
      await screen.findByText(/Selected fitted hardening samples from an exact Processing Output/),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Create Neutral Material JSON" }));
    expect(await screen.findByRole("button", { name: "Download Neutral JSON r1" })).toBeTruthy();
    resolveHistoricalCandidates?.(jsonResponse({ items: [] }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Download Neutral JSON r1" })).toBeTruthy();
    });
    expect(screen.getByText("Exact Neutral JSON r1 restored")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create Neutral Material JSON" })).toBeNull();
    await waitFor(() => {
      const promotionCall = fetchMock.mock.calls.find(([url, init]) =>
        String(url).endsWith(`/processing-outputs/${outputId}/tabulated-plasticity-models`) &&
        init?.method === "POST",
      );
      expect(JSON.parse(String(promotionCall?.[1]?.body))).toMatchObject({
        material_state_id: stateId,
        property_set_revision_id: propertySetRevisionId,
        processing_output_revision_id: outputRevisionId,
        acknowledge_bounded_extrapolation: true,
      });
      const neutralCall = fetchMock.mock.calls.find(([url, init]) =>
        String(url).endsWith("/neutral-materials:promote-metal") && init?.method === "POST",
      );
      expect(JSON.parse(String(neutralCall?.[1]?.body))).toMatchObject({
        material_model_id: modelId,
        material_model_revision_id: modelRevisionId,
      });
    });
  });
});
