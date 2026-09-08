import {
  createFixtureStore,
  filterAndPage,
  makeSelectedCurve,
  mappingForScenario,
  NATIVE_FIXTURE_BYTES,
  NATIVE_FIXTURE_SHA256,
} from "../features/test-data/model/fixtures";
import type { PrototypeScenario, ReaderQueryParams, SolverCard, TestDataRecord } from "../shared/model/reader-contracts";
import { isEngineeringPropertyRows } from "../shared/model/reader-contracts";
import {
  ReaderGatewayError,
  requestScopeKey,
  throwIfAborted,
  type DisplayMetadataPatch,
  type DownloadArtifact,
  type ReaderGateway,
  type ReaderSearchResult,
} from "../shared/api/reader-gateway";

const fixtureUrl = new URL(
  "../../tests/fixtures/openradioss/reference-linear-elasticity-kg-m-s.rad",
  import.meta.url,
).href;

const waitForReader = (signal?: AbortSignal): Promise<void> =>
  new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, 18);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("The operation was aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });

async function withFixtureDelay<T>(operation: () => T | Promise<T>, signal?: AbortSignal): Promise<T> {
  throwIfAborted(signal);
  await waitForReader(signal);
  throwIfAborted(signal);
  return await operation();
}

async function loadNativeFixture(): Promise<Uint8Array> {
  const response = await fetch(fixtureUrl);
  if (!response.ok) throw new ReaderGatewayError(503, "FIXTURE_UNAVAILABLE", "Native fixture could not be read.");
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength !== NATIVE_FIXTURE_BYTES) {
    throw new ReaderGatewayError(503, "FIXTURE_BYTES_CHANGED", "Native fixture byte parity check failed.");
  }
  if (globalThis.crypto?.subtle) {
    const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
    const actual = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("").toUpperCase();
    if (actual !== NATIVE_FIXTURE_SHA256) {
      throw new ReaderGatewayError(503, "FIXTURE_SHA_CHANGED", "Native fixture SHA-256 parity check failed.");
    }
  }
  return bytes;
}

function scopeFor(scenario: PrototypeScenario): string {
  return requestScopeKey("prototype", { actorID: "prototype-reviewer", orgID: "cmp", projectID: "rd01", effectiveAccessFingerprint: "dataset-read+export-read", authEpoch: 1, suffix: `scenario:${scenario}` });
}

function copyRecord(record: TestDataRecord, scenario: PrototypeScenario, includeCurve = false, associatedCards: TestDataRecord["associatedCards"] = []): TestDataRecord {
  const copy: TestDataRecord = {
    ...record,
    cardIds: [...record.cardIds],
    associatedCards,
    mappingStatus: mappingForScenario(record.mappingStatus, scenario),
  };
  if (!isEngineeringPropertyRows(copy.properties)) {
    throw new ReaderGatewayError(503, "PROPERTY_METADATA_INVALID", "Test Data property values could not be validated.");
  }
  if (!includeCurve) {
    copy.curve = undefined;
    copy.curvePreview = undefined;
    return copy;
  }
  const generated = makeSelectedCurve();
  const curve = record.curve ?? generated.definition;
  const curvePreview = record.curvePreview ?? generated.preview;
  return {
    ...copy,
    curve: {
      ...curve,
      channels: curve.channels.map((channel) => ({ ...channel, original_units: channel.original_units.map((unit) => ({ ...unit })) })),
      deviations: curve.deviations.map((deviation) => ({ ...deviation })),
    },
    curvePreview: {
      ...curvePreview,
      indices: [...curvePreview.indices],
      channels: curvePreview.channels.map((channel) => ({ ...channel, values: [...channel.values] })),
      deviations: curvePreview.deviations.map((deviation) => ({ ...deviation, values: [...deviation.values] })),
      source_counts: curvePreview.source_counts.map((count) => ({ ...count, values: [...count.values] })),
    },
  };
}

function copyCard(card: SolverCard, scenario: PrototypeScenario, associatedTestData: SolverCard["associatedTestData"] = []): SolverCard {
  const copy = {
    ...card,
    testDataIds: [...card.testDataIds],
    associatedTestData,
    mappingStatus: mappingForScenario(card.mappingStatus, scenario),
    nativeBytes: undefined,
  };
  if (!isEngineeringPropertyRows(copy.properties)) {
    throw new ReaderGatewayError(503, "PROPERTY_METADATA_INVALID", "Solver Card property values could not be validated.");
  }
  return copy;
}

export class PrototypeReaderGateway implements ReaderGateway {
  readonly mode = "prototype" as const;
  private readonly store = createFixtureStore();
  private nativeBytesPromise?: Promise<Uint8Array>;

  get scopeKey(): string {
    return requestScopeKey("prototype", { actorID: "prototype-reviewer", orgID: "cmp", projectID: "rd01", effectiveAccessFingerprint: "dataset-read+export-read", authEpoch: 1 });
  }

  private async nativeBytes(): Promise<Uint8Array> {
    this.nativeBytesPromise ??= loadNativeFixture();
    return this.nativeBytesPromise;
  }

  private recordCopy(record: TestDataRecord, scenario: PrototypeScenario, includeCurve = false): TestDataRecord {
    const associatedCards = record.cardIds.map((id) => this.store.cards.find((card) => card.id === id)).filter((card): card is SolverCard => Boolean(card)).map((card) => ({ id: card.id, title: card.title, mappingStatus: mappingForScenario(card.mappingStatus, scenario) }));
    return copyRecord(record, scenario, includeCurve, associatedCards);
  }

