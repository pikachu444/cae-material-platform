import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  commitCommonProcessingOutput,
  createCommonMappingProfile,
  createCommonProcessingRecipe,
  downloadCanonicalTestDataDocument,
  downloadCommonProcessingOutput,
  listCanonicalTestDataDocuments,
  listCommonMappingProfiles,
  listCommonProcessingOutputs,
  listCommonProcessingRecipes,
  listCommonProcessingBatches,
  listCommonProcessingMethods,
  listCommonProcessingEnsembleMethods,
  previewCommonProcessing,
  previewCommonProcessingEnsemble,
  preflightCommonProcessingBatch,
  executeCommonProcessingBatch,
  retryFailedCommonProcessingBatch,
  reviseCommonMappingProfile,
  reviseCommonProcessingRecipe,
  type ApiConfig,
} from "./api";
import type {
  CanonicalTestDataDocumentResponse,
  CommonCurveStage,
  CommonEnsemblePreview,
  CommonMappingProfileContent,
  CommonMappingProfileResponse,
  CommonProcessingMethod,
  CommonProcessingBatchPreflight,
  CommonProcessingBatchResponse,
  CommonProcessingOutputResponse,
  CommonProcessingRecipeContent,
  CommonProcessingRecipeResponse,
  CommonProcessingPreview,
  CommonProcessingStep,
  DataClassification,
} from "./types";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}

const DEFAULT_PROFILE: CommonMappingProfileContent = {
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

const DEFAULT_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
];

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "The Processing Workbench operation failed.";
}

function defaultOptions(methodId: string): Record<string, unknown> {
  const options: Record<string, Record<string, unknown>> = {
    "rows.sort_unique": { duplicate_policy: "reject" },
    "curve.crop": { minimum: 0, maximum: 0.001 },
    "curve.scale_shift": { quantity: "stress.engineering", scale: 1, offset: 0 },
    "curve.resample_linear": { start: 0, end: 0.001, count: 21, extrapolation: "reject" },
    "curve.moving_average": { quantity: "stress.engineering", window: 3 },
    "curve.savitzky_golay": { quantity: "stress.engineering", window: 5, polynomial_order: 2 },
    "curve.smoothing_spline": { quantity: "stress.engineering", smoothing_factor: 0 },
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
  };
  return options[methodId] ?? {};
}

function curvePoints(
  stage: CommonCurveStage,
  independentQuantity: string,
  width: number,
  height: number,
  bounds: { xMin: number; xMax: number; yMin: number; yMax: number },
): string {
  const x = stage.series.find((item) => item.quantity === independentQuantity)?.values ?? [];
  const y = stage.series.find((item) => item.quantity !== independentQuantity)?.values ?? [];
  if (x.length < 2 || y.length !== x.length) return "";
  return xyPoints(x, y, width, height, bounds);
}

