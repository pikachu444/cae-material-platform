import { useEffect, useMemo, useRef, useState } from "react";

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
  const plan = plans.find((item) => item.statistical_plan_id === selectedPlanId) ?? null;
  const currentDecision = decisions[0] ?? null;
  const selectableCandidates = result?.candidates.filter((item) => item.status === "succeeded") ?? [];
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
      setNotice("Selected model and reason saved as an exact immutable revision.");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <div
      ref={workbenchRef}
      className="scalar-distribution-workbench"
      id="scalar-distribution-dock"
      tabIndex={-1}
      aria-label="Peak stress distribution candidate comparison"
    >
      <header className="distribution-dock-heading">
        <div>
          <p className="eyebrow">Replicate analysis · saved comparison</p>
          <h3>Peak stress distribution candidates</h3>
          <p>Normal, Lognormal, and Weibull are compared on every exact selected observation.</p>
        </div>
        <button className="text-button" type="button" onClick={onClose}>Close</button>
      </header>

      {!state ? <p className="distribution-empty">Choose a Material State before fitting distributions.</p> : null}
      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {notice ? <p className="notice-message" role="status">{notice}</p> : null}

      <div className="distribution-workflow-grid">
        <section className="distribution-inputs" aria-label="Exact replicate input">
          <div className="distribution-section-heading">
            <div><span>1</span><strong>Exact processed replicates</strong></div>
            <small>{processedDatasets.length} available</small>
          </div>
          <label>
            Saved Selection
            <select
              aria-label="Saved processed replicate Selection"
              value={selectedSelectionId}
              disabled={action !== null}
              onChange={(event) => void chooseSelection(event.target.value)}
            >
              <option value="">Choose or create a Selection</option>
              {processedSelections.map((item) => (
                <option key={item.selection_id} value={item.selection_id}>
                  {item.selection_label} · r{item.current_revision.revision_no} · {item.current_revision.content.member_count} members · {selectionUsesCurrentProcessedHeads(item, datasets) ? "current processed heads" : "historical exact revisions"}
                </option>
              ))}
            </select>
          </label>
          <details className="distribution-create-selection">
            <summary>Create from processed Dataset heads</summary>
            <label>
              Selection label
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
            <button
              className="button secondary"
              type="button"
              disabled={action !== null || selectedDatasetRevisions.length < 2 || !selectionLabel.trim()}
              onClick={() => void saveReplicateSelection()}
            >
              Save exact Selection
            </button>
          </details>
          {selection ? (
            <div className="distribution-input-summary">
              <strong>{selection.current_revision.content.member_count} observations retained</strong>
              <span>{selectionUsesCurrentProcessedHeads(selection, datasets)
                ? "Current processed heads · no alignment, deletion, or complete-case filtering"
                : "Historical exact processed revisions · saved Plan, Run, and Result remain readable"}</span>
            </div>
          ) : null}
          <details className="advanced-workflow-settings distribution-advanced">
            <summary>Advanced · replay and display profile</summary>
            <label>PCG64 seed<input type="number" min="0" max="4294967295" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label>
            <p>999 estimator-aware parametric bootstrap refits. Computation remains in Pa.</p>
            <label>Unit Profile ID<input value={profileId} onChange={(event) => setProfileId(event.target.value)} placeholder="Optional exact UUID" /></label>
            <label>Unit Profile revision ID<input value={profileRevisionId} onChange={(event) => setProfileRevisionId(event.target.value)} placeholder="Optional exact UUID" /></label>
            <label>Unit Profile SHA-256<input value={profileSha256} onChange={(event) => setProfileSha256(event.target.value)} placeholder="Optional exact digest" /></label>
            {profilePartiallyEntered ? <small className="field-error">Enter all three exact Unit Profile fields or clear all three.</small> : null}
          </details>
          <button
            className="button primary"
            type="button"
            disabled={action !== null || !selection || profilePartiallyEntered}
            onClick={() => void fitCandidates()}
          >
            {action === "fit" ? "Fitting 999 refits per candidate…" : "Fit and save candidates"}
          </button>
        </section>

        <section className="distribution-comparison" aria-label="Distribution candidate comparison">
          <div className="distribution-section-heading">
            <div><span>2</span><strong>Candidate comparison</strong></div>
            <small>{result ? `n = ${result.sample_count}` : "No saved result"}</small>
          </div>
          {plans.length ? (
            <div className="distribution-history-controls">
              <label>Saved Plan<select value={selectedPlanId} onChange={(event) => void choosePlan(event.target.value)}>{plans.map((item) => <option key={item.statistical_plan_id} value={item.statistical_plan_id}>r{item.current_revision.revision_no} · seed {item.current_revision.content.scalar_distribution?.seed}</option>)}</select></label>
              <label>Committed Run<select value={result?.statistical_run_id ?? ""} onChange={(event) => void chooseRun(event.target.value)}><option value="">Choose Run</option>{runs.map((item) => <option key={item.statistical_run_id} value={item.statistical_run_id}>{new Date(item.started_at).toLocaleString()} · {item.status}</option>)}</select></label>
            </div>
          ) : null}
          {result ? (
            <>
              <div className="distribution-recommendation">
                <span>Recommendation · AICc Δ ≤ 2</span>
                <strong>{result.recommended_families.length ? result.recommended_families.map((item) => FAMILY_LABELS[item]).join(" + ") : "No comparative recommendation"}</strong>
                <small>At least two successful candidates are required. Recommendation never selects a model.</small>
              </div>
              <div className="distribution-table-scroll">
                <table className="distribution-candidate-table">
                  <thead><tr><th>Candidate</th><th>Parameters</th><th>AICc</th><th>ΔAICc</th><th>BIC</th><th>AD</th><th>Bootstrap p</th><th>State</th></tr></thead>
                  <tbody>{result.candidates.map((candidate) => (
                    <tr key={candidate.family} className={candidate.recommended ? "recommended" : ""}>
                      <th scope="row">{FAMILY_LABELS[candidate.family]}<small>{candidate.support === "positive" ? "x > 0" : "all real x"}</small></th>
                      <td>{parameterSummary(candidate, result)}</td>
                      <td>{metric(candidate.aicc)}</td>
                      <td>{metric(candidate.delta_aicc)}</td>
                      <td>{metric(candidate.bic)}</td>
                      <td>{metric(candidate.anderson_darling)}</td>
                      <td>{metric(candidate.bootstrap_p_value)}<small>{candidate.bootstrap_success_count}/{result.bootstrap_samples} refits</small></td>
                      <td><span className={`distribution-status ${candidate.status}`}>{candidate.status.replace("_", " ")}</span>{candidate.recommended ? <small>Recommended</small> : null}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <div className="distribution-warnings">
                {Array.from(new Set(result.candidates.flatMap((item) => [...item.warnings, ...item.reason_codes.filter((code) => code !== "fit_succeeded")]))).map((warning) => <p key={warning}>{warning.replaceAll("_", " ")}</p>)}
                {observationSummary ? <p>Observation quality: {observationSummary.quality.observed} observed · {observationSummary.quality.missing} missing · {observationSummary.quality.non_finite} non-finite · {observationSummary.quality.censored} censored.</p> : null}
                {observationSummary ? <p>Outlier assessment: {observationSummary.assessment.not_assessed} not assessed · {observationSummary.assessment.flagged} flagged · {observationSummary.assessment.not_flagged} not flagged. Every observation remains retained.</p> : null}
                <p>Censoring is unsupported and is never silently treated as an observed value.</p>
                {result.sample_count < result.small_sample_warning_below ? <p>Small sample: n 8–19 requires cautious interpretation.</p> : null}
              </div>
            </>
          ) : <div className="distribution-empty"><strong>Fit candidates from one saved processed-replicate Selection.</strong><span>n &lt; 8 and unsupported support are preserved as explicit not-eligible candidate states.</span></div>}
        </section>

        <section className="distribution-decision" aria-label="Selected distribution decision">
          <div className="distribution-section-heading">
            <div><span>3</span><strong>Selected model</strong></div>
            <small>{currentDecision ? `r${currentDecision.current_revision.revision_no}` : "Not selected"}</small>
          </div>
          <label>
            Successful candidate
            <select value={selectedFamily} disabled={!result || action !== null} onChange={(event) => setSelectedFamily(event.target.value as DistributionFamily | "")}>
              <option value="">Choose explicitly</option>
              {selectableCandidates.map((candidate) => <option key={candidate.family} value={candidate.family}>{FAMILY_LABELS[candidate.family]}{candidate.recommended ? " · recommended" : ""}</option>)}
            </select>
          </label>
          <label>
            Selection reason
            <textarea value={selectionReason} disabled={!result || action !== null} onChange={(event) => setSelectionReason(event.target.value)} placeholder="Record why this candidate is appropriate for the intended use." />
          </label>
          <button className="button primary" type="button" disabled={!result || !selectedFamily || !selectionReason.trim() || action !== null} onClick={() => void saveDecision()}>{currentDecision ? "Save revised selection" : "Save selection"}</button>
          {currentDecision ? <div className="distribution-saved-decision"><strong>{FAMILY_LABELS[currentDecision.content.selected_family]}</strong><span>{currentDecision.content.selection_reason}</span><small>Exact Result r{result?.current_revision.revision_no} · candidate {shortId(currentDecision.content.candidate_sha256)}</small></div> : <p className="distribution-decision-note">A recommendation is evidence, not a saved selection. The explicit reason is required and reloads with the exact candidate digest.</p>}
          {result ? <details className="distribution-provenance"><summary>Evidence and replay manifest</summary><dl><div><dt>Artifact</dt><dd>{shortId(result.artifact_sha256)}</dd></div><div><dt>Plan revision</dt><dd>{shortId(result.plan_revision_id)}</dd></div><div><dt>Selection revision</dt><dd>{shortId(result.selection_revision_id)}</dd></div><div><dt>Libraries</dt><dd>NumPy {result.runtime_manifest.numpy_version} · SciPy {result.runtime_manifest.scipy_version}</dd></div><div><dt>RNG</dt><dd>PCG64 · seed {result.seed}</dd></div><div><dt>Display</dt><dd>{result.unit_applications[0]?.unit_id ?? "Pa · no Unit Profile pin"}</dd></div></dl></details> : null}
        </section>
      </div>
    </div>
  );
}
