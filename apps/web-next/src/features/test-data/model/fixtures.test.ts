import { createFixtureStore, makeSelectedCurve, NATIVE_FIXTURE_BYTES, NATIVE_FIXTURE_SHA256, SYNTHETIC_PREVIEW_POINT_COUNT, SYNTHETIC_SOURCE_POINT_COUNT, FIXTURE_ID } from "./fixtures";

describe("RD-01 fixture corpus", () => {
  it("keeps 10,000 ordinary metadata rows without prebuilding curves", () => {
    const store = createFixtureStore();
    expect(store.fixtureId).toBe(FIXTURE_ID);
    expect(store.fixtureId).toBe("rd01-reference-steel-reader-v3");
    expect(store.records).toHaveLength(10_000);
    expect(store.records.every((record) => record.curve === undefined && record.curvePreview === undefined)).toBe(true);
    const associationCounts = new Set(store.records.map((record) => record.cardIds.length));
    expect(associationCounts.has(0)).toBe(true);
    expect(associationCounts.has(1)).toBe(true);
    expect(associationCounts.has(2)).toBe(true);
    expect(store.records.find((record) => record.id === "td-00042")?.materialContext).toEqual({
      label: "Reference structural steel (non-production)",
      density: "7,850 kg/m³",
      youngsModulus: "210 GPa",
      poissonRatio: "0.30",
    });
    expect(store.records.find((record) => record.id === "td-00042")?.properties).toEqual([
      { key: "density", label: "Density", value: "7,850", unit: "kg/m³", conditionOrScope: "Reference material · non-production" },
      { key: "youngs_modulus", label: "Young's modulus", value: "210", unit: "GPa", conditionOrScope: "Reference material · non-production" },
      { key: "poisson_ratio", label: "Poisson ratio", value: "0.30", unit: "—", conditionOrScope: "Reference material · non-production" },
    ]);
  });

  it("declares a bounded 1,000 point preview over the 1m source", () => {
    const curve = makeSelectedCurve();
    expect(curve.preview.point_count).toBe(SYNTHETIC_SOURCE_POINT_COUNT);
    expect(curve.preview.returned_point_count).toBe(SYNTHETIC_PREVIEW_POINT_COUNT);
    expect(curve.preview.channels[0].values).toHaveLength(SYNTHETIC_PREVIEW_POINT_COUNT);
    expect(curve.preview.channels[0].values[421]).toBeNull();
  });

  it("keeps the native fixture contract metadata explicit", () => {
    expect(NATIVE_FIXTURE_BYTES).toBe(504);
    expect(NATIVE_FIXTURE_SHA256).toBe("FE8873B1F6978D5BF30D4936EADBEE9FB3B3BF5CD086E4C827BDF2E6105829A1");
    expect(createFixtureStore().cards.map((card) => card.mappingStatus)).toEqual(expect.arrayContaining(["exact", "transformed", "approximated", "unsupported", "ignored", "not_applicable"]));
  });
});
