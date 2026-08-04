import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

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
  previewCommonProcessing,
  reviseCanonicalTestData,
  reviseGovernedImportProfile,
  uploadGovernedTabularFile,
  validateCanonicalTestData,
  type ApiConfig,
} from "./api";
import type { ObservedCurveInput } from "./engineering-curve-plot";
import type {
  CanonicalTestDataDocumentResponse,
  CanonicalTestDataPreviewResponse,
  CommonExportProvenance,
  CommonMappingProfileContent,
  CommonProcessingPreview,
  DataClassification,
  GovernedChannelMapping,
  GovernedImportPreview,
  GovernedImportProfileContent,
  GovernedImportProfileResponse,
  GovernedQuantityKind,
  GovernedTabularDataSchema,
  GovernedTabularFileFormat,
  MaterialResponse,
  MaterialStateResponse,
  TestRunResponse,
} from "./types";
import type { ModelingSessionRecordRef } from "./modeling-session-context";
import { MaterialsScrollRegion } from "./materials-scroll-rail";

type IntakeSource = "library" | "local" | "json";
export type ModelingDataLayoutMode = "compact" | "content-fit";

interface Props {
  config: ApiConfig;
  material?: MaterialResponse;
  state?: MaterialStateResponse;
  documents: CanonicalTestDataDocumentResponse[];
  emptySession?: boolean;
  selectedTestDataRefs?: ModelingSessionRecordRef[];
  selectedDocumentId: string;
  visibleDocumentKeys?: string[];
  processingMappingProfileText: string;
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

function quantities(schema: GovernedTabularDataSchema): [GovernedQuantityKind, GovernedQuantityKind] {
  if (schema === "simple_shear") return ["shear_strain", "shear_stress"];
  if (schema === "shear_relaxation") return ["time", "shear_modulus"];
  return ["engineering_strain", "engineering_stress"];
}

function defaultUnit(quantity: GovernedQuantityKind): string {
  if (quantity.includes("strain")) return "%";
  if (quantity === "time") return "s";
  return "MPa";
}

function quantityLabel(quantity: GovernedQuantityKind): string {
  const label = quantity.replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function normalizedUnit(quantity: GovernedQuantityKind): string {
  if (quantity.includes("strain")) return "1";
  if (quantity === "time") return "s";
  if (quantity === "displacement") return "m";
  if (quantity === "force") return "N";
  return "Pa";
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
  const specimen = item.specimen_id.match(/(?:specimen|sample|s)[-_ ]*(\d+)$/i) ?? item.specimen_id.match(/(\d+)$/);
  return specimen ? `Specimen ${specimen[1].padStart(2, "0")}` : item.specimen_id || item.document_key;
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
  onSelectDocument,
  onPreviewDocument,
  onImported,
  onObservedCurves = NOOP_OBSERVED_CURVES,
  onLayoutModeChange,
}: Props) {
  const [source, setSource] = useState<IntakeSource>("library");
  const [testRuns, setTestRuns] = useState<TestRunResponse[]>([]);
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
  const [firstColumn, setFirstColumn] = useState("");
  const [secondColumn, setSecondColumn] = useState("");
  const [firstUnit, setFirstUnit] = useState("%");
  const [secondUnit, setSecondUnit] = useState("MPa");
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
  const observedPreviewCache = useRef(new Map<string, CommonProcessingPreview>());

  useEffect(() => {
    const selectLocalSource = (event: Event) => {
      const source = (event as CustomEvent<{ source?: IntakeSource }>).detail?.source;
      if (source !== "local") return;
      setSource("local");
      window.setTimeout(() => document.querySelector<HTMLInputElement>("input[name='local-test-data-file']")?.focus(), 0);
    };
    window.addEventListener("cmp:modeling-data-source", selectLocalSource);
    return () => window.removeEventListener("cmp:modeling-data-source", selectLocalSource);
  }, []);

  useEffect(() => {
    if (emptySession) setSource("local");
  }, [emptySession]);

  const selectedRun = testRuns.find((item) => item.test_run_id === testRunId) ?? null;
  const selectedProfile = profiles.find((item) => item.import_profile_id === selectedProfileId) ?? null;
  const channelQuantities = useMemo(() => quantities(schema), [schema]);
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
    return mappingBlockers({
      independentColumn: firstColumn,
      dependentColumn: secondColumn,
      independentUnit: firstUnit,
      dependentUnit: secondUnit,
      quantities: channelQuantities,
    });
  }, [channelQuantities, firstColumn, firstUnit, secondColumn, secondUnit, tabularPreview]);
  const mappingResolved = !mappingEditing && mappingIssues.length === 0 && Boolean(
    selectedProfile && tabularPreview && profileMatchesPreview(selectedProfile, tabularPreview),
  );

  useEffect(() => {
    onLayoutModeChange?.(source === "local" && Boolean(tabularPreview?.header_columns.length)
      ? "content-fit"
      : "compact");
  }, [onLayoutModeChange, source, tabularPreview]);

  useEffect(() => {
    if (tabularPreview) setCanonicalPreview(null);
  }, [firstColumn, firstUnit, schema, secondColumn, secondUnit, tabularPreview]);

  useEffect(() => {
    if (!state || !config.accessToken) return;
    let active = true;
    void Promise.all([
      listTestRunsForMaterialState(config, state.material_state_id),
      listGovernedImportProfiles(config),
    ]).then(([runsResult, profilesResult]) => {
      if (!active) return;
      setTestRuns(runsResult.data.items);
      setProfiles(profilesResult.data);
      setTestRunId((current) => current || runsResult.data.items[0]?.test_run_id || "");
    }).catch((caught: unknown) => {
      if (active) setError(errorMessage(caught));
    });
    return () => { active = false; };
  }, [config, state]);

  useEffect(() => {
    const controller = new AbortController();
    const visibleRefs = selectedTestDataRefs.filter((ref) => visibleDocumentKeys.includes(`${ref.id}:${ref.revisionId}`));
    if (!visibleRefs.length) {
      onObservedCurves([]);
      return () => controller.abort();
    }
    let profile: CommonMappingProfileContent;
    try {
      profile = JSON.parse(processingMappingProfileText) as CommonMappingProfileContent;
    } catch {
      onObservedCurves([]);
      return () => controller.abort();
    }
    void Promise.allSettled(visibleRefs.map(async (ref) => {
      const item = documents.find((candidate) => candidate.test_data_document_id === ref.id);
      const key = `${ref.id}:${ref.revisionId}`;
      const cached = observedPreviewCache.current.get(key);
      if (cached) return { ref, item, preview: cached };
      const downloaded = await downloadCanonicalTestDataDocument(config, ref.id, ref.revisionId);
      if (controller.signal.aborted) return null;
      const sourceDocument = JSON.parse(await downloaded.data.blob.text()) as Record<string, unknown>;
      const result = await previewCommonProcessing(config, {
        document: sourceDocument,
        mapping_profile: profile,
        steps: [],
      }, controller.signal);
      observedPreviewCache.current.set(key, result.data);
      return { ref, item, preview: result.data };
    })).then((results) => {
      if (controller.signal.aborted) return;
      const curves = results.flatMap((result, index) => {
        if (result.status !== "fulfilled" || !result.value) return [];
        const { ref, item, preview } = result.value;
        return [{
          id: `${ref.id}:${ref.revisionId}`,
          label: `${item ? curveLabel(item) : ref.label} · r${ref.revisionNo}`,
          preview,
          color: ["#e56734", "#2f7f78", "#7c3aed", "#2563eb", "#dc2626"][index % 5],
        }];
      });
      onObservedCurves(curves);
    }).catch((caught: unknown) => {
      if (caught instanceof Error && caught.name === "AbortError") return;
      if (!controller.signal.aborted) setNotice("One or more Test Data curves could not be previewed; available curves remain visible.");
    });
    return () => controller.abort();
  }, [config, documents, onObservedCurves, processingMappingProfileText, selectedTestDataRefs, visibleDocumentKeys]);

  useEffect(() => {
    if (!selectedRun) return;
    const base = material?.current_revision.content.material_code
      ?? material?.current_revision.content.name
      ?? "TEST-DATA";
    setDocumentKey(`${base}-${selectedRun.current_revision.content.run_label}`.replace(/\s+/g, "-"));
    setMaker((current) => current || material?.current_revision.content.name || "");
  }, [material, selectedRun]);

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
    setFirstColumn(inspected.data.header_columns[0] ?? "");
    setSecondColumn(inspected.data.header_columns[1] ?? "");
    const matches = profiles.filter((profile) =>
      profile.current_revision.classification === selectedRun?.current_revision.classification
      && profileMatchesPreview(profile, inspected.data));
    if (matches.length === 1) {
      const matched = matches[0];
      setSelectedProfileId(matched.import_profile_id);
      setMappingEditing(false);
      setSchema(matched.content.data_schema);
      setFirstColumn(matched.content.channels[0]?.source_column ?? "");
      setSecondColumn(matched.content.channels[1]?.source_column ?? "");
      setFirstUnit(matched.content.channels[0]?.original_unit ?? "%");
      setSecondUnit(matched.content.channels[1]?.original_unit ?? "MPa");
      setNotice(`Matched approved mapping ${matched.content.profile_label} · r${matched.current_revision.revision_no}.`);
    } else {
      setSelectedProfileId("");
      setMappingEditing(true);
      setNotice(unmatchedMappingNotice(matches.length));
    }
  }

  async function chooseLocalFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const selected = event.target.files?.[0] ?? null;
    if (!selected) return;
    const detected = fileFormat(selected);
    if (!detected) {
      setError("Choose a CSV, TSV, or XLSX file.");
      return;
    }
    setFile(selected);
    setFormat(detected);
    setSheetName(null);
    setTabularPreview(null);
    setCanonicalPreview(null);
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

  function currentProfile(): GovernedImportProfileContent | null {
    if (!tabularPreview || !firstColumn || !secondColumn) return null;
    const channels: GovernedChannelMapping[] = [
      {
        ordinal: 0,
        source_column: firstColumn,
        source_quantity: channelQuantities[0],
        original_unit: firstUnit,
        axis_role: "independent",
      },
      {
        ordinal: 1,
        source_column: secondColumn,
        source_quantity: channelQuantities[1],
        original_unit: secondUnit,
        axis_role: "dependent",
      },
    ];
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
      setError("Complete the Test Run, data name, maker, operator, laboratory, and two required channel rows.");
      return;
    }
    setBusy(true);
    setError("");
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
      await previewOnGraph(result.data.canonical_document);
      setNotice("Graph preview is calculated from the local file. Nothing has been registered yet.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function confirmLocal(): Promise<void> {
    const profile = currentProfile();
    if (!material || !state || !selectedRun || !profile || !canonicalPreview || !rawAssetId || !rawArtifactId) {
      setError("Choose an exact Material, Material State, and Test Run before saving local Test Data.");
      return;
    }
    const governedSource = governedSourceFor(material, state, selectedRun);
    setBusy(true);
    setError("");
    try {
      let approved = selectedProfile;
      if (!approved) {
        const created = await createGovernedImportProfile(config, {
          classification: selectedRun.current_revision.classification as DataClassification,
          content: profile,
          change_reason: "Human-confirmed mapping from Modeling Data intake",
        });
        approved = created.data;
      } else if (JSON.stringify(editableProfile(approved.content)) !== JSON.stringify(profile)) {
        const revised = await reviseGovernedImportProfile(config, approved.import_profile_id, {
          expected_current_revision_id: approved.current_revision.id,
          content: profile,
          change_reason: "Human-confirmed mapping adjustment from Modeling Data intake",
        });
        approved = revised.data;
      }
      const run = await executeGovernedTabularImport(config, {
        test_run_id: selectedRun.test_run_id,
        test_run_revision_id: selectedRun.current_revision.id,
        raw_asset_id: rawAssetId,
        raw_artifact_id: rawArtifactId,
        import_profile_id: approved.import_profile_id,
        import_profile_revision_id: approved.current_revision.id,
        change_reason: "Save local source and normalized Test Data revisions",
      });
      if (run.data.status !== "succeeded") {
        throw new ApiError(422, run.data.failure_detail ?? "The governed import did not succeed.");
      }
      const existing = documents.find((item) => item.document_key === documentKey.trim());
      const imported = existing
        ? await reviseCanonicalTestData(
            config,
            existing.test_data_document_id,
            `"revision:${existing.current_revision.revision_no}:sha256:${existing.current_revision.content_hash}"`,
            {
              document: canonicalPreview.canonical_document,
              change_reason: "Save local Test Data source",
              governed_source: governedSource,
            },
          )
        : await importCanonicalTestData(config, {
            classification: selectedRun.current_revision.classification as DataClassification,
            document: canonicalPreview.canonical_document,
            change_reason: "Save local Test Data source",
            governed_source: governedSource,
          });
      onImported(imported.data);
      setSource("library");
      setCanonicalPreview(null);
      setTabularPreview(null);
      setNotice(`Registered ${imported.data.document_key} · exact revision r${imported.data.current_revision.revision_no}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function chooseJson(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const selected = event.target.files?.[0] ?? null;
    if (!selected) return;
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

  async function previewOnGraph(document: Record<string, unknown>): Promise<void> {
    const graph = await previewCommonProcessing(config, {
      document,
      mapping_profile: JSON.parse(processingMappingProfileText) as CommonMappingProfileContent,
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
      setSource("library");
      setJsonPreview(null);
      setNotice(`Registered ${imported.data.document_key} · exact revision r${imported.data.current_revision.revision_no}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="modeling-data-intake" aria-label="Modeling data intake">
      <div className="data-source-tabs" role="tablist" aria-label="Test data source">
        <button type="button" role="tab" aria-selected={source === "library"} onClick={() => setSource("library")}>Library</button>
        <button type="button" role="tab" aria-selected={source === "local"} onClick={() => setSource("local")}>Local file</button>
        <button type="button" role="tab" aria-selected={source === "json"} onClick={() => setSource("json")}>Test Data JSON</button>
      </div>

      {source === "library" ? (
        <div className="data-library-pane">
          <header className="data-library-heading">
            <strong>Saved Test Data</strong>
            <span>{documents.length} exact revision{documents.length === 1 ? "" : "s"}</span>
          </header>
          <MaterialsScrollRegion
            className="data-library-list"
            shellClassName="data-library-scroll-shell"
            id="modeling-data-library-list"
            role="list"
            aria-label="Saved Test Data revisions"
            tabIndex={0}
          >
            {documents.map((item) => {
              const selectedRef = selectedTestDataRefs.find((ref) => ref.id === item.test_data_document_id);
              const materialRevisionChanged = Boolean(item.governed_source
                && material
                && state
                && (item.governed_source.material.revision_id !== material.current_revision.id
                  || item.governed_source.material_state.revision_id !== state.current_revision.id));
              return <article className={selectedDocumentId === item.test_data_document_id ? "active" : ""} role="listitem" key={`${item.test_data_document_id}:${item.current_revision.id}`}>
              <button type="button" className="data-library-row" onClick={() => onSelectDocument(item.test_data_document_id, item.current_revision.id)}>
                <strong>{item.document_key}</strong><span>{curveLabel(item)} · {selectedRef?.revisionId === item.current_revision.id ? `Session revision r${selectedRef.revisionNo}` : `r${item.current_revision.revision_no}`}</span><small>{item.channels.map((channel) => `${channel.name} ${channel.original_unit_string} → ${channel.normalized_unit}`).join(" · ")}</small>{materialRevisionChanged ? <small className="data-library-warning">Recorded for an earlier material revision; selecting keeps this exact test source.</small> : null}
              </button>
            </article>;
            })}
            {selectedTestDataRefs.filter((ref) => {
              const current = documents.find((item) => item.test_data_document_id === ref.id);
              return current && current.current_revision.id !== ref.revisionId;
            }).map((ref) => {
              const current = documents.find((item) => item.test_data_document_id === ref.id);
              return <article className={selectedDocumentId === ref.id ? "active historical" : "historical"} role="listitem" key={`${ref.id}:${ref.revisionId}`}>
                <button type="button" className="data-library-row" onClick={() => onSelectDocument(ref.id, ref.revisionId)}>
                  <strong>{ref.label}</strong><span>Session revision r{ref.revisionNo} · exact source retained</span><small>{current?.channels.map((channel) => `${channel.name} ${channel.original_unit_string} → ${channel.normalized_unit}`).join(" · ")}</small>
                </button>
              </article>;
            })}
            {!documents.length ? <p className="muted">No Test Data is connected to this material state.</p> : null}
          </MaterialsScrollRegion>
        </div>
      ) : null}

      {source === "local" ? (
        <div className={`data-intake-local${mappingIssues.length ? " has-mapping-blockers" : ""}`}>
          <div className="data-intake-row">
            <label>Exact Test Run<select name="local-test-run" aria-label="Local file Test Run" value={testRunId} onChange={(event) => setTestRunId(event.target.value)}><option value="">Choose a Run</option>{testRuns.map((item) => <option key={item.test_run_id} value={item.test_run_id}>{item.current_revision.content.run_label} · r{item.current_revision.revision_no}</option>)}</select></label>
            <label className="compact-file-picker">Local file<input name="local-test-data-file" aria-label="Local test data file" type="file" accept=".csv,.tsv,.xlsx" onChange={(event) => void chooseLocalFile(event)} /></label>
            {!tabularPreview ? <button className="button primary" type="button" disabled={busy || !file || !selectedRun} onClick={() => void uploadAndInspect()}>{busy ? "Inspecting…" : "Inspect source"}</button> : null}
          </div>
          {tabularPreview?.file_format === "xlsx" && !tabularPreview.selected_sheet_name ? (
            <div className="data-intake-attention"><strong>Choose worksheet</strong><select name="xlsx-worksheet" aria-label="XLSX worksheet" value="" onChange={(event) => void inspectUploaded(event.target.value)}><option value="">Choose</option>{tabularPreview.sheet_names.map((name) => <option key={name}>{name}</option>)}</select></div>
          ) : null}
          {tabularPreview?.header_columns.length ? (
            <>
              <div className="data-source-decision-grid">
              <section className="data-source-evidence" aria-label="Raw source inspector">
                <header><strong>Raw source inspector</strong><span>{tabularPreview.file_format.toUpperCase()} · header row {tabularPreview.header_row} · decimal {tabularPreview.decimal_separator}</span></header>
                <p>Raw bytes stay immutable; source units remain visible in the mapping decision.</p>
                <div className="data-raw-table" role="region" aria-label="Raw source table preview"><table><thead><tr>{tabularPreview.header_columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{tabularPreview.sample_rows.slice(0, 3).map((row, rowIndex) => <tr key={rowIndex}>{tabularPreview.header_columns.map((_, columnIndex) => <td key={columnIndex}>{row[columnIndex] ?? ""}</td>)}</tr>)}</tbody></table></div>
              </section>
              <div className="data-mapping-decision">
              <div className="data-intake-row mapping-context-row">
                <label>Data name<input name="test-data-name" autoComplete="off" spellCheck={false} value={documentKey} onChange={(event) => setDocumentKey(event.target.value)} /></label>
                <label>Maker<input name="test-data-maker" autoComplete="off" value={maker} onChange={(event) => setMaker(event.target.value)} /></label>
                <label>Operator<input name="test-data-operator" autoComplete="off" value={operator} onChange={(event) => setOperator(event.target.value)} /></label>
                <label>Laboratory<input name="test-data-laboratory" autoComplete="off" value={laboratory} onChange={(event) => setLaboratory(event.target.value)} /></label>
              </div>
                  {mappingResolved ? (
                    <div className="data-mapping-resolved">
                      <strong>Approved mapping matched</strong>
                      <span>{selectedProfile?.content.profile_label} · r{selectedProfile?.current_revision.revision_no} · {selectedProfile?.content.channels.map((channel) => `${channel.source_column} [${channel.original_unit}]`).join(" / ")}</span>
                      <button className="text-button" type="button" onClick={() => setMappingEditing(true)}>Change mapping</button>
                      {!canonicalPreview ? <button className="button secondary" type="button" disabled={busy || mappingIssues.length > 0} onClick={() => void previewLocalOnGraph()}>{busy ? "Preparing…" : "Update preview"}</button> : <button className="button primary" type="button" disabled={busy || mappingIssues.length > 0} onClick={() => void confirmLocal()}>{busy ? "Saving…" : "Save Test Data"}</button>}
                    </div>
                  ) : (
                    <div className="data-intake-attention">
                      <header className="data-mapping-heading"><strong>Mapping decision</strong><span>Blocked · review required</span></header>
                      {matchingProfiles.length > 1 ? <select name="approved-import-mapping" aria-label="Matching approved mapping" value={selectedProfileId} onChange={(event) => {
                        const id = event.target.value;
                        const profile = matchingProfiles.find((item) => item.import_profile_id === id);
                        setSelectedProfileId(id);
                        setMappingEditing(false);
                        if (profile) {
                          setSchema(profile.content.data_schema);
                          setFirstColumn(profile.content.channels[0]?.source_column ?? "");
                          setSecondColumn(profile.content.channels[1]?.source_column ?? "");
                          setFirstUnit(profile.content.channels[0]?.original_unit ?? "%");
                          setSecondUnit(profile.content.channels[1]?.original_unit ?? "MPa");
                        }
                      }}><option value="">Choose approved mapping</option>{matchingProfiles.map((profile) => <option key={profile.import_profile_id} value={profile.import_profile_id}>{profile.content.profile_label} · r{profile.current_revision.revision_no}</option>)}</select> : null}
                      <label>Test type<select name="local-data-schema" aria-label="Local data schema" value={schema} onChange={(event) => {
                        const next = event.target.value as GovernedTabularDataSchema;
                        const nextQuantities = quantities(next);
                        setSchema(next);
                        setFirstUnit(defaultUnit(nextQuantities[0]));
                        setSecondUnit(defaultUnit(nextQuantities[1]));
                      }}>{SCHEMAS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                      <div className="data-mapping-table" role="region" aria-label="Axis and unit mapping decision table"><table><thead><tr><th>Axis</th><th>Source column</th><th>Quantity semantics</th><th>Raw unit</th><th>Normalized unit</th><th>Status</th></tr></thead><tbody><tr><td>Independent</td><td><select name="independent-source-column" aria-label="Independent source column" value={firstColumn} onChange={(event) => setFirstColumn(event.target.value)}><option value="">Choose required column</option>{tabularPreview.header_columns.map((name) => <option key={name}>{name}</option>)}</select></td><td>{quantityLabel(channelQuantities[0])}</td><td><select name="independent-original-unit" aria-label="Independent original unit" value={firstUnit} onChange={(event) => setFirstUnit(event.target.value)}>{UNIT_OPTIONS[channelQuantities[0]].map((unit) => <option key={unit}>{unit}</option>)}</select></td><td>{normalizedUnit(channelQuantities[0])}</td><td>{firstColumn === secondColumn && firstColumn ? "Needs correction" : mappingIssues.find((issue) => issue.includes(quantityLabel(channelQuantities[0]))) ? "Blocked · review" : "Ready"}</td></tr><tr><td>Dependent</td><td><select name="dependent-source-column" aria-label="Dependent source column" value={secondColumn} onChange={(event) => setSecondColumn(event.target.value)}><option value="">Choose required column</option>{tabularPreview.header_columns.map((name) => <option key={name}>{name}</option>)}</select></td><td>{quantityLabel(channelQuantities[1])}</td><td><select name="dependent-original-unit" aria-label="Dependent original unit" value={secondUnit} onChange={(event) => setSecondUnit(event.target.value)}>{UNIT_OPTIONS[channelQuantities[1]].map((unit) => <option key={unit}>{unit}</option>)}</select></td><td>{normalizedUnit(channelQuantities[1])}</td><td>{firstColumn === secondColumn && firstColumn ? "Needs correction" : mappingIssues.find((issue) => issue.includes(quantityLabel(channelQuantities[1]))) ? "Blocked · review" : "Ready"}</td></tr></tbody></table></div>
                    </div>
                  )}
                </div>
                {!mappingResolved ? (
                  <div className="data-mapping-recovery-row">
                    <div className={`data-mapping-blockers${mappingIssues.length ? "" : " is-ready"}`} role={mappingIssues.length ? "alert" : "status"}>
                      <strong>{mappingIssues.length ? "Fix the test data mapping." : "Mapping is ready for preview."}</strong>
                      {mappingIssues.map((issue) => <span key={issue}>{issue}</span>)}
                    </div>
                    <div className="data-mapping-recovery-detail">
                      <label>Mapping change reason<input required aria-label="Mapping change reason" value={mappingReason} onChange={(event) => setMappingReason(event.target.value)} placeholder="Why this source meaning and unit are correct" /></label>
                      <p className="data-mapping-consequence">{mappingUnitConsequence(channelQuantities[0], channelQuantities[1])}</p>
                      <div className="data-mapping-actions">
                        <button className="button secondary" type="button" disabled={busy || mappingIssues.length > 0 || !mappingReason.trim()} onClick={() => void previewLocalOnGraph()}>{busy ? "Preparing…" : "Update preview"}</button>
                        <button className={`button ${busy ? "primary" : mappingIssues.length > 0 || !mappingReason.trim() || !canonicalPreview ? "secondary is-prerequisite-blocked" : "primary"}`} type="button" disabled={busy || mappingIssues.length > 0 || !mappingReason.trim() || !canonicalPreview} onClick={() => void confirmLocal()}>{busy ? "Saving…" : "Save Test Data"}</button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
              <details className="data-source-advanced"><summary>Advanced source evidence</summary><div><span>Raw asset</span><code>{tabularPreview.raw_asset_id}</code><span>Raw artifact</span><code>{rawArtifactId || "—"}</code><span>Raw SHA-256</span><code>{tabularPreview.raw_sha256}</code><span>Specimen identifier</span><code>{selectedRun?.current_revision.content.specimen_id ?? "—"}</code><span>Test Run context</span><span>{selectedRun?.current_revision.content.run_label ?? "not selected"} · r{selectedRun?.current_revision.revision_no ?? "—"} · performed {selectedRun?.current_revision.content.performed_at ?? "—"}</span><span>Recorded provenance</span><span>Governed Test Run metadata; maker, operator and laboratory are recorded with this save.</span></div></details>
            </>
          ) : null}
        </div>
      ) : null}

      {source === "json" ? (
        <div className="data-intake-row">
          <label className="compact-file-picker">Canonical JSON<input name="canonical-test-data-json" aria-label="Test Data JSON file" type="file" accept=".json,application/json" onChange={(event) => void chooseJson(event)} /></label>
          <p>{jsonPreview ? `${jsonPreview.point_count} points · ${jsonPreview.channels.length} channels · valid` : "Choose a canonical Test Data JSON file to validate and preview."}</p>
          {jsonPreview ? <button className="button primary" type="button" disabled={busy} onClick={() => void confirmJson()}>{busy ? "Saving…" : "Save dataset"}</button> : null}
        </div>
      ) : null}

      {error ? <p className="data-intake-message error" role="alert">{error}</p> : null}
      {notice ? <p className="data-intake-message" role="status">{notice}</p> : null}
    </aside>
  );
}
