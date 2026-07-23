import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NeutralCardCreationPanel, SolverCardAction } from "./solver-card-delivery-ui";
import type { SolverCardSummary } from "./solver-card-delivery";

const config = { baseUrl: "http://cmp.test/api/v1", accessToken: "token" };
const material = {
  materialId: "material-1",
  materialRevisionId: "material-r1",
  materialLabel: "DP780",
};
const card: SolverCardSummary = {
  id: "card-1",
  revisionId: "card-r1",
  kind: "solver_card",
  label: "DP780 OpenRadioss card",
  solver: "OpenRadioss",
  extension: ".rad",
};

function responseFor(status: "exact" | "approximated" | "unsupported", exportable = true): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => ({
      solver_card_id: card.id,
      target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
      solver_material_id: 301,
      current_revision: {
        revision_no: 1,
        lifecycle_state: "draft",
        content: { card_title: "DP780", card_sha256: "a".repeat(64) },
        mapping_report: {
          exportable,
          mapping_report_sha256: "b".repeat(64),
          items: [{
            name: status === "unsupported" ? "constitutive_law" : "density",
            ir_path: "material.density",
            target_representation: "RHO_I",
            status,
            detail: `${status} mapping`,
          }],
        },
      },
    }),
  } as Response;
}

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

describe("contextual solver-card action", () => {
  afterEach(() => {
    cleanup();
    window.sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("offers direct download for an exact mapping without confirmation", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(responseFor("exact")));

    render(<SolverCardAction config={config} card={card} material={material} onNavigate={vi.fn()}/>);

    expect(await screen.findByRole("button", { name: "Download .rad" })).toBeTruthy();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("routes an approximated mapping to preview", async () => {
    const navigate = vi.fn();
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(responseFor("approximated")));

    render(<SolverCardAction config={config} card={card} material={material} onNavigate={navigate}/>);

    fireEvent.click(await screen.findByRole("button", { name: "Preview card" }));
    expect(navigate).toHaveBeenCalledWith("/materials/material-1/cards/card-1");
  });

  it("names the unsupported field and exposes no misleading download", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(responseFor("unsupported", false)));

    render(<SolverCardAction config={config} card={card} material={material} onNavigate={vi.fn()}/>);

    expect((await screen.findByRole("status")).textContent).toContain("Blocked: constitutive law");
    expect(screen.queryByRole("button", { name: /Download/ })).toBeNull();
  });

  it("creates from the exact Neutral revision only after adjacent approximation acknowledgement", async () => {
    const onCreated = vi.fn();
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/solver-card-preflight")) {
        return jsonResponse({
          mapping_report_sha256: "b".repeat(64),
          exportable: true,
          report: {
            items: [{
              name: "plasticity",
              ir_path: "constitutive_model",
              target_representation: "LAW36",
              status: "approximated",
              detail: "Target law requires an approximation.",
            }],
          },
        });
      }
      if (url.endsWith("/solver-cards")) {
        const body = JSON.parse(String(init?.body));
        expect(body.neutral_material_revision_id).toBe("neutral-r4");
        expect(body.expected_mapping_report_sha256).toBe("b".repeat(64));
        return jsonResponse({
          solver_card_id: "created-card",
          current_revision: { id: "created-card-r1" },
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<NeutralCardCreationPanel config={config} neutralMaterialId="neutral-1" neutralMaterialRevisionId="neutral-r4" materialName="DP780" materialCode="DP780" existingCards={[]} onCreated={onCreated}/>);

    const create = await screen.findByRole("button", { name: "Create card" });
    expect((create as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(await screen.findByRole("checkbox"));
    expect((create as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(create);

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({
      id: "created-card",
      revisionId: "created-card-r1",
      kind: "neutral_solver_card",
    })));
  });

  it("keeps generation disabled when preflight reports an unsupported field", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      mapping_report_sha256: "b".repeat(64),
      exportable: false,
      report: {
        items: [{
          name: "constitutive_law",
          ir_path: "constitutive_model",
          target_representation: null,
          status: "unsupported",
          detail: "The selected target cannot represent this law.",
        }],
      },
    })));

    render(<NeutralCardCreationPanel config={config} neutralMaterialId="neutral-1" neutralMaterialRevisionId="neutral-r4" materialName="DP780" materialCode="DP780" existingCards={[]} onCreated={vi.fn()}/>);

    expect((await screen.findByRole("button", { name: "Create card" }) as HTMLButtonElement).disabled).toBe(true);
    expect((await screen.findByRole("alert")).textContent).toContain("blocked by the unsupported fields");
  });
});
