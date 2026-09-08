import {
  ReaderGatewayError,
  requestScopeKey,
  type DisplayMetadataPatch,
  type DownloadArtifact,
  type ReaderGateway,
  type ReaderSearchResult,
} from "./reader-gateway";
import type { ReaderQueryParams, SolverCard, TestDataRecord } from "../model/reader-contracts";

const disconnected = (): never => {
  throw new ReaderGatewayError(
    503,
    "API_NOT_CONNECTED",
    "API-not-connected: B1 reader integration is not connected in this mode.",
  );
};

/** The ordinary build has a real gateway boundary and an explicit disconnected state.
 * It never imports or falls back to the prototype fixture transport. */
export class LiveReaderGateway implements ReaderGateway {
  readonly mode = "live" as const;
  readonly scopeKey = requestScopeKey("live", { actorID: "live-user", orgID: "cmp", projectID: "rd01", effectiveAccessFingerprint: "observed-live-access", authEpoch: 1, suffix: "live-reader" });

  searchTestData(_params: ReaderQueryParams, _signal?: AbortSignal): Promise<ReaderSearchResult<TestDataRecord>> {
    return Promise.reject(disconnected());
  }

  getTestData(_id: string, _params: Pick<ReaderQueryParams, "scenario">, _signal?: AbortSignal): Promise<TestDataRecord> {
    return Promise.reject(disconnected());
  }

  searchCards(_params: ReaderQueryParams, _signal?: AbortSignal): Promise<ReaderSearchResult<SolverCard>> {
    return Promise.reject(disconnected());
  }

  getCard(_id: string, _params: Pick<ReaderQueryParams, "scenario">, _signal?: AbortSignal): Promise<SolverCard> {
    return Promise.reject(disconnected());
  }

  downloadCard(_id: string, _params: Pick<ReaderQueryParams, "scenario">, _signal?: AbortSignal): Promise<DownloadArtifact> {
    return Promise.reject(disconnected());
  }

  patchDisplayMetadata(
    _kind: "test-data" | "card",
    _id: string,
    _patch: DisplayMetadataPatch,
    _signal?: AbortSignal,
  ): Promise<TestDataRecord | SolverCard> {
    return Promise.reject(disconnected());
  }
}

export const createLiveReaderGateway = (): ReaderGateway => new LiveReaderGateway();
