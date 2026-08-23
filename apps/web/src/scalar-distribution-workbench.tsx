import { type KeyboardEvent as ReactKeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceTensileReplicateSelection,
  createReferenceTensileReplicateStatisticalPlan,
  createScalarDistributionSelection,
  executeReferenceTensileReplicateStatistics,
  getScalarDistributionResult,
  listDatasetRevisions,
  listDatasetsForMaterialState,
  listReferenceTensileReplicateSelections,
  listReferenceTensileReplicateStatisticalPlans,
  listReferenceTensileReplicateStatisticalRuns,
  listScalarDistributionSelections,
  reviseScalarDistributionSelection,
} from "./api";
import type {
  DataClassification,
  DatasetResponse,
  DistributionFamily,
  ExactUnitProfilePin,
  MaterialStateResponse,
  ReplicateStatisticalPlanResponse,
  ReplicateStatisticalRunResponse,
  ScalarDistributionCandidate,
  ScalarDistributionResultResponse,
  ScalarDistributionSelectionResponse,
  TensileReplicateSelectionResponse,
} from "./types";
import "./features/modeling/ui/modeling-scalar-distribution.css";

interface Props {
  config: ApiConfig;
  classification: DataClassification;
  state?: MaterialStateResponse;
  onClose: () => void;
}

type Action = "load" | "selection" | "fit" | "decision" | null;

const FAMILY_LABELS: Record<DistributionFamily, string> = {
  normal: "Normal",
  lognormal: "Lognormal",
  weibull: "Weibull",
};

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Distribution comparison failed.";
}

function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

function metric(value: number | null, digits = 3): string {
  if (value === null) return "—";
  if (Math.abs(value) >= 10_000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) {
    return value.toExponential(digits);
  }
  return value.toFixed(digits);
}

function displayStress(
  valuePa: number,
  result: ScalarDistributionResultResponse,
): { text: string; unit: string } {
  const unit = result.unit_applications[0]?.unit_id ?? "Pa";
  const divisor = unit === "GPa" ? 1e9 : unit === "MPa" ? 1e6 : unit === "kPa" ? 1e3 : 1;
  return { text: metric(valuePa / divisor, 4), unit };
}

function parameterSummary(
  candidate: ScalarDistributionCandidate,
  result: ScalarDistributionResultResponse,
): string {
  if (candidate.status !== "succeeded") return candidate.reason_codes.join(" · ");
  return candidate.parameters.map((parameter) => {
    if (parameter.unit_id === "Pa") {
      const display = displayStress(parameter.estimate, result);
      return `${parameter.name} ${display.text} ${display.unit}`;
    }
    return `${parameter.name} ${metric(parameter.estimate, 5)}`;
  }).join(" · ");
}

function stressDisplayUnit(result: ScalarDistributionResultResponse): {
  divisor: number;
  unit: string;
} {
  const unit = result.unit_applications[0]?.unit_id ?? "Pa";
  const divisor = unit === "GPa" ? 1e9 : unit === "MPa" ? 1e6 : unit === "kPa" ? 1e3 : 1;
  return { divisor, unit };
}

function parameterEstimate(
  candidate: ScalarDistributionCandidate,
  name: "location" | "scale" | "shape",
): number | null {
  return candidate.parameters.find((parameter) => parameter.name === name)?.estimate ?? null;
}

function approximateErf(value: number): number {
  const sign = value < 0 ? -1 : 1;
  const magnitude = Math.abs(value);
  const t = 1 / (1 + 0.3275911 * magnitude);
  const polynomial = (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
    - 0.284496736) * t + 0.254829592) * t;
  return sign * (1 - polynomial * Math.exp(-(magnitude ** 2)));
}

function fittedCdf(candidate: ScalarDistributionCandidate, valuePa: number): number | null {
  if (candidate.status !== "succeeded") return null;
  const scale = parameterEstimate(candidate, "scale");
  if (scale === null || scale <= 0) return null;
  if (candidate.family === "normal") {
    const location = parameterEstimate(candidate, "location");
    if (location === null) return null;
    return 0.5 * (1 + approximateErf((valuePa - location) / (scale * Math.SQRT2)));
  }
  const shape = parameterEstimate(candidate, "shape");
  if (shape === null || shape <= 0 || valuePa <= 0) return 0;
  if (candidate.family === "lognormal") {
    return 0.5 * (1 + approximateErf(Math.log(valuePa / scale) / (shape * Math.SQRT2)));
  }
  return 1 - Math.exp(-((valuePa / scale) ** shape));
}

function plotTick(value: number): string {
  const magnitude = Math.abs(value);
  if (magnitude >= 1_000_000 || (magnitude > 0 && magnitude < 0.01)) {
    return value.toExponential(2);
  }
  if (magnitude >= 100) return value.toFixed(0);
  if (magnitude >= 10) return value.toFixed(1);
  return value.toFixed(2);
}

