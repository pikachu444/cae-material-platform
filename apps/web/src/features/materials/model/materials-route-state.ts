import type { ConfigurableLinkEndpoint } from "../../catalog/contracts";
import type { MaterialsBrowseScope } from "../../../materials-browse-tree";

export type MaterialTab =
  "overview" | "properties" | "curves" | "cards" | "evidence";
export type MaterialsNavigatorMode = "filters" | "browse" | "subsets";
export type MaterialsSortKey = "name" | "material_class";
export type MaterialsSortDirection = "ascending" | "descending";

export interface MaterialRevisionPin {
  recordId: string;
  recordRevisionId: string;
  materialRevisionId: string;
}

export interface MaterialsLocationState {
  query: string;
  materialClass: string;
  provider: string;
  evidenceSource: string;
  scope: MaterialsBrowseScope | null;
  sortKey: MaterialsSortKey;
  sortDirection: MaterialsSortDirection;
  offset: number;
  leftMode: MaterialsNavigatorMode;
  selectedId: string;
}

const MATERIALS_RETURN_KEY = "cmp.materials.return-path";
const MATERIALS_BROWSE_RECORD_KEY = "cmp.materials.browse-record";

function currentSearch(): string {
  return typeof window === "undefined" ? "" : window.location.search;
}

export function parseMaterialsLocation(
  search = currentSearch(),
): MaterialsLocationState {
  const params = new URLSearchParams(search);
  const tableId = params.get("table");
  const mode = params.get("mode");
  const sort = params.get("sort");
  return {
    query: params.get("q") ?? "",
    materialClass: params.get("family") ?? "",
    provider: params.get("provider") ?? "",
    evidenceSource: params.get("source") ?? "",
    scope: tableId
      ? {
          tableId,
          folderId: params.get("folder"),
          recordId: params.get("record"),
          includeDescendants: Boolean(params.get("folder")),
        }
      : null,
    sortKey: sort === "material_class" ? sort : "name",
    sortDirection:
      params.get("direction") === "descending" ? "descending" : "ascending",
    offset: Number(params.get("offset") ?? "0") || 0,
    leftMode: mode === "filters" || mode === "subsets" ? mode : "browse",
    selectedId: params.get("selected") ?? "",
  };
}

export function materialsPath(state: MaterialsLocationState): string {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.materialClass) params.set("family", state.materialClass);
  if (state.provider) params.set("provider", state.provider);
  if (state.evidenceSource) params.set("source", state.evidenceSource);
  if (state.scope?.tableId) params.set("table", state.scope.tableId);
  if (state.scope?.folderId) params.set("folder", state.scope.folderId);
  if (state.scope?.recordId) params.set("record", state.scope.recordId);
  if (state.sortKey !== "name") params.set("sort", state.sortKey);
  if (state.sortDirection !== "ascending")
    params.set("direction", state.sortDirection);
  if (state.leftMode !== "browse") params.set("mode", state.leftMode);
  if (state.selectedId) params.set("selected", state.selectedId);
  if (state.offset) params.set("offset", String(state.offset));
  const query = params.toString();
  return query ? `/materials?${query}` : "/materials";
}

export function exactRecordPath(recordId: string, revisionId: string): string {
  return `/materials/records/${recordId}/revisions/${revisionId}`;
}

export function storedBrowseRecord(): ConfigurableLinkEndpoint | null {
  if (typeof window === "undefined") return null;
  try {
    const value = JSON.parse(
      window.sessionStorage.getItem(MATERIALS_BROWSE_RECORD_KEY) ?? "null",
    ) as ConfigurableLinkEndpoint | null;
    return value?.record_id && value.table_id ? value : null;
  } catch {
    return null;
  }
}

export function rememberBrowseRecord(record: ConfigurableLinkEndpoint): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(
      MATERIALS_BROWSE_RECORD_KEY,
      JSON.stringify(record),
    );
  }
}

export function rememberMaterialsReturnPath(path: string): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, path);
  }
}

export function materialsReturnPath(): string {
  if (typeof window === "undefined") return "/materials";
  const stored = window.sessionStorage.getItem(MATERIALS_RETURN_KEY) ?? "";
  return /^\/materials(?:\?|$)/.test(stored) ? stored : "/materials";
}

export function materialPinQuery(pin: MaterialRevisionPin | undefined): string {
  if (!pin) return "";
  return new URLSearchParams({
    record_id: pin.recordId,
    record_revision_id: pin.recordRevisionId,
    material_revision_id: pin.materialRevisionId,
  }).toString();
}

export function materialDetailPath(
  materialId: string,
  tab: MaterialTab = "overview",
  pin?: MaterialRevisionPin,
): string {
  const path =
    tab === "overview"
      ? `/materials/${materialId}`
      : `/materials/${materialId}/${tab}`;
  const query = materialPinQuery(pin);
  return query ? `${path}?${query}` : path;
}
