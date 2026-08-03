import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MaterialDetailPage, SolverCardPreviewPage, type MaterialRevisionPin } from "./material-library";

const materialId = "material-1";
const materialRevision1 = "material-revision-1";
const materialRevision2 = "material-revision-2";
const recordId = "record-1";
const recordRevision1 = "record-revision-1";
const recordRevision2 = "record-revision-2";
const stateRevision1 = "state-revision-1";
const stateRevision2 = "state-revision-2";
const cardId = "card-1";
const cardRevisionId = "card-revision-1";

function metadata(id: string, aggregateId: string, revisionNo: number) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: revisionNo,
    based_on_revision_id: null,
    schema_id: "cmp.fixture",
    schema_version: "1.0.0",
    content_hash: `${id}-hash`,
    created_at: "2026-07-26T00:00:00Z",
    created_by: "test-user",
    change_reason: "fixture",
    organization_id: "org-1",
    project_id: "project-1",
    classification: "internal",
    lifecycle_state: "draft",
  };
}

const materialRevision = (id: string, revisionNo: number, name: string, density: number) => ({
  ...metadata(id, materialId, revisionNo),
  content: { name, material_code: `CODE-${revisionNo}`, material_family: "steel", description: `${name} description`, material_class: "metal" },
  provenance: {
    entity_type: "material.revision",
    reference_type: "fixture",
    revision_id: id,
    content_sha256: `${id}-hash`,
    based_on_revision_id: null,
    recorded_at: "2026-07-26T00:00:00Z",
    recorded_by: "test-user",
  },
  density,
});

const material1 = materialRevision(materialRevision1, 1, "Pinned Material r1", 1000);
const material2 = materialRevision(materialRevision2, 2, "Current Head m2", 2000);

const state = (revisionId: string, materialRevisionId: string, name: string) => ({
  material_state_id: `state-${revisionId}`,
  material_id: materialId,
  current_revision: {
    ...metadata(revisionId, `state-${revisionId}`, revisionId === stateRevision1 ? 1 : 2),
    content: {
      material_id: materialId,
      material_revision_id: materialRevisionId,
      name,
      manufacturing_route: "Synthetic reference preparation; not for engineering use",
      heat_treatment: null,
      lot_or_batch: "LOT-1",
      description: null,
    },
    provenance: {
      entity_type: "material_state.revision",
      reference_type: "fixture",
      revision_id: revisionId,
      content_sha256: `${revisionId}-hash`,
      based_on_revision_id: null,
      recorded_at: "2026-07-26T00:00:00Z",
      recorded_by: "test-user",
    },
  },
  property_sets_url: `/material-states/state-${revisionId}/property-sets`,
});

const propertySet = (revisionId: string, materialStateId: string, stateRevisionId: string, density: number) => ({
  property_set_id: `property-${revisionId}`,
  material_state_id: materialStateId,
  current_revision: {
    ...metadata(revisionId, `property-${revisionId}`, revisionId === "property-r1" ? 1 : 2),
    content: {
      material_state_id: materialStateId,
      material_state_revision_id: stateRevisionId,
      density_kg_per_m3: density,
      density_source: { kind: "manual", reference: `density-${density}` },
      youngs_modulus_pa: density * 1000,
      youngs_modulus_source: { kind: "manual", reference: "fixture" },
      poisson_ratio: 0.3,
      poisson_ratio_source: { kind: "manual", reference: "fixture" },
      yield_stress_pa: 500000000,
      yield_stress_source: { kind: "manual", reference: "fixture" },
      applicability: {
        temperature_min_k: 293,
        temperature_max_k: 293,
        strain_rate_min_per_s: 0,
        strain_rate_max_per_s: 1,
        note: null,
      },
    },
    provenance: {
      entity_type: "property_set.revision",
      reference_type: "fixture",
      revision_id: revisionId,
      content_sha256: `${revisionId}-hash`,
      based_on_revision_id: null,
      recorded_at: "2026-07-26T00:00:00Z",
      recorded_by: "test-user",
    },
  },
});

function recordRevision(id: string, revisionNo: number, name: string, value: string) {
  return {
    ...metadata(id, recordId, revisionNo),
    content: {
      table_revision_id: "table-revision-1",
      name,
      external_key: `REC-${revisionNo}`,
      description: `${name} description`,
      folder_id: null,
      folder_revision_id: null,
      values: [{
        attribute_definition_id: "attribute-1",
        attribute_definition_revision_id: "attribute-revision-1",
        data_type: "text",
        value,
      }],
    },
  };
}

const record1 = recordRevision(recordRevision1, 3, "Pinned Catalog r1", "r1-layout-value");
const record2 = recordRevision(recordRevision2, 4, "Current Catalog r2", "r2-layout-value");

function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

function textResponse(data: string, status = 200): Response {
  return new Response(data, { status, headers: { "Content-Type": "text/plain" } });
}

