export interface ApiConfig {
  baseUrl: string;
  accessToken: string;
}

export interface ApiResult<T> {
  data: T;
  etag: string | null;
  requestId?: string | null;
}

interface ProblemDocument {
  detail?: string;
  title?: string;
  code?: string;
  trace_id?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly traceId?: string;
  readonly supportReference?: string;

  /** Compatibility bridge until #263 moves the remaining root clients. */
  static readonly modelingTransportCompatibility = {
    authenticatedHeaders,
    endpoint,
    request,
    throwResponseError,
  } as const;

  constructor(status: number, message: string, code?: string, traceId?: string) {
    const supportReference = [code, traceId].filter(Boolean).join(" · ") || undefined;
    super(supportReference ? `${message} Support reference: ${supportReference}.` : message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.traceId = traceId;
    this.supportReference = supportReference;
  }
}

export function endpoint(config: ApiConfig, path: string): string {
  return `${config.baseUrl.replace(/\/$/, "")}${path}`;
}

export function authenticatedHeaders(
  config: ApiConfig,
  init: RequestInit,
  accept: string,
): Headers {
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

export async function throwResponseError(response: Response): Promise<never> {
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
    problem.trace_id,
  );
}

export async function request<T>(
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
    throw new ApiError(
      response.status,
      problem.detail ?? problem.title ?? `Catalog request failed (${response.status}).`,
      problem.code,
      problem.trace_id,
    );
  }

  return {
    data: body as T,
    etag: response.headers.get("etag"),
    requestId: response.headers.get("x-request-id"),
  };
}
