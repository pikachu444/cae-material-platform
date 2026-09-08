import type {
  CurveChannelContract,
  CurveDefinitionContract,
  CurveDeviationContract,
  CurveSeriesPreviewContract,
} from "../../../shared/model/curve-contracts";
import type {
  MappingStatus,
  PrototypeScenario,
  ReaderQueryParams,
  EngineeringPropertyRow,
  SolverCard,
  TestDataRecord,
} from "../../../shared/model/reader-contracts";

export const FIXTURE_ID = "rd01-reference-steel-reader-v3";
export const NATIVE_FIXTURE_SHA256 = "FE8873B1F6978D5BF30D4936EADBEE9FB3B3BF5CD086E4C827BDF2E6105829A1";
export const NATIVE_FIXTURE_BYTES = 504;
export const SYNTHETIC_SOURCE_POINT_COUNT = 1_000_000;
export const SYNTHETIC_PREVIEW_POINT_COUNT = 1_000;

export interface FixtureStore {
  readonly fixtureId: string;
  records: TestDataRecord[];
  cards: SolverCard[];
}

const makeChannels = (): CurveChannelContract[] => [
  {
    key: "engineering_strain",
    label: "Engineering strain",
    quantity_semantics: "mechanics.strain.engineering",
    axis_role: "independent",
    unit_contract: "common",
    dimension: "dimensionless",
    original_units: [{ unit: "%", scale_to_normalized: "0.01", offset_to_normalized: "0" }],
    normalized_unit: "1",
    display_unit: "%",
    display_scale: "100",
    display_offset: "0",
    value_basis: "normalized",
  },
  {
    key: "engineering_stress",
    label: "Engineering stress",
    quantity_semantics: "mechanics.stress.engineering",
    axis_role: "dependent",
    unit_contract: "common",
    dimension: "pressure",
    original_units: [{ unit: "MPa", scale_to_normalized: "1000000", offset_to_normalized: "0" }],
    normalized_unit: "Pa",
    display_unit: "MPa",
    display_scale: "0.000001",
    display_offset: "0",
    value_basis: "normalized",
  },
];

function makeCurve(): { definition: CurveDefinitionContract; preview: CurveSeriesPreviewContract } {
  const strainValues: Array<number | null> = [];
  const stressValues: Array<number | null> = [];
  const deviationValues: Array<number | null> = [];
  const indices: number[] = [];
  // The browser receives a bounded preview of exactly 1,000 positions. The
  // fixture is synthetic and does not pretend to render the one-million-point
  // source in a browser. A bounded reference linear-elastic response keeps the
  // reader scientifically honest without inventing a plastic law.
  for (let point = 0; point < SYNTHETIC_PREVIEW_POINT_COUNT; point += 1) {
    indices.push(point);
    if (point === 421) {
      strainValues.push(null);
      stressValues.push(null);
      deviationValues.push(null);
      continue;
    }
    const strain = (point / 999) * 0.001;
    const elastic = 210_000_000_000 * strain;
    strainValues.push(strain);
    stressValues.push(elastic);
    deviationValues.push(1_000_000);
  }

  const lowerValues = stressValues.map((value, index) => value === null ? null : value - (deviationValues[index] ?? 0));
  const upperValues = stressValues.map((value, index) => value === null ? null : value + (deviationValues[index] ?? 0));
  const channels = makeChannels();
  const deviations: CurveDeviationContract[] = [
    {
      key: "between_run_lower",
      target_channel_key: "engineering_stress",
      scope: "pointwise",
      kind: "standard_deviation",
      method_id: "reference.reader.synthetic.sd",
      method_version: "1.0.0",
      unit: "Pa",
      bound_direction: "lower",
      band_group: "between_run",
      scalar_value: null,
      series_key: "between_run_lower",
      source_count: null,
      source_count_series_key: "member_count",
      confidence_level: null,
      coverage: "pointwise",
      ddof: 1,
      quantile_probability: null,
      quantile_method: null,
    },
    {
      key: "between_run_upper",
      target_channel_key: "engineering_stress",
      scope: "pointwise",
      kind: "standard_deviation",
      method_id: "reference.reader.synthetic.sd",
      method_version: "1.0.0",
      unit: "Pa",
      bound_direction: "upper",
      band_group: "between_run",
      scalar_value: null,
      series_key: "between_run_upper",
      source_count: null,
      source_count_series_key: "member_count",
      confidence_level: null,
      coverage: "pointwise",
      ddof: 1,
      quantile_probability: null,
      quantile_method: null,
    },
  ];
  const preview: CurveSeriesPreviewContract = {
    point_count: SYNTHETIC_SOURCE_POINT_COUNT,
    returned_point_count: SYNTHETIC_PREVIEW_POINT_COUNT,
    sampled: true,
    indices,
    channels: [
      { key: "engineering_strain", values: strainValues },
      { key: "engineering_stress", values: stressValues },
    ],
    deviations: [
      { key: "between_run_lower", values: lowerValues },
      { key: "between_run_upper", values: upperValues },
    ],
    source_counts: [{ key: "member_count", values: Array.from({ length: SYNTHETIC_PREVIEW_POINT_COUNT }, () => 18) }],
  };
  return {
    definition: { definition_version: "1.0.0", channels, deviations },
    preview,
  };
}

