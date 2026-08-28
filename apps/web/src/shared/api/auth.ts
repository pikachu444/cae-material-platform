import type {
  AuthenticatedPrincipal,
  ProductAccessSummary,
} from "../../types";

import {
  request,
  throwResponseError,
} from "./http";

import type { ApiConfig, ApiResult } from "./http";

export function getEffectiveProductAccess(
  config: ApiConfig,
): Promise<ApiResult<ProductAccessSummary>> {
  return request(config, "/product-access/me");
}

export function getAuthenticatedPrincipal(
  config: ApiConfig,
): Promise<ApiResult<AuthenticatedPrincipal>> {
  return request(config, "/me");
}

export type LocalDemoPersona = "administrator" | "user" | "reviewer";

export interface LocalDemoAccessToken {
  access_token: string;
  token_type: "Bearer";
  expires_in_seconds: number;
  organization_id: string;
  project_id: string;
  group: string;
  persona: LocalDemoPersona;
}

export interface LocalDemoTokenSession {
  persona: LocalDemoPersona;
  expiresAt: number;
}

/**
 * Read only the local-demo fixture identity and expiry needed to renew its
 * browser session. These unverified claims never grant access; the API still
 * validates the signed bearer token for every protected request.
 */
export function inspectLocalDemoAccessToken(token: string): LocalDemoTokenSession | null {
  const payloadSegment = token.trim().split(".")[1];
  if (!payloadSegment) return null;

  try {
    const normalized = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const payload = JSON.parse(window.atob(padded)) as { exp?: unknown; sub?: unknown };
    const personaBySubject: Record<string, LocalDemoPersona> = {
      "cmp-demo-administrator": "administrator",
      "cmp-demo-user": "user",
      "cmp-demo-reviewer": "reviewer",
    };
    const persona = typeof payload.sub === "string" ? personaBySubject[payload.sub] : undefined;
    if (!persona || typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) return null;
    return { persona, expiresAt: payload.exp * 1000 };
  } catch {
    return null;
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

/**
 * Request the explicitly enabled local-demo token without attaching a bearer
 * credential.  A normal deployment has no such route, so this never becomes
 * an authentication fallback for the workbench.
 */
export async function requestLocalDemoAccessToken(
  config: Pick<ApiConfig, "baseUrl">,
  persona: LocalDemoPersona = "administrator",
): Promise<ApiResult<LocalDemoAccessToken>> {
  const baseUrl = config.baseUrl.trim().replace(/\/$/, "") || "/api/v1";
  const personaQuery = persona === "administrator" ? "" : `?persona=${persona}`;
  const response = await fetch(`${baseUrl}/demo-identity/token${personaQuery}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    return throwResponseError(response);
  }
  return {
    data: (await response.json()) as LocalDemoAccessToken,
    etag: response.headers.get("etag"),
  };
}
