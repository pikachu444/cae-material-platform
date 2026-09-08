import { ReaderGatewayError } from "./reader-gateway";

type JsonBody = Record<string, unknown> | unknown[];

let accessToken: string | null = null;
let demoTokenRequest: Promise<string | null> | null = null;

function storage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.sessionStorage;
  } catch {
    return undefined;
  }
}

async function ensureAccessToken(signal?: AbortSignal): Promise<string | null> {
  if (accessToken) return accessToken;
  const saved = storage()?.getItem("cmp-access-token");
  if (saved) {
    accessToken = saved;
    return saved;
  }
  return null;
}

/**
 * A stable cache scope for reader queries. The API remains the authority for
 * authorization; this value only prevents React Query from sharing a result
 * between two bearer/tenant/project contexts in one browser session.
 */
export function authorizationScopeKey(): string {
  const token = accessToken ?? storage()?.getItem("cmp-access-token") ?? "anonymous";
  if (token === "anonymous") return token;
  try {
    const payload = token.split(".")[1];
    if (!payload) return "bearer";
    const claims = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as Record<string, unknown>;
    const tenant = claims.tenant_id ?? claims.tenant ?? claims.organization_id ?? "";
    const project = claims.project_id ?? claims.project ?? "";
    const subject = claims.sub ?? "";
    return [tenant, project, subject].map(String).join(":") || "bearer";
  } catch {
    return "bearer";
  }
}

function clearToken() {
  accessToken = null;
  storage()?.removeItem("cmp-access-token");
  if (typeof window !== "undefined") window.dispatchEvent(new Event("cmp-session-expired"));
}

/** Explicit local-demo sign-in. Normal requests never mint an identity implicitly. */
export async function connectDemoSession(persona: "administrator" | "user" | "reviewer" = "administrator"): Promise<boolean> {
  if (demoTokenRequest) return Boolean(await demoTokenRequest);
  demoTokenRequest = (async () => {
    try {
      const response = await fetch(`/api/v1/demo-identity/token?persona=${persona}`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return null;
      const body = (await response.json()) as { access_token?: string };
      if (!body.access_token) return null;
      accessToken = body.access_token;
      storage()?.setItem("cmp-access-token", accessToken);
      return accessToken;
    } catch {
      return null;
    } finally {
      demoTokenRequest = null;
    }
  })();
  return Boolean(await demoTokenRequest);
}

export class ApiError extends ReaderGatewayError {
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    const safeStatus = ([401, 403, 404, 409, 503] as const).includes(status as 401 | 403 | 404 | 409 | 503)
      ? (status as 401 | 403 | 404 | 409 | 503)
      : 503;
    super(safeStatus, code, message);
    this.name = "ApiError";
    this.details = details;
  }
}

async function requestRaw(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await ensureAccessToken(init.signal ?? undefined);
  const headers = new Headers(init.headers);
  headers.set("Accept", headers.get("Accept") ?? "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (response.status === 401) clearToken();
  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = undefined;
    }
    const body = typeof details === "object" && details !== null ? details as { detail?: string; title?: string } : undefined;
    throw new ApiError(response.status, body?.title ?? `HTTP_${response.status}`, response.status === 401 ? "세션이 만료되었거나 연결되지 않았습니다. 상단에서 로컬 데모를 다시 연결해 주세요." : response.status === 403 ? "현재 권한으로 이 자료를 조회할 수 없습니다." : response.status === 404 ? "선택한 저장 자료를 찾을 수 없습니다. 목록으로 돌아가 다시 선택해 주세요." : response.status === 409 ? "선택한 자료와 응답이 일치하지 않습니다. 다시 조회해 주세요." : "서버에 연결할 수 없습니다. 연결을 확인한 뒤 다시 시도하세요.", details);
  }
  return response;
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await requestRaw(path, init);
  return (await response.json()) as T;
}

export async function requestText(path: string, init?: RequestInit): Promise<{
  text: string;
  contentType: string;
  fileName: string;
}> {
  const response = await requestRaw(path, { ...init, headers: { Accept: "text/plain", ...init?.headers } });
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const fileMatch = disposition.match(/filename="?([^";]+)"?/i);
  return {
    text: await response.text(),
    contentType: response.headers.get("Content-Type") ?? "text/plain; charset=utf-8",
    fileName: fileMatch?.[1] ?? "preview.txt",
  };
}

/** Read a semantic JSON document whose server hash is not an HTTP byte hash. */
export async function requestSemanticJson<T>(path: string, init?: RequestInit): Promise<{
  value: T;
  semanticSha256: string;
  headers: Headers;
}> {
  const response = await requestRaw(path, init);
  const header = response.headers.get("X-Content-SHA256");
  if (!header) throw new ApiError(409, "MISSING_DOCUMENT_HASH", "The server did not pin the semantic document hash.");
  const value = (await response.json()) as T;
  return { value, semanticSha256: header.replace(/^sha256:/i, "").toLowerCase(), headers: response.headers };
}

export async function requestBytes(path: string, init?: RequestInit): Promise<{
  bytes: Uint8Array;
  sha256: string;
  contentType: string;
  fileName: string;
}> {
  const response = await requestRaw(path, init);
  const bytes = new Uint8Array(await response.arrayBuffer());
  const expected = response.headers.get("X-Content-SHA256") ?? response.headers.get("X-CMP-Card-SHA256");
  if (!expected) throw new ApiError(409, "MISSING_ARTIFACT_HASH", "The server did not pin the downloaded artifact.");
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const actual = Array.from(new Uint8Array(digest), (item) => item.toString(16).padStart(2, "0")).join("");
  if (actual !== expected.toLowerCase()) throw new ApiError(409, "ARTIFACT_HASH_MISMATCH", "The downloaded artifact does not match its server hash.");
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const fileMatch = disposition.match(/filename="?([^";]+)"?/i);
  return {
    bytes,
    sha256: actual,
    contentType: response.headers.get("Content-Type") ?? "application/octet-stream",
    fileName: fileMatch?.[1] ?? "download",
  };
}

export function queryString(values: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value) params.set(key, value);
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function saveBytes(bytes: Uint8Array, fileName: string, contentType: string): void {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  const blob = new Blob([buffer], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

export type { JsonBody };
