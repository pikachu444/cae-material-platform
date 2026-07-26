import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  listValidationTemplates: vi.fn(),
  listValidationPlans: vi.fn(),
  listMaterialModels: vi.fn(),
  listDatasetsForMaterialState: vi.fn(),
  listSolverCards: vi.fn(),
  listDatasetRevisionSelections: vi.fn(),
  createReferenceValidationPlan: vi.fn(),
  getReferenceValidationResult: vi.fn(),
  submitReferenceValidationRun: vi.fn(),
  pollReferenceValidationRun: vi.fn(),
  evaluateReferenceValidationRun: vi.fn(),
}));

vi.mock("./api", () => ({
  ...api,
  ApiError: class ApiError extends Error {},
}));

import { ModelingValidationStage } from "./modeling-validation-stage";

const revision = { id: "00000000-0000-0000-0000-000000000002", revision_no: 1, content_sha256: "a".repeat(64) };
const template = { validation_template_id: "00000000-0000-0000-0000-000000000010", current_revision: { ...revision, content: { template_label: "Reference tensile specimen" } } };
const model = {
  material_model_id: "00000000-0000-0000-0000-000000000011",
  current_revision: {
    ...revision,
    content: { calibration_evidence: { calibration_candidate_id: "candidate" } },
  },
};
const card = { solver_card_id: "00000000-0000-0000-0000-000000000012", material_model_id: model.material_model_id, current_revision: { ...revision, content: { card_title: "OpenRadioss reference card" } } };
const selection = { selection_id: "00000000-0000-0000-0000-000000000013", selection_label: "Independent holdout", current_revision: { ...revision, content: {} } };
const plan = {
  validation_plan_id: "00000000-0000-0000-0000-000000000014",
  current_revision: {
    ...revision,
    content: {
      plan_label: "Pinned validation",
      material_model_revision_id: revision.id,
      solver_card_id: card.solver_card_id,
      solver_card_revision_id: revision.id,
      experimental_selection_revision_id: revision.id,
    },
  },
};

function renderStage(overrides: Partial<Parameters<typeof ModelingValidationStage>[0]> = {}) {
  const onNavigate = vi.fn();
  const onSessionChange = vi.fn();
  const onSessionEvent = vi.fn();
  render(<ModelingValidationStage
    config={{ baseUrl: "http://example.test", accessToken: "token" }}
    materialState={{ material_state_id: "00000000-0000-0000-0000-000000000001" } as never}
    family="metal"
    session={{
      selection: { id: "candidate", revisionId: "candidate-r1", label: "Selected Voce", revisionNo: 1 },
      processingOutput: { id: "output", revisionId: "output-r1", label: "Selected Voce", revisionNo: 1 },
      materialModelIr: { id: model.material_model_id, revisionId: revision.id, label: "Candidate IR", revisionNo: 1 },
      exportArtifact: { id: card.solver_card_id, revisionId: revision.id, label: "Reference card", revisionNo: 1 },
    } as never}
    onNavigate={onNavigate}
    onSessionChange={onSessionChange}
    onSessionEvent={onSessionEvent}
    {...overrides}
  />);
  return { onNavigate, onSessionChange, onSessionEvent };
}

