import type { CommonCurveStage, CommonProcessingStep } from "./types";
import {
  fitDecisionIdentityLabel,
  hardeningCandidateWarning,
  type FitDecisionSelection,
} from "./modeling-fit-decision-contract";

function displayEngineeringValue(value: number, unit: string): string {
  if (unit === "Pa") return `${(value / 1e6).toPrecision(5)} MPa`;
  return `${Number(value.toPrecision(6))} ${unit}`;
}

function titleCase(value: string): string {
  return value.replaceAll("_", "-");
}

function SelectedParameterInspector({
  selection,
  stage,
}: {
  selection: FitDecisionSelection;
  stage: CommonCurveStage;
}) {
  const scalar = new Map(stage.scalar_results.map((item) => [item.key, item]));
  const selectedLaws = selection.mode === "blend"
    ? [selection.primaryLaw, selection.secondaryLaw].filter(Boolean) as string[]
    : [selection.primaryLaw];
  const parameters = selection.actualTermCount !== undefined
    ? stage.scalar_results
      .filter((item) =>
        item.key === "prony_equilibrium_modulus"
        || item.key.startsWith("prony_g_ratio_")
        || item.key.startsWith("prony_relaxation_time_")
      )
      .map((item) => ({
        law: "generalized-Maxwell",
        name: item.key.replace("prony_", "").replaceAll("_", " "),
        value: item.value,
        unit: item.unit,
        lower: null,
        upper: null,
      }))
    : selectedLaws.flatMap((law) =>
      stage.scalar_results
        .filter((item) =>
          item.key.startsWith(`${law}.parameter.`)
          && !item.key.endsWith(".lower")
          && !item.key.endsWith(".upper")
          && !item.key.endsWith(".initial")
        )
        .map((item) => ({
          law: titleCase(law),
          name: item.key.replace(`${law}.parameter.`, "").replaceAll("_", " "),
          value: item.value,
          unit: item.unit,
          lower: scalar.get(`${item.key}.lower`)?.value ?? null,
          upper: scalar.get(`${item.key}.upper`)?.value ?? null,
        })),
    );
  const numerical = new Map((stage.fit_candidates ?? []).map((candidate) => [candidate.family, candidate]));
  const parametersWithEvidence = parameters.map((parameter) => {
    const law = parameter.law.toLowerCase().replaceAll("-", "_");
    const candidate = numerical.get(law);
    if (!candidate) return { ...parameter, initial: null, active: false, condition: null, rank: null };
    const parameterName = parameter.name.replaceAll(" ", "_");
    const index = candidate.parameter_names.indexOf(parameterName);
    return {
      ...parameter,
      initial: index >= 0 ? candidate.initial[index] : null,
      active: index >= 0 && candidate.active_bound.includes(parameterName),
      condition: candidate.jacobian_condition,
      rank: candidate.jacobian_rank,
    };
  });
  return <details className="selected-parameter-inspector" open>
    <summary>Model parameters ({parameters.length})</summary>
    {parameters.length ? <table className="fit-candidate-table" aria-label="Selected candidate parameters and bounds">
      <thead><tr><th scope="col">Law</th><th scope="col">Parameter</th><th scope="col">Unit</th><th scope="col">Lower</th><th scope="col">Initial</th><th scope="col">Fitted</th><th scope="col">Upper</th><th scope="col">Bound / condition</th></tr></thead>
      <tbody>{parametersWithEvidence.map((parameter) => <tr key={`${parameter.law}:${parameter.name}`}>
        <td>{parameter.law}</td>
        <th scope="row">{parameter.name}</th>
        <td>{parameter.unit}</td>
        <td>{parameter.lower === null ? "—" : displayEngineeringValue(parameter.lower, parameter.unit)}</td>
        <td>{parameter.initial === null ? "—" : displayEngineeringValue(parameter.initial, parameter.unit)}</td>
        <td>{displayEngineeringValue(parameter.value, parameter.unit)}</td>
        <td>{parameter.upper === null ? "—" : displayEngineeringValue(parameter.upper, parameter.unit)}</td>
        <td>{parameter.active ? "Exact active bound" : "Interior"}{parameter.rank === null || parameter.rank === undefined ? " · rank not provided" : ` · rank ${parameter.rank}`}{parameter.condition === null || parameter.condition === undefined ? " · condition not provided" : ` · cond ${parameter.condition.toPrecision(4)}`}</td>
      </tr>)}</tbody>
    </table> : <p className="option-hint">Parameter evidence is unavailable for this row. Re-run candidates; no fallback values will be saved.</p>}
  </details>;
}

