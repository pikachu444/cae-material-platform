import { describe, expect, it } from "vitest";

import type { PolymerSourceSnapshot } from "../../../model/linear-viscoelastic-calibration-draft";
import type { LinearViscoelasticCandidate, LinearViscoelasticResponseResidualEvidence } from "../../../model/linear-viscoelastic-calibration-contracts";
import {
  buildPolymerCalculatedSeries,
  buildPolymerCandidateCalculatedSeries,
  buildPolymerObservedSeries,
  buildProcessedPolymerObservedSeries,
  buildPolymerResidualSeries,
  exactPolymerResponsePartitions,
  polymerResponseDomain,
} from "./polymer-linear-viscoelastic-presentation";

describe("polymer Fit presentation", () => {
  it("maps exact relaxation source rows without calculating a candidate response", () => {
    const snapshot: PolymerSourceSnapshot = {
      mode: "relaxation",
      pointCount: 3,
      channels: [
        { key: "time", quantity: "time.elapsed", unit: "s", values: [0.1, 1, 10] },
        { key: "modulus", quantity: "modulus.shear.relaxation", unit: "Pa", values: [3, 2, 1] },
      ],
      temperatures: [],
      conditionTemperature: 293.15,
    };

    const series = buildPolymerObservedSeries(snapshot, "293.15", ["CALIBRATION", "HOLDOUT", "EXCLUDED"]);

    expect(series).toHaveLength(1);
    expect(series[0].points).toEqual([
      { ordinal: 0, x: 0.1, y: 3, partition: "CALIBRATION" },
      { ordinal: 1, x: 1, y: 2, partition: "HOLDOUT" },
      { ordinal: 2, x: 10, y: 1, partition: "EXCLUDED" },
    ]);
    expect(polymerResponseDomain(series)).toEqual({ xMin: 0.1, xMax: 10, yMin: 1, yMax: 3 });
  });

  it("joins exact server recommendation rows to source coordinates without browser fitting", () => {
    const snapshot: PolymerSourceSnapshot = {
      mode: "relaxation",
      pointCount: 3,
      channels: [
        { key: "time", quantity: "time.elapsed", unit: "s", values: [0.1, 1, 10] },
        { key: "modulus", quantity: "modulus.shear.relaxation", unit: "Pa", values: [3, 2, 1] },
      ],
      temperatures: [],
      conditionTemperature: 293.15,
    };
    const observed = buildPolymerObservedSeries(snapshot, "293.15", ["CALIBRATION", "HOLDOUT", "EXCLUDED"]);
    const evidence = {
      rows: [
        { ordinal: 0, channel: "relaxation", observed: 3, predicted: 2.8, residual: 0.2, partition: "CALIBRATION" },
        { ordinal: 1, channel: "relaxation", observed: 2, predicted: 2.1, residual: -0.1, partition: "HOLDOUT" },
        { ordinal: 2, channel: "relaxation", observed: 1, predicted: 1.05, residual: -0.05, partition: "EXCLUDED" },
      ],
    } as LinearViscoelasticResponseResidualEvidence;

    const calculated = buildPolymerCalculatedSeries(observed, evidence);

    expect(calculated[0].label).toBe("Recommended model");
    expect(calculated[0].points[1]).toEqual({
      ordinal: 1,
      x: 1,
      y: 2.1,
      observed: 2,
      predicted: 2.1,
      residual: -0.1,
      partition: "HOLDOUT",
    });
    expect(calculated[0].points[2]).toEqual({
      ordinal: 2,
      x: 10,
      y: 1.05,
      observed: 1,
      predicted: 1.05,
      residual: -0.05,
      partition: "EXCLUDED",
    });
    expect(polymerResponseDomain(observed, calculated)).toEqual({ xMin: 0.1, xMax: 10, yMin: 1, yMax: 3 });
    expect(exactPolymerResponsePartitions(
      ["CALIBRATION", "CALIBRATION", "CALIBRATION"],
      evidence,
    )).toEqual(["CALIBRATION", "HOLDOUT", "EXCLUDED"]);
  });

  it("uses exact reduced-frequency DMA values and rejects mismatched response evidence", () => {
    const observed = buildProcessedPolymerObservedSeries({
      mode: "dma_frequency_master_curve",
      coordinate_quantity: "frequency.angular.reduced",
      coordinate_unit: "rad/s",
      response_channels: [
        { channel: "dma_storage", quantity: "mechanics.modulus.storage", unit: "Pa" },
        { channel: "dma_loss", quantity: "mechanics.modulus.loss", unit: "Pa" },
      ],
      reference_temperature_k: "313.15",
      rows: [
        { ordinal: 0, coordinate: 0.1, storage_modulus_pa: 3, loss_modulus_pa: 0.3, partition: "CALIBRATION", exclusion_reason: null },
        { ordinal: 1, coordinate: 10, storage_modulus_pa: 2, loss_modulus_pa: 0.2, partition: "HOLDOUT", exclusion_reason: null },
        { ordinal: 2, coordinate: null, storage_modulus_pa: 0, loss_modulus_pa: -1, partition: "EXCLUDED", exclusion_reason: "invalid coordinate" },
      ],
    });

    expect(observed).toHaveLength(2);
    expect(observed[0].xLabel).toBe("Reduced angular frequency");
    expect(observed[0].points).toEqual([
      { ordinal: 0, x: 0.1, y: 3, partition: "CALIBRATION" },
      { ordinal: 1, x: 10, y: 2, partition: "HOLDOUT" },
    ]);

    const mismatched = {
      rows: [
        { ordinal: 0, channel: "dma_storage", observed: 999, predicted: 2.8, residual: -0.2, partition: "CALIBRATION" },
        { ordinal: 1, channel: "dma_storage", observed: 2, predicted: 2.1, residual: 0.1, partition: "HOLDOUT" },
        { ordinal: 0, channel: "dma_loss", observed: 0.3, predicted: 0.25, residual: -0.05, partition: "CALIBRATION" },
        { ordinal: 1, channel: "dma_loss", observed: 0.2, predicted: 0.22, residual: 0.02, partition: "HOLDOUT" },
      ],
    } as LinearViscoelasticResponseResidualEvidence;
    expect(buildPolymerCalculatedSeries(observed, mismatched)).toEqual([]);

    const residuals = buildPolymerResidualSeries(observed, {
      calibration_residuals: [-0.2, -0.05],
      holdout_residuals: [0.1, 0.02],
    } as LinearViscoelasticCandidate, {
      relaxation_weight: "1",
      dma_storage_weight: "0.5",
      dma_loss_weight: "0.5",
      relaxation_scale_pa: "1",
      dma_storage_scale_pa: "1",
      dma_loss_scale_pa: "1",
    });
    expect(residuals.map((series) => series.key)).toEqual([
      "calibration:dma-storage",
      "holdout:dma-storage",
      "calibration:dma-loss",
      "holdout:dma-loss",
    ]);
    expect(residuals.filter((series) => series.key.startsWith("holdout:")).every(
      (series) => series.title.startsWith("Differences on check points"),
    )).toBe(true);
    expect(residuals[0].points[0].residual).toBeCloseTo(-0.2 / Math.sqrt(0.5) / 3);
    expect(residuals[1].points[0].residual).toBeCloseTo(0.1 / 2);
    expect(residuals[2].points[0].residual).toBeCloseTo(-0.05 / Math.sqrt(0.5) / 0.3);
    expect(residuals[3].points[0].residual).toBeCloseTo(0.02 / 0.2);
  });

  it("reconstructs the selected candidate response from its exact normalized residuals", () => {
    const observed = buildProcessedPolymerObservedSeries({
      mode: "dma_frequency_master_curve",
      coordinate_quantity: "frequency.angular.reduced",
      coordinate_unit: "rad/s",
      response_channels: [
        { channel: "dma_storage", quantity: "mechanics.modulus.storage", unit: "Pa" },
        { channel: "dma_loss", quantity: "mechanics.modulus.loss", unit: "Pa" },
      ],
      reference_temperature_k: "313.15",
      rows: [
        { ordinal: 0, coordinate: 0.1, storage_modulus_pa: 3, loss_modulus_pa: 0.3, partition: "CALIBRATION", exclusion_reason: null },
        { ordinal: 1, coordinate: 10, storage_modulus_pa: 2, loss_modulus_pa: 0.2, partition: "HOLDOUT", exclusion_reason: null },
      ],
    });
    const selected = {
      candidate_id: "selected",
      calibration_residuals: [Math.sqrt(0.5) * 0.2 / 10, Math.sqrt(0.5) * -0.02 / 2],
      holdout_residuals: [0.3 / 10, -0.02 / 2],
    } as LinearViscoelasticCandidate;

    const calculated = buildPolymerCandidateCalculatedSeries(observed, selected, {
      relaxation_weight: "1",
      dma_storage_weight: "0.5",
      dma_loss_weight: "0.5",
      relaxation_scale_pa: "1",
      dma_storage_scale_pa: "10",
      dma_loss_scale_pa: "2",
    });

    expect(calculated.map((series) => [series.role, series.label])).toEqual([
      ["selection", "Selected storage response"],
      ["selection", "Selected loss response"],
    ]);
    expect(calculated[0].points[0].predicted).toBeCloseTo(3.2);
    expect(calculated[0].points[1].predicted).toBeCloseTo(2.3);
    expect(calculated[1].points[0].predicted).toBeCloseTo(0.28);
    expect(calculated[1].points[1].predicted).toBeCloseTo(0.18);
  });
});
