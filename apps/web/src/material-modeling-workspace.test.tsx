import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MaterialClass, MaterialDetail, MaterialResponse } from "./types";
import { clearModelingSession, loadModelingSession } from "./features/modeling";

const mocks = vi.hoisted(() => ({
  getMaterialDetail: vi.fn(),
  listMaterials: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  getMaterialDetail: mocks.getMaterialDetail,
  listMaterials: mocks.listMaterials,
}));

vi.mock("./common-processing-workbench", () => ({
  CommonProcessingWorkbench: ({
    onModelingTrackChange,
    onNewSession,
    familyWorkbench,
    initialSession,
  }: {
    onModelingTrackChange: (track: MaterialClass) => void;
    onNewSession: (track: MaterialClass) => void;
    familyWorkbench: React.ReactNode;
    initialSession?: {
      material?: { revisionId: string };
      materialState?: { revisionId: string };
    } | null;
  }) => (
    <main>
      <button type="button" onClick={() => onNewSession("elastomer")}>New session</button>
      <button type="button" onClick={() => onModelingTrackChange("metal")}>Metal track</button>
      <button type="button" onClick={() => onModelingTrackChange("polymer")}>Polymer track</button>
      <button type="button" onClick={() => onModelingTrackChange("elastomer")}>Elastomer track</button>
      <output data-testid="modeling-session-material">{initialSession?.material?.revisionId ?? "none"}</output>
      <output data-testid="modeling-session-state">{initialSession?.materialState?.revisionId ?? "none"}</output>
      {familyWorkbench}
    </main>
  ),
}));

vi.mock("./reference-elastoplastic-workbench", () => ({
  ReferenceElastoplasticWorkbench: () => <h3>Metal engine loaded</h3>,
}));
vi.mock("./reference-linear-viscoelastic-workbench", () => ({
  ReferenceLinearViscoelasticWorkbench: () => <h3>Polymer engine loaded</h3>,
}));
vi.mock("./reference-ogden-prony-workbench", () => ({
  ReferenceOgdenPronyWorkbench: () => <h3>Elastomer engine loaded</h3>,
}));

import { MaterialModelingWorkspace } from "./material-modeling-workspace";

function material(materialClass: MaterialClass): MaterialResponse {
  return {
    material_id: `${materialClass}-material`,
    current_revision: {
      id: `${materialClass}-material-revision`,
      aggregate_id: `${materialClass}-material`,
      revision_no: 2,
      based_on_revision_id: null,
      schema_id: "urn:cmp:material:1.0.0",
      schema_version: "1.0.0",
      content_hash: "a".repeat(64),
      created_at: "2026-07-19T00:00:00Z",
      created_by: "demo-user",
      change_reason: "demo",
      organization_id: "demo-org",
      project_id: "demo-project",
      classification: "internal",
      lifecycle_state: "draft",
      content: {
        name: `${materialClass} demo`,
        material_code: materialClass.toUpperCase(),
        material_family: materialClass,
        description: null,
        material_class: materialClass,
      },
      provenance: {
        entity_type: "material_revision",
        reference_type: "material_revision",
        revision_id: `${materialClass}-material-revision`,
        content_sha256: "a".repeat(64),
        based_on_revision_id: null,
        recorded_at: "2026-07-19T00:00:00Z",
        recorded_by: "demo-user",
      },
    },
    links: { self: "", revisions: "", states: "" },
  };
}

