import type { ReactNode } from "react";

import "./modeling-fit-candidate-comparison.css";

export interface ModelingFitCandidateRow {
  id: string;
  label: string;
  selected: boolean;
  recommended?: boolean;
  disabled?: boolean;
  primaryValue: string;
  secondaryValue?: string;
  status?: string;
  warning?: string;
}

interface ModelingFitCandidateComparisonProps {
  title?: string;
  rows: ModelingFitCandidateRow[];
  primaryColumnLabel: string;
  secondaryColumnLabel?: string;
  rangeLabel?: string;
  selectionLocked?: boolean;
  onSelect: (id: string) => void;
  decision: ReactNode;
}

export function ModelingFitCandidateComparison({
  title = "Calculated models",
  rows,
  primaryColumnLabel,
  secondaryColumnLabel,
  rangeLabel,
  selectionLocked = false,
  onSelect,
  decision,
}: ModelingFitCandidateComparisonProps) {
  const availableCount = rows.filter((row) => !row.disabled).length;
  return (
    <section className="modeling-fit-decision-dock" aria-label="Model comparison and engineer selection">
      <section className="modeling-fit-candidate-comparison" aria-labelledby="modeling-fit-candidates-heading">
        <header className="modeling-fit-candidate-heading">
          <h2 id="modeling-fit-candidates-heading">{title}</h2>
          <span>{availableCount} available</span>
          {rangeLabel ? <strong>{rangeLabel}</strong> : null}
        </header>
        <div
          className="modeling-fit-candidate-table-wrap"
          role="region"
          aria-labelledby="modeling-fit-candidates-heading"
          tabIndex={0}
        >
          <table className="modeling-fit-candidate-table">
            <caption>Calculated model comparison</caption>
            <thead>
              <tr>
                <th scope="col">Model</th>
                <th scope="col">{primaryColumnLabel}</th>
                {secondaryColumnLabel ? <th scope="col">{secondaryColumnLabel}</th> : null}
                <th scope="col">Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className={row.selected ? "selected" : undefined}>
                  <th scope="row">
                    <label>
                      <input
                        type="radio"
                        name="fit-candidate-selection"
                        value={row.id}
                        checked={row.selected}
                        disabled={selectionLocked || row.disabled}
                        aria-label={`Select ${row.label}`}
                        onChange={() => onSelect(row.id)}
                      />
                      <span>
                        <strong>{row.label}</strong>
                        {row.recommended ? <em>Recommended</em> : null}
                      </span>
                    </label>
                  </th>
                  <td>{row.primaryValue}</td>
                  {secondaryColumnLabel ? <td>{row.secondaryValue ?? "—"}</td> : null}
                  <td>
                    <span>{row.status ?? (row.disabled ? "Not available" : "Calculated")}</span>
                    {row.warning ? <small>{row.warning}</small> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="modeling-fit-selection-pane" aria-label="Engineer selection">
        {decision}
      </section>
    </section>
  );
}
