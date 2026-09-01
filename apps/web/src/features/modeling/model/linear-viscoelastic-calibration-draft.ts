import type {
  DirectLinearViscoelasticPlanRequest,
  LinearViscoelasticAvailability,
  LinearViscoelasticAvailabilityMap,
  LinearViscoelasticCandidateScopeMode,
  LinearViscoelasticParameterBound,
  LinearViscoelasticPlanContent,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticPointDisposition,
  LinearViscoelasticPointPartition,
  LinearViscoelasticWeights,
  ProcessedLinearViscoelasticPlanRequest,
} from "./linear-viscoelastic-calibration-contracts";

export type PolymerFitSourceChoice = "test-data" | "processing-output";
export type PolymerSourceCurveMode = "relaxation" | "dma" | "unknown";
export type PolymerDraftAvailability = LinearViscoelasticAvailability | "";

export interface PolymerSourceSnapshot {
  mode: PolymerSourceCurveMode;
  pointCount: number;
  channels: Array<{ key: string; quantity: string; unit: string; values: Array<number | null> }>;
  temperatures: number[];
  conditionTemperature: number | null;
}

export interface PolymerOptimizerDraft {
  ftol: string;
  xtol: string;
  gtol: string;
  max_nfev: string;
}

export interface PolymerCalibrationDraft {
  selectedTemperature: string;
  partitions: Array<LinearViscoelasticPointPartition | null>;
  candidateScopeMode: LinearViscoelasticCandidateScopeMode;
  termCounts: number[];
  bounds: Record<string, LinearViscoelasticParameterBound[]>;
  availability: Record<typeof POLYMER_AVAILABILITY_FIELDS[number], PolymerDraftAvailability>;
  weights: LinearViscoelasticWeights;
  optimizer: PolymerOptimizerDraft;
  setupName: string;
  overrideReason: string;
  changeReason: string;
}

export interface PolymerCalibrationGovernanceContext {
  material: { id: string; revisionId: string };
  materialState: { id: string; revisionId: string };
  inputMode: "relaxation" | "dma" | "dma_frequency_master_curve";
  basedOn?: { planId: string; planRevisionId: string };
}

export interface PolymerCalibrationSourceContext {
  sourceChoice: PolymerFitSourceChoice;
  directAvailable: boolean;
  processedAvailable: boolean;
  processedCalibrationObservationCount: number;
  directSource?: { id: string; revisionId: string };
  processingSource?: { id: string; revisionId: string };
  snapshot: PolymerSourceSnapshot;
}

export interface PolymerCalibrationBlockers {
  direct: string[];
  model: string[];
  solver: string[];
}

export const POLYMER_AVAILABILITY_FIELDS = ["ramp", "sweep", "preconditioning", "linear_range"] as const;
export const EMPTY_POLYMER_AVAILABILITY: Record<typeof POLYMER_AVAILABILITY_FIELDS[number], PolymerDraftAvailability> = {
  ramp: "",
  sweep: "",
  preconditioning: "",
  linear_range: "",
};
export const EMPTY_POLYMER_OPTIMIZER: PolymerOptimizerDraft = {
  ftol: "",
  xtol: "",
  gtol: "",
  max_nfev: "",
};
export const EMPTY_POLYMER_WEIGHTS: LinearViscoelasticWeights = {
  relaxation_weight: "",
  dma_storage_weight: "",
  dma_loss_weight: "",
  relaxation_scale_pa: "",
  dma_storage_scale_pa: "",
  dma_loss_scale_pa: "",
  q_rule_version: "equal_per_point@1.0.0",
};

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function numberArray(value: unknown): Array<number | null> {
  return Array.isArray(value) ? value.map(numberValue) : [];
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : value === undefined || value === null ? "" : String(value);
}