function xyPoints(
  x: number[],
  y: number[],
  width: number,
  height: number,
  bounds: { xMin: number; xMax: number; yMin: number; yMax: number },
): string {
  const { xMin, xMax, yMin, yMax } = bounds;
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  return x
    .map((value, index) => {
      const px = 28 + ((value - xMin) / xRange) * (width - 48);
      const py = height - 24 - ((y[index] - yMin) / yRange) * (height - 44);
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .join(" ");
}

function curveBounds(
  stages: CommonCurveStage[],
  independentQuantity: string,
): { xMin: number; xMax: number; yMin: number; yMax: number } {
  const x = stages.flatMap(
    (stage) => stage.series.find((item) => item.quantity === independentQuantity)?.values ?? [],
  );
  const y = stages.flatMap(
    (stage) => stage.series.find((item) => item.quantity !== independentQuantity)?.values ?? [],
  );
  return {
    xMin: Math.min(...x),
    xMax: Math.max(...x),
    yMin: Math.min(...y),
    yMax: Math.max(...y),
  };
}

const HARDENING_COLORS = ["#64748b", "#0f766e", "#d97706", "#7c3aed", "#dc2626"];

function StageCurveEvidence({
  preview,
  activeStage,
  baseStage,
  width,
  height,
}: {
  preview: CommonProcessingPreview;
  activeStage: CommonCurveStage;
  baseStage: CommonCurveStage;
  width: number;
  height: number;
}) {
  const hardening = activeStage.method_id === "metal.hardening_fit_extrapolate";
  const prony = activeStage.method_id === "polymer.prony_fit_compare";
  const xQuantity = activeStage.series.some((item) => item.quantity === preview.independent_quantity)
    ? preview.independent_quantity
    : activeStage.series.find((item) => item.quantity.includes("strain"))?.quantity;
  if (!xQuantity) return <p className="muted">The selected stage has no plottable independent quantity.</p>;
  const candidateSeries = activeStage.series.filter(
    (item) => item.quantity.startsWith("stress.hardening.")
      && item.quantity !== "stress.hardening.selected",
  );
  const selectedSeries = activeStage.series.find(
    (item) => item.quantity === "stress.hardening.selected",
  );
  const pronyCandidates = activeStage.series.filter((item) =>
    item.quantity.startsWith("modulus.prony.candidate_"),
  );
  const selectedProny = activeStage.series.find(
    (item) => item.quantity === "modulus.prony.selected",
  );
  const xValues = activeStage.series.find((item) => item.quantity === xQuantity)?.values ?? [];
  const hardeningValues = [...candidateSeries, ...(selectedSeries ? [selectedSeries] : [])]
    .flatMap((item) => item.values);
  const pronyValues = [...pronyCandidates, ...(selectedProny ? [selectedProny] : [])]
    .flatMap((item) => item.values);
  const bounds = hardening ? {
    xMin: Math.min(...xValues),
    xMax: Math.max(...xValues),
    yMin: Math.min(...hardeningValues),
    yMax: Math.max(...hardeningValues),
  } : prony ? {
    xMin: Math.min(...xValues),
    xMax: Math.max(...xValues),
    yMin: Math.min(...pronyValues),
    yMax: Math.max(...pronyValues),
  } : curveBounds([baseStage, activeStage], xQuantity);
  return (
    <>
      <svg className="processing-curve" role="img" aria-label={hardening ? "Hardening candidate and selected extrapolation curves" : prony ? "Prony candidate and selected relaxation curves" : "Mapped and selected processing stage curve overlay"} viewBox={`0 0 ${width} ${height}`}>
        <line x1="28" y1={height - 24} x2={width - 20} y2={height - 24} className="chart-axis" />
        <line x1="28" y1="20" x2="28" y2={height - 24} className="chart-axis" />
        {hardening ? candidateSeries.map((series, index) => (
          <polyline
            key={series.quantity}
            points={xyPoints(xValues, series.values, width, height, bounds)}
            className="curve-line hardening-candidate"
            style={{ stroke: HARDENING_COLORS[index % HARDENING_COLORS.length] }}
          />
        )) : prony ? pronyCandidates.map((series, index) => (
          <polyline
            key={series.quantity}
            points={xyPoints(xValues, series.values, width, height, bounds)}
            className="curve-line hardening-candidate"
            style={{ stroke: HARDENING_COLORS[index % HARDENING_COLORS.length] }}
          />
        )) : (
          <>
            <polyline points={curvePoints(baseStage, xQuantity, width, height, bounds)} className="curve-line source" />
            <polyline points={curvePoints(activeStage, xQuantity, width, height, bounds)} className="curve-line processed" />
          </>
        )}
        {hardening && selectedSeries ? (
          <polyline
            points={xyPoints(xValues, selectedSeries.values, width, height, bounds)}
            className="curve-line hardening-selected"
          />
        ) : null}
        {prony && selectedProny ? (
          <polyline
            points={xyPoints(xValues, selectedProny.values, width, height, bounds)}
            className="curve-line hardening-selected"
          />
        ) : null}
      </svg>
      <div className="curve-legend">
        {hardening ? (
          <>
            {candidateSeries.map((series, index) => (
              <span key={series.quantity}>
                <i style={{ background: HARDENING_COLORS[index % HARDENING_COLORS.length] }} />
                {series.quantity.replace("stress.hardening.", "")}
              </span>
            ))}
            <span><i className="hardening-selected" />Selected combination</span>
          </>
        ) : prony ? (
          <>
            {pronyCandidates.map((series, index) => (
              <span key={series.quantity}>
                <i style={{ background: HARDENING_COLORS[index % HARDENING_COLORS.length] }} />
                {series.quantity.replace("modulus.prony.candidate_", "").replace("_", " ")}
              </span>
            ))}
            <span><i className="hardening-selected" />Selected Prony candidate</span>
          </>
        ) : (
          <><span><i className="source" />Mapped input</span><span><i className="processed" />Selected stage</span></>
        )}
      </div>
      <div className="stage-diagnostics">{activeStage.diagnostics.map((item) => <p key={item}>{item}</p>)}</div>
      {(activeStage.scalar_results ?? []).length ? (
        <div className="metal-scalar-grid" aria-label="Metal processing scalar results">
          {(activeStage.scalar_results ?? []).map((item) => (
            <article key={item.key}>
              <span>{item.key.replaceAll("_", " ").replaceAll(".", " ")}</span>
              <strong>{item.unit === "Pa" ? `${(item.value / 1e9).toPrecision(6)} GPa` : item.value.toPrecision(7)}</strong>
              <small>{item.quantity_semantics} · {item.unit}</small>
            </article>
          ))}
        </div>
      ) : null}
      <p className="digest-line"><span>Mapping SHA-256</span><code>{preview.mapping_profile_sha256}</code></p>
    </>
  );
}

export function CommonProcessingWorkbench({ config, onNavigate, onOpenConnection }: Props) {
  const [documents, setDocuments] = useState<CanonicalTestDataDocumentResponse[]>([]);
  const [profiles, setProfiles] = useState<CommonMappingProfileResponse[]>([]);
  const [methods, setMethods] = useState<CommonProcessingMethod[]>([]);
  const [ensembleMethods, setEnsembleMethods] = useState<CommonProcessingMethod[]>([]);
  const [outputs, setOutputs] = useState<CommonProcessingOutputResponse[]>([]);
  const [recipes, setRecipes] = useState<CommonProcessingRecipeResponse[]>([]);
  const [batches, setBatches] = useState<CommonProcessingBatchResponse[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [document, setDocument] = useState<Record<string, unknown> | null>(null);
  const [profileText, setProfileText] = useState(JSON.stringify(DEFAULT_PROFILE, null, 2));
  const [stepsText, setStepsText] = useState(JSON.stringify(DEFAULT_STEPS, null, 2));
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [changeReason, setChangeReason] = useState("Save reusable channel mapping");
  const [outputLabel, setOutputLabel] = useState("Processed tensile curve");
  const [outputReason, setOutputReason] = useState("Commit reviewed processing stages");
  const [recipeKey, setRecipeKey] = useState("normalized-tensile-cleanup");
  const [recipeLabel, setRecipeLabel] = useState("Normalized tensile cleanup");
  const [recipeDescription, setRecipeDescription] = useState("Reusable explicit processing steps");
  const [recipeReason, setRecipeReason] = useState("Save reusable Processing Recipe");
  const [preview, setPreview] = useState<CommonProcessingPreview | null>(null);
  const [selectedStage, setSelectedStage] = useState(0);
  const [ensembleDocumentIds, setEnsembleDocumentIds] = useState<string[]>([]);
  const [batchDocumentIds, setBatchDocumentIds] = useState<string[]>([]);
  const [batchLabel, setBatchLabel] = useState("Published Recipe batch");
  const [batchPreflight, setBatchPreflight] = useState<CommonProcessingBatchPreflight | null>(null);
  const [ensemblePointCount, setEnsemblePointCount] = useState(21);
  const [ensemblePreview, setEnsemblePreview] = useState<CommonEnsemblePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([
      listCanonicalTestDataDocuments(config),
      listCommonMappingProfiles(config),
      listCommonProcessingMethods(config),
      listCommonProcessingOutputs(config),
      listCommonProcessingEnsembleMethods(config),
      listCommonProcessingRecipes(config),
      listCommonProcessingBatches(config),
    ])
      .then(([documentResult, profileResult, methodResult, outputResult, ensembleMethodResult, recipeResult, batchResult]) => {
        setDocuments(documentResult.data.items);
        setProfiles(profileResult.data.items);
        setMethods(methodResult.data.items);
        setOutputs(outputResult.data.items);
        setEnsembleMethods(ensembleMethodResult.data.items);
        setRecipes(recipeResult.data.items);
        setBatches(batchResult.data.items);
        setSelectedDocumentId((current) => current || documentResult.data.items[0]?.test_data_document_id || "");
        setEnsembleDocumentIds((current) => current.length ? current : documentResult.data.items.slice(0, 2).map((item) => item.test_data_document_id));
        setBatchDocumentIds((current) => current.length ? current : documentResult.data.items.slice(0, 2).map((item) => item.test_data_document_id));
      })
      .catch((caught: unknown) => setError(errorMessage(caught)));
  }, [config]);

  async function loadDocument(id: string): Promise<void> {
    setSelectedDocumentId(id);
    setPreview(null);
    const item = documents.find((candidate) => candidate.test_data_document_id === id);
    if (!item) {
      setDocument(null);
      return;
    }
    setBusy(true);
    try {
      const result = await downloadCanonicalTestDataDocument(
        config,
        item.test_data_document_id,
        item.current_revision.id,
      );
      setDocument(JSON.parse(await result.data.blob.text()) as Record<string, unknown>);
      setNotice(`Loaded exact Test Data revision ${item.current_revision.revision_no}.`);
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function selectProfile(id: string): void {
    setSelectedProfileId(id);
    const item = profiles.find((candidate) => candidate.mapping_profile_id === id);
    if (item) setProfileText(JSON.stringify(item.content, null, 2));
  }

  function selectRecipe(id: string): void {
    setSelectedRecipeId(id);
    setBatchPreflight(null);
    const item = recipes.find((candidate) => candidate.processing_recipe_id === id);
    if (!item) return;
    setRecipeKey(item.content.recipe_key);
    setRecipeLabel(item.content.label);
    setRecipeDescription(item.content.description ?? "");
    setStepsText(JSON.stringify(item.content.steps, null, 2));
    const exactProfile = profiles.find(
      (profile) => profile.mapping_profile_id === item.content.mapping_profile_id
        && profile.current_revision.id === item.content.mapping_profile_revision_id,
    );
    if (exactProfile) selectProfile(exactProfile.mapping_profile_id);
    else {
      setSelectedProfileId("");
      setNotice("This Recipe pins an older exact Mapping Profile revision. Select a current profile before saving a new Recipe revision.");
    }
  }

  function toggleBatchDocument(id: string): void {
    setBatchDocumentIds((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : current.length < 500 ? [...current, id] : current);
    setBatchPreflight(null);
  }

  function selectedBatchInputs(): {
    recipe: CommonProcessingRecipeResponse;
    sources: Array<{ document_id: string; revision_id: string }>;
  } | null {
    const recipe = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
    if (!recipe || recipe.content.lifecycle_state !== "published") {
      setError("Select an exact published Recipe revision before batch preflight.");
      return null;
    }
    const selected = documents.filter((item) => batchDocumentIds.includes(item.test_data_document_id));
    if (!selected.length) {
      setError("Select at least one exact Test Data revision for the batch.");
      return null;
    }
    return {
      recipe,
      sources: selected.map((item) => ({
        document_id: item.test_data_document_id,
        revision_id: item.current_revision.id,
      })),
    };
  }

  async function preflightBatch(): Promise<void> {
    const input = selectedBatchInputs();
    if (!input) return;
    setBusy(true);
    setError(null);
    try {
      const result = await preflightCommonProcessingBatch(config, {
        classification: input.recipe.current_revision.classification as DataClassification,
        recipe_id: input.recipe.processing_recipe_id,
        recipe_revision_id: input.recipe.current_revision.id,
        sources: input.sources,
      });
      setBatchPreflight(result.data);
      setNotice(result.data.compatible
        ? `Preflight accepted ${result.data.members.length} exact inputs.`
        : "Preflight found incompatible inputs; execution remains blocked.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function executeBatch(): Promise<void> {
    const input = selectedBatchInputs();
    if (!input || !batchPreflight?.compatible) {
      setError("Run a successful compatibility preflight before batch execution.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await executeCommonProcessingBatch(config, {
        classification: input.recipe.current_revision.classification as DataClassification,
        label: batchLabel,
        recipe_id: input.recipe.processing_recipe_id,
        recipe_revision_id: input.recipe.current_revision.id,
        sources: input.sources,
        change_reason: "Execute exact published Processing Recipe batch",
      });
      const refreshed = await listCommonProcessingBatches(config);
      setBatches(refreshed.data.items);
      setNotice(`Batch ${result.data.status}: ${result.data.attempts.length} append-only attempts recorded.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function retryFailedBatch(batchId: string): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const result = await retryFailedCommonProcessingBatch(config, batchId);
      const refreshed = await listCommonProcessingBatches(config);
      setBatches(refreshed.data.items);
      setNotice(`Retry completed with batch status ${result.data.status}; earlier attempts remain immutable.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function recipeContent(
    profile: CommonMappingProfileResponse,
    lifecycleState: "draft" | "published",
  ): CommonProcessingRecipeContent {
    return {
      recipe_key: recipeKey,
      label: recipeLabel,
      description: recipeDescription.trim() || null,
      mapping_profile_id: profile.mapping_profile_id,
      mapping_profile_revision_id: profile.current_revision.id,
      mapping_profile_sha256: profile.current_revision.content_hash,
      steps: JSON.parse(stepsText) as CommonProcessingStep[],
      lifecycle_state: lifecycleState,
    };
  }

  async function saveRecipe(): Promise<void> {
    const profile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
    if (!profile) {
      setError("Select and save one exact Mapping Profile before saving a Recipe.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const selected = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
      const content = recipeContent(profile, "draft");
      const result = selected
        ? await reviseCommonProcessingRecipe(
            config,
            selected.processing_recipe_id,
            `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`,
            { content, change_reason: recipeReason },
          )
        : await createCommonProcessingRecipe(config, {
            classification: profile.current_revision.classification as DataClassification,
            content,
            change_reason: recipeReason,
          });
      const refreshed = await listCommonProcessingRecipes(config);
      setRecipes(refreshed.data.items);
      setSelectedRecipeId(result.data.processing_recipe_id);
      setNotice(`Saved reusable Recipe revision ${result.data.current_revision.revision_no} as draft.`);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid Recipe step JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function publishRecipe(): Promise<void> {
    const selected = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
    if (!selected || selected.content.lifecycle_state !== "draft") {
      setError("Select a saved draft Recipe before publishing it.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await reviseCommonProcessingRecipe(
        config,
        selected.processing_recipe_id,
        `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`,
        {
          content: { ...selected.content, lifecycle_state: "published" },
          change_reason: "Publish reviewed Processing Recipe",
        },
      );
      const refreshed = await listCommonProcessingRecipes(config);
      setRecipes(refreshed.data.items);
      setNotice(`Published Recipe revision ${result.data.current_revision.revision_no}; earlier revisions remain unchanged.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function addMethod(method: CommonProcessingMethod): void {
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      steps.push({ method_id: method.method_id, method_version: method.version, options: defaultOptions(method.method_id) });
      setStepsText(JSON.stringify(steps, null, 2));
      setError(null);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? caught.message : errorMessage(caught));
    }
  }

  async function saveProfile(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const content = JSON.parse(profileText) as CommonMappingProfileContent;
      const selected = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
      const result = selected
        ? await reviseCommonMappingProfile(
            config,
            selected.mapping_profile_id,
            `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`,
            { content, change_reason: changeReason },
          )
        : await createCommonMappingProfile(config, { classification, content, change_reason: changeReason });
      setSelectedProfileId(result.data.mapping_profile_id);
      const refreshed = await listCommonMappingProfiles(config);
      setProfiles(refreshed.data.items);
      setNotice(`Saved Mapping Profile revision ${result.data.current_revision.revision_no}.`);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid profile JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function runPreview(): Promise<void> {
    if (!document) {
      setError("Load one exact Test Data revision before previewing processing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await previewCommonProcessing(config, {
        document,
        mapping_profile: JSON.parse(profileText) as CommonMappingProfileContent,
        steps: JSON.parse(stepsText) as CommonProcessingStep[],
      });
      setPreview(result.data);
      setSelectedStage(result.data.stages.length - 1);
      setNotice("Preview completed. It is ephemeral and cannot be promoted or released.");
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid Workbench JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function commitOutput(): Promise<void> {
    const source = documents.find((item) => item.test_data_document_id === selectedDocumentId);
    const profile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
    if (!preview || !source || !profile) {
      setError("Preview an exact Test Data revision with a saved Mapping Profile before commit.");
      return;
    }
    if (preview.mapping_profile_sha256 !== profile.current_revision.content_hash) {
      setError("The preview differs from the selected exact input/profile. Save changes and preview again.");
      return;
    }
    if (source.current_revision.classification !== profile.current_revision.classification) {
      setError("Exact Test Data and Mapping Profile revisions must share classification.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await commitCommonProcessingOutput(config, {
        classification: source.current_revision.classification as DataClassification,
        label: outputLabel,
        source_document: {
          aggregate_id: source.test_data_document_id,
          revision_id: source.current_revision.id,
        },
        mapping_profile: {
          aggregate_id: profile.mapping_profile_id,
          revision_id: profile.current_revision.id,
        },
        steps: JSON.parse(stepsText) as CommonProcessingStep[],
        change_reason: outputReason,
      });
      const refreshed = await listCommonProcessingOutputs(config);
      setOutputs(refreshed.data.items);
      setNotice(
        `Committed immutable Processing Output ${result.data.processing_output_id} · ${result.data.output_sha256.slice(0, 12)}…`,
      );
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid step JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function downloadOutput(output: CommonProcessingOutputResponse): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const result = await downloadCommonProcessingOutput(config, output.processing_output_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded exact Processing Output ${output.output_sha256.slice(0, 12)}…`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function toggleEnsembleDocument(id: string): void {
    setEnsembleDocumentIds((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : current.length < 100 ? [...current, id] : current);
    setEnsemblePreview(null);
  }

  async function runEnsemblePreview(): Promise<void> {
    const selected = documents.filter((item) => ensembleDocumentIds.includes(item.test_data_document_id));
    if (selected.length < 2) {
      setError("Select at least two exact Test Data documents for replicate statistics.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const downloads = await Promise.all(selected.map((item) =>
        downloadCanonicalTestDataDocument(config, item.test_data_document_id, item.current_revision.id)));
      const canonicalDocuments = await Promise.all(downloads.map(async (item) =>
        JSON.parse(await item.data.blob.text()) as Record<string, unknown>));
      const result = await previewCommonProcessingEnsemble(config, {
        documents: canonicalDocuments,
        mapping_profile: JSON.parse(profileText) as CommonMappingProfileContent,
        preprocessing_steps: JSON.parse(stepsText) as CommonProcessingStep[],
        alignment: {
          point_count: ensemblePointCount,
          domain_policy: "intersection",
          extrapolation: "reject",
        },
      });
      setEnsemblePreview(result.data);
      setNotice(`Aligned ${result.data.members.length} immutable curves; every member remains visible.`);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid ensemble JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  const activeStage = preview?.stages[selectedStage] ?? null;
  const baseStage = preview?.stages[0] ?? null;
  const chart = useMemo(() => ({ width: 620, height: 250 }), []);
  const ensembleStatistic = ensemblePreview?.statistics[0] ?? null;
  const ensembleBounds = useMemo(() => {
    if (!ensemblePreview || !ensembleStatistic) return null;
    const values = [
      ...ensemblePreview.members.flatMap((member) =>
        member.stage.series.find((series) => series.quantity === ensembleStatistic.quantity)?.values ?? []),
      ...ensembleStatistic.confidence_95_lower,
      ...ensembleStatistic.confidence_95_upper,
    ];
    return {
      xMin: Math.min(...ensemblePreview.grid),
      xMax: Math.max(...ensemblePreview.grid),
      yMin: Math.min(...values),
      yMax: Math.max(...values),
    };
  }, [ensemblePreview, ensembleStatistic]);

  return (
    <main className="processing-workbench-page">
      <section className="page-hero compact-hero processing-hero">
        <div><p className="eyebrow">T-53 · configurable processing</p><h1>Processing Workbench</h1><p>Pin Test Data, reuse a Mapping Profile, compose versioned methods, and inspect every curve stage before commit.</p></div>
        <div className="hero-actions"><button className="button secondary" type="button" onClick={() => onNavigate("/datasets/test-json")}>Test Data JSON</button><button className="button secondary" type="button" onClick={onOpenConnection}>Connection</button></div>
      </section>
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {notice ? <div className="success-banner" role="status">{notice}</div> : null}

      <section className="processing-setup-grid">
        <article className="workbench-card processing-input-card">
          <p className="eyebrow">1 · exact input</p><h2>Test Data revision</h2>
          <label>Imported document<select aria-label="Test Data revision" value={selectedDocumentId} onChange={(event) => void loadDocument(event.target.value)}><option value="">Choose a document</option>{documents.map((item) => <option key={item.test_data_document_id} value={item.test_data_document_id}>{item.document_key} · r{item.current_revision.revision_no}</option>)}</select></label>
          <button className="button secondary" type="button" disabled={!selectedDocumentId || busy} onClick={() => void loadDocument(selectedDocumentId)}>Load exact JSON</button>
          {document ? <p className="mapping-note">Loaded <code>{String(document.document_id)}</code>. Original and normalized arrays remain unchanged.</p> : <p className="muted">Import Test Data JSON first, then load its exact revision.</p>}
        </article>

        <article className="workbench-card mapping-profile-card">
          <div className="section-heading"><div><p className="eyebrow">2 · reusable contract</p><h2>Mapping Profile</h2></div><span className="status-chip">{profiles.length} saved</span></div>
          <label>Saved profile<select aria-label="Saved Mapping Profile" value={selectedProfileId} onChange={(event) => selectProfile(event.target.value)}><option value="">New profile</option>{profiles.map((item) => <option key={item.mapping_profile_id} value={item.mapping_profile_id}>{item.content.label} · r{item.current_revision.revision_no}</option>)}</select></label>
          <label>Profile JSON<textarea className="mapping-profile-editor" aria-label="Mapping Profile JSON" value={profileText} onChange={(event) => setProfileText(event.target.value)} spellCheck={false} /></label>
          <div className="profile-save-row"><label>Classification<select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}><option value="internal">Internal</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option><option value="export_controlled">Export controlled</option></select></label><label>Change reason<input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} /></label><button className="button primary" type="button" disabled={busy || !changeReason.trim()} onClick={() => void saveProfile()}>{selectedProfileId ? "Append profile revision" : "Save new profile"}</button></div>
        </article>
      </section>

      <section className="workbench-card method-builder-card">
        <div className="section-heading"><div><p className="eyebrow">3 · ordered methods</p><h2>Pipeline builder</h2></div><button className="button primary" type="button" disabled={busy} onClick={() => void runPreview()}>{busy ? "Working…" : "Preview all stages"}</button></div>
        <div className="method-registry-strip">{methods.map((method) => <button type="button" className="method-pill" key={method.method_id} onClick={() => addMethod(method)} title={method.description}><strong>{method.label}</strong><small>{method.method_id} · {method.version}</small></button>)}</div>
        <label>Ordered step JSON<textarea className="pipeline-editor" aria-label="Ordered processing steps" value={stepsText} onChange={(event) => { setStepsText(event.target.value); setPreview(null); }} spellCheck={false} /></label>
        <p className="mapping-note">Methods are deterministic. The common resampler declares <code>extrapolation: reject</code>; unsupported or hidden policies fail before calculation.</p>
      </section>

      <section className="workbench-card recipe-library-card">
        <div className="section-heading"><div><p className="eyebrow">T-54 · reusable execution contract</p><h2>Processing Recipe library</h2></div><span className="status-chip">{recipes.length} saved</span></div>
        <p className="mapping-note">A Recipe pins one exact Mapping Profile revision and every ordered method version/options. Publishing appends a revision; it never edits a reviewed Recipe in place.</p>
        <div className="recipe-library-grid">
          <label>Saved Recipe<select aria-label="Saved Processing Recipe" value={selectedRecipeId} onChange={(event) => selectRecipe(event.target.value)}><option value="">New Recipe</option>{recipes.map((item) => <option key={item.processing_recipe_id} value={item.processing_recipe_id}>{item.content.label} · r{item.current_revision.revision_no} · {item.content.lifecycle_state}</option>)}</select></label>
          <label>Recipe key<input value={recipeKey} onChange={(event) => setRecipeKey(event.target.value)} /></label>
          <label>Label<input value={recipeLabel} onChange={(event) => setRecipeLabel(event.target.value)} /></label>
          <label>Description<input value={recipeDescription} onChange={(event) => setRecipeDescription(event.target.value)} /></label>
          <label>Change reason<input value={recipeReason} onChange={(event) => setRecipeReason(event.target.value)} /></label>
        </div>
        <div className="recipe-actions"><button className="button primary" type="button" disabled={busy || !selectedProfileId || !recipeKey.trim() || !recipeLabel.trim() || !recipeReason.trim()} onClick={() => void saveRecipe()}>{selectedRecipeId ? "Append draft revision" : "Save new Recipe"}</button><button className="button secondary" type="button" disabled={busy || !recipes.some((item) => item.processing_recipe_id === selectedRecipeId && item.content.lifecycle_state === "draft")} onClick={() => void publishRecipe()}>Publish reviewed revision</button></div>
        {selectedRecipeId ? <p className="digest-line"><span>Exact profile and Recipe content</span><code>{recipes.find((item) => item.processing_recipe_id === selectedRecipeId)?.content.mapping_profile_revision_id} · {recipes.find((item) => item.processing_recipe_id === selectedRecipeId)?.current_revision.content_hash}</code></p> : null}
      </section>

      <section className="workbench-card batch-monitor-card">
        <div className="section-heading"><div><p className="eyebrow">T-54 · reusable batch execution</p><h2>Batch Run Monitor</h2></div><span className="status-chip">{batches.length} batches</span></div>
        <p className="mapping-note">The selected published Recipe, Mapping Profile, and every Test Data revision are pinned exactly. Compatibility is checked before execution; successful outputs survive other member failures.</p>
        <div className="batch-builder-grid">
          <fieldset><legend>Exact Test Data selection</legend>{documents.map((item) => <label key={item.test_data_document_id}><input type="checkbox" checked={batchDocumentIds.includes(item.test_data_document_id)} onChange={() => toggleBatchDocument(item.test_data_document_id)} />{item.document_key} · r{item.current_revision.revision_no}</label>)}</fieldset>
          <div className="batch-actions"><label>Batch label<input aria-label="Processing Batch label" value={batchLabel} onChange={(event) => setBatchLabel(event.target.value)} /></label><button className="button secondary" type="button" disabled={busy || !selectedRecipeId || !batchDocumentIds.length} onClick={() => void preflightBatch()}>Run compatibility preflight</button><button className="button primary" type="button" disabled={busy || !batchPreflight?.compatible || !batchLabel.trim()} onClick={() => void executeBatch()}>Execute published Recipe</button></div>
        </div>
        {batchPreflight ? <div className="batch-preflight" aria-label="Batch compatibility report"><div className="batch-summary"><strong>{batchPreflight.compatible ? "Compatible" : "Blocked"}</strong><span>{batchPreflight.members.length} exact revisions</span><code>{batchPreflight.recipe_sha256}</code></div>{batchPreflight.members.map((member) => <article key={`${member.source.document_id}-${member.source.revision_id}`}><span className={`status-chip ${member.compatible ? "" : "warning"}`}>{member.compatible ? "ready" : "incompatible"}</span><div><strong>Member {member.ordinal + 1}</strong><small>{member.final_point_count ?? 0} output points</small><code>{member.source.revision_id}</code>{member.diagnostic ? <p>{member.diagnostic}</p> : null}</div></article>)}</div> : <p className="muted">Choose a published Recipe and exact Test Data revisions, then run preflight.</p>}
        {batches.length ? <div className="batch-run-list">{batches.map((batch) => <article key={batch.batch_id}><div className="batch-run-heading"><div><strong>{batch.label}</strong><small>{batch.members.length} members · {batch.attempts.length} attempts</small></div><span className={`status-chip ${batch.status === "partial" || batch.status === "failed" ? "warning" : ""}`}>{batch.status}</span></div><code>{batch.recipe_revision_id}</code><div className="batch-member-list">{batch.members.map((member) => { const attempts = batch.attempts.filter((attempt) => attempt.member_id === member.member_id); const latest = attempts.at(-1); return <div key={member.member_id}><span>#{member.ordinal + 1}</span><strong>{latest?.status ?? "planned"}</strong><small>attempt {latest?.attempt_no ?? 0}</small><code>{latest?.output_revision_id ?? latest?.error_code ?? member.source.revision_id}</code></div>; })}</div>{batch.status === "partial" || batch.status === "failed" ? <button className="button secondary" type="button" disabled={busy} onClick={() => void retryFailedBatch(batch.batch_id)}>Retry failed members only</button> : null}</article>)}</div> : null}
      </section>

      <section className="processing-result-grid">
        <article className="workbench-card stage-list-card">
          <p className="eyebrow">4 · immutable stage view</p><h2>Stage history</h2>
          {preview ? <div className="stage-list">{preview.stages.map((stage) => <button className={selectedStage === stage.ordinal ? "stage-item active" : "stage-item"} type="button" key={`${stage.ordinal}-${stage.method_id}`} onClick={() => setSelectedStage(stage.ordinal)}><span>{stage.ordinal}</span><div><strong>{stage.method_id}</strong><small>{stage.point_count} points · {stage.method_version}</small></div></button>)}</div> : <p className="muted">Run a preview to preserve and compare the mapped and processed stages.</p>}
        </article>
        <article className="workbench-card curve-overlay-card">
          <div className="section-heading"><div><p className="eyebrow">Curve overlay</p><h2>{activeStage?.method_id ?? "Awaiting preview"}</h2></div>{preview ? <span className="status-chip warning">Preview only · not promotable</span> : null}</div>
          {preview && activeStage && baseStage ? <StageCurveEvidence preview={preview} activeStage={activeStage} baseStage={baseStage} width={chart.width} height={chart.height} /> : <p className="muted">The overlay uses the actual server result. No browser-only curve is treated as evidence.</p>}
        </article>
      </section>

      <section className="workbench-card processing-output-card">
        <div className="section-heading"><div><p className="eyebrow">5 · immutable output</p><h2>Commit reviewed result</h2></div><span className="status-chip">{outputs.length} committed</span></div>
        <p className="mapping-note">Commit recomputes the selected exact Test Data and saved Mapping Profile on the server. Preview arrays are never accepted as authoritative output.</p>
        <div className="processing-output-form"><label>Output label<input value={outputLabel} onChange={(event) => setOutputLabel(event.target.value)} /></label><label>Change reason<input value={outputReason} onChange={(event) => setOutputReason(event.target.value)} /></label><button className="button primary" type="button" disabled={busy || !preview || !selectedProfileId || !outputLabel.trim() || !outputReason.trim()} onClick={() => void commitOutput()}>Commit immutable output</button></div>
        {outputs.length ? <div className="processing-output-list">{outputs.map((output) => <article key={output.processing_output_id}><div><strong>{output.label}</strong><small>r{output.current_revision.revision_no} · {output.final_point_count} points · {output.stage_count} stages</small><code>{output.output_sha256}</code></div><button className="button secondary" type="button" disabled={busy} onClick={() => void downloadOutput(output)}>Download JSON</button></article>)}</div> : <p className="muted">No committed common Processing Output is visible yet.</p>}
      </section>

      <section className="workbench-card ensemble-card">
        <div className="section-heading"><div><p className="eyebrow">6 · replicate evidence</p><h2>Alignment and pointwise statistics</h2></div><span className="status-chip warning">Preview · members retained</span></div>
        <p className="mapping-note">Select multiple exact Test Data heads. Alignment uses only their observed domain intersection and rejects extrapolation; no raw curve or outlier is deleted.</p>
        <div className="ensemble-methods">{ensembleMethods.map((method) => <article key={method.method_id}><strong>{method.label}</strong><code>{method.method_id} · {method.version}</code><small>{method.description}</small></article>)}</div>
        <div className="ensemble-controls"><fieldset><legend>Exact Test Data members</legend>{documents.map((item) => <label key={item.test_data_document_id}><input type="checkbox" checked={ensembleDocumentIds.includes(item.test_data_document_id)} onChange={() => toggleEnsembleDocument(item.test_data_document_id)} />{item.document_key} · r{item.current_revision.revision_no}</label>)}</fieldset><label>Common grid points<input type="number" min="2" max="100000" value={ensemblePointCount} onChange={(event) => { setEnsemblePointCount(Number(event.target.value)); setEnsemblePreview(null); }} /></label><button className="button primary" type="button" disabled={busy || ensembleDocumentIds.length < 2} onClick={() => void runEnsemblePreview()}>Align and calculate</button></div>
        {ensemblePreview && ensembleStatistic && ensembleBounds ? <div className="ensemble-results"><svg className="processing-curve ensemble-curve" role="img" aria-label="Aligned replicate curves with pointwise mean and confidence interval" viewBox={`0 0 ${chart.width} ${chart.height}`}><line x1="28" y1={chart.height - 24} x2={chart.width - 20} y2={chart.height - 24} className="chart-axis"/><line x1="28" y1="20" x2="28" y2={chart.height - 24} className="chart-axis"/>{ensemblePreview.members.map((member) => { const values = member.stage.series.find((series) => series.quantity === ensembleStatistic.quantity)?.values ?? []; return <polyline key={member.ordinal} points={xyPoints(ensemblePreview.grid, values, chart.width, chart.height, ensembleBounds)} className="curve-line ensemble-member"/>; })}<polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.confidence_95_lower, chart.width, chart.height, ensembleBounds)} className="curve-line confidence"/><polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.confidence_95_upper, chart.width, chart.height, ensembleBounds)} className="curve-line confidence"/><polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.mean, chart.width, chart.height, ensembleBounds)} className="curve-line ensemble-mean"/></svg><div className="curve-legend"><span><i className="ensemble-member"/>Members ({ensemblePreview.members.length})</span><span><i className="ensemble-mean"/>Mean</span><span><i className="confidence"/>95% mean CI</span></div><div className="statistics-grid"><article><span>Quantity</span><strong>{ensembleStatistic.quantity}</strong><small>{ensembleStatistic.unit}</small></article><article><span>Last mean</span><strong>{ensembleStatistic.mean.at(-1)?.toPrecision(6)}</strong></article><article><span>Sample SD</span><strong>{ensembleStatistic.standard_deviation.at(-1)?.toPrecision(6)}</strong></article><article><span>MAD</span><strong>{ensembleStatistic.mad.at(-1)?.toPrecision(6)}</strong></article><article><span>IQR</span><strong>{ensembleStatistic.q1.at(-1)?.toPrecision(4)} – {ensembleStatistic.q3.at(-1)?.toPrecision(4)}</strong></article></div><div className="stage-diagnostics">{ensemblePreview.diagnostics.map((item) => <p key={item}>{item}</p>)}</div></div> : <p className="muted">At least two imported Test Data identities are required. Import each replicate separately so its exact revision remains addressable.</p>}
      </section>
    </main>
  );
}