function exactGraph(mismatch = false, withCard = false) {
  const binding = {
    binding_id: "binding-1",
    record_id: recordId,
    record_revision_id: recordRevision1,
    kind: "material",
    object_id: mismatch ? "material-2" : materialId,
    revision_id: mismatch ? materialRevision2 : materialRevision1,
    workbench_path: `/materials/${materialId}`,
  };
  const root = {
    record_id: recordId,
    record_revision_id: recordRevision1,
    revision_no: 3,
    table_id: "table-1",
    name: "Pinned Catalog r1",
    external_key: "REC-1",
    domain_binding: binding,
  };
  const card = {
    ...root,
    record_id: "card-record-1",
    record_revision_id: "card-record-revision-1",
    name: "Pinned OpenRadioss card",
    domain_binding: {
      binding_id: "card-binding-1",
      record_id: "card-record-1",
      record_revision_id: "card-record-revision-1",
      kind: "neutral_solver_card",
      object_id: cardId,
      revision_id: cardRevisionId,
      workbench_path: "/exports",
    },
  };
  return { root, nodes: withCard ? [root, card] : [root], links: [] };
}

function installFetch(mismatch = false, withCard = false) {
  const cardEndpoint = `/api/v1/neutral-solver-cards/${cardId}`;
  const exactRevision = `?revision_id=${cardRevisionId}`;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith(`/materials/${materialId}/revisions`)) return response({ material_id: materialId, revisions: [material2, material1] });
    if (url.endsWith(`/materials/${materialId}`)) return response({
      material: { material_id: materialId, current_revision: material2, links: { self: "", revisions: "", states: "" } },
      states: [state(stateRevision2, materialRevision2, "Current State r2"), state(stateRevision1, materialRevision1, "Pinned State r1")],
      property_sets: [propertySet("property-r2", `state-${stateRevision2}`, stateRevision2, 2000), propertySet("property-r1", `state-${stateRevision1}`, stateRevision1, 1000)],
    });
    if (url.startsWith("/api/v1/review-requests?")) return response({ items: [] });
    if (url.endsWith(`/catalog/records/${recordId}/revisions`)) return response({ items: [record2, record1] });
    if (url.endsWith(`/catalog/records/${recordId}`)) return response({ record_id: recordId, table_id: "table-1", current_revision: record2 });
    if (url.includes(`/catalog/workflow-explorer/${recordId}/revisions/${recordRevision1}`)) return response(exactGraph(mismatch, withCard));
    if (url.endsWith("/catalog/tables/table-1/attributes")) return response({ items: [{
      attribute_definition_id: "attribute-1",
      table_id: "table-1",
      current_revision: { ...metadata("attribute-revision-1", "attribute-1", 1), content: {
        table_revision_id: "table-revision-1", key: "fixture_value", name: "Fixture value", data_type: "text", required: false,
        quantity_semantics: null, normalized_unit: null, minimum_number: null, maximum_number: null, minimum_length: null,
        maximum_length: null, pattern: null, allowed_values: [], reference_table_id: null, help_text: null,
      } },
    }] });
    if (url.endsWith("/catalog/tables/table-1/layouts")) return response({ items: [{
      layout_id: "layout-1", table_id: "table-1", revision: metadata("layout-revision-1", "layout-1", 1), name: "Pinned Layout", description: null,
      items: [{ attribute_definition_id: "attribute-1", attribute_definition_revision_id: "attribute-revision-1", section: "Mechanical", ordinal: 1 }],
    }] });
    if (url.includes("/bulk-export-candidates?")) throw new Error("Pinned detail must not query bulk candidates");
    if (url === `${cardEndpoint}/preview${exactRevision}`) return textResponse("/MAT/LAW36/1\nPinned card\n");
    if (url === `${cardEndpoint}/mapping-report${exactRevision}`) return response({ exportable: true, report: { exportable: true, items: [] }, mapping_report_sha256: "mapping-hash" });
    if (url === `${cardEndpoint}/download${exactRevision}`) return new Response("/MAT/LAW36/1\nPinned card\n", {
      status: 200,
      headers: { "Content-Type": "text/plain", "Content-Disposition": 'attachment; filename="pinned-card.rad"' },
    });
    if (url === `${cardEndpoint}${exactRevision}`) return response({
      solver_card_id: cardId,
      solver_material_id: 781,
      target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
      current_revision: {
        ...metadata(cardRevisionId, cardId, 1),
        content: { card_title: "Pinned OpenRadioss card", card_sha256: "card-hash", mapping_report: { exportable: true, items: [] }, solver_material_id: 781, material_name: "Pinned Material r1", mapping_statuses: {} },
      },
    });
    if (url.includes(cardEndpoint)) throw new Error(`Pinned graph card request lost exact revision: ${url}`);
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const pin: MaterialRevisionPin = { recordId, recordRevisionId: recordRevision1, materialRevisionId: materialRevision1 };