export function polymerSourceSnapshot(
  document: Record<string, unknown> | null | undefined,
): PolymerSourceSnapshot {
  const channels = Array.isArray(document?.channels) ? document.channels : [];
  const mapped = channels.flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const channel = value as Record<string, unknown>;
    return [{
      key: stringValue(channel.key),
      quantity: stringValue(channel.quantity_semantics),
      unit: stringValue(channel.normalized_unit),
      values: numberArray(channel.normalized_values),
    }];
  });
  const hasRelaxation = mapped.some((channel) => channel.quantity.includes("time.elapsed"))
    && mapped.some((channel) => channel.quantity.includes("modulus.shear.relaxation"));
  const hasDma = mapped.some((channel) => channel.quantity.includes("physics.temperature"))
    && mapped.some((channel) => channel.quantity.includes("frequency.cyclic"))
    && mapped.some((channel) => channel.quantity.includes("modulus.shear.storage") || channel.quantity.includes("modulus.storage"))
    && mapped.some((channel) => channel.quantity.includes("modulus.shear.loss") || channel.quantity.includes("modulus.loss"));
  const conditionItems = Array.isArray(document?.conditions) ? document.conditions : [];
  const conditionTemperature = conditionItems.flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const item = value as Record<string, unknown>;
    const quantity = stringValue(item.quantity_semantics);
    const normalizedUnit = stringValue(item.normalized_unit);
    const normalized = numberValue(item.normalized_value);
    return normalized !== null && normalizedUnit === "K" && quantity.includes("temperature") ? [normalized] : [];
  })[0] ?? null;
  const temperatureChannel = mapped.find((channel) => channel.quantity.includes("physics.temperature"));
  const pointCount = mapped.length ? Math.max(...mapped.map((channel) => channel.values.length)) : 0;
  return {
    mode: hasRelaxation ? "relaxation" : hasDma ? "dma" : "unknown",
    pointCount,
    channels: mapped,
    temperatures: [...new Set((temperatureChannel?.values ?? []).flatMap((value) => value === null ? [] : [value]))],
    conditionTemperature,
  };
}

export function buildPolymerCalibrationSourceSummary(
  document: Record<string, unknown> | null | undefined,
): Pick<PolymerSourceSnapshot, "mode" | "pointCount" | "temperatures"> {
  const snapshot = polymerSourceSnapshot(document);
  return { mode: snapshot.mode, pointCount: snapshot.pointCount, temperatures: snapshot.temperatures };
}

export function linearViscoelasticPlanSourceKey(content: LinearViscoelasticPlanContent): string {
  if (content.input_semantics?.source_kind === "processing_output") {
    return `processing-output:${content.processing_output?.id ?? ""}:${content.processing_output?.revision_id ?? ""}`;
  }
  return `test-data:${content.test_data?.id ?? ""}:${content.test_data?.revision_id ?? ""}`;
}

export function polymerSnapshotChannel(
  snapshot: PolymerSourceSnapshot,
  includes: string,
): PolymerSourceSnapshot["channels"][number] | undefined {
  return snapshot.channels.find((item) => item.quantity.includes(includes));
}

export function blankPolymerBounds(termCount: number): LinearViscoelasticParameterBound[] {
  return [
    { name: "G_inf_pa", lower: NaN, start: NaN, upper: NaN, unit: "Pa", transform: "ln" },
    ...Array.from({ length: termCount }, (_, index) => ({ name: `G_${index + 1}_pa`, lower: NaN, start: NaN, upper: NaN, unit: "Pa" as const, transform: "ln" as const })),
    ...Array.from({ length: termCount }, (_, index) => ({ name: `tau_${index + 1}_s`, lower: NaN, start: NaN, upper: NaN, unit: "s" as const, transform: "ln" as const })),
  ];
}

export function polymerBoundsStartVectors(
  termCounts: number[],
  bounds: Record<string, LinearViscoelasticParameterBound[]>,
): Record<string, number[][]> {
  return Object.fromEntries(
    termCounts.map((term) => [String(term), [[...(bounds[String(term)] ?? []).map((item) => item.start)]]]),
  ) as Record<string, number[][]>;
}

export function finitePolymerDraftValue(value: string): number | null {
  return value.trim() && Number.isFinite(Number(value)) ? Number(value) : null;
}

export function polymerPronyParameterCount(termCount: number): number {
  return 1 + (2 * termCount);
}

export function activePolymerDirectPartitionCounts(
  draft: PolymerCalibrationDraft,
  snapshot: PolymerSourceSnapshot,
) {
  if (snapshot.mode !== "dma" || !draft.selectedTemperature) {
    return countPolymerPartitions(draft.partitions);
  }
  const temperature = polymerSnapshotChannel(snapshot, "physics.temperature");
  const selected = Number(draft.selectedTemperature);
  if (!temperature || !Number.isFinite(selected)) return countPolymerPartitions(draft.partitions);
  return countPolymerPartitions(draft.partitions.map((partition, ordinal) => (
    temperature.values[ordinal] === selected ? partition : "EXCLUDED"
  )));
}

