import type {
  CommonCurveStage,
  CommonProcessingFitDecision,
  CommonProcessingOutputResponse,
  CommonProcessingPreview,
  CommonProcessingStep,
} from "./common-processing-contracts";
import type { CommonExactRevisionPin } from "./exact-revision-contracts";
import {
  fitDecisionIdentityLabel,
  hardeningCandidateWarning,
  type FitDecisionSelection,
} from "./fit-decision-contract";

export interface ExactFitPlotData {
  /** The persisted true-plastic-strain samples paired with observations. */
  observedX: number[];
  /** The persisted true-stress observations, in Pa. */
  observed: number[];
  /** The persisted true-plastic-strain samples paired with the selected response. */
  selectedX: number[];
  /** The persisted selected hardening response, in Pa. */
  selected: number[];
  xUnit: string;
  stressUnit: string;
  selectedQuantity: string;
}

const PLOT_DATA_ERROR = "Saved Fit result is missing true plastic strain, true stress, or selected hardening series with matching units";

type PersistedSeriesPair = {
  x: number[];
  y: number[];
  xUnit: string;
  yUnit: string;
};

function lastPersistedSeriesPair(
  stages: CommonCurveStage[],
  yQuantity: string,
): PersistedSeriesPair | undefined {
  let last: PersistedSeriesPair | undefined;
  for (const stage of stages) {
    if (!stage || !Array.isArray(stage.series)) throw new Error(PLOT_DATA_ERROR);
    const xSeries = stage.series.filter((item) => item.quantity === "strain.true_plastic");
    const ySeries = stage.series.filter((item) => item.quantity === yQuantity);
    // A stage may legitimately contain only one half of a pair (the live
    // 7-point observed stage and 101-point selected stage are separate).  A
    // duplicate quantity in either stage, however, is ambiguous and cannot be
    // selected by ordinal or by client-side heuristics.
    if (xSeries.length > 1 || ySeries.length > 1) throw new Error(PLOT_DATA_ERROR);
    if (xSeries.length !== 1 || ySeries.length !== 1) continue;
    const x = xSeries[0];
    const y = ySeries[0];
    if (
      !Array.isArray(x.values)
      || !Array.isArray(y.values)
      || x.values.length < 2
      || x.values.length !== y.values.length
      || x.unit !== "1"
      || y.unit !== "Pa"
      || x.values.some((value) => !Number.isFinite(value))
      || y.values.some((value) => !Number.isFinite(value))
    ) {
      throw new Error(PLOT_DATA_ERROR);
    }
    last = { x: [...x.values], y: [...y.values], xUnit: x.unit, yUnit: y.unit };
  }
  return last;
}

/**
 * Returns only the persisted samples used by the metal Fit plot.  The helper
 * intentionally does not resample, smooth, or interpolate: a malformed or
 * incomplete saved document is rejected by the caller instead of receiving a
 * client-side curve fallback.
 */
export function exactFitPlotData(
  preview: CommonProcessingPreview,
  selection: FitDecisionSelection,
): ExactFitPlotData {
  const selectedQuantity = selection.mode === "blend"
    ? "stress.hardening.selected"
    : `stress.hardening.${selection.primaryLaw}`;
  const observed = lastPersistedSeriesPair(preview.stages, "stress.true");
  const selected = lastPersistedSeriesPair(preview.stages, selectedQuantity);
  if (!observed || !selected || observed.xUnit !== selected.xUnit || observed.yUnit !== selected.yUnit) {
    throw new Error(PLOT_DATA_ERROR);
  }
  return {
    observedX: observed.x,
    observed: observed.y,
    selectedX: selected.x,
    selected: selected.y,
    xUnit: observed.xUnit,
    stressUnit: observed.yUnit,
    selectedQuantity,
  };
}

type SavedFitDocument = {
  document_type?: unknown;
  document_version?: unknown;
  output_id?: unknown;
  source_processing_output?: CommonExactRevisionPin | null;
  source_processing_output_sha256?: unknown;
  source_document?: CommonExactRevisionPin;
  mapping_profile?: CommonExactRevisionPin;
  source_canonical_artifact_sha256?: unknown;
  steps?: CommonProcessingStep[];
  fit_decision?: CommonProcessingFitDecision | null;
  result?: {
    source_document_sha256?: unknown;
    mapping_profile_sha256?: unknown;
    independent_quantity?: unknown;
    stages?: CommonCurveStage[];
  };
};

