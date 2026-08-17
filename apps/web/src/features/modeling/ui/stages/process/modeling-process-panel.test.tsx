import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ModelingProcessPanel, { parseSavedProcessingOutput } from "./modeling-process-panel";
import type { CommonProcessingOutputResponse } from "../../../model/common-processing-contracts";

function output(id: string): CommonProcessingOutputResponse {
  return {
    processing_output_id: id,
    current_revision: { revision_no: 1 } as CommonProcessingOutputResponse["current_revision"],
    label: `Saved ${id}`,
    source_document: { aggregate_id: "source", revision_id: "source-r1" },
    source_document_sha256: "source-hash",
    source_canonical_artifact_sha256: "canonical-hash",
    mapping_profile: { aggregate_id: "profile", revision_id: "profile-r1" },
    mapping_profile_sha256: "profile-hash",
    steps: [
      { method_id: "rows.sort_unique", method_version: "1.0.0", options: { duplicate_policy: "reject" } },
      { method_id: "metal.elastic_modulus", method_version: "1.0.0", options: { method: "robust_huber" } },
    ],
    independent_quantity: "strain.engineering",
    stage_count: 1,
    final_point_count: 1,
    output_artifact_id: `${id}-artifact`,
    output_sha256: `${id}-hash`,
    workup_overrides: [],
    fit_decision: null,
    export_provenance: null,
  };
}

const baseProps = {
  stepLabel: "Young's modulus",
  sourceIdentity: "Tensile · r1",
  stepControls: <p>Controls</p>,
  processReady: true,
  hasPreview: true,
  hasLastValidPreview: false,
  busy: false,
  outputLabel: "Processed curve",
  outputReason: "Save result",
  savedResultStates: {},
  onClose: vi.fn(),
  onOutputLabelChange: vi.fn(),
  onOutputReasonChange: vi.fn(),
  onSave: vi.fn(),
  onLoadSavedResult: vi.fn(),
  onUseSavedSettings: vi.fn(),
};

function artifactFor(saved: CommonProcessingOutputResponse, overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    document_type: "cmp.processing-output",
    output_id: saved.processing_output_id,
    source_document: saved.source_document,
    mapping_profile: saved.mapping_profile,
    steps: saved.steps,
    result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: 210_000_000_000, unit: "Pa" }] }] },
    ...overrides,
  });
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ModelingProcessPanel saved result disclosure", () => {
  it("loads outputs that arrive after opening an empty disclosure exactly once", async () => {
    const onLoadSavedResult = vi.fn();
    const first = output("output-1");
    const second = output("output-2");
    const view = render(<ModelingProcessPanel {...baseProps} savedOutputs={[]} onLoadSavedResult={onLoadSavedResult} />);

    fireEvent.click(screen.getByText("Saved results (0)"));
    expect(onLoadSavedResult).not.toHaveBeenCalled();

    view.rerender(<ModelingProcessPanel {...baseProps} savedOutputs={[first, second]} onLoadSavedResult={onLoadSavedResult} />);
    await waitFor(() => expect(onLoadSavedResult).toHaveBeenCalledTimes(2));
    expect(onLoadSavedResult).toHaveBeenNthCalledWith(1, first);
    expect(onLoadSavedResult).toHaveBeenNthCalledWith(2, second);
  });

  it("does not duplicate loads across unrelated rerenders or unstable callbacks", async () => {
    const first = output("output-1");
    const second = output("output-2");
    const initialLoad = vi.fn();
    const replacementLoad = vi.fn();
    const view = render(<ModelingProcessPanel {...baseProps} savedOutputs={[first, second]} onLoadSavedResult={initialLoad} />);

    fireEvent.click(screen.getByText("Saved results (2)"));
    await waitFor(() => expect(initialLoad).toHaveBeenCalledTimes(2));
    view.rerender(<ModelingProcessPanel {...baseProps} outputLabel="Unrelated rerender" savedOutputs={[first, second]} onLoadSavedResult={replacementLoad} />);
    await waitFor(() => expect(screen.getByDisplayValue("Unrelated rerender")).toBeTruthy());
    expect(initialLoad).toHaveBeenCalledTimes(2);
    expect(replacementLoad).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Saved results (2)"));
    fireEvent.click(screen.getByText("Saved results (2)"));
    await waitFor(() => expect(replacementLoad).toHaveBeenCalledTimes(2));
  });

  it("makes removed output IDs eligible when they reappear while open", async () => {
    const saved = output("output-1");
    const onLoadSavedResult = vi.fn();
    const view = render(<ModelingProcessPanel {...baseProps} savedOutputs={[saved]} onLoadSavedResult={onLoadSavedResult} />);

    fireEvent.click(screen.getByText("Saved results (1)"));
    await waitFor(() => expect(onLoadSavedResult).toHaveBeenCalledTimes(1));
    view.rerender(<ModelingProcessPanel {...baseProps} savedOutputs={[]} onLoadSavedResult={onLoadSavedResult} />);
    view.rerender(<ModelingProcessPanel {...baseProps} savedOutputs={[saved]} onLoadSavedResult={onLoadSavedResult} />);
    await waitFor(() => expect(onLoadSavedResult).toHaveBeenCalledTimes(2));
  });

  it("loads outputs already present when the disclosure is opened", async () => {
    const first = output("output-1");
    const second = output("output-2");
    const onLoadSavedResult = vi.fn();
    render(<ModelingProcessPanel {...baseProps} savedOutputs={[first, second]} onLoadSavedResult={onLoadSavedResult} />);

    expect(onLoadSavedResult).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Saved results (2)"));
    await waitFor(() => expect(onLoadSavedResult).toHaveBeenCalledTimes(2));
  });

  it("exposes only the settled exact-source retry and keeps it keyboard reachable", () => {
    const onRetryExactSource = vi.fn();
    const { rerender } = render(
      <ModelingProcessPanel
        {...baseProps}
        savedOutputs={[]}
        processReady={false}
        sourceIdentity="Exact source unavailable · r1"
        onRetryExactSource={onRetryExactSource}
      />,
    );
    const retry = screen.getByRole("button", { name: "Retry exact source" });
    expect(retry).toBeTruthy();
    retry.focus();
    expect(document.activeElement).toBe(retry);
    fireEvent.click(retry);
    expect(onRetryExactSource).toHaveBeenCalledTimes(1);
    rerender(<ModelingProcessPanel {...baseProps} savedOutputs={[]} processReady={false} sourceIdentity="No exact Test Data" />);
    expect(screen.queryByRole("button", { name: "Retry exact source" })).toBeNull();
  });
});

