import type { CurveDefinitionContract, CurveSeriesPreviewContract } from "./curve-contracts";

export type TestDataKind = "tensile";
export type MappingStatus = "exact" | "transformed" | "approximated" | "unsupported" | "ignored" | "not_applicable";
export type PrototypeScenario = "normal" | "dense" | "empty" | "error" | "unsupported" | "long-name";

export interface TestCondition {
  temperature: string;
  rate: string;
  environment: string;
}

export interface EngineeringPropertyRow {
  key: string;
  label: string;
  value: string | null;
  unit: string | null;
  conditionOrScope?: string;
}

export interface TestDataRecord {
  id: string;
  title: string;
  description: string;
  kind: TestDataKind;
  sourceLabel: string;
  sourceFilename: string;
  condition: TestCondition;
  materialContext: {
    label: string;
    density: string;
    youngsModulus: string;
    poissonRatio: string;
  };
  properties: EngineeringPropertyRow[];
  curve?: CurveDefinitionContract;
  curvePreview?: CurveSeriesPreviewContract;
  sourcePointCount: number;
  previewPointCount: number;
  cardIds: string[];
  associatedCards?: Array<{ id: string; title: string; mappingStatus: MappingStatus }>;
  relationLabel: string;
  mappingStatus: MappingStatus;
  updatedAt: string;
  metadataApplied?: boolean;
}

export interface SolverCard {
  id: string;
  title: string;
  description: string;
  testDataIds: string[];
  associatedTestData?: Array<{ id: string; title: string }>;
  relationLabel: string;
  mappingStatus: MappingStatus;
  mappingNote: string;
  properties: EngineeringPropertyRow[];
  nativeFileName: string;
  nativeByteLength: number;
  nativeSha256: string;
  outputStatus: "complete" | "incomplete";
  metadataApplied?: boolean;
  nativeBytes?: Uint8Array;
}

export interface ReaderQueryParams {
  q: string;
  kind: TestDataKind | "all";
  sort: "title" | "updatedAt" | "kind";
  direction: "asc" | "desc";
  offset: number;
  pageSize: number;
  scenario: PrototypeScenario;
}

const MAPPING_STATUSES: readonly MappingStatus[] = ["exact", "transformed", "approximated", "unsupported", "ignored", "not_applicable"];

export function isEngineeringPropertyRows(value: unknown): value is EngineeringPropertyRow[] {
  return Array.isArray(value) && value.every((row) => {
    if (!row || typeof row !== "object") return false;
    const item = row as Partial<EngineeringPropertyRow>;
    return typeof item.key === "string" && item.key.length > 0
      && typeof item.label === "string" && item.label.length > 0
      && (item.value === null || typeof item.value === "string")
      && (item.unit === null || typeof item.unit === "string")
      && (item.conditionOrScope === undefined || typeof item.conditionOrScope === "string");
  });
}

export function isMappingStatus(value: unknown): value is MappingStatus {
  return typeof value === "string" && MAPPING_STATUSES.includes(value as MappingStatus);
}

/** Runtime guard for responses crossing the reader gateway. Unknown mappings
 * and incomplete artifact metadata stay identifiable but cannot be eligible
 * for preview or download. */
export function isSolverCardMetadata(value: unknown): value is SolverCard {
  if (!value || typeof value !== "object") return false;
  const card = value as Partial<SolverCard>;
  const nativeByteLength = card.nativeByteLength;
  return typeof card.id === "string" && card.id.length > 0
    && typeof card.title === "string"
    && typeof card.description === "string"
    && Array.isArray(card.testDataIds) && card.testDataIds.every((id) => typeof id === "string")
    && typeof card.relationLabel === "string"
    && isMappingStatus(card.mappingStatus)
    && typeof card.mappingNote === "string"
    && isEngineeringPropertyRows(card.properties)
    && typeof card.nativeFileName === "string" && card.nativeFileName.length > 0
    && typeof nativeByteLength === "number" && Number.isInteger(nativeByteLength) && nativeByteLength > 0
    && typeof card.nativeSha256 === "string" && /^[0-9a-f]{64}$/i.test(card.nativeSha256)
    && (card.outputStatus === "complete" || card.outputStatus === "incomplete")
    && (card.nativeBytes === undefined || card.nativeBytes instanceof Uint8Array)
    && (card.associatedTestData === undefined || (Array.isArray(card.associatedTestData) && card.associatedTestData.every((item) => item && typeof item.id === "string" && typeof item.title === "string")))
    && (card.metadataApplied === undefined || typeof card.metadataApplied === "boolean");
}