function DecisionEditor({
  selection,
  stage,
  onChange,
}: {
  selection: FitDecisionSelection | null;
  stage: CommonCurveStage;
  onChange: (next: FitDecisionSelection) => void;
}) {
  if (!selection) return <p className="option-hint">No candidate is selected. A recommendation is calculated evidence, not an engineering decision.</p>;
  const next = (patch: Partial<FitDecisionSelection>) => onChange({ ...selection, ...patch });
  const label = fitDecisionIdentityLabel(selection);
  return <section className="selected-candidate-parameters" aria-label="Selected candidate decision">
    <div className="candidate-evidence-heading"><div><p className="eyebrow">Engineer decision</p><h4>Selected · {label}</h4></div><span>Not saved</span></div>
    <p className="option-hint">Model identity is fixed by the calculated row you selected. Change the preview laws or ratio and update candidates before selecting a different blend.</p>
    <p className="option-hint">Fit range: {selection.fitRange}. {selection.actualTermCount !== undefined ? `Recommended result uses ${selection.actualTermCount} term${selection.actualTermCount === 1 ? "" : "s"}; requested policy is ${selection.requestedTermPolicy ?? "not recorded"}.` : "Parameters and bounds remain in the contextual fit inspector."}</p>
    <SelectedParameterInspector selection={selection} stage={stage} />
    <label>Selection reason<textarea aria-label="Candidate selection reason" rows={3} value={selection.reason} onChange={(event) => next({ reason: event.target.value })} /></label>
    {selection.warning ? <label className="warning-acknowledgement"><input aria-label="Acknowledge selected candidate warning" type="checkbox" checked={selection.warningAcknowledged} onChange={(event) => next({ warningAcknowledged: event.target.checked })} />I acknowledge: {selection.warning}</label> : null}
  </section>;
}

