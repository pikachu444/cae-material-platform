import type {
  GrantProductAccessInput,
  ProductAccessAssignment,
} from "../contracts";

import {
  request,
} from "../../../shared/api/http";

import type { ApiConfig, ApiResult } from "../../../shared/api/http";

export { ApiError } from "../../../shared/api/http";
export type { ApiConfig } from "../../../shared/api/http";
export { getEffectiveProductAccess } from "../../../shared/api/auth";

export function listProductAccessAssignments(
  config: ApiConfig,
): Promise<ApiResult<{ items: ProductAccessAssignment[] }>> {
  return request(config, "/product-access/assignments");
}

export function grantProductAccess(
  config: ApiConfig,
  input: GrantProductAccessInput,
): Promise<ApiResult<ProductAccessAssignment>> {
  return request(config, "/product-access/assignments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revokeProductAccess(
  config: ApiConfig,
  assignmentId: string,
  reason: string,
): Promise<ApiResult<null>> {
  return request(config, `/product-access/assignments/${assignmentId}/revoke`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}
