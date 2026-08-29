import type { CanonicalTestDataDocumentResponse } from "../../test-data/contracts";
import type {
  CommonMappingProfileContent,
  CommonMappingProfileResponse,
  CommonProcessingStep,
  CommonProcessingWorkupOverride,
} from "./common-processing-contracts";
import { METAL_HARDENING_EQUATION_CONTRACT } from "./fit-decision-contract";

export type ModelingTrack = "metal" | "polymer" | "elastomer";

export const DEFAULT_PROFILE: CommonMappingProfileContent = {
  profile_key: "normalized-tensile",
  label: "Normalized tensile channels",
  independent_quantity: "strain.engineering",
  missing_data_policy: "drop_any",
  bindings: [
    {
      channel_key: "engineering_strain",
      target_quantity: "strain.engineering",
      accepted_normalized_units: ["1"],
      required: true,
      scale: 1,
      offset: 0,
    },
    {
      channel_key: "engineering_stress",
      target_quantity: "stress.engineering",
      accepted_normalized_units: ["Pa"],
      required: true,
      scale: 1,
      offset: 0,
    },
  ],
  attribute_bindings: [],
};

export const POLYMER_RELAXATION_PROFILE: CommonMappingProfileContent = {
  profile_key: "polymer-shear-relaxation",
  label: "Polymer shear relaxation channels",
  independent_quantity: "time",
  missing_data_policy: "drop_any",
  bindings: [
    {
      channel_key: "time_s",
      target_quantity: "time",
      accepted_normalized_units: ["s"],
      required: true,
      scale: 1,
      offset: 0,
    },
    {
      channel_key: "shear_modulus_mpa",
      target_quantity: "modulus.shear.relaxation",
      accepted_normalized_units: ["Pa"],
      required: true,
      scale: 1,
      offset: 0,
    },
  ],
  attribute_bindings: [],
};

export const POLYMER_DMA_PROFILE: CommonMappingProfileContent = {
  profile_key: "polymer-dma-frequency",
  label: "Polymer DMA storage/loss channels",
  independent_quantity: "frequency",
  missing_data_policy: "drop_any",
  bindings: [
    { channel_key: "frequency_hz", target_quantity: "frequency", accepted_normalized_units: ["Hz"], required: true, scale: 1, offset: 0 },
    { channel_key: "storage_modulus_pa", target_quantity: "modulus.shear.storage", accepted_normalized_units: ["Pa"], required: true, scale: 1, offset: 0 },
    { channel_key: "loss_modulus_pa", target_quantity: "modulus.shear.loss", accepted_normalized_units: ["Pa"], required: true, scale: 1, offset: 0 },
  ],
  attribute_bindings: [],
};

export const ELASTOMER_CURVE_PROFILE: CommonMappingProfileContent = {
  profile_key: "elastomer-test-mode-preparation",
  label: "Elastomer test-mode curve preparation",
  independent_quantity: "strain.engineering",
  missing_data_policy: "drop_any",
  bindings: [
    {
      channel_key: "engineering_strain",
      target_quantity: "strain.engineering",
      accepted_normalized_units: ["1"],
      required: true,
      scale: 1,
      offset: 0,
    },
    {
      channel_key: "engineering_stress",
      target_quantity: "stress.engineering",
      accepted_normalized_units: ["Pa"],
      required: true,
      scale: 1,
      offset: 0,
    },
  ],
  attribute_bindings: [],
};

export const ELASTOMER_PREPARATION_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
];

export const POLYMER_RELAXATION_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
  {
    method_id: "curve.crop",
    method_version: "1.0.0",
    options: { minimum: 0.01, maximum: 100 },
  },
  {
    method_id: "polymer.log_time_resample",
    method_version: "1.0.0",
    options: { start_time_s: 0.01, end_time_s: 100, count: 81, extrapolation: "reject" },
  },
  {
    method_id: "polymer.prony_fit_compare",
    method_version: "1.0.0",
    options: {
      time_quantity: "time",
      modulus_quantity: "modulus.shear.relaxation",
      candidate_term_counts: [1, 2, 3, 4],
      selection_mode: "automatic_bic",
      selected_term_count: 2,
      normalization_modulus_pa: 1000000000,
      minimum_relaxation_time_s: 0.0001,
      maximum_relaxation_time_s: 1000000,
      maximum_function_evaluations: 5000,
    },
  },
];

