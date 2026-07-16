import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GovernedImportWorkbench } from "./governed-import-workbench";
import type { MaterialStateResponse } from "./types";

const ids = Array.from({ length: 8 }, (_, index) =>
  `5b000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
);
const metadata = {
  id: ids[1], aggregate_id: ids[0], revision_no: 1, based_on_revision_id: null,
  schema_id: "urn:cmp:test:1.0.0", schema_version: "1.0.0", content_hash: "a".repeat(64),
  created_at: "2026-07-16T00:00:00Z", created_by: ids[6], change_reason: "fixture",
  organization_id: ids[6], project_id: ids[7], classification: "internal" as const,
  lifecycle_state: "draft" as const,
};
const state: MaterialStateResponse = {
  material_state_id: ids[0], material_id: ids[2],
  current_revision: {
    ...metadata,
    content: { material_id: ids[2], material_revision_id: ids[3], name: "Pilot State", manufacturing_route: null, heat_treatment: null, lot_or_batch: null, description: null },
    provenance: { entity_type: "catalog.revision", reference_type: "catalog.revision", revision_id: ids[1], content_sha256: metadata.content_hash, based_on_revision_id: null, recorded_at: metadata.created_at, recorded_by: metadata.created_by },
  },
  property_sets_url: "",
};

function response(body: unknown): Response {
  return { ok: true, status: 200, headers: new Headers({ "content-type": "application/json" }), json: async () => body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("GovernedImportWorkbench", () => {
  it("shows the explicit preview, approval, and exact execution sequence", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.endsWith(`/material-states/${ids[0]}/test-runs`)) {
        return response({ items: [{ test_run_id: ids[4], specimen_id: ids[5], test_method_id: ids[3], current_revision: { ...metadata, id: ids[5], aggregate_id: ids[4], content: { specimen_id: ids[5], specimen_revision_id: ids[5], test_method_id: ids[3], test_method_revision_id: ids[3], run_label: "TENSION-01", performed_at: "2026-07-16T00:00:00Z", test_temperature_k: 296.15, crosshead_speed_mm_per_min: 2, reference_only: true } }, links: {} }] });
      }
      if (url.endsWith("/import-profiles")) return response({ items: [] });
      throw new Error(`unexpected request ${url}`);
    }));

    render(<GovernedImportWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} state={state} />);

    expect(await screen.findByRole("heading", { name: "Governed CSV / TSV / XLSX import" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "1. Upload and preview" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "2. Approve reusable Profile" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "3. Execute exact revision" })).toBeTruthy();
    expect(await screen.findByRole("option", { name: /TENSION-01 · r1/ })).toBeTruthy();
    expect(screen.queryByText(/Formula cells, macros, external links/)).toBeNull();
  });
});
