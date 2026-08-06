import type {
  CommonCurveStage,
  CommonExactRevisionPin,
  CommonProcessingFitDecision,
  CommonProcessingOutputResponse,
  CommonProcessingPreview,
  CommonProcessingStep,
} from "./types";
import {
  fitDecisionIdentityLabel,
  hardeningCandidateWarning,
  type FitDecisionSelection,
} from "./modeling-fit-decision-contract";

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
  return new TextDecoder().decode(bytes);
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
    || parsed.document_version !== "1.3.0"
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
  const fitRange = `${decision.fit_minimum.toPrecision(3)}–${decision.fit_maximum.toPrecision(3)} measured; to ${decision.extrapolation_maximum?.toPrecision(3) ?? "declared limit"} extrapolated`;
  return {
    preview: {
      execution_mode: "preview",
      promotable: false,
      source_document_sha256: String(parsed.result?.source_document_sha256),
      mapping_profile_sha256: String(parsed.result?.mapping_profile_sha256),
      independent_quantity: String(parsed.result?.independent_quantity),
      stages,
    },
    selection: selectedCandidate
      ? {
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
      }
      : null,
  };
}
