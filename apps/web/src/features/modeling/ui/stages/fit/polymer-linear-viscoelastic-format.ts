import type { LinearViscoelasticCandidate } from "../../../model/linear-viscoelastic-calibration-contracts";

export function formatPolymerFitNumber(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined || !Number.isFinite(value))
    return "—";
  const magnitude = Math.abs(value);
  return magnitude >= 1_000_000 || (magnitude > 0 && magnitude < 0.001)
    ? value.toExponential(3)
    : value.toLocaleString("en-US", {
        maximumSignificantDigits: 6,
        useGrouping: false,
      });
}

export function formatPolymerInputNumber(value: number): string {
  if (!Number.isFinite(value)) return "";
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude >= 1_000_000 || magnitude < 0.001) {
    const [coefficient, exponent] = value.toExponential(3).split("e");
    return `${coefficient.replace(/\.?0+$/, "")}e${Number(exponent)}`;
  }
  return value.toLocaleString("en-US", {
    maximumSignificantDigits: 6,
    useGrouping: false,
  });
}

export function formatPolymerDeviation(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined || !Number.isFinite(value))
    return "Not available";
  const percent = Math.abs(value) * 100;
  if (percent === 0) return "0%";
  if (percent < 0.01) return "<0.01%";
  return `${percent.toLocaleString("en-US", {
    maximumFractionDigits: percent < 10 ? 2 : 1,
  })}%`;
}

const SUPERSCRIPT_DIGITS: Record<string, string> = {
  "-": "⁻",
  "0": "⁰",
  "1": "¹",
  "2": "²",
  "3": "³",
  "4": "⁴",
  "5": "⁵",
  "6": "⁶",
  "7": "⁷",
  "8": "⁸",
  "9": "⁹",
};

export function formatPolymerRangeCoordinate(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const exponent = Math.floor(Math.log10(Math.abs(value)));
  if (exponent > -3 && exponent < 4) return formatPolymerFitNumber(value);
  const coefficient = value / (10 ** exponent);
  const exponentLabel = String(exponent).split("").map((digit) => SUPERSCRIPT_DIGITS[digit] ?? digit).join("");
  const coefficientLabel = Math.abs(coefficient - 1) < Number.EPSILON
    ? ""
    : `${coefficient.toLocaleString("en-US", { maximumSignificantDigits: 3, useGrouping: false })} × `;
  return `${coefficientLabel}10${exponentLabel}`;
}

export function formatPolymerAxisTick(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const magnitude = Math.abs(value);
  if (magnitude >= 10_000 || (magnitude > 0 && magnitude <= 0.001)) {
    return formatPolymerRangeCoordinate(value);
  }
  return value.toLocaleString("en-US", {
    maximumSignificantDigits: 3,
    useGrouping: false,
  });
}

export function formatPolymerSignedDeviation(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined || !Number.isFinite(value))
    return "Not available";
  return `${value < 0 ? "−" : ""}${formatPolymerDeviation(value)}`;
}

export function polymerCandidateRankMap(
  candidates: LinearViscoelasticCandidate[],
): Map<string, number> {
  const ordered = [...candidates].sort((left, right) => {
    const leftScore = Number.isFinite(left.bic)
      ? left.bic
      : Number.POSITIVE_INFINITY;
    const rightScore = Number.isFinite(right.bic)
      ? right.bic
      : Number.POSITIVE_INFINITY;
    return (
      leftScore - rightScore ||
      left.term_count - right.term_count ||
      left.attempt_ordinal - right.attempt_ordinal
    );
  });
  return new Map(
    ordered.map((candidate, index) => [candidate.candidate_id, index + 1]),
  );
}

export interface PolymerParameterCheckPresentation {
  label: "Pass" | "Failed" | "Not available";
  accessibleLabel: string;
}

export function polymerParameterCheck(
  candidate: LinearViscoelasticCandidate,
): PolymerParameterCheckPresentation {
  const total = candidate.physical_parameters.length;
  const rank = candidate.rank?.rank;
  if (!Number.isInteger(rank)) {
    return {
      label: "Not available",
      accessibleLabel: "Parameter check not available",
    };
  }
  if ((rank ?? 0) >= total) {
    return {
      label: "Pass",
      accessibleLabel: `Parameter check passed; ${total} of ${total} parameters resolved`,
    };
  }
  return {
    label: "Failed",
    accessibleLabel: `Parameter check failed; ${rank} of ${total} parameters resolved`,
  };
}

export function meanAbsoluteResidual(values: number[]): number | null {
  const valid = values.filter(Number.isFinite);
  return valid.length
    ? valid.reduce((sum, value) => sum + Math.abs(value), 0) / valid.length
    : null;
}

export function polymerParameterLabel(name: string): string {
  if (name === "G_inf_pa") return "Equilibrium shear modulus G∞";
  const modulus = /^G_(\d+)_pa$/.exec(name);
  if (modulus) return `Prony shear modulus G${modulus[1]}`;
  const relaxationTime = /^tau_(\d+)_s$/.exec(name);
  if (relaxationTime) return `Relaxation time τ${relaxationTime[1]}`;
  return name;
}

export function polymerCandidateParameterLabel(
  index: number,
  termCount: number,
): string {
  if (index === 0) return "Equilibrium shear modulus G∞";
  if (index <= termCount) return `Prony shear modulus G${index}`;
  return `Relaxation time τ${index - termCount}`;
}
