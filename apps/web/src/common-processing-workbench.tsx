import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { EngineeringCurvePlot } from "./engineering-curve-plot";

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
import { DomainWorkflowLinks } from "./domain-workflow-links";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
  onModelingTrackChange?: (track: ModelingTrack) => void;
  familyWorkbench?: ReactNode;
}

export type ModelingTrack = "metal" | "polymer" | "elastomer";
type WorkspaceInspector = "step" | "recipe" | "batch";

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

const POLYMER_RELAXATION_PROFILE: CommonMappingProfileContent = {
  profile_key: "polymer-shear-relaxation",
  label: "Polymer shear relaxation channels",
  independent_quantity: "time",
  missing_data_policy: "drop_any",
  bindings: [
    {
      channel_key: "time_s",
      target_quantity: "time",
      accepted_normalized_units: ["s"],
      required: true,
      scale: 1,
      offset: 0,
    },
    {
      channel_key: "shear_modulus_mpa",
      target_quantity: "modulus.shear.relaxation",
      accepted_normalized_units: ["Pa"],
      required: true,
      scale: 1,
      offset: 0,
    },
  ],
  attribute_bindings: [],
};

const ELASTOMER_CURVE_PROFILE: CommonMappingProfileContent = {
  profile_key: "elastomer-test-mode-preparation",
  label: "Elastomer test-mode curve preparation",
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

const ELASTOMER_PREPARATION_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
];

const POLYMER_RELAXATION_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
  {
    method_id: "curve.crop",
    method_version: "1.0.0",
    options: { minimum: 0.01, maximum: 100 },
  },
  {
    method_id: "polymer.log_time_resample",
    method_version: "1.0.0",
    options: { start_time_s: 0.01, end_time_s: 100, count: 81, extrapolation: "reject" },
  },
  {
    method_id: "polymer.prony_fit_compare",
    method_version: "1.0.0",
    options: {
      time_quantity: "time",
      modulus_quantity: "modulus.shear.relaxation",
      candidate_term_counts: [1, 2, 3, 4],
      selection_mode: "automatic_bic",
      selected_term_count: 2,
      normalization_modulus_pa: 1000000000,
      minimum_relaxation_time_s: 0.0001,
      maximum_relaxation_time_s: 1000000,
      maximum_function_evaluations: 5000,
    },
  },
];

