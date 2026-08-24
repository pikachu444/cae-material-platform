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
} from "./api";
import { publishWorkspaceStatus } from "../../../design/application-shell";
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
      throw new Error("The source-set envelope manifest is not a source-v2 bundle.");
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
    throw new Error("Choose a JSON bundle with a safe, non-empty filename.");
  }
  if (!filename.toLowerCase().endsWith(".json") || !ACCEPTED_MEDIA_TYPES.has(file.type)) {
    throw new Error("Choose a JSON Schema Definition Bundle file (.json).");
  }
  if (file.size < 1) {
    throw new Error("The definition bundle is empty.");
  }
  if (file.size > MAX_BUNDLE_BYTES) {
    throw new Error("The definition bundle is larger than 64 MiB.");
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
      "The JSON is not a version 1.0.0 Schema Definition Bundle with a scope, catalog, and at least one record schema.",
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
    bundle: "Bundle",
    database: "Database",
    profile: "Profile",
    table: "Table",
    attribute: "Attribute",
    layout: "Layout",
    profile_table_placement: "Table placement",
    link_type: "Link Type",
  }[value];
}

function dispositionLabel(value: SchemaDefinitionBundlePlanAction["disposition"]): string {
  return value === "no-op" ? "No change" : `${value[0]?.toUpperCase()}${value.slice(1)}`;
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
          : "Definition bundles",
      revision: application ? "Applied bundle" : plan ? "Plan not applied" : "No bundle selected",
      jobs:
        phase === "uploading" || phase === "planning" || phase === "applying" || phase === "restoring"
          ? "Operation in progress"
          : "No active job",
      warnings: error ? "1 action required" : plan && !planApplicable ? "Plan blocked" : "0 validation errors",
      connection: roleState === "error" ? "degraded" : "online",
    });
  }, [application, error, phase, plan, planApplicable, roleState]);

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
        setError(operationError(caught, "The saved bundle state could not be restored."));
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
      setError(operationError(caught, "The bundle could not be uploaded and planned."));
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
      setError(operationError(caught, "The bundle could not be planned again."));
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
      const nextError = operationError(caught, "The bundle could not be applied.");
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
        throw new Error("The exported bundle does not match the applied source evidence.");
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
      setError(operationError(caught, "The applied bundle could not be exported."));
    } finally {
      if (operationIsCurrent(generation)) setExporting(false);
    }
  }

  function startNewBundle(): void {
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
    window.setTimeout(() => fileInputRef.current?.focus(), 0);
  }

  const recoveryAction = useMemo(() => {
    if (error?.code === "CMP-CATALOG-0207" && artifact) {
      return { label: "Plan again", run: planAgain };
    }
    if (applicationRecoveryId && !application) {
      return {
        label: "Read applied result",
        run: () => restoreApplication(applicationRecoveryId),
      };
    }
    if (application) {
      return {
        label: "Restore applied result",
        run: () => restoreApplication(application.application_id),
      };
    }
    if (artifact) return { label: "Plan again", run: planAgain };
    if (fileSummary) return { label: "Retry upload and plan", run: uploadAndPlan };
    return null;
  }, [application, applicationRecoveryId, artifact, error?.code, fileSummary]);

  if (roleState === "checking") {
    return (
      <section className="schema-bundle-workbench" aria-busy="true">
        <header className="schema-editor-header">
          <div>
            <h2>Format definitions</h2>
            <p>Checking Administrator access…</p>
          </div>
        </header>
      </section>
    );
  }

  if (roleState === "denied") {
    return (
      <section className="schema-bundle-workbench">
        <header className="schema-editor-header">
          <div>
            <h2>Format definitions</h2>
          </div>
        </header>
        <div className="ux-notice warning" role="alert">
          <strong>Administrator access is required.</strong>
          <p>User and Reviewer roles cannot upload, plan, apply, read back, or export definition bundles.</p>
        </div>
      </section>
    );
  }

  if (roleState === "error") {
    return (
      <section className="schema-bundle-workbench">
        <header className="schema-editor-header">
          <div>
            <h2>Format definitions</h2>
          </div>
          <button className="ux-button primary" type="button" onClick={onOpenConnection}>
            Check connection
          </button>
        </header>
        <div className="ux-notice error" role="alert">{error?.message}</div>
      </section>
    );
  }

  return (
    <section className="schema-bundle-workbench" aria-busy={phase === "restoring"}>
      <div className="schema-bundle-flow-row">
        <ol className="schema-bundle-steps" aria-label="Format definition workflow">
          <li aria-current={!artifact && !application ? "step" : undefined}>Select</li>
          <li aria-current={artifact && !plan && !application ? "step" : undefined}>Plan</li>
          <li aria-current={plan && !application ? "step" : undefined}>Apply</li>
          <li aria-current={application ? "step" : undefined}>Read back</li>
        </ol>
        {(plan || application || artifact || applicationRecoveryId) && !busy ? (
          <button className="ux-button" type="button" onClick={startNewBundle}>
            New bundle
          </button>
        ) : null}
      </div>

      {error ? (
        <section className="ux-notice error schema-bundle-error" role="alert">
          <strong>{error.code === "CMP-CATALOG-0207" ? "The approved plan is stale." : "Action required"}</strong>
          <p>{error.message}</p>
          <dl>
            <div><dt>Location</dt><dd>{error.code === "CMP-CATALOG-0207" ? "Current Catalog snapshot" : "Bundle operation"}</dd></div>
            <div><dt>Impact</dt><dd>{application ? "The saved application remains available." : applicationRecoveryId ? "Apply returned an application, but success is withheld until immutable read-back completes." : "No client plan actions were applied."}</dd></div>
            <div><dt>Next action</dt><dd>{recoveryAction?.label ?? "Choose a valid bundle file."}</dd></div>
          </dl>
          {recoveryAction ? (
            <button className="ux-button primary" type="button" onClick={() => void recoveryAction.run()}>
              {recoveryAction.label}
            </button>
          ) : null}
        </section>
      ) : null}

      <div className={`schema-bundle-grid ${!plan && !application && !artifact ? "source-only" : ""}`}>
        <section className="schema-bundle-source" aria-labelledby="bundle-source-heading">
          <header>
            <h3 id="bundle-source-heading">Select source</h3>
            <span>{artifact ? "Verified source" : fileSummary?.sourceFormat ?? "JSON files or ZIP"}</span>
          </header>
          <label className="schema-bundle-file-field">
            Definition bundle
            <input
              ref={fileInputRef}
              className="ux-input"
              type="file"
              accept=".json,.zip,application/json,application/schema+json,application/zip,application/vnd.cmp.catalog-schema-definition-bundle+json,application/vnd.cmp.catalog-schema-source-set+json,application/vnd.cmp.catalog-schema-source-set+zip"
              multiple
              disabled={busy || sourceLocked}
              onChange={(event) => void chooseFile(event)}
            />
          </label>
          {fileSummary ? (
            <dl className="schema-bundle-summary">
              <div><dt>File</dt><dd>{fileSummary.file.name}</dd></div>
              <div><dt>Source</dt><dd>{fileSummary.sourceFormat} · {fileSummary.fileCount} file{fileSummary.fileCount === 1 ? "" : "s"}</dd></div>
              <div><dt>Bundle</dt><dd>{fileSummary.bundleKey}</dd></div>
              <div><dt>Version</dt><dd>{fileSummary.bundleVersion}</dd></div>
              <div><dt>Record schemas</dt><dd>{fileSummary.schemaCount}</dd></div>
              <div><dt>Unit profiles</dt><dd>{fileSummary.unitProfileCount ?? "Server-verified"}</dd></div>
              <div><dt>Classification</dt><dd><select aria-label="Source classification" value={fileSummary.classification} disabled={sourceLocked || busy} onChange={(event) => setFileSummary((current) => current ? { ...current, classification: event.target.value as DataClassification } : current)}>{[...CLASSIFICATIONS].map((value) => <option value={value} key={value}>{value.replace("_", " ")}</option>)}</select></dd></div>
            </dl>
          ) : plan?.bundle ? (
            <dl className="schema-bundle-summary">
              <div><dt>Bundle</dt><dd>{plan.bundle.bundle_key}</dd></div>
              <div><dt>Version</dt><dd>{plan.bundle.bundle_version}</dd></div>
              <div><dt>Record schemas</dt><dd>{plan.bundle.record_schema_count}</dd></div>
              <div><dt>Unit profiles</dt><dd>{plan.bundle.unit_profile_count}</dd></div>
              <div><dt>Classification</dt><dd>{plan.bundle.scope.classification.replace("_", " ")}</dd></div>
            </dl>
          ) : application ? (
            <dl className="schema-bundle-summary">
              <div><dt>Bundle</dt><dd>{application.bundle_key}</dd></div>
              <div><dt>Version</dt><dd>{application.bundle_version}</dd></div>
              <div><dt>Applied</dt><dd>{new Date(application.applied_at).toLocaleString()}</dd></div>
              <div><dt>Classification</dt><dd>{application.classification.replace("_", " ")}</dd></div>
            </dl>
          ) : (
            <p className="schema-bundle-empty">No source selected</p>
          )}
          {!plan && !application ? (
            <button
              className="ux-button primary"
              type="button"
              disabled={!fileSummary || phase === "uploading" || phase === "planning"}
              aria-busy={phase === "uploading" || phase === "planning"}
              onClick={() => void uploadAndPlan()}
            >
              {phase === "uploading" ? "Uploading…" : phase === "planning" ? "Planning…" : "Upload and plan"}
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
        </section>

        {plan || application || artifact ? <>
        <section className="schema-bundle-plan" aria-labelledby="bundle-plan-heading">
          <header>
            <div>
              <h3 id="bundle-plan-heading">{application ? "Read-back results" : "Change plan"}</h3>
              <span>
                {application
                  ? `${application.results.length} results`
                  : plan
                    ? `${plan.actions.length} actions`
                    : "No plan"}
              </span>
            </div>
            {plan && !application ? (
              <div className="schema-bundle-counts" aria-label="Plan counts">
                <span>Create {plan.action_counts.create}</span>
                <span>Update {plan.action_counts.update}</span>
                <span>No change {plan.action_counts["no-op"]}</span>
                <span className={plan.action_counts.conflict ? "blocked" : ""}>Conflict {plan.action_counts.conflict}</span>
                <span className={plan.action_counts.error ? "blocked" : ""}>Error {plan.action_counts.error}</span>
              </div>
            ) : null}
          </header>
          {phase === "restoring" ? <p className="schema-bundle-loading" role="status">Restoring the last valid server result…</p> : null}
          {plan || application ? (
            <div className="schema-bundle-table-scroll" tabIndex={0} aria-label={application ? "Applied bundle results" : "Bundle plan actions"}>
              <table className="ux-table schema-bundle-table">
                <thead>
                  <tr><th>Action</th><th>Object</th><th>Target</th><th>State</th></tr>
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
                            >{action.external_key}</button>
                          </td>
                          <td>{action.current ? (action.current.published ? "Published" : "Draft") : "Not present"}</td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="schema-bundle-plan-empty">No plan generated</div>
          )}
        </section>

        <aside className="schema-bundle-detail" aria-labelledby="bundle-detail-heading">
          <header>
            <h3 id="bundle-detail-heading">{application ? "Exact read-back" : confirming ? "Apply" : "Plan details"}</h3>
            <span>{selectedPlanAction ? `Action ${selectedPlanAction.sequence}` : selectedResult ? `Result ${selectedResult.sequence}` : "No selection"}</span>
          </header>

          {selectedPlanAction ? (() => {
            const diagnostic = diagnosticForAction(selectedPlanAction, plan?.diagnostics ?? []);
            return (
              <div className="schema-bundle-detail-body">
                <h4>{selectedPlanAction.external_key}</h4>
                <dl>
                  <div><dt>Decision</dt><dd>{dispositionLabel(selectedPlanAction.disposition)}</dd></div>
                  <div><dt>Object</dt><dd>{targetLabel(selectedPlanAction.target_type)}</dd></div>
                  <div><dt>Location</dt><dd>{diagnostic?.location ?? selectedPlanAction.parent_external_key ?? "Bundle root"}</dd></div>
                  <div><dt>Impact</dt><dd>{diagnostic?.message ?? (selectedPlanAction.disposition === "no-op" ? "The current published definition already matches." : "The server will create a new immutable result only after confirmation.")}</dd></div>
                  <div><dt>Next action</dt><dd>{diagnostic?.remediation ?? (planApplicable ? "Review the exact plan before applying." : "Resolve every conflict or error, then plan again.")}</dd></div>
                </dl>
                {selectedPlanAction.reason_codes.length ? (
                  <p className="schema-bundle-reasons">Reason: {selectedPlanAction.reason_codes.join(", ")}</p>
                ) : null}
              </div>
            );
          })() : selectedResult ? (
            <div className="schema-bundle-detail-body">
              <h4>{selectedResult.external_key}</h4>
              <dl>
                <div><dt>Outcome</dt><dd>{dispositionLabel(selectedResult.disposition)}</dd></div>
                <div><dt>Object</dt><dd>{targetLabel(selectedResult.target_type)}</dd></div>
                <div><dt>State</dt><dd>{selectedResult.published ? "Published exact revision" : "Recorded"}</dd></div>
                <div><dt>Source location</dt><dd>{selectedResult.source_pointer}</dd></div>
              </dl>
              <details className="ux-disclosure">
                <summary>Exact revision</summary>
                <dl className="schema-bundle-technical">
                  <div><dt>Aggregate</dt><dd>{selectedResult.aggregate_id ?? "Not applicable"}</dd></div>
                  <div><dt>Revision</dt><dd>{selectedResult.revision_id ?? "Not applicable"}</dd></div>
                  <div><dt>Content hash</dt><dd>{selectedResult.content_hash}</dd></div>
                  <div><dt>Source schema</dt><dd>{selectedResult.source_schema_id} · {selectedResult.source_schema_version}</dd></div>
                </dl>
              </details>
            </div>
          ) : (
            <p className="schema-bundle-empty">No row selected</p>
          )}

          {plan && !application && plan.diagnostics.length ? (
            <details className="ux-disclosure schema-bundle-diagnostics" open={!plan.valid}>
              <summary>Plan diagnostics ({plan.diagnostics.length})</summary>
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
                    : "Apply is blocked until the server returns a valid plan with no conflicts or errors."}
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
                Review exact plan
              </button>
            </footer>
          ) : null}

          {plan && !application && confirming ? (
            <section className="schema-bundle-confirmation" aria-labelledby="bundle-confirm-heading">
              <h4 id="bundle-confirm-heading">Confirm the exact plan</h4>
              <dl className="schema-bundle-technical">
                <div><dt>Bundle</dt><dd>{plan.bundle?.bundle_key}</dd></div>
                <div><dt>Version</dt><dd>{plan.bundle?.bundle_version}</dd></div>
                <div><dt>Source SHA-256</dt><dd>{plan.source_artifact.sha256}</dd></div>
                <div><dt>Plan fingerprint</dt><dd>{plan.plan_fingerprint}</dd></div>
                <div><dt>Changes</dt><dd>{plan.action_counts.create} create · {plan.action_counts.update} update · {plan.action_counts["no-op"]} no change</dd></div>
              </dl>
              <label className="schema-bundle-confirm-check">
                <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
                I reviewed this exact version, checksum, and plan fingerprint.
              </label>
              <footer>
                <button className="ux-button" type="button" disabled={phase === "applying"} onClick={() => setConfirming(false)}>Back to plan</button>
                <button className="ux-button primary" type="button" disabled={!confirmed || phase === "applying"} aria-busy={phase === "applying"} onClick={() => void applyExactPlan()}>
                  {phase === "applying" ? "Applying…" : "Apply exact plan"}
                </button>
              </footer>
            </section>
          ) : null}

          {application ? (
            <section className="schema-bundle-completion" aria-live="polite">
              <strong>Exact application read back</strong>
              <dl className="schema-bundle-readback-summary">
                <div><dt>Bundle</dt><dd>{application.bundle_key} {application.bundle_version}</dd></div>
                <div><dt>Application</dt><dd>{application.application_id}</dd></div>
                <div><dt>Results</dt><dd>{application.results.length}</dd></div>
              </dl>
              <button className="ux-button primary" type="button" disabled={exporting} aria-busy={exporting} onClick={() => void exportBundle()}>
                {exporting ? "Verifying export…" : "Export verified source"}
              </button>
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
    </section>
  );
}
