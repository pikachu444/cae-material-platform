import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";

import {
  ApiError,
  applySchemaDefinitionBundle,
  downloadSchemaDefinitionBundle,
  getEffectiveProductAccess,
  getSchemaDefinitionBundleApplication,
  planSchemaDefinitionBundle,
  uploadSchemaDefinitionBundle,
  type ApiConfig,
} from "./definition-bundle-api";
import { publishWorkspaceStatus } from "../../../design/application-shell";
import { EngineeringPane, SemanticText } from "../../../design/semantic-ui";
import {
  definitionBundleRoutePath,
  parseDefinitionBundleRouteSelection,
} from "../model/administration-route-state";
import type {
  DataClassification,
  SchemaDefinitionBundleApplication,
  SchemaDefinitionBundleDiagnostic,
  SchemaDefinitionBundlePlan,
  SchemaDefinitionBundlePlanAction,
} from "./model";

const BUNDLE_SCHEMA =
  "https://cmp.example/contracts/catalog/schema-definition-bundle.schema.json";
const SOURCE_SET_SCHEMA =
  "https://cmp.example/contracts/catalog/schema-definition-source-set.schema.json";
const SOURCE_SET_MEDIA_TYPE = "application/vnd.cmp.catalog-schema-source-set+json";
const SOURCE_ZIP_MEDIA_TYPE = "application/vnd.cmp.catalog-schema-source-set+zip";
const MAX_BUNDLE_BYTES = 64 * 1024 * 1024;
const RECOVERY_KEY = "cmp.schema-definition-bundle-administration.v1";
const ACCEPTED_MEDIA_TYPES = new Set([
  "",
  "application/json",
  "application/schema+json",
  "application/vnd.cmp.catalog-schema-definition-bundle+json",
  SOURCE_SET_MEDIA_TYPE,
  "application/zip",
  SOURCE_ZIP_MEDIA_TYPE,
]);
const CLASSIFICATIONS = new Set<DataClassification>([
  "internal",
  "confidential",
  "restricted",
  "export_controlled",
]);

interface BundleFileSummary {
  file: File;
  bundleKey: string;
  bundleVersion: string;
  classification: DataClassification;
  schemaCount: number;
  unitProfileCount: number | null;
  fileCount: number;
  sourceFormat: "canonical JSON" | "source file set" | "ZIP source set";
}

interface RecoveryState {
  artifactId: string;
  artifactSha256: string;
  bundleKey: string | null;
  bundleVersion: string | null;
  applicationId: string | null;
}