export function polymerCalibrationObservationCount(
  draft: PolymerCalibrationDraft,
  source: PolymerCalibrationSourceContext,
): number {
  if (source.sourceChoice === "processing-output") {
    return source.processedCalibrationObservationCount;
  }
  const calibrationRows = activePolymerDirectPartitionCounts(draft, source.snapshot).calibration;
  return calibrationRows * (source.snapshot.mode === "dma" ? 2 : 1);
}

export function maximumSupportedPronyTermCount(observationCount: number): number {
  return Math.max(0, Math.min(10, Math.floor((observationCount - 1) / 2)));
}

export function automaticPolymerTermCounts(observationCount: number): number[] {
  return Array.from({ length: maximumSupportedPronyTermCount(observationCount) }, (_, index) => index + 1);
}

export function createPolymerCalibrationDraft(snapshot: PolymerSourceSnapshot): PolymerCalibrationDraft {
  return {
    selectedTemperature: snapshot.mode === "relaxation" && snapshot.conditionTemperature !== null
      ? String(snapshot.conditionTemperature)
      : "",
    partitions: Array.from({ length: snapshot.pointCount }, () => null),
    candidateScopeMode: "automatic",
    termCounts: [],
    bounds: {},
    availability: { ...EMPTY_POLYMER_AVAILABILITY },
    weights: { ...EMPTY_POLYMER_WEIGHTS },
    optimizer: { ...EMPTY_POLYMER_OPTIMIZER },
    setupName: "",
    overrideReason: "",
    changeReason: "",
  };
}

export function restorePolymerCalibrationDraft(
  snapshot: PolymerSourceSnapshot,
  plan: LinearViscoelasticPlanResponse,
): PolymerCalibrationDraft {
  const restored = createPolymerCalibrationDraft(snapshot);
  const content = plan.current_revision.content;
  const dispositions = content.input_semantics?.point_dispositions ?? [];
  for (const item of dispositions) {
    if (item.ordinal >= 0 && item.ordinal < restored.partitions.length) {
      restored.partitions[item.ordinal] = item.partition;
    }
  }
  const statuses = content.statuses ?? {};
  const availability = { ...restored.availability };
  for (const key of POLYMER_AVAILABILITY_FIELDS) {
    const value = statuses[key];
    if (value === "PROVIDED" || value === "NOT_PROVIDED") availability[key] = value;
  }
  const weights = { ...restored.weights };
  for (const key of [
    "relaxation_weight",
    "dma_storage_weight",
    "dma_loss_weight",
    "relaxation_scale_pa",
    "dma_storage_scale_pa",
    "dma_loss_scale_pa",
  ] as const) {
    const value = content.weights?.[key];
    if (value !== undefined) weights[key] = String(value);
  }
  const optimizer = { ...restored.optimizer };
  for (const key of ["ftol", "xtol", "gtol", "max_nfev"] as const) {
    const value = content.optimizer?.[key];
    if (value !== undefined) optimizer[key] = String(value);
  }
  return {
    ...restored,
    selectedTemperature: content.input_semantics?.selected_temperature_k === null
      || content.input_semantics?.selected_temperature_k === undefined
      ? restored.selectedTemperature
      : String(content.input_semantics.selected_temperature_k),
    candidateScopeMode: content.candidate_scope_mode === "automatic" ? "automatic" : "manual",
    termCounts: [...(content.term_counts ?? [])],
    bounds: Object.fromEntries(Object.entries(content.parameter_bounds ?? {}).map(([term, bounds]) => [
      term,
      bounds.map((bound) => ({
        ...bound,
        lower: Number(bound.lower),
        start: Number(bound.start),
        upper: Number(bound.upper),
      })),
    ])),
    availability,
    weights,
    optimizer,
    setupName: content.setup_name ?? "",
    overrideReason: content.override_reason ?? "",
    changeReason: plan.current_revision.change_reason ?? "",
  };
}

export function togglePolymerCalibrationTerm(
  draft: PolymerCalibrationDraft,
  term: number,
): PolymerCalibrationDraft {
  const termCounts = draft.termCounts.includes(term)
    ? draft.termCounts.filter((item) => item !== term)
    : [...draft.termCounts, term].sort((left, right) => left - right);
  const bounds = { ...draft.bounds };
  if (termCounts.includes(term) && !bounds[String(term)]) bounds[String(term)] = blankPolymerBounds(term);
  if (!termCounts.includes(term)) delete bounds[String(term)];
  return { ...draft, candidateScopeMode: "manual", termCounts, bounds };
}

