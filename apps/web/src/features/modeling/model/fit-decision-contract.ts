import type { CommonCurveStage, CommonProcessingStep } from "./common-processing-contracts";

export type FitDecisionMode = "single" | "blend";
export const METAL_HARDENING_EQUATION_CONTRACT = "altair-material-modeler-2025-v1";

export function hardeningCandidateWarning(
  family: string,
  parameterNearBound: boolean,
): string | undefined {
  const warnings: string[] = [];
  if (family === "ghosh") {
    warnings.push(
      "Ghosh n and p are not separately identifiable; evidence stores p − n, and εp must remain below ε0",
    );
  }
  if (parameterNearBound) warnings.push("Parameter near bound");
  return warnings.length ? warnings.join("; ") : undefined;
}

/**
 * A local, explicit engineering choice. Recipe options are fit-run intent only;
 * this record is deliberately not derived from them. The immutable snapshot is
 * created only by the explicit Save fit & continue action.
 */
export interface FitDecisionSelection {
  candidateKey: string;
  displayLabel: string;
  mode: FitDecisionMode;
  primaryLaw: string;
  secondaryLaw?: string;
  primaryWeight?: number;
  actualTermCount?: number;
  requestedTermPolicy?: string;
  reason: string;
  warningAcknowledged: boolean;
  fitRange: string;
  warning?: string;
}

export interface FitDecisionSnapshotInput {
  candidate_key: string;
  mode: FitDecisionMode;
  primary_law: string;
  secondary_law: string | null;
  primary_weight: number | null;
  parameter_sets: Array<{
    law: string;
    parameters: Array<{
      name: string;
      value: number;
      unit: string;
      lower: number | null;
      upper: number | null;
    }>;
  }>;
  fit_minimum: number;
  fit_maximum: number;
  extrapolation_maximum: number | null;
  extrapolation_policy: string;
  metric_definition: string;
  metric_value: number;
  requested_term_policy: string | null;
  actual_term_count: number | null;
  selection_reason: string;
  warning_acknowledged: boolean;
}

/** Build persistence input only from the active server-recomputed stage plus an explicit choice. */
export function buildFitDecisionSnapshot(
  selection: FitDecisionSelection,
  step: CommonProcessingStep,
  stage: CommonCurveStage,
  independentQuantity: string,
): FitDecisionSnapshotInput | null {
  const scalar = new Map(stage.scalar_results.map((item) => [item.key, item]));
  const fitMinimum = Number(step.options.fit_minimum_strain);
  const fitMaximum = Number(step.options.fit_maximum_strain);
  if (step.method_id === "metal.hardening_fit_extrapolate") {
    if (step.options.equation_contract !== METAL_HARDENING_EQUATION_CONTRACT) return null;
    const laws = selection.mode === "blend"
      ? [selection.primaryLaw, selection.secondaryLaw]
      : [selection.primaryLaw];
    if (
      !Number.isFinite(fitMinimum)
      || !Number.isFinite(fitMaximum)
      || laws.some((law) => !law)
    ) return null;
    const parameterSets = laws.map((law) => {
      const parameters = stage.scalar_results
        .filter((item) =>
          item.key.startsWith(`${law}.parameter.`)
          && !item.key.endsWith(".lower")
          && !item.key.endsWith(".upper")
          && !item.key.endsWith(".initial")
        )
        .map((item) => ({
          name: item.key.replace(`${law}.parameter.`, ""),
          value: item.value,
          unit: item.unit,
          lower: scalar.get(`${item.key}.lower`)?.value ?? null,
          upper: scalar.get(`${item.key}.upper`)?.value ?? null,
        }));
      return { law: law!, parameters };
    });
    const metric = scalar.get(`${selection.primaryLaw}.relative_rmse`);
    const extrapolationMaximum = Number(step.options.extrapolation_maximum_strain);
    if (
      !metric
      || !Number.isFinite(extrapolationMaximum)
      || parameterSets.some((set) => !set.parameters.length)
    ) return null;
    const ghoshParameters = parameterSets.find((set) => set.law === "ghosh")?.parameters;
    if (
      ghoshParameters
      && (
        !ghoshParameters.some((item) => item.name === "delta_p_minus_n")
        || ghoshParameters.some((item) => ["n", "p", "d_pa"].includes(item.name))
      )
    ) return null;
    return {
      candidate_key: selection.mode === "blend"
        ? `${selection.primaryLaw}+${selection.secondaryLaw}`
        : selection.primaryLaw,
      mode: selection.mode,
      primary_law: selection.primaryLaw,
      secondary_law: selection.mode === "blend" ? selection.secondaryLaw ?? null : null,
      primary_weight: selection.mode === "blend" ? selection.primaryWeight ?? null : null,
      parameter_sets: parameterSets,
      fit_minimum: fitMinimum,
      fit_maximum: fitMaximum,
      extrapolation_maximum: extrapolationMaximum,
      extrapolation_policy: "bounded",
      metric_definition: "relative_rmse",
      metric_value: metric.value,
      requested_term_policy: null,
      actual_term_count: null,
      selection_reason: selection.reason.trim(),
      warning_acknowledged: selection.warningAcknowledged,
    };
  }
  const actual = Number(scalar.get("prony_selected_term_count")?.value);
  const metric = scalar.get(`prony_${actual}_normalized_rmse`);
  if (
    !Number.isInteger(actual)
    || actual < 1
    || !metric
    || selection.candidateKey !== `prony:${actual}`
    || selection.actualTermCount !== actual
  ) return null;
  const parameterItems = stage.scalar_results
    .filter((item) =>
      item.key === "prony_equilibrium_modulus"
      || item.key.startsWith("prony_g_ratio_")
      || item.key.startsWith("prony_relaxation_time_")
    )
    .map((item) => ({
      name: item.key,
      value: item.value,
      unit: item.unit,
      lower: null,
      upper: null,
    }));
  const independentValues = stage.series.find(
    (item) => item.quantity === independentQuantity,
  )?.values.filter(Number.isFinite);
  if (!parameterItems.length || !independentValues || independentValues.length < 2) return null;
  return {
    candidate_key: `prony:${actual}`,
    mode: "single",
    primary_law: "generalized_maxwell",
    secondary_law: null,
    primary_weight: null,
    parameter_sets: [{ law: "generalized_maxwell", parameters: parameterItems }],
    fit_minimum: Math.min(...independentValues),
    fit_maximum: Math.max(...independentValues),
    extrapolation_maximum: null,
    extrapolation_policy: "observed_only",
    metric_definition: "normalized_rmse",
    metric_value: metric.value,
    requested_term_policy: String(step.options.selection_mode ?? ""),
    actual_term_count: actual,
    selection_reason: selection.reason.trim(),
    warning_acknowledged: selection.warningAcknowledged,
  };
}

function titleCase(value: string): string {
  return value.replaceAll("_", "-");
}

export function fitDecisionIdentityLabel(
  selection: Pick<
    FitDecisionSelection,
    "mode" | "primaryLaw" | "secondaryLaw" | "primaryWeight" | "actualTermCount"
  >,
): string {
  if (selection.actualTermCount !== undefined) {
    return `${selection.actualTermCount}-term Generalized Maxwell`;
  }
  if (selection.mode === "blend") {
    const primaryPercent = Math.round((selection.primaryWeight ?? 0) * 100);
    return `${titleCase(selection.primaryLaw)} + ${titleCase(selection.secondaryLaw ?? "")} ${primaryPercent}/${100 - primaryPercent}`;
  }
  return titleCase(selection.primaryLaw);
}