function stableJson(value: unknown): string {
  return JSON.stringify(value, (_key, nested) => {
    if (!nested || typeof nested !== "object" || Array.isArray(nested)) return nested;
    return Object.fromEntries(Object.entries(nested as Record<string, unknown>).sort());
  });
}

const SUPPORTED_SAVED_FIT_DOCUMENT_VERSIONS = new Set(["1.3.0", "1.4.0", "1.5.0"]);
const CURRENT_SAVED_FIT_DOCUMENT_VERSION = "1.5.0";
const SHA256 = /^[0-9a-f]{64}$/;
const CURVE_KEY = /^[a-z][a-z0-9_.-]{0,127}$/;
const QUANTITY_SEMANTICS = /^[a-z][a-z0-9_.-]{0,159}$/;
const DECIMAL_TEXT = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$/;

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/**
 * Require the declared curve metadata added by processing-output v1.5 to
 * describe the exact persisted series.  The immutable outer document digest
 * is verified before this parser runs; these checks additionally prevent a
 * current document from being treated as a legacy series-only result.
 */
function currentCurveMetadataMatchesSeries(stage: CommonCurveStage): boolean {
  const definition = stage.curve_definition as unknown;
  if (
    typeof stage.curve_definition_sha256 !== "string"
    || !SHA256.test(stage.curve_definition_sha256)
    || !record(definition)
    || definition.definition_version !== "1.0.0"
    || !Array.isArray(definition.channels)
    || definition.channels.length < 2
    || definition.channels.length !== stage.series.length
    || !Array.isArray(definition.deviations)
  ) return false;

  const seriesByQuantity = new Map(stage.series.map((series) => [series.quantity, series]));
  if (seriesByQuantity.size !== stage.series.length) return false;
  const channelKeys = new Set<string>();
  let independentCount = 0;
  let dependentCount = 0;
  for (const value of definition.channels) {
    if (!record(value)) return false;
    const {
      key,
      label,
      quantity_semantics: quantity,
      axis_role: axisRole,
      unit_contract: unitContract,
      dimension,
      original_units: originalUnits,
      normalized_unit: normalizedUnit,
      display_unit: displayUnit,
      display_scale: displayScale,
      display_offset: displayOffset,
      value_basis: valueBasis,
    } = value;
    if (
      typeof key !== "string"
      || !CURVE_KEY.test(key)
      || channelKeys.has(key)
      || typeof label !== "string"
      || !label
      || typeof quantity !== "string"
      || !QUANTITY_SEMANTICS.test(quantity)
      || !["independent", "dependent", "auxiliary"].includes(String(axisRole))
      || !["common", "explicit_legacy"].includes(String(unitContract))
      || (unitContract === "common" ? typeof dimension !== "string" || !dimension : dimension !== null)
      || !Array.isArray(originalUnits)
      || originalUnits.length < 1
      || typeof normalizedUnit !== "string"
      || !normalizedUnit
      || typeof displayUnit !== "string"
      || !displayUnit
      || typeof displayScale !== "string"
      || !DECIMAL_TEXT.test(displayScale)
      || Number(displayScale) === 0
      || typeof displayOffset !== "string"
      || !DECIMAL_TEXT.test(displayOffset)
      || !["original", "normalized", "derived"].includes(String(valueBasis))
      || !originalUnits.every((unit) => record(unit)
        && typeof unit.unit === "string"
        && Boolean(unit.unit)
        && typeof unit.scale_to_normalized === "string"
        && DECIMAL_TEXT.test(unit.scale_to_normalized)
        && typeof unit.offset_to_normalized === "string"
        && DECIMAL_TEXT.test(unit.offset_to_normalized))
    ) return false;
    const series = seriesByQuantity.get(quantity);
    if (!series || series.unit !== normalizedUnit) return false;
    channelKeys.add(key);
    if (axisRole === "independent") independentCount += 1;
    if (axisRole === "dependent") dependentCount += 1;
  }
  return independentCount >= 1 && dependentCount >= 1;
}

