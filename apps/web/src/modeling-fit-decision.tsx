import type { CommonCurveStage, CommonProcessingStep } from "./types";

function displayEngineeringValue(value: number, unit: string): string {
  if (unit === "Pa") return `${(value / 1e6).toPrecision(5)} MPa`;
  return `${Number(value.toPrecision(6))} ${unit}`;
}

export function HardeningCandidateEvidence({
  stage,
  step,
  onSelectPrimary,
}: {
  stage: CommonCurveStage;
  step: CommonProcessingStep;
  onSelectPrimary: (family: string) => void;
}) {
  const families = Array.isArray(step.options.families) ? step.options.families.map(String) : [];
  const primary = String(step.options.primary_family ?? "");
  const scalar = new Map(stage.scalar_results.map((item) => [item.key, item]));
  const evidence = families.map((family) => {
    const rmse = scalar.get(`${family}.rmse_pa`);
    const relative = scalar.get(`${family}.relative_rmse`);
    const parameterKeys = stage.scalar_results
      .map((item) => item.key)
      .filter((key) => key.startsWith(`${family}.parameter.`)
        && !key.endsWith(".lower")
        && !key.endsWith(".initial")
        && !key.endsWith(".upper"));
    const parameters = parameterKeys.map((key) => ({
      name: key.replace(`${family}.parameter.`, ""),
      value: scalar.get(key),
      lower: scalar.get(`${key}.lower`),
      upper: scalar.get(`${key}.upper`),
    }));
    const boundWarning = parameters.some(({ value, lower, upper }) => {
      if (!value || !lower || !upper) return false;
      const span = upper.value - lower.value;
      return span > 0 && Math.min(value.value - lower.value, upper.value - value.value) / span < 0.001;
    });
    return { family, rmse, relative, parameters, boundWarning };
  }).sort((left, right) =>
    (left.rmse?.value ?? Number.POSITIVE_INFINITY)
    - (right.rmse?.value ?? Number.POSITIVE_INFINITY));
  const best = evidence[0]?.family;
  const fitMinimum = Number(step.options.fit_minimum_strain);
  const fitMaximum = Number(step.options.fit_maximum_strain);
  const extrapolationMaximum = Number(step.options.extrapolation_maximum_strain);
  const applicability = Number.isFinite(fitMinimum) && Number.isFinite(fitMaximum)
    ? `${fitMinimum.toPrecision(3)}–${fitMaximum.toPrecision(3)} observed; to ${Number.isFinite(extrapolationMaximum) ? extrapolationMaximum.toPrecision(3) : "declared limit"} unobserved`
    : "Observed fit domain; declared bounded extrapolation";
  const selected = evidence.find((candidate) => candidate.family === primary);

  return (
    <section className="hardening-candidate-evidence" aria-label="Hardening candidate numerical comparison">
      <div className="candidate-evidence-heading">
        <div><p className="eyebrow">Calculated candidates</p><h4>Fit evidence</h4></div>
        <span>{evidence.length} equations</span>
      </div>
      <div className="fit-candidate-table-wrap">
        <table className="fit-candidate-table" aria-label="Hardening candidate comparison">
          <thead>
            <tr>
              <th scope="col">Decision</th><th scope="col">Candidate</th>
              <th scope="col">Status</th><th scope="col">Error</th>
              <th scope="col">Applicability</th><th scope="col">Warning</th>
            </tr>
          </thead>
          <tbody>
            {evidence.map((candidate) => (
              <tr className={primary === candidate.family ? "selected" : ""} key={candidate.family}>
                <td>
                  <button
                    type="button"
                    aria-pressed={primary === candidate.family}
                    aria-label={primary === candidate.family
                      ? `${candidate.family.replaceAll("_", "-")} selected`
                      : `Select ${candidate.family.replaceAll("_", "-")} candidate`}
                    onClick={() => onSelectPrimary(candidate.family)}
                  >
                    {primary === candidate.family ? "Selected" : "Select"}
                  </button>
                </td>
                <th scope="row">
                  <strong>{candidate.family.replaceAll("_", "-")}</strong>
                  <small>{candidate.family === best ? "Best calculated RMSE" : "Calculated candidate"}</small>
                </th>
                <td><span className={`fit-candidate-status ${candidate.rmse ? "ready" : "blocked"}`}>{candidate.rmse ? "Ready" : "Incomplete"}</span></td>
                <td>
                  <strong>{candidate.relative ? `${(candidate.relative.value * 100).toFixed(3)}%` : "—"}</strong>
                  <small>{candidate.rmse ? displayEngineeringValue(candidate.rmse.value, candidate.rmse.unit) : "No objective"}</small>
                </td>
                <td>{applicability}</td>
                <td>{candidate.boundWarning ? <span className="fit-candidate-warning">Near bound</span> : "None"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected ? (
        <details className="selected-candidate-parameters">
          <summary>Selected parameters and bounds</summary>
          <div className="candidate-parameter-table">
            {selected.parameters.map(({ name, value, lower, upper }) => (
              <div key={name}>
                <span>{name.replaceAll("_", " ")}</span>
                <strong>{value ? displayEngineeringValue(value.value, value.unit) : "—"}</strong>
                <small>{lower && upper
                  ? `${displayEngineeringValue(lower.value, lower.unit)} … ${displayEngineeringValue(upper.value, upper.unit)}`
                  : "bounds unavailable"}</small>
              </div>
            ))}
          </div>
        </details>
      ) : null}
      <p className="option-hint">
        Select one candidate, compare response, residual and tangent modulus, then record the
        engineering reason before commit.
      </p>
    </section>
  );
}

export function PronyCandidateEvidence({
  stage,
  step,
  onSelect,
}: {
  stage: CommonCurveStage;
  step: CommonProcessingStep;
  onSelect: (termCount: number) => void;
}) {
  const scalar = new Map(stage.scalar_results.map((item) => [item.key, item]));
  const counts = Array.isArray(step.options.candidate_term_counts)
    ? step.options.candidate_term_counts.map(Number)
    : [];
  const selectedCount = Number(
    scalar.get("prony_selected_term_count")?.value ?? step.options.selected_term_count ?? 0,
  );
  const candidates = counts.map((count) => ({
    count,
    bic: scalar.get(`prony_${count}_bic`),
    rmse: scalar.get(`prony_${count}_normalized_rmse`),
  })).sort((left, right) =>
    (left.bic?.value ?? Number.POSITIVE_INFINITY)
    - (right.bic?.value ?? Number.POSITIVE_INFINITY));
  const selectedTerms = Array.from({ length: Math.max(0, selectedCount) }, (_, index) => ({
    ordinal: index + 1,
    ratio: scalar.get(`prony_g_ratio_${index + 1}`)?.value,
    time: scalar.get(`prony_relaxation_time_${index + 1}`)?.value,
  }));
  const applicability = step.method_id === "polymer.dma_prony_fit_compare"
    ? "Observed frequency grid; no hidden extrapolation"
    : "Observed time grid; declared relaxation domain";

  return (
    <section className="prony-candidate-evidence" aria-label="Prony candidate numerical comparison">
      <div className="candidate-evidence-heading">
        <div><p className="eyebrow">Calculated candidates</p><h4>Prony evidence</h4></div>
        <span>{candidates.length} fits</span>
      </div>
      <div className="fit-candidate-table-wrap">
        <table className="fit-candidate-table" aria-label="Prony candidate comparison">
          <thead>
            <tr>
              <th scope="col">Decision</th><th scope="col">Candidate</th>
              <th scope="col">Status</th><th scope="col">Error</th>
              <th scope="col">Applicability</th><th scope="col">Warning</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate, index) => (
              <tr className={selectedCount === candidate.count ? "selected" : ""} key={candidate.count}>
                <td>
                  <button
                    type="button"
                    aria-pressed={selectedCount === candidate.count}
                    aria-label={selectedCount === candidate.count
                      ? `${candidate.count}-term Prony candidate selected`
                      : `Select ${candidate.count}-term Prony candidate`}
                    onClick={() => onSelect(candidate.count)}
                  >
                    {selectedCount === candidate.count ? "Selected" : "Select"}
                  </button>
                </td>
                <th scope="row">
                  <strong>{candidate.count} term{candidate.count === 1 ? "" : "s"}</strong>
                  <small>{index === 0 ? "Best calculated BIC" : "Calculated candidate"}</small>
                </th>
                <td><span className={`fit-candidate-status ${candidate.bic && candidate.rmse ? "ready" : "blocked"}`}>{candidate.bic && candidate.rmse ? "Ready" : "Incomplete"}</span></td>
                <td>
                  <strong>nRMSE {candidate.rmse ? `${(candidate.rmse.value * 100).toFixed(3)}%` : "—"}</strong>
                  <small>BIC {candidate.bic?.value.toFixed(2) ?? "—"}</small>
                </td>
                <td>{applicability}</td>
                <td>{candidate.bic && candidate.rmse
                  ? "None"
                  : <span className="fit-candidate-warning">Missing diagnostic</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedTerms.length ? (
        <div className="prony-selected-terms" role="table" aria-label="Selected Prony term parameters">
          <div className="prony-selected-term header" role="row">
            <span>Term</span><span>gᵢ ratio</span><span>τᵢ (s)</span>
          </div>
          {selectedTerms.map((term) => (
            <div className="prony-selected-term" role="row" key={term.ordinal}>
              <strong>{term.ordinal}</strong>
              <span>{term.ratio?.toPrecision(5) ?? "—"}</span>
              <span>{term.time?.toPrecision(5) ?? "—"}</span>
            </div>
          ))}
        </div>
      ) : null}
      <p className="option-hint">
        Select one fitted candidate, compare response and residual, then record the engineering
        reason before commit.
      </p>
    </section>
  );
}
