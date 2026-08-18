import { useEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from "react";

import {
  ApiError,
  convertTabularToCanonicalTestData,
  createGovernedImportProfile,
  executeGovernedTabularImport,
  downloadCanonicalTestDataDocument,
  importCanonicalTestData,
  listGovernedImportProfiles,
  listTestRunsForMaterialState,
  previewGovernedTabularImport,
  reviseCanonicalTestData,
  reviseGovernedImportProfile,
  uploadGovernedTabularFile,
  validateCanonicalTestData,
  type ApiConfig,
} from "../../../../../api";
import type { ObservedCurveInput } from "../../../../../engineering-curve-plot";
import type {
  CanonicalTestDataChannelPreview,
  CanonicalTestDataDocumentResponse,
  CanonicalTestDataPreviewResponse,
  DataClassification,
  GovernedChannelMapping,
  GovernedImportPreview,
  GovernedImportProfileContent,
  GovernedImportProfileResponse,
  GovernedImportRunResponse,
  GovernedQuantityKind,
  GovernedTabularDataSchema,
  GovernedTabularFileFormat,
  MaterialResponse,
  MaterialStateResponse,
  TestRunResponse,
} from "../../../../../types";
import { previewCommonProcessing } from "../../../api/modeling-api";
import type {
  CommonMappingProfileContent,
  CommonProcessingPreview,
} from "../../../model/common-processing-contracts";
import type { CommonExportProvenance } from "../../../model/exact-revision-contracts";
import type { ModelingSessionRecordRef } from "../../../model/session-controller";
import { MaterialsScrollRegion } from "../../../../../materials-scroll-rail";
import { SemanticStatus, SemanticText, WorkbenchMessage } from "../../../../../design/semantic-ui";
import { modelingDataRecordLabel, modelingTestRunDisplayLabel } from "./modeling-data-library-model";
import "./modeling-data-stage.css";

export type ModelingDataIntakeSource = "library" | "import";
type ImportKind = "tabular" | "json";
export type ModelingDataLayoutMode = "compact" | "content-fit";

export interface ModelingDataIntakeProps {
  config: ApiConfig;
  material?: MaterialResponse;
  state?: MaterialStateResponse;
  documents: CanonicalTestDataDocumentResponse[];
  emptySession?: boolean;
  selectedTestDataRefs?: ModelingSessionRecordRef[];
  selectedDocumentId: string;
  visibleDocumentKeys?: string[];
  processingMappingProfileText: string;
  source?: ModelingDataIntakeSource;
  showSourceTabs?: boolean;
  testRuns?: TestRunResponse[];
  libraryContent?: ReactNode;
  onSourceChange?: (source: ModelingDataIntakeSource) => void;
  onSelectDocument: (id: string, revisionId?: string) => void;
  onPreviewDocument: (
    document: Record<string, unknown>,
    preview: CommonProcessingPreview,
  ) => void;
  onImported: (document: CanonicalTestDataDocumentResponse) => void;
  onObservedCurves?: (curves: ObservedCurveInput[]) => void;
  onLayoutModeChange?: (mode: ModelingDataLayoutMode) => void;
}

const SCHEMAS: Array<{ value: GovernedTabularDataSchema; label: string }> = [
  { value: "monotonic_tension", label: "Monotonic tension" },
  { value: "monotonic_compression", label: "Monotonic compression" },
  { value: "planar_tension", label: "Planar tension" },
  { value: "biaxial_tension", label: "Biaxial tension" },
  { value: "simple_shear", label: "Simple shear" },
  { value: "shear_relaxation", label: "Shear relaxation" },
  { value: "dma_frequency_temperature_sweep", label: "DMA frequency-temperature sweep" },
  { value: "forming_limit_diagram", label: "Forming limit diagram (FLD)" },
];

const UNIT_OPTIONS: Record<GovernedQuantityKind, string[]> = {
  engineering_strain: ["1", "%"],
  // Keep a raw unsupported choice visible so the engineer can see and correct
  // the source declaration instead of silently coercing it.
  engineering_stress: ["Pa", "kPa", "MPa", "GPa", "%"],
  shear_strain: ["1", "%"],
  shear_stress: ["Pa", "kPa", "MPa", "GPa", "%"],
  time: ["s", "ms", "min", "h"],
  shear_modulus: ["Pa", "kPa", "MPa", "GPa", "%"],
  displacement: ["m", "mm", "um"],
  force: ["N", "kN", "%"],
  temperature: ["degC", "K"],
  frequency: ["Hz"],
  storage_modulus: ["Pa", "kPa", "MPa", "GPa", "%"],
  loss_modulus: ["Pa", "kPa", "MPa", "GPa", "%"],
  tan_delta: ["1"],
  minor_strain: ["1", "%"],
  major_strain: ["1", "%"],
};

function supportedUnits(quantity: GovernedQuantityKind): string[] {
  return UNIT_OPTIONS[quantity].filter((unit) => unit !== "%"
    || quantity.includes("strain"));
}

function unitChoices(units: readonly string[]): string {
  if (units.length < 2) return units.join("");
  if (units.length === 2) return `${units[0]} or ${units[1]}`;
  return `${units.slice(0, -1).join(", ")}, or ${units.at(-1)}`;
}

export function mappingBlockers({
  independentColumn,
  dependentColumn,
  independentUnit,
  dependentUnit,
  quantities: channelQuantities,
}: {
  independentColumn: string;
  dependentColumn: string;
  independentUnit: string;
  dependentUnit: string;
  quantities: readonly [GovernedQuantityKind, GovernedQuantityKind];
}): string[] {
  const issues: string[] = [];
  if (!independentColumn) issues.push(`Choose the required ${quantityLabel(channelQuantities[0])} channel.`);
  if (!dependentColumn) issues.push(`Choose the required ${quantityLabel(channelQuantities[1])} channel.`);
  if (independentColumn && dependentColumn && independentColumn === dependentColumn) {
    issues.push("Use different source columns for Independent and Dependent.");
  }
  if (independentUnit && !supportedUnits(channelQuantities[0]).includes(independentUnit)) {
    issues.push(`${quantityLabel(channelQuantities[0])} cannot use “${independentUnit}”. Choose ${unitChoices(supportedUnits(channelQuantities[0]))}.`);
  }
  if (dependentUnit && !supportedUnits(channelQuantities[1]).includes(dependentUnit)) {
    issues.push(`${quantityLabel(channelQuantities[1])} cannot use “${dependentUnit}”. Choose ${unitChoices(supportedUnits(channelQuantities[1]))}.`);
  }
  return issues;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "The data source could not be prepared.";
}

function fileFormat(file: File): GovernedTabularFileFormat | null {
  const extension = file.name.toLowerCase().split(".").at(-1);
  return extension === "csv" || extension === "tsv" || extension === "xlsx" ? extension : null;
}

async function fileBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function quantities(
  schema: GovernedTabularDataSchema,
  includeTanDelta = false,
): GovernedQuantityKind[] {
  if (schema === "dma_frequency_temperature_sweep") {
    return [
      "temperature",
      "frequency",
      "storage_modulus",
      "loss_modulus",
      ...(includeTanDelta ? ["tan_delta" as const] : []),
    ];
  }
  if (schema === "forming_limit_diagram") return ["minor_strain", "major_strain"];
  if (schema === "simple_shear") return ["shear_strain", "shear_stress"];
  if (schema === "shear_relaxation") return ["time", "shear_modulus"];
  return ["engineering_strain", "engineering_stress"];
}

function axisRole(
  schema: GovernedTabularDataSchema,
  ordinal: number,
): GovernedChannelMapping["axis_role"] {
  return schema === "dma_frequency_temperature_sweep" && ordinal < 2
    ? "independent"
    : ordinal === 0
      ? "independent"
      : "dependent";
}

function defaultUnit(quantity: GovernedQuantityKind): string {
  if (quantity.includes("strain")) return "%";
  if (quantity === "time") return "s";
  if (quantity === "temperature") return "degC";
  if (quantity === "frequency") return "Hz";
  if (quantity === "tan_delta") return "1";
  return "MPa";
}

function quantityLabel(quantity: GovernedQuantityKind): string {
  const label = quantity.replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function sourceColumnLabel(name: string, ordinal: number): string {
  const compact = name.trim().replace(/\s+/g, " ");
  const shortened = compact.length > 30 ? `${compact.slice(0, 29).trimEnd()}…` : compact;
  return `${ordinal + 1}${shortened ? ` · ${shortened}` : ""}`;
}

function normalizedUnit(quantity: GovernedQuantityKind): string {
  if (quantity.includes("strain")) return "1";
  if (quantity === "time") return "s";
  if (quantity === "temperature") return "K";
  if (quantity === "frequency") return "Hz";
  if (quantity === "tan_delta") return "1";
  if (quantity === "displacement") return "m";
  if (quantity === "force") return "N";
  return "Pa";
}

function normalizedQuantity(quantity: GovernedQuantityKind): GovernedQuantityKind {
  if (quantity === "displacement") return "engineering_strain";
  if (quantity === "force") return "engineering_stress";
  return quantity;
}

export function channelMappingBlockers({
  columns,
  units,
  quantities: channelQuantities,
}: {
  columns: readonly string[];
  units: readonly string[];
  quantities: readonly GovernedQuantityKind[];
}): string[] {
  const issues = channelQuantities.flatMap((quantity, ordinal) => {
    const column = columns[ordinal] ?? "";
    const unit = units[ordinal] ?? "";
    const result: string[] = [];
    if (!column) result.push(`Choose the required ${quantityLabel(quantity)} channel.`);
    if (unit && !supportedUnits(quantity).includes(unit)) {
      result.push(`${quantityLabel(quantity)} cannot use “${unit}”. Choose ${unitChoices(supportedUnits(quantity))}.`);
    }
    return result;
  });
  const chosen = columns.slice(0, channelQuantities.length).filter(Boolean);
  if (new Set(chosen).size !== chosen.length) {
    issues.push("Use a different source column for each required channel.");
  }
  return issues;
}

function intakePreviewProfile(profile: GovernedImportProfileContent): CommonMappingProfileContent {
  const previewChannels = profile.data_schema === "dma_frequency_temperature_sweep"
    ? profile.channels.filter((channel) => channel.source_quantity !== "frequency")
    : profile.channels;
  const bindings = previewChannels.map((channel) => {
    const quantity = normalizedQuantity(channel.source_quantity);
    return {
      channel_key: quantity,
      target_quantity: quantity,
      accepted_normalized_units: [normalizedUnit(quantity)],
      required: true,
      scale: 1,
      offset: 0,
    };
  });
  const independent = profile.channels.find((channel) => channel.axis_role === "independent");
  return {
    profile_key: `governed-intake-${profile.data_schema}`,
    label: `${profile.profile_label} preview`,
    independent_quantity: normalizedQuantity(independent?.source_quantity ?? profile.channels[0].source_quantity),
    missing_data_policy: "reject",
    bindings,
    attribute_bindings: [],
  };
}

function matchingPreviewProfile(
  channels: readonly CanonicalTestDataChannelPreview[] | undefined,
  preferred: CommonMappingProfileContent,
): CommonMappingProfileContent {
  if (!channels?.length) return preferred;
  const keys = new Set(channels.map((channel) => channel.key));
  if (preferred.bindings.every((binding) => keys.has(binding.channel_key))) return preferred;
  const governedDma = ["temperature", "frequency", "storage_modulus", "loss_modulus"]
    .every((key) => keys.has(key));
  const previewChannels = governedDma
    ? channels.filter((channel) => channel.key !== "frequency")
    : channels;
  const independent = previewChannels.find((channel) => channel.axis_role === "independent")
    ?? previewChannels[0];
  return {
    profile_key: "canonical-test-data-intake-preview",
    label: "Canonical Test Data intake preview",
    independent_quantity: independent.key,
    missing_data_policy: "reject",
    bindings: previewChannels.map((channel) => ({
      channel_key: channel.key,
      target_quantity: channel.key,
      accepted_normalized_units: [channel.normalized_unit],
      required: true,
      scale: 1,
      offset: 0,
    })),
    attribute_bindings: [],
  };
}

export function mappingUnitConsequence(
  independentQuantity: GovernedQuantityKind,
  dependentQuantity: GovernedQuantityKind,
): string {
  return `Stored units stay unchanged; preview uses ${normalizedUnit(independentQuantity)} and ${normalizedUnit(dependentQuantity)}.`;
}

export function unmatchedMappingNotice(matchCount: number): string {
  return matchCount > 1
    ? "More than one approved mapping matches. Choose the intended profile."
    : "";
}

const NOOP_OBSERVED_CURVES = (_curves: ObservedCurveInput[]): void => undefined;

function curveLabel(item: CanonicalTestDataDocumentResponse): string {
  const value = item.specimen_id.trim();
  const specimen = value.match(/^(?:specimen|sample|s)[-_ ]*(\d+)$/i);
  if (specimen) return `Specimen ${specimen[1].padStart(2, "0")}`;
  if (/^(?:specimen|sample)\b/i.test(value)) return value;
  if (!value || /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value) || /^\d{8,}$/.test(value)) return "Unnamed specimen";
  return value;
}

function testMethodLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized.includes("planar")) return "Planar tension";
  if (normalized.includes("biaxial")) return "Biaxial tension";
  if (normalized.includes("uniaxial")) return "Uniaxial tension";
  if (normalized.includes("tensile")) return "Tensile test";
  if (normalized.includes("relaxation")) return "Relaxation test";
  if (normalized.includes("dma")) return "DMA test";
  const label = value.trim().replaceAll("_", " ");
  return label ? `${label[0].toUpperCase()}${label.slice(1)}` : "Test Data";
}