function detailFor(item: MaterialResponse): MaterialDetail {
  const materialClass = item.current_revision.content.material_class;
  const stateId = `${materialClass}-state`;
  const stateRevisionId = `${materialClass}-state-revision`;
  return {
    material: item,
    states: [{
      material_state_id: stateId,
      material_id: item.material_id,
      current_revision: {
        ...item.current_revision,
        id: stateRevisionId,
        aggregate_id: stateId,
        content: {
          material_id: item.material_id,
          material_revision_id: item.current_revision.id,
          name: `${materialClass} state`,
          manufacturing_route: null,
          heat_treatment: null,
          lot_or_batch: null,
          description: null,
        },
      },
      property_sets_url: "",
    }],
    property_sets: [{
      property_set_id: `${materialClass}-properties`,
      material_state_id: stateId,
      current_revision: {
        ...item.current_revision,
        id: `${materialClass}-property-revision`,
        aggregate_id: `${materialClass}-properties`,
        content: {
          material_state_id: stateId,
          material_state_revision_id: stateRevisionId,
          density_kg_per_m3: 1000,
          density_source: { kind: "manual", reference: null },
          youngs_modulus_pa: 1e9,
          youngs_modulus_source: { kind: "manual", reference: null },
          poisson_ratio: 0.3,
          poisson_ratio_source: { kind: "manual", reference: null },
          yield_stress_pa: 1e6,
          yield_stress_source: { kind: "manual", reference: null },
          applicability: {
            temperature_min_k: null,
            temperature_max_k: null,
            strain_rate_min_per_s: null,
            strain_rate_max_per_s: null,
            note: null,
          },
        },
      },
    }],
  };
}

function materialIdentity(item: MaterialResponse, materialId: string, revisionId: string, name: string): MaterialResponse {
  return {
    ...item,
    material_id: materialId,
    current_revision: {
      ...item.current_revision,
      id: revisionId,
      aggregate_id: materialId,
      content: { ...item.current_revision.content, name },
      provenance: { ...item.current_revision.provenance, revision_id: revisionId },
    },
  };
}

function stateIdentity(
  detail: MaterialDetail,
  stateId: string,
  revisionId: string,
  name: string,
): MaterialDetail["states"][number] {
  const state = detail.states[0];
  return {
    ...state,
    material_state_id: stateId,
    current_revision: {
      ...state.current_revision,
      id: revisionId,
      aggregate_id: stateId,
      content: { ...state.current_revision.content, name },
    },
  };
}