  private cardCopy(card: SolverCard, scenario: PrototypeScenario): SolverCard {
    const associatedTestData = card.testDataIds.map((id) => this.store.records.find((record) => record.id === id)).filter((record): record is TestDataRecord => Boolean(record)).map((record) => ({ id: record.id, title: record.title }));
    return copyCard(card, scenario, associatedTestData);
  }

  searchTestData(params: ReaderQueryParams, signal?: AbortSignal): Promise<ReaderSearchResult<TestDataRecord>> {
    return withFixtureDelay(() => {
      if (params.scenario === "error") {
        throw new ReaderGatewayError(503, "READER_UNAVAILABLE", "예시 reader 요청을 불러오지 못했습니다.", scopeFor(params.scenario));
      }
      if (params.scenario === "empty") return { rows: [], total: 0, requestScopeKey: scopeFor(params.scenario) };
      const result = filterAndPage(this.store.records, params);
      return {
        rows: result.rows.map((record) => this.recordCopy(record, params.scenario)),
        total: result.total,
        requestScopeKey: scopeFor(params.scenario),
      };
    }, signal);
  }

  getTestData(
    id: string,
    params: Pick<ReaderQueryParams, "scenario">,
    signal?: AbortSignal,
  ): Promise<TestDataRecord> {
    return withFixtureDelay(() => {
      if (params.scenario === "error") {
        throw new ReaderGatewayError(503, "READER_UNAVAILABLE", "예시 reader 요청을 불러오지 못했습니다.", scopeFor(params.scenario));
      }
      const record = this.store.records.find((candidate) => candidate.id === id);
      if (!record) throw new ReaderGatewayError(404, "TEST_DATA_NOT_FOUND", "Test Data를 찾을 수 없습니다.", scopeFor(params.scenario));
      return this.recordCopy(record, params.scenario, true);
    }, signal);
  }

  searchCards(params: ReaderQueryParams, signal?: AbortSignal): Promise<ReaderSearchResult<SolverCard>> {
    return withFixtureDelay(() => {
      if (params.scenario === "error") {
        throw new ReaderGatewayError(503, "READER_UNAVAILABLE", "예시 Cards 요청을 불러오지 못했습니다.", scopeFor(params.scenario));
      }
      if (params.scenario === "empty") return { rows: [], total: 0, requestScopeKey: scopeFor(params.scenario) };
      const result = filterAndPage(this.store.cards, params);
      return {
        rows: result.rows.map((card) => this.cardCopy(card, params.scenario)),
        total: result.total,
        requestScopeKey: scopeFor(params.scenario),
      };
    }, signal);
  }

  getCard(
    id: string,
    params: Pick<ReaderQueryParams, "scenario">,
    signal?: AbortSignal,
  ): Promise<SolverCard> {
    return withFixtureDelay(async () => {
      if (params.scenario === "error") {
        throw new ReaderGatewayError(503, "READER_UNAVAILABLE", "예시 Cards 요청을 불러오지 못했습니다.", scopeFor(params.scenario));
      }
      const card = this.store.cards.find((candidate) => candidate.id === id);
      if (!card) throw new ReaderGatewayError(404, "CARD_NOT_FOUND", "Solver Card를 찾을 수 없습니다.", scopeFor(params.scenario));
      const copy = this.cardCopy(card, params.scenario);
      copy.nativeBytes = await this.nativeBytes();
      return copy;
    }, signal);
  }

  downloadCard(
    id: string,
    params: Pick<ReaderQueryParams, "scenario">,
    signal?: AbortSignal,
  ): Promise<DownloadArtifact> {
    return withFixtureDelay(async () => {
      const card = this.store.cards.find((candidate) => candidate.id === id);
      if (!card) throw new ReaderGatewayError(404, "CARD_NOT_FOUND", "Solver Card를 찾을 수 없습니다.", scopeFor(params.scenario));
      const mappingStatus = mappingForScenario(card.mappingStatus, params.scenario);
      if (card.outputStatus !== "complete" || mappingStatus === "unsupported") {
        throw new ReaderGatewayError(409, "DOWNLOAD_BLOCKED", "필수 매핑이 없어 다운로드할 수 없습니다.", scopeFor(params.scenario));
      }
      const bytes = await this.nativeBytes();
      return {
        fileName: card.nativeFileName,
        bytes,
        sha256: NATIVE_FIXTURE_SHA256,
        byteLength: NATIVE_FIXTURE_BYTES,
      };
    }, signal);
  }

  patchDisplayMetadata(
    kind: "test-data" | "card",
    id: string,
    patch: DisplayMetadataPatch,
    signal?: AbortSignal,
  ): Promise<TestDataRecord | SolverCard> {
    return withFixtureDelay(() => {
      const title = patch.title.trim();
      const description = patch.description?.trim() ?? "";
      const collection = kind === "test-data" ? this.store.records : this.store.cards;
      const item = collection.find((candidate) => candidate.id === id);
      if (!item) throw new ReaderGatewayError(404, "OBJECT_NOT_FOUND", "저장 객체를 찾을 수 없습니다.");
      item.title = title;
      item.description = description;
      item.metadataApplied = true;
      return kind === "test-data"
        ? copyRecord(item as TestDataRecord, "normal")
        : this.cardCopy(item as SolverCard, "normal");
    }, signal);
  }
}

export const createPrototypeReaderGateway = (): ReaderGateway => new PrototypeReaderGateway();