const METAL_TENSILE_STEPS: CommonProcessingStep[] = [
  {
    method_id: "rows.sort_unique",
    method_version: "1.0.0",
    options: { duplicate_policy: "reject" },
  },
  {
    method_id: "metal.elastic_modulus",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      method: "robust_huber",
      minimum_strain: 0.0002,
      maximum_strain: 0.002,
      manual_modulus_pa: 210000000000,
    },
  },
  {
    method_id: "metal.proof_stress",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      youngs_modulus_pa: 210000000000,
      offset_strain: 0.002,
      search_start: 0.002,
      search_end: 0.1,
    },
  },
  {
    method_id: "metal.necking_candidate",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      method: "peak_engineering_stress",
    },
  },
  {
    method_id: "metal.engineering_to_true_plastic",
    method_version: "1.0.0",
    options: {
      strain_quantity: "strain.engineering",
      stress_quantity: "stress.engineering",
      youngs_modulus_pa: 210000000000,
      necking_policy: "observed_full_domain",
      manual_necking_index: 1,
      negative_plastic_policy: "drop",
    },
  },
  {
    method_id: "metal.hardening_fit_extrapolate",
    method_version: "1.0.0",
    options: {
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

function xyPoints(
  x: number[],
  y: number[],
  width: number,
  height: number,
  bounds: { xMin: number; xMax: number; yMin: number; yMax: number },
  margins: { left: number; right: number; top: number; bottom: number } = {
    left: 28,
    right: 20,
    top: 20,
    bottom: 24,
  },
): string {
  const { xMin, xMax, yMin, yMax } = bounds;
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  return x
    .map((value, index) => {
      const px = margins.left + ((value - xMin) / xRange) * (width - margins.left - margins.right);
      const py = height - margins.bottom - ((y[index] - yMin) / yRange) * (height - margins.top - margins.bottom);
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .join(" ");
}

function documentMatchesTrack(
  item: CanonicalTestDataDocumentResponse,
  track: ModelingTrack,
): boolean {
  const quantities = item.channels.map((channel) => channel.quantity_semantics.toLowerCase());
  const hasQuantity = (suffix: string) => quantities.some((quantity) => quantity === suffix || quantity.endsWith(`.${suffix}`));
  if (track === "polymer") {
    return hasQuantity("time.elapsed") && hasQuantity("modulus.shear.relaxation");
  }
  const hasStressStrain = hasQuantity("strain.engineering") && hasQuantity("stress.engineering");
  if (!hasStressStrain) return false;
  const method = item.method.trim().toLowerCase();
  if (track === "metal") return method === "tensile" || method === "uniaxial tensile reference method";
  return ["uniaxial", "planar", "biaxial"].some((mode) => method === mode || method === `${mode} tension`);
}

interface PlotBounds {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

function paddedBounds(x: number[], y: number[]): PlotBounds {
  const finiteX = x.filter(Number.isFinite);
  const finiteY = y.filter(Number.isFinite);
  if (!finiteX.length || !finiteY.length) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
  const xMin = Math.min(...finiteX);
  const xMax = Math.max(...finiteX);
  const yMin = Math.min(...finiteY);
  const yMax = Math.max(...finiteY);
  const xPadding = Math.max((xMax - xMin) * 0.025, Math.abs(xMax || 1) * 0.0025);
  const yPadding = Math.max((yMax - yMin) * 0.06, Math.abs(yMax || 1) * 0.01);
  return {
    xMin: xMin - xPadding,
    xMax: xMax + xPadding,
    yMin: yMin - yPadding,
    yMax: yMax + yPadding,
  };
}

export function CommonProcessingWorkbench({ config, onNavigate, onModelingTrackChange, familyWorkbench }: Props) {
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
  const [stepsText, setStepsText] = useState(JSON.stringify(METAL_TENSILE_STEPS, null, 2));
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
  const [selectedStepIndex, setSelectedStepIndex] = useState(0);
  const [modelingTrack, setModelingTrack] = useState<ModelingTrack>("metal");
  const [workspaceInspector, setWorkspaceInspector] = useState<WorkspaceInspector>("step");
  const [ensembleDocumentIds, setEnsembleDocumentIds] = useState<string[]>([]);
  const [batchDocumentIds, setBatchDocumentIds] = useState<string[]>([]);
  const [batchLabel, setBatchLabel] = useState("Published Recipe batch");
  const [batchPreflight, setBatchPreflight] = useState<CommonProcessingBatchPreflight | null>(null);
  const [ensemblePointCount, setEnsemblePointCount] = useState(21);
  const [ensemblePreview, setEnsemblePreview] = useState<CommonEnsemblePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const autoPreviewKey = useRef("");

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
      })
      .catch((caught: unknown) => setError(errorMessage(caught)));
  }, [config]);

  async function loadDocument(id: string): Promise<void> {
    autoPreviewKey.current = "";
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

  useEffect(() => {
    if (selectedDocumentId || !documents.length) return;
    const compatible = documents.find((item) => documentMatchesTrack(item, modelingTrack));
    if (compatible) setSelectedDocumentId(compatible.test_data_document_id);
  }, [documents, modelingTrack, selectedDocumentId]);

  useEffect(() => {
    if (selectedProfileId || !profiles.length) return;
    const compatible = profiles.find((item) => {
      const content = item.content;
      if (modelingTrack === "metal") {
        return content.independent_quantity.includes("strain")
          && content.bindings.some((binding) => binding.target_quantity.includes("stress"));
      }
      if (modelingTrack === "polymer") {
        return content.independent_quantity === "time"
          || content.profile_key.includes("polymer");
      }
      return content.profile_key.includes("elastomer");
    });
    if (!compatible) return;
    setSelectedProfileId(compatible.mapping_profile_id);
    setProfileText(JSON.stringify(compatible.content, null, 2));
  }, [modelingTrack, profiles, selectedProfileId]);

  useEffect(() => {
    if (!selectedDocumentId || document || busy) return;
    void loadDocument(selectedDocumentId);
  }, [busy, document, selectedDocumentId]);

  useEffect(() => {
    if (!document || !selectedProfileId || busy || preview) return;
    const key = `${selectedDocumentId}:${selectedProfileId}:${stepsText}`;
    if (autoPreviewKey.current === key) return;
    const timer = window.setTimeout(() => {
      autoPreviewKey.current = key;
      void runPreview();
    }, 180);
    return () => window.clearTimeout(timer);
  }, [busy, document, preview, selectedDocumentId, selectedProfileId, stepsText]);

  function applyModelingTrack(track: ModelingTrack): void {
    setModelingTrack(track);
    onModelingTrackChange?.(track);
  }

  function selectProfile(id: string): void {
    setSelectedProfileId(id);
    const item = profiles.find((candidate) => candidate.mapping_profile_id === id);
    if (item) {
      setProfileText(JSON.stringify(item.content, null, 2));
      if (item.content.profile_key.includes("polymer") || item.content.independent_quantity === "time") applyModelingTrack("polymer");
      else if (item.content.profile_key.includes("elastomer")) applyModelingTrack("elastomer");
      else applyModelingTrack("metal");
    }
  }

  function useProfileTemplate(
    profile: CommonMappingProfileContent,
    steps: CommonProcessingStep[],
  ): void {
    setSelectedProfileId("");
    setProfileText(JSON.stringify(profile, null, 2));
    setStepsText(JSON.stringify(steps, null, 2));
    setSelectedStepIndex(0);
    setPreview(null);
    setNotice(`Loaded the ${profile.label} template. Confirm channel keys, units, and bounds before saving.`);
  }

  function selectModelingTrack(track: ModelingTrack): void {
    applyModelingTrack(track);
    setWorkspaceInspector("step");
    // A family switch changes the quantity contract. Do not silently carry a Test Data
    // revision from another family into the new track; the user must select the exact input.
    setSelectedDocumentId("");
    setDocument(null);
    setBatchDocumentIds([]);
    if (track === "metal") useProfileTemplate(DEFAULT_PROFILE, METAL_TENSILE_STEPS);
    if (track === "polymer") useProfileTemplate(POLYMER_RELAXATION_PROFILE, POLYMER_RELAXATION_STEPS);
    if (track === "elastomer") {
      useProfileTemplate(ELASTOMER_CURVE_PROFILE, ELASTOMER_PREPARATION_STEPS);
      setNotice("Elastomer multi-mode preparation is selected. T-80 connects its saved Plan and candidate controls without treating a single curve as a complete fit.");
    }
    setSelectedRecipeId("");
    setBatchPreflight(null);
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
    if (item.content.steps.some((step) => step.method_id.startsWith("polymer."))) applyModelingTrack("polymer");
    else if (item.content.steps.some((step) => step.method_id.startsWith("metal."))) applyModelingTrack("metal");
    setSelectedStepIndex(0);
    setPreview(null);
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
      setSelectedStepIndex(steps.length - 1);
      setPreview(null);
      setError(null);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? caught.message : errorMessage(caught));
    }
  }

  function updateStepOption(option: string, value: unknown): void {
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      const step = steps[selectedStepIndex];
      if (!step) return;
      steps[selectedStepIndex] = { ...step, options: { ...step.options, [option]: value } };
      setStepsText(JSON.stringify(steps, null, 2));
      setPreview(null);
    } catch {
      setError("The advanced processing definition is not valid JSON.");
    }
  }

  function parseStepOption(value: unknown, rawValue: string): unknown {
    if (typeof value === "number") return Number(rawValue);
    if (!Array.isArray(value)) return rawValue;
    const items = rawValue.split(",").map((item) => item.trim()).filter(Boolean);
    return typeof value[0] === "number" ? items.map(Number) : items;
  }

  function removeSelectedStep(): void {
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      steps.splice(selectedStepIndex, 1);
      setStepsText(JSON.stringify(steps, null, 2));
      setSelectedStepIndex(Math.max(0, selectedStepIndex - 1));
      setPreview(null);
    } catch {
      setError("The advanced processing definition is not valid JSON.");
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
  const configuredSteps = useMemo(() => {
    try {
      return JSON.parse(stepsText) as CommonProcessingStep[];
    } catch {
      return [];
    }
  }, [stepsText]);
  const trackDocuments = useMemo(
    () => documents.filter((item) => documentMatchesTrack(item, modelingTrack)),
    [documents, modelingTrack],
  );
  const selectedTrackDocument = trackDocuments.find(
    (item) => item.test_data_document_id === selectedDocumentId,
  );
  useEffect(() => {
    const exactIds = new Set(trackDocuments.map((item) => item.test_data_document_id));
    if (!exactIds.has(selectedDocumentId)) {
      setSelectedDocumentId(trackDocuments[0]?.test_data_document_id ?? "");
      setDocument(null);
      setPreview(null);
    }
    setEnsembleDocumentIds((current) => {
      const compatible = current.filter((id) => exactIds.has(id));
      return compatible.length ? compatible : trackDocuments.slice(0, 2).map((item) => item.test_data_document_id);
    });
    setBatchDocumentIds((current) => {
      const compatible = current.filter((id) => exactIds.has(id));
      return compatible.length ? compatible : trackDocuments.slice(0, 2).map((item) => item.test_data_document_id);
    });
  }, [modelingTrack, selectedDocumentId, trackDocuments]);
  const selectedConfiguredStep = configuredSteps[selectedStepIndex] ?? null;
  const trackRecipes = useMemo(() => recipes.filter((recipe) => {
    const methodIds = recipe.content.steps.map((step) => step.method_id);
    if (modelingTrack === "metal") return methodIds.some((methodId) => methodId.startsWith("metal."));
    if (modelingTrack === "polymer") return methodIds.some((methodId) => methodId.startsWith("polymer."));
    return !methodIds.some((methodId) => methodId.startsWith("metal.") || methodId.startsWith("polymer."));
  }), [recipes, modelingTrack]);
  const trackMethods = useMemo(() => methods.filter((method) => {
    const family = method.method_id.split(".")[0];
    if (family === "metal") return modelingTrack === "metal";
    if (family === "polymer") return modelingTrack === "polymer";
    return true;
  }), [methods, modelingTrack]);
  const chart = useMemo(() => ({ width: 760, height: 420 }), []);
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

  function focusConfiguredStep(index: number): void {
    setSelectedStepIndex(index);
    setWorkspaceInspector("step");
    const stage = preview?.stages.find((item) => item.ordinal === index + 1);
    if (stage) setSelectedStage(stage.ordinal);
  }

  return (
    <main className="processing-workbench-page">
      <header className="modeling-app-header">
        <div className="modeling-session-heading"><p className="eyebrow">Material Modeling</p><h1>Test curves to material model</h1><p>Exact Test Data · live processing preview · immutable reviewed output</p></div>
        <div className="modeling-session-actions"><button className="button secondary" type="button" onClick={() => onNavigate("/datasets/test-json")}>Import test data</button><button className="button secondary" type="button" onClick={() => onNavigate("/database")}>Material Database</button></div>
        <nav className="modeling-flow-nav" aria-label="Material Modeling steps"><a href="#modeling-import">Import</a><a href="#modeling-map">Map</a><a href="#modeling-prepare">Prepare</a><a href="#modeling-fit">Fit</a><a href="#modeling-fit">Extrapolate</a><a href="#modeling-output">Card</a></nav>
        <div className="modeling-track-selector" role="tablist" aria-label="Material modeling family">
          <button type="button" role="tab" aria-selected={modelingTrack === "metal"} className={modelingTrack === "metal" ? "active metal" : "metal"} onClick={() => selectModelingTrack("metal")}><span>Metal</span><strong>Elastoplastic</strong><small>E, proof, necking, hardening</small></button>
          <button type="button" role="tab" aria-selected={modelingTrack === "polymer"} className={modelingTrack === "polymer" ? "active polymer" : "polymer"} onClick={() => selectModelingTrack("polymer")}><span>Polymer</span><strong>Viscoelastic</strong><small>Log-time, Prony candidates</small></button>
          <button type="button" role="tab" aria-selected={modelingTrack === "elastomer"} className={modelingTrack === "elastomer" ? "active elastomer" : "elastomer"} onClick={() => selectModelingTrack("elastomer")}><span>Elastomer</span><strong>Hyper-viscoelastic</strong><small>Multi-mode, stability, Prony</small></button>
        </div>
      </header>
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {notice ? <div className="success-banner" role="status">{notice}</div> : null}

      <section className="processing-setup-grid">
        <article className="workbench-card processing-input-card" id="modeling-import">
          <p className="eyebrow">1 · exact input</p><h2>Test Data revision</h2>
          <label>Imported document<select aria-label="Test Data revision" value={selectedDocumentId} onChange={(event) => void loadDocument(event.target.value)}><option value="">Choose a compatible document</option>{trackDocuments.map((item) => <option key={item.test_data_document_id} value={item.test_data_document_id}>{item.document_key} · r{item.current_revision.revision_no}</option>)}</select></label>
          <button className="button secondary" type="button" disabled={!selectedDocumentId || busy} onClick={() => void loadDocument(selectedDocumentId)}>Load exact JSON</button>
          {document && selectedTrackDocument ? <p className="mapping-note">Loaded <strong>{selectedTrackDocument.document_key}</strong> · revision {selectedTrackDocument.current_revision.revision_no}. Original and normalized arrays remain unchanged.</p> : <p className="muted">{modelingTrack === "elastomer" ? "Select multi-mode governed Datasets in the family calibration panel below, or import a canonical Test JSON for common preprocessing." : "Choose one exact family-compatible Test Data revision, then load its JSON."}</p>}
        </article>

        <article className="workbench-card mapping-profile-card" id="modeling-map">
          <div className="section-heading"><div><p className="eyebrow">2 · reusable contract</p><h2>Mapping Profile</h2></div><span className="status-chip">{profiles.length} saved</span></div>
          <label>Saved profile<select aria-label="Saved Mapping Profile" value={selectedProfileId} onChange={(event) => selectProfile(event.target.value)}><option value="">New profile</option>{profiles.map((item) => <option key={item.mapping_profile_id} value={item.mapping_profile_id}>{item.content.label} · r{item.current_revision.revision_no}</option>)}</select></label>
          <p className="track-contract-note"><strong>{modelingTrack === "metal" ? "Metal tensile" : modelingTrack === "polymer" ? "Polymer relaxation" : "Elastomer multi-mode"}</strong>{modelingTrack === "elastomer" ? " requires uniaxial, planar or biaxial roles; no single curve is silently treated as a complete calibration." : " profile and ordered method defaults are loaded from the selected family track."}</p>
          <details className="advanced-definition"><summary>Advanced mapping definition</summary><label>Profile JSON<textarea className="mapping-profile-editor" aria-label="Mapping Profile JSON" value={profileText} onChange={(event) => setProfileText(event.target.value)} spellCheck={false} /></label></details>
          <div className="profile-save-row"><label>Classification<select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}><option value="internal">Internal</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option><option value="export_controlled">Export controlled</option></select></label><label>Change reason<input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} /></label><button className="button primary" type="button" disabled={busy || !changeReason.trim()} onClick={() => void saveProfile()}>{selectedProfileId ? "Append profile revision" : "Save new profile"}</button></div>
        </article>
      </section>

      <section className="workbench-card method-builder-card" id="modeling-prepare">
        <div className="section-heading"><div><p className="eyebrow">3 · Prepare, fit and extrapolate</p><h2>Processing pipeline</h2></div><button className="button primary" type="button" disabled={busy} onClick={() => void runPreview()}>{busy ? "Working…" : "Preview changes"}</button></div>
        <details className="method-library"><summary>Add a processing method <span>{trackMethods.length} compatible</span></summary><div className="method-registry-strip" aria-label="Available processing methods">{trackMethods.map((method) => <button type="button" className="method-pill" key={method.method_id} onClick={() => addMethod(method)} title={method.description}><strong>+ {method.label}</strong><small>{method.version}</small></button>)}</div></details>
        <div className="modeling-graph-workspace">
          <aside className="modeling-workspace-rail">
            <div className="modeling-dataset-list"><p className="eyebrow">Datasets &amp; curves</p>{trackDocuments.map((item) => <button type="button" className={selectedDocumentId === item.test_data_document_id ? "active" : ""} key={item.test_data_document_id} onClick={() => void loadDocument(item.test_data_document_id)}><span className="dataset-curve-swatch"/><span><strong>{item.document_key}</strong><small>Exact revision r{item.current_revision.revision_no}</small></span></button>)}{!trackDocuments.length ? <p className="muted">No Test Data revision declares the quantities required by this material track.</p> : null}</div>
            <div className="configured-step-list"><p className="eyebrow">Recipe steps</p>{configuredSteps.map((step, index) => <button type="button" className={selectedStepIndex === index ? "active" : ""} key={`${index}:${step.method_id}`} onClick={() => focusConfiguredStep(index)}><span>{index + 1}</span><span><strong>{methods.find((method) => method.method_id === step.method_id)?.label ?? step.method_id}</strong><small>{step.method_version}</small></span></button>)}</div>
          </aside>
          <article className="persistent-modeling-plot" id="modeling-fit">
            <div className="section-heading"><div><p className="eyebrow">Live curve comparison</p><h2>{activeStage?.method_id ?? "Load data and preview"}</h2></div>{preview ? <span className="status-chip warning">Preview only · not committed</span> : null}</div>
            {preview && activeStage && baseStage ? <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={chart.width} height={chart.height} /> : <div className="modeling-plot-empty"><strong>The graph stays here while you configure processing.</strong><p>Load an exact Test Data revision and choose Preview changes. Server-calculated raw and processed curves will be overlaid without changing the source.</p></div>}
            {preview ? <div className="stage-chip-rail" aria-label="Preview stage history">{preview.stages.map((stage) => <button className={selectedStage === stage.ordinal ? "active" : ""} type="button" key={`${stage.ordinal}-${stage.method_id}`} onClick={() => setSelectedStage(stage.ordinal)}><span>{stage.ordinal}</span><strong>{stage.method_id}</strong><small>{stage.point_count} points</small></button>)}</div> : null}
          </article>
          <aside className="step-option-panel">
            <nav className="workspace-inspector-tabs" aria-label="Modeling workspace inspector">
              <button type="button" className={workspaceInspector === "step" ? "active" : ""} onClick={() => setWorkspaceInspector("step")}>Step options</button>
              <button type="button" className={workspaceInspector === "recipe" ? "active" : ""} onClick={() => setWorkspaceInspector("recipe")}>Recipe <span>{trackRecipes.length}</span></button>
              <button type="button" className={workspaceInspector === "batch" ? "active" : ""} onClick={() => setWorkspaceInspector("batch")}>Batch <span>{batches.length}</span></button>
            </nav>
            {workspaceInspector === "step" ? selectedConfiguredStep ? <>
              <div className="section-heading"><div><p className="eyebrow">Step {selectedStepIndex + 1}</p><h3>{methods.find((method) => method.method_id === selectedConfiguredStep.method_id)?.label ?? selectedConfiguredStep.method_id}</h3></div><button className="text-button" type="button" onClick={removeSelectedStep}>Remove</button></div>
              <div className="step-option-grid">{Object.entries(selectedConfiguredStep.options).map(([option, value]) => <label key={option}>{option.replaceAll("_", " ")}{typeof value === "boolean" ? <input type="checkbox" checked={value} onChange={(event) => updateStepOption(option, event.target.checked)} /> : <input value={Array.isArray(value) ? value.join(", ") : String(value)} type={typeof value === "number" ? "number" : "text"} onChange={(event) => updateStepOption(option, parseStepOption(value, event.target.value))} />}</label>)}</div>
            </> : <p className="muted">Add or select a processing step.</p> : null}
            {workspaceInspector === "recipe" ? <div className="inspector-recipe-panel">
              <div className="section-heading"><div><p className="eyebrow">Reusable execution</p><h3>Processing Recipe</h3></div><span className="status-chip">{trackRecipes.length} saved</span></div>
              <label>Saved Recipe<select aria-label="Saved Processing Recipe" value={selectedRecipeId} onChange={(event) => selectRecipe(event.target.value)}><option value="">New Recipe</option>{trackRecipes.map((item) => <option key={item.processing_recipe_id} value={item.processing_recipe_id}>{item.content.label} · r{item.current_revision.revision_no} · {item.content.lifecycle_state}</option>)}</select></label>
              <label>Recipe key<input value={recipeKey} onChange={(event) => setRecipeKey(event.target.value)} /></label>
              <label>Label<input value={recipeLabel} onChange={(event) => setRecipeLabel(event.target.value)} /></label>
              <label>Description<input value={recipeDescription} onChange={(event) => setRecipeDescription(event.target.value)} /></label>
              <label>Change reason<input value={recipeReason} onChange={(event) => setRecipeReason(event.target.value)} /></label>
              <div className="inspector-action-stack"><button className="button primary" type="button" disabled={busy || !selectedProfileId || !recipeKey.trim() || !recipeLabel.trim() || !recipeReason.trim()} onClick={() => void saveRecipe()}>{selectedRecipeId ? "Append draft revision" : "Save new Recipe"}</button><button className="button secondary" type="button" disabled={busy || !recipes.some((item) => item.processing_recipe_id === selectedRecipeId && item.content.lifecycle_state === "draft")} onClick={() => void publishRecipe()}>Publish reviewed revision</button></div>
              {selectedRecipeId ? <p className="digest-line"><span>Exact Recipe</span><code>{recipes.find((item) => item.processing_recipe_id === selectedRecipeId)?.current_revision.content_hash}</code></p> : <p className="muted">Save these ordered method versions and options for reuse.</p>}
            </div> : null}
            {workspaceInspector === "batch" ? <div className="inspector-batch-panel">
              <div className="section-heading"><div><p className="eyebrow">Exact revision batch</p><h3>Batch execution</h3></div><span className="status-chip">{batches.length} runs</span></div>
              <fieldset><legend>Test Data selection</legend>{trackDocuments.map((item) => <label key={item.test_data_document_id}><input type="checkbox" checked={batchDocumentIds.includes(item.test_data_document_id)} onChange={() => toggleBatchDocument(item.test_data_document_id)} />{item.document_key} · r{item.current_revision.revision_no}</label>)}</fieldset>
              <label>Batch label<input aria-label="Processing Batch label" value={batchLabel} onChange={(event) => setBatchLabel(event.target.value)} /></label>
              <div className="inspector-action-stack"><button className="button secondary" type="button" disabled={busy || !selectedRecipeId || !batchDocumentIds.length} onClick={() => void preflightBatch()}>Compatibility preflight</button><button className="button primary" type="button" disabled={busy || !batchPreflight?.compatible || !batchLabel.trim()} onClick={() => void executeBatch()}>Execute published Recipe</button></div>
              {batchPreflight ? <div className="batch-summary"><strong>{batchPreflight.compatible ? "Compatible" : "Blocked"}</strong><span>{batchPreflight.members.length} exact revisions</span><code>{batchPreflight.recipe_sha256}</code></div> : <p className="muted">Select a published Recipe in the Recipe tab, then check exact inputs.</p>}
              <div className="inspector-batch-history">{batches.map((batch) => <article key={batch.batch_id}><div><strong>{batch.label}</strong><small>{batch.members.length} members · {batch.attempts.length} attempts</small></div><span className={`status-chip ${batch.status === "partial" || batch.status === "failed" ? "warning" : ""}`}>{batch.status}</span>{batch.status === "partial" || batch.status === "failed" ? <button className="text-button" type="button" disabled={busy} onClick={() => void retryFailedBatch(batch.batch_id)}>Retry failed</button> : null}</article>)}</div>
            </div> : null}
          </aside>
        </div>
        <details className="advanced-definition"><summary>Advanced Recipe JSON</summary><label>Ordered step JSON<textarea className="pipeline-editor" aria-label="Ordered processing steps" value={stepsText} onChange={(event) => { setStepsText(event.target.value); setPreview(null); }} spellCheck={false} /></label></details>
        <p className="mapping-note">Methods are deterministic. The common resampler declares <code>extrapolation: reject</code>; unsupported or hidden policies fail before calculation.</p>
      </section>

      {familyWorkbench ? <section className="family-modeling-workbench" aria-label="Selected material family modeling">{familyWorkbench}</section> : null}

      <section className="workbench-card processing-output-card" id="modeling-output">
        <div className="section-heading"><div><p className="eyebrow">5 · immutable output</p><h2>Commit reviewed result</h2></div><span className="status-chip">{outputs.length} committed</span></div>
        <p className="mapping-note">Commit recomputes the selected exact Test Data and saved Mapping Profile on the server. Preview arrays are never accepted as authoritative output.</p>
        <div className="processing-output-form"><label>Output label<input value={outputLabel} onChange={(event) => setOutputLabel(event.target.value)} /></label><label>Change reason<input value={outputReason} onChange={(event) => setOutputReason(event.target.value)} /></label><button className="button primary" type="button" disabled={busy || !preview || !selectedProfileId || !outputLabel.trim() || !outputReason.trim()} onClick={() => void commitOutput()}>Commit immutable output</button></div>
        {outputs.length ? <div className="processing-output-list">{outputs.map((output) => <article key={output.processing_output_id}><div><strong>{output.label}</strong><small>r{output.current_revision.revision_no} · {output.final_point_count} points · {output.stage_count} stages</small><code>{output.output_sha256}</code></div><button className="button secondary" type="button" disabled={busy} onClick={() => void downloadOutput(output)}>Download JSON</button><DomainWorkflowLinks compact config={config} target={{ kind: "processing_output", objectId: output.processing_output_id, revisionId: output.current_revision.id, label: `${output.label} r${output.current_revision.revision_no}` }} /></article>)}</div> : <p className="muted">No committed common Processing Output is visible yet.</p>}
      </section>

      <section className="workbench-card ensemble-card">
        <div className="section-heading"><div><p className="eyebrow">6 · replicate evidence</p><h2>Alignment and pointwise statistics</h2></div><span className="status-chip warning">Preview · members retained</span></div>
        <p className="mapping-note">Select multiple exact Test Data heads. Alignment uses only their observed domain intersection and rejects extrapolation; no raw curve or outlier is deleted.</p>
        <div className="ensemble-methods">{ensembleMethods.map((method) => <article key={method.method_id}><strong>{method.label}</strong><code>{method.method_id} · {method.version}</code><small>{method.description}</small></article>)}</div>
        <div className="ensemble-controls"><fieldset><legend>Exact Test Data members</legend>{trackDocuments.map((item) => <label key={item.test_data_document_id}><input type="checkbox" checked={ensembleDocumentIds.includes(item.test_data_document_id)} onChange={() => toggleEnsembleDocument(item.test_data_document_id)} />{item.document_key} · r{item.current_revision.revision_no}</label>)}</fieldset><label>Common grid points<input type="number" min="2" max="100000" value={ensemblePointCount} onChange={(event) => { setEnsemblePointCount(Number(event.target.value)); setEnsemblePreview(null); }} /></label><button className="button primary" type="button" disabled={busy || ensembleDocumentIds.length < 2} onClick={() => void runEnsemblePreview()}>Align and calculate</button></div>
        {ensemblePreview && ensembleStatistic && ensembleBounds ? <div className="ensemble-results"><svg className="processing-curve ensemble-curve" role="img" aria-label="Aligned replicate curves with pointwise mean and confidence interval" viewBox={`0 0 ${chart.width} ${chart.height}`}><line x1="28" y1={chart.height - 24} x2={chart.width - 20} y2={chart.height - 24} className="chart-axis"/><line x1="28" y1="20" x2="28" y2={chart.height - 24} className="chart-axis"/>{ensemblePreview.members.map((member) => { const values = member.stage.series.find((series) => series.quantity === ensembleStatistic.quantity)?.values ?? []; return <polyline key={member.ordinal} points={xyPoints(ensemblePreview.grid, values, chart.width, chart.height, ensembleBounds)} className="curve-line ensemble-member"/>; })}<polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.confidence_95_lower, chart.width, chart.height, ensembleBounds)} className="curve-line confidence"/><polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.confidence_95_upper, chart.width, chart.height, ensembleBounds)} className="curve-line confidence"/><polyline points={xyPoints(ensemblePreview.grid, ensembleStatistic.mean, chart.width, chart.height, ensembleBounds)} className="curve-line ensemble-mean"/></svg><div className="curve-legend"><span><i className="ensemble-member"/>Members ({ensemblePreview.members.length})</span><span><i className="ensemble-mean"/>Mean</span><span><i className="confidence"/>95% mean CI</span></div><div className="statistics-grid"><article><span>Quantity</span><strong>{ensembleStatistic.quantity}</strong><small>{ensembleStatistic.unit}</small></article><article><span>Last mean</span><strong>{ensembleStatistic.mean.at(-1)?.toPrecision(6)}</strong></article><article><span>Sample SD</span><strong>{ensembleStatistic.standard_deviation.at(-1)?.toPrecision(6)}</strong></article><article><span>MAD</span><strong>{ensembleStatistic.mad.at(-1)?.toPrecision(6)}</strong></article><article><span>IQR</span><strong>{ensembleStatistic.q1.at(-1)?.toPrecision(4)} – {ensembleStatistic.q3.at(-1)?.toPrecision(4)}</strong></article></div><div className="stage-diagnostics">{ensemblePreview.diagnostics.map((item) => <p key={item}>{item}</p>)}</div></div> : <p className="muted">At least two imported Test Data identities are required. Import each replicate separately so its exact revision remains addressable.</p>}
      </section>
    </main>
  );
}