export async function readVerifiedExactOutput(
  result: { data: { blob: Blob } },
  expectedSha256: string,
): Promise<string> {
  const bytes = await result.data.blob.arrayBuffer();
  if (!globalThis.crypto?.subtle) {
    throw new Error("Exact saved Fit verification is unavailable in this browser");
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  const actual = Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
  if (actual !== expectedSha256) {
    throw new Error("Exact saved Fit content digest does not match its pinned revision");
  }
  const text = new TextDecoder().decode(bytes);
  const parsed = JSON.parse(text) as SavedFitDocument;
  if (parsed.document_version === CURRENT_SAVED_FIT_DOCUMENT_VERSION) {
    const stages = parsed.result?.stages;
    if (!Array.isArray(stages)) {
      throw new Error("Saved Fit result has invalid current curve metadata");
    }
    for (const stage of stages) {
      if (
        typeof stage.curve_definition_sha256 !== "string"
        || !SHA256.test(stage.curve_definition_sha256)
        || !record(stage.curve_definition)
      ) {
        throw new Error("Saved Fit result has invalid current curve metadata");
      }
      const definitionDigest = await globalThis.crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(stableJson(stage.curve_definition)),
      );
      const definitionSha256 = Array.from(new Uint8Array(definitionDigest), (value) =>
        value.toString(16).padStart(2, "0"),
      ).join("");
      if (definitionSha256 !== stage.curve_definition_sha256) {
        throw new Error("Saved Fit result curve definition digest does not match its metadata");
      }
    }
  }
  return text;
}

