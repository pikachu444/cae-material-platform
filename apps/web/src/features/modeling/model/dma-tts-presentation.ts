import type { ObservedCurveInput } from "../../../engineering-curve-plot";
import type { CommonCurveStage, CommonProcessingPreview } from "./common-processing-contracts";
import type {
  DmaFrequencySweepSnapshot,
  DmaTtsIsotherm,
  DmaTtsMultiSourceSnapshot,
  DmaTemperatureSweepSnapshot,
  DmaTtsReadResponse,
} from "./dma-tts-contracts";
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

function multiSweepPreview(
  sweep: DmaFrequencySweepSnapshot,
  shifted = false,
): CommonProcessingPreview {
  const x = sweep.points.map((point) => point.frequencyHz);
  return preview({
    ordinal: sweep.sourceSweepOrdinal,
    method_id: "polymer.dma_frequency_master_curve",
    method_version: "1.0.0",
    point_count: sweep.points.length,
    series: [
      { quantity: shifted ? "frequency.angular.reduced" : "frequency.cyclic", unit: shifted ? "rad/s" : "Hz", values: x },
      { quantity: "mechanics.modulus.storage", unit: "Pa", values: sweep.points.map((point) => point.storageModulusPa) },
      { quantity: "mechanics.modulus.loss", unit: "Pa", values: sweep.points.map((point) => point.lossModulusPa) },
    ],
    diagnostics: [],
    scalar_results: [],
  }, shifted ? "frequency.angular.reduced" : "frequency.cyclic");
}

export function dmaMultiFrequencyPreview(
  source: DmaTtsMultiSourceSnapshot,
  visibleSweepOrdinals = source.sweeps.map((sweep) => sweep.sourceSweepOrdinal),
): CommonProcessingPreview | null {
  const first = source.sweeps.find((sweep) => visibleSweepOrdinals.includes(sweep.sourceSweepOrdinal));
  return first ? multiSweepPreview(first) : null;
}

export function dmaMultiFrequencyObservedCurves(
  source: DmaTtsMultiSourceSnapshot,
  visibleSweepOrdinals = source.sweeps.map((sweep) => sweep.sourceSweepOrdinal),
): ObservedCurveInput[] {
  return source.sweeps
    .filter((sweep) => visibleSweepOrdinals.includes(sweep.sourceSweepOrdinal))
    .flatMap((sweep) => {
      const base = multiSweepPreview(sweep);
      const temperature = sweep.representativeTemperatureK;
      const color = temperatureColor(temperature, source.sweeps);
      return [
        {
          id: `sweep-${sweep.sourceSweepOrdinal}-storage`,
          label: `${temperature} K · G′`,
          preview: { ...base, stages: [{ ...base.stages[0], series: [base.stages[0].series[0], base.stages[0].series[1]] }] },
          color,
          style: { lineStyle: "solid" as const, channel: "storage" as const, temperatureK: temperature },
        },
        {
          id: `sweep-${sweep.sourceSweepOrdinal}-loss`,
          label: `${temperature} K · G″`,
          preview: { ...base, stages: [{ ...base.stages[0], series: [base.stages[0].series[0], base.stages[0].series[2]] }] },
          color,
          style: { lineStyle: "dashed" as const, channel: "loss" as const, temperatureK: temperature },
        },
      ];
    });
}

function temperatureColor(value: number, sweeps: readonly { representativeTemperatureK: number }[]): string {
  const values = sweeps.map((sweep) => sweep.representativeTemperatureK);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const ratio = maximum === minimum ? 0.5 : (value - minimum) / (maximum - minimum);
  const hue = 212 - Math.round(Math.max(0, Math.min(1, ratio)) * 172);
  return `hsl(${hue} 64% 42%)`;
}

