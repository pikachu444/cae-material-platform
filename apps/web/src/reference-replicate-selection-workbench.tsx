import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceTensileAlignmentRecipe,
  createReferenceTensileReplicateSelection,
  executeReferenceTensileAlignment,
  listReferenceTensileReplicateSelections,
  previewDatasetCurve,
  reviseReferenceTensileReplicateSelection,
} from "./api";
import type {
  CurvePreview,
  DatasetResponse,
  MaterialStateResponse,
  PropertySetResponse,
  TensileReplicateSelectionResponse,
} from "./types";
import { ReferenceReplicateStatisticsWorkbench } from "./reference-replicate-statistics-workbench";

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
  propertySet?: PropertySetResponse;
}

export function ReferenceReplicateSelectionWorkbench({ config, state, datasets, propertySet }: Props) {
  const eligible = useMemo(() => datasets.filter((dataset) => (
    dataset.current_revision.content.representation === "normalized"
    || dataset.current_revision.content.representation === "processed"
  )), [datasets]);
  const [selectedRevisionIds, setSelectedRevisionIds] = useState<string[]>([]);
  const [selections, setSelections] = useState<TensileReplicateSelectionResponse[]>([]);
  const [selectedSelectionId, setSelectedSelectionId] = useState("");
  const [curves, setCurves] = useState<CurvePreview[]>([]);
  const [alignedCurves, setAlignedCurves] = useState<CurvePreview[]>([]);
  const [alignedDatasetRevisionIds, setAlignedDatasetRevisionIds] = useState<string[]>([]);
  const [label, setLabel] = useState("Reference tensile replicate set");
  const [reason, setReason] = useState("Pin independent tensile Dataset revisions");
  const [busy, setBusy] = useState(false);
  const [aligning, setAligning] = useState(false);
  const [alignmentLabel, setAlignmentLabel] = useState("Common tensile replicate grid");
  const [gridStart, setGridStart] = useState("0");
  const [gridEnd, setGridEnd] = useState("0.02");
  const [gridPointCount, setGridPointCount] = useState("201");
  const [alignmentReason, setAlignmentReason] = useState(
    "Align pinned tensile replicates on an explicit common grid",
  );
  const [alignmentSummary, setAlignmentSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedSelection = selections.find((item) => item.selection_id === selectedSelectionId);
  const selectedProcessedRevisionIds = selectedSelection?.current_revision.content.members.every(
    (member) => eligible.some((dataset) => (
      dataset.current_revision.id === member.dataset_revision_id
      && dataset.current_revision.content.representation === "processed"
    )),
  )
    ? selectedSelection.current_revision.content.members.map((member) => member.dataset_revision_id)
    : [];
  const statisticsInputRevisionIds = alignedDatasetRevisionIds.length
    ? alignedDatasetRevisionIds
    : selectedProcessedRevisionIds;
  const pinnedStatisticsSelection = alignedDatasetRevisionIds.length
    ? undefined
    : selectedProcessedRevisionIds.length
      ? selectedSelection
      : undefined;

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

  useEffect(() => {
    if (curves.length < 2) return;
    const start = Math.max(...curves.map((item) => item.points[0]?.engineering_strain ?? 0));
    const end = Math.min(...curves.map(
      (item) => item.points[item.points.length - 1]?.engineering_strain ?? 0,
    ));
    if (end > start) {
      setGridStart(String(start));
      setGridEnd(String(end));
    }
  }, [curves]);

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

  async function align(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedSelection) return;
    const start = Number(gridStart);
    const end = Number(gridEnd);
    const pointCount = Number(gridPointCount);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      setError("Enter a finite common-grid end greater than its start.");
      return;
    }
    if (!Number.isInteger(pointCount) || pointCount < 2 || pointCount > 100_000) {
      setError("Grid point count must be an integer from 2 to 100000.");
      return;
    }
    setAligning(true);
    setError(null);
    setAlignmentSummary(null);
    try {
      const recipe = await createReferenceTensileAlignmentRecipe(config, {
        classification: selectedSelection.current_revision.classification,
        content: {
          recipe_label: alignmentLabel.trim(),
          grid_start_engineering_strain: start,
          grid_end_engineering_strain: end,
          grid_point_count: pointCount,
          domain_policy: "intersection",
          interpolation_policy: "piecewise_linear",
          extrapolation_policy: "reject",
        },
        change_reason: alignmentReason.trim(),
      });
      const batch = await executeReferenceTensileAlignment(config, {
        selection_id: selectedSelection.selection_id,
        selection_revision_id: selectedSelection.current_revision.id,
        recipe_id: recipe.data.recipe_id,
        recipe_revision_id: recipe.data.current_revision.id,
        change_reason: alignmentReason.trim(),
      });
      const previews = await Promise.all(batch.data.runs.map((run) => {
        if (!run.output_dataset_revision_id) {
          throw new Error("Alignment run did not commit an output Dataset revision.");
        }
        return previewDatasetCurve(config, run.output_dataset_revision_id, 1000);
      }));
      setAlignedCurves(previews.map((result) => result.data));
      setAlignedDatasetRevisionIds(batch.data.runs.map((run) => run.output_dataset_revision_id!));
      setAlignmentSummary(
        `Batch ${shortId(batch.data.alignment_batch_id)} committed ${batch.data.member_count} `
        + `processed Dataset revisions on [${batch.data.common_domain_start}, `
        + `${batch.data.common_domain_end}].`,
      );
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAligning(false);
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
      {selectedSelection ? (
        <form className="form-stack alignment-workbench" onSubmit={(event) => void align(event)}>
          <strong>6B. Commit separate processed revisions on one explicit grid</strong>
          <p className="form-hint">
            Domain=intersection, interpolation=piecewise linear, extrapolation=reject. All four
            choices and the exact grid are persisted in the immutable Recipe revision.
          </p>
          <label>
            Recipe label
            <input value={alignmentLabel} onChange={(event) => setAlignmentLabel(event.target.value)} required />
          </label>
          <div className="form-grid three-columns">
            <label>Grid start (strain, 1)<input type="number" step="any" min="0" value={gridStart} onChange={(event) => setGridStart(event.target.value)} required /></label>
            <label>Grid end (strain, 1)<input type="number" step="any" min="0" value={gridEnd} onChange={(event) => setGridEnd(event.target.value)} required /></label>
            <label>Point count<input type="number" min="2" max="100000" step="1" value={gridPointCount} onChange={(event) => setGridPointCount(event.target.value)} required /></label>
          </div>
          <label>
            Change reason
            <input value={alignmentReason} onChange={(event) => setAlignmentReason(event.target.value)} required />
          </label>
          <button className="button secondary" type="submit" disabled={aligning}>
            {aligning ? "Committing aligned revisions..." : "Create Recipe and align all members"}
          </button>
          {alignmentSummary ? <div className="success-banner">{alignmentSummary}</div> : null}
        </form>
      ) : null}
      {alignedCurves.length ? <Overlay curves={alignedCurves} /> : null}
      {statisticsInputRevisionIds.length ? (
        <ReferenceReplicateStatisticsWorkbench
          config={config}
          classification={state.current_revision.classification}
          alignedDatasetRevisionIds={statisticsInputRevisionIds}
          pinnedSelection={pinnedStatisticsSelection}
          state={state}
          propertySet={propertySet}
          datasets={datasets}
        />
      ) : null}
    </div>
  );
}
