import type { ModelingSessionSummary, ModelingStage } from "./modeling-session-context";

const stages: Array<{ id: ModelingStage; label: string }> = [
  { id: "data", label: "Data" },
  { id: "process", label: "Process" },
  { id: "fit", label: "Fit" },
  { id: "export", label: "Export" },
];

type StageStatus = "Complete" | "Blocked" | "Warning" | "Stale";

function stageStatusLabel(stage: ModelingStage, status: StageStatus): string {
  if (status === "Stale") return "Needs update";
  if (stage === "data") return status === "Complete" ? "Test data ready" : "Add test data";
  if (stage === "process") return status === "Complete" ? "Processed curves ready" : "Prepare test curves";
  if (stage === "fit") return status === "Complete" ? "Model selected" : "Choose a model";
  if (stage === "validate") return "Run validation";
  if (stage === "review") return "Submit for review";
  return status === "Complete" ? "Card ready" : "Ready to create card";
}

function stageStatus(session: ModelingSessionSummary | null, stage: ModelingStage): { status: StageStatus; reason: string } {
  const invalidation = session?.invalidation;
  const hasStale = (keys: string[]) => keys.some((key) => (
    invalidation?.dispositions[key as keyof typeof invalidation.dispositions] === "stale"
    && session?.stalePointers?.[key as keyof typeof session.stalePointers]
  ));
  if (stage === "data") return session?.testData
    ? { status: "Complete", reason: `Exact Test Data r${session.testData.revisionNo} pinned` }
    : { status: "Blocked", reason: "Choose and save an exact Test Data revision" };
  if (stage === "process") return hasStale(["processingOutput"])
    ? { status: "Stale", reason: "Upstream context changed; recompute Process" }
    : session?.processingOutput
      ? { status: "Complete", reason: `Current output r${session.processingOutput.revisionNo}` }
      : { status: "Blocked", reason: "Save Test Data before processing" };
  if (stage === "fit") return hasStale(["fitCandidate", "selection"])
    ? { status: "Stale", reason: "Fit evidence is no longer current" }
    : !session?.processingOutput
      ? { status: "Blocked", reason: "Save current processed curves before fitting" }
    : session?.selection
      ? { status: "Complete", reason: "Explicit candidate selection pinned" }
      : { status: "Warning", reason: "Candidate decision is not yet pinned" };
  if (stage === "validate") return hasStale(["validation"])
    ? { status: "Stale", reason: "Validation must be run again" }
    : session?.validation
      ? { status: "Warning", reason: `Pinned validation record · ${session.validation.label}; inspect the result state` }
      : { status: "Blocked", reason: "A candidate-compatible validation adapter, pinned plan and result are required" };
  if (stage === "review") return hasStale(["reviewRelease"])
    ? { status: "Stale", reason: "Source changed; a new review is required" }
    : { status: "Blocked", reason: "Review package and release policy are not configured for this session" };
  return session?.exportArtifact
    ? { status: "Complete", reason: `Delivered artifact r${session.exportArtifact.revisionNo} pinned` }
    : hasStale(["exportArtifact"]) || invalidation?.dispositions.exportArtifact === "regenerate"
    ? { status: "Stale", reason: "Target representation must be regenerated" }
    : session?.processingOutput && session.material && session.materialState && session.testData && session.mappingProfile
      ? { status: "Warning", reason: "Exact session source pinned; verify delivery lineage and target" }
      : { status: "Blocked", reason: "Pin current Material, State, Test Data, Mapping Profile, and output; previous output is never reused" };
}

export function ModelingStageShell({
  session,
  activeStage,
  onStageChange,
}: {
  session: ModelingSessionSummary | null;
  activeStage: ModelingStage;
  onStageChange: (stage: ModelingStage) => void;
}) {
  return <nav className="modeling-stage-shell" aria-label="Modeling workflow stages">
    {stages.map((stage, index) => {
      const state = stageStatus(session, stage.id);
      return <button
        key={stage.id}
        type="button"
        className={activeStage === stage.id ? "active" : ""}
        aria-current={activeStage === stage.id ? "step" : undefined}
        aria-label={`${stage.label} · ${stageStatusLabel(stage.id, state.status)} · ${state.reason}`}
        onClick={() => onStageChange(stage.id)}
        title={state.reason}
      >
        <span className="modeling-stage-number">{index + 1}</span>
        <strong>{stage.label}</strong>
      </button>;
    })}
  </nav>;
}
