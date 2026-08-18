import type {
  CanonicalTestDataDocumentResponse,
  MaterialResponse,
  TestRunResponse,
} from "../../../../../types";
import type { ModelingSessionRecordRef } from "../../../model/session-controller";

export const MODELING_DATA_PAGE_SIZE = 25;

export interface ModelingDataLibraryRow {
  key: string;
  document: CanonicalTestDataDocumentResponse;
  revisionId: string;
  revisionNo: number;
  recordLabel: string;
  testType: string;
  materialLabel: string;
  conditionLabel: string;
  testDateLabel: string;
  pointCount: number | null;
  historical: boolean;
}

export interface ModelingDataLibraryFilters {
  query: string;
  testType: string;
  condition: string;
}

const NOT_RECORDED = "Not recorded";

function looksTechnical(value: string): boolean {
  const trimmed = value.trim();
  return !trimmed
    || /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(trimmed)
    || /^[0-9a-f]{32,}$/i.test(trimmed)
    || /^\d{8,}$/.test(trimmed)
    || /\d{8,}/.test(trimmed)
    || /^(?:specimen|sample|s)[-_ ]*\d+$/i.test(trimmed)
    || /(?:^|\s)(?:demo|fixture|synthetic)(?:\s|$)/i.test(trimmed)
    || /^cmp(?:\s|[-_])/i.test(trimmed);
}

export function modelingTestTypeLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized.includes("planar")) return "Planar tension";
  if (normalized.includes("biaxial")) return "Biaxial tension";
  if (normalized.includes("uniaxial")) return "Uniaxial tension";
  if (normalized.includes("compress")) return "Compression";
  if (normalized.includes("relaxation")) return "Relaxation";
  if (normalized.includes("dma")) return "DMA";
  if (normalized.includes("fatigue")) return "Fatigue";
  if (normalized.includes("forming") || normalized.includes("fld")) return "Forming limit";
  if (normalized.includes("shear")) return "Shear";
  if (normalized.includes("tensile") || normalized.includes("tension")) return "Tensile";
  const label = value.trim().replaceAll("_", " ").replaceAll("-", " ");
  return label ? `${label[0].toUpperCase()}${label.slice(1)}` : "Test Data";
}

export function modelingTestConditionLabel(run: TestRunResponse | undefined): string {
  const kelvin = run?.current_revision.content.test_temperature_k;
  if (kelvin === null || kelvin === undefined || !Number.isFinite(kelvin)) return NOT_RECORDED;
  const celsius = kelvin - 273.15;
  const rounded = Math.abs(celsius - Math.round(celsius)) < 0.05
    ? Math.round(celsius)
    : Number(celsius.toFixed(1));
  return `${new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(rounded)} \u00b0C`;
}

export function modelingTestDateLabel(value: string): string {
  const parsed = new Date(value.length === 10 ? `${value}T00:00:00Z` : value);
  if (Number.isNaN(parsed.valueOf())) return value || NOT_RECORDED;
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "UTC",
  }).format(parsed);
}

export function modelingTestRunDisplayLabel(run: TestRunResponse): string {
  const raw = run.current_revision.content.run_label?.trim() ?? "";
  if (!looksTechnical(raw)) return raw || "Test record";
  const sequence = raw.match(/(?:^|[-_ ]|replicate\s+)(\d+)$/iu)?.[1]
    ?? run.current_revision.content.specimen_id?.match(/(?:specimen|sample|s)?[-_ ]*(\d+)$/iu)?.[1];
  const testType = /^(?:specimen|sample|s)[-_ ]*\d+$/iu.test(raw)
    ? "Test Data"
    : modelingTestTypeLabel(raw);
  const base = testType === "Test Data" ? "Test record" : `${testType} test`;
  const readableSequence = sequence ? sequence.slice(-4).padStart(4, "0") : "";
  return readableSequence ? `${base} ${readableSequence}` : base;
}

export function modelingDataRecordLabel(
  document: CanonicalTestDataDocumentResponse,
  run: TestRunResponse | undefined,
): string {
  const runLabel = run?.current_revision.content.run_label?.trim() ?? "";
  if (run && runLabel) {
    const runDisplayLabel = modelingTestRunDisplayLabel(run);
    if (!runDisplayLabel.startsWith("Test record")) return runDisplayLabel;
  }

  const sequence = document.specimen_id.match(/(?:specimen|sample|s)?[-_ ]*(\d+)$/i)?.[1]
    ?? document.document_key.match(/(?:^|[-_ ])(\d+)$/)?.[1];
  const testType = modelingTestTypeLabel(document.method);
  const base = testType === "Test Data" ? "Test Data record" : `${testType} test`;
  const readableSequence = sequence ? sequence.slice(-4).padStart(4, "0") : "";
  return readableSequence ? `${base} ${readableSequence}` : base;
}

