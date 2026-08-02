import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MappingStatusList, NeutralCardCreationPanel, SolverCardAction } from "./solver-card-delivery-ui";
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
        id: card.revisionId,
        content_hash: "c".repeat(64),
        classification: "internal",
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

    expect((await screen.findByRole("status")).textContent).toContain("Not supported: constitutive law");
    expect(screen.queryByRole("button", { name: /Download/ })).toBeNull();
  });

  it("projects exporter statuses into consequence language for the normal card view", () => {
    render(<MappingStatusList items={[
      { name: "density", ir_path: "density", target_representation: "RHO_I", status: "exact", detail: "Recorded unchanged." },
      { name: "hardening", ir_path: "hardening", target_representation: "*PLASTIC", status: "transformed", detail: "Rendered in native syntax." },
      { name: "post_necking_extension", ir_path: "extension", target_representation: "*PLASTIC", status: "approximated", detail: "Review the delivery note." },
      { name: "optional", ir_path: "optional", target_representation: null, status: "not_applicable", detail: "Not part of this reference." },
      { name: "unsupported_field", ir_path: "unsupported_field", target_representation: null, status: "unsupported", detail: "Not available for this solver." },
    ]}/>);

    expect(screen.getByText("Values unchanged")).toBeTruthy();
    expect(screen.getByText("Converted")).toBeTruthy();
    expect(screen.getByText("Review required")).toBeTruthy();
    expect(screen.getByText("The selected curve continues beyond the measured range.")).toBeTruthy();
    expect(screen.getByText("Context only")).toBeTruthy();
    expect(screen.getByText("Not supported")).toBeTruthy();
    expect(screen.queryByText("Recorded unchanged.")).toBeNull();
    expect(screen.queryByText("Not available for this solver.")).toBeNull();
    expect(screen.queryByText("approximated")).toBeNull();
    expect(screen.queryByText("unsupported")).toBeNull();

    const rows = screen.getByRole("list", { name: "Delivery checks" }).querySelectorAll("li");
    expect(rows[0]?.firstElementChild?.className).toContain("delivery-mapping-copy");
    expect(rows[0]?.lastElementChild?.className).toContain("mapping-status");
    expect(rows[0]?.lastElementChild?.textContent).toBe("Values unchanged");
  });

  it("places one review acknowledgement inside the first review-required row", () => {
    render(<MappingStatusList
      items={[
        { name: "density", ir_path: "density", target_representation: "RHO_I", status: "exact", detail: "Recorded unchanged." },
        { name: "post_necking_extension", ir_path: "extension", target_representation: "*PLASTIC", status: "approximated", detail: "Review the delivery note." },
      ]}
      reviewAcknowledgement={<label><input type="checkbox" />I reviewed the delivery notes.</label>}
    />);

    const checkbox = screen.getByRole("checkbox");
    const row = checkbox.closest("li");
    expect(row).not.toBeNull();
    expect(row?.textContent).toContain("Review required");
    expect(row?.textContent).toContain("I reviewed the delivery notes.");
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
    const acknowledgement = await screen.findByRole("checkbox");
    expect(acknowledgement.closest("li")).not.toBeNull();
    expect(acknowledgement.closest("li")?.textContent).toContain("Review required");
    fireEvent.click(acknowledgement);
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
    expect((await screen.findByRole("alert")).textContent).toContain("not supported by the selected solver");
  });
});