export function setPolymerCandidateScopeMode(
  draft: PolymerCalibrationDraft,
  candidateScopeMode: LinearViscoelasticCandidateScopeMode,
): PolymerCalibrationDraft {
  return { ...draft, candidateScopeMode };
}

export function countPolymerPartitions(partitions: PolymerCalibrationDraft["partitions"]) {
  return {
    calibration: partitions.filter((item) => item === "CALIBRATION").length,
    holdout: partitions.filter((item) => item === "HOLDOUT").length,
    excluded: partitions.filter((item) => item === "EXCLUDED").length,
    unresolved: partitions.filter((item) => item === null).length,
  };
}

function parsedPolicy(draft: PolymerCalibrationDraft) {
  return {
    tolerances: {
      ftol: finitePolymerDraftValue(draft.optimizer.ftol),
      xtol: finitePolymerDraftValue(draft.optimizer.xtol),
      gtol: finitePolymerDraftValue(draft.optimizer.gtol),
      max_nfev: finitePolymerDraftValue(draft.optimizer.max_nfev),
    },
    weights: {
      relaxation_weight: finitePolymerDraftValue(draft.weights.relaxation_weight),
      dma_storage_weight: finitePolymerDraftValue(draft.weights.dma_storage_weight),
      dma_loss_weight: finitePolymerDraftValue(draft.weights.dma_loss_weight),
      relaxation_scale_pa: finitePolymerDraftValue(draft.weights.relaxation_scale_pa),
      dma_storage_scale_pa: finitePolymerDraftValue(draft.weights.dma_storage_scale_pa),
      dma_loss_scale_pa: finitePolymerDraftValue(draft.weights.dma_loss_scale_pa),
    },
  };
}

export function derivePolymerCalibrationBlockers(
  draft: PolymerCalibrationDraft,
  source: PolymerCalibrationSourceContext,
  requiresOverrideReason = false,
): PolymerCalibrationBlockers {
  const partitionCounts = countPolymerPartitions(draft.partitions);
  const activeDirectPartitionCounts = activePolymerDirectPartitionCounts(draft, source.snapshot);
  const observationCount = polymerCalibrationObservationCount(draft, source);
  const availabilityBlocker = Object.values(draft.availability).some((value) => !value)
    ? "Declare whether the loading ramp, frequency sweep, preconditioning, and linear viscoelastic range were recorded."
    : "";
  const direct = source.sourceChoice === "test-data" ? [
    !source.directAvailable ? "Load a supported exact shear relaxation or DMA Test Data revision." : "",
    availabilityBlocker,
    partitionCounts.unresolved ? `Choose how each of the ${partitionCounts.unresolved} unassigned measured points will be used.` : "",
    activeDirectPartitionCounts.calibration < 3 ? "At least three measured values from the selected response must be used to calculate the model." : "",
    source.snapshot.mode === "dma" && !draft.selectedTemperature ? "Choose the exact isothermal DMA temperature." : "",
  ].filter(Boolean) : [
    availabilityBlocker,
    !source.processedAvailable ? "Save the shifted DMA response in Process before choosing this source." : "",
  ].filter(Boolean);
  const { tolerances, weights } = parsedPolicy(draft);
  const automatic = draft.candidateScopeMode === "automatic";
  const automaticTerms = automaticPolymerTermCounts(observationCount);
  const activeTerms = automatic ? automaticTerms : draft.termCounts;
  const incompleteBounds = activeTerms.some((term) => (
    (draft.bounds[String(term)] ?? []).length !== polymerPronyParameterCount(term)
  ));
  const model = [
    automatic && !automaticTerms.length ? "The selected data does not provide enough values for a Prony model." : "",
    !automatic && !draft.termCounts.length ? "Choose at least one Prony term count." : "",
    !automatic && draft.termCounts.some((term) => polymerPronyParameterCount(term) > observationCount)
      ? `The selected Prony models need more values than the ${observationCount} values used to calculate the model.`
      : "",
    incompleteBounds ? "Every model in this scope needs its reviewed parameter ranges." : "",
    activeTerms.some((term) => (draft.bounds[String(term)] ?? []).some((item) => !Number.isFinite(item.lower) || !Number.isFinite(item.start) || !Number.isFinite(item.upper))) ? "Every selected parameter requires numeric lower, start, and upper values." : "",
    activeTerms.some((term) => (draft.bounds[String(term)] ?? []).some((item) => !(item.lower < item.start && item.start < item.upper))) ? "Every start value must be strictly inside its bounds." : "",
  ].filter(Boolean);
  const solver = [
    !draft.setupName.trim() ? "Enter a name for this calculation setup." : "",
    requiresOverrideReason && !draft.overrideReason.trim() ? "Record why the current calculation settings are being changed." : "",
    Object.values(weights).some((value) => value === null || value <= 0) ? "Enter objective weights and positive response scales." : "",
    weights.dma_storage_weight !== null && weights.dma_loss_weight !== null && weights.dma_storage_weight + weights.dma_loss_weight !== 1 ? "DMA storage and loss weights must sum exactly to 1." : "",
    Object.values(draft.optimizer).some((value) => !value.trim()) ? "Enter all solver tolerances and the evaluation limit." : "",
    Object.entries(tolerances).some(([key, value]) => value === null || (key !== "max_nfev" && !(value > 0 && value < 1)) || (key === "max_nfev" && (!Number.isInteger(value) || value < 10))) ? "Optimizer tolerances must be in (0, 1), and max_nfev must be an integer from 10 upward." : "",
    !draft.changeReason.trim() ? "Record why this calculation is being run." : "",
  ].filter(Boolean);
  return { direct, model, solver };
}

