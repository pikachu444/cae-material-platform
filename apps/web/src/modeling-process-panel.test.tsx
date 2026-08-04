import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ModelingProcessPanel from "./modeling-process-panel";
import type { CommonProcessingOutputResponse } from "./types";

function output(id: string): CommonProcessingOutputResponse {
  return {
    processing_output_id: id,
    current_revision: {} as CommonProcessingOutputResponse["current_revision"],
    label: `Saved ${id}`,
    source_document: { aggregate_id: "source", revision_id: "source-r1" },
    source_document_sha256: "source-hash",
    source_canonical_artifact_sha256: "canonical-hash",
    mapping_profile: { aggregate_id: "profile", revision_id: "profile-r1" },
    mapping_profile_sha256: "profile-hash",
    steps: [],
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
});
