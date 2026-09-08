import { queryString, requestJson } from "../../shared/api/http-client";
import type { RevisionPin } from "../test-data/api";

export interface MaterialRow {
  id: string;
  revisionId: string;
  revision: RevisionPin;
  name: string;
  code: string;
  family: string;
  description: string | null;
  materialClass: string;
}

export interface MaterialStateRow {
  id: string;
  materialId: string;
  revisionId: string;
  name: string;
  stateCode?: string;
  status?: string;
}

export interface MaterialPropertySet {
  id: string;
  stateId: string;
  revisionId: string;
  content: Record<string, unknown>;
}

export interface MaterialDetail {
  material: MaterialRow;
  states: MaterialStateRow[];
  propertySets: MaterialPropertySet[];
}

interface ApiMaterial {
  material_id: string;
  current_revision: RevisionPin & { content?: { name?: string; material_code?: string; material_family?: string; description?: string | null; material_class?: string } };
}
interface ApiMaterialList { items: ApiMaterial[]; total_count: number; offset: number; limit: number; facets?: unknown }
interface ApiMaterialState {
  material_state_id: string;
  material_id: string;
  current_revision: RevisionPin & { content?: { name?: string; state_code?: string; status?: string } };
}

function mapMaterial(value: ApiMaterial): MaterialRow {
  const content = value.current_revision.content ?? {};
  return {
    id: value.material_id,
    revisionId: value.current_revision.id,
    revision: value.current_revision,
    name: content.name?.trim() || "이름 없는 소재",
    code: content.material_code ?? "",
    family: content.material_family ?? "",
    description: content.description ?? null,
    materialClass: content.material_class ?? "unknown",
  };
}

export interface MaterialListOptions {
  query?: string;
  materialClass?: string;
  offset?: number;
  limit?: number;
  sortBy?: "name" | "material_class";
  sortDirection?: "ascending" | "descending";
}

export interface MaterialListPage {
  items: MaterialRow[];
  totalCount: number;
  offset: number;
  limit: number;
  facets: Array<{ materialClass: string; count: number }>;
}

export async function listMaterials(options: MaterialListOptions = {}, signal?: AbortSignal): Promise<MaterialListPage> {
  const response = await requestJson<ApiMaterialList & { facets?: { material_classes?: Array<{ material_class: string; count: number }> } }>(`/api/v1/materials${queryString({
    q: options.query,
    material_class: options.materialClass,
    offset: String(options.offset ?? 0),
    limit: String(options.limit ?? 12),
    sort_by: options.sortBy ?? "name",
    sort_direction: options.sortDirection ?? "ascending",
  })}`, { signal });
  return {
    items: response.items.map(mapMaterial),
    totalCount: response.total_count,
    offset: response.offset,
    limit: response.limit,
    facets: (response.facets?.material_classes ?? []).map((item) => ({ materialClass: item.material_class, count: item.count })),
  };
}

export async function listAllMaterials(signal?: AbortSignal): Promise<MaterialRow[]> {
  const first = await listMaterials({ offset: 0, limit: 100 }, signal);
  const pages = [first];
  for (let offset = first.items.length; offset < first.totalCount; offset += first.limit) {
    pages.push(await listMaterials({ offset, limit: first.limit }, signal));
  }
  return pages.flatMap((page) => page.items);
}

function mapState(value: { material_state_id: string; material_id: string; current_revision: RevisionPin & { content?: { name?: string; state_code?: string; status?: string } } }): MaterialStateRow {
  return {
    id: value.material_state_id,
    materialId: value.material_id,
    revisionId: value.current_revision.id,
    name: value.current_revision.content?.name?.trim() || "이름 없는 소재 상태",
    stateCode: value.current_revision.content?.state_code,
    status: value.current_revision.content?.status,
  };
}

export async function readMaterial(id: string, signal?: AbortSignal): Promise<MaterialDetail> {
  const response = await requestJson<{
    material: ApiMaterial;
    states: ApiMaterialState[];
    property_sets: Array<{ property_set_id: string; material_state_id: string; current_revision: RevisionPin & { content?: Record<string, unknown> } }>;
  }>(`/api/v1/materials/${id}`, { signal });
  return {
    material: mapMaterial(response.material),
    states: response.states.map(mapState),
    propertySets: response.property_sets.map((item) => ({
      id: item.property_set_id,
      stateId: item.material_state_id,
      revisionId: item.current_revision.id,
      content: item.current_revision.content ?? {},
    })),
  };
}