describe("Material Modeling Workspace", () => {
  afterEach(() => {
    cleanup();
    clearModelingSession();
    vi.clearAllMocks();
  });

  it("loads the exact Material context and swaps the real family engine with the selected track", async () => {
    clearModelingSession();
    const materials = new Map<MaterialClass, MaterialResponse>([
      ["metal", material("metal")],
      ["polymer", material("polymer")],
      ["elastomer", material("elastomer")],
    ]);
    mocks.listMaterials.mockImplementation(async (_config, _query, materialClass: MaterialClass) => ({
      data: { items: [materials.get(materialClass)], total_count: 1 },
      etag: null,
    }));
    mocks.getMaterialDetail.mockImplementation(async (_config, materialId: string) => {
      const item = [...materials.values()].find((candidate) => candidate.material_id === materialId);
      if (!item) throw new Error("unknown material");
      return { data: detailFor(item), etag: null };
    });

    const view = render(
      <MaterialModelingWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "demo" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Metal engine loaded" }, { timeout: 3_000 })).toBeTruthy();
    expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("metal-material");

    fireEvent.click(screen.getByRole("button", { name: "Polymer track" }));
    expect(await screen.findByRole("heading", { name: "Polymer engine loaded" }, { timeout: 3_000 })).toBeTruthy();
    expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("polymer-material");

    fireEvent.click(screen.getByRole("button", { name: "Elastomer track" }));
    expect(await screen.findByRole("heading", { name: "Elastomer engine loaded" }, { timeout: 3_000 })).toBeTruthy();
    expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("elastomer-material");

    await waitFor(() => expect(mocks.listMaterials).toHaveBeenCalledTimes(3));
    expect(mocks.listMaterials.mock.calls.map((call) => call[2])).toEqual(["metal", "polymer", "elastomer"]);

    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    await waitFor(() => {
      expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("");
      expect((screen.getByLabelText("Modeling material state") as HTMLSelectElement).value).toBe("");
    });
    expect(screen.queryByRole("heading", { name: /engine loaded/ })).toBeNull();
    expect(loadModelingSession()?.contextSelectionRequired).toBe(true);

    view.unmount();
    render(
      <MaterialModelingWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "demo" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );
    await waitFor(() => {
      expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("");
      expect((screen.getByLabelText("Modeling material state") as HTMLSelectElement).value).toBe("");
    });
  });

  it("prefers exact URL Material and State revisions over the first selectable heads", async () => {
    const base = material("metal");
    const first = materialIdentity(base, "material-first", "material-first-r2", "First current Material");
    const exact = materialIdentity(base, "material-exact", "material-exact-r7", "Exact URL Material");
    const exactDetail = detailFor(exact);
    exactDetail.states = [
      stateIdentity(exactDetail, "state-first", "state-first-r3", "First current State"),
      stateIdentity(exactDetail, "state-exact", "state-exact-r9", "Exact URL State"),
    ];
    mocks.listMaterials.mockResolvedValue({ data: { items: [first, exact], total_count: 2 }, etag: null });
    mocks.getMaterialDetail.mockResolvedValue({ data: exactDetail, etag: null });

    render(
      <MaterialModelingWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "demo" }}
        locationSearch="?family=metal&material_id=material-exact&material_revision_id=material-exact-r7&material_state_id=state-exact&material_state_revision_id=state-exact-r9"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    await waitFor(() => {
      expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("material-exact");
      expect((screen.getByLabelText("Modeling material state") as HTMLSelectElement).value).toBe("state-exact");
      expect(screen.getByTestId("modeling-session-material").textContent).toBe("material-exact-r7");
      expect(screen.getByTestId("modeling-session-state").textContent).toBe("state-exact-r9");
    });
    expect(loadModelingSession()).toMatchObject({
      material: { id: "material-exact", revisionId: "material-exact-r7" },
      materialState: { id: "state-exact", revisionId: "state-exact-r9" },
    });
  });

  it("blocks a stale URL Material revision instead of substituting its current head", async () => {
    const current = materialIdentity(material("metal"), "material-exact", "material-current-r8", "Current Material head");
    mocks.listMaterials.mockResolvedValue({ data: { items: [current], total_count: 1 }, etag: null });

    render(
      <MaterialModelingWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "demo" }}
        locationSearch="?family=metal&material_id=material-exact&material_revision_id=material-stale-r7"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByText(/Material revision is no longer the current selectable head/)).toBeTruthy();
    expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("");
    expect(screen.queryByRole("heading", { name: "Metal engine loaded" })).toBeNull();
    expect(mocks.getMaterialDetail).not.toHaveBeenCalled();
    expect(loadModelingSession()?.material).toBeUndefined();
  });

  it("blocks a stale URL State revision instead of substituting its current head", async () => {
    const exact = materialIdentity(material("metal"), "material-exact", "material-exact-r7", "Exact URL Material");
    const exactDetail = detailFor(exact);
    exactDetail.states = [stateIdentity(exactDetail, "state-exact", "state-current-r10", "Current State head")];
    mocks.listMaterials.mockResolvedValue({ data: { items: [exact], total_count: 1 }, etag: null });
    mocks.getMaterialDetail.mockResolvedValue({ data: exactDetail, etag: null });

    render(
      <MaterialModelingWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "demo" }}
        locationSearch="?family=metal&material_id=material-exact&material_revision_id=material-exact-r7&material_state_id=state-exact&material_state_revision_id=state-stale-r9"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByText(/Material State revision is no longer the current selectable head/)).toBeTruthy();
    expect((screen.getByLabelText("Modeling material") as HTMLSelectElement).value).toBe("material-exact");
    expect((screen.getByLabelText("Modeling material state") as HTMLSelectElement).value).toBe("");
    expect(screen.queryByRole("heading", { name: "Metal engine loaded" })).toBeNull();
    await waitFor(() => expect(screen.getByTestId("modeling-session-material").textContent).toBe("material-exact-r7"));
    expect(loadModelingSession()?.materialState).toBeUndefined();
  });
});