export const POLYMER_DMA_STEPS: CommonProcessingStep[] = [
  { method_id: "rows.sort_unique", method_version: "1.0.0", options: { duplicate_policy: "reject" } },
  {
    method_id: "polymer.dma_prony_fit_compare",
    method_version: "1.0.0",
    options: {
      frequency_quantity: "frequency",
      storage_modulus_quantity: "modulus.shear.storage",
      loss_modulus_quantity: "modulus.shear.loss",
      candidate_term_counts: [1, 2, 3, 4],
      selection_mode: "automatic_bic",
      selected_term_count: 2,
      normalization_modulus_pa: 1000000000,
      minimum_relaxation_time_s: 0.0001,
      maximum_relaxation_time_s: 1000000,
      maximum_function_evaluations: 5000,
    },
  },
];

export const METAL_TENSILE_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
  {
    method_id: "metal.elastic_modulus",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      method: "robust_huber",
      minimum_strain: 0.0002,
      maximum_strain: 0.002,
      manual_modulus_pa: 210000000000,
    },
  },
  {
    method_id: "metal.proof_stress",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      youngs_modulus_pa: 210000000000,
      offset_strain: 0.002,
      search_start: 0.002,
      search_end: 0.1,
    },
  },
  {
    method_id: "metal.necking_candidate",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      method: "peak_engineering_stress",
    },
  },
  {
    method_id: "metal.engineering_to_true_plastic",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      youngs_modulus_pa: 210000000000,
      necking_policy: "observed_full_domain",
      manual_necking_index: 1,
      negative_plastic_policy: "drop",
    },
  },
  {
    method_id: "metal.hardening_fit_extrapolate",
    method_version: "1.0.0",
    options: {
      equation_contract: METAL_HARDENING_EQUATION_CONTRACT,
      plastic_strain_quantity: "strain.true_plastic",
      stress_quantity: "stress.true",
      families: ["voce", "swift", "hockett_sherby", "ghosh"],
      fit_minimum_strain: 0,
      fit_maximum_strain: 0.1,
      extrapolation_maximum_strain: 1,
      output_point_count: 101,
      primary_family: "swift",
      secondary_family: "voce",
      primary_weight: 0.5,
      normalization_stress_pa: 100000000,
      maximum_function_evaluations: 5000,
    },
  },
];

export const PRONY_TERM_COUNTS = [1, 2, 3, 4, 5, 6, 8, 10] as const;

export function numberOption(step: CommonProcessingStep, key: string): number {
  const value = step.options[key];
  return typeof value === "number" ? value : Number(value ?? 0);
}

export type ModulusDisplayUnit = "GPa" | "MPa";

function modulusPaScale(unit: ModulusDisplayUnit): number {
  return unit === "GPa" ? 1e9 : 1e6;
}

export function modulusDisplayUnit(value: unknown): ModulusDisplayUnit {
  return value === "MPa" ? "MPa" : "GPa";
}

export function manualModulusPascals(value: number, unit: ModulusDisplayUnit): number {
  return value * modulusPaScale(unit);
}

export function manualModulusDisplayValue(valuePa: number, unit: ModulusDisplayUnit): number {
  return valuePa / modulusPaScale(unit);
}

const UI_ONLY_PROCESS_OPTION_KEYS = new Set([
  "manual_modulus_unit", "manual_modulus_reason", "manual_necking_unit", "manual_necking_reason",
]);

export function serverProcessingSteps(steps: CommonProcessingStep[]): CommonProcessingStep[] {
  return steps.map((step) => ({
    ...step,
    options: Object.fromEntries(Object.entries(step.options).filter(([key]) => !UI_ONLY_PROCESS_OPTION_KEYS.has(key))),
  }));
}

function toeAcknowledgementContext(step: unknown): string | null {
  if (!step || typeof step !== "object") return null;
  const candidate = step as Partial<CommonProcessingStep>;
  if (candidate.method_id !== "tensile.toe_zero_intercept" || !candidate.options || typeof candidate.options !== "object") return null;
  return JSON.stringify([
    candidate.method_version,
    candidate.options.strain_quantity,
    candidate.options.stress_quantity,
    candidate.options.minimum_strain,
    candidate.options.maximum_strain,
    candidate.options.equipment_compliance,
  ]);
}

