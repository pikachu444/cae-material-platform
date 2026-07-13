import { type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  createReferenceDatasetSelection,
  createReferenceTensileCropRecipe,
  createReferenceTensilePairStatisticalPlan,
  createReferenceTensileTestMethod,
  createReferenceTensileTestRun,
  createSpecimen,
  executeReferenceTensileCrop,
  executeReferenceTensilePairStatistics,
  getStatisticalResult,
  importReferenceTensileDataset,
  listDatasetRevisions,
  listDatasetRevisionSelections,
  listDatasetsForMaterialState,
  listSpecimensForMaterialState,
  listProcessingRecipes,
  listStatisticalPlans,
  listTestMethods,
  listTestRunsForMaterialState,
  previewDatasetCurve,
  previewStatisticalResultCurve,
  uploadReferenceTensileCsv,
} from "./api";
import type {
  CurvePreview,
  DatasetSelectionResponse,
  DatasetResponse,
  DatasetRevision,
  MaterialStateResponse,
  ProcessingRecipeResponse,
  ProcessingRunResponse,
  ReferenceTensileMapping,
  SpecimenResponse,
  StatisticalCurvePreview,
  StatisticalPlanResponse,
  StatisticalResultResponse,
  StatisticalRunResponse,
  TestMethodResponse,
  TestRunResponse,
} from "./types";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return "The reference tensile workflow could not be completed. Check the protected API connection and try again.";
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : null;
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function defaultPerformedAt(): string {
  const now = new Date();
  const shifted = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function plotPoints(curve: CurvePreview): string {
  const width = 720;
  const height = 280;
  const left = 48;
  const right = 18;
  const top = 18;
  const bottom = 40;
  const xs = curve.points.map((point) => point.engineering_strain);
  const ys = curve.points.map((point) => point.engineering_stress);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  return curve.points
    .map((point) => {
      const x = left + ((point.engineering_strain - minX) / xSpan) * (width - left - right);
      const y = height - bottom - ((point.engineering_stress - minY) / ySpan) * (height - top - bottom);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function CurvePanel({ curve }: { curve: CurvePreview }) {
  const xValues = curve.points.map((point) => point.engineering_strain);
  const yValues = curve.points.map((point) => point.engineering_stress);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  return (
    <section className="curve-panel" aria-label={`${curve.representation} tensile curve`}>
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Curve preview</p>
          <h5>
            {curve.representation === "raw"
              ? "Original-unit raw curve"
              : curve.representation === "processed"
                ? "Committed processed SI curve"
                : "Normalized SI curve"}
          </h5>
        </div>
        <span className="reference-chip">{curve.representation}</span>
      </div>
      <p className="curve-summary">
        {curve.returned_point_count.toLocaleString()} of {curve.point_count.toLocaleString()} point
        {curve.point_count === 1 ? "" : "s"} · strain ({curve.strain_unit}) · stress ({curve.stress_unit})
        {curve.sampled ? " · deterministically sampled for this preview" : ""}
      </p>
      <svg className="curve-plot" viewBox="0 0 720 280" role="img" aria-label="Stress strain curve">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        <polyline points={plotPoints(curve)} />
        <text x="48" y="264">{minX.toPrecision(4)}</text>
        <text x="642" y="264">{maxX.toPrecision(4)}</text>
        <text x="4" y="236">{minY.toPrecision(4)}</text>
        <text x="4" y="26">{maxY.toPrecision(4)}</text>
        <text x="340" y="278">engineering strain ({curve.strain_unit})</text>
        <text x="14" y="144" transform="rotate(-90 14 144)">engineering stress ({curve.stress_unit})</text>
      </svg>
    </section>
  );
}

function plotStatisticsPoints(curve: StatisticalCurvePreview): string {
  const width = 720;
  const height = 280;
  const left = 48;
  const right = 18;
  const top = 18;
  const bottom = 40;
  const xs = curve.points.map((point) => point.engineering_strain);
  const ys = curve.points.map((point) => point.mean_engineering_stress_pa);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  return curve.points
    .map((point) => {
      const x = left + ((point.engineering_strain - minX) / xSpan) * (width - left - right);
      const y = height - bottom - ((point.mean_engineering_stress_pa - minY) / ySpan) * (height - top - bottom);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function StatisticsCurvePanel({ curve }: { curve: StatisticalCurvePreview }) {
  const xValues = curve.points.map((point) => point.engineering_strain);
  const yValues = curve.points.map((point) => point.mean_engineering_stress_pa);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  return (
    <section className="curve-panel" aria-label="Reference tensile pair mean curve">
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Statistics result</p>
          <h5>Mean engineering-stress curve</h5>
        </div>
        <span className="reference-chip">n=2</span>
      </div>
      <p className="curve-summary">
        {curve.returned_point_count.toLocaleString()} of {curve.point_count.toLocaleString()} observed
        points; the range and sample standard deviation remain in the immutable result Artifact.
      </p>
      <svg className="curve-plot" viewBox="0 0 720 280" role="img" aria-label="Mean stress strain curve">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        <polyline points={plotStatisticsPoints(curve)} />
        <text x="48" y="264">{minX.toPrecision(4)}</text>
        <text x="642" y="264">{maxX.toPrecision(4)}</text>
        <text x="4" y="236">{minY.toPrecision(4)}</text>
        <text x="4" y="26">{maxY.toPrecision(4)}</text>
        <text x="340" y="278">engineering strain (1)</text>
        <text x="14" y="144" transform="rotate(-90 14 144)">mean engineering stress (Pa)</text>
      </svg>
    </section>
  );
}

interface ReferenceTensileWorkflowProps {
  config: ApiConfig;
  state: MaterialStateResponse;
}

export function ReferenceTensileWorkflow({ config, state }: ReferenceTensileWorkflowProps) {
  const [open, setOpen] = useState(false);
  const [specimens, setSpecimens] = useState<SpecimenResponse[]>([]);
  const [methods, setMethods] = useState<TestMethodResponse[]>([]);
  const [runs, setRuns] = useState<TestRunResponse[]>([]);
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [selectedSpecimenId, setSelectedSpecimenId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [datasetRevisions, setDatasetRevisions] = useState<DatasetRevision[]>([]);
  const [selectedDatasetRevisionId, setSelectedDatasetRevisionId] = useState("");
  const [curve, setCurve] = useState<CurvePreview | null>(null);
  const [selections, setSelections] = useState<DatasetSelectionResponse[]>([]);
  const [selectedSelectionId, setSelectedSelectionId] = useState("");
  const [recipes, setRecipes] = useState<ProcessingRecipeResponse[]>([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [processingRun, setProcessingRun] = useState<ProcessingRunResponse | null>(null);
  const [processedCurve, setProcessedCurve] = useState<CurvePreview | null>(null);
  const [statisticsSelections, setStatisticsSelections] = useState<DatasetSelectionResponse[]>([]);
  const [firstStatisticsSelectionId, setFirstStatisticsSelectionId] = useState("");
  const [secondStatisticsSelectionId, setSecondStatisticsSelectionId] = useState("");
  const [statisticalPlans, setStatisticalPlans] = useState<StatisticalPlanResponse[]>([]);
  const [selectedStatisticalPlanId, setSelectedStatisticalPlanId] = useState("");
  const [statisticalRun, setStatisticalRun] = useState<StatisticalRunResponse | null>(null);
  const [statisticalResult, setStatisticalResult] = useState<StatisticalResultResponse | null>(null);
  const [statisticalCurve, setStatisticalCurve] = useState<StatisticalCurvePreview | null>(null);
  const [specimenCode, setSpecimenCode] = useState("");
  const [orientation, setOrientation] = useState("");
  const [specimenReason, setSpecimenReason] = useState("Register reference tensile specimen");
  const [methodReason, setMethodReason] = useState("Register reference tensile method");
  const [runLabel, setRunLabel] = useState("Tensile run 001");
  const [performedAt, setPerformedAt] = useState(defaultPerformedAt);
  const [temperatureK, setTemperatureK] = useState("");
  const [crossheadSpeed, setCrossheadSpeed] = useState("");
  const [runReason, setRunReason] = useState("Register reference tensile test run");
  const [file, setFile] = useState<File | null>(null);
  const [strainColumn, setStrainColumn] = useState("");
  const [stressColumn, setStressColumn] = useState("");
  const [strainUnit, setStrainUnit] = useState<ReferenceTensileMapping["strain_unit"]>("1");
  const [stressUnit, setStressUnit] = useState<ReferenceTensileMapping["stress_unit"]>("MPa");
  const [datasetReason, setDatasetReason] = useState("Import reference tensile CSV and normalize units");
  const [selectionLabel, setSelectionLabel] = useState("Reference crop input");
  const [selectionReason, setSelectionReason] = useState("Pin normalized Dataset revision for processing");
  const [recipeLabel, setRecipeLabel] = useState("Observed-point crop");
  const [minimumStrain, setMinimumStrain] = useState("0");
  const [maximumStrain, setMaximumStrain] = useState("0.02");
  const [recipeReason, setRecipeReason] = useState("Define committed observed-point crop recipe");
  const [processingReason, setProcessingReason] = useState("Create processed Dataset from pinned input and recipe");
  const [statisticalPlanLabel, setStatisticalPlanLabel] = useState("Reference tensile pair statistics");
  const [statisticalPlanReason, setStatisticalPlanReason] = useState("Pin two normalized selections for reference statistics");
  const [statisticsReason, setStatisticsReason] = useState("Calculate reference pair scalar statistics and curve band");
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const matchingMethods = useMemo(
    () => methods.filter(
      (method) => method.current_revision.content.method_code === "reference_uniaxial_tensile"
        && method.current_revision.classification === state.current_revision.classification,
    ),
    [methods, state.current_revision.classification],
  );
  const selectedSpecimen = specimens.find((specimen) => specimen.specimen_id === selectedSpecimenId) ?? null;
  const selectedRun = runs.find((run) => run.test_run_id === selectedRunId) ?? null;
  const normalizedRevision = datasetRevisions.find(
    (revision) => revision.content.representation === "normalized",
  ) ?? null;
  const selectedSelection = selections.find((selection) => selection.selection_id === selectedSelectionId) ?? null;
  const selectedRecipe = recipes.find((recipe) => recipe.recipe_id === selectedRecipeId) ?? null;
  const firstStatisticsSelection = statisticsSelections.find(
    (selection) => selection.selection_id === firstStatisticsSelectionId,
  ) ?? null;
  const secondStatisticsSelection = statisticsSelections.find(
    (selection) => selection.selection_id === secondStatisticsSelectionId,
  ) ?? null;
  const selectedStatisticalPlan = statisticalPlans.find(
    (plan) => plan.statistical_plan_id === selectedStatisticalPlanId,
  ) ?? null;
  const statisticalScalar = statisticalResult?.current_revision.content.scalar ?? null;
  const normalizedDatasetHeads = useMemo(
    () => datasets.filter((dataset) => dataset.current_revision.content.representation === "normalized"),
    [datasets],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextSpecimens, nextMethods, nextRuns, nextDatasets] = await Promise.all([
        listSpecimensForMaterialState(config, state.material_state_id),
        listTestMethods(config),
        listTestRunsForMaterialState(config, state.material_state_id),
        listDatasetsForMaterialState(config, state.material_state_id),
      ]);
      setSpecimens(nextSpecimens.data.items);
      setMethods(nextMethods.data.items);
      setRuns(nextRuns.data.items);
      setDatasets(nextDatasets.data.items);
      setSelectedSpecimenId((current) => current || nextSpecimens.data.items[0]?.specimen_id || "");
      setSelectedRunId((current) => current || nextRuns.data.items[0]?.test_run_id || "");
      setSelectedDatasetId((current) => current || nextDatasets.data.items[0]?.dataset_id || "");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoading(false);
    }
  }, [config, state.material_state_id]);

  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open, refresh]);

  useEffect(() => {
    if (!open || !selectedDatasetId) {
      setDatasetRevisions([]);
      setSelectedDatasetRevisionId("");
      return;
    }
    let current = true;
    void listDatasetRevisions(config, selectedDatasetId)
      .then((result) => {
        if (!current) {
          return;
        }
        setDatasetRevisions(result.data.revisions);
        const normalized = result.data.revisions.find(
          (revision) => revision.content.representation === "normalized",
        );
        setSelectedDatasetRevisionId((selected) => selected || normalized?.id || result.data.revisions[0]?.id || "");
      })
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, open, selectedDatasetId]);

  useEffect(() => {
    if (!open || !selectedDatasetRevisionId) {
      setCurve(null);
      return;
    }
    let current = true;
    void previewDatasetCurve(config, selectedDatasetRevisionId)
      .then((result) => current && setCurve(result.data))
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, open, selectedDatasetRevisionId]);

  useEffect(() => {
    if (!open || !normalizedRevision) {
      setSelections([]);
      setSelectedSelectionId("");
      return;
    }
    let current = true;
    void Promise.all([
      listDatasetRevisionSelections(config, normalizedRevision.id),
      listProcessingRecipes(config),
    ])
      .then(([nextSelections, nextRecipes]) => {
        if (!current) {
          return;
        }
        const scopedRecipes = nextRecipes.data.items.filter(
          (recipe) => recipe.current_revision.classification === state.current_revision.classification,
        );
        setSelections(nextSelections.data.items);
        setRecipes(scopedRecipes);
        setSelectedSelectionId((selected) => (
          nextSelections.data.items.some((item) => item.selection_id === selected)
            ? selected
            : nextSelections.data.items[0]?.selection_id ?? ""
        ));
        setSelectedRecipeId((selected) => (
          scopedRecipes.some((item) => item.recipe_id === selected)
            ? selected
            : scopedRecipes[0]?.recipe_id ?? ""
        ));
      })
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, normalizedRevision, open, state.current_revision.classification]);

  useEffect(() => {
    if (!open) {
      setStatisticsSelections([]);
      setStatisticalPlans([]);
      setFirstStatisticsSelectionId("");
      setSecondStatisticsSelectionId("");
      setSelectedStatisticalPlanId("");
      return;
    }
    let current = true;
    const selectionRequests = normalizedDatasetHeads.map((dataset) => (
      listDatasetRevisionSelections(config, dataset.current_revision.id)
    ));
    void Promise.all([
      Promise.all(selectionRequests),
      listStatisticalPlans(config),
    ])
      .then(([selectionResults, planResult]) => {
        if (!current) {
          return;
        }
        const selectionById = new Map<string, DatasetSelectionResponse>();
        for (const result of selectionResults) {
          for (const selection of result.data.items) {
            if (selection.current_revision.classification === state.current_revision.classification) {
              selectionById.set(selection.selection_id, selection);
            }
          }
        }
        const scopedSelections = [...selectionById.values()];
        const scopedPlans = planResult.data.items.filter(
          (plan) => plan.current_revision.classification === state.current_revision.classification,
        );
        setStatisticsSelections(scopedSelections);
        setStatisticalPlans(scopedPlans);
        setFirstStatisticsSelectionId((selected) => (
          scopedSelections.some((item) => item.selection_id === selected)
            ? selected
            : scopedSelections[0]?.selection_id ?? ""
        ));
        setSecondStatisticsSelectionId((selected) => {
          if (scopedSelections.some((item) => item.selection_id === selected && selected !== scopedSelections[0]?.selection_id)) {
            return selected;
          }
          return scopedSelections.find((item) => item.selection_id !== scopedSelections[0]?.selection_id)?.selection_id ?? "";
        });
        setSelectedStatisticalPlanId((selected) => (
          scopedPlans.some((item) => item.statistical_plan_id === selected)
            ? selected
            : scopedPlans[0]?.statistical_plan_id ?? ""
        ));
      })
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, normalizedDatasetHeads, open, state.current_revision.classification]);

  useEffect(() => {
    const outputRevisionId = processingRun?.output_dataset_revision_id;
    if (!open || !outputRevisionId) {
      setProcessedCurve(null);
      return;
    }
    let current = true;
    void previewDatasetCurve(config, outputRevisionId)
      .then((result) => current && setProcessedCurve(result.data))
      .catch((cause: unknown) => current && setError(messageFor(cause)));
    return () => {
      current = false;
    };
  }, [config, open, processingRun?.output_dataset_revision_id]);

  async function submitSpecimen(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setAction("specimen");
    setError(null);
    try {
      const result = await createSpecimen(config, state.material_state_id, {
        material_state_revision_id: state.current_revision.id,
        specimen_code: specimenCode.trim(),
        orientation: optionalText(orientation),
        preparation_note: null,
        change_reason: specimenReason.trim(),
      });
      setSpecimens((current) => [result.data, ...current]);
      setSelectedSpecimenId(result.data.specimen_id);
      setSpecimenCode("");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function registerMethod(): Promise<void> {
    setAction("method");
    setError(null);
    try {
      const result = await createReferenceTensileTestMethod(config, {
        classification: state.current_revision.classification,
        change_reason: methodReason.trim(),
      });
      setMethods((current) => [result.data, ...current]);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function submitRun(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const method = matchingMethods[0];
    if (!selectedSpecimen || !method) {
      return;
    }
    setAction("run");
    setError(null);
    try {
      const performed = new Date(performedAt);
      if (Number.isNaN(performed.getTime())) {
        throw new ApiError(422, "Provide a valid performed-at timestamp for the Test Run.");
      }
      const result = await createReferenceTensileTestRun(config, {
        specimen_id: selectedSpecimen.specimen_id,
        specimen_revision_id: selectedSpecimen.current_revision.id,
        test_method_id: method.test_method_id,
        test_method_revision_id: method.current_revision.id,
        run_label: runLabel.trim(),
        performed_at: performed.toISOString(),
        test_temperature_k: optionalNumber(temperatureK),
        crosshead_speed_mm_per_min: optionalNumber(crossheadSpeed),
        change_reason: runReason.trim(),
      });
      setRuns((current) => [result.data, ...current]);
      setSelectedRunId(result.data.test_run_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>): void {
    setFile(event.target.files?.[0] ?? null);
  }

  async function submitDataset(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!file || !selectedRun) {
      return;
    }
    setAction("dataset");
    setError(null);
    try {
      const completed = await uploadReferenceTensileCsv(config, {
        file,
        classification: state.current_revision.classification,
        test_run_revision_id: selectedRun.current_revision.id,
      });
      if (!completed.data.available_artifact_id) {
        throw new ApiError(409, "The raw CSV was stored but no immutable Artifact is available for Dataset import.");
      }
      const result = await importReferenceTensileDataset(config, {
        test_run_id: selectedRun.test_run_id,
        test_run_revision_id: selectedRun.current_revision.id,
        raw_asset_id: completed.data.raw_asset.raw_asset_id,
        raw_artifact_id: completed.data.available_artifact_id,
        mapping: {
          strain_column: strainColumn.trim(),
          stress_column: stressColumn.trim(),
          strain_unit: strainUnit,
          stress_unit: stressUnit,
        },
        change_reason: datasetReason.trim(),
      });
      setDatasets((current) => [result.data, ...current.filter((item) => item.dataset_id !== result.data.dataset_id)]);
      setSelectedDatasetId(result.data.dataset_id);
      setSelectedDatasetRevisionId(result.data.current_revision.id);
      setFile(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function submitSelection(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!normalizedRevision) {
      return;
    }
    setAction("selection");
    setError(null);
    try {
      const result = await createReferenceDatasetSelection(config, {
        classification: state.current_revision.classification,
        selection_label: selectionLabel.trim(),
        dataset_revision_id: normalizedRevision.id,
        change_reason: selectionReason.trim(),
      });
      setSelections((current) => [
        result.data,
        ...current.filter((item) => item.selection_id !== result.data.selection_id),
      ]);
      setSelectedSelectionId(result.data.selection_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function submitRecipe(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const minimum = Number(minimumStrain);
    const maximum = Number(maximumStrain);
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || minimum < 0 || maximum <= minimum) {
      setError("Provide finite crop bounds with 0 ≤ minimum strain < maximum strain.");
      return;
    }
    setAction("recipe");
    setError(null);
    try {
      const result = await createReferenceTensileCropRecipe(config, {
        classification: state.current_revision.classification,
        content: {
          recipe_label: recipeLabel.trim(),
          minimum_engineering_strain: minimum,
          maximum_engineering_strain: maximum,
        },
        change_reason: recipeReason.trim(),
      });
      setRecipes((current) => [
        result.data,
        ...current.filter((item) => item.recipe_id !== result.data.recipe_id),
      ]);
      setSelectedRecipeId(result.data.recipe_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function executeProcessing(): Promise<void> {
    if (!selectedSelection || !selectedRecipe) {
      return;
    }
    setAction("processing");
    setError(null);
    try {
      const result = await executeReferenceTensileCrop(config, {
        selection_id: selectedSelection.selection_id,
        selection_revision_id: selectedSelection.current_revision.id,
        recipe_id: selectedRecipe.recipe_id,
        recipe_revision_id: selectedRecipe.current_revision.id,
        change_reason: processingReason.trim(),
      });
      setProcessingRun(result.data);
      if (result.data.output_dataset_revision_id) {
        const output = await previewDatasetCurve(config, result.data.output_dataset_revision_id);
        setProcessedCurve(output.data);
      }
      await refresh();
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function submitStatisticalPlan(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!firstStatisticsSelection || !secondStatisticsSelection) {
      return;
    }
    if (firstStatisticsSelection.current_revision.id === secondStatisticsSelection.current_revision.id) {
      setError("Select two distinct pinned Selection revisions for the reference pair.");
      return;
    }
    setAction("statistical-plan");
    setError(null);
    try {
      const result = await createReferenceTensilePairStatisticalPlan(config, {
        classification: state.current_revision.classification,
        content: {
          plan_label: statisticalPlanLabel.trim(),
          first_selection_id: firstStatisticsSelection.selection_id,
          first_selection_revision_id: firstStatisticsSelection.current_revision.id,
          second_selection_id: secondStatisticsSelection.selection_id,
          second_selection_revision_id: secondStatisticsSelection.current_revision.id,
        },
        change_reason: statisticalPlanReason.trim(),
      });
      setStatisticalPlans((current) => [
        result.data,
        ...current.filter((plan) => plan.statistical_plan_id !== result.data.statistical_plan_id),
      ]);
      setSelectedStatisticalPlanId(result.data.statistical_plan_id);
      setStatisticalRun(null);
      setStatisticalResult(null);
      setStatisticalCurve(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function executeStatistics(): Promise<void> {
    if (!selectedStatisticalPlan) {
      return;
    }
    setAction("statistics");
    setError(null);
    try {
      const result = await executeReferenceTensilePairStatistics(config, {
        plan_id: selectedStatisticalPlan.statistical_plan_id,
        plan_revision_id: selectedStatisticalPlan.current_revision.id,
        change_reason: statisticsReason.trim(),
      });
      setStatisticalRun(result.data);
      if (result.data.result_id) {
        const [nextResult, nextCurve] = await Promise.all([
          getStatisticalResult(config, result.data.result_id),
          previewStatisticalResultCurve(config, result.data.result_id),
        ]);
        setStatisticalResult(nextResult.data);
        setStatisticalCurve(nextCurve.data);
      } else {
        setStatisticalResult(null);
        setStatisticalCurve(null);
      }
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <section className="reference-tensile-workflow" aria-label="Reference tensile Dataset workflow">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Test data workflow</p>
          <h4>Reference tensile CSV → Dataset revision</h4>
        </div>
        <span className="reference-chip">Reference only</span>
      </div>
      <p className="form-hint">
        Preserve the uploaded source as an immutable Raw Asset, explicitly confirm column and unit
        semantics, then view separate raw and normalized Dataset revisions.
      </p>
      <button className="text-button workflow-toggle" type="button" onClick={() => setOpen((current) => !current)}>
        {open ? "Close test data workflow" : "Manage reference tensile data"}
      </button>
      {!open ? null : (
        <div className="workflow-stack tensile-workflow-stack">
          <div className="workflow-toolbar">
            <span>{loading ? "Loading tenant-scoped test data…" : "All records are immutable revisions."}</span>
            <button className="text-button" type="button" onClick={() => void refresh()} disabled={loading}>
              Refresh
            </button>
          </div>
          {error ? <p className="error-notice" role="alert">{error}</p> : null}
          <div className="workflow-step">
            <strong>1. Register a concrete Specimen</strong>
            <form className="form-stack" onSubmit={(event) => void submitSpecimen(event)}>
              <div className="form-grid">
                <label>Specimen code<input value={specimenCode} onChange={(event) => setSpecimenCode(event.target.value)} required /></label>
                <label>Orientation (optional)<input value={orientation} onChange={(event) => setOrientation(event.target.value)} /></label>
              </div>
              <label>Change reason<input value={specimenReason} onChange={(event) => setSpecimenReason(event.target.value)} required /></label>
              <button className="button secondary" type="submit" disabled={action !== null}>
                {action === "specimen" ? "Registering specimen…" : "Register specimen"}
              </button>
            </form>
            {specimens.length ? (
              <label>
                Test Run specimen
                <select value={selectedSpecimenId} onChange={(event) => setSelectedSpecimenId(event.target.value)}>
                  {specimens.map((specimen) => <option key={specimen.specimen_id} value={specimen.specimen_id}>{specimen.current_revision.content.specimen_code} · r{specimen.current_revision.revision_no}</option>)}
                </select>
              </label>
            ) : <small className="muted">Register a Specimen before creating a Test Run.</small>}
          </div>
          <div className="workflow-step">
            <strong>2. Bind the reference tensile Test Method</strong>
            {matchingMethods.length ? (
              <p className="source-line">Reference method revision {shortId(matchingMethods[0].current_revision.id)} is available for this classification.</p>
            ) : (
              <>
                <p className="form-hint">This intentionally narrow method is a reference CSV contract, not a generic Test Method schema.</p>
                <label>Change reason<input value={methodReason} onChange={(event) => setMethodReason(event.target.value)} required /></label>
                <button className="button secondary" type="button" onClick={() => void registerMethod()} disabled={action !== null}>
                  {action === "method" ? "Registering method…" : "Register reference method"}
                </button>
              </>
            )}
          </div>
          <div className="workflow-step">
            <strong>3. Create a Test Run pinned to those revisions</strong>
            <form className="form-stack" onSubmit={(event) => void submitRun(event)}>
              <div className="form-grid">
                <label>Run label<input value={runLabel} onChange={(event) => setRunLabel(event.target.value)} required /></label>
                <label>Performed at<input type="datetime-local" value={performedAt} onChange={(event) => setPerformedAt(event.target.value)} required /></label>
                <label>Temperature (K, optional)<input type="number" min="0" step="any" value={temperatureK} onChange={(event) => setTemperatureK(event.target.value)} /></label>
                <label>Crosshead speed (mm/min, optional)<input type="number" min="0" step="any" value={crossheadSpeed} onChange={(event) => setCrossheadSpeed(event.target.value)} /></label>
              </div>
              <label>Change reason<input value={runReason} onChange={(event) => setRunReason(event.target.value)} required /></label>
              <button className="button secondary" type="submit" disabled={!selectedSpecimen || !matchingMethods.length || action !== null}>
                {action === "run" ? "Creating Test Run…" : "Create Test Run"}
              </button>
            </form>
            {runs.length ? (
              <label>
                Dataset source Test Run
                <select value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)}>
                  {runs.map((run) => <option key={run.test_run_id} value={run.test_run_id}>{run.current_revision.content.run_label} · r{run.current_revision.revision_no} · {shortId(run.current_revision.id)}</option>)}
                </select>
              </label>
            ) : <small className="muted">Create a Test Run before uploading a Dataset source.</small>}
          </div>
          <div className="workflow-step">
            <strong>4. Upload and explicitly map the CSV</strong>
            <p className="form-hint">Only UTF-8 CSV up to 16 MiB is accepted. Column names are never inferred; the source bytes and their raw-unit curve remain available after normalization.</p>
            <form className="form-stack" onSubmit={(event) => void submitDataset(event)}>
              <label>Reference tensile CSV<input type="file" accept=".csv,text/csv" onChange={selectFile} required /></label>
              {file ? <small className="source-line">{file.name} · {file.size.toLocaleString()} bytes</small> : null}
              <div className="form-grid">
                <label>Strain column<input value={strainColumn} onChange={(event) => setStrainColumn(event.target.value)} placeholder="e.g. engineering_strain" required /></label>
                <label>Stress column<input value={stressColumn} onChange={(event) => setStressColumn(event.target.value)} placeholder="e.g. engineering_stress" required /></label>
                <label>Source strain unit<select value={strainUnit} onChange={(event) => setStrainUnit(event.target.value as ReferenceTensileMapping["strain_unit"])}><option value="1">1</option><option value="%">%</option></select></label>
                <label>Source stress unit<select value={stressUnit} onChange={(event) => setStressUnit(event.target.value as ReferenceTensileMapping["stress_unit"])}><option value="Pa">Pa</option><option value="kPa">kPa</option><option value="MPa">MPa</option><option value="GPa">GPa</option></select></label>
              </div>
              <label>Change reason<input value={datasetReason} onChange={(event) => setDatasetReason(event.target.value)} required /></label>
              <button className="button primary" type="submit" disabled={!selectedRun || !file || action !== null}>
                {action === "dataset" ? "Uploading and normalizing…" : "Create raw and normalized Dataset revisions"}
              </button>
            </form>
          </div>
          <div className="workflow-step dataset-results">
            <strong>5. Inspect immutable raw and normalized curves</strong>
            {!datasets.length ? <p className="muted">No Dataset revision is available for this Material State yet.</p> : null}
            {datasets.length ? (
              <>
                <label>
                  Dataset
                  <select value={selectedDatasetId} onChange={(event) => { setSelectedDatasetId(event.target.value); setSelectedDatasetRevisionId(""); }}>
                    {datasets.map((dataset) => <option key={dataset.dataset_id} value={dataset.dataset_id}>{shortId(dataset.dataset_id)} · current {dataset.current_revision.content.representation} r{dataset.current_revision.revision_no}</option>)}
                  </select>
                </label>
                {datasetRevisions.length ? (
                  <label>
                    Dataset revision
                    <select value={selectedDatasetRevisionId} onChange={(event) => setSelectedDatasetRevisionId(event.target.value)}>
                      {datasetRevisions.map((revision) => <option key={revision.id} value={revision.id}>r{revision.revision_no} · {revision.content.representation} · {revision.content.point_count.toLocaleString()} points</option>)}
                    </select>
                  </label>
                ) : null}
                {curve ? <CurvePanel curve={curve} /> : <p className="muted">Select a Dataset revision to load its curve.</p>}
              </>
            ) : null}
          </div>
          <div className="workflow-step">
            <strong>6. Pin the normalized revision as a Processing Selection</strong>
            {!normalizedRevision ? (
              <p className="muted">Import a normalized Dataset revision before creating a Selection.</p>
            ) : (
              <>
                <p className="form-hint">
                  This narrow reference Selection contains exactly one normalized Dataset revision.
                  It never follows a moving Dataset head.
                </p>
                <p className="source-line">
                  Input Dataset revision {shortId(normalizedRevision.id)} · {normalizedRevision.content.point_count.toLocaleString()} points
                </p>
                <form className="form-stack" onSubmit={(event) => void submitSelection(event)}>
                  <label>Selection label<input value={selectionLabel} onChange={(event) => setSelectionLabel(event.target.value)} required /></label>
                  <label>Change reason<input value={selectionReason} onChange={(event) => setSelectionReason(event.target.value)} required /></label>
                  <button className="button secondary" type="submit" disabled={action !== null}>
                    {action === "selection" ? "Pinning Selection…" : "Create pinned Selection"}
                  </button>
                </form>
                {selections.length ? (
                  <label>
                    Pinned Selection
                    <select value={selectedSelectionId} onChange={(event) => setSelectedSelectionId(event.target.value)}>
                      {selections.map((selection) => (
                        <option key={selection.selection_id} value={selection.selection_id}>
                          {selection.selection_label} · r{selection.current_revision.revision_no} · {shortId(selection.current_revision.id)}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </>
            )}
          </div>
          <div className="workflow-step">
            <strong>7. Define the one-step observed-point crop Recipe</strong>
            <p className="form-hint">
              The reference Recipe is intentionally limited to inclusive observed engineering-strain bounds. It does not interpolate, resample, smooth, or alter units.
            </p>
            <form className="form-stack" onSubmit={(event) => void submitRecipe(event)}>
              <div className="form-grid">
                <label>Recipe label<input value={recipeLabel} onChange={(event) => setRecipeLabel(event.target.value)} required /></label>
                <label>Minimum engineering strain<input type="number" min="0" step="any" value={minimumStrain} onChange={(event) => setMinimumStrain(event.target.value)} required /></label>
                <label>Maximum engineering strain<input type="number" min="0" step="any" value={maximumStrain} onChange={(event) => setMaximumStrain(event.target.value)} required /></label>
              </div>
              <label>Change reason<input value={recipeReason} onChange={(event) => setRecipeReason(event.target.value)} required /></label>
              <button className="button secondary" type="submit" disabled={action !== null}>
                {action === "recipe" ? "Creating Recipe…" : "Create immutable Recipe"}
              </button>
            </form>
            {recipes.length ? (
              <label>
                Processing Recipe
                <select value={selectedRecipeId} onChange={(event) => setSelectedRecipeId(event.target.value)}>
                  {recipes.map((recipe) => (
                    <option key={recipe.recipe_id} value={recipe.recipe_id}>
                      {recipe.recipe_label} · [{recipe.current_revision.content.minimum_engineering_strain}, {recipe.current_revision.content.maximum_engineering_strain}] · r{recipe.current_revision.revision_no}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
          <div className="workflow-step dataset-results">
            <strong>8. Commit Processing Run and inspect the separate processed Dataset</strong>
            <p className="form-hint">
              This action has no transient preview mode. It creates a durable committed Run, a derived immutable Artifact, and revision 1 of a separate processed Dataset identity; raw and normalized inputs remain unchanged.
            </p>
            <label>Change reason<input value={processingReason} onChange={(event) => setProcessingReason(event.target.value)} required /></label>
            <button className="button primary" type="button" onClick={() => void executeProcessing()} disabled={!selectedSelection || !selectedRecipe || action !== null}>
              {action === "processing" ? "Committing Processing Run…" : "Commit crop Processing Run"}
            </button>
            {!selectedSelection || !selectedRecipe ? <small className="muted">Create or select both a pinned Selection and Recipe before committing a run.</small> : null}
            {processingRun ? (
              <div className="workflow-toolbar">
                <span>
                  Run {shortId(processingRun.processing_run_id)} · {processingRun.status} · {processingRun.input_point_count.toLocaleString()} → {processingRun.output_point_count?.toLocaleString() ?? "—"} points
                </span>
                {processingRun.output_dataset_revision_id ? <span className="reference-chip">processed Dataset r1</span> : null}
              </div>
            ) : null}
            {processedCurve ? <CurvePanel curve={processedCurve} /> : null}
          </div>
          <div className="workflow-step dataset-results">
            <strong>9. Compare two pinned selections with reference Statistics/QC</strong>
            <p className="form-hint">
              This reference method uses exactly two distinct Test Runs. It accepts only identical
              observed engineering-strain grids: there is no implicit alignment, resampling,
              interpolation, extrapolation, or confidence interval.
            </p>
            {statisticsSelections.length < 2 ? (
              <p className="muted">
                Create pinned Selections for two normalized Dataset revisions from distinct Test Runs
                before defining a Statistical Plan.
              </p>
            ) : (
              <>
                <form className="form-stack" onSubmit={(event) => void submitStatisticalPlan(event)}>
                  <div className="form-grid">
                    <label>
                      First pinned Selection
                      <select
                        value={firstStatisticsSelectionId}
                        onChange={(event) => {
                          const next = event.target.value;
                          setFirstStatisticsSelectionId(next);
                          if (next === secondStatisticsSelectionId) {
                            setSecondStatisticsSelectionId(
                              statisticsSelections.find((selection) => selection.selection_id !== next)?.selection_id ?? "",
                            );
                          }
                        }}
                      >
                        {statisticsSelections.map((selection) => (
                          <option key={selection.selection_id} value={selection.selection_id}>
                            {selection.selection_label} - {shortId(selection.current_revision.id)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Second pinned Selection
                      <select
                        value={secondStatisticsSelectionId}
                        onChange={(event) => setSecondStatisticsSelectionId(event.target.value)}
                      >
                        {statisticsSelections
                          .filter((selection) => selection.selection_id !== firstStatisticsSelectionId)
                          .map((selection) => (
                            <option key={selection.selection_id} value={selection.selection_id}>
                              {selection.selection_label} - {shortId(selection.current_revision.id)}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Statistical Plan label
                      <input
                        value={statisticalPlanLabel}
                        onChange={(event) => setStatisticalPlanLabel(event.target.value)}
                        required
                      />
                    </label>
                  </div>
                  <label>
                    Change reason
                    <input
                      value={statisticalPlanReason}
                      onChange={(event) => setStatisticalPlanReason(event.target.value)}
                      required
                    />
                  </label>
                  <button
                    className="button secondary"
                    type="submit"
                    disabled={!firstStatisticsSelection || !secondStatisticsSelection || action !== null}
                  >
                    {action === "statistical-plan" ? "Pinning Statistical Plan..." : "Create immutable Statistical Plan"}
                  </button>
                </form>
              </>
            )}
            {statisticalPlans.length ? (
              <>
                <label>
                  Statistical Plan
                  <select
                    value={selectedStatisticalPlanId}
                    onChange={(event) => {
                      setSelectedStatisticalPlanId(event.target.value);
                      setStatisticalRun(null);
                      setStatisticalResult(null);
                      setStatisticalCurve(null);
                    }}
                  >
                    {statisticalPlans.map((plan) => (
                      <option key={plan.statistical_plan_id} value={plan.statistical_plan_id}>
                        {plan.plan_label} - r{plan.current_revision.revision_no}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Change reason
                  <input value={statisticsReason} onChange={(event) => setStatisticsReason(event.target.value)} required />
                </label>
                <button
                  className="button primary"
                  type="button"
                  onClick={() => void executeStatistics()}
                  disabled={!selectedStatisticalPlan || action !== null}
                >
                  {action === "statistics" ? "Committing Statistical Run..." : "Commit Statistical Run"}
                </button>
              </>
            ) : null}
            {statisticalRun ? (
              <div className="statistics-result" aria-live="polite">
                <div className="workflow-toolbar">
                  <span>
                    Run {shortId(statisticalRun.statistical_run_id)} - {statisticalRun.status} - n={statisticalRun.sample_count}
                  </span>
                  <span className="reference-chip">{statisticalRun.failure_code ?? "QC recorded"}</span>
                </div>
                <ul className="qc-list" aria-label="Statistical quality-control observations">
                  {statisticalRun.qc_observations.map((observation) => (
                    <li key={observation.check_code} className={observation.outcome}>
                      <strong>{observation.outcome}</strong> {observation.check_code}: {observation.detail}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {statisticalScalar ? (
              <div className="statistics-result">
                <p className="source-line">
                  Scalar feature: peak engineering stress (Pa); quantiles use linear inclusive;
                  confidence interval: {statisticalScalar.confidence_interval_status}.
                </p>
                <dl className="definition-list statistics-definition-list">
                  <div><dt>Mean (Pa)</dt><dd>{statisticalScalar.mean_engineering_stress_pa.toPrecision(6)}</dd></div>
                  <div><dt>Sample standard deviation (Pa)</dt><dd>{statisticalScalar.sample_standard_deviation_engineering_stress_pa.toPrecision(6)}</dd></div>
                  <div><dt>Median (Pa)</dt><dd>{statisticalScalar.median_engineering_stress_pa.toPrecision(6)}</dd></div>
                  <div><dt>MAD (Pa)</dt><dd>{statisticalScalar.median_absolute_deviation_engineering_stress_pa.toPrecision(6)}</dd></div>
                  <div><dt>IQR (Pa)</dt><dd>{statisticalScalar.interquartile_range_engineering_stress_pa.toPrecision(6)}</dd></div>
                  <div><dt>Coefficient of variation</dt><dd>{statisticalScalar.coefficient_of_variation?.toPrecision(6) ?? "not applicable"}</dd></div>
                </dl>
                {statisticalCurve ? <StatisticsCurvePanel curve={statisticalCurve} /> : null}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}