function DistributionCdfPlot({
  result,
  selectedFamily,
}: {
  result: ScalarDistributionResultResponse;
  selectedFamily: DistributionFamily | "";
}) {
  const plotRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 900, height: 240 });

  useEffect(() => {
    const element = plotRef.current;
    if (!element || typeof ResizeObserver === "undefined") return undefined;
    const update = (): void => {
      const box = element.getBoundingClientRect();
      if (box.width > 0 && box.height > 0) {
        setSize({ width: Math.round(box.width), height: Math.round(box.height) });
      }
    };
    const observer = new ResizeObserver(update);
    observer.observe(element);
    update();
    return () => observer.disconnect();
  }, []);

  const chart = useMemo(() => {
    const display = stressDisplayUnit(result);
    const observations = result.observations
      .map((observation) => observation.value_pa)
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
      .sort((first, second) => first - second);
    const displayValues = observations.map((value) => value / display.divisor);
    if (!displayValues.length) return null;
    const minimum = displayValues[0];
    const maximum = displayValues[displayValues.length - 1];
    const observedSpan = maximum - minimum;
    const span = observedSpan > 0 ? observedSpan : Math.max(Math.abs(maximum) * 0.08, 1);
    const lower = minimum - span * 0.12;
    const upper = maximum + span * 0.12;
    const margin = { top: 18, right: 26, bottom: 50, left: 76 };
    const innerWidth = Math.max(120, size.width - margin.left - margin.right);
    const innerHeight = Math.max(80, size.height - margin.top - margin.bottom);
    const x = (value: number): number => margin.left + ((value - lower) / (upper - lower)) * innerWidth;
    const y = (probability: number): number => margin.top + (1 - probability) * innerHeight;
    const empiricalParts = [`M ${x(lower)} ${y(0)}`];
    displayValues.forEach((value, index) => {
      const previous = index / displayValues.length;
      const next = (index + 1) / displayValues.length;
      empiricalParts.push(`L ${x(value)} ${y(previous)}`, `L ${x(value)} ${y(next)}`);
    });
    empiricalParts.push(`L ${x(upper)} ${y(1)}`);
    const candidates = result.candidates
      .filter((candidate) => candidate.status === "succeeded")
      .map((candidate) => {
        const parts: string[] = [];
        for (let index = 0; index <= 160; index += 1) {
          const displayValue = lower + ((upper - lower) * index) / 160;
          const probability = fittedCdf(candidate, displayValue * display.divisor);
          if (probability === null || !Number.isFinite(probability)) continue;
          parts.push(`${parts.length ? "L" : "M"} ${x(displayValue)} ${y(Math.max(0, Math.min(1, probability)))}`);
        }
        return { candidate, path: parts.join(" ") };
      });
    return {
      display,
      observations,
      empiricalPath: empiricalParts.join(" "),
      candidates,
      xTicks: Array.from({ length: 6 }, (_, index) => lower + ((upper - lower) * index) / 5),
      yTicks: [0, 0.25, 0.5, 0.75, 1],
      x,
      y,
      margin,
      innerWidth,
      innerHeight,
    };
  }, [result, size]);

  if (!chart) return null;
  return (
    <section className="distribution-probability-panel" aria-labelledby="distribution-probability-title">
      <header>
        <div>
          <strong id="distribution-probability-title">Probability comparison</strong>
          <span>Empirical CDF against fitted candidates · source observations retained</span>
        </div>
        <div className="distribution-plot-legend" aria-label="Distribution curve legend">
          <span className="empirical"><i />Empirical</span>
          {chart.candidates.map(({ candidate }) => <span className={candidate.family} key={candidate.family}><i />{FAMILY_LABELS[candidate.family]}{selectedFamily === candidate.family ? " · selected" : ""}</span>)}
        </div>
      </header>
      <div className="distribution-cdf-plot" ref={plotRef}>
        <svg width={size.width} height={size.height} role="img" aria-labelledby="distribution-cdf-svg-title distribution-cdf-svg-description">
          <title id="distribution-cdf-svg-title">Peak engineering stress empirical and fitted cumulative distributions</title>
          <desc id="distribution-cdf-svg-description">{chart.observations.length} retained observations compared with successful Normal, Lognormal, and Weibull fitted cumulative distribution functions.</desc>
          <g className="distribution-plot-grid">
            {chart.yTicks.map((tick) => <line key={`y-${tick}`} x1={chart.margin.left} x2={chart.margin.left + chart.innerWidth} y1={chart.y(tick)} y2={chart.y(tick)} />)}
            {chart.xTicks.map((tick) => <line key={`x-${tick}`} x1={chart.x(tick)} x2={chart.x(tick)} y1={chart.margin.top} y2={chart.margin.top + chart.innerHeight} />)}
          </g>
          <g className="distribution-plot-axes">
            <line x1={chart.margin.left} x2={chart.margin.left} y1={chart.margin.top} y2={chart.margin.top + chart.innerHeight} />
            <line x1={chart.margin.left} x2={chart.margin.left + chart.innerWidth} y1={chart.margin.top + chart.innerHeight} y2={chart.margin.top + chart.innerHeight} />
            {chart.yTicks.map((tick) => <text key={`yl-${tick}`} x={chart.margin.left - 10} y={chart.y(tick) + 4} textAnchor="end">{tick.toFixed(2)}</text>)}
            {chart.xTicks.map((tick) => <text key={`xl-${tick}`} x={chart.x(tick)} y={chart.margin.top + chart.innerHeight + 20} textAnchor="middle">{plotTick(tick)}</text>)}
            <text className="axis-title" x={chart.margin.left + chart.innerWidth / 2} y={size.height - 10} textAnchor="middle">Peak engineering stress [{chart.display.unit}]</text>
            <text className="axis-title y-axis-title" x={16} y={chart.margin.top + chart.innerHeight / 2} textAnchor="middle" transform={`rotate(-90 16 ${chart.margin.top + chart.innerHeight / 2})`}>Cumulative probability</text>
          </g>
          {chart.candidates.map(({ candidate, path }) => <path className={`distribution-fit-line ${candidate.family}${selectedFamily === candidate.family ? " selected" : ""}`} d={path} key={candidate.family}><title>{FAMILY_LABELS[candidate.family]} fitted CDF</title></path>)}
          <path className="distribution-empirical-line" d={chart.empiricalPath}><title>Empirical CDF</title></path>
        </svg>
      </div>
    </section>
  );
}

