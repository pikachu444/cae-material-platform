import { describe, expect, it } from "vitest";

import {
  parseExactSavedFitOutput,
  readVerifiedExactOutput,
} from "./modeling-fit-output";
import type { CommonProcessingOutputResponse } from "./types";

type FitFixtureOptions = {
  families?: string[];
  pointCount?: number;
  responseLength?: number;
  tangentLength?: number;
  residualLength?: number;
  objectiveHistory?: number[];
  blendObjectiveHistory?: number[];
  activeBound?: string[];
  warningAcknowledged?: boolean;
};

function fitFixture(options: FitFixtureOptions = {}) {
  const pointCount = options.pointCount ?? 2;
  const families = options.families ?? ["voce"];
  const processStep = {
    method_id: "metal.elastic_modulus",
    method_version: "1.0.0",
    options: { method: "automatic" },
  };
  const fitStep = {
    method_id: "metal.hardening_fit_extrapolate",
    method_version: "1.0.0",
    options: { families },
  };
  const candidateFor = (family: string) => {
    const blend = family.includes("+");
    const parameterNames = blend
      ? []
      : [family === "ghosh" ? "delta_p_minus_n" : "coefficient"];
    return {
      family,
      response: Array.from({ length: options.responseLength ?? pointCount }, () => 1),
      residual: Array.from({ length: options.residualLength ?? 2 }, () => 0.1),
      tangent: Array.from({ length: options.tangentLength ?? pointCount }, () => 1),
      parameter_names: parameterNames,
      parameter_units: parameterNames.map(() => "Pa"),
      lower: parameterNames.map(() => 0),
      initial: parameterNames.map(() => 0.5),
      fitted: parameterNames.map(() => 0.6),
      upper: parameterNames.map(() => 1),
      rmse_pa: 1,
      relative_rmse: 0.01,
      objective: 0.02,
      scipy_cost: 0.01,
      convergence: true,
      nfev: 2,
      active_bound: family === families[0] ? (options.activeBound ?? []) : [],
      jacobian_rank: 1,
      jacobian_tolerance: 1e-12,
      jacobian_condition: null,
      identifiability: "identified",
      uncertainty: "not_provided",
      objective_history: blend
        ? (options.blendObjectiveHistory ?? [])
        : (options.objectiveHistory ?? [1, 0.1]),
      optimizer_status: 1,
      optimizer_message: "converged",
    };
  };
  const candidates = families.map(candidateFor);
  const stages = [
    "mapping",
    processStep.method_id,
    fitStep.method_id,
  ].map((method_id, ordinal) => ({
    ordinal,
    method_id,
    method_version: "1.0.0",
    point_count: pointCount,
    series: [
      { quantity: "strain.plastic", unit: "1", values: Array.from({ length: pointCount }, () => 0.1) },
      { quantity: "stress", unit: "Pa", values: Array.from({ length: pointCount }, () => 1) },
    ],
    diagnostics: [],
    scalar_results: [],
    fit_candidates: ordinal === 2 ? candidates : [],
  }));
  const processSource = {
    processing_output_id: "process-output",
    current_revision: { id: "process-revision" },
    output_sha256: "p".repeat(64),
    source_document: { aggregate_id: "document", revision_id: "document-revision" },
    source_document_sha256: "d".repeat(64),
    mapping_profile: { aggregate_id: "profile", revision_id: "profile-revision" },
    mapping_profile_sha256: "m".repeat(64),
    independent_quantity: "strain.plastic",
    steps: [processStep],
    stage_count: 2,
  };
  const output = {
    processing_output_id: "fit-output",
    current_revision: { id: "fit-revision" },
    output_sha256: "o".repeat(64),
    source_processing_output: { aggregate_id: "process-output", revision_id: "process-revision" },
    source_processing_output_sha256: "p".repeat(64),
    source_document: processSource.source_document,
    source_document_sha256: processSource.source_document_sha256,
    source_canonical_artifact_sha256: "c".repeat(64),
    mapping_profile: processSource.mapping_profile,
    mapping_profile_sha256: processSource.mapping_profile_sha256,
    independent_quantity: processSource.independent_quantity,
    steps: [processStep, fitStep],
    stage_count: 3,
    final_point_count: pointCount,
  };
  const blend = families.includes("voce+swift");
  const selectedLaws = blend ? ["voce", "swift"] : [families[0]];
  const parameter_sets = selectedLaws.map((law) => {
    const candidate = candidates.find((item) => item.family === law)!;
    return {
      law,
      parameters: candidate.parameter_names.map((name, index) => ({
        name,
        value: candidate.fitted[index],
        unit: candidate.parameter_units[index],
        lower: candidate.lower[index],
        upper: candidate.upper[index],
      })),
    };
  });
  const fit_decision = {
    candidate_key: blend ? "voce+swift" : families[0],
    mode: blend ? "blend" : "single",
    primary_law: blend ? "voce" : families[0],
    secondary_law: blend ? "swift" : null,
    primary_weight: blend ? 0.5 : null,
    parameter_sets,
    fit_minimum: 0.1,
    fit_maximum: 1,
    extrapolation_maximum: 2,
    extrapolation_policy: "bounded",
    metric_definition: "relative_rmse",
    metric_value: 0.01,
    requested_term_policy: null,
    actual_term_count: null,
    selection_reason: "fixture",
    warning_acknowledged: options.warningAcknowledged ?? false,
  };
  const document = {
    document_type: "cmp.processing-output",
    document_version: "1.3.0",
    output_id: output.processing_output_id,
    source_processing_output: output.source_processing_output,
    source_processing_output_sha256: output.source_processing_output_sha256,
    source_document: output.source_document,
    mapping_profile: output.mapping_profile,
    source_canonical_artifact_sha256: output.source_canonical_artifact_sha256,
    steps: output.steps,
    fit_decision,
    result: {
      source_document_sha256: output.source_document_sha256,
      mapping_profile_sha256: output.mapping_profile_sha256,
      independent_quantity: output.independent_quantity,
      stages,
    },
  };
  return {
    document,
    output: output as unknown as CommonProcessingOutputResponse,
    processSource: processSource as unknown as CommonProcessingOutputResponse,
  };
}