describe("pinned Material detail", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders exact Material and Catalog revisions, exact Layout values and CSV", async () => {
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(1440);
    installFetch();
    const csvBlobs: Blob[] = [];
    vi.spyOn(URL, "createObjectURL").mockImplementation((value) => {
      csvBlobs.push(value as Blob);
      return "blob:pinned-csv";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const workspaceStatusUpdates: Array<{ revision?: string }> = [];
    const observeWorkspaceStatus = (event: Event) => {
      const detail = (event as CustomEvent<{ revision?: string }>).detail;
      workspaceStatusUpdates.push(detail);
    };
    window.addEventListener("cmp:workspace-status", observeWorkspaceStatus);
    render(<MaterialDetailPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} materialId={materialId} activeTab="properties" exactPin={pin} onNavigate={vi.fn()} />);

    expect(await screen.findByRole("heading", { name: "Pinned Catalog r1", level: 1 })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Request review" })).toBeTruthy();
    await waitFor(() => expect(workspaceStatusUpdates.some(({ revision }) => revision === "r3")).toBe(true));
    const pinnedWorkspaceStatus = workspaceStatusUpdates.find(({ revision }) => revision === "r3");
    expect(pinnedWorkspaceStatus?.revision).toBe("r3");
    expect(pinnedWorkspaceStatus?.revision).not.toMatch(/\bdraft\b/i);
    const detailHeaderText = screen.getByRole("heading", { name: "Pinned Catalog r1", level: 1 }).closest("header")?.textContent ?? "";
    expect(detailHeaderText).not.toMatch(/\bdraft\b/i);
    expect(detailHeaderText).toContain("Request review");
    const relatedContextText = screen.getByLabelText("Related exact records").textContent ?? "";
    expect(relatedContextText).not.toMatch(/\bdraft\b/i);
    expect(relatedContextText).toContain("Revision");
    expect(relatedContextText).toContain("r3");
    expect(relatedContextText).toContain("Related");
    expect(screen.getByText("1,000 kg/m³")).toBeTruthy();
    expect(await screen.findByText("r1-layout-value")).toBeTruthy();
    expect(screen.queryByText("Current Head m2")).toBeNull();
    expect(screen.queryByText("r2-layout-value")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(async () => expect(csvBlobs).toHaveLength(1));
    const csv = await csvBlobs[0].text();
    expect(csv).toContain("r1-layout-value");
    expect(csv).not.toContain("r2-layout-value");
    window.removeEventListener("cmp:workspace-status", observeWorkspaceStatus);
  });

  it("fails closed when the exact workflow binding does not match the pin", async () => {
    installFetch(true);
    render(<MaterialDetailPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} materialId={materialId} activeTab="overview" exactPin={pin} onNavigate={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toContain("does not match");
    expect(screen.queryByText("Current Head m2")).toBeNull();
  });

  it("fails closed for an incomplete exact pin instead of loading the current head", async () => {
    render(<MaterialDetailPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} materialId={materialId} activeTab="overview" exactPin={{ recordId, recordRevisionId: "", materialRevisionId: materialRevision1 }} onNavigate={vi.fn()} />);
    expect((await screen.findByRole("alert")).textContent).toContain("link is incomplete");
  });

  it("keeps a direct unpinned Material deep link on the current head", async () => {
    installFetch();
    render(<MaterialDetailPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} materialId={materialId} activeTab="overview" onNavigate={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Current Head m2", level: 1 })).toBeTruthy();
    expect(screen.queryByText("Pinned Catalog r1")).toBeNull();
  });

  it("uses only the exact graph card in a pinned solver preview", async () => {
    const fetchMock = installFetch(false, true);
    const createObjectUrl = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:pinned-card");
    const revokeObjectUrl = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<SolverCardPreviewPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} materialId={materialId} cardId={cardId} exactPin={pin} onNavigate={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Pinned OpenRadioss card", level: 1 })).toBeTruthy();
    const requests = fetchMock.mock.calls.map(([input]) => String(input));
    const cardEndpoint = `/api/v1/neutral-solver-cards/${cardId}`;
    const exactRevision = `?revision_id=${cardRevisionId}`;
    expect(requests).toContain(`${cardEndpoint}${exactRevision}`);
    expect(requests).toContain(`${cardEndpoint}/preview${exactRevision}`);
    expect(requests).toContain(`${cardEndpoint}/mapping-report${exactRevision}`);
    expect(requests).not.toContain(cardEndpoint);
    expect(requests.some((url) => url.startsWith(cardEndpoint) && !url.includes(exactRevision))).toBe(false);
    expect(requests.some((url) => url.includes("/bulk-export-candidates?"))).toBe(false);
    expect(requests.some((url) => url.includes("material-2"))).toBe(false);
    expect(requests).toContain(`/api/v1/catalog/workflow-explorer/${recordId}/revisions/${recordRevision1}?depth=6`);

    fireEvent.click(await screen.findByRole("button", { name: "Download .rad" }));
    await waitFor(() => expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain(`${cardEndpoint}/download${exactRevision}`));
    fireEvent.click(screen.getByText("Advanced mapping evidence", { exact: true }));
    fireEvent.click(screen.getByRole("button", { name: "Download mapping report" }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => String(input) === `${cardEndpoint}/mapping-report${exactRevision}`).length).toBeGreaterThan(1));
    expect(createObjectUrl).toHaveBeenCalled();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:pinned-card");
    expect(anchorClick).toHaveBeenCalled();
  });
});