function exactRunFor(
  document: CanonicalTestDataDocumentResponse,
  runsById: ReadonlyMap<string, TestRunResponse>,
): TestRunResponse | undefined {
  const pin = document.governed_source?.test_run;
  if (!pin) return undefined;
  const run = runsById.get(pin.aggregate_id);
  return run?.current_revision.id === pin.revision_id ? run : undefined;
}

export function buildModelingDataLibraryRows(
  documents: CanonicalTestDataDocumentResponse[],
  selectedRefs: ModelingSessionRecordRef[],
  testRuns: TestRunResponse[],
  material?: MaterialResponse,
): ModelingDataLibraryRow[] {
  const refsById = new Map(selectedRefs.map((ref) => [ref.id, ref]));
  const runsById = new Map(testRuns.map((run) => [run.test_run_id, run]));
  const materialCode = material?.current_revision.content.material_code?.trim()
    .replace(/^CMP-(?:DEMO-)?/iu, "");
  const materialLabel = materialCode || material?.current_revision.content.name.trim();
  const rows: ModelingDataLibraryRow[] = [];

  for (const document of documents) {
    const run = exactRunFor(document, runsById);
    const selectedRef = refsById.get(document.test_data_document_id);
    if (selectedRef && selectedRef.revisionId !== document.current_revision.id) {
      rows.push({
        key: `${selectedRef.id}:${selectedRef.revisionId}`,
        document,
        revisionId: selectedRef.revisionId,
        revisionNo: selectedRef.revisionNo,
        recordLabel: selectedRef.label
          && selectedRef.label !== document.document_key
          && !looksTechnical(selectedRef.label)
          ? selectedRef.label
          : modelingDataRecordLabel(document, undefined),
        testType: modelingTestTypeLabel(document.method),
        materialLabel: materialLabel || document.material_grade.trim() || NOT_RECORDED,
        conditionLabel: NOT_RECORDED,
        testDateLabel: NOT_RECORDED,
        pointCount: null,
        historical: true,
      });
    }
    rows.push({
      key: `${document.test_data_document_id}:${document.current_revision.id}`,
      document,
      revisionId: document.current_revision.id,
      revisionNo: document.current_revision.revision_no,
      recordLabel: modelingDataRecordLabel(document, run),
      testType: modelingTestTypeLabel(document.method),
      materialLabel: materialLabel || document.material_grade.trim() || NOT_RECORDED,
      conditionLabel: modelingTestConditionLabel(run),
      testDateLabel: modelingTestDateLabel(document.test_date),
      pointCount: document.point_count,
      historical: false,
    });
  }

  return rows;
}

export function filterModelingDataLibraryRows(
  rows: ModelingDataLibraryRow[],
  filters: ModelingDataLibraryFilters,
): ModelingDataLibraryRow[] {
  const query = filters.query.trim().toLocaleLowerCase();
  return rows.filter((row) => {
    if (filters.testType && row.testType !== filters.testType) return false;
    if (filters.condition && row.conditionLabel !== filters.condition) return false;
    if (!query) return true;
    return [
      row.recordLabel,
      row.testType,
      row.materialLabel,
      row.conditionLabel,
      row.testDateLabel,
      row.document.document_key,
      row.document.method,
    ].some((value) => value.toLocaleLowerCase().includes(query));
  });
}

export function modelingDataFacetValues(rows: ModelingDataLibraryRow[]): {
  testTypes: string[];
  conditions: string[];
} {
  const sorted = (values: string[]) => [...new Set(values)].sort((left, right) => left.localeCompare(right));
  return {
    testTypes: sorted(rows.map((row) => row.testType)),
    conditions: sorted(rows.map((row) => row.conditionLabel)),
  };
}

export function modelingDataGraphTitle(row: ModelingDataLibraryRow | undefined): string {
  if (!row) return "Test Data curves";
  const quantities = row.document.channels.map((channel) => channel.quantity_semantics.toLowerCase());
  const method = row.document.method.toLowerCase();
  if (method.includes("dma") || quantities.some((quantity) => quantity.includes("storage_modulus") || quantity.includes("loss_modulus"))) return "DMA curves";
  if (method.includes("relaxation") || quantities.some((quantity) => quantity.includes("relaxation"))) return "Relaxation curves";
  if (quantities.some((quantity) => quantity.includes("stress")) && quantities.some((quantity) => quantity.includes("strain"))) return "Stress\u2013strain curves";
  if (method.includes("forming") || method.includes("fld")) return "Forming-limit curves";
  return `${row.testType} curves`;
}
