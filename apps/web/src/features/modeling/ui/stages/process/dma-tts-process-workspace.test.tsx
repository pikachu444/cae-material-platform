import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import { DmaTtsProcessWorkspace } from "./dma-tts-process-workspace";

const config = { baseUrl: "/api/v1", accessToken: "token" };
const testData = {
  test_data_document_id: "document-a",
  current_revision: {
    id: "revision-a",
    revision_no: 1,
    content_hash: "a".repeat(64),
    classification: "internal",
  },
  governed_source: {
    tabular_import: {
      import_profile: { aggregate_id: "profile-a", revision_id: "profile-revision-a" },
    },
  },
} as unknown as CanonicalTestDataDocumentResponse;
const sourceDocument = {
  conditions: [{ quantity_semantics: "frequency.cyclic", normalized_unit: "Hz", normalized_value: 1 }],
  channels: [
    { quantity_semantics: "physics.temperature", normalized_values: [293.15, 303.15, 313.15] },
    { quantity_semantics: "mechanics.modulus.storage", normalized_values: [3e6, 2.4e6, 1.9e6] },
    { quantity_semantics: "mechanics.modulus.loss", normalized_values: [1e5, 3e5, 5e5] },
  ],
};
const recommendation = {
  source_evidence: {},
  reference_temperature_k: 303.15,
  source_ordinal: 1,
  c1: 17.44,
  c2_k: 51.6,
  value_origin: "generic_wlf_at_tg_starting_suggestion",
  material_specific: false,
  requires_confirmation: true,
  rule_id: "polymer.dma_wlf_starting_suggestion",
  rule_version: "1.0.0",
  recommendation_sha256: "d".repeat(64),
};
const created = {
  master_curve_output: {
    output_id: "output-a",
    revision_id: "output-revision-a",
    content_sha256: "e".repeat(64),
    metadata_artifact_id: "metadata-a",
    metadata_sha256: "f".repeat(64),
    result_artifact_id: "result-a",
    result_sha256: "1".repeat(64),
    result_schema_ref: "urn:cmp:dma-master-curve:1",
    result_media_type: "application/vnd.apache.parquet",
  },
};
const readBack = {
  output: created.master_curve_output,
  input_mode: "fixed_frequency_temperature_sweep",
  options: {
    input_mode: "fixed_frequency_temperature_sweep",
    recommendation: null,
    shift_law: {
      kind: "wlf",
      reference_temperature_k: 303.15,
      initial_parameters: [17.44, 51.6],
    },
    application_range: {
      basis: "at_least_two_shifted_calibration_isotherms",
      holdout_included: false,
      reduced_angular_frequency_intervals_rad_per_s: [{ minimum: 1, maximum: 100 }],
      calibration_temperature_interval_k: { minimum: 293.15, maximum: 313.15 },
    },
    assessment: { adequacy: "not_assessed" },
    production_readiness: "non_production",
    warnings: ["Backend warning"],
  },
  isotherms: [],
  test_data: { document_id: "document-a", revision_id: "revision-a", content_sha256: "a".repeat(64) },
  import_profile: { document_id: "profile-a", revision_id: "profile-revision-a", content_sha256: "b".repeat(64) },
};
const fitInput = {
  mode: "dma_frequency_master_curve",
  coordinate_quantity: "frequency.angular.reduced",
  coordinate_unit: "rad/s",
  response_channels: [
    { channel: "dma_storage", quantity: "mechanics.modulus.storage", unit: "Pa" },
    { channel: "dma_loss", quantity: "mechanics.modulus.loss", unit: "Pa" },
  ],
  reference_temperature_k: "303.15",
  rows: [
    { ordinal: 0, coordinate: 0.1, storage_modulus_pa: 3e6, loss_modulus_pa: 1e5, partition: "CALIBRATION", exclusion_reason: null },
    { ordinal: 1, coordinate: 1, storage_modulus_pa: 2.4e6, loss_modulus_pa: 3e5, partition: "CALIBRATION", exclusion_reason: null },
  ],
};

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DMA TTS Process workspace", () => {
  it("prepares a recommendation, saves one shifted response, and reloads its Fit input after exact GET", async () => {
    const requests: Array<{ url: string; body?: Record<string, unknown> }> = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      requests.push({ url, ...(init?.body ? { body: JSON.parse(String(init.body)) as Record<string, unknown> } : {}) });
      if (url.endsWith("/import-profiles")) return response({ items: [{
        import_profile_id: "profile-a",
        current_revision: { id: "profile-revision-a", content_hash: "b".repeat(64) },
      }] });
      if (url.endsWith("/dma-frequency-master-curves/recommendations")) return response(recommendation);
      if (url.endsWith("/dma-frequency-master-curves")) return response(created);
      if (url.includes("/dma-frequency-master-curves/output-a/revisions/")) return response(readBack);
      if (url.includes("/linear-viscoelastic-fit-input")) return response(fitInput);
      throw new Error(`Unexpected request: ${url}`);
    });
    const onSaved = vi.fn().mockResolvedValue(undefined);
    const { container } = render(<DmaTtsProcessWorkspace
      config={config}
      testData={testData}
      sourceDocument={sourceDocument}
      chart={{ width: 1200, height: 420 }}
      ribbonOpen
      onRibbonOpenChange={vi.fn()}
      onSaved={onSaved}
      onContinue={vi.fn()}
    />);

    const prepareButton = await screen.findByRole("button", { name: "Prepare recommendation" });
    expect(container.querySelector(".modeling-workspace-rail")).toBeNull();
    expect(container.querySelector(".modeling-split-workspace-no-navigator")).toBeTruthy();
    expect(screen.queryByRole("separator", { name: "Resize curve and process navigator" })).toBeNull();
    expect(screen.queryByLabelText("C1")).toBeNull();
    expect(requests.some((item) => item.url.endsWith("/dma-frequency-master-curves"))).toBe(false);
    fireEvent.click(prepareButton);
    const createButton = await screen.findByRole("button", { name: "Save TTS result" });
    expect(screen.getByText("Shift method")).toBeTruthy();
    expect(screen.getByText("WLF")).toBeTruthy();
    expect((createButton as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(createButton);

    await screen.findByRole("heading", { name: "TTS result saved" });
    expect(screen.getByText("303.15 K")).toBeTruthy();
    expect(screen.getByText("1–100 rad/s")).toBeTruthy();
    expect(screen.getByText("293.15–313.15 K")).toBeTruthy();
    expect(screen.queryByText(/calibration_temperature_interval_k|reduced_angular_frequency_intervals_rad_per_s|\"minimum\"/)).toBeNull();
    expect(screen.queryByText(/initial_parameters/)).toBeNull();
    expect(onSaved).toHaveBeenCalledWith(created, readBack);
    const createRequest = requests.find((item) => item.url.endsWith("/dma-frequency-master-curves"));
    expect(createRequest?.body).toMatchObject({
      test_data: { document_id: "document-a", revision_id: "revision-a" },
      import_profile: { profile_id: "profile-a", revision_id: "profile-revision-a" },
      input_mode: "fixed_frequency_temperature_sweep",
      row_dispositions: [
        { source_ordinal: 0, partition: "CALIBRATION", exclusion_reason: null },
        { source_ordinal: 1, partition: "CALIBRATION", exclusion_reason: null },
        { source_ordinal: 2, partition: "CALIBRATION", exclusion_reason: null },
      ],
      shift_law: { reference_temperature_k: 303.15, c1: 17.44, c2_k: 51.6 },
      confirmation: { confirmed: true, reason: "Use the recommended shift settings for this test." },
    });
    await waitFor(() => expect(requests.some((item) => item.url.includes("/linear-viscoelastic-fit-input"))).toBe(true));
  });

  it("retries only the Fit handoff after the shifted response was already created", async () => {
    let createCount = 0;
    let readCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/import-profiles")) return response({ items: [{
        import_profile_id: "profile-a",
        current_revision: { id: "profile-revision-a", content_hash: "b".repeat(64) },
      }] });
      if (url.endsWith("/dma-frequency-master-curves/recommendations")) return response(recommendation);
      if (url.endsWith("/dma-frequency-master-curves")) {
        createCount += 1;
        return response(created);
      }
      if (url.includes("/dma-frequency-master-curves/output-a/revisions/")) {
        readCount += 1;
        return response(readBack);
      }
      if (url.includes("/linear-viscoelastic-fit-input")) return response(fitInput);
      throw new Error(`Unexpected request: ${url}`);
    });
    const onSaved = vi.fn()
      .mockRejectedValueOnce(new Error("Fit handoff failed."))
      .mockResolvedValueOnce(undefined);
    render(<DmaTtsProcessWorkspace
      config={config}
      testData={testData}
      sourceDocument={sourceDocument}
      chart={{ width: 1200, height: 420 }}
      ribbonOpen
      onRibbonOpenChange={vi.fn()}
      onSaved={onSaved}
      onContinue={vi.fn()}
    />);

    fireEvent.click(await screen.findByRole("button", { name: "Prepare recommendation" }));
    fireEvent.click(await screen.findByRole("button", { name: "Save TTS result" }));
    await screen.findByText("Fit handoff failed.");
    fireEvent.click(screen.getByRole("button", { name: "Retry exact read" }));

    await screen.findByRole("heading", { name: "TTS result saved" });
    expect(createCount).toBe(1);
    expect(readCount).toBe(2);
    expect(onSaved).toHaveBeenCalledTimes(2);
  });

  it("keeps a rejected client draft editable and allows one explicit corrected save", async () => {
    let createCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/import-profiles")) return response({ items: [{
        import_profile_id: "profile-a",
        current_revision: { id: "profile-revision-a", content_hash: "b".repeat(64) },
      }] });
      if (url.endsWith("/dma-frequency-master-curves/recommendations")) return response(recommendation);
      if (url.endsWith("/dma-frequency-master-curves")) {
        createCount += 1;
        if (createCount === 1) return response({ detail: "Correct the governed draft." }, 422);
        return response(created);
      }
      if (url.includes("/dma-frequency-master-curves/output-a/revisions/")) return response(readBack);
      if (url.includes("/linear-viscoelastic-fit-input")) return response(fitInput);
      throw new Error(`Unexpected request: ${url}`);
    });
    render(<DmaTtsProcessWorkspace
      config={config}
      testData={testData}
      sourceDocument={sourceDocument}
      chart={{ width: 1200, height: 420 }}
      ribbonOpen
      onRibbonOpenChange={vi.fn()}
      onSaved={vi.fn().mockResolvedValue(undefined)}
      onContinue={vi.fn()}
    />);

    fireEvent.click(await screen.findByRole("button", { name: "Prepare recommendation" }));
    fireEvent.click(await screen.findByRole("button", { name: "Save TTS result" }));
    await screen.findByText("Correct the governed draft.");
    fireEvent.click(screen.getByRole("button", { name: "TTS settings" }));
    const c1 = document.querySelector('input[name="dma-tts-c1"]') as HTMLInputElement;
    expect(c1).toBeTruthy();
    expect(c1.disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Save TTS result" }));

    await screen.findByRole("heading", { name: "TTS result saved" });
    expect(createCount).toBe(2);
  });

  it("does not repeat an outcome-unknown create request", async () => {
    let createCount = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/import-profiles")) return response({ items: [{
        import_profile_id: "profile-a",
        current_revision: { id: "profile-revision-a", content_hash: "b".repeat(64) },
      }] });
      if (url.endsWith("/dma-frequency-master-curves/recommendations")) return response(recommendation);
      if (url.endsWith("/dma-frequency-master-curves")) {
        createCount += 1;
        return response({ detail: "Service unavailable." }, 503);
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    render(<DmaTtsProcessWorkspace
      config={config}
      testData={testData}
      sourceDocument={sourceDocument}
      chart={{ width: 1200, height: 420 }}
      ribbonOpen
      onRibbonOpenChange={vi.fn()}
      onSaved={vi.fn()}
      onContinue={vi.fn()}
    />);

    fireEvent.click(await screen.findByRole("button", { name: "Prepare recommendation" }));
    fireEvent.click(await screen.findByRole("button", { name: "Save TTS result" }));
    await screen.findByText("Save outcome unknown", { exact: true });
    expect((screen.getByRole("button", { name: "Save TTS result" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(createCount).toBe(1);
  });
});
