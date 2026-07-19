import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NeutralHyperelasticExport } from "./neutral-hyperelastic-export";
import type { NeutralMaterialResponse } from "./types";

const neutralId = "e5700000-0000-4000-8000-000000000001";
const neutralRevisionId = "e5700000-0000-4000-8000-000000000002";
const cardId = "e5700000-0000-4000-8000-000000000003";
const sha = "a".repeat(64);
const neutral: NeutralMaterialResponse = {
  neutral_material_id: neutralId,
  neutral_material_revision_id: neutralRevisionId,
  revision_no: 1,
  content_hash: sha,
  document_artifact: { artifact_id: cardId, sha256: sha },
  document: {
    document_type: "cmp.neutral-material",
    schema_version: "1.0.0",
    document_id: neutralId,
    content_sha256: sha,
    sources: {
      material: { id: "material-1", revision_id: "material-revision-1" },
      material_state: { id: "state-1", revision_id: "state-revision-1" },
      property_set: { id: "properties-1", revision_id: "properties-revision-1" },
      datasets: [{
        dataset: { id: "dataset-1", revision_id: "dataset-revision-1" },
        role: "calibration",
        test_mode: "uniaxial_tension",
      }],
    },
    curve_stages: [],
    candidate_selection: {
      candidate_id: cardId,
      reason: "Reviewed",
      stability_status: "monotonic_on_fitted_domain",
      warnings: [],
    },
    material_model_ir: {
      model: { id: neutralId, revision_id: neutralRevisionId },
      schema_id: "urn:cmp:modeling:neutral-hyperelastic-ir:1.0.0",
      schema_version: "1.0.0",
      model_family: "generalized_maxwell",
      constitutive_model: {
        family: "generalized_maxwell",
        parameters: {
          youngs_modulus_pa: { value: 3.3e9, unit: "Pa" },
          poisson_ratio: { value: 0.495, unit: "1" },
        },
      },
      maturity: "reference",
      non_production: true,
    },
    applicability: { engineering_strain: { minimum: 0, maximum: 0.5, unit: "1" } },
    validation: { status: "reference_numerical_checks_passed" },
  },
  links: { self: "", download: "" },
};

function json(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("NeutralHyperelasticExport", () => {
  it("acknowledges OpenRadioss LPRONY prerequisites and previews native ASCII", async () => {
    const report = {
      mapping_report_sha256: sha,
      exportable: true,
      report: {
        neutral_material_id: neutralId,
        neutral_material_revision_id: neutralRevisionId,
        neutral_material_sha256: sha,
        model_schema_digest: sha,
        model_family: "generalized_maxwell",
        family: "generalized_maxwell",
        target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
        items: [
          {
            name: "shear_prony_terms",
            ir_path: "/material_model_ir/constitutive_model/terms",
            target_representation: "/VISC/LPRONY/GAMMA_i,TAU_i",
            status: "exact",
            detail: "Ordered shear ratios and relaxation times map directly.",
          },
          {
            name: "solid_property_total_strain",
            ir_path: "/applicability/solver_property",
            target_representation: "/PROP I_smstr=10 or 12",
            status: "approximated",
            detail: "A compatible external total-strain property is required.",
          },
        ],
        exporter: {
          id: "cmp.reference.openradioss-linear-lprony",
          version: "1.0.0",
          digest: sha,
          documentation_url:
            "https://help.altair.com/hwsolvers/rad/topics/solvers/rad/visc_lprony_starter_r.htm",
        },
        non_production: true,
      },
    };
    const card = {
      solver_card_id: cardId,
      neutral_material_id: neutralId,
      target: report.report.target,
      current_revision: {
        id: cardId,
        aggregate_id: cardId,
        revision_no: 1,
        based_on_revision_id: null,
        schema_id: "urn:cmp:exporting:neutral-hyperelastic-card:1.0.0",
        schema_version: "1.0.0",
        content_hash: sha,
        created_at: "2026-07-18T00:00:00Z",
        created_by: cardId,
        change_reason: "Reviewed",
        organization_id: cardId,
        project_id: cardId,
        classification: "internal",
        lifecycle_state: "draft",
        content: {
          neutral_material_id: neutralId,
          neutral_material_revision_id: neutralRevisionId,
          neutral_material_sha256: sha,
          model_schema_digest: sha,
          model_family: "generalized_maxwell",
          family: "generalized_maxwell",
          target: report.report.target,
          solver_material_id: 301,
          material_name: "POLYMER_REFERENCE",
          density_kg_per_m3: 1100,
          constitutive_model: {},
          applicability: { engineering_strain: { minimum: 0, maximum: 0.5, unit: "1" } },
          mapping_statuses: { solid_property_total_strain: "approximated" },
          mapping_report_sha256: sha,
          card_sha256: sha,
          exporter: { id: "cmp.reference", version: "1.0.0", digest: sha },
          non_production: true,
        },
      },
      links: { self: "", mapping_report: "", preview: "", download: "" },
    };
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/solver-card-preflight") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        expect(body.neutral_material_revision_id).toBe(neutralRevisionId);
        expect(body.target.solver).toBe("openradioss");
        return json(report);
      }
      if (url.endsWith("/solver-cards") && init?.method === "POST") {
        expect(JSON.parse(String(init.body)).expected_mapping_report_sha256).toBe(sha);
        return json(card, 201);
      }
      if (url.endsWith(`/neutral-solver-cards/${cardId}/preview`)) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "text/plain" }),
          text: async () =>
            "/MAT/LAW1/301/1\nPOLYMER_REFERENCE\n/VISC/LPRONY/301/1\n",
        } as Response;
      }
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const onNavigate = vi.fn();

    render(
      <NeutralHyperelasticExport
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        neutralMaterial={neutral}
        onNavigate={onNavigate}
      />,
    );
    expect(screen.getByText("Neutral Material JSON → verified mapping → native solver card")).toBeTruthy();
    expect(screen.getByText("5 exact references")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download exact Neutral JSON" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Return to Material datasheet" }));
    expect(onNavigate).toHaveBeenCalledWith("/materials/material-1/models");
    fireEvent.change(screen.getByLabelText("Solver target"), {
      target: { value: "openradioss" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run mapping preflight" }));
    expect((await screen.findAllByText("approximated")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("/VISC/LPRONY")).toBeTruthy();
    expect(screen.getByLabelText("All solver mapping status meanings")).toBeTruthy();
    const create = screen.getByRole("button", { name: "Create solver card" });
    expect((create as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/I reviewed every approximated/));
    expect((create as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(create);
    expect(await screen.findByText(/openradioss card r1 created/)).toBeTruthy();
    expect(await screen.findByText(/\/VISC\/LPRONY\/301\/1/)).toBeTruthy();
    expect(screen.queryByLabelText("Exact reviewed evidence")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Review exact evidence and mapping" }));
    expect(screen.getByLabelText("Exact reviewed evidence")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download native ASCII card" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download mapping report JSON" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add exact files to a bulk package" }));
    expect(onNavigate).toHaveBeenCalledWith("/exports");
  });
});
