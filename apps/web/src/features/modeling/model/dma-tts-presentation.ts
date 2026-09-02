import type { CommonCurveStage, CommonProcessingPreview } from "./common-processing-contracts";
import type { DmaTemperatureSweepSnapshot } from "./dma-tts-contracts";
import type { ProcessedLinearViscoelasticFitInput } from "./linear-viscoelastic-calibration-contracts";

function preview(stage: CommonCurveStage, independentQuantity: string): CommonProcessingPreview {
  return {
    execution_mode: "preview",
    promotable: false,
    source_document_sha256: "",
    mapping_profile_sha256: "",
    independent_quantity: independentQuantity,
    stages: [stage],
  };
}

export function dmaTemperatureSweepPreview(source: DmaTemperatureSweepSnapshot): CommonProcessingPreview {
  return preview({
    ordinal: 0,
    method_id: "polymer.dma_temperature_sweep",
    method_version: "1.0.0",
    point_count: source.rows.length,
    series: [
      { quantity: "physics.temperature", unit: "K", values: source.rows.map((row) => row.temperatureK) },
      { quantity: "mechanics.modulus.storage", unit: "Pa", values: source.rows.map((row) => row.storageModulusPa) },
      { quantity: "mechanics.modulus.loss", unit: "Pa", values: source.rows.map((row) => row.lossModulusPa) },
    ],
    diagnostics: [],
    scalar_results: [],
  }, "physics.temperature");
}

export function dmaMasterCurvePreview(input: ProcessedLinearViscoelasticFitInput): CommonProcessingPreview {
  const visible = input.rows.filter((row) => row.coordinate !== null && row.partition !== "EXCLUDED");
  return preview({
    ordinal: 0,
    method_id: "polymer.dma_frequency_master_curve",
    method_version: "1.0.0",
    point_count: visible.length,
    series: [
      { quantity: input.coordinate_quantity, unit: input.coordinate_unit, values: visible.map((row) => row.coordinate!) },
      { quantity: "mechanics.modulus.storage", unit: "Pa", values: visible.map((row) => row.storage_modulus_pa) },
      { quantity: "mechanics.modulus.loss", unit: "Pa", values: visible.map((row) => row.loss_modulus_pa) },
    ],
    diagnostics: [],
    scalar_results: [],
  }, input.coordinate_quantity);
}