export function parsedStepArray(value: string): unknown[] | null {
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function normalizeToeWarningAcknowledgement(previous: string, next: string): string {
  const previousSteps = parsedStepArray(previous);
  const nextSteps = parsedStepArray(next);
  if (!nextSteps) return next;
  const previousToeContexts = (previousSteps ?? [])
    .map(toeAcknowledgementContext)
    .filter((context): context is string => context !== null);
  let toeIndex = 0;
  let changed = false;
  const normalized = nextSteps.map((step) => {
    const context = toeAcknowledgementContext(step);
    if (context === null) return step;
    const previousContext = previousToeContexts[toeIndex];
    toeIndex += 1;
    const candidate = step as CommonProcessingStep;
    if (candidate.options.warning_acknowledged !== true || previousContext === context) return step;
    changed = true;
    return { ...candidate, options: { ...candidate.options, warning_acknowledged: false } };
  });
  return changed ? JSON.stringify(normalized, null, 2) : next;
}

export function workupOverridesFromSteps(steps: CommonProcessingStep[]): CommonProcessingWorkupOverride[] {
  const overrides: CommonProcessingWorkupOverride[] = [];
  const modulus = steps.find((step) => step.method_id === "metal.elastic_modulus");
  if (modulus?.options.method === "manual") {
    const original_unit = modulusDisplayUnit(modulus.options.manual_modulus_unit);
    const canonical_value = numberOption(modulus, "manual_modulus_pa");
    overrides.push({
      kind: "youngs_modulus",
      original_value: manualModulusDisplayValue(canonical_value, original_unit),
      original_unit,
      canonical_value,
      canonical_unit: "Pa",
      reason: String(modulus.options.manual_modulus_reason ?? "").trim(),
    });
  }
  const workup = steps.find((step) => step.method_id === "metal.engineering_to_true_plastic");
  if (workup?.options.necking_policy === "manual_index") {
    const selectedIndex = numberOption(workup, "manual_necking_index");
    overrides.push({
      kind: "necking_boundary",
      original_value: selectedIndex,
      original_unit: String(workup.options.manual_necking_unit ?? "observed-point-index"),
      canonical_value: selectedIndex,
      canonical_unit: "observed-point-index",
      reason: String(workup.options.manual_necking_reason ?? "").trim(),
    });
  }
  return overrides;
}

export function defaultOptions(methodId: string): Record<string, unknown> {
  const options: Record<string, Record<string, unknown>> = {
    "rows.sort_unique": { duplicate_policy: "reject" },
    "curve.crop": { minimum: 0, maximum: 0.001 },
    "curve.scale_shift": { quantity: "stress.engineering", scale: 1, offset: 0 },
    "curve.resample_linear": { start: 0, end: 0.001, count: 21, extrapolation: "reject" },
    "curve.moving_average": { quantity: "stress.engineering", window: 3 },
    "curve.savitzky_golay": { quantity: "stress.engineering", window: 5, polynomial_order: 2 },
    "curve.smoothing_spline": { quantity: "stress.engineering", smoothing_factor: 0 },
    "tensile.toe_zero_intercept": {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      minimum_strain: 0,
      maximum_strain: 0.002,
      equipment_compliance: "not_provided",
      warning_acknowledged: false,
    },
    "metal.elastic_modulus": {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      method: "robust_huber",
      minimum_strain: 0.0002,
      maximum_strain: 0.002,
      manual_modulus_pa: 210000000000,
    },
    "metal.proof_stress": {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      youngs_modulus_pa: 210000000000,
      offset_strain: 0.002,
      search_start: 0.002,
      search_end: 0.1,
    },
    "metal.necking_candidate": {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      method: "peak_engineering_stress",
    },
    "metal.engineering_to_true_plastic": {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      youngs_modulus_pa: 210000000000,
      necking_policy: "observed_full_domain",
      manual_necking_index: 1,
      negative_plastic_policy: "drop",
    },
    "metal.hardening_fit_extrapolate": {
      equation_contract: METAL_HARDENING_EQUATION_CONTRACT,
      plastic_strain_quantity: "strain.true_plastic",
      stress_quantity: "stress.true",
      families: ["voce", "swift", "hockett_sherby", "ghosh"],
      fit_minimum_strain: 0,
      fit_maximum_strain: 0.1,
      extrapolation_maximum_strain: 1,
      output_point_count: 101,
      primary_family: "swift",
      secondary_family: "voce",
      primary_weight: 0.5,
      normalization_stress_pa: 100000000,
      maximum_function_evaluations: 5000,
    },
    "polymer.log_time_resample": {
      start_time_s: 0.01,
      end_time_s: 100,
      count: 81,
      extrapolation: "reject",
    },
    "polymer.prony_fit_compare": {
      time_quantity: "time",
      modulus_quantity: "modulus.shear.relaxation",
      candidate_term_counts: [1, 2, 3, 4],
      selection_mode: "automatic_bic",
      selected_term_count: 2,
      normalization_modulus_pa: 10000000,
      minimum_relaxation_time_s: 0.0001,
      maximum_relaxation_time_s: 1000000,
      maximum_function_evaluations: 5000,
    },
    "polymer.dma_prony_fit_compare": {
      frequency_quantity: "frequency",
      storage_modulus_quantity: "modulus.shear.storage",
      loss_modulus_quantity: "modulus.shear.loss",
      candidate_term_counts: [1, 2, 3, 4],
      selection_mode: "automatic_bic",
      selected_term_count: 2,
      normalization_modulus_pa: 1000000000,
      minimum_relaxation_time_s: 0.0001,
      maximum_relaxation_time_s: 1000000,
      maximum_function_evaluations: 5000,
    },
  };
  return options[methodId] ?? {};
}

export function documentMatchesTrack(
  item: CanonicalTestDataDocumentResponse,
  track: ModelingTrack,
): boolean {
  const quantities = item.channels.map((channel) => channel.quantity_semantics.toLowerCase());
  const hasQuantity = (suffix: string) => quantities.some((quantity) => quantity === suffix || quantity.endsWith(`.${suffix}`));
  if (track === "polymer") {
    const relaxation = hasQuantity("time.elapsed") && hasQuantity("modulus.shear.relaxation");
    const dma = hasQuantity("frequency.cyclic")
      && hasQuantity("modulus.shear.storage")
      && hasQuantity("modulus.shear.loss");
    return relaxation || dma;
  }
  const hasStressStrain = hasQuantity("strain.engineering") && hasQuantity("stress.engineering");
  if (!hasStressStrain) return false;
  const method = item.method.trim().toLowerCase();
  if (track === "metal") return method === "tensile" || method === "uniaxial tensile reference method";
  return ["uniaxial", "planar", "biaxial"].some((mode) => method === mode || method === `${mode} tension`);
}

export function documentMatchesDataTrack(
  item: CanonicalTestDataDocumentResponse,
  track: ModelingTrack,
): boolean {
  if (documentMatchesTrack(item, track)) return true;
  const quantities = new Set(item.channels.map((channel) => channel.quantity_semantics.toLowerCase()));
  if (track === "polymer") {
    return quantities.has("physics.temperature")
      && quantities.has("frequency.cyclic")
      && quantities.has("mechanics.modulus.storage")
      && quantities.has("mechanics.modulus.loss");
  }
  if (track === "metal") {
    return quantities.has("mechanics.strain.minor")
      && quantities.has("mechanics.strain.major");
  }
  return false;
}

export function profileMatchesTrack(
  item: CommonMappingProfileResponse,
  track: ModelingTrack,
): boolean {
  const content = item.content;
  if (track === "metal") {
    return content.independent_quantity.includes("strain")
      && content.bindings.some((binding) => binding.target_quantity.includes("stress"));
  }
  if (track === "polymer") {
    return ["time", "frequency"].includes(content.independent_quantity)
      || content.profile_key.includes("polymer");
  }
  return content.profile_key.includes("elastomer");
}

export function documentIsPolymerDma(item: CanonicalTestDataDocumentResponse | undefined): boolean {
  if (!item) return false;
  const quantities = new Set(item.channels.map((channel) => channel.quantity_semantics.toLowerCase()));
  return quantities.has("frequency.cyclic")
    && quantities.has("modulus.shear.storage")
    && quantities.has("modulus.shear.loss");
}

export function isFitMethod(methodId: string): boolean {
  return methodId.includes("hardening_fit")
    || methodId.includes("prony_fit")
    || methodId.includes("fit_compare");
}

export function methodDisplayName(methodId: string | undefined): string {
  if (!methodId || methodId === "mapping") return "Mapped source";
  const explicit: Record<string, string> = {
    "tensile.toe_zero_intercept": "Tensile toe compensation",
    "metal.elastic_modulus": "Young's modulus",
    "metal.proof_stress": "Proof stress",
    "metal.necking_candidate": "Necking candidate",
    "metal.engineering_to_true_plastic": "True plastic workup",
    "metal.hardening_fit_extrapolate": "Hardening candidates",
    "polymer.log_time_resample": "Log-time resampling",
    "polymer.prony_fit_compare": "Prony candidates",
    "polymer.dma_prony_fit_compare": "DMA Prony candidates",
  };
  if (explicit[methodId]) return explicit[methodId];
  return methodId
    .split(".")
    .at(-1)!
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
