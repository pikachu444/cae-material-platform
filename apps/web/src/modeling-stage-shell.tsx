import type { ModelingSessionSummary, ModelingStage } from "./features/modeling";
import "./features/modeling/ui/stages/process/modeling-process-stage.css";
import "./features/modeling/ui/stages/fit/modeling-fit-stage.css";
import "./features/modeling/ui/stages/export/modeling-export-stage.css";
import "./features/modeling/ui/modeling-export-delivery-workbenches.css";
import "./features/modeling/ui/modeling-stage-normalization.css";

const stages: Array<{ id: ModelingStage; label: string }> = [
  { id: "data", label: "Data" },
  { id: "process", label: "Process" },
  { id: "fit", label: "Fit" },
  { id: "export", label: "Export" },
];

type StageStatus = "Complete" | "Blocked" | "Warning" | "Stale";

function stageStatusLabel(stage: ModelingStage, status: StageStatus, processOptional: boolean): string {
  if (status === "Stale") return "Needs update";
  if (stage === "data") return status === "Complete" ? "Test data ready" : "Add test data";
  if (stage === "process" && processOptional) return "Optional for this data";
  if (stage === "process") return status === "Complete" ? "Processed curves ready" : "Prepare test curves";
  if (stage === "fit") return status === "Complete" ? "Model selected" : "Choose a model";
  if (stage === "validate") return "Run validation";
  if (stage === "review") return "Submit for review";
  return status === "Complete" ? "Card ready" : "Ready to create card";
}

function stageStatus(session: ModelingSessionSummary | null, stage: ModelingStage, processOptional: boolean): { status: StageStatus; reason: string } {
  const invalidation = session?.invalidation;
  const hasStale = (keys: string[]) => keys.some((key) => (
    invalidation?.dispositions[key as keyof typeof invalidation.dispositions] === "stale"
    && session?.stalePointers?.[key as keyof typeof session.stalePointers]
  ));
  if (stage === "data") return session?.testData
    ? { status: "Complete", reason: "Test Data selected" }
    : { status: "Blocked", reason: "Choose Test Data" };
  if (stage === "process" && processOptional && !session?.processingOutput) {
    return { status: "Complete", reason: "Raw relaxation data can be fitted directly" };
  }
  if (stage === "process") return hasStale(["processingOutput"])
    ? { status: "Stale", reason: "Upstream context changed; recompute Process" }
    : session?.processingOutput
      ? { status: "Complete", reason: "Process result saved" }
      : { status: "Blocked", reason: "Select Test Data before processing" };
  if (stage === "fit") return hasStale(["fitCandidate", "selection"])
    ? { status: "Stale", reason: "Fit evidence is no longer current" }
    : !processOptional && !session?.processingOutput
      ? { status: "Blocked", reason: "Save current processed curves before fitting" }
    : session?.selection
      ? { status: "Complete", reason: "Model selected" }
      : { status: "Warning", reason: "Select a model" };
  if (stage === "validate") return hasStale(["validation"])
    ? { status: "Stale", reason: "Validation must be run again" }
    : session?.validation
      ? { status: "Warning", reason: `Pinned validation record · ${session.validation.label}; inspect the result state` }
      : { status: "Blocked", reason: "A candidate-compatible validation adapter, pinned plan and result are required" };
  if (stage === "review") return hasStale(["reviewRelease"])
    ? { status: "Stale", reason: "Source changed; a new review is required" }
    : { status: "Blocked", reason: "Review package and release policy are not configured for this session" };
  return session?.exportArtifact
    ? { status: "Complete", reason: "Solver card created" }
    : hasStale(["exportArtifact"]) || invalidation?.dispositions.exportArtifact === "regenerate"
    ? { status: "Stale", reason: "Target representation must be regenerated" }
    : (processOptional || session?.processingOutput)
      && session?.material && session.materialState && session.testData && session.mappingProfile
      ? { status: "Warning", reason: "Choose a destination and review the solver card" }
      : { status: "Blocked", reason: processOptional ? "Complete Data and Fit first" : "Complete Data, Process, and Fit first" };
}

export function ModelingStageShell({
  session,
  activeStage,
  processOptional = false,
  onStageChange,
}: {
  session: ModelingSessionSummary | null;
  activeStage: ModelingStage;
  processOptional?: boolean;
  onStageChange: (stage: ModelingStage) => void;
}) {
  return <nav className="modeling-stage-shell" aria-label="Modeling workflow stages">
    {stages.map((stage, index) => {
      const state = stageStatus(session, stage.id, processOptional);
      const label = stage.id === "process" && processOptional ? "Process (optional)" : stage.label;
      return <button
        key={stage.id}
        type="button"
        className={activeStage === stage.id ? "active" : ""}
        aria-current={activeStage === stage.id ? "step" : undefined}
        aria-label={`${label} · ${stageStatusLabel(stage.id, state.status, processOptional)} · ${state.reason}`}
        onClick={() => onStageChange(stage.id)}
        title={state.reason}
      >
        <span className="modeling-stage-number">{index + 1}</span>
        <strong>{label}</strong>
      </button>;
    })}
  </nav>;
}