function editableProfile(value: GovernedImportProfileContent): GovernedImportProfileContent {
  return {
    profile_label: value.profile_label,
    data_schema: value.data_schema,
    file_format: value.file_format,
    sheet_name: value.sheet_name,
    header_row: value.header_row,
    encoding: value.encoding,
    delimiter: value.delimiter,
    decimal_separator: value.decimal_separator,
    channels: value.channels.map((channel) => ({
      ordinal: channel.ordinal,
      source_column: channel.source_column,
      source_quantity: channel.source_quantity,
      original_unit: channel.original_unit,
      axis_role: channel.axis_role,
    })),
    initial_gauge_length_m: value.initial_gauge_length_m,
    initial_cross_section_area_m2: value.initial_cross_section_area_m2,
    approval_kind: "human_confirmed",
  };
}

export function profileMatchesPreview(
  profile: GovernedImportProfileResponse,
  preview: GovernedImportPreview,
): boolean {
  const content = profile.content;
  return content.file_format === preview.file_format
    && content.sheet_name === preview.selected_sheet_name
    && content.header_row === preview.header_row
    && content.encoding === preview.encoding
    && content.delimiter === preview.delimiter
    && content.decimal_separator === preview.decimal_separator
    && content.channels.every((channel) => preview.header_columns.includes(channel.source_column));
}