describe("Saved Processing Output artifact contract", () => {
  it("returns the finite Pa scalar only for a fully exact artifact", () => {
    const saved = output("output-valid");
    expect(parseSavedProcessingOutput(artifactFor(saved), saved, ["source", "source-r1", "profile", "profile-r1"])).toBe(210_000_000_000);
  });

  it.each([
    ["document type", (artifact: Record<string, unknown>) => ({ ...artifact, document_type: "cmp.other" })],
    ["output id", (artifact: Record<string, unknown>) => ({ ...artifact, output_id: "other-output" })],
    ["ordered steps", (artifact: Record<string, unknown>) => ({ ...artifact, steps: [...(artifact.steps as unknown[]).slice().reverse()] })],
    ["Artifact row source", (artifact: Record<string, unknown>) => ({ ...artifact, source_document: { aggregate_id: "other-source", revision_id: "source-r1" } })],
    ["Artifact caller source", (artifact: Record<string, unknown>) => artifact],
    ["Artifact row profile", (artifact: Record<string, unknown>) => ({ ...artifact, mapping_profile: { aggregate_id: "other-profile", revision_id: "profile-r1" } })],
    ["Artifact caller profile", (artifact: Record<string, unknown>) => artifact],
    ["unit", (artifact: Record<string, unknown>) => ({ ...artifact, result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: 210_000_000_000, unit: "MPa" }] }] } })],
    ["non-number", (artifact: Record<string, unknown>) => ({ ...artifact, result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: "210000000000", unit: "Pa" }] }] } })],
    ["non-finite", (artifact: Record<string, unknown>) => ({ ...artifact, result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: null, unit: "Pa" }] }] } })],
  ] as const)("rejects %s without fallback", (_name, mutate) => {
    const saved = output("output-invalid");
    const artifact = JSON.parse(artifactFor(saved)) as Record<string, unknown>;
    const text = artifactFor(saved, mutate(artifact));
    const callerPins: [string | undefined, string | undefined, string | undefined, string | undefined] = ["source", "source-r1", "profile", "profile-r1"];
    if (_name === "Artifact caller source") callerPins[0] = "other-source";
    if (_name === "Artifact caller profile") callerPins[2] = "other-profile";
    expect(() => parseSavedProcessingOutput(text, saved, callerPins)).toThrow("Saved result unavailable");
  });

  it("rejects a non-r1 row revision", () => {
    const saved = output("output-revision");
    const row = { ...saved, current_revision: { revision_no: 2 } as CommonProcessingOutputResponse["current_revision"] };
    expect(() => parseSavedProcessingOutput(artifactFor(saved), row, ["source", "source-r1", "profile", "profile-r1"])).toThrow("Saved result unavailable");
  });
});