const titleFor = (index: number): string => {
  if (index === 42) return "Reference tensile coupon · structural steel · room temperature";
  if (index % 17 === 0) return `장기 반복 인장 시험 데이터 — Structural steel comparison ${index.toString().padStart(5, "0")} / engineering baseline with a deliberately long name`;
  if (index % 23 === 0) return `Duplicate comparison set ${Math.ceil(index / 23)} · tensile curve`;
  return `Tensile reference set ${index.toString().padStart(5, "0")}`;
};

function cardIdsFor(index: number): string[] {
  if (index === 42) return ["card-00001"];
  if (index === 37 || index === 74) return ["card-00002", "card-00003"];
  if (index === 31) return ["card-00007"];
  if (index === 29) return ["card-00006"];
  if (index === 13) return ["card-00004"];
  if (index === 3 || index === 6) return ["card-00005"];
  return [];
}

function referenceProperties(conditionOrScope = "Reference material · non-production"): EngineeringPropertyRow[] {
  return [
    { key: "density", label: "Density", value: "7,850", unit: "kg/m³", conditionOrScope },
    { key: "youngs_modulus", label: "Young's modulus", value: "210", unit: "GPa", conditionOrScope },
    { key: "poisson_ratio", label: "Poisson ratio", value: "0.30", unit: "—", conditionOrScope },
  ];
}

function unknownCardProperties(): EngineeringPropertyRow[] {
  return [
    { key: "density", label: "Density", value: null, unit: "kg/m³", conditionOrScope: "Not supplied by stored card" },
    { key: "youngs_modulus", label: "Young's modulus", value: null, unit: "GPa", conditionOrScope: "Not supplied by stored card" },
    { key: "poisson_ratio", label: "Poisson ratio", value: null, unit: "—", conditionOrScope: "Not supplied by stored card" },
  ];
}