function isothermPreview(row: DmaTtsIsotherm, rows: readonly DmaTtsIsotherm[]): ObservedCurveInput[] {
  const rawX = row.angular_frequency_rad_per_s;
  const shiftedX = row.reduced_angular_frequency_rad_per_s;
  const points = (x: number[], representation: "raw" | "shifted"): ObservedCurveInput[] => {
    const base: CommonProcessingPreview = preview({
      ordinal: row.source_sweep_ordinal ?? 0,
      method_id: "polymer.dma_frequency_master_curve",
      method_version: "1.0.0",
      point_count: x.length,
      series: [{ quantity: "frequency.angular.reduced", unit: "rad/s", values: x }],
      diagnostics: [],
      scalar_results: [],
    }, "frequency.angular.reduced");
    const suffix = representation === "raw" ? "raw" : "shifted";
    return [
      {
        id: `saved-${row.source_sweep_ordinal ?? "fixed"}-${suffix}-storage`,
        label: `${row.representative_temperature_k} K · ${suffix} · G′`,
        preview: { ...base, stages: [{ ...base.stages[0], series: [...base.stages[0].series, { quantity: "mechanics.modulus.storage", unit: "Pa", values: row.storage_modulus_pa }] }] },
        color: temperatureColor(row.representative_temperature_k, rows.map((item) => ({ representativeTemperatureK: item.representative_temperature_k }))),
        style: { lineStyle: "solid" as const, channel: "storage" as const, representation, temperatureK: row.representative_temperature_k },
      },
      {
        id: `saved-${row.source_sweep_ordinal ?? "fixed"}-${suffix}-loss`,
        label: `${row.representative_temperature_k} K · ${suffix} · G″`,
        preview: { ...base, stages: [{ ...base.stages[0], series: [...base.stages[0].series, { quantity: "mechanics.modulus.loss", unit: "Pa", values: row.loss_modulus_pa }] }] },
        color: temperatureColor(row.representative_temperature_k, rows.map((item) => ({ representativeTemperatureK: item.representative_temperature_k }))),
        style: { lineStyle: "dashed" as const, channel: "loss" as const, representation, temperatureK: row.representative_temperature_k },
      },
    ];
  };
  const raw = rawX.length >= 2 ? points(rawX, "raw") : [];
  const shifted = shiftedX && shiftedX.length === rawX.length && shiftedX.length >= 2
    ? points(shiftedX, "shifted")
    : [];
  return [...raw, ...shifted];
}

export function dmaReadBackObservedCurves(
  readBack: DmaTtsReadResponse,
  visibleSweepOrdinals?: readonly number[],
): ObservedCurveInput[] {
  const rows = visibleSweepOrdinals
    ? readBack.isotherms.filter((row) => row.source_sweep_ordinal === null
      || visibleSweepOrdinals.includes(row.source_sweep_ordinal))
    : readBack.isotherms;
  return rows.flatMap((row) => isothermPreview(row, readBack.isotherms));
}

export function dmaReadBackPreview(
  readBack: DmaTtsReadResponse,
  visibleSweepOrdinals?: readonly number[],
): CommonProcessingPreview | null {
  const visible = visibleSweepOrdinals
    ? readBack.isotherms.filter((row) => row.source_sweep_ordinal === null
      || visibleSweepOrdinals.includes(row.source_sweep_ordinal))
    : readBack.isotherms;
  const first = visible.find((row) => row.partition !== "EXCLUDED" && row.source_frequency_hz.length >= 2)
    ?? visible.find((row) => row.source_frequency_hz.length >= 2);
  if (!first) return null;
  const x = first.reduced_angular_frequency_rad_per_s?.length === first.source_frequency_hz.length
    ? first.reduced_angular_frequency_rad_per_s
    : first.angular_frequency_rad_per_s;
  return preview({
    ordinal: first.source_sweep_ordinal ?? 0,
    method_id: "polymer.dma_frequency_master_curve",
    method_version: "1.0.0",
    point_count: x.length,
    series: [
      { quantity: "frequency.angular.reduced", unit: "rad/s", values: x },
      { quantity: "mechanics.modulus.storage", unit: "Pa", values: first.storage_modulus_pa },
      { quantity: "mechanics.modulus.loss", unit: "Pa", values: first.loss_modulus_pa },
    ],
    diagnostics: [],
    scalar_results: [],
  }, "frequency.angular.reduced");
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
