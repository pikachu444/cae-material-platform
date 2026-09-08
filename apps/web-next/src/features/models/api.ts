import { ApiError, requestJson } from "../../shared/api/http-client";
import type { RevisionPin } from "../test-data/api";
import type { MaterialDetail } from "../materials/api";

export interface MaterialModelRow {
  id: string;
  stateId: string;
  stateRevisionId: string | null;
  revisionId: string;
  family: string;
  schemaId: string;
  content: Record<string, unknown>;
  ir: Record<string, unknown>;
  resourcePath: string;
  createdAt?: string;
}

export interface ProcessingOutputRelation {
  id: string;
  revisionId: string;
}

interface ApiModel {
  material_model_id: string;
  material_state_id: string;
  current_revision: RevisionPin & {
    content?: Record<string, unknown>;
    ir?: Record<string, unknown>;
  };
}

function mapModel(value: ApiModel, resourcePath: string): MaterialModelRow {
  const content = value.current_revision.content ?? {};
  const family = String(content.model_family_id ?? content.family ?? value.current_revision.schema_id ?? "reference");
  return {
    id: value.material_model_id,
    stateId: value.material_state_id,
    stateRevisionId: typeof content.material_state_revision_id === "string" ? content.material_state_revision_id : null,
    revisionId: value.current_revision.id,
    family,
    schemaId: value.current_revision.schema_id,
    content,
    ir: value.current_revision.ir ?? {},
    resourcePath,
    createdAt: value.current_revision.created_at,
  };
}

export async function listModelsForState(stateId: string, signal?: AbortSignal): Promise<MaterialModelRow[]> {
  const resources = [
    "material-models",
    "linear-viscoelastic-models",
    "ogden-prony-models",
    "tabulated-plasticity-models",
  ];
  const responses = await Promise.all(resources.map(async (resource) => {
    try {
      return [resource, await requestJson<{ items: ApiModel[] }>(`/api/v1/material-states/${stateId}/${resource}`, { signal })] as const;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return [resource, { items: [] }] as const;
      throw error;
    }
  }));
  return responses.flatMap(([resource, response]) => response.items.map((item) => mapModel(item, resource)));
}

export async function listModelsForMaterials(materials: MaterialDetail[], signal?: AbortSignal): Promise<MaterialModelRow[]> {
  const values = await Promise.all(materials.flatMap((material) => material.states.map((state) => listModelsForState(state.id, signal))));
  const byId = new Map<string, MaterialModelRow>();
  for (const row of values.flat()) byId.set(row.id, row);
  return [...byId.values()].sort((left, right) => left.family.localeCompare(right.family) || left.id.localeCompare(right.id));
}

export async function readMaterialModel(id: string, signal?: AbortSignal, resourcePath = "material-models", revisionId?: string): Promise<MaterialModelRow> {
  const response = await requestJson<ApiModel>(`/api/v1/${resourcePath}/${id}${revisionId ? `?revision_id=${encodeURIComponent(revisionId)}` : ""}`, { signal });
  if (response.material_model_id !== id || (revisionId && response.current_revision.id !== revisionId)) {
    throw new ApiError(409, "MODEL_REVISION_MISMATCH", "The Material Model response is not the pinned model revision.");
  }
  return mapModel(response, resourcePath);
}

export function modelProcessingRelation(row: MaterialModelRow): ProcessingOutputRelation | null {
  const contentProjection = row.content.processing_projection;
  if (typeof contentProjection === "object" && contentProjection !== null) {
    const value = contentProjection as { output_id?: unknown; output_revision_id?: unknown };
    if (typeof value.output_id === "string" && typeof value.output_revision_id === "string") return { id: value.output_id, revisionId: value.output_revision_id };
  }
  const sourceRevisions = row.ir.source_revisions;
  if (typeof sourceRevisions === "object" && sourceRevisions !== null) {
    const value = (sourceRevisions as { processing_output?: unknown }).processing_output;
    if (typeof value === "object" && value !== null) {
      const source = value as { id?: unknown; revision_id?: unknown };
      if (typeof source.id === "string" && typeof source.revision_id === "string") return { id: source.id, revisionId: source.revision_id };
    }
  }
  return null;
}
