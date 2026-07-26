import { afterEach, describe, expect, it, vi } from "vitest";

import {
  loadDeliveryActivities,
  loadSolverCardEvidence,
  mappingDisposition,
  recordDeliveryActivity,
} from "./solver-card-delivery";

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

  it("projects review identity from the loaded Solver Card revision, not the summary", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue({ ok: true, status: 200, headers: new Headers({ "content-type": "application/json" }), json: async () => ({
      solver_card_id: "card-1", target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" }, solver_material_id: 301,
      current_revision: { id: "loaded-card-r2", content_hash: "c".repeat(64), classification: "restricted", revision_no: 2, lifecycle_state: "draft", content: { card_title: "DP780", card_sha256: "a".repeat(64) }, mapping_report: { exportable: true, mapping_report_sha256: "b".repeat(64), items: [] } },
    }) } as Response);
    vi.stubGlobal("fetch", fetchMock);
    const evidence = await loadSolverCardEvidence({ baseUrl: "/api/v1", accessToken: "token" }, { id: "card-1", revisionId: "stale-summary-r1", kind: "solver_card", label: "DP780", solver: "OpenRadioss", extension: ".rad" });
    expect(evidence).toMatchObject({ reviewRevisionId: "loaded-card-r2", reviewContentHash: "c".repeat(64), reviewClassification: "restricted", reviewAggregateType: "exporting.solver_card" });
    vi.unstubAllGlobals();
  });

  it("uses the Neutral Solver Card lifecycle aggregate for an exact neutral revision", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => url.endsWith("/mapping-report") ? {
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
      reviewRevisionId: "neutral-card-r3",
      reviewContentHash: "d".repeat(64),
      reviewAggregateType: "exporting.neutral_solver_card",
    });
    vi.unstubAllGlobals();
  });
});
