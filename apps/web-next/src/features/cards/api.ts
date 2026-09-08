import { ApiError, requestBytes, requestJson, requestText } from "../../shared/api/http-client";

function withRevision(path: string, revisionId: string): string {
  const [base, rawQuery = ""] = path.split("?", 2);
  const params = new URLSearchParams(rawQuery);
  params.set("revision_id", revisionId);
  return `${base}?${params.toString()}`;
}

export type CardFamily =
  | "reference_elastic"
  | "linear_viscoelastic"
  | "ogden_prony"
  | "tabulated_plasticity"
  | "neutral_solver"
  | "neutral_hyperelastic"
  | "unsupported";

export interface SolverCardRow {
  id: string;
  revisionId: string;
  revisionNo: number;
  family: CardFamily;
  title: string;
  schemaId: string;
  contentSha256: string;
  cardSha256: string;
  materialId: string | null;
  materialModelId: string | null;
  materialModelRevisionId: string | null;
  neutralMaterialId: string | null;
  neutralMaterialRevisionId?: string | null;
  target: { solver: string; version: string; unit_system: string };
  solverMaterialId: number;
  exporterId: string | null;
  modelFamily: string | null;
  neutralFamily: string | null;
  unsupportedReason: string | null;
  links: { self: string; preview: string; download: string };
}

export interface SolverCardDetail {
  row: SolverCardRow;
  payload: Record<string, unknown>;
  nativeText: string | null;
}

export const cardFamilyPaths: Record<Exclude<CardFamily, "unsupported">, string> = {
  reference_elastic: "solver-cards",
  linear_viscoelastic: "linear-viscoelastic-solver-cards",
  ogden_prony: "ogden-prony-solver-cards",
  tabulated_plasticity: "elastoplastic-solver-cards",
  neutral_solver: "neutral-solver-cards",
  neutral_hyperelastic: "neutral-hyperelastic-solver-cards",
};

interface ApiIndexItem {
  solver_card_id: string;
  revision_id: string;
  revision_no: number;
  schema_id: string;
  content_sha256: string;
  card_sha256: string;
  family: CardFamily;
  title: string;
  material_id: string | null;
  material_model_id: string | null;
  material_model_revision_id: string | null;
  neutral_material_id: string | null;
  neutral_material_revision_id?: string | null;
  target: { solver: string; version: string; unit_system: string };
  solver_material_id: number;
  exporter_id: string | null;
  model_family: string | null;
  neutral_family: string | null;
  unsupported_reason: string | null;
  links: SolverCardRow["links"];
}

function mapRow(value: ApiIndexItem): SolverCardRow {
  return {
    id: value.solver_card_id,
    revisionId: value.revision_id,
    revisionNo: value.revision_no,
    family: value.family,
    title: value.title?.trim() || "이름 없는 솔버 카드",
    schemaId: value.schema_id,
    contentSha256: value.content_sha256,
    cardSha256: value.card_sha256,
    materialId: value.material_id,
    materialModelId: value.material_model_id,
    materialModelRevisionId: value.material_model_revision_id,
    neutralMaterialId: value.neutral_material_id,
    neutralMaterialRevisionId: value.neutral_material_revision_id ?? null,
    target: value.target,
    solverMaterialId: value.solver_material_id,
    exporterId: value.exporter_id,
    modelFamily: value.model_family,
    neutralFamily: value.neutral_family,
    unsupportedReason: value.unsupported_reason,
    links: value.links,
  };
}

export async function listProjectCards(signal?: AbortSignal): Promise<SolverCardRow[]> {
  const response = await requestJson<{ items: ApiIndexItem[]; total_count: number }>("/api/v1/solver-cards", { signal });
  return response.items.map(mapRow).sort((left, right) => left.title.localeCompare(right.title) || left.id.localeCompare(right.id));
}

interface ApiNeutralCard {
  solver_card_id: string;
  neutral_material_id: string;
  target: SolverCardRow["target"];
  current_revision: {
    id: string;
    revision_no?: number;
    schema_id?: string;
    content_hash?: string;
    content?: Record<string, unknown>;
  };
  links: SolverCardRow["links"];
}

