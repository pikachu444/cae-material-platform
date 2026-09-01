import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import { buildPolymerCalibrationSourceSummary } from "../../../model/linear-viscoelastic-calibration-draft";
import { PolymerLinearViscoelasticFit } from "./polymer-linear-viscoelastic-fit";

const config = { baseUrl: "/api/v1", accessToken: "token" };
const catalogContext = {
  material: { id: "37700000-0000-4000-8000-000000000101", revisionId: "37700000-0000-4000-8000-000000000102" },
  materialState: { id: "37700000-0000-4000-8000-000000000103", revisionId: "37700000-0000-4000-8000-000000000104" },
  propertySet: { id: "37700000-0000-4000-8000-000000000105", revisionId: "37700000-0000-4000-8000-000000000106" },
};
const testDataRef = { id: "37700000-0000-4000-8000-000000000011", revisionId: "37700000-0000-4000-8000-000000000012", label: "Polymer relaxation", revisionNo: 1 };
const testDataShape = {
  test_data_document_id: testDataRef.id,
  current_revision: { id: testDataRef.revisionId, revision_no: 1 },
  document_key: "POLYMER-RELAXATION-01",
  channels: [
    { name: "Elapsed time", normalized_unit: "s" },
    { name: "Shear relaxation modulus", normalized_unit: "Pa" },
  ],
};
const testData = testDataShape as unknown as CanonicalTestDataDocumentResponse;
const sourceDocument = {
  channels: [
    { key: "time", quantity_semantics: "time.elapsed", normalized_unit: "s", normalized_values: [0, 1, 2] },
    { key: "modulus", quantity_semantics: "modulus.shear.relaxation", normalized_unit: "Pa", normalized_values: [3_000_000, 2_000_000, 1_000_000] },
  ],
  conditions: [{ quantity_semantics: "physics.temperature", normalized_unit: "K", normalized_value: 298.15 }],
};
const denseRelaxationSourceDocument = {
  channels: [
    { key: "time", quantity_semantics: "time.elapsed", normalized_unit: "s", normalized_values: Array.from({ length: 25 }, (_, index) => 10 ** (-3 + index / 4)) },
    { key: "modulus", quantity_semantics: "modulus.shear.relaxation", normalized_unit: "Pa", normalized_values: Array.from({ length: 25 }, (_, index) => 3_000_000 - (index * 60_000)) },
  ],
  conditions: [{ quantity_semantics: "physics.temperature", normalized_unit: "K", normalized_value: 298.15 }],
};
const dmaTestData = {
  ...testDataShape,
  document_key: "POLYMER-DMA-01",
  channels: [
    { name: "Temperature", normalized_unit: "K" },
    { name: "Frequency", normalized_unit: "Hz" },
    { name: "Storage modulus", normalized_unit: "Pa" },
    { name: "Loss modulus", normalized_unit: "Pa" },
  ],
} as unknown as CanonicalTestDataDocumentResponse;
const dmaSourceDocument = {
  channels: [
    { key: "temperature", quantity_semantics: "physics.temperature", normalized_unit: "K", normalized_values: [293.15, 293.15, 293.15, 303.15] },
    { key: "frequency", quantity_semantics: "frequency.cyclic", normalized_unit: "Hz", normalized_values: [0.1, 1, 10, 1] },
    { key: "storage", quantity_semantics: "modulus.shear.storage", normalized_unit: "Pa", normalized_values: [1_000_000, 1_100_000, 1_200_000, 1_300_000] },
    { key: "loss", quantity_semantics: "modulus.shear.loss", normalized_unit: "Pa", normalized_values: [100_000, 110_000, 120_000, 130_000] },
  ],
};
const dmaTemperatureSweepSourceDocument = {
  channels: [
    { key: "temperature", quantity_semantics: "physics.temperature", normalized_unit: "K", normalized_values: [293.15, 303.15, 313.15] },
    { key: "storage", quantity_semantics: "mechanics.modulus.storage", normalized_unit: "Pa", normalized_values: [1_300_000, 1_100_000, 900_000] },
    { key: "loss", quantity_semantics: "mechanics.modulus.loss", normalized_unit: "Pa", normalized_values: [120_000, 180_000, 210_000] },
  ],
  conditions: [{ quantity_semantics: "frequency.cyclic", normalized_unit: "Hz", normalized_value: 1 }],
};
const processingOutput = {
  processing_output_id: "37700000-0000-4000-8000-000000000091",
  current_revision: { id: "37700000-0000-4000-8000-000000000092", revision_no: 1 },
  label: "Shifted DMA response 01",
  steps: [{ method_id: "polymer.dma_frequency_master_curve" }],
  final_point_count: 18,
} as never;

