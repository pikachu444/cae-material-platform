import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceTensileReplicateSelection,
  listReferenceTensileReplicateSelections,
  previewDatasetCurve,
  reviseReferenceTensileReplicateSelection,
} from "./api";
import type {
  CurvePreview,
  DatasetResponse,
  MaterialStateResponse,
  TensileReplicateSelectionResponse,
} from "./types";

const COLORS = ["#55d6be", "#ffb347", "#7aa7ff", "#e77cff", "#ff6b6b", "#9cdb5d"];

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return "The replicate Selection could not be completed.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function Overlay({ curves }: { curves: CurvePreview[] }) {
  const allPoints = curves.flatMap((curve) => curve.points);
  if (!allPoints.length) return null;
  const xs = allPoints.map((point) => point.engineering_strain);
  const ys = allPoints.map((point) => point.engineering_stress);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  const points = (curve: CurvePreview) => curve.points.map((point) => {
    const x = 48 + ((point.engineering_strain - minX) / xSpan) * 654;
    const y = 240 - ((point.engineering_stress - minY) / ySpan) * 222;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
  return (
    <section className="curve-panel" aria-label="Pinned replicate tensile curve overlay">
      <div className="curve-heading">
        <div><p className="eyebrow">Pinned replicate overlay</p><h5>Independent immutable curves</h5></div>
        <span className="reference-chip">n={curves.length}</span>
      </div>
      <svg className="curve-plot replicate-overlay" viewBox="0 0 720 280" role="img">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        {curves.map((curve, index) => (
          <polyline
            key={curve.dataset_revision_id}
            points={points(curve)}
            style={{ stroke: COLORS[index % COLORS.length] }}
          />
        ))}
        <text x="340" y="278">engineering strain (1)</text>
        <text x="14" y="144" transform="rotate(-90 14 144)">engineering stress (Pa)</text>
      </svg>
      <ul className="qc-list">
        {curves.map((curve, index) => (
          <li key={curve.dataset_revision_id}>
            <span style={{ color: COLORS[index % COLORS.length] }}>●</span>{" "}
            member {index + 1}: {shortId(curve.dataset_revision_id)} · {curve.point_count} points
          </li>
        ))}
      </ul>
    </section>
  );
}

interface Props {
  config: ApiConfig;
  state: MaterialStateResponse;
  datasets: DatasetResponse[];
}

export function ReferenceReplicateSelectionWorkbench({ config, state, datasets }: Props) {
  const eligible = useMemo(() => datasets.filter((dataset) => (
    dataset.current_revision.content.representation === "normalized"
    || dataset.current_revision.content.representation === "processed"
  )), [datasets]);
  const [selectedRevisionIds, setSelectedRevisionIds] = useState<string[]>([]);
  const [selections, setSelections] = useState<TensileReplicateSelectionResponse[]>([]);
  const [selectedSelectionId, setSelectedSelectionId] = useState("");
  const [curves, setCurves] = useState<CurvePreview[]>([]);
  const [label, setLabel] = useState("Reference tensile replicate set");
  const [reason, setReason] = useState("Pin independent tensile Dataset revisions");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedSelection = selections.find((item) => item.selection_id === selectedSelectionId);

  useEffect(() => {
    void listReferenceTensileReplicateSelections(config, state.material_state_id)
      .then((result) => {
        setSelections(result.data.items);
        setSelectedSelectionId((current) => current || result.data.items[0]?.selection_id || "");
      })
      .catch((cause: unknown) => setError(messageFor(cause)));
  }, [config, state.material_state_id]);

  useEffect(() => {
    const members = selectedSelection?.current_revision.content.members ?? [];
    setSelectedRevisionIds(members.map((member) => member.dataset_revision_id));
    if (!members.length) {
      setCurves([]);
      return;
    }
    let current = true;
    void Promise.all(members.map((member) => previewDatasetCurve(
      config, member.dataset_revision_id, 1000,
    ))).then((results) => {
      if (current) setCurves(results.map((result) => result.data));
    }).catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => { current = false; };
  }, [config, selectedSelection]);

  function toggle(revisionId: string): void {
    setSelectedRevisionIds((current) => current.includes(revisionId)
      ? current.filter((value) => value !== revisionId)
      : [...current, revisionId]);
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (selectedRevisionIds.length < 2) {
      setError("Select at least two independent Test Run Dataset revisions.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = selectedSelection
        ? await reviseReferenceTensileReplicateSelection(config, selectedSelection.selection_id, {
            expected_current_revision_id: selectedSelection.current_revision.id,
            dataset_revision_ids: selectedRevisionIds,
            change_reason: reason.trim(),
          })
        : await createReferenceTensileReplicateSelection(config, {
            classification: state.current_revision.classification,
            selection_label: label.trim(),
            dataset_revision_ids: selectedRevisionIds,
            change_reason: reason.trim(),
          });
      setSelections((current) => [
        result.data,
        ...current.filter((item) => item.selection_id !== result.data.selection_id),
      ]);
      setSelectedSelectionId(result.data.selection_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workflow-step">
      <strong>6A. Pin independent replicates as one immutable Selection</strong>
      <p className="form-hint">
        Each member pins a concrete normalized or processed Dataset revision from a distinct
        Test Run. Earlier Selection revisions and source curves are never changed.
      </p>
      {eligible.length < 2 ? (
        <p className="muted">Create at least two independent Test Run Datasets for this Material State.</p>
      ) : (
        <form className="form-stack" onSubmit={(event) => void submit(event)}>
          <fieldset>
            <legend>Dataset revision members</legend>
            {eligible.map((dataset) => (
              <label key={dataset.dataset_id} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={selectedRevisionIds.includes(dataset.current_revision.id)}
                  onChange={() => toggle(dataset.current_revision.id)}
                />
                {shortId(dataset.current_revision.id)} · {dataset.current_revision.content.representation}
                {" · "}{dataset.current_revision.content.point_count} points
              </label>
            ))}
          </fieldset>
          {!selectedSelection ? (
            <label>Selection label<input value={label} onChange={(event) => setLabel(event.target.value)} required /></label>
          ) : null}
          <label>Change reason<input value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
          <button className="button secondary" type="submit" disabled={busy}>
            {busy ? "Committing Selection…" : selectedSelection ? "Append membership revision" : "Create replicate Selection"}
          </button>
        </form>
      )}
      {selections.length ? (
        <label>
          Replicate Selection
          <select value={selectedSelectionId} onChange={(event) => setSelectedSelectionId(event.target.value)}>
            <option value="">Create a new Selection</option>
            {selections.map((selection) => (
              <option key={selection.selection_id} value={selection.selection_id}>
                {selection.selection_label} · r{selection.current_revision.revision_no} · n={selection.current_revision.content.member_count}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {curves.length ? <Overlay curves={curves} /> : null}
    </div>
  );
}