interface OperationError {
  message: string;
  code: string | null;
  correlationId: string | null;
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export async function inspectSchemaDefinitionBundleFile(
  file: File,
): Promise<BundleFileSummary> {
  return inspectSchemaDefinitionBundleFiles([file]);
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function strictUtf8Text(file: File): Promise<string> {
  try {
    return new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(
      await file.arrayBuffer(),
    );
  } catch {
    throw new Error(`${file.name} is not valid UTF-8 JSON.`);
  }
}

function sourcePath(file: File): string {
  const relative = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  return relative?.replaceAll("\\", "/") || file.name;
}

export async function inspectSchemaDefinitionBundleFiles(
  files: File[],
): Promise<BundleFileSummary> {
  if (files.length < 1 || files.length > 128) {
    throw new Error("Choose 1 to 128 JSON source files, or one ZIP source set.");
  }
  if (files.length === 1 && files[0]!.name.toLowerCase().endsWith(".zip")) {
    const file = files[0]!;
    if (file.size < 1 || file.size > MAX_BUNDLE_BYTES) {
      throw new Error("The ZIP source set must be between 1 byte and 64 MiB.");
    }
    const prepared = new File([file], file.name, { type: SOURCE_ZIP_MEDIA_TYPE });
    return {
      file: prepared,
      bundleKey: file.name.replace(/\.zip$/i, ""),
      bundleVersion: "Server-verified",
      classification: "internal",
      schemaCount: 0,
      unitProfileCount: null,
      fileCount: 1,
      sourceFormat: "ZIP source set",
    };
  }
  if (files.some((file) => !file.name.toLowerCase().endsWith(".json"))) {
    throw new Error("A source file set may contain JSON files only.");
  }
  if (files.reduce((total, file) => total + file.size, 0) > MAX_BUNDLE_BYTES) {
    throw new Error("The selected source files are larger than 64 MiB in total.");
  }
  const parsed = await Promise.all(files.map(async (file) => {
    const text = await strictUtf8Text(file);
    try {
      return { file, text, document: JSON.parse(text) as unknown };
    } catch {
      throw new Error(`${file.name} is not valid JSON.`);
    }
  }));
  const envelope = files.length === 1 ? objectValue(parsed[0]!.document) : null;
  if (envelope?.$schema === SOURCE_SET_SCHEMA) {
    const entries = Array.isArray(envelope.files) ? envelope.files : [];
    if (envelope.contract_version !== "1.0.0" || entries.length < 2 || entries.length > 128) {
      throw new Error("The source-set envelope is not a bounded version 1.0.0 source set.");
    }
    const checked = await Promise.all(entries.map(async (entry) => {
      const value = objectValue(entry);
      if (
        typeof value?.path !== "string"
        || typeof value.content !== "string"
        || typeof value.sha256 !== "string"
        || await sha256(value.content) !== value.sha256
      ) {
        throw new Error("The source-set envelope contains an invalid file or checksum.");
      }
      return { path: value.path, content: value.content };
    }));
    const manifests = checked.filter(({ path }) => (
      path.endsWith("catalog-schema-bundle.manifest.json")
    ));
    if (manifests.length !== 1) {
      throw new Error("The source-set envelope requires one source-v2 manifest.");
    }
    const manifest = objectValue(JSON.parse(manifests[0]!.content));
    const tables = Array.isArray(manifest?.tables) ? manifest.tables : [];
    const unitProfiles = Array.isArray(manifest?.unit_profiles) ? manifest.unit_profiles : [];
    if (!manifest || manifest.document_type !== "cmp.catalog-schema-bundle" || !tables.length) {
      throw new Error("The selected source set does not contain a valid source-v2 definition package.");
    }
    return {
      file: new File([files[0]!], files[0]!.name, { type: SOURCE_SET_MEDIA_TYPE }),
      bundleKey: typeof manifest.bundle_id === "string" ? manifest.bundle_id : "source-v2",
      bundleVersion: typeof manifest.bundle_version === "string"
        ? manifest.bundle_version
        : "Server-verified",
      classification: "internal",
      schemaCount: tables.length,
      unitProfileCount: unitProfiles.length,
      fileCount: entries.length,
      sourceFormat: "source file set",
    };
  }
  const sourceManifest = parsed.filter(({ document }) => (
    objectValue(document)?.document_type === "cmp.catalog-schema-bundle"
  ));
  if (sourceManifest.length > 0) {
    if (sourceManifest.length !== 1) {
      throw new Error("Choose exactly one source-v2 manifest.");
    }
    const manifest = objectValue(sourceManifest[0]!.document)!;
    const tables = Array.isArray(manifest.tables) ? manifest.tables : [];
    const unitProfiles = Array.isArray(manifest.unit_profiles) ? manifest.unit_profiles : [];
    if (tables.length < 1) {
      throw new Error("The source-v2 manifest has no Tables.");
    }
    const requiredPaths = tables.map((value) => {
      const reference = objectValue(value)?.record_schema_ref;
      if (typeof reference !== "string" || !reference.trim()) {
        throw new Error("Every source-v2 Table must name a record_schema_ref.");
      }
      return reference.replace(/^\.\//, "");
    });
    const resolved = new Map<string, File>();
    for (const requiredPath of requiredPaths) {
      const matches = files.filter((file) => (
        sourcePath(file).endsWith(requiredPath)
        || file.name === requiredPath.split("/").at(-1)
      ));
      if (matches.length !== 1) {
        throw new Error(`Choose exactly one source file for ${requiredPath}.`);
      }
      resolved.set(requiredPath, matches[0]!);
    }
    if (files.length !== requiredPaths.length + 1) {
      throw new Error("Choose the manifest and each referenced record schema once.");
    }
    const manifestFile = sourceManifest[0]!.file;
    const entries = [
      { path: "catalog-schema-bundle.manifest.json", file: manifestFile },
      ...requiredPaths.map((path) => ({ path, file: resolved.get(path)! })),
    ].sort((left, right) => left.path.localeCompare(right.path));
    const envelopeFiles = await Promise.all(entries.map(async ({ path, file }) => {
      const content = parsed.find((item) => item.file === file)!.text;
      return { path, sha256: await sha256(content), content };
    }));
    const envelope = JSON.stringify({
      $schema: SOURCE_SET_SCHEMA,
      contract_version: "1.0.0",
      files: envelopeFiles,
    });
    const bundleKey = typeof manifest.bundle_id === "string" ? manifest.bundle_id : "source-v2";
    const bundleVersion = typeof manifest.bundle_version === "string"
      ? manifest.bundle_version
      : "Server-verified";
    return {
      file: new File([envelope], `${bundleKey}-source-set.json`, {
        type: SOURCE_SET_MEDIA_TYPE,
      }),
      bundleKey,
      bundleVersion,
      classification: "internal",
      schemaCount: tables.length,
      unitProfileCount: unitProfiles.length,
      fileCount: envelopeFiles.length,
      sourceFormat: "source file set",
    };
  }
  if (files.length !== 1) {
    throw new Error("Multiple JSON files require one source-v2 manifest.");
  }
  const file = files[0]!;
  const filename = file.name.trim();
  if (!filename || filename.includes("/") || filename.includes("\\")) {
    throw new Error("Choose format-definition files with safe, non-empty filenames.");
  }
  if (!filename.toLowerCase().endsWith(".json") || !ACCEPTED_MEDIA_TYPES.has(file.type)) {
    throw new Error("Choose JSON format-definition files or a ZIP definition package.");
  }
  if (file.size < 1) {
    throw new Error("The selected definition file is empty.");
  }
  if (file.size > MAX_BUNDLE_BYTES) {
    throw new Error("The selected definition file is larger than 64 MiB.");
  }

  let document: unknown;
  try {
    document = JSON.parse(parsed[0]!.text) as unknown;
  } catch {
    throw new Error("The selected file is not valid JSON.");
  }
  const root = objectValue(document);
  const scope = objectValue(root?.scope);
  const catalog = objectValue(root?.catalog);
  const recordSchemas = root?.record_schemas;
  if (
    !root ||
    root.$schema !== BUNDLE_SCHEMA ||
    root.contract_version !== "1.0.0" ||
    typeof root.bundle_key !== "string" ||
    typeof root.bundle_version !== "string" ||
    !scope ||
    !CLASSIFICATIONS.has(scope.classification as DataClassification) ||
    !catalog ||
    !objectValue(catalog.database) ||
    !objectValue(catalog.profile) ||
    !Array.isArray(recordSchemas) ||
    recordSchemas.length < 1
  ) {
    throw new Error(
      "The JSON is not a valid version 1.0.0 format-definition file with a scope, catalog, and at least one record type definition.",
    );
  }

  return {
    file,
    bundleKey: root.bundle_key,
    bundleVersion: root.bundle_version,
    classification: scope.classification as DataClassification,
    schemaCount: recordSchemas.length,
    unitProfileCount: Array.isArray(root.unit_profiles) ? root.unit_profiles.length : 0,
    fileCount: 1,
    sourceFormat: "canonical JSON",
  };
}

function readRecovery(): RecoveryState | null {
  try {
    const parsed = objectValue(JSON.parse(window.sessionStorage.getItem(RECOVERY_KEY) ?? "null"));
    if (
      !parsed ||
      typeof parsed.artifactId !== "string" ||
      typeof parsed.artifactSha256 !== "string"
    ) {
      return null;
    }
    return {
      artifactId: parsed.artifactId,
      artifactSha256: parsed.artifactSha256,
      bundleKey: typeof parsed.bundleKey === "string" ? parsed.bundleKey : null,
      bundleVersion:
        typeof parsed.bundleVersion === "string" ? parsed.bundleVersion : null,
      applicationId:
        typeof parsed.applicationId === "string" ? parsed.applicationId : null,
    };
  } catch {
    window.sessionStorage.removeItem(RECOVERY_KEY);
    return null;
  }
}

function writeRecovery(value: RecoveryState): void {
  try {
    window.sessionStorage.setItem(RECOVERY_KEY, JSON.stringify(value));
  } catch {
    // Recovery is helpful but must never weaken the server-owned operation.
  }
}

function clearRecovery(): void {
  try {
    window.sessionStorage.removeItem(RECOVERY_KEY);
  } catch {
    // A blocked storage implementation does not block a new server-owned plan.
  }
}

function operationError(error: unknown, fallback: string): OperationError {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      code: error.code ?? null,
      correlationId: error.traceId ?? null,
    };
  }
  return {
    message: error instanceof Error ? error.message : fallback,
    code: null,
    correlationId: null,
  };
}

function targetLabel(value: SchemaDefinitionBundlePlanAction["target_type"]): string {
  return {
    bundle: "Definition set",
    database: "Database",
    profile: "Configuration",
    table: "Record type",
    attribute: "Attribute",
    layout: "Layout",
    profile_table_placement: "Table placement",
    link_type: "Link Type",
  }[value];
}

function dispositionLabel(value: SchemaDefinitionBundlePlanAction["disposition"]): string {
  return value === "no-op" ? "No change" : `${value[0]?.toUpperCase()}${value.slice(1)}`;
}

function actionDisplayName(action: SchemaDefinitionBundlePlanAction): string {
  const projectedName = action.projected?.name;
  return typeof projectedName === "string" && projectedName.trim()
    ? projectedName
    : action.external_key;
}

function diagnosticForAction(
  action: SchemaDefinitionBundlePlanAction,
  diagnostics: SchemaDefinitionBundleDiagnostic[],
): SchemaDefinitionBundleDiagnostic | null {
  return (
    diagnostics.find((item) => item.location.includes(action.external_key)) ??
    diagnostics.find((item) => item.severity === "error") ??
    null
  );
}

function moveRowFocus(
  event: KeyboardEvent<HTMLButtonElement>,
  index: number,
  count: number,
  select: (next: number) => void,
): void {
  const next =
    event.key === "ArrowDown"
      ? Math.min(count - 1, index + 1)
      : event.key === "ArrowUp"
        ? Math.max(0, index - 1)
        : event.key === "Home"
          ? 0
          : event.key === "End"
            ? count - 1
            : null;
  if (next === null) return;
  event.preventDefault();
  select(next);
  document.querySelector<HTMLButtonElement>(`[data-bundle-row=\"${next}\"]`)?.focus();
}

export function SchemaDefinitionBundleAdmin({
  config,
  locationSearch = "",
  onNavigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  locationSearch?: string;
  onNavigate?: (path: string) => void;
  onOpenConnection: () => void;
}) {
  const requestedSelection = useMemo(
    () => parseDefinitionBundleRouteSelection(locationSearch),
    [locationSearch],
  );
  const [roleState, setRoleState] = useState<"checking" | "administrator" | "denied" | "error">(
    "checking",
  );
  const [phase, setPhase] = useState<
    "empty" | "uploading" | "planning" | "ready" | "applying" | "restoring" | "applied" | "failed"
  >("empty");
  const [fileSummary, setFileSummary] = useState<BundleFileSummary | null>(null);
  const [artifact, setArtifact] = useState<{ id: string; sha256: string } | null>(null);
  const [plan, setPlan] = useState<SchemaDefinitionBundlePlan | null>(null);
  const [application, setApplication] = useState<SchemaDefinitionBundleApplication | null>(null);
  const [applicationRecoveryId, setApplicationRecoveryId] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<OperationError | null>(null);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportEvidence, setExportEvidence] = useState<{ sha256: string; filename: string } | null>(
    null,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);
  const operationGenerationRef = useRef(0);
  const loadedApplicationIdRef = useRef<string | null>(null);