export function governedSourceFor(
  material: MaterialResponse,
  state: MaterialStateResponse,
  run: TestRunResponse,
  tabularRun?: GovernedImportRunResponse,
): CommonExportProvenance {
  return {
    material: {
      aggregate_id: material.material_id,
      revision_id: material.current_revision.id,
    },
    material_state: {
      aggregate_id: state.material_state_id,
      revision_id: state.current_revision.id,
    },
    test_run: {
      aggregate_id: run.test_run_id,
      revision_id: run.current_revision.id,
    },
    ...(tabularRun?.normalized_dataset_id && tabularRun.normalized_dataset_revision_id
      ? {
          tabular_import: {
            raw_asset_id: tabularRun.raw_asset_id,
            raw_artifact_id: tabularRun.raw_artifact_id,
            import_run_id: tabularRun.import_run_id,
            import_profile: {
              aggregate_id: tabularRun.import_profile_id,
              revision_id: tabularRun.import_profile_revision_id,
            },
            normalized_dataset: {
              aggregate_id: tabularRun.normalized_dataset_id,
              revision_id: tabularRun.normalized_dataset_revision_id,
            },
          },
        }
      : {}),
  };
}

export function ModelingDataIntake({
  config,
  material,
  state,
  documents,
  emptySession = false,
  selectedTestDataRefs = [],
  selectedDocumentId,
  visibleDocumentKeys = [],
  processingMappingProfileText,
  source: controlledSource,
  showSourceTabs = true,
  testRuns: controlledTestRuns,
  libraryContent,
  onSourceChange,
  onSelectDocument,
  onPreviewDocument,
  onImported,
  onObservedCurves = NOOP_OBSERVED_CURVES,
  onLayoutModeChange,
}: ModelingDataIntakeProps) {
  const [internalSource, setInternalSource] = useState<ModelingDataIntakeSource>("library");
  const source = controlledSource ?? internalSource;
  const [importKind, setImportKind] = useState<ImportKind | null>(null);
  const [loadedTestRuns, setLoadedTestRuns] = useState<TestRunResponse[]>([]);
  const testRuns = controlledTestRuns ?? loadedTestRuns;
  const [profiles, setProfiles] = useState<GovernedImportProfileResponse[]>([]);
  const [testRunId, setTestRunId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<GovernedTabularFileFormat>("csv");
  const [sheetName, setSheetName] = useState<string | null>(null);
  const [delimiter, setDelimiter] = useState(",");
  const [decimalSeparator, setDecimalSeparator] = useState<"." | ",">(".");
  const [rawAssetId, setRawAssetId] = useState("");
  const [rawArtifactId, setRawArtifactId] = useState("");
  const [tabularPreview, setTabularPreview] = useState<GovernedImportPreview | null>(null);
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [mappingEditing, setMappingEditing] = useState(false);
  const [schema, setSchema] = useState<GovernedTabularDataSchema>("monotonic_tension");
  const [includeTanDelta, setIncludeTanDelta] = useState(false);
  const [channelColumns, setChannelColumns] = useState<string[]>(["", ""]);
  const [channelUnits, setChannelUnits] = useState<string[]>(["%", "MPa"]);
  const [mappingReason, setMappingReason] = useState("");
  const [documentKey, setDocumentKey] = useState("");
  const [maker, setMaker] = useState("");
  const [operator, setOperator] = useState("");
  const [laboratory, setLaboratory] = useState("");
  const [canonicalPreview, setCanonicalPreview] = useState<CanonicalTestDataPreviewResponse | null>(null);
  const [jsonFile, setJsonFile] = useState<File | null>(null);
  const [jsonPreview, setJsonPreview] = useState<CanonicalTestDataPreviewResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [importDiagnostics, setImportDiagnostics] = useState<GovernedImportRunResponse["diagnostics"]>([]);
  const [previewValidationRejected, setPreviewValidationRejected] = useState(false);
  const importRetry = useRef<{ identity: string; key: string } | null>(null);
  const observedPreviewCache = useRef(new Map<string, CommonProcessingPreview>());
  const observedConfigKey = `${config.baseUrl}\u0000${config.accessToken ?? ""}`;
  const observedDocumentKey = documents
    .map((item) => `${item.test_data_document_id}:${item.current_revision.id}:${item.specimen_id}`)
    .join("|");
  const observedRefKey = selectedTestDataRefs
    .map((ref) => `${ref.id}:${ref.revisionId}:${ref.revisionNo}:${ref.label}`)
    .join("|");
  const observedTestRunKey = testRuns
    .map((run) => `${run.test_run_id}:${run.current_revision.id}:${run.current_revision.content.run_label}`)
    .join("|");
  const observedVisibilityKey = visibleDocumentKeys.join("|");
  const observedRequestKey = [
    observedConfigKey,
    observedDocumentKey,
    observedRefKey,
    observedTestRunKey,
    observedVisibilityKey,
    processingMappingProfileText,
  ].join("\u0001");
  // Advance only from a committed effect. Mutating a "latest key" ref during
  // render lets an interrupted concurrent render invalidate the request owned
  // by the last committed surface without ever starting a replacement.
  const observedHydrationGeneration = useRef(0);

  function selectSource(next: ModelingDataIntakeSource): void {
    if (controlledSource === undefined) setInternalSource(next);
    onSourceChange?.(next);
  }

  useEffect(() => {
    const selectImportSource = (event: Event) => {
      const requested = (event as CustomEvent<{ source?: string }>).detail?.source;
      if (requested !== "local" && requested !== "import") return;
      selectSource("import");
      window.setTimeout(() => document.querySelector<HTMLInputElement>("input[name='import-test-data-file']")?.focus(), 0);
    };
    window.addEventListener("cmp:modeling-data-source", selectImportSource);
    return () => window.removeEventListener("cmp:modeling-data-source", selectImportSource);
  }, [controlledSource, onSourceChange]);

  useEffect(() => {
    // A new standalone intake defaults to Local file once. When a parent
    // controls the source, it owns that initial choice and the engineer must
    // remain free to switch back to Library.
    if (emptySession && controlledSource === undefined) setInternalSource("import");
  }, [controlledSource, emptySession]);

  const selectedRun = testRuns.find((item) => item.test_run_id === testRunId) ?? null;
  const selectedProfile = profiles.find((item) => item.import_profile_id === selectedProfileId) ?? null;
  const channelQuantities = useMemo(
    () => quantities(schema, includeTanDelta),
    [includeTanDelta, schema],
  );
  const matchingProfiles = useMemo(
    () => tabularPreview
      ? profiles.filter((profile) =>
          profile.current_revision.classification === selectedRun?.current_revision.classification
          && profileMatchesPreview(profile, tabularPreview))
      : [],
    [profiles, selectedRun, tabularPreview],
  );
  const mappingIssues = useMemo(() => {
    if (!tabularPreview) return [];
    return channelMappingBlockers({
      columns: channelColumns,
      units: channelUnits,
      quantities: channelQuantities,
    });
  }, [channelColumns, channelQuantities, channelUnits, tabularPreview]);
  const mappingResolved = !mappingEditing && mappingIssues.length === 0 && Boolean(
    selectedProfile && tabularPreview && profileMatchesPreview(selectedProfile, tabularPreview),
  );

  useEffect(() => {
    onLayoutModeChange?.(source === "import" && importKind === "tabular" && Boolean(tabularPreview?.header_columns.length)
      ? "content-fit"
      : "compact");
  }, [importKind, onLayoutModeChange, source, tabularPreview]);

  useEffect(() => {
    if (tabularPreview) setCanonicalPreview(null);
  }, [channelColumns, channelUnits, includeTanDelta, schema, tabularPreview]);

  useEffect(() => {
    if (!state || !config.accessToken) return;
    let active = true;
    void Promise.all([
      controlledTestRuns === undefined
        ? listTestRunsForMaterialState(config, state.material_state_id)
        : Promise.resolve(null),
      listGovernedImportProfiles(config),
    ]).then(([runsResult, profilesResult]) => {
      if (!active) return;
      if (runsResult) setLoadedTestRuns(runsResult.data.items);
      setProfiles(profilesResult.data);
      const availableRuns = runsResult?.data.items ?? controlledTestRuns ?? [];
      setTestRunId((current) => availableRuns.some((run) => run.test_run_id === current)
        ? current
        : "");
    }).catch((caught: unknown) => {
      if (active) setError(errorMessage(caught));
    });
    return () => { active = false; };
  }, [config, controlledTestRuns, state]);

  useEffect(() => {
    const generation = observedHydrationGeneration.current + 1;
    observedHydrationGeneration.current = generation;
    const controller = new AbortController();
    const visibleRefs = selectedTestDataRefs.filter((ref) => visibleDocumentKeys.includes(`${ref.id}:${ref.revisionId}`));
    if (!visibleRefs.length) {
      onObservedCurves([]);
      return () => {
        controller.abort();
        if (observedHydrationGeneration.current === generation) observedHydrationGeneration.current += 1;
      };
    }
    let profile: CommonMappingProfileContent;
    try {
      profile = JSON.parse(processingMappingProfileText) as CommonMappingProfileContent;
    } catch {
      onObservedCurves([]);
      return () => {
        controller.abort();
        if (observedHydrationGeneration.current === generation) observedHydrationGeneration.current += 1;
      };
    }
    void Promise.allSettled(visibleRefs.map(async (ref) => {
      const item = documents.find((candidate) => candidate.test_data_document_id === ref.id);
      const previewProfile = matchingPreviewProfile(item?.channels, profile);
      const previewProfileText = JSON.stringify(previewProfile);
      const key = `${ref.id}:${ref.revisionId}:${previewProfileText}`;
      const cached = observedPreviewCache.current.get(key);
      if (cached) return { ref, item, preview: cached };
      const downloaded = await downloadCanonicalTestDataDocument(config, ref.id, ref.revisionId);
      if (controller.signal.aborted) return null;
      const sourceDocument = JSON.parse(await downloaded.data.blob.text()) as Record<string, unknown>;
      const result = await previewCommonProcessing(config, {
        document: sourceDocument,
        mapping_profile: previewProfile,
        steps: [],
      }, controller.signal);
      observedPreviewCache.current.set(key, result.data);
      return { ref, item, preview: result.data };
    })).then((results) => {
      if (controller.signal.aborted || observedHydrationGeneration.current !== generation) return;
      const curves = results.flatMap((result, index) => {
        if (result.status !== "fulfilled" || !result.value) return [];
        const { ref, item, preview } = result.value;
        const runPin = item?.governed_source?.test_run;
        const exactRun = runPin
          ? testRuns.find((run) => run.test_run_id === runPin.aggregate_id
            && run.current_revision.id === runPin.revision_id)
          : undefined;
        return [{
          id: `${ref.id}:${ref.revisionId}`,
          label: item ? modelingDataRecordLabel(item, exactRun) : ref.label,
          preview,
          color: ["#e56734", "#2f7f78", "#7c3aed", "#2563eb", "#dc2626"][index % 5],
        }];
      });
      onObservedCurves(curves);
      if (curves.length !== visibleRefs.length) {
          setNotice("Some selected curves could not be loaded. Other selected curves remain on the graph.");
      }
    }).catch((caught: unknown) => {
      if (caught instanceof Error && caught.name === "AbortError") return;
      if (!controller.signal.aborted && observedHydrationGeneration.current === generation) {
        setNotice("Some selected curves could not be loaded. Other selected curves remain on the graph.");
      }
    });
    return () => {
      controller.abort();
      if (observedHydrationGeneration.current === generation) observedHydrationGeneration.current += 1;
    };
  }, [observedRequestKey, onObservedCurves]);

  useEffect(() => {
    if (!selectedRun) return;
    const base = material?.current_revision.content.material_code
      ?? material?.current_revision.content.name
      ?? "TEST-DATA";
    setDocumentKey(`${base}-${selectedRun.current_revision.content.run_label}`.replace(/\s+/g, "-"));
    setMaker((current) => current || material?.current_revision.content.name || "");
  }, [material, selectedRun]);

  useEffect(() => {
    setCanonicalPreview(null);
    setPreviewValidationRejected(false);
    setImportDiagnostics([]);
    importRetry.current = null;
  }, [material?.current_revision?.id, selectedRun?.current_revision?.id, state?.current_revision?.id]);

  function invalidateLocalPreview(): void {
    setCanonicalPreview(null);
    setPreviewValidationRejected(false);
    setImportDiagnostics([]);
    importRetry.current = null;
  }

  async function inspectUploaded(
    nextSheetName: string | null,
    assetId = rawAssetId,
    artifactId = rawArtifactId,
  ): Promise<void> {
    if (!assetId || !artifactId) return;
    const inspected = await previewGovernedTabularImport(config, {
      raw_asset_id: assetId,
      raw_artifact_id: artifactId,
      file_format: format,
      sheet_name: format === "xlsx" ? nextSheetName : null,
      header_row: 1,
      encoding: format === "xlsx" ? "binary" : "utf-8",
      delimiter: format === "xlsx" ? null : format === "tsv" ? "\t" : delimiter,
      decimal_separator: decimalSeparator,
    });
    setTabularPreview(inspected.data);
    setSheetName(inspected.data.selected_sheet_name);
    setChannelColumns(channelQuantities.map((_, ordinal) => inspected.data.header_columns[ordinal] ?? ""));
    setChannelUnits(channelQuantities.map(defaultUnit));
    invalidateLocalPreview();
    const matches = profiles.filter((profile) =>
      profile.current_revision.classification === selectedRun?.current_revision.classification
      && profileMatchesPreview(profile, inspected.data));
    if (matches.length === 1) {
      const matched = matches[0];
      setSelectedProfileId(matched.import_profile_id);
      setMappingEditing(false);
      setSchema(matched.content.data_schema);
      setIncludeTanDelta(matched.content.channels.some((channel) => channel.source_quantity === "tan_delta"));
      setChannelColumns(matched.content.channels.map((channel) => channel.source_column));
      setChannelUnits(matched.content.channels.map((channel) => channel.original_unit));
      setNotice("File columns matched.");
    } else {
      setSelectedProfileId("");
      setMappingEditing(true);
      setNotice(unmatchedMappingNotice(matches.length));
    }
  }

  function chooseTabularFile(selected: File): void {
    const detected = fileFormat(selected);
    if (!detected) {
      setError("Choose a CSV, TSV, XLSX, or JSON file.");
      return;
    }
    setImportKind("tabular");
    setFile(selected);
    setJsonFile(null);
    setJsonPreview(null);
    setFormat(detected);
    setSheetName(null);
    setTabularPreview(null);
    invalidateLocalPreview();
    setSelectedProfileId("");
    setMappingEditing(false);
    setError("");
  }

  async function uploadAndInspect(): Promise<void> {
    if (!file || !selectedRun) {
      setError("Choose an exact Test Run and local file first.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const uploaded = await uploadGovernedTabularFile(config, {
        file,
        file_format: format,
        classification: selectedRun.current_revision.classification as DataClassification,
        test_run_revision_id: selectedRun.current_revision.id,
      });
      const asset = uploaded.data.raw_asset;
      const artifactId = uploaded.data.available_artifact_id;
      if (!artifactId) throw new ApiError(409, "The verified upload has no available Raw Artifact.");
      setRawAssetId(asset.raw_asset_id);
      setRawArtifactId(artifactId);
      await inspectUploaded(null, asset.raw_asset_id, artifactId);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function changeSchema(next: GovernedTabularDataSchema): void {
    const nextQuantities = quantities(next);
    setSchema(next);
    setIncludeTanDelta(false);
    setChannelColumns((current) => nextQuantities.map(
      (_, ordinal) => current[ordinal] ?? tabularPreview?.header_columns[ordinal] ?? "",
    ));
    setChannelUnits(nextQuantities.map(defaultUnit));
    invalidateLocalPreview();
  }

  function changeTanDelta(included: boolean): void {
    const nextQuantities = quantities(schema, included);
    setIncludeTanDelta(included);
    setChannelColumns((current) => nextQuantities.map(
      (_, ordinal) => current[ordinal] ?? tabularPreview?.header_columns[ordinal] ?? "",
    ));
    setChannelUnits((current) => nextQuantities.map(
      (quantity, ordinal) => current[ordinal] ?? defaultUnit(quantity),
    ));
    invalidateLocalPreview();
  }

  function changeChannelColumn(ordinal: number, value: string): void {
    setChannelColumns((current) => current.map((column, index) => index === ordinal ? value : column));
    invalidateLocalPreview();
  }

  function changeChannelUnit(ordinal: number, value: string): void {
    setChannelUnits((current) => current.map((unit, index) => index === ordinal ? value : unit));
    invalidateLocalPreview();
  }

  function currentProfile(): GovernedImportProfileContent | null {
    if (!tabularPreview || channelQuantities.some((_, ordinal) => !channelColumns[ordinal])) return null;
    const channels: GovernedChannelMapping[] = channelQuantities.map((quantity, ordinal) => ({
      ordinal,
      source_column: channelColumns[ordinal],
      source_quantity: quantity,
      original_unit: channelUnits[ordinal],
      axis_role: axisRole(schema, ordinal),
    }));
    return {
      profile_label: selectedProfile?.content.profile_label ?? `${documentKey || "Test data"} mapping`,
      data_schema: schema,
      file_format: format,
      sheet_name: format === "xlsx" ? sheetName : null,
      header_row: tabularPreview.header_row,
      encoding: tabularPreview.encoding,
      delimiter: tabularPreview.delimiter,
      decimal_separator: tabularPreview.decimal_separator,
      channels,
      initial_gauge_length_m: null,
      initial_cross_section_area_m2: null,
      approval_kind: "human_confirmed",
    };
  }

  async function previewLocalOnGraph(): Promise<void> {
    const profile = currentProfile();
    if (!file || !selectedRun || !profile || !documentKey.trim() || !maker.trim() || !operator.trim() || !laboratory.trim()) {
      setError("Complete the Test Run, data name, maker, operator, laboratory, and every required channel row.");
      return;
    }
    setBusy(true);
    setError("");
    setCanonicalPreview(null);
    setPreviewValidationRejected(false);
    setImportDiagnostics([]);
    try {
      const result = await convertTabularToCanonicalTestData(config, {
        document_id: documentKey.trim(),
        material: {
          maker: maker.trim(),
          grade: material?.current_revision.content.name ?? "Reference material",
          lot_batch: state?.current_revision.content.lot_or_batch ?? null,
        },
        test: {
          date: selectedRun.current_revision.content.performed_at.slice(0, 10),
          operator: operator.trim(),
          laboratory: laboratory.trim(),
          method: selectedRun.current_revision.content.run_label,
          equipment_maker: null,
          equipment_model: null,
        },
        specimen: {
          specimen_id: selectedRun.current_revision.content.specimen_id,
          description: null,
        },
        conditions: [],
        source_file_name: file.name,
        source_base64: await fileBase64(file),
        profile,
      });
      setCanonicalPreview(result.data);
      await previewOnGraph(result.data.canonical_document, intakePreviewProfile(profile));
      setNotice("Graph preview is calculated from the local file. Nothing has been registered yet.");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 422) {
        setPreviewValidationRejected(true);
      }
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function confirmLocal(mode: "save" | "record-rejection" = "save"): Promise<void> {
    const profile = currentProfile();
    const preview = canonicalPreview;
    if (!material || !state || !selectedRun || !profile || !rawAssetId || !rawArtifactId) {
      setError("Choose an exact Material, Material State, and Test Run before saving local Test Data.");
      return;
    }
    if (mode === "save" && !preview) {
      setError("Update the graph preview before saving local Test Data.");
      return;
    }
    if (mode === "record-rejection" && (!previewValidationRejected || preview)) {
      setError("Re-run the rejected preview before recording its governed diagnostics.");
      return;
    }
    setBusy(true);
    setError("");
    setImportDiagnostics([]);
    try {
      let approved = selectedProfile;
      if (!approved) {
        const created = await createGovernedImportProfile(config, {
          classification: selectedRun.current_revision.classification as DataClassification,
          content: profile,
          change_reason: "Human-confirmed mapping from Modeling Data intake",
        });
        approved = created.data;
        setProfiles((current) => [...current.filter((item) => item.import_profile_id !== created.data.import_profile_id), created.data]);
        setSelectedProfileId(created.data.import_profile_id);
      } else if (JSON.stringify(editableProfile(approved.content)) !== JSON.stringify(profile)) {
        const revised = await reviseGovernedImportProfile(config, approved.import_profile_id, {
          expected_current_revision_id: approved.current_revision.id,
          content: profile,
          change_reason: "Human-confirmed mapping adjustment from Modeling Data intake",
        });
        approved = revised.data;
        setProfiles((current) => current.map((item) => item.import_profile_id === revised.data.import_profile_id ? revised.data : item));
      }
      const retryIdentity = [
        selectedRun.current_revision.id,
        rawAssetId,
        rawArtifactId,
        approved.current_revision.id,
        documentKey.trim(),
      ].join(":");
      if (importRetry.current?.identity !== retryIdentity) {
        importRetry.current = { identity: retryIdentity, key: crypto.randomUUID() };
      }
      const run = await executeGovernedTabularImport(config, {
        test_run_id: selectedRun.test_run_id,
        test_run_revision_id: selectedRun.current_revision.id,
        raw_asset_id: rawAssetId,
        raw_artifact_id: rawArtifactId,
        import_profile_id: approved.import_profile_id,
        import_profile_revision_id: approved.current_revision.id,
        change_reason: "Save local source and normalized Test Data revisions",
      }, importRetry.current.key);
      setImportDiagnostics(run.data.diagnostics);
      if (run.data.status !== "succeeded") {
        throw new ApiError(422, run.data.failure_detail ?? "The governed import did not succeed.");
      }
      if (!preview) {
        setPreviewValidationRejected(false);
        throw new ApiError(409, "The governed import succeeded. Update the graph preview before saving Test Data.");
      }
      const governedSource = governedSourceFor(material, state, selectedRun, run.data);
      const existing = documents.find((item) => item.document_key === documentKey.trim());
      const imported = existing
        ? await reviseCanonicalTestData(
            config,
            existing.test_data_document_id,
            `"revision:${existing.current_revision.revision_no}:sha256:${existing.current_revision.content_hash}"`,
            {
              document: preview.canonical_document,
              change_reason: "Save local Test Data source",
              governed_source: governedSource,
            },
          )
        : await importCanonicalTestData(config, {
            classification: selectedRun.current_revision.classification as DataClassification,
            document: preview.canonical_document,
            change_reason: "Save local Test Data source",
            governed_source: governedSource,
          });
      onImported(imported.data);
      selectSource("library");
      setImportKind(null);
      setCanonicalPreview(null);
      setPreviewValidationRejected(false);
      setTabularPreview(null);
      setImportDiagnostics([]);
      importRetry.current = null;
      setNotice("Test Data saved and selected for preview.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function chooseJsonFile(selected: File): Promise<void> {
    setImportKind("json");
    setFile(null);
    setTabularPreview(null);
    invalidateLocalPreview();
    setJsonFile(selected);
    setJsonPreview(null);
    setBusy(true);
    setError("");
    try {
      const parsed = JSON.parse(await selected.text()) as Record<string, unknown>;
      const result = await validateCanonicalTestData(config, parsed);
      setJsonPreview(result.data);
      await previewOnGraph(result.data.canonical_document);
      setNotice("JSON passed validation and is shown on the graph. Nothing has been registered yet.");
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function chooseImportFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const selected = event.target.files?.[0] ?? null;
    if (!selected) return;
    selectSource("import");
    setNotice("");
    if (selected.name.toLowerCase().endsWith(".json")) {
      await chooseJsonFile(selected);
      return;
    }
    chooseTabularFile(selected);
  }

  async function previewOnGraph(
    document: Record<string, unknown>,
    mappingProfile?: CommonMappingProfileContent,
  ): Promise<void> {
    const graph = await previewCommonProcessing(config, {
      document,
      mapping_profile: mappingProfile
        ?? JSON.parse(processingMappingProfileText) as CommonMappingProfileContent,
      steps: [],
    });
    onPreviewDocument(document, graph.data);
  }

  async function confirmJson(): Promise<void> {
    if (!jsonPreview || !jsonFile) return;
    setBusy(true);
    setError("");
    try {
      const key = String(jsonPreview.canonical_document.document_id ?? "");
      const existing = documents.find((item) => item.document_key === key);
      const imported = existing
        ? await reviseCanonicalTestData(
            config,
            existing.test_data_document_id,
            `"revision:${existing.current_revision.revision_no}:sha256:${existing.current_revision.content_hash}"`,
            { document: jsonPreview.canonical_document, change_reason: "Save canonical Test Data JSON" },
          )
        : await importCanonicalTestData(config, {
            classification: (state?.current_revision.classification ?? "internal") as DataClassification,
            document: jsonPreview.canonical_document,
            change_reason: "Save canonical Test Data JSON",
          });
      onImported(imported.data);
      selectSource("library");
      setImportKind(null);
      setJsonPreview(null);
      setNotice("Test Data saved and selected for preview.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className={`modeling-data-intake${showSourceTabs ? "" : " source-tabs-external"}`} aria-label="Modeling data intake">
      {showSourceTabs ? (
        <div className="data-source-tabs" role="tablist" aria-label="Test data source">
          <button type="button" role="tab" aria-selected={source === "library"} onClick={() => selectSource("library")}>Library</button>
          <button type="button" role="tab" aria-selected={source === "import"} onClick={() => selectSource("import")}>Local file</button>
        </div>
      ) : null}

      {source === "library" ? (
        libraryContent ?? <div className="data-library-pane">
          <div className="data-library-columns" aria-hidden="true"><span>Select specimen</span><span>Test</span><span>Date</span><span>Data points</span></div>
          <MaterialsScrollRegion
            className="data-library-list"
            shellClassName="data-library-scroll-shell"
            id="modeling-data-library-list"
            role="list"
            aria-label="Test Data from Materials"
            tabIndex={0}
          >
            {documents.map((item) => {
              const selectedRef = selectedTestDataRefs.find((ref) => ref.id === item.test_data_document_id);
              const materialRevisionChanged = Boolean(item.governed_source
                && material
                && state
                && (item.governed_source.material.revision_id !== material.current_revision.id
                  || item.governed_source.material_state.revision_id !== state.current_revision.id));
              const active = selectedDocumentId === item.test_data_document_id
                && (!selectedRef || selectedRef.revisionId === item.current_revision.id);
              const label = curveLabel(item);
              const method = testMethodLabel(item.method);
              return <article className={active ? "active" : ""} role="listitem" key={`${item.test_data_document_id}:${item.current_revision.id}`}>
              <button type="button" className="data-library-row" data-document-key={item.document_key} data-revision-id={item.current_revision.id} aria-current={active ? "true" : undefined} aria-label={`${label}, ${method}, tested ${item.test_date}, ${item.point_count.toLocaleString()} data points`} title={`${item.document_key} · saved version r${item.current_revision.revision_no}`} onClick={() => onSelectDocument(item.test_data_document_id, item.current_revision.id)}>
                <strong>{label}</strong><span>{method}</span><time dateTime={item.test_date}>{item.test_date}</time><small>{item.point_count.toLocaleString()}</small>{materialRevisionChanged ? <small className="data-library-warning">This item was recorded for an earlier material state.</small> : null}
              </button>
            </article>;
            })}
            {selectedTestDataRefs.filter((ref) => {
              const current = documents.find((item) => item.test_data_document_id === ref.id);
              return current && current.current_revision.id !== ref.revisionId;
            }).map((ref) => {
              const current = documents.find((item) => item.test_data_document_id === ref.id);
              const active = selectedDocumentId === ref.id;
              return <article className={active ? "active historical" : "historical"} role="listitem" key={`${ref.id}:${ref.revisionId}`}>
                <button type="button" className="data-library-row" data-document-key={current?.document_key ?? ref.label} data-revision-id={ref.revisionId} aria-current={active ? "true" : undefined} aria-label={`${current ? curveLabel(current) : "Unnamed specimen"}, earlier saved version`} title={`${current?.document_key ?? ref.label} · saved version r${ref.revisionNo}`} onClick={() => onSelectDocument(ref.id, ref.revisionId)}>
                  <strong>{current ? curveLabel(current) : "Unnamed specimen"}</strong><span>Earlier saved version</span><time>—</time><small>—</small>
                </button>
              </article>;
            })}
            {!documents.length ? <p className="muted">No Test Data is connected to this material state.</p> : null}
          </MaterialsScrollRegion>
        </div>
      ) : null}

      {source === "import" ? (
        <div
          className={`data-intake-local${mappingIssues.length ? " has-mapping-blockers" : ""}`}
          role="region"
          aria-label="Local Test Data import"
          tabIndex={0}
        >
          <div className="data-intake-row data-import-file-row">
            <label className="data-import-file-control" title="Accepted files: CSV, TSV, XLSX, or JSON"><input name="import-test-data-file" aria-label="Import Test Data file" type="file" accept=".csv,.tsv,.xlsx,.json,application/json" onChange={(event) => void chooseImportFile(event)} /><span className="data-import-file-button" aria-hidden="true">Choose data file</span><span className="data-import-file-name" aria-hidden="true">{file?.name ?? "No file selected"}</span></label>
          </div>
          {importKind === "tabular" ? <>
          <div className="data-intake-row data-import-context-row">
            <label>Test record<select name="local-test-run" aria-label="Imported file Test record" value={testRunId} onChange={(event) => {
              setTestRunId(event.target.value);
              invalidateLocalPreview();
            }}><option value="">Choose a Test record</option>{testRuns.map((item) => <option key={item.test_run_id} value={item.test_run_id}>{modelingTestRunDisplayLabel(item)}</option>)}</select></label>
            {!tabularPreview ? <button className="button primary" type="button" disabled={busy || !file || !selectedRun} onClick={() => void uploadAndInspect()}>{busy ? "Inspecting…" : "Inspect file"}</button> : null}
          </div>
          {tabularPreview?.file_format === "xlsx" && !tabularPreview.selected_sheet_name ? (
            <div className="data-intake-attention"><strong>Choose worksheet</strong><select name="xlsx-worksheet" aria-label="XLSX worksheet" value="" onChange={(event) => void inspectUploaded(event.target.value)}><option value="">Choose</option>{tabularPreview.sheet_names.map((name) => <option key={name}>{name}</option>)}</select></div>
          ) : null}
          {tabularPreview?.header_columns.length ? (
            <>
              <div className="data-source-decision-grid">
              <div className="data-mapping-decision">
                  {mappingResolved ? (
                    <div className="data-mapping-resolved">
                      <SemanticStatus status="success" label="Columns ready" />
                      <button className="text-button" type="button" onClick={() => setMappingEditing(true)}>Change mapping</button>
                      {canonicalPreview
                        ? <button className="button primary" type="button" disabled={busy || mappingIssues.length > 0} onClick={() => void confirmLocal()}>{busy ? "Saving…" : "Save Test Data"}</button>
                        : previewValidationRejected
                          ? <button className="button secondary" type="button" disabled={busy || mappingIssues.length > 0} onClick={() => void confirmLocal("record-rejection")}>{busy ? "Recording…" : "Record rejected import"}</button>
                          : <button className="button secondary" type="button" disabled={busy || mappingIssues.length > 0} onClick={() => void previewLocalOnGraph()}>{busy ? "Preparing…" : "Update preview"}</button>}
                    </div>
                  ) : (
                    <div className="data-intake-attention">
                      <header className="data-mapping-heading"><strong>Match file columns</strong></header>
                      {mappingIssues.length ? <WorkbenchMessage className="data-mapping-blockers" kind="blocked" title="Fix the test data mapping.">{mappingIssues.map((issue) => <span key={issue}>{issue}</span>)}</WorkbenchMessage> : null}
                      {matchingProfiles.length > 1 ? <select name="approved-import-mapping" aria-label="Matching approved mapping" value={selectedProfileId} onChange={(event) => {
                        const id = event.target.value;
                        const profile = matchingProfiles.find((item) => item.import_profile_id === id);
                        setSelectedProfileId(id);
                        setMappingEditing(false);
                        if (profile) {
                          setSchema(profile.content.data_schema);
                          setIncludeTanDelta(profile.content.channels.some((channel) => channel.source_quantity === "tan_delta"));
                          setChannelColumns(profile.content.channels.map((channel) => channel.source_column));
                          setChannelUnits(profile.content.channels.map((channel) => channel.original_unit));
                          invalidateLocalPreview();
                        }
                      }}><option value="">Choose approved mapping</option>{matchingProfiles.map((profile) => <option key={profile.import_profile_id} value={profile.import_profile_id}>{profile.content.profile_label}</option>)}</select> : null}
                      <label>Test type<select name="local-data-schema" aria-label="Local data schema" value={schema} onChange={(event) => changeSchema(event.target.value as GovernedTabularDataSchema)}>{SCHEMAS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                      {schema === "dma_frequency_temperature_sweep" ? <label className="data-optional-channel"><input type="checkbox" name="include-tan-delta" checked={includeTanDelta} onChange={(event) => changeTanDelta(event.target.checked)} /> Include optional tan delta channel</label> : null}
                      <div className="data-mapping-table" role="region" aria-label="Axis and unit mapping decision table"><table><thead><tr><th>Modeling data</th><th>Column in file</th><th>File unit</th><th>Modeling unit</th></tr></thead><tbody>{channelQuantities.map((quantity, ordinal) => {
                        const column = channelColumns[ordinal] ?? "";
                        return <tr key={quantity}>
                          <td><strong>{quantityLabel(quantity)}</strong></td>
                          <td><select name={`${quantity}-source-column`} aria-label={`${quantityLabel(quantity)} source column`} title={column} value={column} onChange={(event) => changeChannelColumn(ordinal, event.target.value)}><option value="">Choose column</option>{tabularPreview.header_columns.map((name, columnOrdinal) => <option key={name} value={name} title={name}>{sourceColumnLabel(name, columnOrdinal)}</option>)}</select></td>
                          <td><select name={`${quantity}-original-unit`} aria-label={`${quantityLabel(quantity)} original unit`} value={channelUnits[ordinal] ?? defaultUnit(quantity)} onChange={(event) => changeChannelUnit(ordinal, event.target.value)}>{UNIT_OPTIONS[quantity].map((unit) => <option key={unit}>{unit}</option>)}</select></td>
                          <td><strong aria-label={`${quantityLabel(quantity)} saved unit`}>{normalizedUnit(normalizedQuantity(quantity))}</strong></td>
                        </tr>;
                      })}</tbody></table></div>
                    </div>
                  )}
                  <details className="data-import-record-details">
                    <summary>Save details</summary>
                    <div className="data-intake-row mapping-context-row">
                      <label>Data name<input name="test-data-name" autoComplete="off" spellCheck={false} value={documentKey} onChange={(event) => {
                        setDocumentKey(event.target.value);
                        invalidateLocalPreview();
                      }} /></label>
                      <label>Maker<input name="test-data-maker" autoComplete="off" value={maker} onChange={(event) => {
                        setMaker(event.target.value);
                        invalidateLocalPreview();
                      }} /></label>
                      <label>Operator<input name="test-data-operator" autoComplete="off" value={operator} onChange={(event) => {
                        setOperator(event.target.value);
                        invalidateLocalPreview();
                      }} /></label>
                      <label>Laboratory<input name="test-data-laboratory" autoComplete="off" value={laboratory} onChange={(event) => {
                        setLaboratory(event.target.value);
                        invalidateLocalPreview();
                      }} /></label>
                    </div>
                  </details>
                </div>
                {!mappingResolved && !mappingIssues.length ? (
                  <div className={`data-mapping-recovery-row${mappingIssues.length ? " is-blocked" : " is-ready"}`}>
                    <div className="data-mapping-recovery-detail">
                      {!mappingIssues.length ? <label>Reason for mapping change<input required name="mapping-change-reason" autoComplete="off" aria-label="Mapping change reason" value={mappingReason} onChange={(event) => setMappingReason(event.target.value)} placeholder="Why the mapping changed…" /></label> : null}
                      <div className="data-mapping-actions">
                        <button className="button secondary" type="button" disabled={busy || mappingIssues.length > 0 || !mappingReason.trim()} onClick={() => void previewLocalOnGraph()}>{busy ? "Preparing…" : "Update preview"}</button>
                        {previewValidationRejected
                          ? <button className="button secondary" type="button" disabled={busy || mappingIssues.length > 0 || !mappingReason.trim()} onClick={() => void confirmLocal("record-rejection")}>{busy ? "Recording…" : "Record rejected import"}</button>
                          : <button className={`button ${busy ? "primary" : mappingIssues.length > 0 || !mappingReason.trim() || !canonicalPreview ? "secondary is-prerequisite-blocked" : "primary"}`} type="button" disabled={busy || mappingIssues.length > 0 || !mappingReason.trim() || !canonicalPreview} onClick={() => void confirmLocal()}>{busy ? "Saving…" : "Save Test Data"}</button>}
                      </div>
                    </div>
                  </div>
                ) : null}
                {importDiagnostics.length ? <WorkbenchMessage className="data-import-diagnostics" kind="error" title="Import rejected · no Test Data revision was created" aria-label="Governed import diagnostics"><span>Raw source evidence is retained. Choose a corrected file; an unchanged retry returns this same result.</span><div role="region" aria-label="Rejected source cells"><table><thead><tr><th>Row</th><th>Column</th><th>Issue</th><th>Recovery</th></tr></thead><tbody>{importDiagnostics.map((diagnostic) => <tr key={`${diagnostic.ordinal}:${diagnostic.error_code}`}><td>{diagnostic.row_number ?? "File"}</td><td>{diagnostic.column_name ?? "—"}</td><td>{diagnostic.error_detail}</td><td>{diagnostic.recovery_hint}</td></tr>)}</tbody></table></div></WorkbenchMessage> : null}
              </div>
              <details className="data-source-advanced"><summary>File details</summary><div><span>File parsing</span><span>{tabularPreview.file_format.toUpperCase()} · column names in row {tabularPreview.header_row}</span><span>Original columns</span><span>{tabularPreview.header_columns.map((name, ordinal) => `Column ${ordinal + 1}: ${name}`).join(" · ")}</span><span>Mapping profile</span><span>{selectedProfile ? `${selectedProfile.content.profile_label} · saved version ${selectedProfile.current_revision.revision_no}` : "New mapping"}</span><span>Raw asset</span><code>{tabularPreview.raw_asset_id}</code><span>Raw artifact</span><code>{rawArtifactId || "—"}</code><span>Raw SHA-256</span><code>{tabularPreview.raw_sha256}</code><span>Specimen identifier</span><code>{selectedRun?.current_revision.content.specimen_id ?? "—"}</code><span>Test Run</span><span>{selectedRun?.current_revision.content.run_label ?? "not selected"} · saved version {selectedRun?.current_revision.revision_no ?? "—"} · performed {selectedRun?.current_revision.content.performed_at ?? "—"}</span><span>Saved traceability</span><span>Raw bytes, source units, Test Run, maker, operator, and laboratory remain linked to this Test Data.</span><div className="data-raw-table data-source-advanced-table" role="region" aria-label="Raw source table preview"><table><thead><tr>{tabularPreview.header_columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{tabularPreview.sample_rows.slice(0, 3).map((row, rowIndex) => <tr key={rowIndex}>{tabularPreview.header_columns.map((_, columnIndex) => <td key={columnIndex}>{row[columnIndex] ?? ""}</td>)}</tr>)}</tbody></table></div></div></details>
            </>
          ) : null}
          </> : null}
          {importKind === "json" ? (
            <div className="data-intake-row data-json-import-result">
              <strong>{jsonFile?.name}</strong>
              <SemanticText semanticRole="metadata">{jsonPreview ? `${jsonPreview.point_count.toLocaleString()} points · ${jsonPreview.channels.length} channels` : busy ? "Validating…" : "Validation required"}</SemanticText>
              {jsonPreview ? <button className="button primary" type="button" disabled={busy} onClick={() => void confirmJson()}>{busy ? "Saving…" : "Save Test Data"}</button> : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? <p className="data-intake-message error" role="alert">{error}</p> : null}
      {notice ? <p className="data-intake-message" role="status">{notice}</p> : null}
    </aside>
  );
}