export async function listNeutralMaterialCards(neutralMaterialId: string, signal?: AbortSignal): Promise<SolverCardRow[]> {
  const response = await requestJson<{ items: ApiNeutralCard[] }>(`/api/v1/neutral-materials/${encodeURIComponent(neutralMaterialId)}/solver-cards`, { signal });
  return response.items.map((item) => {
    const content = item.current_revision.content ?? {};
    const exporter = typeof content.exporter === "object" && content.exporter !== null ? content.exporter as { id?: unknown } : undefined;
    return {
      id: item.solver_card_id,
      revisionId: item.current_revision.id,
      revisionNo: item.current_revision.revision_no ?? 0,
      family: "neutral_solver",
      title: typeof content.material_name === "string" ? content.material_name : "Neutral Solver Card",
      schemaId: item.current_revision.schema_id ?? "urn:cmp:exporting:neutral-family-card:2.0.0",
      contentSha256: item.current_revision.content_hash ?? "",
      cardSha256: typeof content.card_sha256 === "string" ? content.card_sha256 : "",
      materialId: null,
      materialModelId: null,
      materialModelRevisionId: null,
      neutralMaterialId: item.neutral_material_id,
      neutralMaterialRevisionId: typeof content.neutral_material_revision_id === "string" ? content.neutral_material_revision_id : null,
      target: item.target,
      solverMaterialId: typeof content.solver_material_id === "number" ? content.solver_material_id : 0,
      exporterId: typeof exporter?.id === "string" ? exporter.id : null,
      modelFamily: null,
      neutralFamily: typeof content.family === "string" ? content.family : typeof content.model_family === "string" ? content.model_family : null,
      unsupportedReason: null,
      links: item.links,
    } satisfies SolverCardRow;
  }).sort((left, right) => left.title.localeCompare(right.title) || left.id.localeCompare(right.id));
}

function exactRowFromPayload(
  row: SolverCardRow,
  payload: Record<string, unknown>,
  revisionId: string,
): SolverCardRow {
  if (String(payload.solver_card_id ?? "") !== row.id) {
    throw new ApiError(409, "CARD_IDENTITY_MISMATCH", "The Solver Card response is not the selected card aggregate.");
  }
  const current = payload.current_revision as { id?: string; aggregate_id?: string; revision_no?: number; schema_id?: string; content_hash?: string; content?: Record<string, unknown> } | undefined;
  if (!current?.id || current.id !== revisionId) {
    throw new ApiError(409, "CARD_REVISION_MISMATCH", "The Solver Card response is not the pinned revision.");
  }
  if (current.aggregate_id && current.aggregate_id !== row.id) {
    throw new ApiError(409, "CARD_IDENTITY_MISMATCH", "The Solver Card revision belongs to another aggregate.");
  }
  if (!current.content_hash) {
    throw new ApiError(409, "CARD_CONTENT_HASH_MISSING", "The Solver Card revision did not return its content hash.");
  }
  if (row.contentSha256 && row.contentSha256 !== current.content_hash) {
    throw new ApiError(409, "CARD_CONTENT_HASH_MISMATCH", "The Solver Card revision content hash differs from the indexed identity.");
  }
  const currentCardSha = typeof current.content?.card_sha256 === "string" ? current.content.card_sha256 : null;
  if (!currentCardSha) {
    throw new ApiError(409, "CARD_ARTIFACT_HASH_MISSING", "The Solver Card revision did not return its native artifact hash.");
  }
  if (row.cardSha256 && row.cardSha256 !== currentCardSha) {
    throw new ApiError(409, "CARD_ARTIFACT_HASH_MISMATCH", "The Solver Card native artifact hash differs from the indexed identity.");
  }
  const content = current.content ?? {};
  const target = typeof content.target === "object" && content.target !== null ? content.target as SolverCardRow["target"] : row.target;
  const title = typeof content.card_title === "string" ? content.card_title : typeof content.material_name === "string" ? content.material_name : row.title;
  const materialModelId = typeof content.material_model_id === "string" ? content.material_model_id : row.materialModelId;
  const materialModelRevisionId = typeof content.material_model_revision_id === "string" ? content.material_model_revision_id : row.materialModelRevisionId;
  const neutralMaterialId = typeof content.neutral_material_id === "string" ? content.neutral_material_id : row.neutralMaterialId;
  const neutralMaterialRevisionId = typeof content.neutral_material_revision_id === "string" ? content.neutral_material_revision_id : row.neutralMaterialRevisionId;
  return row.revisionId === revisionId ? { ...row, title, target, materialModelId, materialModelRevisionId, neutralMaterialId, neutralMaterialRevisionId } : {
    ...row,
    revisionId,
    title,
    revisionNo: current.revision_no ?? row.revisionNo,
    schemaId: current.schema_id ?? row.schemaId,
    contentSha256: current.content_hash,
    cardSha256: currentCardSha,
    target,
    materialModelId,
    materialModelRevisionId,
    neutralMaterialId,
    neutralMaterialRevisionId,
    links: {
      self: withRevision(row.links.self, revisionId),
      preview: withRevision(row.links.preview, revisionId),
      download: withRevision(row.links.download, revisionId),
    },
  };
}