export function buildPolymerCalibrationPlanRequest(
  draft: PolymerCalibrationDraft,
  source: PolymerCalibrationSourceContext,
  governance: PolymerCalibrationGovernanceContext | null,
): DirectLinearViscoelasticPlanRequest | ProcessedLinearViscoelasticPlanRequest | null {
  const blockers = derivePolymerCalibrationBlockers(draft, source, Boolean(governance?.basedOn));
  if (blockers.direct.length || blockers.model.length || blockers.solver.length || !governance
    || !draft.setupName.trim() || (governance.basedOn && !draft.overrideReason.trim())) return null;
  const { tolerances, weights } = parsedPolicy(draft);
  const observationCount = polymerCalibrationObservationCount(draft, source);
  const termCounts = draft.candidateScopeMode === "automatic"
    ? automaticPolymerTermCounts(observationCount)
    : draft.termCounts;
  const base = {
    setup_name: draft.setupName.trim(),
    material: { id: governance.material.id, revision_id: governance.material.revisionId },
    material_state: { id: governance.materialState.id, revision_id: governance.materialState.revisionId },
    input_mode: governance.inputMode,
    candidate_scope_mode: draft.candidateScopeMode,
    ...(governance.basedOn ? {
      based_on_plan_id: governance.basedOn.planId,
      based_on_plan_revision_id: governance.basedOn.planRevisionId,
      override_reason: draft.overrideReason.trim(),
    } : {}),
    availability: draft.availability as LinearViscoelasticAvailabilityMap,
    term_counts: termCounts,
    parameter_bounds: Object.fromEntries(termCounts.map((term) => [String(term), draft.bounds[String(term)]])),
    start_vectors: polymerBoundsStartVectors(termCounts, draft.bounds),
    weights: {
      ...draft.weights,
      relaxation_weight: String(weights.relaxation_weight),
      dma_storage_weight: String(weights.dma_storage_weight),
      dma_loss_weight: String(weights.dma_loss_weight),
      relaxation_scale_pa: String(weights.relaxation_scale_pa),
      dma_storage_scale_pa: String(weights.dma_storage_scale_pa),
      dma_loss_scale_pa: String(weights.dma_loss_scale_pa),
    },
    optimizer: {
      method: "trf" as const,
      x_scale: "jac" as const,
      transform: "ln" as const,
      ftol: tolerances.ftol!,
      xtol: tolerances.xtol!,
      gtol: tolerances.gtol!,
      max_nfev: tolerances.max_nfev!,
    },
    recommendation_policy: "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0" as const,
    change_reason: draft.changeReason.trim(),
  };
  if (source.sourceChoice === "processing-output") {
    return source.processingSource ? {
      ...base,
      processing_output: { id: source.processingSource.id, revision_id: source.processingSource.revisionId },
    } : null;
  }
  if (!source.directSource) return null;
  const pointDispositions: LinearViscoelasticPointDisposition[] = draft.partitions.map((partition, ordinal) => ({
    ordinal,
    partition: partition!,
    exclusion_reason: partition === "EXCLUDED" ? "Excluded by engineer from the active calibration domain" : null,
  }));
  return {
    ...base,
    test_data: { id: source.directSource.id, revision_id: source.directSource.revisionId },
    selected_temperature_k: finitePolymerDraftValue(draft.selectedTemperature)!,
    point_dispositions: pointDispositions,
  };
}
