import { describe, expect, it } from "vitest";

import type { PolymerObservedSeries } from "./polymer-linear-viscoelastic-presentation";
import {
  buildPolymerApprovedSetupContext,
  formatPolymerApplicationRange,
} from "./polymer-linear-viscoelastic-fit-view";

describe("Polymer Fit application range", () => {
  it("uses fit and verification coordinates while excluding unused measurements", () => {
    const series: PolymerObservedSeries[] = [{
      key: "relaxation",
      label: "Measured relaxation modulus",
      xLabel: "Elapsed time",
      xUnit: "s",
      yLabel: "Shear modulus",
      yUnit: "Pa",
      points: [
        { ordinal: 0, x: 0.000_001, y: 1, partition: "EXCLUDED" },
        { ordinal: 1, x: 0.001, y: 1, partition: "CALIBRATION" },
        { ordinal: 2, x: 100, y: 1, partition: "HOLDOUT" },
        { ordinal: 3, x: 1_000_000, y: 1, partition: "EXCLUDED" },
      ],
    }];

    expect(formatPolymerApplicationRange(series)).toEqual({
      quantity: "Elapsed time",
      from: "10⁻³",
      to: "100",
      unit: "s",
    });
  });
});

describe("Polymer Fit approved setup context", () => {
  it("resolves a processed shifted DMA response when the original temperature sweep is not a direct Fit input", () => {
    expect(buildPolymerApprovedSetupContext({
      catalog: {
        material: { id: "material", revisionId: "material-r1" },
        materialState: { id: "state", revisionId: "state-r1" },
        propertySet: { id: "properties", revisionId: "properties-r1" },
      },
      testData: { id: "dma-temperature-sweep", revisionId: "dma-r1" },
      directMode: "unknown",
      sourceChoice: "processing-output",
      processingOutput: { id: "master-curve", revisionId: "master-curve-r1" },
    })).toEqual({
      material: { id: "material", revision_id: "material-r1" },
      material_state: { id: "state", revision_id: "state-r1" },
      test_data: { id: "dma-temperature-sweep", revision_id: "dma-r1" },
      processing_output: { id: "master-curve", revision_id: "master-curve-r1" },
      input_mode: "dma_frequency_master_curve",
    });
  });
});