async function readExact(row: SolverCardRow, signal: AbortSignal | undefined, revisionId: string): Promise<SolverCardDetail> {
  const payload = await requestJson<Record<string, unknown>>(withRevision(row.links.self, revisionId), { signal });
  const exactRow = exactRowFromPayload(row, payload, revisionId);
  let nativeText: string | null = null;
  try {
    nativeText = (await requestText(withRevision(row.links.preview, revisionId), { signal })).text;
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 404)) throw error;
  }
  return {
    row: exactRow,
    payload,
    nativeText,
  };
}

export async function readCard(row: SolverCardRow, signal?: AbortSignal, revisionId = row.revisionId): Promise<SolverCardDetail> {
  return readExact(row, signal, revisionId);
}

export async function readCardByIdentity(
  id: string,
  revisionId: string,
  family: Exclude<CardFamily, "unsupported">,
  signal?: AbortSignal,
): Promise<SolverCardDetail> {
  const root = `/api/v1/${cardFamilyPaths[family]}/${id}`;
  const payload = await requestJson<Record<string, unknown>>(withRevision(root, revisionId), { signal });
  const current = payload.current_revision as { revision_no?: number; schema_id?: string; content_hash?: string; content?: Record<string, unknown> } | undefined;
  const content = current?.content ?? {};
  const row: SolverCardRow = {
    id,
    revisionId,
    revisionNo: current?.revision_no ?? 0,
    family,
    title: typeof content.card_title === "string" ? content.card_title : "Solver Card",
    schemaId: current?.schema_id ?? "unknown",
    contentSha256: current?.content_hash ?? "",
    cardSha256: typeof content.card_sha256 === "string" ? content.card_sha256 : "",
    materialId: typeof content.material_id === "string" ? content.material_id : null,
    materialModelId: typeof content.material_model_id === "string" ? content.material_model_id : null,
    materialModelRevisionId: typeof content.material_model_revision_id === "string" ? content.material_model_revision_id : null,
    neutralMaterialId: typeof content.neutral_material_id === "string" ? content.neutral_material_id : null,
    neutralMaterialRevisionId: typeof content.neutral_material_revision_id === "string" ? content.neutral_material_revision_id : null,
    target: typeof content.target === "object" && content.target !== null ? content.target as SolverCardRow["target"] : { solver: "unknown", version: "unknown", unit_system: "unknown" },
    solverMaterialId: typeof content.solver_material_id === "number" ? content.solver_material_id : 0,
    exporterId: typeof content.exporter_id === "string" ? content.exporter_id : null,
    modelFamily: null,
    neutralFamily: typeof content.family === "string" ? content.family : typeof content.model_family === "string" ? content.model_family : null,
    unsupportedReason: null,
    links: { self: root, preview: `${root}/preview`, download: `${root}/download` },
  };
  return readExact(row, signal, revisionId);
}

export async function downloadCard(row: SolverCardRow, signal?: AbortSignal, revisionId = row.revisionId) {
  return requestBytes(withRevision(row.links.download, revisionId), { signal });
}