export function HardeningCandidateEvidence({ stage, step, selection, onSelect, onChangeSelection }: {
  stage: CommonCurveStage; step: CommonProcessingStep; selection: FitDecisionSelection | null;
  onSelect: (selection: FitDecisionSelection) => void; onChangeSelection: (selection: FitDecisionSelection) => void;
}) {
  const families = Array.isArray(step.options.families) ? step.options.families.map(String) : [];
  const scalar = new Map(stage.scalar_results.map((item) => [item.key, item]));
  const fitMinimum = Number(step.options.fit_minimum_strain);
  const fitMaximum = Number(step.options.fit_maximum_strain);
  const extrapolationMaximum = Number(step.options.extrapolation_maximum_strain);
  const fitRange = Number.isFinite(fitMinimum) && Number.isFinite(fitMaximum) ? `${fitMinimum.toPrecision(3)}–${fitMaximum.toPrecision(3)} measured; to ${Number.isFinite(extrapolationMaximum) ? extrapolationMaximum.toPrecision(3) : "declared limit"} extrapolated` : "Observed fit domain; declared bounded extrapolation";
  const numerical = new Map((stage.fit_candidates ?? []).map((candidate) => [candidate.family, candidate]));
  const evidence = families.map((family) => {
    const rmse = scalar.get(`${family}.rmse_pa`); const relative = scalar.get(`${family}.relative_rmse`);
    const parameterKeys = stage.scalar_results.map((item) => item.key).filter((key) => key.startsWith(`${family}.parameter.`) && !key.endsWith(".lower") && !key.endsWith(".initial") && !key.endsWith(".upper"));
    // Warning truth comes from server-persisted candidate evidence.  Scalar
    // bounds are explanatory values only and must not manufacture a UI warning.
    const boundWarning = Boolean(numerical.get(family)?.active_bound.length);
    return { family, rmse, relative, boundWarning, numerical: numerical.get(family) };
  }).sort((left, right) => (left.relative?.value ?? Number.POSITIVE_INFINITY) - (right.relative?.value ?? Number.POSITIVE_INFINITY));
  const recommended = evidence[0]?.family;
  const primaryLaw = String(step.options.primary_family ?? "");
  const secondaryLaw = String(step.options.secondary_family ?? "");
  const primaryWeight = Number(step.options.primary_weight);
  const blend = primaryLaw && secondaryLaw && primaryLaw !== secondaryLaw
    && families.includes(primaryLaw) && families.includes(secondaryLaw)
    && Number.isFinite(primaryWeight) && primaryWeight > 0 && primaryWeight < 1
    ? {
        candidateKey: `${primaryLaw}+${secondaryLaw}`,
        displayLabel: `${titleCase(primaryLaw)} + ${titleCase(secondaryLaw)} ${Math.round(primaryWeight * 100)}/${Math.round((1 - primaryWeight) * 100)}`,
        primaryLaw,
        secondaryLaw,
        primaryWeight,
        metric: scalar.get(`${primaryLaw}.relative_rmse`),
        warning: Array.from(new Set(
          evidence
            .filter((candidate) => candidate.family === primaryLaw || candidate.family === secondaryLaw)
            .map((candidate) => hardeningCandidateWarning(candidate.family, candidate.boundWarning))
            .filter((item): item is string => Boolean(item)),
        )).join("; ") || undefined,
      }
    : null;
  const blendNumerical = blend ? numerical.get(blend.candidateKey) : undefined;
  return <section className="hardening-candidate-evidence" aria-label="Hardening candidate numerical comparison"><div className="candidate-evidence-heading"><div><p className="eyebrow">Calculated candidates</p><h4>Fit evidence</h4></div><span>{evidence.length} equations{blend ? " + 1 combined model" : ""}</span></div><div className="fit-candidate-table-wrap"><table className="fit-candidate-table" aria-label="Hardening candidate comparison"><thead><tr><th scope="col">Decision</th><th scope="col">Model / law</th><th scope="col">Recommendation</th><th scope="col">Metric</th><th scope="col">Fit / extrapolation range</th><th scope="col">Stability</th><th scope="col">Compatibility</th><th scope="col">Warning</th></tr></thead><tbody>{evidence.map((candidate) => { const selected = selection?.candidateKey === candidate.family; const warning = hardeningCandidateWarning(candidate.family, candidate.boundWarning); const fit = candidate.numerical; return <tr className={selected ? "selected" : ""} key={candidate.family}><td><button type="button" aria-pressed={selected} aria-label={selected ? `${titleCase(candidate.family)} candidate selected` : `Select ${titleCase(candidate.family)} candidate`} onClick={() => onSelect({ candidateKey: candidate.family, displayLabel: titleCase(candidate.family), mode: "single", primaryLaw: candidate.family, reason: "", warningAcknowledged: false, fitRange, warning })}>{selected ? "Selected" : "Select candidate"}</button></td><th scope="row"><strong>{titleCase(candidate.family)}</strong></th><td>{candidate.family === recommended ? "Recommended · lowest relative RMSE" : "—"}</td><td><strong>{candidate.relative ? `${(candidate.relative.value * 100).toFixed(3)}%` : "—"}</strong><small>{candidate.rmse ? `RMSE · ${displayEngineeringValue(candidate.rmse.value, candidate.rmse.unit)}` : "No objective"}</small>{fit ? <small>response {fit.response.length} · residual {fit.residual.length} · tangent {fit.tangent.length}</small> : <small>No persisted numerical evidence</small>}</td><td>{fitRange}</td><td>{fit ? `${fit.convergence ? "Converged" : "Not converged"} · status ${fit.optimizer_status} · ${fit.nfev} evals · rank ${fit.jacobian_rank} · condition ${fit.jacobian_condition ?? "not provided"}` : candidate.family === "ghosh" ? "Structural non-identifiability" : candidate.boundWarning ? "Bound check" : "Missing numerical evidence"}</td><td>{fit ? `${fit.identifiability}; uncertainty ${fit.uncertainty}; active bound ${fit.active_bound.length ? fit.active_bound.join(", ") : "none"}` : "Missing evidence · selection blocked"}</td><td>{warning ?? "None"}</td></tr>; })}{blend ? <tr className={selection?.candidateKey === blend.candidateKey ? "selected" : ""}><td><button type="button" aria-pressed={selection?.candidateKey === blend.candidateKey} aria-label={selection?.candidateKey === blend.candidateKey ? `${blend.displayLabel} candidate selected` : `Select ${blend.displayLabel} candidate`} onClick={() => onSelect({ candidateKey: blend.candidateKey, displayLabel: blend.displayLabel, mode: "blend", primaryLaw: blend.primaryLaw, secondaryLaw: blend.secondaryLaw, primaryWeight: blend.primaryWeight, reason: "", warningAcknowledged: false, fitRange, warning: blend.warning })}>{selection?.candidateKey === blend.candidateKey ? "Selected" : "Select candidate"}</button></td><th scope="row"><strong>{blend.displayLabel}</strong><small>Combined model</small></th><td>—</td><td><strong>{blendNumerical ? `${(blendNumerical.relative_rmse * 100).toFixed(3)}%` : "—"}</strong><small>{blendNumerical ? `RMSE · ${displayEngineeringValue(blendNumerical.rmse_pa, "Pa")}` : "Missing blend evidence"}</small></td><td>{fitRange}</td><td>{blendNumerical ? `${blendNumerical.convergence ? "Converged" : "Not converged"} · status ${blendNumerical.optimizer_status} · ${blendNumerical.nfev} evals · rank ${blendNumerical.jacobian_rank} · condition ${blendNumerical.jacobian_condition ?? "not provided"}` : "Missing numerical evidence"}</td><td>{blendNumerical ? `${blendNumerical.identifiability}; uncertainty ${blendNumerical.uncertainty}; active bound ${blendNumerical.active_bound.length ? blendNumerical.active_bound.join(", ") : "none"}` : "Missing evidence · selection blocked"}</td><td>{blend.warning ?? "None"}</td></tr> : null}</tbody></table></div><DecisionEditor selection={selection} stage={stage} onChange={onChangeSelection}/></section>;
}

