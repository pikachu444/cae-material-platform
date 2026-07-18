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
    sources: { datasets: [] },
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
      constitutive_model: {
        family: "mooney_rivlin",
        parameters: { c10_pa: { value: 1e6, unit: "Pa" } },
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
  it("requires explicit acknowledgement, creates a card, and previews native ASCII", async () => {
    const report = {
      mapping_report_sha256: sha,
      exportable: true,
      report: {
        neutral_material_id: neutralId,
        neutral_material_revision_id: neutralRevisionId,
        neutral_material_sha256: sha,
        model_schema_digest: sha,
        family: "mooney_rivlin",
        target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
        items: [
          {
            name: "constitutive_parameters",
            ir_path: "/material_model_ir/constitutive_model",
            target_representation: "/MAT/LAW82",
            status: "transformed",
            detail: "Exact strain-energy transformation.",
          },
          {
            name: "volumetric_response",
            ir_path: "/material_model_ir/volumetric_response",
            target_representation: "explicit LAW82 nu",
            status: "approximated",
            detail: "Explicit nu=0.495 approximation.",
          },
        ],
        exporter: {
          id: "cmp.reference.openradioss-neutral-hyperelastic",
          version: "1.0.0",
          digest: sha,
          documentation_url: "https://example.invalid/law82",
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
          family: "mooney_rivlin",
          target: report.report.target,
          solver_material_id: 301,
          material_name: "ELASTOMER_REFERENCE",
          density_kg_per_m3: 1100,
          constitutive_model: {},
          applicability: { engineering_strain: { minimum: 0, maximum: 0.5, unit: "1" } },
          mapping_statuses: { volumetric_response: "approximated" },
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
      if (url.endsWith(`/neutral-hyperelastic-solver-cards/${cardId}/preview`)) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "text/plain" }),
          text: async () => "/MAT/LAW82/301/1\nELASTOMER_REFERENCE\n",
        } as Response;
      }
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <NeutralHyperelasticExport
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        neutralMaterial={neutral}
      />,
    );
    fireEvent.change(screen.getByLabelText("Solver target"), {
      target: { value: "openradioss" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run mapping preflight" }));
    expect(await screen.findByText("approximated")).toBeTruthy();
    const create = screen.getByRole("button", { name: "Create solver card" });
    expect((create as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/I reviewed every approximated/));
    expect((create as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(create);
    expect(await screen.findByText(/openradioss card r1 created/)).toBeTruthy();
    expect(await screen.findByText(/\/MAT\/LAW82\/301\/1/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download native ASCII card" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download mapping report JSON" })).toBeTruthy();
  });
});