export function createFixtureStore(): FixtureStore {
  const records: TestDataRecord[] = [];
  for (let index = 1; index <= 10_000; index += 1) {
    const cardIds = cardIdsFor(index);
    records.push({
      id: `td-${index.toString().padStart(5, "0")}`,
      title: titleFor(index),
      description: "Synthetic non-production tensile reference fixture for reader and contract review.",
      kind: "tensile",
      sourceLabel: "Reference CSV import",
      sourceFilename: "reference-linear-elasticity.csv",
      condition: { temperature: "23 °C", rate: "1 mm/min", environment: "Dry air" },
        materialContext: {
        label: "Reference structural steel (non-production)",
        density: "7,850 kg/m³",
        youngsModulus: "210 GPa",
          poissonRatio: "0.30",
        },
        properties: referenceProperties(),
      sourcePointCount: SYNTHETIC_SOURCE_POINT_COUNT,
      previewPointCount: SYNTHETIC_PREVIEW_POINT_COUNT,
      cardIds,
      relationLabel: cardIds.length > 0 ? "Associated stored card" : "No stored card association",
      mappingStatus: "exact",
      updatedAt: `2026-${((index % 9) + 1).toString().padStart(2, "0")}-${((index % 27) + 1).toString().padStart(2, "0")}`,
    });
  }
  const cards: SolverCard[] = [
    {
      id: "card-00001",
      title: "OpenRadioss linear elastic reference card",
      description: "Stored native card explicitly associated with the selected Test Data record.",
      testDataIds: ["td-00042"],
      relationLabel: "Explicitly associated Test Data",
      mappingStatus: "exact",
      mappingNote: "Exact mapping; native download is available.",
      properties: referenceProperties("Stored card parameters · reference linear elastic"),
      nativeFileName: "reference-linear-elasticity-kg-m-s.rad",
      nativeByteLength: NATIVE_FIXTURE_BYTES,
      nativeSha256: NATIVE_FIXTURE_SHA256,
      outputStatus: "complete",
    },
    {
      id: "card-00002",
      title: "Comparison card with acknowledged approximation",
      description: "Synthetic card showing an explicit approximation acknowledgement state.",
      testDataIds: ["td-00037", "td-00074"],
      relationLabel: "Explicitly associated Test Data",
      mappingStatus: "approximated",
      mappingNote: "One optional field is approximated; acknowledgement is required for this card.",
      properties: unknownCardProperties(),
      nativeFileName: "comparison-approximation.rad",
      nativeByteLength: NATIVE_FIXTURE_BYTES,
      nativeSha256: NATIVE_FIXTURE_SHA256,
      outputStatus: "complete",
    },
    {
      id: "card-00003",
      title: "Card awaiting mapping decision",
      description: "Synthetic card retained for a blocked unsupported mapping state.",
      testDataIds: ["td-00037", "td-00074"],
      relationLabel: "Explicitly associated Test Data",
      mappingStatus: "unsupported",
      mappingNote: "A required field has no supported native mapping; download is blocked.",
      properties: unknownCardProperties(),
      nativeFileName: "blocked-card.rad",
      nativeByteLength: NATIVE_FIXTURE_BYTES,
      nativeSha256: NATIVE_FIXTURE_SHA256,
      outputStatus: "incomplete",
    },
    {
      id: "card-00004",
      title: "Reference comparison stored card",
      description: "Synthetic stored card for direct Cards navigation and download review.",
      testDataIds: ["td-00013"],
      relationLabel: "Explicitly associated Test Data",
      mappingStatus: "transformed",
      mappingNote: "Unit conversion is recorded as transformed mapping.",
      properties: unknownCardProperties(),
      nativeFileName: "comparison-reference.rad",
      nativeByteLength: NATIVE_FIXTURE_BYTES,
      nativeSha256: NATIVE_FIXTURE_SHA256,
      outputStatus: "complete",
    },
    {
      id: "card-00005",
      title: "Stored card for duplicate comparison set",
      description: "Synthetic card used to demonstrate duplicate names with independent IDs.",
      testDataIds: ["td-00003", "td-00006"],
      relationLabel: "Explicitly associated Test Data",
      mappingStatus: "exact",
      mappingNote: "Exact mapping for this synthetic fixture.",
      properties: unknownCardProperties(),
      nativeFileName: "duplicate-comparison.rad",
      nativeByteLength: NATIVE_FIXTURE_BYTES,
      nativeSha256: NATIVE_FIXTURE_SHA256,
      outputStatus: "complete",
    },
    {
      id: "card-00006",
      title: "Stored card with intentionally ignored optional field",
      description: "Synthetic card retained to show explicit ignored mapping acknowledgement.",
      testDataIds: ["td-00029"],
      relationLabel: "Explicitly associated Test Data",
      mappingStatus: "ignored",
      mappingNote: "An optional field is explicitly ignored; acknowledgement is required for this card.",
      properties: unknownCardProperties(),
      nativeFileName: "ignored-field-card.rad",
      nativeByteLength: NATIVE_FIXTURE_BYTES,
      nativeSha256: NATIVE_FIXTURE_SHA256,
      outputStatus: "complete",
    },
    {
      id: "card-00007",
      title: "Stored card with not applicable field",
      description: "Synthetic card showing a not-applicable mapping retained in the report.",
      testDataIds: ["td-00031"],
      relationLabel: "Explicitly associated Test Data",
      mappingStatus: "not_applicable",
      mappingNote: "The field does not apply to this card; native artifact remains available.",
      properties: unknownCardProperties(),
      nativeFileName: "not-applicable-card.rad",
      nativeByteLength: NATIVE_FIXTURE_BYTES,
      nativeSha256: NATIVE_FIXTURE_SHA256,
      outputStatus: "complete",
    },
  ];
  return { fixtureId: FIXTURE_ID, records, cards };
}

export function filterAndPage<T extends TestDataRecord | SolverCard>(values: T[], params: ReaderQueryParams): { rows: T[]; total: number } {
  const query = params.q.trim().toLocaleLowerCase();
  const filtered = values.filter((value) => !query || `${value.id} ${value.title} ${value.description}`.toLocaleLowerCase().includes(query));
  const sorted = [...filtered].sort((left, right) => {
    const leftValue = params.sort === "updatedAt" && "updatedAt" in left ? left.updatedAt : left.title;
    const rightValue = params.sort === "updatedAt" && "updatedAt" in right ? right.updatedAt : right.title;
    const comparison = String(leftValue).localeCompare(String(rightValue), "en", { numeric: true });
    return params.direction === "asc" ? comparison : -comparison;
  });
  return { rows: sorted.slice(params.offset, params.offset + params.pageSize), total: sorted.length };
}

export function mappingForScenario(status: MappingStatus, scenario: PrototypeScenario): MappingStatus {
  return scenario === "unsupported" ? "unsupported" : status;
}

export function makeSelectedCurve(): { definition: CurveDefinitionContract; preview: CurveSeriesPreviewContract } {
  return makeCurve();
}