  function beginOperation(): number {
    operationGenerationRef.current += 1;
    return operationGenerationRef.current;
  }

  function operationIsCurrent(generation: number): boolean {
    return operationGenerationRef.current === generation;
  }

  const planMigrationRequired = Boolean(
    plan?.actions.some((action) => action.reason_codes.includes("record_migration_required")) ||
      plan?.diagnostics.some((diagnostic) => diagnostic.code === "CMP-SCHEMA-BUNDLE-0014"),
  );
  const planApplicable = Boolean(
    plan?.valid &&
      plan.bundle &&
      plan.action_counts.conflict === 0 &&
      plan.action_counts.error === 0 &&
      !planMigrationRequired,
  );
  const busy =
    exporting ||
    phase === "uploading" ||
    phase === "planning" ||
    phase === "applying" ||
    phase === "restoring";
  const sourceLocked = Boolean(artifact || plan || application || applicationRecoveryId);
  const selectedPlanAction = application ? null : plan?.actions[selectedIndex] ?? null;
  const selectedResult = application?.results[selectedIndex] ?? null;

  useEffect(() => {
    publishWorkspaceStatus({
      selection: application
        ? `${application.bundle_key} ${application.bundle_version}`
        : plan?.bundle
          ? `${plan.bundle.bundle_key} ${plan.bundle.bundle_version}`
          : "Format definitions",
      revision: application
        ? "Verified result"
        : plan
          ? `${plan.actions.length} ${plan.actions.length === 1 ? "change" : "changes"} to review`
          : fileSummary
            ? "Files selected"
            : "",
      jobs:
        phase === "uploading" || phase === "planning" || phase === "applying" || phase === "restoring"
          ? "Operation in progress"
          : "",
      warnings: error ? "1 action required" : plan && !planApplicable ? "Changes blocked" : "",
      connection: roleState === "error" ? "degraded" : "online",
    });
  }, [application, error, fileSummary, phase, plan, planApplicable, roleState]);