export function PronyCandidateEvidence({ stage, step, selection, onSelect, onChangeSelection }: {
  stage: CommonCurveStage; step: CommonProcessingStep; selection: FitDecisionSelection | null;
  onSelect: (selection: FitDecisionSelection) => void; onChangeSelection: (selection: FitDecisionSelection) => void;
}) {
  const scalar = new Map(stage.scalar_results.map((item) => [item.key, item]));
  const counts = Array.isArray(step.options.candidate_term_counts) ? step.options.candidate_term_counts.map(Number) : [];
  const actualCount = Number(scalar.get("prony_selected_term_count")?.value ?? 0);
  const candidates = counts.map((count) => ({ count, bic: scalar.get(`prony_${count}_bic`), rmse: scalar.get(`prony_${count}_normalized_rmse`) })).sort((left, right) => (left.bic?.value ?? Number.POSITIVE_INFINITY) - (right.bic?.value ?? Number.POSITIVE_INFINITY));
  const fitRange = step.method_id === "polymer.dma_prony_fit_compare" ? "Measured frequency grid; no extrapolation" : "Measured time grid; no extrapolation";
  const requestedPolicy = String(step.options.selection_mode ?? "automatic_bic");
  return <section className="prony-candidate-evidence" aria-label="Prony candidate numerical comparison"><div className="candidate-evidence-heading"><div><p className="eyebrow">Calculated candidates</p><h4>Prony evidence</h4></div><span>{candidates.length} fits</span></div><div className="fit-candidate-table-wrap"><table className="fit-candidate-table" aria-label="Prony candidate comparison"><thead><tr><th scope="col">Decision</th><th scope="col">Model / law</th><th scope="col">Recommendation</th><th scope="col">Metric</th><th scope="col">Fit / extrapolation range</th><th scope="col">Stability</th><th scope="col">Compatibility</th><th scope="col">Warning</th></tr></thead><tbody>{candidates.map((candidate, index) => { const isActualResult = candidate.count === actualCount; const selected = selection?.candidateKey === `prony:${candidate.count}`; const warning = !candidate.bic || !candidate.rmse ? "Missing diagnostic" : undefined; return <tr className={selected ? "selected" : ""} key={candidate.count}><td>{isActualResult ? <button type="button" aria-pressed={selected} aria-label={selected ? `${candidate.count}-term Prony candidate selected` : `Select ${candidate.count}-term Prony candidate`} onClick={() => onSelect({ candidateKey: `prony:${candidate.count}`, displayLabel: `${candidate.count}-term Prony`, mode: "single", primaryLaw: "generalized_maxwell", actualTermCount: candidate.count, requestedTermPolicy: requestedPolicy, reason: "", warningAcknowledged: false, fitRange, warning })}>{selected ? "Selected" : "Select candidate"}</button> : <span title="Change the requested policy and run fit before selecting this result.">Run fit to select</span>}</td><th scope="row"><strong>{candidate.count} term{candidate.count === 1 ? "" : "s"}</strong></th><td>{isActualResult ? `Recommended · ${actualCount} term${actualCount === 1 ? "" : "s"}` : index === 0 ? "Lowest calculated BIC" : "—"}</td><td><strong>nRMSE {candidate.rmse ? `${(candidate.rmse.value * 100).toFixed(3)}%` : "—"}</strong><small>BIC {candidate.bic?.value.toFixed(2) ?? "—"}</small></td><td>{fitRange}</td><td>{warning ? "Incomplete" : "Converged"}</td><td>{warning ? "Missing compatibility evidence · selection blocked" : "Compatible with current processing route"}</td><td>{warning ?? "None"}</td></tr>; })}</tbody></table></div><DecisionEditor selection={selection} stage={stage} onChange={onChangeSelection}/></section>;
}
