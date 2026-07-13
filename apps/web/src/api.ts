import type {
  ExportTarget,
  MaterialCreateInput,
  MaterialDetail,
  MaterialModelList,
  MaterialModelResponse,
  MaterialResponse,
  MaterialRevisionComparison,
  MaterialRevisionList,
  MaterialStateCreateInput,
  MaterialStateResponse,
  MappingReport,
  PropertySetCreateInput,
  PropertySetResponse,
  ReferenceModelCreateInput,
  SolverCardCreateInput,
  SolverCardList,
  SolverCardResponse,
} from "./types";

export interface ApiConfig {
  baseUrl: string;
  accessToken: string;
}

export interface ApiResult<T> {
  data: T;
  etag: string | null;
}

interface ProblemDocument {
  detail?: string;
  title?: string;
  code?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export const defaultApiConfig: ApiConfig = {
  baseUrl: (import.meta.env.VITE_CMP_API_BASE_URL ?? "/api/v1").replace(/\/$/, ""),
  accessToken: "",
};

const storageKey = "cmp.material-platform.api-config";

export function loadApiConfig(): ApiConfig {
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) {
    return defaultApiConfig;
  }
  try {
    const value: unknown = JSON.parse(raw);
    if (
      typeof value === "object" &&
      value !== null &&
      "baseUrl" in value &&
      "accessToken" in value &&
      typeof value.baseUrl === "string" &&
      typeof value.accessToken === "string"
    ) {
      return {
        baseUrl: value.baseUrl.replace(/\/$/, "") || defaultApiConfig.baseUrl,
        accessToken: value.accessToken,
      };
    }
  } catch {
    // A malformed local preference must not make the catalog inaccessible.
  }
  return defaultApiConfig;
}

export function saveApiConfig(config: ApiConfig): void {
  window.localStorage.setItem(storageKey, JSON.stringify(config));
}

function endpoint(config: ApiConfig, path: string): string {
  return `${config.baseUrl.replace(/\/$/, "")}${path}`;
}

function authenticatedHeaders(config: ApiConfig, init: RequestInit, accept: string): Headers {
  const token = config.accessToken.trim();
  if (!token) {
    throw new ApiError(401, "Add a bearer access token in Connection before using the catalog.");
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", accept);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

async function throwResponseError(response: Response): Promise<never> {
  const isJson = response.headers.get("content-type")?.includes("json");
  let problem: ProblemDocument = {};
  if (isJson) {
    try {
      problem = (await response.json()) as ProblemDocument;
    } catch {
      // Preserve a useful HTTP failure if a proxy sends an invalid problem body.
    }
  }
  throw new ApiError(
    response.status,
    problem.detail ?? problem.title ?? `Catalog request failed (${response.status}).`,
    problem.code,
  );
}

async function request<T>(
  config: ApiConfig,
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const headers = authenticatedHeaders(config, init, "application/json");
  const response = await fetch(endpoint(config, path), { ...init, headers });
  const isJson = response.headers.get("content-type")?.includes("json");
  const body: unknown = isJson ? await response.json() : undefined;

  if (!response.ok) {
    const problem = (body ?? {}) as ProblemDocument;
    throw new ApiError(response.status, problem.detail ?? problem.title ?? `Catalog request failed (${response.status}).`, problem.code);
  }

  return { data: body as T, etag: response.headers.get("etag") };
}

export function listMaterials(
  config: ApiConfig,
  query: string,
): Promise<ApiResult<{ items: MaterialResponse[] }>> {
  const search = new URLSearchParams({ limit: "50" });
  if (query.trim()) {
    search.set("q", query.trim());
  }
  return request(config, `/materials?${search.toString()}`);
}

export function getMaterialDetail(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<MaterialDetail>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}`);
}

export function getMaterialRevisions(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<MaterialRevisionList>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/revisions`);
}

export function compareMaterialRevisions(
  config: ApiConfig,
  materialId: string,
  leftRevisionId: string,
  rightRevisionId: string,
): Promise<ApiResult<MaterialRevisionComparison>> {
  const search = new URLSearchParams({
    left_revision_id: leftRevisionId,
    right_revision_id: rightRevisionId,
  });
  return request(
    config,
    `/materials/${encodeURIComponent(materialId)}/revisions:compare?${search.toString()}`,
  );
}

export function createMaterial(
  config: ApiConfig,
  input: MaterialCreateInput,
): Promise<ApiResult<MaterialResponse>> {
  return request(config, "/materials", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createMaterialState(
  config: ApiConfig,
  materialId: string,
  input: MaterialStateCreateInput,
): Promise<ApiResult<MaterialStateResponse>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/states`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getPropertySet(
  config: ApiConfig,
  propertySetId: string,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/property-sets/${encodeURIComponent(propertySetId)}`);
}

export function createPropertySet(
  config: ApiConfig,
  materialStateId: string,
  input: PropertySetCreateInput,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/property-sets`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revisePropertySet(
  config: ApiConfig,
  propertySetId: string,
  etag: string,
  input: PropertySetCreateInput,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/property-sets/${encodeURIComponent(propertySetId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listMaterialModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<MaterialModelList>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/material-models`);
}

export function createReferenceMaterialModel(
  config: ApiConfig,
  materialStateId: string,
  input: ReferenceModelCreateInput,
): Promise<ApiResult<MaterialModelResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/material-models`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function preflightSolverCardMapping(
  config: ApiConfig,
  materialModelId: string,
  target: ExportTarget,
): Promise<ApiResult<MappingReport>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/mapping-preflight`, {
    method: "POST",
    body: JSON.stringify({ target }),
  });
}

export function listSolverCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<SolverCardList>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/solver-cards`);
}

export function createSolverCard(
  config: ApiConfig,
  materialModelId: string,
  input: SolverCardCreateInput,
): Promise<ApiResult<SolverCardResponse>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/solver-cards`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function previewSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export interface SolverCardDownload {
  blob: Blob;
  filename: string;
}

export async function downloadSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/solver-cards/${encodeURIComponent(solverCardId)}/download`),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  const header = response.headers.get("content-disposition") ?? "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `solver-card-${solverCardId}.rad`,
    },
    etag: response.headers.get("etag"),
  };
}