  useEffect(() => {
    let active = true;
    async function load(): Promise<void> {
      setRoleState("checking");
      try {
        const access = await getEffectiveProductAccess(config);
        if (!active) return;
        if (access.data.product_role !== "administrator") {
          setRoleState("denied");
          return;
        }
        setRoleState("administrator");
        const requestedApplicationId = requestedSelection.applicationId;
        if (requestedApplicationId) {
          if (loadedApplicationIdRef.current === requestedApplicationId) return;
          setApplicationRecoveryId(requestedApplicationId);
          setPhase("restoring");
          const restored = await getSchemaDefinitionBundleApplication(
            config,
            requestedApplicationId,
          );
          if (!active) return;
          const restoredArtifact = {
            id: restored.data.source_artifact.artifact_id,
            sha256: restored.data.source_artifact.sha256,
          };
          setArtifact(restoredArtifact);
          setApplication(restored.data);
          loadedApplicationIdRef.current = restored.data.application_id;
          setCorrelationId(restored.requestId ?? null);
          setPhase("applied");
          writeRecovery({
            artifactId: restoredArtifact.id,
            artifactSha256: restoredArtifact.sha256,
            bundleKey: restored.data.bundle_key,
            bundleVersion: restored.data.bundle_version,
            applicationId: restored.data.application_id,
          });
          return;
        }
        const saved = readRecovery();
        if (!saved) return;
        setArtifact({ id: saved.artifactId, sha256: saved.artifactSha256 });
        setPhase("restoring");
        if (saved.applicationId) {
          setApplicationRecoveryId(saved.applicationId);
          const restored = await getSchemaDefinitionBundleApplication(config, saved.applicationId);
          if (!active) return;
          setApplication(restored.data);
          loadedApplicationIdRef.current = restored.data.application_id;
          setCorrelationId(restored.requestId ?? null);
          setPhase("applied");
          return;
        }
        const restored = await planSchemaDefinitionBundle(config, {
          artifact_id: saved.artifactId,
          artifact_sha256: saved.artifactSha256,
        });
        if (!active) return;
        setPlan(restored.data);
        setCorrelationId(restored.requestId ?? null);
        setPhase("ready");
      } catch (caught) {
        if (!active) return;
        setError(operationError(caught, "The saved format-definition state could not be restored."));
        setRoleState((current) => (current === "checking" ? "error" : current));
        setPhase("failed");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [config, requestedSelection.applicationId]);

  async function chooseFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    if (sourceLocked || busy) {
      event.target.value = "";
      return;
    }
    const generation = beginOperation();
    const files = [...(event.target.files ?? [])];
    setFileSummary(null);
    setError(null);
    setExportEvidence(null);
    if (!files.length) return;
    try {
      const summary = await inspectSchemaDefinitionBundleFiles(files);
      if (!operationIsCurrent(generation)) return;
      setFileSummary(summary);
      setPhase("empty");
    } catch (caught) {
      if (!operationIsCurrent(generation)) return;
      setError(operationError(caught, "The selected file could not be inspected."));
      event.target.value = "";
      window.setTimeout(() => fileInputRef.current?.focus(), 0);
    }
  }

  async function uploadAndPlan(): Promise<void> {
    if (!fileSummary) return;
    const sourceSummary = fileSummary;
    const generation = beginOperation();
    setError(null);
    setApplication(null);
    setApplicationRecoveryId(null);
    setPlan(null);
    setSelectedIndex(0);
    setPhase("uploading");
    try {
      const uploaded = await uploadSchemaDefinitionBundle(config, {
        file: sourceSummary.file,
        classification: sourceSummary.classification,
      });
      if (!operationIsCurrent(generation)) return;
      const artifactId = uploaded.data.available_artifact_id;
      if (!artifactId) {
        throw new Error("The upload completed without an available Artifact.");
      }
      const nextArtifact = { id: artifactId, sha256: uploaded.data.raw_asset.sha256 };
      setArtifact(nextArtifact);
      setPhase("planning");
      const planned = await planSchemaDefinitionBundle(config, {
        artifact_id: nextArtifact.id,
        artifact_sha256: nextArtifact.sha256,
      });
      if (!operationIsCurrent(generation)) return;
      setPlan(planned.data);
      setCorrelationId(planned.requestId ?? uploaded.requestId ?? null);
      setPhase("ready");
      writeRecovery({
        artifactId: nextArtifact.id,
        artifactSha256: nextArtifact.sha256,
        bundleKey: planned.data.bundle?.bundle_key ?? sourceSummary.bundleKey,
        bundleVersion: planned.data.bundle?.bundle_version ?? sourceSummary.bundleVersion,
        applicationId: null,
      });
    } catch (caught) {
      if (!operationIsCurrent(generation)) return;
      setError(operationError(caught, "The selected files could not be uploaded and compared."));
      setPhase("failed");
    }
  }

  async function planAgain(): Promise<void> {
    if (!artifact) return;
    const targetArtifact = artifact;
    const generation = beginOperation();
    setError(null);
    setConfirming(false);
    setConfirmed(false);
    setPhase("planning");
    try {
      const planned = await planSchemaDefinitionBundle(config, {
        artifact_id: targetArtifact.id,
        artifact_sha256: targetArtifact.sha256,
      });
      if (!operationIsCurrent(generation)) return;
      setPlan(planned.data);
      setSelectedIndex(0);
      setCorrelationId(planned.requestId ?? null);
      setPhase("ready");
      writeRecovery({
        artifactId: targetArtifact.id,
        artifactSha256: targetArtifact.sha256,
        bundleKey: planned.data.bundle?.bundle_key ?? null,
        bundleVersion: planned.data.bundle?.bundle_version ?? null,
        applicationId: null,
      });
    } catch (caught) {
      if (!operationIsCurrent(generation)) return;
      setError(operationError(caught, "The selected files could not be compared again."));
      setPhase("failed");
    }
  }

  async function restoreApplication(applicationId: string): Promise<void> {
    const generation = beginOperation();
    setError(null);
    setPhase("restoring");
    try {
      const restored = await getSchemaDefinitionBundleApplication(config, applicationId);
      if (!operationIsCurrent(generation)) return;
      setArtifact({
        id: restored.data.source_artifact.artifact_id,
        sha256: restored.data.source_artifact.sha256,
      });
      setApplication(restored.data);
      loadedApplicationIdRef.current = restored.data.application_id;
      setApplicationRecoveryId(applicationId);
      setCorrelationId(restored.requestId ?? null);
      setSelectedIndex(0);
      setPhase("applied");
      onNavigate?.(definitionBundleRoutePath({ applicationId: restored.data.application_id }));
    } catch (caught) {
      if (!operationIsCurrent(generation)) return;
      setError(operationError(caught, "The applied result could not be read back."));
      setPhase("failed");
    }
  }

  async function applyExactPlan(): Promise<void> {
    if (!artifact || !plan || !planApplicable || !confirmed) return;
    const targetArtifact = artifact;
    const targetPlan = plan;
    const generation = beginOperation();
    setError(null);
    setApplicationRecoveryId(null);
    setPhase("applying");
    let appliedApplicationId: string | null = null;
    try {
      const applied = await applySchemaDefinitionBundle(config, {
        artifact_id: targetArtifact.id,
        artifact_sha256: targetArtifact.sha256,
        plan_fingerprint: targetPlan.plan_fingerprint,
      });
      if (!operationIsCurrent(generation)) return;
      appliedApplicationId = applied.data.application_id;
      setApplicationRecoveryId(appliedApplicationId);
      setConfirming(false);
      writeRecovery({
        artifactId: targetArtifact.id,
        artifactSha256: targetArtifact.sha256,
        bundleKey: applied.data.bundle_key,
        bundleVersion: applied.data.bundle_version,
        applicationId: applied.data.application_id,
      });
      const readBack = await getSchemaDefinitionBundleApplication(
        config,
        applied.data.application_id,
      );
      if (!operationIsCurrent(generation)) return;
      setApplication(readBack.data);
      loadedApplicationIdRef.current = readBack.data.application_id;
      setCorrelationId(readBack.requestId ?? applied.requestId ?? null);
      setSelectedIndex(0);
      setPhase("applied");
      onNavigate?.(definitionBundleRoutePath({ applicationId: readBack.data.application_id }));
    } catch (caught) {
      if (!operationIsCurrent(generation)) return;
      if (appliedApplicationId) setApplicationRecoveryId(appliedApplicationId);
      const nextError = operationError(caught, "The format-definition changes could not be applied.");
      setError(nextError);
      setCorrelationId(nextError.correlationId);
      setConfirming(false);
      setPhase("failed");
    }
  }

  async function exportBundle(): Promise<void> {
    if (!application) return;
    const targetApplication = application;
    const generation = beginOperation();
    setError(null);
    setExporting(true);
    try {
      const exported = await downloadSchemaDefinitionBundle(
        config,
        targetApplication.bundle_key,
        targetApplication.bundle_version,
      );
      if (!operationIsCurrent(generation)) return;
      if (
        exported.application_id !== targetApplication.application_id ||
        exported.source_artifact_id !== targetApplication.source_artifact.artifact_id ||
        exported.source_artifact_sha256 !== targetApplication.source_artifact.sha256
      ) {
        throw new Error("The downloaded definition files do not match the applied source evidence.");
      }
      const objectUrl = URL.createObjectURL(exported.blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = exported.filename;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
      setExportEvidence({ sha256: exported.sha256, filename: exported.filename });
      setCorrelationId(exported.request_id ?? correlationId);
    } catch (caught) {
      if (!operationIsCurrent(generation)) return;
      setError(operationError(caught, "The applied definition files could not be downloaded."));
    } finally {
      if (operationIsCurrent(generation)) setExporting(false);
    }
  }

  function startNewBundle(openPicker = false): void {
    beginOperation();
    clearRecovery();
    setFileSummary(null);
    setArtifact(null);
    setPlan(null);
    setApplication(null);
    loadedApplicationIdRef.current = null;
    setApplicationRecoveryId(null);
    setError(null);
    setCorrelationId(null);
    setExportEvidence(null);
    setSelectedIndex(0);
    setConfirming(false);
    setConfirmed(false);
    setPhase("empty");
    onNavigate?.(definitionBundleRoutePath({ applicationId: "" }));
    if (fileInputRef.current) fileInputRef.current.value = "";
    window.setTimeout(() => {
      if (openPicker) fileInputRef.current?.click();
      else fileInputRef.current?.focus();
    }, 0);
  }

  const recoveryAction = useMemo(() => {
    if (error?.code === "CMP-CATALOG-0207" && artifact) {
      return { label: "Compare again", run: planAgain };
    }
    if (applicationRecoveryId && !application) {
      return {
        label: "Verify applied result",
        run: () => restoreApplication(applicationRecoveryId),
      };
    }
    if (application) {
      return {
        label: "Verify applied result again",
        run: () => restoreApplication(application.application_id),
      };
    }
    if (artifact) return { label: "Compare again", run: planAgain };
    if (fileSummary) return { label: "Retry change preview", run: uploadAndPlan };
    return null;
  }, [application, applicationRecoveryId, artifact, error?.code, fileSummary]);

  if (roleState === "checking") {
    return (
      <EngineeringPane className="schema-bundle-workbench" label="Format definitions" aria-busy="true">
        <header className="schema-editor-header">
          <div>
            <SemanticText semanticRole="sectionHeading">Format definitions</SemanticText>
            <p>Checking Administrator access…</p>
          </div>
        </header>
      </EngineeringPane>
    );
  }

  if (roleState === "denied") {
    return (
      <EngineeringPane className="schema-bundle-workbench" label="Format definitions">
        <header className="schema-editor-header">
          <div>
            <SemanticText semanticRole="sectionHeading">Format definitions</SemanticText>
          </div>
        </header>
        <div className="ux-notice warning" role="alert">
          <strong>Administrator access is required.</strong>
          <p>User and Reviewer roles cannot choose, review, apply, verify, or download format-definition files.</p>
        </div>
      </EngineeringPane>
    );
  }

  if (roleState === "error") {
    return (
      <EngineeringPane className="schema-bundle-workbench" label="Format definitions">
        <header className="schema-editor-header">
          <div>
            <SemanticText semanticRole="sectionHeading">Format definitions</SemanticText>
          </div>
          <button className="ux-button primary" type="button" onClick={onOpenConnection}>
            Check connection
          </button>
        </header>
        <div className="ux-notice error" role="alert">{error?.message}</div>
      </EngineeringPane>
    );
  }

  const activeStep = application
    ? 4
    : confirming || phase === "applying"
      ? 3
      : artifact || plan
        ? 2
        : 1;

  return (
    <EngineeringPane className="schema-bundle-workbench" label="Format definitions" aria-busy={phase === "restoring"}>
      <div className="schema-bundle-flow-row">
        <ol className="schema-bundle-steps" aria-label="Format definition workflow">
          <li aria-current={activeStep === 1 ? "step" : undefined}>1 Choose files</li>
          <li aria-current={activeStep === 2 ? "step" : undefined}>2 Review changes</li>
          <li aria-current={activeStep === 3 ? "step" : undefined}>3 Apply changes</li>
          <li aria-current={activeStep === 4 ? "step" : undefined}>4 Verify result</li>
        </ol>
        {(plan || application || artifact || applicationRecoveryId) && !busy ? (
          <button className="ux-button tertiary local-action" type="button" onClick={() => startNewBundle(true)}>
            Replace files
          </button>
        ) : null}
      </div>

      {error ? (
        <section className="ux-notice error schema-bundle-error" role="alert">
          <strong>{error.code === "CMP-CATALOG-0207" ? "The reviewed changes are stale." : "Action required"}</strong>
          <p>{error.message}</p>
          <dl>
            <div><dt>Location</dt><dd>{error.code === "CMP-CATALOG-0207" ? "Current Catalog snapshot" : "Format-definition operation"}</dd></div>
            <div><dt>Impact</dt><dd>{application ? "The verified result remains available." : applicationRecoveryId ? "The server applied changes, but completion is withheld until immutable verification succeeds." : "No selected changes were applied."}</dd></div>
            <div><dt>Next action</dt><dd>{recoveryAction?.label ?? "Choose valid format-definition files."}</dd></div>
          </dl>
          {recoveryAction ? (
            <button className="ux-button primary" type="button" onClick={() => void recoveryAction.run()}>
              {recoveryAction.label}
            </button>
          ) : null}
        </section>
      ) : null}

      <div className={`schema-bundle-grid ${!plan && !application && !artifact ? "source-only" : ""}`}>
        <EngineeringPane className="schema-bundle-source" label={artifact || fileSummary ? "Selected files" : "Choose files"}>
          <header>
            <SemanticText semanticRole="sectionHeading" as="h3">{artifact || fileSummary ? "Selected files" : "Choose files"}</SemanticText>
          </header>
          {!sourceLocked ? (
            <label className="ux-field schema-bundle-file-field">
              Format definition files
              <input
                ref={fileInputRef}
                className="ux-input"
                type="file"
                accept=".json,.zip,application/json,application/schema+json,application/zip,application/vnd.cmp.catalog-schema-definition-bundle+json,application/vnd.cmp.catalog-schema-source-set+json,application/vnd.cmp.catalog-schema-source-set+zip"
                multiple
                disabled={busy}
                onChange={(event) => void chooseFile(event)}
              />
            </label>
          ) : null}
          {fileSummary ? (
            <dl className="schema-bundle-summary">
              <div><dt>File</dt><dd>{fileSummary.file.name}</dd></div>
              <div><dt>File format</dt><dd>{fileSummary.sourceFormat} · {fileSummary.fileCount} file{fileSummary.fileCount === 1 ? "" : "s"}</dd></div>
              <div><dt>Definition set</dt><dd>{fileSummary.bundleKey}</dd></div>
              <div><dt>Definition version</dt><dd>{fileSummary.bundleVersion}</dd></div>
              <div><dt>Record type definitions</dt><dd>{fileSummary.schemaCount}</dd></div>
              <div><dt>Unit definitions</dt><dd>{fileSummary.unitProfileCount ?? "Server-verified"}</dd></div>
              <div><dt>Data classification</dt><dd><select className="ux-select" aria-label="Data classification" value={fileSummary.classification} disabled={sourceLocked || busy} onChange={(event) => setFileSummary((current) => current ? { ...current, classification: event.target.value as DataClassification } : current)}>{[...CLASSIFICATIONS].map((value) => <option value={value} key={value}>{value.replace("_", " ")}</option>)}</select></dd></div>
            </dl>
          ) : plan?.bundle ? (
            <dl className="schema-bundle-summary">
              <div><dt>Definition set</dt><dd>{plan.bundle.bundle_key}</dd></div>
              <div><dt>Definition version</dt><dd>{plan.bundle.bundle_version}</dd></div>
              <div><dt>Record type definitions</dt><dd>{plan.bundle.record_schema_count}</dd></div>
              <div><dt>Unit definitions</dt><dd>{plan.bundle.unit_profile_count}</dd></div>
              <div><dt>Data classification</dt><dd>{plan.bundle.scope.classification.replace("_", " ")}</dd></div>
            </dl>
          ) : application ? (
            <dl className="schema-bundle-summary">
              <div><dt>Definition set</dt><dd>{application.bundle_key}</dd></div>
              <div><dt>Definition version</dt><dd>{application.bundle_version}</dd></div>
              <div><dt>Applied</dt><dd>{new Date(application.applied_at).toLocaleString()}</dd></div>
              <div><dt>Data classification</dt><dd>{application.classification.replace("_", " ")}</dd></div>
            </dl>
          ) : (
            <p className="schema-bundle-empty">No files selected</p>
          )}
          {!plan && !application ? (
            <button
              className="ux-button primary"
              type="button"
              disabled={!fileSummary || phase === "uploading" || phase === "planning"}
              aria-busy={phase === "uploading" || phase === "planning"}
              onClick={() => void uploadAndPlan()}
            >
              {phase === "uploading" ? "Uploading files…" : phase === "planning" ? "Comparing definitions…" : "Preview changes (no write)"}
            </button>
          ) : null}
          {artifact ? (
            <details className="ux-disclosure">
              <summary>Checksum and provenance</summary>
              <dl className="schema-bundle-technical">
                <div><dt>Source ID</dt><dd>{artifact.id}</dd></div>
                <div><dt>SHA-256</dt><dd>{artifact.sha256}</dd></div>
                {correlationId ? <div><dt>Request</dt><dd>{correlationId}</dd></div> : null}
              </dl>
            </details>
          ) : null}
        </EngineeringPane>

        {plan || application || artifact ? <>
        <EngineeringPane className="schema-bundle-plan" label={application ? "Verified changes" : "Changes to review"}>
          <header>
            <div>
              <SemanticText semanticRole="sectionHeading" as="h3">{application ? "Verified changes" : "Changes to review"}</SemanticText>
              <span>
                {application
                  ? `${application.results.length} results`
                  : plan
                    ? `${plan.actions.length} changes`
                    : "No comparison"}
              </span>
            </div>
            {plan && !application ? (
              <dl className="schema-bundle-counts" aria-label="Change summary">
                <div><dt>Create</dt><dd>{plan.action_counts.create}</dd></div>
                <div><dt>Update</dt><dd>{plan.action_counts.update}</dd></div>
                <div><dt>No change</dt><dd>{plan.action_counts["no-op"]}</dd></div>
                <div className={plan.action_counts.conflict ? "blocked" : ""}><dt>Conflict</dt><dd>{plan.action_counts.conflict}</dd></div>
                <div className={plan.action_counts.error ? "blocked" : ""}><dt>Error</dt><dd>{plan.action_counts.error}</dd></div>
              </dl>
            ) : null}
          </header>
          {phase === "restoring" ? <p className="schema-bundle-loading" role="status">Restoring the last valid server result…</p> : null}
          {plan || application ? (
            <div className="schema-bundle-table-scroll" tabIndex={0} aria-label={application ? "Verified format-definition changes" : "Format-definition changes to review"}>
              <table className="ux-table schema-bundle-table">
                <thead>
                  <tr><th>Change</th><th>Definition type</th><th>Name</th><th>Current state</th></tr>
                </thead>
                <tbody>
                  {application
                    ? application.results.map((result, index) => (
                        <tr key={`${result.sequence}-${result.target_type}-${result.external_key}`} aria-selected={selectedIndex === index}>
                          <td>{dispositionLabel(result.disposition)}</td>
                          <td>{targetLabel(result.target_type)}</td>
                          <td>
                            <button
                              className="schema-bundle-row-button"
                              type="button"
                              data-bundle-row={index}
                              title={result.external_key}
                              onClick={() => setSelectedIndex(index)}
                              onKeyDown={(event) => moveRowFocus(event, index, application.results.length, setSelectedIndex)}
                            >{result.external_key}</button>
                          </td>
                          <td>{result.published ? "Published" : "Recorded"}</td>
                        </tr>
                      ))
                    : plan?.actions.map((action, index) => (
                        <tr key={`${action.sequence}-${action.target_type}-${action.external_key}`} aria-selected={selectedIndex === index}>
                          <td>{dispositionLabel(action.disposition)}</td>
                          <td>{targetLabel(action.target_type)}</td>
                          <td>
                            <button
                              className="schema-bundle-row-button"
                              type="button"
                              data-bundle-row={index}
                              title={action.external_key}
                              onClick={() => setSelectedIndex(index)}
                              onKeyDown={(event) => moveRowFocus(event, index, plan.actions.length, setSelectedIndex)}
                            >{actionDisplayName(action)}</button>
                          </td>
                          <td>{action.current ? (action.current.published ? "Published" : "Draft") : "Not present"}</td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="schema-bundle-plan-empty">No changes computed</div>
          )}
        </EngineeringPane>

        <aside className="ux-engineering-pane schema-bundle-detail" aria-label={application ? "Verified result" : confirming ? "Apply changes" : "Selected change"}>
          <header>
            <SemanticText semanticRole="sectionHeading" as="h3">{application ? "Verified result" : confirming ? "Apply changes" : "Selected change"}</SemanticText>
          </header>

          {selectedPlanAction ? (() => {
            const diagnostic = diagnosticForAction(selectedPlanAction, plan?.diagnostics ?? []);
            return (
              <div className="schema-bundle-detail-body">
                <h4>{actionDisplayName(selectedPlanAction)}</h4>
                <p className="schema-bundle-consequence">{diagnostic?.message ?? (selectedPlanAction.disposition === "no-op" ? "The current persisted definition already matches." : "A new immutable definition will be persisted only after confirmation.")}</p>
                <dl>
                  <div><dt>Change</dt><dd>{dispositionLabel(selectedPlanAction.disposition)}</dd></div>
                  <div><dt>Definition type</dt><dd>{targetLabel(selectedPlanAction.target_type)}</dd></div>
                </dl>
                <details className="ux-disclosure">
                  <summary>Technical details</summary>
                  <dl className="schema-bundle-technical">
                    <div><dt>External key</dt><dd>{selectedPlanAction.external_key}</dd></div>
                    <div><dt>Change sequence</dt><dd>{selectedPlanAction.sequence}</dd></div>
                    <div><dt>Source location</dt><dd>{diagnostic?.location ?? selectedPlanAction.parent_external_key ?? "Definition set root"}</dd></div>
                    <div><dt>Reason codes</dt><dd>{selectedPlanAction.reason_codes.join(", ") || "None"}</dd></div>
                  </dl>
                </details>
              </div>
            );
          })() : selectedResult ? (
            <div className="schema-bundle-detail-body">
              <h4>{selectedResult.external_key}</h4>
              <dl>
                <div><dt>Outcome</dt><dd>{dispositionLabel(selectedResult.disposition)}</dd></div>
                <div><dt>Definition type</dt><dd>{targetLabel(selectedResult.target_type)}</dd></div>
                <div><dt>State</dt><dd>{selectedResult.published ? "Published exact revision" : "Recorded"}</dd></div>
              </dl>
              <details className="ux-disclosure">
                <summary>Technical details</summary>
                <dl className="schema-bundle-technical">
                  <div><dt>Aggregate</dt><dd>{selectedResult.aggregate_id ?? "Not applicable"}</dd></div>
                  <div><dt>Revision</dt><dd>{selectedResult.revision_id ?? "Not applicable"}</dd></div>
                  <div><dt>Content hash</dt><dd>{selectedResult.content_hash}</dd></div>
                  <div><dt>Source schema</dt><dd>{selectedResult.source_schema_id} · {selectedResult.source_schema_version}</dd></div>
                  <div><dt>Source location</dt><dd>{selectedResult.source_pointer}</dd></div>
                </dl>
              </details>
            </div>
          ) : (
            <p className="schema-bundle-empty">No row selected</p>
          )}

          {plan && !application && plan.diagnostics.length ? (
            <details className="ux-disclosure schema-bundle-diagnostics" open={!plan.valid}>
              <summary>Technical diagnostics ({plan.diagnostics.length})</summary>
              <ul>
                {plan.diagnostics.map((diagnostic) => (
                  <li key={`${diagnostic.code}-${diagnostic.location}`}>
                    <strong>{diagnostic.code}</strong>
                    <span>{diagnostic.location}</span>
                    <p>{diagnostic.message}</p>
                    <p>Next: {diagnostic.remediation}</p>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          {plan && !application && !confirming ? (
            <footer className="schema-bundle-actions">
              {!planApplicable ? (
                <p role="status">
                  {planMigrationRequired
                    ? "Apply is blocked because current Records require an approved migration before this schema change."
                    : "Apply is blocked until the server returns a valid change preview with no conflicts or errors."}
                </p>
              ) : null}
              <button
                className={planApplicable && !error ? "ux-button primary" : "ux-button"}
                type="button"
                disabled={!planApplicable || Boolean(error) || phase === "planning"}
                onClick={() => {
                  setConfirmed(false);
                  setConfirming(true);
                }}
              >
                Apply {plan.actions.length} {plan.actions.length === 1 ? "change" : "changes"}
              </button>
            </footer>
          ) : null}

          {plan && !application && confirming ? (
            <section className="schema-bundle-confirmation" aria-labelledby="bundle-confirm-heading">
              <h4 id="bundle-confirm-heading">Apply these changes?</h4>
              <dl className="schema-bundle-summary">
                <div><dt>Definition set</dt><dd>{plan.bundle?.bundle_key}</dd></div>
                <div><dt>Definition version</dt><dd>{plan.bundle?.bundle_version}</dd></div>
                <div><dt>Changes</dt><dd>{plan.action_counts.create} create · {plan.action_counts.update} update · {plan.action_counts["no-op"]} no change</dd></div>
              </dl>
              <label className="ux-checkbox schema-bundle-confirm-check">
                <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
                I reviewed this definition version and its changes.
              </label>
              <details className="ux-disclosure">
                <summary>Technical details</summary>
                <dl className="schema-bundle-technical">
                  <div><dt>Source SHA-256</dt><dd>{plan.source_artifact.sha256}</dd></div>
                  <div><dt>Plan fingerprint</dt><dd>{plan.plan_fingerprint}</dd></div>
                </dl>
              </details>
              <footer className="ux-action-row">
                <button className="ux-button tertiary local-action" type="button" disabled={phase === "applying"} onClick={() => setConfirming(false)}>Back to changes</button>
                <button className="ux-button primary" type="button" disabled={!confirmed || phase === "applying"} aria-busy={phase === "applying"} onClick={() => void applyExactPlan()}>
                  {phase === "applying" ? "Applying changes…" : "Apply confirmed changes"}
                </button>
              </footer>
            </section>
          ) : null}

          {application ? (
            <section className="schema-bundle-completion" aria-live="polite">
              <strong>Verified immutable result</strong>
              <dl className="schema-bundle-readback-summary">
                <div><dt>Definition set</dt><dd>{application.bundle_key} {application.bundle_version}</dd></div>
                <div><dt>Applied</dt><dd>{new Date(application.applied_at).toLocaleString()}</dd></div>
                <div><dt>Results</dt><dd>{application.results.length}</dd></div>
              </dl>
              <div className="schema-bundle-completion-actions">
                <button className="ux-button primary" type="button" disabled={exporting} aria-busy={exporting} onClick={() => void exportBundle()}>
                  {exporting ? "Preparing download…" : "Download applied definition files"}
                </button>
                {onNavigate ? <button className="ux-button tertiary local-action" type="button" onClick={() => onNavigate("/materials")}>Open Materials</button> : null}
              </div>
              {exportEvidence ? (
                <p className="schema-bundle-export-status">{exportEvidence.filename} · {exportEvidence.sha256}</p>
              ) : null}
              <details className="ux-disclosure">
                <summary>Application provenance</summary>
                <dl className="schema-bundle-technical">
                  <div><dt>Application</dt><dd>{application.application_id}</dd></div>
                  <div><dt>Source ID</dt><dd>{application.source_artifact.artifact_id}</dd></div>
                  <div><dt>Source SHA-256</dt><dd>{application.source_artifact.sha256}</dd></div>
                  <div><dt>Before snapshot</dt><dd>{application.before_snapshot_fingerprint}</dd></div>
                  <div><dt>After snapshot</dt><dd>{application.after_snapshot_fingerprint}</dd></div>
                </dl>
              </details>
            </section>
          ) : null}

        </aside>
        </> : null}
      </div>
    </EngineeringPane>
  );
}
