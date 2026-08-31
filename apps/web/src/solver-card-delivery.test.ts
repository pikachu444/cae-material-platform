import { afterEach, describe, expect, it, vi } from "vitest";

import {
  loadDeliveryActivities,
  loadSolverCardEvidence,
  mappingDisposition,
  recordDeliveryActivity,
} from "./solver-card-delivery";
import {
  loadExactSolverCardSummaries,
  solverCardSummaryFromEndpoint,
} from "./features/materials/api/load-material-experience";

describe("solver-card delivery policy", () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  it("classifies every delivery mapping state without silently downgrading it", () => {
    expect(mappingDisposition([{ status: "exact" }, { status: "transformed" }])).toBe("direct");
    expect(mappingDisposition([{ status: "exact" }, { status: "approximated" }])).toBe("review");
    expect(mappingDisposition([{ status: "ignored" }])).toBe("review");
    expect(mappingDisposition([{ status: "ignored" }, { status: "unsupported" }])).toBe("blocked");
  });

  it("records exact Material and Solver Card revisions without duplicating the same action", () => {
    const activity = {
      action: "preview" as const,
      materialId: "material-1",
      materialRevisionId: "material-r3",
      materialLabel: "DP780",
      cardId: "card-1",
      cardRevisionId: "card-r2",
      cardLabel: "DP780 OpenRadioss card",
      solver: "OpenRadioss" as const,
      extension: ".rad" as const,
    };

    recordDeliveryActivity(activity);
    recordDeliveryActivity(activity);

    expect(loadDeliveryActivities()).toMatchObject([{
      version: 1,
      ...activity,
    }]);
  });

  it("projects every exact solver-card binding from the workflow graph", () => {
    const node = (
      cardId: string,
      revisionId: string,
      name: string,
      kind: "solver_card" | "neutral_solver_card",
    ) => ({
      record_id: `record-${cardId}`,
      record_revision_id: `record-${cardId}-r1`,
      name,
      domain_binding: {
        binding_id: `binding-${cardId}`,
        record_id: `record-${cardId}`,
        record_revision_id: `record-${cardId}-r1`,
        kind,
        object_id: cardId,
        revision_id: revisionId,
        workbench_path: `/materials/material-1/cards/${cardId}`,
      },
    });

    const summaries = [
      node("abaqus-card", "abaqus-card-r3", "DP780 Abaqus card", "solver_card"),
      node(
        "radioss-card",
        "radioss-card-r2",
        "DP780 OpenRadioss card",
        "neutral_solver_card",
      ),
    ].map((item) => solverCardSummaryFromEndpoint(item as never));

    expect(summaries).toEqual([
      {
        id: "abaqus-card",
        revisionId: "abaqus-card-r3",
        kind: "solver_card",
        label: "DP780 Abaqus card",
        solver: "Abaqus",
        extension: ".inp",
      },
      {
        id: "radioss-card",
        revisionId: "radioss-card-r2",
        kind: "neutral_solver_card",
        label: "DP780 OpenRadioss card",
        solver: "OpenRadioss",
        extension: ".rad",
      },
    ]);
  });

  it("hydrates every unique card binding from its exact revision response", async () => {
    const node = (
      cardId: string,
      revisionId: string,
      kind: "solver_card" | "neutral_solver_card",
    ) => ({
      record_id: "record-1",
      record_revision_id: "record-r1",
      name: "Record label is not card metadata",
      domain_binding: {
        binding_id: `binding-${cardId}`,
        record_id: "record-1",
        record_revision_id: "record-r1",
        kind,
        object_id: cardId,
        revision_id: revisionId,
        workbench_path: `/materials/material-1/cards/${cardId}`,
      },
    });
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      const neutral = url.includes("/neutral-solver-cards/");
      const cardId = neutral ? "radioss-card" : "abaqus-card";
      const revisionId = neutral ? "radioss-card-r2" : "abaqus-card-r3";
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          solver_card_id: cardId,
          ...(neutral
            ? { neutral_material_id: "neutral-1" }
            : { material_model_id: "model-1", solver_material_id: 301 }),
          target: {
            solver: neutral ? "openradioss" : "abaqus",
            version: "2025",
            unit_system: "kg_m_s",
          },
          current_revision: {
            id: revisionId,
            content: neutral
              ? { material_name: "Exact OpenRadioss card" }
              : { card_title: "Exact Abaqus card" },
          },
        }),
      } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    const graph = {
      root: node("abaqus-card", "abaqus-card-r3", "solver_card"),
      nodes: [
        node("abaqus-card", "abaqus-card-r3", "solver_card"),
        node("radioss-card", "radioss-card-r2", "neutral_solver_card"),
      ],
      links: [],
    };
    const cards = await loadExactSolverCardSummaries(
      { baseUrl: "/api/v1", accessToken: "token" },
      graph as never,
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls).toEqual(
      expect.arrayContaining([
        expect.stringContaining("/solver-cards/abaqus-card?revision_id=abaqus-card-r3"),
        expect.stringContaining(
          "/neutral-solver-cards/radioss-card?revision_id=radioss-card-r2",
        ),
      ]),
    );
    expect(cards).toEqual([
      {
        id: "abaqus-card",
        revisionId: "abaqus-card-r3",
        kind: "solver_card",
        label: "Exact Abaqus card",
        solver: "Abaqus",
        extension: ".inp",
      },
      {
        id: "radioss-card",
        revisionId: "radioss-card-r2",
        kind: "neutral_solver_card",
        label: "Exact OpenRadioss card",
        solver: "OpenRadioss",
        extension: ".rad",
      },
    ]);
    vi.unstubAllGlobals();
  });

  it("fails closed when one exact card hydration fails", async () => {
    const binding = {
      record_id: "record-1",
      record_revision_id: "record-r1",
      name: "Record",
      domain_binding: {
        binding_id: "binding-1",
        record_id: "record-1",
        record_revision_id: "record-r1",
        kind: "solver_card" as const,
        object_id: "card-1",
        revision_id: "card-r1",
        workbench_path: "/materials/material-1/cards/card-1",
      },
    };
    const neutralBinding = {
      ...binding,
      domain_binding: {
        ...binding.domain_binding,
        binding_id: "binding-2",
        kind: "neutral_solver_card" as const,
        object_id: "neutral-card-1",
        revision_id: "neutral-card-r1",
        workbench_path: "/materials/material-1/cards/neutral-card-1",
      },
    };
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("neutral-solver-cards")) {
        return {
          ok: false,
          status: 404,
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ detail: "card revision unavailable" }),
        } as Response;
      }
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          solver_card_id: "card-1",
          material_model_id: "model-1",
          target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
          current_revision: {
            id: "card-r1",
            content: { card_title: "Exact Abaqus card" },
          },
        }),
      } as Response;
    });
    vi.stubGlobal(
      "fetch",
      fetchMock,
    );

    await expect(
      loadExactSolverCardSummaries(
        { baseUrl: "/api/v1", accessToken: "token" },
        { root: binding, nodes: [neutralBinding], links: [] } as never,
      ),
    ).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.unstubAllGlobals();
  });

  it("projects review identity from the loaded Solver Card revision, not the summary", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue({ ok: true, status: 200, headers: new Headers({ "content-type": "application/json" }), json: async () => ({
      solver_card_id: "card-1", material_model_id: "model-1", target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" }, solver_material_id: 301,
      current_revision: { id: "loaded-card-r2", content_hash: "c".repeat(64), classification: "restricted", revision_no: 2, lifecycle_state: "draft", content: { card_title: "DP780", card_sha256: "a".repeat(64) }, mapping_report: { exportable: true, mapping_report_sha256: "b".repeat(64), items: [] }, provenance: { source_material_model_revision_id: "model-r3" } },
    }) } as Response);
    vi.stubGlobal("fetch", fetchMock);
    const evidence = await loadSolverCardEvidence({ baseUrl: "/api/v1", accessToken: "token" }, { id: "card-1", revisionId: "stale-summary-r1", kind: "solver_card", label: "DP780", solver: "OpenRadioss", extension: ".rad" });
    expect(evidence).toMatchObject({ source: { kind: "material_model", id: "model-1", revisionId: "model-r3" }, reviewRevisionId: "loaded-card-r2", reviewContentHash: "c".repeat(64), reviewClassification: "restricted", reviewAggregateType: "exporting.solver_card" });
    vi.unstubAllGlobals();
  });

  it("uses the Neutral Solver Card lifecycle aggregate for an exact neutral revision", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => url.includes("/mapping-report") ? {
          mapping_report_sha256: "b".repeat(64),
          exportable: true,
          report: { items: [] },
        } : {
          solver_card_id: "neutral-card-1",
          neutral_material_id: "neutral-1",
          target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
          current_revision: {
            id: "neutral-card-r3",
            content_hash: "d".repeat(64),
            classification: "internal",
            revision_no: 3,
            lifecycle_state: "draft",
            content: {
              neutral_material_revision_id: "neutral-r2",
              card_sha256: "a".repeat(64),
              mapping_statuses: {},
              solver_material_id: 301,
              material_name: "DP780",
            },
          },
        },
      } as Response;
    }));

    const evidence = await loadSolverCardEvidence(
      { baseUrl: "/api/v1", accessToken: "token" },
      { id: "neutral-card-1", revisionId: "stale-r1", kind: "neutral_solver_card", label: "DP780", solver: "OpenRadioss", extension: ".rad" },
    );

    expect(evidence).toMatchObject({
      source: { kind: "neutral_material", id: "neutral-1", revisionId: "neutral-r2" },
      reviewRevisionId: "neutral-card-r3",
      reviewContentHash: "d".repeat(64),
      reviewAggregateType: "exporting.neutral_solver_card",
    });
    vi.unstubAllGlobals();
  });
});
