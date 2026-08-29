export {
  ApiError,
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
} from "./http";
export type { ApiConfig, ApiResult } from "./http";
export {
  defaultApiConfig,
  getAuthenticatedPrincipal,
  getEffectiveProductAccess,
  inspectLocalDemoAccessToken,
  loadApiConfig,
  requestLocalDemoAccessToken,
  saveApiConfig,
} from "./auth";
export type {
  LocalDemoAccessToken,
  LocalDemoPersona,
  LocalDemoTokenSession,
} from "./auth";
export type {
  AuthenticatedPrincipal,
  FeatureGrant,
  ProductAccessSummary,
  ProductRole,
} from "./auth-contracts";