describe("exact saved Fit output verification", () => {
  it("accepts a blob whose bytes match the pinned SHA-256", async () => {
    const text = JSON.stringify({ document_type: "cmp.processing-output" });
    const bytes = new TextEncoder().encode(text);
    const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
    const expected = Array.from(new Uint8Array(digest), (value) =>
      value.toString(16).padStart(2, "0"),
    ).join("");

    await expect(
      readVerifiedExactOutput(
        { data: { blob: new Blob([bytes], { type: "application/json" }) } },
        expected,
      ),
    ).resolves.toBe(text);
  });

  it("rejects a saved document whose source digest was tampered", () => {
    const processStep = {
      method_id: "metal.elastic_modulus",
      method_version: "1.0.0",
      options: { method: "automatic" },
    };
    const fitStep = {
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      options: { families: ["voce", "swift", "hockett_sherby", "ghosh"] },
    };
    const processSource = {
      processing_output_id: "process-output",
      current_revision: { id: "process-revision" },
      output_sha256: "p".repeat(64),
      source_document: { aggregate_id: "document", revision_id: "document-revision" },
      source_document_sha256: "d".repeat(64),
      mapping_profile: { aggregate_id: "profile", revision_id: "profile-revision" },
      mapping_profile_sha256: "m".repeat(64),
      independent_quantity: "strain.plastic",
      steps: [processStep],
      stage_count: 2,
    };
    const output = {
      processing_output_id: "fit-output",
      current_revision: { id: "fit-revision" },
      output_sha256: "o".repeat(64),
      source_processing_output: { aggregate_id: "process-output", revision_id: "process-revision" },
      source_processing_output_sha256: "p".repeat(64),
      source_document: processSource.source_document,
      source_document_sha256: "d".repeat(64),
      source_canonical_artifact_sha256: "c".repeat(64),
      mapping_profile: processSource.mapping_profile,
      mapping_profile_sha256: "m".repeat(64),
      independent_quantity: "strain.plastic",
      steps: [processStep, fitStep],
      stage_count: 3,
    };
    const tampered = {
      document_type: "cmp.processing-output",
      document_version: "1.3.0",
      output_id: output.processing_output_id,
      source_processing_output: output.source_processing_output,
      source_processing_output_sha256: output.source_processing_output_sha256,
      source_document: output.source_document,
      mapping_profile: output.mapping_profile,
      source_canonical_artifact_sha256: output.source_canonical_artifact_sha256,
      steps: output.steps,
      result: {
        source_document_sha256: "x".repeat(64),
        mapping_profile_sha256: output.mapping_profile_sha256,
        independent_quantity: output.independent_quantity,
      },
    };

    expect(() => parseExactSavedFitOutput(
      JSON.stringify(tampered),
      output as unknown as CommonProcessingOutputResponse,
      processSource as unknown as CommonProcessingOutputResponse,
    )).toThrow("Saved Fit result failed exact source or step validation");
  });

  it("rejects candidate response and tangent arrays that do not match the Fit point count", () => {
    const responseTampered = fitFixture({ responseLength: 1 });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(responseTampered.document),
      responseTampered.output,
      responseTampered.processSource,
    )).toThrow("Saved Fit result candidate evidence is invalid");

    const tangentTampered = fitFixture({ tangentLength: 1 });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(tangentTampered.document),
      tangentTampered.output,
      tangentTampered.processSource,
    )).toThrow("Saved Fit result candidate evidence is invalid");
  });

  it("requires nonempty finite residuals with one consistent length across candidates", () => {
    const emptyResidual = fitFixture({ residualLength: 0 });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(emptyResidual.document),
      emptyResidual.output,
      emptyResidual.processSource,
    )).toThrow("Saved Fit result candidate evidence is invalid");

    const inconsistent = fitFixture({ families: ["voce", "swift"] });
    inconsistent.document.result.stages[2].fit_candidates[1].residual = [0.1, 0.1, 0.1];
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(inconsistent.document),
      inconsistent.output,
      inconsistent.processSource,
    )).toThrow("Saved Fit result candidate evidence is invalid");
  });

  it("rejects non-finite blend objective history but permits an empty server blend history", () => {
    const valid = fitFixture({ families: ["voce", "swift", "voce+swift"] });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(valid.document),
      valid.output,
      valid.processSource,
    )).not.toThrow();

    const tampered = fitFixture({ families: ["voce", "swift", "voce+swift"] });
    tampered.document.result.stages[2].fit_candidates[2].objective_history = [
      0.1,
      "not-a-number" as unknown as number,
    ];
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(tampered.document),
      tampered.output,
      tampered.processSource,
    )).toThrow("Saved Fit result candidate evidence is invalid");
  });

  it("requires acknowledgement when selected Ghosh or active-bound evidence carries a warning", () => {
    const ghosh = fitFixture({ families: ["ghosh"] });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(ghosh.document),
      ghosh.output,
      ghosh.processSource,
    )).toThrow("Saved Fit decision warning must be acknowledged");

    const activeBound = fitFixture({ families: ["voce"], activeBound: ["coefficient"] });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(activeBound.document),
      activeBound.output,
      activeBound.processSource,
    )).toThrow("Saved Fit decision warning must be acknowledged");
  });
});