function isProcessedSelection(
  selection: TensileReplicateSelectionResponse,
  processedRevisionIds: Set<string>,
): boolean {
  return selection.current_revision.content.members.every((member) =>
    processedRevisionIds.has(member.dataset_revision_id),
  );
}

function selectionUsesCurrentProcessedHeads(
  selection: TensileReplicateSelectionResponse,
  datasets: DatasetResponse[],
): boolean {
  const currentByDataset = new Map(datasets.map((item) => [item.dataset_id, item]));
  return selection.current_revision.content.members.every((member) => {
    const dataset = currentByDataset.get(member.dataset_id);
    return dataset?.current_revision.id === member.dataset_revision_id
      && dataset.current_revision.content.representation === "processed";
  });
}

async function resolveProcessedRevisionIds(
  config: ApiConfig,
  datasets: DatasetResponse[],
  selections: TensileReplicateSelectionResponse[],
): Promise<Set<string>> {
  const currentByDataset = new Map(datasets.map((item) => [item.dataset_id, item]));
  const processed = new Set(
    datasets
      .filter((item) => item.current_revision.content.representation === "processed")
      .map((item) => item.current_revision.id),
  );
  const historicalDatasetIds = new Set<string>();
  selections.forEach((selection) => {
    selection.current_revision.content.members.forEach((member) => {
      if (currentByDataset.get(member.dataset_id)?.current_revision.id !== member.dataset_revision_id) {
        historicalDatasetIds.add(member.dataset_id);
      }
    });
  });
  const histories = await Promise.all(
    [...historicalDatasetIds].map((datasetId) => listDatasetRevisions(config, datasetId)),
  );
  histories.forEach((response) => {
    response.data.revisions.forEach((revision) => {
      if (revision.content.representation === "processed") processed.add(revision.id);
    });
  });
  return processed;
}

function isSameUnitProfile(
  first: ExactUnitProfilePin | null,
  second: ExactUnitProfilePin | null,
): boolean {
  if (first === null || second === null) return first === second;
  return first.profile_id === second.profile_id
    && first.revision_id === second.revision_id
    && first.content_sha256 === second.content_sha256;
}