export function parseExactSavedFitOutput(
  text: string,
  output: CommonProcessingOutputResponse,
  processSource: CommonProcessingOutputResponse,
): { preview: CommonProcessingPreview; selection: FitDecisionSelection | null } {
  const parsed = JSON.parse(text) as SavedFitDocument;
  const exactPin = (
    left: CommonExactRevisionPin | null | undefined,
    right: CommonExactRevisionPin | null | undefined,
  ) => Boolean(
    left
      && right
      && left.aggregate_id === right.aggregate_id
      && left.revision_id === right.revision_id,
  );
  if (
    parsed.document_type !== "cmp.processing-output"
    || typeof parsed.document_version !== "string"
    || !SUPPORTED_SAVED_FIT_DOCUMENT_VERSIONS.has(parsed.document_version)
    || parsed.output_id !== output.processing_output_id
    || !exactPin(parsed.source_document, output.source_document)
    || !exactPin(parsed.mapping_profile, output.mapping_profile)
    || !exactPin(parsed.source_processing_output, output.source_processing_output)
    || parsed.source_processing_output_sha256 !== output.source_processing_output_sha256
    || parsed.source_canonical_artifact_sha256 !== output.source_canonical_artifact_sha256
    || !parsed.steps
    || stableJson(parsed.steps) !== stableJson(output.steps)
    || !output.source_processing_output
    || !exactPin(output.source_processing_output, {
      aggregate_id: processSource.processing_output_id,
      revision_id: processSource.current_revision.id,
    })
    || output.source_processing_output_sha256 !== processSource.output_sha256
    || !exactPin(output.source_document, processSource.source_document)
    || output.source_document_sha256 !== processSource.source_document_sha256
    || !exactPin(output.mapping_profile, processSource.mapping_profile)
    || output.mapping_profile_sha256 !== processSource.mapping_profile_sha256
    || output.independent_quantity !== processSource.independent_quantity
    || stableJson(processSource.steps) !== stableJson(output.steps.slice(0, -1))
    || processSource.stage_count !== output.stage_count - 1
    || parsed.result?.source_document_sha256 !== output.source_document_sha256
    || parsed.result?.mapping_profile_sha256 !== output.mapping_profile_sha256
    || parsed.result?.independent_quantity !== output.independent_quantity
  ) {
    throw new Error("Saved Fit result failed exact source or step validation");
  }
  const stages = parsed.result?.stages;
  if (!Array.isArray(stages) || stages.length !== output.stage_count) {
    throw new Error("Saved Fit result has an invalid stage count");
  }
  if (
    parsed.document_version === CURRENT_SAVED_FIT_DOCUMENT_VERSION
    && stages.some((stage) => !currentCurveMetadataMatchesSeries(stage))
  ) {
    throw new Error("Saved Fit result has invalid current curve metadata");
  }
  const expectedMethods = [
    { method_id: "mapping", method_version: "1.0.0" },
    ...output.steps.map((step) => ({ method_id: step.method_id, method_version: step.method_version })),
  ];
  const finiteArray = (values: unknown): values is number[] =>
    Array.isArray(values)
    && values.length > 0
    && values.every((value) => typeof value === "number" && Number.isFinite(value));
  const finiteOrNullArray = (values: unknown): values is Array<number | null> =>
    Array.isArray(values)
    && values.length > 0
    && values.every((value) => value === null || (typeof value === "number" && Number.isFinite(value)));
  const finiteArrayAllowEmpty = (values: unknown): values is number[] =>
    Array.isArray(values)
    && values.every((value) => typeof value === "number" && Number.isFinite(value));
  stages.forEach((stage, index) => {
    const expected = expectedMethods[index];
    if (
      !stage
      || !expected
      || stage.ordinal !== index
      || stage.method_id !== expected.method_id
      || stage.method_version !== expected.method_version
      || !Number.isInteger(stage.point_count)
      || stage.point_count < 2
    ) {
      throw new Error("Saved Fit result stage identity is invalid");
    }
    if (!Array.isArray(stage.series) || stage.series.length < 2) {
      throw new Error("Saved Fit result stage series are missing");
    }
    stage.series.forEach((series) => {
      if (
        !series.quantity
        || !series.unit
        || !Array.isArray(series.values)
        || series.values.length !== stage.point_count
        || series.values.some((value) => !Number.isFinite(value))
      ) {
        throw new Error("Saved Fit result contains invalid series evidence");
      }
    });
    if (
      !Array.isArray(stage.scalar_results)
      || stage.scalar_results.some((item) =>
        !item
        || typeof item.key !== "string"
        || typeof item.quantity_semantics !== "string"
        || typeof item.unit !== "string"
        || typeof item.value !== "number"
        || !Number.isFinite(item.value))
    ) {
      throw new Error("Saved Fit result scalar evidence is invalid");
    }
    if (!Array.isArray(stage.fit_candidates)) {
      throw new Error("Saved Fit result candidate evidence is missing");
    }
    const candidateFamilies = new Set<string>();
    let residualLength: number | undefined;
    stage.fit_candidates.forEach((candidate) => {
      const blendCandidate = typeof candidate?.family === "string" && candidate.family.includes("+");
      if (
        !candidate
        || typeof candidate.family !== "string"
        || !candidate.family
        || candidateFamilies.has(candidate.family)
        || !finiteArray(candidate.response)
        || !finiteArray(candidate.residual)
        || !finiteOrNullArray(candidate.tangent)
        || candidate.response.length !== stage.point_count
        || candidate.tangent.length !== stage.point_count
        || (residualLength !== undefined && candidate.residual.length !== residualLength)
        || !Array.isArray(candidate.parameter_names)
        || (!candidate.parameter_names.length && !blendCandidate)
        || candidate.parameter_names.some((value) => typeof value !== "string" || !value)
        || new Set(candidate.parameter_names).size !== candidate.parameter_names.length
        || !Array.isArray(candidate.parameter_units)
        || candidate.parameter_units.length !== candidate.parameter_names.length
        || candidate.parameter_units.some((value) => typeof value !== "string" || !value)
        || (
          blendCandidate
            ? ![candidate.lower, candidate.initial, candidate.fitted, candidate.upper].every(
              (values) => Array.isArray(values)
                && values.every((value) => typeof value === "number" && Number.isFinite(value)),
            )
            : !finiteArray(candidate.lower)
              || !finiteArray(candidate.initial)
              || !finiteArray(candidate.fitted)
              || !finiteArray(candidate.upper)
        )
        || candidate.lower.length !== candidate.parameter_names.length
        || candidate.initial.length !== candidate.parameter_names.length
        || candidate.fitted.length !== candidate.parameter_names.length
        || candidate.upper.length !== candidate.parameter_names.length
        || [
          candidate.rmse_pa,
          candidate.relative_rmse,
          candidate.objective,
          candidate.scipy_cost,
          candidate.jacobian_tolerance,
        ].some((value) => typeof value !== "number" || !Number.isFinite(value))
        || typeof candidate.convergence !== "boolean"
        || !Number.isInteger(candidate.nfev)
        || candidate.nfev < 0
        || !Array.isArray(candidate.active_bound)
        || candidate.active_bound.some((value) => typeof value !== "string")
        || !Number.isInteger(candidate.jacobian_rank)
        || candidate.jacobian_rank < 0
        || (
          candidate.jacobian_condition !== null
          && (typeof candidate.jacobian_condition !== "number" || !Number.isFinite(candidate.jacobian_condition))
        )
        || typeof candidate.identifiability !== "string"
        || typeof candidate.uncertainty !== "string"
        || (!blendCandidate && !finiteArray(candidate.objective_history))
        || (blendCandidate && !finiteArrayAllowEmpty(candidate.objective_history))
        || (candidate.optimizer_status !== undefined && !Number.isInteger(candidate.optimizer_status))
        || (candidate.optimizer_message !== undefined && typeof candidate.optimizer_message !== "string")
      ) {
        throw new Error("Saved Fit result candidate evidence is invalid");
      }
      residualLength ??= candidate.residual.length;
      candidateFamilies.add(candidate.family);
    });
  });
  const final = stages.at(-1);
  if (!final || final.method_id !== "metal.hardening_fit_extrapolate" || !parsed.fit_decision) {
    throw new Error("Saved Fit result has no exact hardening decision");
  }
  const decision = parsed.fit_decision;
  if (
    (decision.mode !== "single" && decision.mode !== "blend")
    || typeof decision.candidate_key !== "string"
    || typeof decision.primary_law !== "string"
    || (decision.secondary_law !== null && typeof decision.secondary_law !== "string")
    || (
      decision.primary_weight !== null
      && (typeof decision.primary_weight !== "number" || !Number.isFinite(decision.primary_weight))
    )
    || !Array.isArray(decision.parameter_sets)
    || typeof decision.fit_minimum !== "number"
    || !Number.isFinite(decision.fit_minimum)
    || typeof decision.fit_maximum !== "number"
    || !Number.isFinite(decision.fit_maximum)
    || (
      decision.extrapolation_maximum !== null
      && (typeof decision.extrapolation_maximum !== "number" || !Number.isFinite(decision.extrapolation_maximum))
    )
    || typeof decision.extrapolation_policy !== "string"
    || typeof decision.metric_definition !== "string"
    || typeof decision.metric_value !== "number"
    || !Number.isFinite(decision.metric_value)
    || typeof decision.selection_reason !== "string"
    || typeof decision.warning_acknowledged !== "boolean"
  ) {
    throw new Error("Saved Fit decision evidence is malformed");
  }
  const finalCandidates = final.fit_candidates ?? [];
  const candidateByFamily = new Map(finalCandidates.map((candidate) => [candidate.family, candidate]));
  const selectedCandidate = candidateByFamily.get(decision.candidate_key);
  const selectedLaws = decision.mode === "blend"
    ? [decision.primary_law, decision.secondary_law]
    : [decision.primary_law];
  if (
    !selectedCandidate
    || selectedLaws.some((law) => typeof law !== "string" || !candidateByFamily.has(law))
    || (
      decision.mode === "single"
      && (
        decision.secondary_law !== null
        || decision.primary_weight !== null
        || decision.candidate_key !== decision.primary_law
        || decision.parameter_sets.length !== 1
      )
    )
    || (
      decision.mode === "blend"
      && (
        !decision.secondary_law
        || decision.secondary_law === decision.primary_law
        || decision.primary_weight === null
        || decision.primary_weight <= 0
        || decision.primary_weight >= 1
        || decision.candidate_key !== `${decision.primary_law}+${decision.secondary_law}`
        || decision.parameter_sets.length !== 2
      )
    )
  ) {
    throw new Error("Saved Fit decision identity does not match candidate evidence");
  }
  decision.parameter_sets.forEach((parameterSet, index) => {
    const law = selectedLaws[index];
    const candidate = typeof law === "string" ? candidateByFamily.get(law) : undefined;
    if (!candidate || !parameterSet || parameterSet.law !== law || !Array.isArray(parameterSet.parameters)) {
      throw new Error("Saved Fit decision parameter identity is invalid");
    }
    const names = new Set(candidate.parameter_names);
    if (
      parameterSet.parameters.length !== candidate.parameter_names.length
      || parameterSet.parameters.some((parameter) => {
        const parameterIndex = parameter && typeof parameter.name === "string"
          ? candidate.parameter_names.indexOf(parameter.name)
          : -1;
        const fitted = parameterIndex >= 0 ? candidate.fitted[parameterIndex] : undefined;
        const lower = parameterIndex >= 0 ? candidate.lower[parameterIndex] : undefined;
        const upper = parameterIndex >= 0 ? candidate.upper[parameterIndex] : undefined;
        return (
          !parameter
          || typeof parameter.name !== "string"
          || !names.has(parameter.name)
          || typeof parameter.value !== "number"
          || !Number.isFinite(parameter.value)
          || typeof parameter.unit !== "string"
          || (
            parameter.lower !== null
            && (typeof parameter.lower !== "number" || !Number.isFinite(parameter.lower))
          )
          || (
            parameter.upper !== null
            && (typeof parameter.upper !== "number" || !Number.isFinite(parameter.upper))
          )
          || (
            fitted !== undefined
            && Math.abs(parameter.value - fitted) > Math.max(1e-10, Math.abs(fitted) * 1e-10)
          )
          || (
            parameter.lower !== null
            && lower !== undefined
            && Math.abs(parameter.lower - lower) > Math.max(1e-10, Math.abs(lower) * 1e-10)
          )
          || (
            parameter.upper !== null
            && upper !== undefined
            && Math.abs(parameter.upper - upper) > Math.max(1e-10, Math.abs(upper) * 1e-10)
          )
        );
      })
    ) {
      throw new Error("Saved Fit decision parameter evidence is invalid");
    }
  });
  const warningParts = selectedLaws
    .filter((law): law is string => typeof law === "string")
    .map((law) => hardeningCandidateWarning(law, Boolean(candidateByFamily.get(law)?.active_bound.length)))
    .filter((item): item is string => Boolean(item));
  const warning = [...new Set(warningParts)].join("; ") || undefined;
  if (warning && !decision.warning_acknowledged) {
    throw new Error("Saved Fit decision warning must be acknowledged");
  }
  // A saved Fit is exportable only when its persisted response contains the
  // real metal quantities used by the engineering graph.  Do this check
  // after decision identity validation so a missing/ambiguous selected series
  // cannot be hidden behind a fabricated client curve.
  const fitRange = `${decision.fit_minimum.toPrecision(3)}–${decision.fit_maximum.toPrecision(3)} measured; to ${decision.extrapolation_maximum?.toPrecision(3) ?? "declared limit"} extrapolated`;
  // Keep the numeric persisted bounds alongside the human selection label so
  // the Export-side Fit source can filter existing samples without parsing or
  // inventing a view range from rendered text.
  const selection: FitDecisionSelection & { fitMinimum: number; fitMaximum: number } = {
    candidateKey: decision.candidate_key,
    displayLabel: fitDecisionIdentityLabel({
      mode: decision.mode,
      primaryLaw: decision.primary_law,
      secondaryLaw: decision.secondary_law ?? undefined,
      primaryWeight: decision.primary_weight ?? undefined,
      actualTermCount: decision.actual_term_count ?? undefined,
    }),
    mode: decision.mode,
    primaryLaw: decision.primary_law,
    secondaryLaw: decision.secondary_law ?? undefined,
    primaryWeight: decision.primary_weight ?? undefined,
    actualTermCount: decision.actual_term_count ?? undefined,
    requestedTermPolicy: decision.requested_term_policy ?? undefined,
    reason: decision.selection_reason,
    warningAcknowledged: decision.warning_acknowledged,
    fitRange,
    warning,
    fitMinimum: decision.fit_minimum,
    fitMaximum: decision.fit_maximum,
  };
  exactFitPlotData(
    {
      execution_mode: "preview",
      promotable: false,
      source_document_sha256: String(parsed.result?.source_document_sha256),
      mapping_profile_sha256: String(parsed.result?.mapping_profile_sha256),
      independent_quantity: String(parsed.result?.independent_quantity),
      stages,
    },
    selection,
  );
  return {
    preview: {
      execution_mode: "preview",
      promotable: false,
      source_document_sha256: String(parsed.result?.source_document_sha256),
      mapping_profile_sha256: String(parsed.result?.mapping_profile_sha256),
      independent_quantity: String(parsed.result?.independent_quantity),
      stages,
    },
    selection: selectedCandidate ? selection : null,
  };
}
