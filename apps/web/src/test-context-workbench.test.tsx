import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TestContextWorkbench } from "./test-context-workbench";
import type { MaterialStateResponse } from "./types";

function response(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const ids = Array.from({ length: 14 }, (_, index) =>
  `4a000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
);
const [stateId, stateRevisionId, materialId, materialRevisionId, methodId, methodRevisionId, runId, runRevisionId, instrumentId, instrumentRevisionId, calibrationId, calibrationRevisionId] = ids;
const metadata = {
  id: stateRevisionId,
  aggregate_id: stateId,
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-16T00:00:00Z",
  created_by: ids[12],
  change_reason: "fixture",
  organization_id: ids[12],
  project_id: ids[13],
  classification: "internal" as const,
  lifecycle_state: "draft" as const,
};
const state: MaterialStateResponse = {
  material_state_id: stateId,
  material_id: materialId,
  current_revision: {
    ...metadata,
    content: { material_id: materialId, material_revision_id: materialRevisionId, name: "Pilot State", manufacturing_route: null, heat_treatment: null, lot_or_batch: null, description: null },
    provenance: { entity_type: "catalog.revision", reference_type: "catalog.revision", revision_id: stateRevisionId, content_sha256: metadata.content_hash, based_on_revision_id: null, recorded_at: metadata.created_at, recorded_by: metadata.created_by },
  },
  property_sets_url: "",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TestContextWorkbench", () => {
  it("does not offer a stale calibration for an exact historical Test Run", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.endsWith("/test-methods")) return response({ items: [{ test_method_id: methodId, current_revision: { ...metadata, id: methodRevisionId, aggregate_id: methodId, content: { method_code: "reference_uniaxial_tensile", display_name: "Reference uniaxial tensile CSV", reference_only: true } }, links: {} }] });
      if (url.endsWith(`/material-states/${stateId}/test-runs`)) return response({ items: [{ test_run_id: runId, specimen_id: ids[12], test_method_id: methodId, current_revision: { ...metadata, id: runRevisionId, aggregate_id: runId, content: { specimen_id: ids[12], specimen_revision_id: ids[13], test_method_id: methodId, test_method_revision_id: methodRevisionId, run_label: "RUN-OLD", performed_at: "2025-01-15T00:00:00Z", test_temperature_k: 296.15, crosshead_speed_mm_per_min: 2, reference_only: true } }, links: {} }] });
      if (url.endsWith("/test-campaigns")) return response({ items: [] });
      if (url.endsWith("/instruments")) return response({ items: [{ resource_id: instrumentId, current_revision: { ...metadata, id: instrumentRevisionId, aggregate_id: instrumentId, content: { instrument_code: "UTM-01", name: "Tester", serial_number: "SN-1", manufacturer: null, model: null, location: null, description: null } }, links: {} }] });
      if (url.endsWith(`/instruments/${instrumentId}/calibrations`)) return response({ items: [{ resource_id: calibrationId, current_revision: { ...metadata, id: calibrationRevisionId, aggregate_id: calibrationId, content: { instrument_id: instrumentId, instrument_revision_id: instrumentRevisionId, calibration_code: "CAL-STALE", certificate_reference: "CERT", provider: "Lab", calibrated_at: "2026-01-01T00:00:00Z", valid_from: "2026-01-01T00:00:00Z", valid_until: "2027-01-01T00:00:00Z", result: "passed", limitation_note: null } }, links: {} }] });
      if (url.endsWith(`/test-runs/${runId}/context`)) return response(null);
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<TestContextWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} state={state} />);

    await screen.findByText(/No selected Instrument calibration is valid/);
    expect(screen.queryByRole("option", { name: /CAL-STALE/ })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining(`/test-runs/${runId}/context`), expect.anything()));
  });
});
