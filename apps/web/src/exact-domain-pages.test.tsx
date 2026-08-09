import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ExactMaterialModelPage,
  ExactNeutralMaterialPage,
  ExactSolverCardPage,
} from "./exact-domain-pages";

const config = { baseUrl: "/api/v1", accessToken: "test-token" };
const modelId = "00000000-0000-4000-8000-000000000101";
const modelRevisionId = "00000000-0000-4000-8000-000000000102";
const neutralId = "00000000-0000-4000-8000-000000000103";
const neutralRevisionId = "00000000-0000-4000-8000-000000000104";
const cardId = "00000000-0000-4000-8000-000000000105";
const cardRevisionId = "00000000-0000-4000-8000-000000000106";
const recordId = "00000000-0000-4000-8000-000000000107";
const recordRevisionId = "00000000-0000-4000-8000-000000000108";

function metadata(id: string, aggregateId: string, revisionNo = 1) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: revisionNo,
    based_on_revision_id: null,
    schema_id: "cmp.fixture",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-08-09T00:00:00Z",
    created_by: "00000000-0000-4000-8000-000000000109",
    change_reason: "fixture",
    organization_id: "00000000-0000-4000-8000-000000000110",
    project_id: "00000000-0000-4000-8000-000000000111",
    classification: "internal",
    lifecycle_state: "approved",
  };
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function graph(kind: "material_model" | "neutral_material" | "neutral_solver_card", objectId: string, revisionId: string) {
  const binding = {
    binding_id: "00000000-0000-4000-8000-000000000112",
    record_id: recordId,
    record_revision_id: recordRevisionId,
    kind,
    object_id: objectId,
    revision_id: revisionId,
    workbench_path: "/models/exact",
  };
  const root = {
    record_id: recordId,
    record_revision_id: recordRevisionId,
    revision_no: 1,
    table_id: "00000000-0000-4000-8000-000000000113",
    name: "Exact fixture record",
    external_key: "EXACT",
    domain_binding: binding,
    domain_bindings: [binding],
  };
  return { root, nodes: [root], links: [] };
}

