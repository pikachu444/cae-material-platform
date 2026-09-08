import type { MaterialPropertySet } from "../api";

const fields = [
  ["density_kg_per_m3", "밀도", "kg/m³", 1],
  ["youngs_modulus_pa", "탄성계수", "GPa", 1e9],
  ["poisson_ratio", "포아송비", "—", 1],
  ["yield_stress_pa", "항복강도", "MPa", 1e6],
] as const;

export function materialPropertyRows(propertySet: MaterialPropertySet, compact = false) {
  return fields.map(([key, label, unit, divisor]) => ({
    key, label, unit,
    value: typeof propertySet.content[key] === "number"
      ? (propertySet.content[key] / divisor).toLocaleString("ko-KR", { maximumSignificantDigits: compact ? 4 : 8 })
      : "미등록",
    exactValue: typeof propertySet.content[key] === "number" ? String(propertySet.content[key] / divisor) : undefined,
  }));
}

function range(minimum: unknown, maximum: unknown, unit: string) {
  const low = typeof minimum === "number" ? (unit === "°C" ? Number((minimum - 273.15).toPrecision(12)) : minimum) : null;
  const high = typeof maximum === "number" ? (unit === "°C" ? Number((maximum - 273.15).toPrecision(12)) : maximum) : null;
  if (low === null && high === null) return null;
  if (low === high) return `${low} ${unit}`;
  return `${low ?? "미지정"}–${high ?? "미지정"} ${unit}`;
}

export function propertyApplicability(propertySet: MaterialPropertySet) {
  const applicability = (propertySet.content.applicability ?? {}) as Record<string, unknown>;
  return {
    temperature: range(applicability.temperature_min_k, applicability.temperature_max_k, "°C"),
    strainRate: range(applicability.strain_rate_min_per_s, applicability.strain_rate_max_per_s, "s⁻¹"),
    note: typeof applicability.note === "string" ? applicability.note : null,
  };
}
