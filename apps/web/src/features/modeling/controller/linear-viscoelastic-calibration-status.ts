import type { LinearViscoelasticCalibrationPhase } from "../model/linear-viscoelastic-calibration-state";

export function linearViscoelasticCalibrationStatus(phase: LinearViscoelasticCalibrationPhase) {
  if (phase === "saved") return { kind: "success" as const, label: "Model saved" };
  if (phase === "selection-saved") return { kind: "success" as const, label: "Selection saved" };
  if (phase === "succeeded") return { kind: "success" as const, label: "Calculation complete" };
  if (phase === "failed" || phase === "error") return { kind: "danger" as const, label: "Review required" };
  if (phase === "stale") return { kind: "warning" as const, label: "Stale upstream" };
  if (phase === "saving-selection") return { kind: "warning" as const, label: "Saving selection" };
  if (phase === "saving-model") return { kind: "warning" as const, label: "Saving model" };
  if (phase === "running" || phase === "queueing-run" || phase === "creating-plan") {
    return { kind: "warning" as const, label: "Calculation in progress" };
  }
  return { kind: "warning" as const, label: "Setup required" };
}