describe("ModelingValidationStage", () => {
  it("keeps fit, validation, review, approval, and release as separate states", async () => {
    api.listValidationTemplates.mockResolvedValue({ data: { items: [] } });
    api.listValidationPlans.mockResolvedValue({ data: { items: [] } });
    api.listMaterialModels.mockResolvedValue({ data: { items: [] } });
    api.listDatasetsForMaterialState.mockResolvedValue({ data: { items: [] } });
    renderStage();

    expect(await screen.findByText("Available as fit evidence only")).toBeTruthy();
    expect(screen.getByText(/Review package/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Submit.*Not configured/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: /Request changes.*Not run/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: /Approve.*Not run/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: /Release.*Not configured/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(/never guesses SHA-256/i)).toBeTruthy();
  });

  it("pins only explicitly selected exact validation artifacts before submitting a job", async () => {
    api.listValidationTemplates.mockResolvedValue({ data: { items: [template] } });
    api.listValidationPlans.mockResolvedValue({ data: { items: [] } });
    api.listMaterialModels.mockResolvedValue({ data: { items: [model] } });
    api.listDatasetsForMaterialState.mockResolvedValue({ data: { items: [{ current_revision: revision }] } });
    api.listSolverCards.mockResolvedValue({ data: { items: [card] } });
    api.listDatasetRevisionSelections.mockResolvedValue({ data: { items: [selection] } });
    api.createReferenceValidationPlan.mockResolvedValue({ data: plan });
    const { onSessionChange, onSessionEvent, onNavigate } = renderStage();

    const create = await screen.findByRole("button", { name: "Create pinned validation plan" });
    expect((create as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Validation template"), { target: { value: template.validation_template_id } });
    fireEvent.change(screen.getByLabelText("Validation Material Model"), { target: { value: model.material_model_id } });
    fireEvent.change(screen.getByLabelText("Validation Solver Card"), { target: { value: card.solver_card_id } });
    fireEvent.change(screen.getByLabelText("Validation experimental selection"), { target: { value: selection.selection_id } });
    expect((create as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(create);

    await waitFor(() => expect(api.createReferenceValidationPlan).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ content: expect.objectContaining({ material_model_revision_id: revision.id, solver_card_revision_id: revision.id, experimental_selection_revision_id: revision.id }) })));
    expect(onSessionEvent).toHaveBeenCalledWith({ type: "CHANGE_VALIDATION_TARGET" });
    expect(onSessionChange).toHaveBeenCalledWith({ validationPlan: expect.objectContaining({ id: plan.validation_plan_id, revisionId: revision.id }) });
    fireEvent.click(screen.getByRole("button", { name: "Open Activity context" }));
    expect(onNavigate).toHaveBeenCalledWith(expect.stringContaining("candidate_id=candidate"));
  });

  it("does not substitute a validation path for an unsupported family", async () => {
    api.listValidationTemplates.mockResolvedValue({ data: { items: [] } });
    api.listValidationPlans.mockResolvedValue({ data: { items: [] } });
    api.listMaterialModels.mockResolvedValue({ data: { items: [] } });
    api.listDatasetsForMaterialState.mockResolvedValue({ data: { items: [] } });
    renderStage({ family: "polymer" });

    expect(await screen.findByText(/Not supported: this non-production OpenRadioss reference path/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create pinned validation plan" })).toBeNull();
  });

  it("rejects a model from the same state when its candidate lineage is different", async () => {
    api.listValidationTemplates.mockResolvedValue({ data: { items: [template] } });
    api.listValidationPlans.mockResolvedValue({ data: { items: [] } });
    api.listMaterialModels.mockResolvedValue({
      data: {
        items: [{
          ...model,
          current_revision: {
            ...model.current_revision,
            content: { calibration_evidence: { calibration_candidate_id: "another-candidate" } },
          },
        }],
      },
    });
    api.listDatasetsForMaterialState.mockResolvedValue({ data: { items: [] } });
    api.listSolverCards.mockResolvedValue({ data: { items: [card] } });
    renderStage();

    expect(await screen.findByText(/Not supported for this selected candidate/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create pinned validation plan" })).toBeNull();
  });

  it("does not expose plan controls without the exact session Solver Card", async () => {
    api.listValidationTemplates.mockResolvedValue({ data: { items: [template] } });
    api.listValidationPlans.mockResolvedValue({ data: { items: [] } });
    api.listMaterialModels.mockResolvedValue({ data: { items: [model] } });
    api.listDatasetsForMaterialState.mockResolvedValue({ data: { items: [] } });
    api.listSolverCards.mockResolvedValue({ data: { items: [card] } });
    renderStage({
      session: {
        selection: { id: "candidate", revisionId: "candidate-r1", label: "Selected Voce", revisionNo: 1 },
        processingOutput: { id: "output", revisionId: "output-r1", label: "Selected Voce", revisionNo: 1 },
        materialModelIr: { id: model.material_model_id, revisionId: revision.id, label: "Candidate IR", revisionNo: 1 },
      } as never,
    });

    expect(await screen.findByText(/exact Solver Card is not pinned/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create pinned validation plan" })).toBeNull();
  });

  it("keeps an already pinned plan runnable after validation-target invalidation clears the card pointer", async () => {
    api.listValidationTemplates.mockResolvedValue({ data: { items: [template] } });
    api.listValidationPlans.mockResolvedValue({ data: { items: [plan] } });
    api.listMaterialModels.mockResolvedValue({ data: { items: [model] } });
    api.listDatasetsForMaterialState.mockResolvedValue({ data: { items: [] } });
    api.listSolverCards.mockResolvedValue({ data: { items: [card] } });
    renderStage({
      session: {
        selection: { id: "candidate", revisionId: "candidate-r1", label: "Selected Voce", revisionNo: 1 },
        processingOutput: { id: "output", revisionId: "output-r1", label: "Selected Voce", revisionNo: 1 },
        materialModelIr: { id: model.material_model_id, revisionId: revision.id, label: "Candidate IR", revisionNo: 1 },
        validationPlan: { id: plan.validation_plan_id, revisionId: revision.id, label: "Pinned validation", revisionNo: 1 },
      } as never,
    });

    expect(await screen.findByText(/Plan 00000000…0014 pins model revision/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Submit validation job" }).hasAttribute("disabled")).toBe(false);
    expect(screen.queryByRole("button", { name: "Create pinned validation plan" })).toBeNull();
  });

  it("restores the exact plan and immutable result on remount", async () => {
    const savedResult = {
      validation_result_id: "00000000-0000-0000-0000-000000000099",
      validation_result_manifest_id: "00000000-0000-0000-0000-000000000098",
      verdict: "passed",
      holdout_independence: "independent_selection",
      relative_root_mean_squared_error: 0.012,
    };
    api.listValidationTemplates.mockResolvedValue({ data: { items: [template] } });
    api.listValidationPlans.mockResolvedValue({ data: { items: [plan] } });
    api.listMaterialModels.mockResolvedValue({ data: { items: [model] } });
    api.listDatasetsForMaterialState.mockResolvedValue({ data: { items: [] } });
    api.listSolverCards.mockResolvedValue({ data: { items: [card] } });
    api.getReferenceValidationResult.mockResolvedValue({ data: savedResult });
    renderStage({
      session: {
        selection: { id: "candidate", revisionId: "candidate-r1", label: "Selected Voce", revisionNo: 1 },
        processingOutput: { id: "output", revisionId: "output-r1", label: "Selected Voce", revisionNo: 1 },
        materialModelIr: { id: model.material_model_id, revisionId: revision.id, label: "Candidate IR", revisionNo: 1 },
        exportArtifact: { id: card.solver_card_id, revisionId: revision.id, label: "Reference card", revisionNo: 1 },
        validationPlan: { id: plan.validation_plan_id, revisionId: revision.id, label: "Pinned validation", revisionNo: 1 },
        validation: { id: savedResult.validation_result_id, revisionId: savedResult.validation_result_manifest_id, label: "Validation passed", revisionNo: 1 },
      } as never,
    });

    expect(await screen.findByText(/Pinned validation · r1/)).toBeTruthy();
    expect(screen.getByText(/Validation result passed · relative RMSE/i)).toBeTruthy();
    expect(api.getReferenceValidationResult).toHaveBeenCalledWith(
      expect.anything(),
      savedResult.validation_result_id,
    );
  });
});