function installFetch(options: { binding?: boolean; currentRevisionId?: string; neutralDownload?: boolean } = {}) {
  let lastResolvedKind: "material_model" | "neutral_material" | "neutral_solver_card" = "material_model";
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith(`/material-models/${modelId}`)) {
      return jsonResponse({
        material_model_id: modelId,
        material_state_id: "00000000-0000-4000-8000-000000000114",
        current_revision: {
          ...metadata(options.currentRevisionId ?? modelRevisionId, modelId),
          content: {
            material_state_id: "00000000-0000-4000-8000-000000000114",
            material_state_revision_id: "00000000-0000-4000-8000-000000000115",
            density_kg_per_m3: 7800,
            youngs_modulus_pa: 210e9,
            poisson_ratio: 0.3,
          },
          ir: {},
          provenance: {},
        },
      });
    }
    if (url.endsWith(`/neutral-materials/${neutralId}`)) {
      return jsonResponse({
        neutral_material_id: neutralId,
        neutral_material_revision_id: options.currentRevisionId ?? neutralRevisionId,
        revision_no: 1,
        content_hash: "b".repeat(64),
        document_artifact: { artifact_id: "00000000-0000-4000-8000-000000000116", sha256: "c".repeat(64) },
        document: {
          document_type: "cmp.neutral-material",
          schema_version: "1.0.0",
          document_id: neutralId,
          content_sha256: "b".repeat(64),
          sources: { datasets: [] },
          curve_stages: [],
          candidate_selection: { reason: "fixture", warnings: [] },
          material_model_ir: {
            model: { id: modelId, revision_id: modelRevisionId },
            schema_id: "cmp.fixture",
            schema_version: "1.0.0",
            model_family: "hyperelastic",
            constitutive_model: { family: "neo_hookean", parameters: {} },
            maturity: "reference",
            non_production: true,
          },
          applicability: { engineering_strain: { minimum: 0, maximum: 0.2, unit: "1" } },
          validation: { status: "reference checks passed" },
        },
      });
    }
    if (url.includes("/catalog/domain-bindings:resolve")) {
      if (options.binding === false) return jsonResponse(null);
      const kind = url.includes("neutral_solver_card") ? "neutral_solver_card" : url.includes("neutral_material") ? "neutral_material" : url.includes("material_model") ? "material_model" : "material_model";
      lastResolvedKind = kind;
      const objectId = kind === "neutral_solver_card" ? cardId : kind === "neutral_material" ? neutralId : modelId;
      const revisionId = kind === "neutral_solver_card" ? cardRevisionId : kind === "neutral_material" ? neutralRevisionId : modelRevisionId;
      return jsonResponse({ binding_id: "00000000-0000-4000-8000-000000000112", record_id: recordId, record_revision_id: recordRevisionId, kind, object_id: objectId, revision_id: revisionId, workbench_path: "/models/exact" });
    }
    if (url.includes(`/catalog/workflow-explorer/${recordId}/revisions/${recordRevisionId}`)) {
      if (lastResolvedKind === "neutral_solver_card") return jsonResponse(graph("neutral_solver_card", cardId, cardRevisionId));
      if (lastResolvedKind === "neutral_material") return jsonResponse(graph("neutral_material", neutralId, neutralRevisionId));
      return jsonResponse(graph("material_model", modelId, modelRevisionId));
    }
    if (url.startsWith("/api/v1/review-requests?")) return jsonResponse({ items: [] });
    if (url.endsWith(`/neutral-solver-cards/${cardId}?revision_id=${cardRevisionId}`)) {
      return jsonResponse({
        solver_card_id: cardId,
        neutral_material_id: neutralId,
        target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
        current_revision: { ...metadata(cardRevisionId, cardId), content: { card_title: "Exact OpenRadioss card", card_sha256: "d".repeat(64), mapping_report_sha256: "e".repeat(64), mapping_statuses: { density: "exact" }, target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" }, solver_material_id: 1, material_name: "Exact card", neutral_material_id: neutralId, neutral_material_revision_id: neutralRevisionId, neutral_material_sha256: "b".repeat(64), model_schema_digest: "f".repeat(64), family: "neo_hookean", density_kg_per_m3: 7800, constitutive_model: {}, applicability: { engineering_strain: { minimum: 0, maximum: 0.2, unit: "1" } }, exporter: { id: "fixture", version: "1", digest: "0".repeat(64) }, non_production: true } },
      });
    }
    if (url.endsWith(`/neutral-solver-cards/${cardId}/mapping-report?revision_id=${cardRevisionId}`)) return jsonResponse({ exportable: true, report: { items: [] }, mapping_report_sha256: "e".repeat(64) });
    if (url.endsWith(`/neutral-solver-cards/${cardId}/preview?revision_id=${cardRevisionId}`)) return new Response("/MAT/LAW36/1\nEXACT\n", { status: 200 });
    if (url.endsWith(`/neutral-materials/${neutralId}/revisions/${neutralRevisionId}/download`)) {
      expect(init?.method).toBeUndefined();
      return new Response("{}", { status: 200, headers: { "content-disposition": 'attachment; filename="exact-neutral.json"' } });
    }
    if (url.endsWith(`/neutral-materials/${neutralId}/revisions/${neutralRevisionId}/download`)) return new Response("{}", { status: 200 });
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("exact governed domain routes", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("requires the approved exact graph before rendering a Material Model", async () => {
    installFetch();
    render(<ExactMaterialModelPage config={config} materialModelId={modelId} revisionId={modelRevisionId} onNavigate={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Material Model" })).toBeTruthy();
    expect(screen.getByText("Approved exact state input")).toBeTruthy();
    expect(screen.queryByText(modelId)).toBeNull();
  });

  it("fails closed for a missing model binding and a stale model revision", async () => {
    installFetch({ binding: false });
    render(<ExactMaterialModelPage config={config} materialModelId={modelId} revisionId={modelRevisionId} onNavigate={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toContain("not an approved");
    cleanup();
    installFetch({ currentRevisionId: "00000000-0000-4000-8000-000000000117" });
    render(<ExactMaterialModelPage config={config} materialModelId={modelId} revisionId={modelRevisionId} onNavigate={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toContain("no longer");
  });

  it("uses the exact Neutral revision download endpoint only after approval", async () => {
    const fetchMock = installFetch();
    const createObjectUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:neutral");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<ExactNeutralMaterialPage config={config} neutralMaterialId={neutralId} revisionId={neutralRevisionId} onNavigate={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Neutral Material" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Download Neutral JSON" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith(`/neutral-materials/${neutralId}/revisions/${neutralRevisionId}/download`))).toBe(true));
    expect(createObjectUrl).toHaveBeenCalled();
  });

  it("fails closed for a non-approved Neutral revision", async () => {
    installFetch({ binding: false });
    render(<ExactNeutralMaterialPage config={config} neutralMaterialId={neutralId} revisionId={neutralRevisionId} onNavigate={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toContain("not an approved");
  });

  it("requires the exact approved card binding before previewing a card", async () => {
    installFetch();
    render(<ExactSolverCardPage config={config} cardId={cardId} revisionId={cardRevisionId} kind="neutral_solver_card" onNavigate={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Exact card" })).toBeTruthy();
    expect(screen.getByLabelText("Native solver card preview").textContent).toContain("/MAT/LAW36/1");
    expect(screen.queryByText(cardId)).toBeNull();
  });

  it("hides an unapproved direct card URL", async () => {
    installFetch({ binding: false });
    render(<ExactSolverCardPage config={config} cardId={cardId} revisionId={cardRevisionId} kind="neutral_solver_card" onNavigate={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toContain("not an approved");
  });
});
