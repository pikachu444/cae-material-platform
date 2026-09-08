import { ApiError, requestJson, requestSemanticJson } from "../../shared/api/http-client";

export interface NeutralReference {
  id: string;
  revisionId: string;
}

export interface NeutralMaterialDocument {
  document_type?: string;
  document_id?: string;
  content_sha256?: string;
  sources?: {
    material?: NeutralReference;
    material_state?: NeutralReference;
    datasets?: Array<{ dataset?: NeutralReference; role?: string; test_mode?: string }>;
  };
  candidate_selection?: {
    processing_output?: NeutralReference;
    selected_series?: string;
    primary_family?: string;
    secondary_family?: string;
    primary_weight?: number;
  };
  material_model_ir?: {
    model?: NeutralReference;
    model_family?: string;
    schema_id?: string;
    density?: { value?: number; unit?: string };
    prony_overlay?: { terms?: unknown };
    constitutive_model?: {
      prony_terms?: unknown;
      parameters?: Record<string, { value?: number; unit?: string }>;
      selection?: { primary_family?: string; secondary_family?: string; primary_weight?: number };
    };
  };
}

export interface NeutralMaterialRead {
  id: string;
  revisionId: string;
  materialId: string | null;
  semanticSha256: string;
  document: NeutralMaterialDocument;
  candidate: {
    artifactId: string | null;
    sourceSha256: string | null;
    label: string;
  };
  sourceOutput: NeutralReference | null;
  sourceTestData: NeutralReference | null;
}

export interface NeutralCandidate {
  kind?: string;
  artifact_id?: string | null;
  neutral_material_id?: string | null;
  neutral_material_revision_id?: string | null;
  source_sha256?: string | null;
  label?: string;
}

interface ExportCandidate {
  source?: NeutralCandidate;
  artifact_id?: string | null;
  source_sha256?: string | null;
  label?: string | null;
}

function normalizeHash(value: string | null | undefined): string | null {
  return value ? value.replace(/^sha256:/i, "").toLowerCase() : null;
}

function reference(value: unknown): NeutralReference | null {
  if (!value || typeof value !== "object") return null;
  const item = value as { id?: unknown; revision_id?: unknown };
  return typeof item.id === "string" && typeof item.revision_id === "string"
    ? { id: item.id, revisionId: item.revision_id }
    : null;
}

/**
 * Resolve and validate one exact neutral revision. The candidate source pins
 * the selected model; the download contract pins the canonical document's
 * semantic hash. Raw HTTP response bytes are intentionally not hashed here.
 */
export async function readExactNeutralMaterial(
  materialId: string | undefined,
  neutralId: string,
  revisionId: string,
  signal?: AbortSignal,
): Promise<NeutralMaterialRead> {
  // Candidate discovery is a useful optional relation, but it is not required
  // to read an exact neutral document from a card deep link. The download
  // endpoint is the authoritative identity and semantic-hash contract.
  let candidate: NeutralCandidate | undefined;
  if (materialId) {
    try {
      candidate = (await listNeutralCandidates(materialId, signal)).find((source) => source.neutral_material_id === neutralId && source.neutral_material_revision_id === revisionId);
    } catch {
      candidate = undefined;
    }
  }

  const downloaded = await requestSemanticJson<NeutralMaterialDocument>(
    `/api/v1/neutral-materials/${encodeURIComponent(neutralId)}/revisions/${encodeURIComponent(revisionId)}/download`,
    { signal },
  );
  const headerId = downloaded.headers.get("X-Neutral-Material-ID");
  const headerRevisionId = downloaded.headers.get("X-Neutral-Material-Revision-ID");
  if (headerId !== neutralId || headerRevisionId !== revisionId) {
    throw new ApiError(409, "NEUTRAL_REVISION_MISMATCH", "The Neutral Material response is not the requested revision.");
  }
  const document = downloaded.value;
  if (document.document_id !== neutralId) {
    throw new ApiError(409, "NEUTRAL_DOCUMENT_IDENTITY_MISMATCH", "The Neutral Material document does not match the selected identity.");
  }
  const modelRef = reference(document.material_model_ir?.model);
  if (!modelRef || modelRef.id !== neutralId || modelRef.revisionId !== revisionId) {
    throw new ApiError(409, "NEUTRAL_MODEL_IDENTITY_MISMATCH", "The Neutral Material model reference does not match the selected revision.");
  }
  const documentHash = normalizeHash(document.content_sha256);
  if (!documentHash || documentHash !== downloaded.semanticSha256) {
    throw new ApiError(409, "NEUTRAL_DOCUMENT_HASH_MISMATCH", "The Neutral Material semantic document hash does not match the response header.");
  }

  const sourceOutput = reference(document.candidate_selection?.processing_output);
  const sourceTestData = document.sources?.datasets?.find((item) => item.role === "processing_input")?.dataset;
  const sourceMaterial = reference(document.sources?.material);
  if (materialId && sourceMaterial && sourceMaterial.id !== materialId) {
    throw new ApiError(409, "NEUTRAL_SOURCE_MATERIAL_MISMATCH", "The Neutral Material source does not match the requested Material relation.");
  }
  const normalizedDocument: NeutralMaterialDocument = {
    ...document,
    sources: document.sources ? {
      ...document.sources,
      material: reference(document.sources.material) ?? undefined,
      material_state: reference(document.sources.material_state) ?? undefined,
    } : document.sources,
  };
  return {
    id: neutralId,
    revisionId,
    materialId: sourceMaterial?.id ?? materialId ?? null,
    semanticSha256: downloaded.semanticSha256,
    document: normalizedDocument,
    candidate: {
      artifactId: candidate?.artifact_id ?? null,
      sourceSha256: normalizeHash(candidate?.source_sha256),
      label: candidate?.label ?? "Neutral Material JSON",
    },
    sourceOutput,
    sourceTestData: reference(sourceTestData),
  };
}

export async function listNeutralCandidates(materialId: string, signal?: AbortSignal): Promise<NeutralCandidate[]> {
  const candidates = await requestJson<{ items: ExportCandidate[] }>(
    `/api/v1/bulk-export-candidates?material_id=${encodeURIComponent(materialId)}`,
    { signal },
  );
  return candidates.items
    .map((item): NeutralCandidate | null => item.source ? {
      ...item.source,
      artifact_id: item.artifact_id ?? item.source.artifact_id,
      source_sha256: item.source_sha256 ?? item.source.source_sha256,
      label: item.label ?? item.source.label,
    } : null)
    .filter((source): source is NeutralCandidate => source?.kind === "neutral_material_json");
}