export function ScalarDistributionWorkbench({
  config,
  classification,
  state,
  onClose,
}: Props) {
  const workbenchRef = useRef<HTMLDivElement | null>(null);
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [selections, setSelections] = useState<TensileReplicateSelectionResponse[]>([]);
  const [processedRevisionIds, setProcessedRevisionIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [selectedDatasetRevisions, setSelectedDatasetRevisions] = useState<string[]>([]);
  const [selectedSelectionId, setSelectedSelectionId] = useState("");
  const [plans, setPlans] = useState<ReplicateStatisticalPlanResponse[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [runs, setRuns] = useState<ReplicateStatisticalRunResponse[]>([]);
  const [result, setResult] = useState<ScalarDistributionResultResponse | null>(null);
  const [decisions, setDecisions] = useState<ScalarDistributionSelectionResponse[]>([]);
  const [selectedFamily, setSelectedFamily] = useState<DistributionFamily | "">("");
  const [selectionReason, setSelectionReason] = useState("");
  const [decisionEditing, setDecisionEditing] = useState(false);
  const [seed, setSeed] = useState(210);
  const [selectionLabel, setSelectionLabel] = useState("Processed tensile replicate set");
  const [profileId, setProfileId] = useState("");
  const [profileRevisionId, setProfileRevisionId] = useState("");
  const [profileSha256, setProfileSha256] = useState("");
  const [action, setAction] = useState<Action>("load");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const processedDatasets = useMemo(
    () => datasets.filter((item) => item.current_revision.content.representation === "processed"),
    [datasets],
  );
  const processedSelections = useMemo(
    () => selections.filter((item) => isProcessedSelection(item, processedRevisionIds)),
    [processedRevisionIds, selections],
  );
  const selection = selections.find((item) => item.selection_id === selectedSelectionId) ?? null;
  const currentDecision = decisions[0] ?? null;
  const observationSummary = useMemo(() => {
    if (!result) return null;
    const quality = { observed: 0, missing: 0, non_finite: 0, censored: 0 };
    const assessment = { not_assessed: 0, flagged: 0, not_flagged: 0 };
    result.observations.forEach((observation) => {
      quality[observation.quality] += 1;
      assessment[observation.outlier_assessment] += 1;
    });
    return { quality, assessment };
  }, [result]);
  const candidateWarnings = useMemo(() => result
    ? Array.from(new Set(result.candidates.flatMap((item) => [
        ...item.warnings,
        ...item.reason_codes.filter((code) => code !== "fit_succeeded"),
      ])))
    : [], [result]);
  const profileFields = [profileId.trim(), profileRevisionId.trim(), profileSha256.trim()];
  const profilePartiallyEntered = profileFields.some(Boolean) && !profileFields.every(Boolean);

  useEffect(() => {
    // The workbench is lazy-loaded. Parent focus may run while Suspense still
    // shows its fallback, so focus again when the real dock first mounts.
    workbenchRef.current?.focus();
  }, []);

  async function loadResult(resultId: string): Promise<void> {
    const [resultResponse, selectionResponse] = await Promise.all([
      getScalarDistributionResult(config, resultId),
      listScalarDistributionSelections(config, resultId),
    ]);
    setResult(resultResponse.data);
    setDecisions(selectionResponse.data.items);
    const saved = selectionResponse.data.items[0];
    setSelectedFamily(saved?.content.selected_family ?? "");
    setSelectionReason(saved?.content.selection_reason ?? "");
    setDecisionEditing(false);
  }

  async function loadRuns(nextPlan: ReplicateStatisticalPlanResponse): Promise<void> {
    const response = await listReferenceTensileReplicateStatisticalRuns(
      config,
      nextPlan.current_revision.id,
    );
    setRuns(response.data.items);
    const latest = response.data.items.find(
      (item) => item.status === "succeeded" && item.scalar_distribution_result_id,
    );
    if (latest?.scalar_distribution_result_id) {
      await loadResult(latest.scalar_distribution_result_id);
    } else {
      setResult(null);
      setDecisions([]);
      setSelectedFamily("");
      setSelectionReason("");
    }
  }

  async function loadPlans(nextSelection: TensileReplicateSelectionResponse): Promise<void> {
    const response = await listReferenceTensileReplicateStatisticalPlans(
      config,
      nextSelection.current_revision.id,
    );
    const distributionPlans = response.data.items.filter(
      (item) => item.current_revision.content.scalar_distribution !== null,
    );
    setPlans(distributionPlans);
    const latest = distributionPlans[0];
    setSelectedPlanId(latest?.statistical_plan_id ?? "");
    if (latest) await loadRuns(latest);
    else {
      setRuns([]);
      setResult(null);
      setDecisions([]);
    }
  }

  useEffect(() => {
    let active = true;
    const materialStateId = state?.material_state_id;
    if (!materialStateId) {
      setAction(null);
      setDatasets([]);
      setSelections([]);
      setProcessedRevisionIds(new Set());
      return () => { active = false; };
    }
    setAction("load");
    setError(null);
    Promise.all([
      listDatasetsForMaterialState(config, materialStateId),
      listReferenceTensileReplicateSelections(config, materialStateId),
    ]).then(async ([datasetResponse, selectionResponse]) => {
      if (!active) return;
      const nextProcessedRevisionIds = await resolveProcessedRevisionIds(
        config,
        datasetResponse.data.items,
        selectionResponse.data.items,
      );
      if (!active) return;
      setDatasets(datasetResponse.data.items);
      setSelections(selectionResponse.data.items);
      setProcessedRevisionIds(nextProcessedRevisionIds);
      const first = selectionResponse.data.items
        .filter((item) => isProcessedSelection(item, nextProcessedRevisionIds))
        .at(-1);
      setSelectedSelectionId(first?.selection_id ?? "");
      if (first) await loadPlans(first);
    }).catch((cause) => {
      if (active) setError(messageFor(cause));
    }).finally(() => {
      if (active) setAction(null);
    });
    return () => { active = false; };
  // The exact Material State identity is the reload boundary; config is stable per connection.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.material_state_id]);

  async function chooseSelection(selectionId: string): Promise<void> {
    setSelectedSelectionId(selectionId);
    setResult(null);
    setDecisions([]);
    setSelectedFamily("");
    setSelectionReason("");
    setDecisionEditing(false);
    const next = selections.find((item) => item.selection_id === selectionId);
    if (!next) {
      setPlans([]);
      setRuns([]);
      return;
    }
    setAction("load");
    setError(null);
    try {
      await loadPlans(next);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  function toggleDataset(revisionId: string): void {
    setSelectedDatasetRevisions((current) => current.includes(revisionId)
      ? current.filter((item) => item !== revisionId)
      : [...current, revisionId]);
    setNotice("Working selection changed; saved Selection revisions and Results remain immutable.");
  }

  async function saveReplicateSelection(): Promise<void> {
    if (selectedDatasetRevisions.length < 2) return;
    setAction("selection");
    setError(null);
    setNotice(null);
    try {
      const response = await createReferenceTensileReplicateSelection(config, {
        classification,
        selection_label: selectionLabel.trim(),
        dataset_revision_ids: selectedDatasetRevisions,
        change_reason: "Pin exact processed replicates for scalar distribution comparison",
      });
      const next = response.data;
      setSelections((current) => [next, ...current]);
      setSelectedSelectionId(next.selection_id);
      setSelectedDatasetRevisions([]);
      await loadPlans(next);
      setNotice("Exact processed replicate Selection saved. Source Dataset revisions were not changed.");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  function exactUnitProfile(): ExactUnitProfilePin | null {
    if (!profileFields.every(Boolean)) return null;
    return {
      profile_id: profileFields[0],
      revision_id: profileFields[1],
      content_sha256: profileFields[2],
    };
  }

  async function fitCandidates(): Promise<void> {
    if (!selection || profilePartiallyEntered) return;
    setAction("fit");
    setError(null);
    setNotice(null);
    setResult(null);
    setDecisions([]);
    setSelectedFamily("");
    setSelectionReason("");
    setDecisionEditing(false);
    try {
      const unitProfile = exactUnitProfile();
      const reusablePlan = plans.find((item) => {
        const options = item.current_revision.content.scalar_distribution;
        return item.current_revision.content.selection_revision_id === selection.current_revision.id
          && options?.seed === seed
          && options.bootstrap_samples === 999
          && isSameUnitProfile(options.unit_profile, unitProfile);
      });
      const nextPlan = reusablePlan ?? (await createReferenceTensileReplicateStatisticalPlan(config, {
        classification,
        plan_label: `Peak engineering stress distribution comparison · selection ${selection.current_revision.id.slice(0, 8)} · seed ${seed}`,
        selection_id: selection.selection_id,
        selection_revision_id: selection.current_revision.id,
        sample_count: selection.current_revision.content.member_count,
        scalar_distribution: {
          seed,
          bootstrap_samples: 999,
          unit_profile: unitProfile,
        },
        change_reason: "Fit approved scalar distribution candidates on exact processed replicates",
      })).data;
      if (!reusablePlan) setPlans((current) => [nextPlan, ...current]);
      setSelectedPlanId(nextPlan.statistical_plan_id);
      const runResponse = await executeReferenceTensileReplicateStatistics(config, {
        plan_id: nextPlan.statistical_plan_id,
        plan_revision_id: nextPlan.current_revision.id,
        change_reason: "Calculate deterministic Normal, Lognormal, and Weibull comparison",
      });
      setRuns([runResponse.data]);
      if (runResponse.data.status !== "succeeded" || !runResponse.data.scalar_distribution_result_id) {
        throw new Error(runResponse.data.failure_code ?? "The committed Statistics Run failed.");
      }
      await loadResult(runResponse.data.scalar_distribution_result_id);
      setNotice("Comparison saved. All source observations and descriptive statistics remain unchanged.");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function choosePlan(planId: string): Promise<void> {
    setSelectedPlanId(planId);
    const next = plans.find((item) => item.statistical_plan_id === planId);
    if (!next) return;
    setAction("load");
    setError(null);
    try {
      await loadRuns(next);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function chooseRun(runId: string): Promise<void> {
    const next = runs.find((item) => item.statistical_run_id === runId);
    if (!next?.scalar_distribution_result_id) return;
    setAction("load");
    setError(null);
    try {
      await loadResult(next.scalar_distribution_result_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function saveDecision(): Promise<void> {
    if (!result || !selectedFamily || !selectionReason.trim()) return;
    const candidate = result.candidates.find((item) => item.family === selectedFamily);
    if (!candidate || candidate.status !== "succeeded") return;
    setAction("decision");
    setError(null);
    try {
      const response = currentDecision
        ? await reviseScalarDistributionSelection(config, currentDecision.distribution_selection_id, {
            expected_current_revision_id: currentDecision.current_revision.id,
            distribution_result_id: result.scalar_distribution_result_id,
            distribution_result_revision_id: result.current_revision.id,
            selected_family: selectedFamily,
            candidate_sha256: candidate.candidate_sha256,
            selection_reason: selectionReason.trim(),
          })
        : await createScalarDistributionSelection(
            config,
            result.scalar_distribution_result_id,
            {
              classification,
              distribution_result_revision_id: result.current_revision.id,
              selected_family: selectedFamily,
              candidate_sha256: candidate.candidate_sha256,
              selection_reason: selectionReason.trim(),
            },
          );
      setDecisions([response.data]);
      setDecisionEditing(false);
      setNotice("Selected model and reason saved as an exact immutable revision.");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  function beginDecision(candidate: ScalarDistributionCandidate): void {
    if (candidate.status !== "succeeded") return;
    setSelectedFamily(candidate.family);
    setSelectionReason(
      currentDecision?.content.selected_family === candidate.family
        ? currentDecision.content.selection_reason
        : "",
    );
    setDecisionEditing(true);
  }

  const selectedCandidate = result?.candidates.find(
    (candidate) => candidate.family === selectedFamily,
  ) ?? null;
  const diagnosticCount = result
    ? candidateWarnings.length + (result.sample_count < result.small_sample_warning_below ? 1 : 0)
    : 0;

  function keepAnalysisFocus(event: ReactKeyboardEvent<HTMLDivElement>): void {
    if (event.key !== "Tab") return;
    const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
      'button:not([disabled]), summary, input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )).filter((item) => {
      if (item.getAttribute("aria-hidden") === "true") return false;
      const closedDetails = item.closest("details:not([open])");
      return !closedDetails || item === closedDetails.querySelector(":scope > summary");
    });
    if (!focusable.length) {
      event.preventDefault();
      event.currentTarget.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      ref={workbenchRef}
      className="scalar-distribution-workbench"
      id="scalar-distribution-analysis"
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-labelledby="distribution-analysis-title"
      aria-describedby="distribution-analysis-subtitle"
      onKeyDown={keepAnalysisFocus}
    >
      <header className="distribution-drawer-heading">
        <div className="distribution-drawer-title">
          <h3 id="distribution-analysis-title">Distribution analysis</h3>
          <span id="distribution-analysis-subtitle">Optional · peak engineering stress</span>
        </div>
        <div className="distribution-drawer-state">
          {result ? <span>
            Result r{result.current_revision.revision_no} · n = {result.sample_count} · recommendation {result.recommended_families.length
              ? result.recommended_families.map((item) => FAMILY_LABELS[item]).join(" + ")
              : "none"}
          </span> : <span>{action === "load" ? "Loading saved analysis…" : "No saved comparison"}</span>}
          <button className="text-button" type="button" onClick={onClose}>Close</button>
        </div>
      </header>

      <div className="distribution-workbench-body">
        <div className="distribution-command-bar" aria-label="Distribution analysis commands">
          <label className="distribution-selection-control">
            <span>Replicate set</span>
            <select
              aria-label="Saved replicate set"
              value={selectedSelectionId}
              disabled={action !== null}
              onChange={(event) => void chooseSelection(event.target.value)}
            >
              <option value="">Choose exact replicates</option>
              {processedSelections.map((item) => (
                <option key={item.selection_id} value={item.selection_id}>
                  {item.selection_label} · r{item.current_revision.revision_no} · {item.current_revision.content.member_count} observations · {selectionUsesCurrentProcessedHeads(item, datasets) ? "current revisions" : "historical exact revisions"}
                </option>
              ))}
            </select>
          </label>
          {selection ? (
            <div className="distribution-input-summary">
              <strong>{selection.current_revision.content.member_count} exact observations</strong>
              <span>{selectionUsesCurrentProcessedHeads(selection, datasets)
                ? "Current processed revisions"
                : "Historical processed revisions"}</span>
            </div>
          ) : <div className="distribution-input-summary unavailable"><strong>No exact set selected</strong><span>Analysis remains off</span></div>}

          <div className="distribution-command-tools">
            <details className="distribution-command-detail distribution-sets-detail">
              <summary>Replicate sets</summary>
              <div className="distribution-popover distribution-sets-popover">
                <div className="distribution-popover-heading">
                  <strong>Create exact replicate set</strong>
                  <span>{processedDatasets.length} processed Dataset revisions available</span>
                </div>
                <label>
                  Set label
                  <input value={selectionLabel} onChange={(event) => setSelectionLabel(event.target.value)} />
                </label>
                <fieldset>
                  <legend>Exact Dataset revisions</legend>
                  {processedDatasets.map((item) => (
                    <label key={item.current_revision.id}>
                      <input
                        type="checkbox"
                        checked={selectedDatasetRevisions.includes(item.current_revision.id)}
                        onChange={() => toggleDataset(item.current_revision.id)}
                      />
                      <span>
                        Dataset {shortId(item.dataset_id)} · r{item.current_revision.revision_no}
                        <small>{item.current_revision.content.point_count} points · Test Run {shortId(item.test_run_id)}</small>
                      </span>
                    </label>
                  ))}
                  {!processedDatasets.length ? <p>No processed Dataset heads are available for this state.</p> : null}
                </fieldset>
                <div className="distribution-popover-actions">
                  <span>{selectedDatasetRevisions.length} selected</span>
                  <button
                    className="button secondary"
                    type="button"
                    disabled={action !== null || selectedDatasetRevisions.length < 2 || !selectionLabel.trim()}
                    onClick={() => void saveReplicateSelection()}
                  >
                    Save replicate set
                  </button>
                </div>
              </div>
            </details>
            <details className="distribution-command-detail distribution-replay-detail">
              <summary>Replay</summary>
              <div className="distribution-popover distribution-replay-popover">
                <div className="distribution-popover-heading">
                  <strong>Deterministic replay</strong>
                  <span>999 estimator-aware bootstrap refits · computation remains in Pa</span>
                </div>
                <label>PCG64 seed<input type="number" min="0" max="4294967295" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label>
                <label>Unit Profile ID<input value={profileId} onChange={(event) => setProfileId(event.target.value)} placeholder="Optional exact UUID" /></label>
                <label>Unit Profile revision ID<input value={profileRevisionId} onChange={(event) => setProfileRevisionId(event.target.value)} placeholder="Optional exact UUID" /></label>
                <label>Unit Profile SHA-256<input value={profileSha256} onChange={(event) => setProfileSha256(event.target.value)} placeholder="Optional exact digest" /></label>
                {profilePartiallyEntered ? <small className="field-error">Enter all three exact Unit Profile fields or clear all three.</small> : null}
              </div>
            </details>
            <button
              className={`button ${result ? "secondary" : "primary"} distribution-fit-action`}
              type="button"
              disabled={action !== null || !selection || profilePartiallyEntered}
              onClick={() => void fitCandidates()}
            >
              {action === "fit" ? "Fitting…" : result ? "Refit candidates" : "Fit candidates"}
            </button>
          </div>
        </div>

        {!state ? <p className="distribution-empty">Choose a Material State before fitting distributions.</p> : null}
        {error ? <p className="error-message" role="alert">{error}</p> : null}
        {notice ? <p className="notice-message" role="status">{notice}</p> : null}

        {result ? (
          <section className="distribution-ledger" aria-label="Distribution candidate comparison">
            <DistributionCdfPlot result={result} selectedFamily={selectedFamily} />
            <div className="distribution-ledger-heading">
              <div>
                <strong>Candidate ranking</strong>
                <span>2-parameter MLE · AICc primary · ΔAICc ≤ 2 co-recommended</span>
              </div>
              <div className="distribution-ledger-recommendation">
                <span>Recommendation</span>
                <strong>{result.recommended_families.length
                  ? result.recommended_families.map((item) => FAMILY_LABELS[item]).join(" + ")
                  : "No comparative recommendation"}</strong>
              </div>
            </div>
            <div className="distribution-table-scroll">
              <table className="distribution-candidate-table">
                <thead><tr><th>Candidate</th><th>Parameter estimates</th><th>AICc</th><th>ΔAICc</th><th>BIC</th><th>AD</th><th>Bootstrap p</th><th>Assessment</th><th>Selection</th></tr></thead>
                <tbody>{result.candidates.map((candidate) => {
                  const saved = currentDecision?.content.selected_family === candidate.family;
                  const active = decisionEditing && selectedFamily === candidate.family;
                  const rowClasses = [candidate.recommended ? "recommended" : "", saved || active ? "selected" : ""].filter(Boolean).join(" ");
                  return (
                    <tr key={candidate.family} className={rowClasses}>
                      <th scope="row"><strong>{FAMILY_LABELS[candidate.family]}</strong><small>{candidate.support === "positive" ? "x > 0" : "all real x"}</small></th>
                      <td>{parameterSummary(candidate, result)}</td>
                      <td>{metric(candidate.aicc)}</td>
                      <td>{metric(candidate.delta_aicc)}</td>
                      <td>{metric(candidate.bic)}</td>
                      <td>{metric(candidate.anderson_darling)}</td>
                      <td>{metric(candidate.bootstrap_p_value)}<small>{candidate.bootstrap_success_count}/{result.bootstrap_samples} refits</small></td>
                      <td><span className={`distribution-status ${candidate.status}`}>{candidate.status.replace("_", " ")}</span>{candidate.recommended ? <small>Recommended</small> : null}</td>
                      <td><button
                        className="distribution-row-action"
                        type="button"
                        aria-label={`${FAMILY_LABELS[candidate.family]} ${saved ? "edit selection" : "select"}`}
                        aria-pressed={saved || active}
                        disabled={candidate.status !== "succeeded" || action !== null}
                        onClick={() => beginDecision(candidate)}
                      >{saved ? "Edit" : active ? "Choosing" : "Select"}</button></td>
                    </tr>
                  );
                })}</tbody>
              </table>
            </div>

            {decisionEditing && selectedCandidate ? (
              <section className="distribution-decision-editor" aria-label="Selected distribution decision">
                <div className="distribution-decision-model">
                  <span>Explicit selection</span>
                  <strong>{FAMILY_LABELS[selectedCandidate.family]}</strong>
                  <small>{selectedCandidate.recommended ? "Within the recommended ΔAICc set" : "Outside the recommended ΔAICc set"}</small>
                </div>
                <label>
                  <span>Engineering rationale</span>
                  <textarea value={selectionReason} disabled={action !== null} onChange={(event) => setSelectionReason(event.target.value)} placeholder="Why is this distribution appropriate for the intended use?" />
                </label>
                <div className="distribution-decision-actions">
                  <button className="text-button" type="button" disabled={action !== null} onClick={() => setDecisionEditing(false)}>Cancel</button>
                  <button className="button primary" type="button" disabled={!selectionReason.trim() || action !== null} onClick={() => void saveDecision()}>{currentDecision ? "Save revised selection" : "Save exact selection"}</button>
                </div>
              </section>
            ) : currentDecision ? (
              <div className="distribution-decision-record" aria-label="Saved distribution selection">
                <span>Saved selection</span>
                <strong>{FAMILY_LABELS[currentDecision.content.selected_family]} · r{currentDecision.current_revision.revision_no}</strong>
                <p>{currentDecision.content.selection_reason}</p>
                <small>Exact Result r{result.current_revision.revision_no} · candidate {shortId(currentDecision.content.candidate_sha256)}</small>
              </div>
            ) : <p className="distribution-decision-note">Recommendation is evidence only. Select a successful row to record an explicit model and rationale.</p>}
          </section>
        ) : state ? (
          <div className="distribution-empty">
            <strong>No candidate comparison loaded</strong>
            <span>Choose an exact processed-replicate set and fit only when a probability model is needed.</span>
          </div>
        ) : null}

        <div className="distribution-evidence-bar">
          {result ? <details className="distribution-diagnostics"><summary>Diagnostics · {diagnosticCount}</summary><div className="distribution-warnings">
            {candidateWarnings.map((warning) => <p key={warning}>{warning.replaceAll("_", " ")}</p>)}
            {observationSummary ? <p>Observation quality: {observationSummary.quality.observed} observed · {observationSummary.quality.missing} missing · {observationSummary.quality.non_finite} non-finite · {observationSummary.quality.censored} censored.</p> : null}
            {observationSummary ? <p>Outlier assessment: {observationSummary.assessment.not_assessed} not assessed · {observationSummary.assessment.flagged} flagged · {observationSummary.assessment.not_flagged} not flagged. Every observation remains retained.</p> : null}
            <p>Censoring is unsupported and is never silently treated as an observed value.</p>
            {result.sample_count < result.small_sample_warning_below ? <p>Small sample: n 8–19 requires cautious interpretation.</p> : null}
          </div></details> : null}
          {plans.length ? <details className="distribution-history"><summary>Plan / Run history</summary><div className="distribution-history-controls">
            <label>Saved Plan<select value={selectedPlanId} onChange={(event) => void choosePlan(event.target.value)}>{plans.map((item) => <option key={item.statistical_plan_id} value={item.statistical_plan_id}>r{item.current_revision.revision_no} · seed {item.current_revision.content.scalar_distribution?.seed}</option>)}</select></label>
            <label>Committed Run<select value={result?.statistical_run_id ?? ""} onChange={(event) => void chooseRun(event.target.value)}><option value="">Choose Run</option>{runs.map((item) => <option key={item.statistical_run_id} value={item.statistical_run_id}>{new Date(item.started_at).toLocaleString()} · {item.status}</option>)}</select></label>
          </div></details> : null}
          {result ? <details className="distribution-provenance"><summary>Evidence / replay manifest</summary><dl><div><dt>Artifact</dt><dd>{shortId(result.artifact_sha256)}</dd></div><div><dt>Plan revision</dt><dd>{shortId(result.plan_revision_id)}</dd></div><div><dt>Selection revision</dt><dd>{shortId(result.selection_revision_id)}</dd></div><div><dt>Libraries</dt><dd>NumPy {result.runtime_manifest.numpy_version} · SciPy {result.runtime_manifest.scipy_version}</dd></div><div><dt>RNG</dt><dd>PCG64 · seed {result.seed}</dd></div><div><dt>Display</dt><dd>{result.unit_applications[0]?.unit_id ?? "Pa · no Unit Profile pin"}</dd></div></dl></details> : null}
        </div>
      </div>
    </div>
  );
}
