import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticResponseResidualEvidence,
  LinearViscoelasticRunResponse,
  LinearViscoelasticSelectionResponse,
} from "./linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticModelResponse } from "./modeling-resource-contracts";

export type LinearViscoelasticCalibrationPhase =
  | "idle"
  | "creating-plan"
  | "plan-ready"
  | "queueing-run"
  | "running"
  | "succeeded"
  | "failed"
  | "saving-selection"
  | "selection-saved"
  | "saving-model"
  | "saved"
  | "stale"
  | "error";

export interface LinearViscoelasticCalibrationState {
  phase: LinearViscoelasticCalibrationPhase;
  plan: LinearViscoelasticPlanResponse | null;
  run: LinearViscoelasticRunResponse | null;
  candidates: LinearViscoelasticCandidate[];
  recommendation: LinearViscoelasticRunResponse["recommendation"];
  responseEvidence: LinearViscoelasticResponseResidualEvidence | null;
  selection: LinearViscoelasticSelectionResponse | null;
  selectedModel: LinearViscoelasticModelResponse | null;
  selectedCandidateId: string;
  reason: string;
  error: string | null;
  recoveryHint: string | null;
}

export const INITIAL_LINEAR_VISCOELASTIC_CALIBRATION_STATE: LinearViscoelasticCalibrationState = {
  phase: "idle",
  plan: null,
  run: null,
  candidates: [],
  recommendation: null,
  responseEvidence: null,
  selection: null,
  selectedModel: null,
  selectedCandidateId: "",
  reason: "",
  error: null,
  recoveryHint: null,
};

export type LinearViscoelasticCalibrationAction =
  | { type: "RESET" }
  | { type: "STALE"; error?: string }
  | { type: "PLAN_START" }
  | { type: "PLAN_READY"; plan: LinearViscoelasticPlanResponse }
  | { type: "RUN_START" }
  | { type: "RUN_ACCEPTED"; run: LinearViscoelasticRunResponse }
  | { type: "RUN_UPDATE"; run: LinearViscoelasticRunResponse }
  | { type: "RUN_SUCCEEDED"; run: LinearViscoelasticRunResponse; candidates: LinearViscoelasticCandidate[]; recommendation: LinearViscoelasticRunResponse["recommendation"]; responseEvidence: LinearViscoelasticResponseResidualEvidence | null }
  | { type: "RUN_FAILED"; run: LinearViscoelasticRunResponse }
  | { type: "SELECT_CANDIDATE"; candidateId: string }
  | { type: "SET_REASON"; reason: string }
  | { type: "SELECTION_START" }
  | { type: "SELECTION_RESTORED"; selection: LinearViscoelasticSelectionResponse }
  | { type: "SELECTION_RECORDED"; selection: LinearViscoelasticSelectionResponse }
  | { type: "MODEL_SAVE_START" }
  | { type: "MODEL_SAVED"; model: LinearViscoelasticModelResponse }
  | { type: "ERROR"; error: string; recoveryHint?: string | null };

export function reduceLinearViscoelasticCalibration(
  state: LinearViscoelasticCalibrationState,
  action: LinearViscoelasticCalibrationAction,
): LinearViscoelasticCalibrationState {
  switch (action.type) {
    case "RESET":
      return INITIAL_LINEAR_VISCOELASTIC_CALIBRATION_STATE;
    case "STALE":
      return { ...state, phase: "stale", error: action.error ?? "The exact upstream revision changed. Create a new Plan." };
    case "PLAN_START":
      return { ...state, phase: "creating-plan", error: null, recoveryHint: null, selection: null, selectedModel: null };
    case "PLAN_READY":
      return { ...state, phase: "plan-ready", plan: action.plan, run: null, candidates: [], recommendation: null, responseEvidence: null, selection: null, selectedModel: null, error: null, recoveryHint: null };
    case "RUN_START":
      return { ...state, phase: "queueing-run", error: null, recoveryHint: null };
    case "RUN_ACCEPTED":
      return { ...state, phase: "running", run: action.run, error: null, recoveryHint: null };
    case "RUN_UPDATE":
      return { ...state, phase: action.run.status === "failed" ? "failed" : "running", run: action.run, error: action.run.failure_detail, recoveryHint: action.run.recovery_hint };
    case "RUN_SUCCEEDED":
      return { ...state, phase: "succeeded", run: action.run, candidates: action.candidates, recommendation: action.recommendation, responseEvidence: action.responseEvidence, error: null, recoveryHint: null };
    case "RUN_FAILED":
      return { ...state, phase: "failed", run: action.run, error: action.run.failure_detail ?? "The calibration Run failed.", recoveryHint: action.run.recovery_hint };
    case "SELECT_CANDIDATE":
      return { ...state, selectedCandidateId: action.candidateId, selection: null, selectedModel: null, phase: state.phase === "saved" || state.phase === "selection-saved" ? "succeeded" : state.phase };
    case "SET_REASON":
      return { ...state, reason: action.reason, selection: null, selectedModel: null, phase: state.phase === "saved" || state.phase === "selection-saved" ? "succeeded" : state.phase };
    case "SELECTION_START":
      return { ...state, phase: "saving-selection", error: null, recoveryHint: null };
    case "SELECTION_RESTORED":
      return { ...state, phase: "selection-saved", selection: action.selection, selectedCandidateId: action.selection.candidate_id, reason: action.selection.reason, selectedModel: null, error: null, recoveryHint: null };
    case "SELECTION_RECORDED":
      return { ...state, phase: "selection-saved", selection: action.selection, selectedCandidateId: action.selection.candidate_id, reason: action.selection.reason, selectedModel: null, error: null, recoveryHint: null };
    case "MODEL_SAVE_START":
      return { ...state, phase: "saving-model", error: null, recoveryHint: null };
    case "MODEL_SAVED":
      return { ...state, phase: "saved", selectedModel: action.model, error: null, recoveryHint: null };
    case "ERROR":
      return { ...state, phase: "error", error: action.error, recoveryHint: action.recoveryHint ?? null };
  }
}

export function terminalRunStatus(status: string): boolean {
  return status === "succeeded" || status === "failed";
}