describe("ModelingProcessPanel result surface states", () => {
  it("labels the server response as Result and keeps normal completion feedback out of the visual band", () => {
    render(
      <ModelingProcessPanel
        {...baseProps}
        savedOutputs={[]}
        scalarPa={210_000_000_000}
        notice="Preview ready."
      />,
    );

    expect(screen.getByRole("heading", { name: "Result" })).toBeTruthy();
    expect(screen.getByText("Young's modulus")).toBeTruthy();
    expect(screen.getByText("210.0 GPa")).toBeTruthy();
    expect(screen.queryByText("Calculated preview", { exact: true })).toBeNull();
    expect(screen.queryByText("Server result · preview only", { exact: true })).toBeNull();
    expect(document.querySelector(".process-band-status")?.className).toContain("visually-hidden");
    expect(screen.getByText("Saved results (0)")).toBeTruthy();
  });

  it("keeps the last server result visible and asks for a new preview only after draft changes", () => {
    render(
      <ModelingProcessPanel
        {...baseProps}
        savedOutputs={[]}
        hasPreview={false}
        hasLastValidPreview
        scalarPa={210_000_000_000}
        notice="Current Process result cleared; saved results remain in history. Fit and Export require a new saved processed result."
      />,
    );

    expect(screen.getByText("210.0 GPa")).toBeTruthy();
    expect(screen.getByText("Result retained; preview again to save changes.")).toBeTruthy();
    expect(document.querySelector(".process-band-status")?.className).toContain("visually-hidden");
  });

  it("keeps Use settings disabled while loading, offers row-local Retry on error, and enables ready rows", () => {
    const saved = output("output-surface");
    const onLoadSavedResult = vi.fn();
    const onUseSavedSettings = vi.fn();
    const { rerender } = render(
      <ModelingProcessPanel
        {...baseProps}
        savedOutputs={[saved]}
        savedResultStates={{ [saved.processing_output_id]: { status: "loading" } }}
        onLoadSavedResult={onLoadSavedResult}
        onUseSavedSettings={onUseSavedSettings}
      />,
    );
    fireEvent.click(screen.getByText("Saved results (1)"));
    const table = screen.getByRole("table", { name: "Saved processing results" });
    expect(Array.from(table.querySelectorAll("thead th"), (header) => header.textContent)).toEqual([
      "Label", "Method", "Range", "Result", "Revision", "State", "Action",
    ]);
    expect(within(table).getByText("Auto robust")).toBeTruthy();
    expect(table.textContent).not.toContain("Tensile · r1");
    expect(screen.getByText("Loading saved result…", { exact: false })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Use settings" }) as HTMLButtonElement).disabled).toBe(true);

    rerender(
      <ModelingProcessPanel
        {...baseProps}
        savedOutputs={[saved]}
        savedResultStates={{ [saved.processing_output_id]: { status: "error" } }}
        onLoadSavedResult={onLoadSavedResult}
        onUseSavedSettings={onUseSavedSettings}
      />,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onLoadSavedResult).toHaveBeenCalledWith(saved);

    rerender(
      <ModelingProcessPanel
        {...baseProps}
        savedOutputs={[saved]}
        currentOutputId={saved.processing_output_id}
        savedResultStates={{ [saved.processing_output_id]: { status: "ready", scalarPa: 210_000_000_000 } }}
        onLoadSavedResult={onLoadSavedResult}
        onUseSavedSettings={onUseSavedSettings}
      />,
    );
    expect(screen.getByText(/210\.0 GPa/)).toBeTruthy();
    expect(within(document.querySelector(".process-comparison-row") as HTMLElement).getByText(/current/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Use settings" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Use settings" }));
    expect(onUseSavedSettings).toHaveBeenCalledWith(saved);
  });
});
