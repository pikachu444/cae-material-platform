import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { ReferenceLinearViscoelasticExport } from "./reference-linear-viscoelastic-export";
import type { LinearViscoelasticModelResponse } from "./types";

const modelId = "c1000000-0000-4000-8000-000000000001";
const revisionId = "c1000000-0000-4000-8000-000000000002";
const cardId = "c1000000-0000-4000-8000-000000000003";

const model = {
  material_model_id: modelId,
  material_state_id: "c1000000-0000-4000-8000-000000000004",
  current_revision: {
    id: revisionId,
    revision_no: 1,
    content: {},
  },
} as LinearViscoelasticModelResponse;

function json(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

function text(body: string): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "text/plain" }),
    text: async () => body,
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("acknowledges mapping before generating and previewing an Abaqus Prony card", async () => {
  const mapping = {
    material_model_id: modelId,
    material_model_revision_id: revisionId,
    model_schema_digest: "a".repeat(64),
    target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
    items: [
      {
        name: "shear_prony_terms",
        ir_path: "/terms",
        target_representation: "*VISCOELASTIC",
        status: "exact",
        detail: "Prony terms map exactly.",
      },
    ],
    exporter_id: "cmp.reference.abaqus-linear-prony",
    exporter_version: "1.0.0",
    exporter_digest: "b".repeat(64),
    mapping_report_sha256: "c".repeat(64),
    exportable: true,
    non_production: true,
  };
  const card = {
    solver_card_id: cardId,
    material_model_id: modelId,
    target: mapping.target,
    solver_material_id: 201,
    material_name: "POLYMER_REFERENCE",
    current_revision: { id: "c1000000-0000-4000-8000-000000000005", content: {} },
    links: {},
  };
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const url = String(input);
    if (url.endsWith(`/linear-viscoelastic-models/${modelId}/mapping-preflight`)) {
      return Promise.resolve(json(mapping));
    }
    if (url.endsWith(`/linear-viscoelastic-models/${modelId}/solver-cards`)) {
      return Promise.resolve(
        json(init?.method === "POST" ? { card, mapping_report: mapping } : { items: [] }, init?.method === "POST" ? 201 : 200),
      );
    }
    if (url.endsWith(`/linear-viscoelastic-solver-cards/${cardId}/preview`)) {
      return Promise.resolve(text("*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC\n"));
    }
    return Promise.resolve(json({ items: [] }));
  });
  vi.stubGlobal("fetch", fetchMock);

  render(
    <ReferenceLinearViscoelasticExport
      config={{ baseUrl: "/api/v1", accessToken: "token" }}
      model={model}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Run Abaqus mapping preflight" }));
  expect(await screen.findByText("shear prony terms")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Generate Abaqus .inp" }));
  expect(await screen.findByText("*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC")).toBeTruthy();
  const create = fetchMock.mock.calls.find(
    ([input, init]) =>
      String(input).endsWith(`/linear-viscoelastic-models/${modelId}/solver-cards`) &&
      init?.method === "POST",
  );
  expect(JSON.parse(String(create?.[1]?.body))).toMatchObject({
    material_model_revision_id: revisionId,
    expected_mapping_report_sha256: "c".repeat(64),
    target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
  });
});
