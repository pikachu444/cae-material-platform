import type { PrototypeScenario, ReaderQueryParams, SolverCard, TestDataRecord } from "../model/reader-contracts";

export interface ReaderSearchResult<T> {
  rows: T[];
  total: number;
  requestScopeKey: string;
  stale?: boolean;
}

export interface DisplayMetadataPatch {
  title: string;
  description?: string;
}

export interface DownloadArtifact {
  fileName: string;
  bytes: Uint8Array;
  sha256: string;
  byteLength: number;
}

export type ReaderGatewayErrorStatus = 401 | 403 | 404 | 409 | 503;

export class ReaderGatewayError extends Error {
  readonly status: ReaderGatewayErrorStatus;
  readonly code: string;
  readonly requestScopeKey?: string;

  constructor(
    status: ReaderGatewayErrorStatus,
    code: string,
    message: string,
    requestScopeKey?: string,
  ) {
    super(message);
    this.name = "ReaderGatewayError";
    this.status = status;
    this.code = code;
    this.requestScopeKey = requestScopeKey;
  }
}

export interface ReaderGateway {
  readonly mode: "prototype" | "live";
  readonly scopeKey: string;
  searchTestData(params: ReaderQueryParams, signal?: AbortSignal): Promise<ReaderSearchResult<TestDataRecord>>;
  getTestData(id: string, params: Pick<ReaderQueryParams, "scenario">, signal?: AbortSignal): Promise<TestDataRecord>;
  searchCards(params: ReaderQueryParams, signal?: AbortSignal): Promise<ReaderSearchResult<SolverCard>>;
  getCard(id: string, params: Pick<ReaderQueryParams, "scenario">, signal?: AbortSignal): Promise<SolverCard>;
  downloadCard(id: string, params: Pick<ReaderQueryParams, "scenario">, signal?: AbortSignal): Promise<DownloadArtifact>;
  patchDisplayMetadata(
    kind: "test-data" | "card",
    id: string,
    patch: DisplayMetadataPatch,
    signal?: AbortSignal,
  ): Promise<TestDataRecord | SolverCard>;
}

export interface RequestScopeParts {
  actorID: string;
  orgID: string;
  projectID: string;
  effectiveAccessFingerprint: string;
  authEpoch: number;
  suffix?: string;
}

export function requestScopeKey(mode: ReaderGateway["mode"], scope: RequestScopeParts): string {
  // A cache scope is intentionally made from identity and effective access
  // context. Bearer tokens never enter the key.
  return [mode, scope.actorID, scope.orgID, scope.projectID, scope.effectiveAccessFingerprint, `auth:${scope.authEpoch}`, scope.suffix].filter(Boolean).join("|");
}

export function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("The operation was aborted", "AbortError");
}

export function isGatewayError(error: unknown): error is ReaderGatewayError {
  return error instanceof ReaderGatewayError;
}