function jsonResponse(body: unknown, status = 200): Response {
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

describe("polymer linear-viscoelastic Fit", () => {
  it("offers one direct return to Data when the exact source is missing", async () => {
    const openData = vi.fn();
    render(<PolymerLinearViscoelasticFit config={config} onOpenData={openData} />);

    expect(screen.queryByRole("button", { name: "Calculation settings" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Calculate Prony models" })).toBeNull();
    expect(screen.queryByText(/governed Plan|compatible response data/i)).toBeNull();
    expect(openData).not.toHaveBeenCalled();
    expect(screen.getByRole("region", { name: "Fit input required" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Choose Test Data" }));
    expect(openData).toHaveBeenCalledOnce();
  });

  it("uses a human Test Data name instead of the system document key", () => {
    render(<PolymerLinearViscoelasticFit config={config} testData={testData} testDataRef={testDataRef} sourceDocument={sourceDocument} />);

    expect(screen.queryByText(testDataShape.document_key)).toBeNull();
    expect(screen.getAllByText("Polymer relaxation").length).toBeGreaterThanOrEqual(1);
  });

  it("keeps an isothermal DMA frequency sweep available as a direct Fit input", () => {
    render(
      <PolymerLinearViscoelasticFit
        config={config}
        testData={dmaTestData}
        testDataRef={testDataRef}
        sourceDocument={dmaSourceDocument}
      />,
    );

    expect(screen.getByRole("heading", { name: "DMA response" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Calculation settings" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Go to Process" })).toBeNull();
  });

  it("routes a fixed-frequency DMA temperature sweep to TTS Process", () => {
    const openProcess = vi.fn();
    render(
      <PolymerLinearViscoelasticFit
        config={config}
        testData={dmaTestData}
        testDataRef={testDataRef}
        sourceDocument={dmaTemperatureSweepSourceDocument}
        onOpenProcess={openProcess}
      />,
    );

    expect(screen.getByRole("region", { name: "Fit input required" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Calculation settings" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Go to Process" }));
    expect(openProcess).toHaveBeenCalledOnce();
  });

  it("keeps the required recorded-condition inputs available for a saved DMA / TTS result", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      mode: "dma_frequency_master_curve",
      coordinate_quantity: "frequency.angular.reduced",
      coordinate_unit: "rad/s",
      response_channels: [
        { channel: "dma_storage", quantity: "mechanics.modulus.storage", unit: "Pa" },
        { channel: "dma_loss", quantity: "mechanics.modulus.loss", unit: "Pa" },
      ],
      reference_temperature_k: "313.15",
      rows: [
        { ordinal: 0, coordinate: 0.1, storage_modulus_pa: 3_000_000, loss_modulus_pa: 100_000, partition: "CALIBRATION", exclusion_reason: null },
        { ordinal: 1, coordinate: 1, storage_modulus_pa: 2_800_000, loss_modulus_pa: 300_000, partition: "CALIBRATION", exclusion_reason: null },
        { ordinal: 2, coordinate: 10, storage_modulus_pa: 2_400_000, loss_modulus_pa: 500_000, partition: "HOLDOUT", exclusion_reason: null },
      ],
    }));
    render(
      <PolymerLinearViscoelasticFit
        config={config}
        testData={testData}
        testDataRef={testDataRef}
        sourceDocument={sourceDocument}
        processingOutput={processingOutput}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Calculation settings" }));
    await waitFor(() => expect((screen.getByRole("tab", { name: "DMA / TTS result" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("tab", { name: "DMA / TTS result" }));

    expect(screen.getAllByText("Shifted DMA response 01").length).toBeGreaterThanOrEqual(1);
    for (const label of ["Loading ramp", "Frequency sweep", "Preconditioning", "Linear viscoelastic range"]) {
      expect(screen.getByLabelText(label)).toBeTruthy();
    }
    expect(screen.getByRole("table", { name: "Saved shifted DMA values used to calculate the model" })).toBeTruthy();
    expect(screen.getAllByText("313.15 K").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole("table", { name: /Observed points/ })).toBeNull();
  });

  it("keeps 3-, 5-, and 10-term models editable through each final parameter when the data supports them", () => {
    render(<PolymerLinearViscoelasticFit config={config} testData={testData} testDataRef={testDataRef} sourceDocument={denseRelaxationSourceDocument} />);

    fireEvent.click(screen.getByRole("button", { name: "Calculation settings" }));
    for (const label of ["Loading ramp", "Frequency sweep", "Preconditioning", "Linear viscoelastic range"]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value: "NOT_PROVIDED" } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Use all to calculate" }));
    fireEvent.click(screen.getByLabelText("Manual"));

    for (const [term, parameterCount] of [[3, 7], [5, 11], [10, 21]] as const) {
      const termChoice = screen.getByLabelText(`${term}-term Prony, ${parameterCount} parameters`) as HTMLInputElement;
      expect(termChoice.disabled).toBe(false);
      fireEvent.click(termChoice);
      fireEvent.change(screen.getByLabelText("Model"), { target: { value: String(term) } });
      const lastParameterInput = screen.getByLabelText(`${term}-term Relaxation time τ${term} upper`) as HTMLInputElement;
      fireEvent.change(lastParameterInput, { target: { value: String(1000 + term) } });
      expect(lastParameterInput.value).toBe(String(1000 + term));
      expect(lastParameterInput.closest("table")?.querySelectorAll("tbody tr")).toHaveLength(parameterCount);
      expect(lastParameterInput.type).toBe("text");
      expect(lastParameterInput.inputMode).toBe("decimal");
    }
    expect(screen.queryByText("25 values used · can evaluate up to 10 terms")).toBeNull();
    expect(screen.queryByText("21 parameters")).toBeNull();
    const parameterTable = screen.getByLabelText("10-term Relaxation time τ10 upper").closest("table")!;
    expect(Array.from(parameterTable.querySelectorAll("thead th"), (header) => header.textContent)).toEqual([
      "Parameter",
      "Initial value",
      "Minimum",
      "Maximum",
      "Unit",
    ]);
    expect((screen.getByLabelText("3-term Prony, 7 parameters") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("5-term Prony, 11 parameters") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("10-term Prony, 21 parameters") as HTMLInputElement).checked).toBe(true);
    expect(screen.getByRole("region", { name: "Parameter ranges" }).tabIndex).toBe(0);
  });

  it("keeps an invalidated Selection as history and starts the current input cleanly", () => {
    const currentTestDataRef = {
      ...testDataRef,
      revisionId: "37700000-0000-4000-8000-000000000083",
      revisionNo: 2,
    };
    const staleSelection = {
      id: "37700000-0000-4000-8000-000000000081",
      revisionId: "37700000-0000-4000-8000-000000000082",
      label: "Earlier polymer Selection",
      revisionNo: 1,
    };
    const staleTestData = {
      id: testDataRef.id,
      revisionId: "37700000-0000-4000-8000-000000000080",
      label: "Earlier relaxation",
      revisionNo: 1,
    };
    const restoreSavedInput = vi.fn();
    render(
      <PolymerLinearViscoelasticFit
        config={config}
        testData={testData}
        testDataRef={currentTestDataRef}
        sourceDocument={sourceDocument}
        staleTestData={staleTestData}
        staleTestDataDisplayLabel="Earlier relaxation"
        staleSelection={staleSelection}
        onRestoreSavedInput={restoreSavedInput}
      />,
    );

    const staleMessage = document.querySelector<HTMLElement>(".polymer-stale-message")!;
    expect(staleMessage.textContent).toContain("Saved result inputEarlier relaxation · version 1");
    expect(staleMessage.textContent).toContain("Current inputPolymer relaxation · version 2");
    expect(staleMessage.querySelector("details")).toBeNull();
    expect(staleMessage.textContent).not.toContain("Revision");
    fireEvent.click(screen.getByRole("button", { name: "Restore saved input" }));
    expect(restoreSavedInput).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Use current input" }));

    expect(document.querySelector(".polymer-stale-message")).toBeNull();
    expect(screen.getByRole("region", { name: "Calculate Prony models" })).toBeTruthy();
  });

  it("calculates with the only exact approved setup without creating another Plan", async () => {
    const planId = "37700000-0000-4000-8000-000000000021";
    const planRevisionId = "37700000-0000-4000-8000-000000000022";
    const runId = "37700000-0000-4000-8000-000000000031";
    const exact = {
      plan_id: planId,
      plan_revision_id: planRevisionId,
      plan_sha256: "a".repeat(64),
      setup_name: "Approved relaxation setup",
      input_mode: "relaxation",
      material: { id: catalogContext.material.id, revision_id: catalogContext.material.revisionId },
      material_state: { id: catalogContext.materialState.id, revision_id: catalogContext.materialState.revisionId },
      test_data: { id: testDataRef.id, revision_id: testDataRef.revisionId },
      processing_output: null,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/linear-viscoelastic-calibration-plans/resolve")) {
        return jsonResponse({
          summary: "1 setup",
          selection_required: false,
          matches: [{
            ...exact,
            approval: {
              ...exact,
              state: "active",
              review_request_id: "37700000-0000-4000-8000-000000000041",
              review_decision_id: "37700000-0000-4000-8000-000000000042",
              evidence_sha256: "b".repeat(64),
              approved_at: "2026-09-01T00:00:00Z",
              approved_by: "37700000-0000-4000-8000-000000000043",
              superseded_by_plan_id: null,
              superseded_by_plan_revision_id: null,
            },
          }],
        });
      }
      if (url.endsWith(`/linear-viscoelastic-calibration-plans/${planId}`)) {
        return jsonResponse({
          plan_id: planId,
          current_revision: {
            id: planRevisionId,
            content_hash: "a".repeat(64),
            change_reason: "Approved reference setup.",
            content: {
              setup_name: exact.setup_name,
              test_data: exact.test_data,
              input_semantics: {
                mode: "relaxation",
                source_kind: "test_data",
                selected_temperature_k: "298.15",
                point_dispositions: [0, 1, 2].map((ordinal) => ({ ordinal, partition: "CALIBRATION", exclusion_reason: null })),
              },
              term_counts: [1],
              parameter_bounds: {},
              weights: {},
              optimizer: {},
              statuses: {},
            },
          },
          links: {},
        });
      }
      if (url.endsWith(`/linear-viscoelastic-calibration-plans/${planId}/runs`)) {
        return jsonResponse({
          run_id: runId,
          job_id: "37700000-0000-4000-8000-000000000032",
          run_url: `/api/v1/linear-viscoelastic-calibration-runs/${runId}`,
          job_url: "/api/v1/jobs/37700000-0000-4000-8000-000000000032",
          status: "queued",
        }, 202);
      }
      if (url.endsWith(`/linear-viscoelastic-calibration-runs/${runId}`)) {
        return jsonResponse({
          run_id: runId,
          plan_revision_id: planRevisionId,
          status: "failed",
          attempts: [],
          candidates: [],
          recommendation: null,
          failure_code: "SYNTHETIC_STOP",
          failure_detail: "Stop after proving the approved run request.",
          recovery_hint: "No recovery required in this contract test.",
          execution_ledger_sha256: "c".repeat(64),
        });
      }
      throw new Error(`Unexpected request ${url}`);
    });

    render(<PolymerLinearViscoelasticFit
      config={config}
      testData={testData}
      testDataRef={testDataRef}
      sourceDisplayLabel="Polymer relaxation"
      sourceDocument={sourceDocument}
      catalogContext={catalogContext}
    />);

    const calculate = await screen.findByRole("button", { name: "Calculate Prony models" }) as HTMLButtonElement;
    expect(screen.queryByText("Approved relaxation setup")).toBeNull();
    const inputReview = screen.getByRole("region", { name: "Calculate Prony models" });
    fireEvent.click(within(inputReview).getByText("Input details"));
    await waitFor(() => expect(within(inputReview).getByText("Used to fit").nextElementSibling?.textContent).toBe("3 points"));
    expect(inputReview.textContent).not.toContain("Revision");
    fireEvent.click(calculate);
    await waitFor(() => expect(fetchMock.mock.calls.some(([calledUrl]) => String(calledUrl).endsWith(`/${planId}/runs`))).toBe(true));
    expect(fetchMock.mock.calls.filter(([calledUrl]) => String(calledUrl) === "/api/v1/linear-viscoelastic-calibration-plans")).toHaveLength(0);
  });

  it("requires explicit policy inputs and posts exact Test Data identity", async () => {
    expect(buildPolymerCalibrationSourceSummary(sourceDocument)).toEqual({ mode: "relaxation", pointCount: 3, temperatures: [] });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/linear-viscoelastic-calibration-plans/resolve")) {
        return jsonResponse({ summary: "0 approved setups", selection_required: true, matches: [] });
      }
      if (url.endsWith("/linear-viscoelastic-calibration-plans")) {
        return jsonResponse({
          plan_id: "37700000-0000-4000-8000-000000000021",
          current_revision: {
            id: "37700000-0000-4000-8000-000000000022",
            content_hash: "a".repeat(64),
            classification: "internal",
            change_reason: "Calibrate the exact relaxation revision for review.",
            content: {
              setup_name: "Reference relaxation setup",
              test_data: { id: testDataRef.id, revision_id: testDataRef.revisionId },
              input_semantics: { source_kind: "test_data" },
            },
          },
          links: {},
        });
      }
      if (url.includes("/review-requests?")) return jsonResponse({ items: [] });
      if (url.endsWith("/review-requests")) {
        return jsonResponse({
          review_request_id: "37700000-0000-4000-8000-000000000031",
          aggregate_type: "modeling.linear_viscoelastic_calibration_plan",
          aggregate_id: "37700000-0000-4000-8000-000000000021",
          revision_id: "37700000-0000-4000-8000-000000000022",
          lifecycle_state: "review",
        });
      }
      throw new Error(`Unexpected request ${url}`);
    });

    render(<PolymerLinearViscoelasticFit config={config} testData={testData} testDataRef={testDataRef} sourceDocument={sourceDocument} catalogContext={catalogContext} />);
    expect(screen.queryByRole("navigation", { name: "Fit steps" })).toBeNull();
    expect(screen.getByRole("region", { name: "Calculate Prony models" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Review calculation settings" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Calculate Prony models" })).toBeNull();
    expect(screen.queryByText(/digest|sha256|candidate_id/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Review calculation settings" }));

    for (const label of ["Loading ramp", "Frequency sweep", "Preconditioning", "Linear viscoelastic range"]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value: "NOT_PROVIDED" } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Use all to calculate" }));
    expect(screen.getByRole("heading", { name: "Prony models" })).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Manual"));
    fireEvent.click(screen.getByLabelText("1-term Prony, 3 parameters"));
    const boundValues = [
      ["Equilibrium shear modulus G∞", "100000", "900000", "5000000"],
      ["Prony shear modulus G1", "100000", "1800000", "5000000"],
      ["Relaxation time τ1", "0.01", "0.4", "1"],
    ];
    boundValues.forEach(([name, lower, start, upper]) => {
      fireEvent.change(screen.getByLabelText(`1-term ${name} lower`), { target: { value: lower } });
      fireEvent.change(screen.getByLabelText(`1-term ${name} start`), { target: { value: start } });
      fireEvent.change(screen.getByLabelText(`1-term ${name} upper`), { target: { value: upper } });
    });
    const policyValues: Record<string, string> = {
      "Relaxation response weight (0–1)": "1",
      "Relaxation modulus scale (Pa)": "3000000",
      "Storage modulus weight (0–1)": "0.5",
      "Loss modulus weight (0–1)": "0.5",
      "Storage modulus scale (Pa)": "3000000",
      "Loss modulus scale (Pa)": "3000000",
      "Function tolerance": "1e-8",
      "Parameter tolerance": "1e-8",
      "Gradient tolerance": "1e-8",
      "Maximum evaluations": "1000",
    };
    Object.entries(policyValues).forEach(([label, value]) => {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    });
    fireEvent.change(screen.getByLabelText("Setup name"), { target: { value: "Reference relaxation setup" } });
    fireEvent.change(screen.getByLabelText("Reason for this setup"), { target: { value: "Calibrate the exact relaxation revision for review." } });
    await waitFor(() => expect((screen.getByRole("button", { name: "Request settings review" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "Request settings review" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, planCall] = fetchMock.mock.calls.map((call) => [String(call[0]), call[1]] as const).find(([url]) => url.endsWith("/linear-viscoelastic-calibration-plans"))!;
    const url = "/api/v1/linear-viscoelastic-calibration-plans";
    const init = planCall;
    expect(url).toBe("/api/v1/linear-viscoelastic-calibration-plans");
    const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
    expect(body.test_data).toEqual({ id: testDataRef.id, revision_id: testDataRef.revisionId });
    expect(body.term_counts).toEqual([1]);
    expect(body.point_dispositions).toHaveLength(3);
    expect(body.availability).toEqual({ ramp: "NOT_PROVIDED", sweep: "NOT_PROVIDED", preconditioning: "NOT_PROVIDED", linear_range: "NOT_PROVIDED" });
    expect(body.setup_name).toBe("Reference relaxation setup");
    expect(body.material).toEqual({ id: catalogContext.material.id, revision_id: catalogContext.material.revisionId });
    expect(body.material_state).toEqual({ id: catalogContext.materialState.id, revision_id: catalogContext.materialState.revisionId });
    expect(body.input_mode).toBe("relaxation");
    expect(body.change_reason).toBe("Calibrate the exact relaxation revision for review.");
    await waitFor(() => expect(fetchMock.mock.calls.some(([calledUrl]) => String(calledUrl).endsWith("/review-requests"))).toBe(true));
    const reviewCall = fetchMock.mock.calls.find(([calledUrl]) => String(calledUrl).endsWith("/review-requests"))!;
    expect(JSON.parse(String(reviewCall[1]?.body))).toMatchObject({
      aggregate_type: "modeling.linear_viscoelastic_calibration_plan",
      aggregate_id: "37700000-0000-4000-8000-000000000021",
      revision_id: "37700000-0000-4000-8000-000000000022",
      manifest_sha256: "a".repeat(64),
    });
  });
});
