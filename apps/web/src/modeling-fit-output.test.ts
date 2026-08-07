import { describe, expect, it } from "vitest";

import {
  exactFitPlotData,
  parseExactSavedFitOutput,
  readVerifiedExactOutput,
} from "./modeling-fit-output";
import type { CommonProcessingOutputResponse } from "./types";

type FitFixtureOptions = {
  families?: string[];
  responseLength?: number;
  tangentLength?: number;
  residualLength?: number;
  objectiveHistory?: number[];
  blendObjectiveHistory?: number[];
  activeBound?: string[];
  warningAcknowledged?: boolean;
};

function fitFixture(options: FitFixtureOptions = {}) {
  // Mirror the canonical metal output: the true/plastic workup retains the
  // seven observed samples while hardening extrapolation persists its own
  // 101-point response grid.  The x arrays intentionally differ so the
  // frontend cannot hide a shared-grid assumption.
  const observedPointCount = 7;
  const selectedPointCount = 101;
  const observedStrain = [0, 0.01, 0.025, 0.04, 0.06, 0.08, 0.1];
  const observedStress = [3.2e8, 3.6e8, 4.1e8, 4.5e8, 4.9e8, 5.2e8, 5.45e8];
  const selectedStrain = Array.from({ length: selectedPointCount }, (_, index) => index / 100);
  const selectedStress = Array.from({ length: selectedPointCount }, (_, index) => 3.2e8 + index * 2.5e6);
  const families = options.families ?? ["voce"];
  const processSteps = [
    { method_id: "rows.sort_unique", method_version: "1.0.0", options: { duplicate_policy: "reject" } },
    { method_id: "metal.elastic_modulus", method_version: "1.0.0", options: { method: "automatic" } },
    { method_id: "metal.proof_stress", method_version: "1.0.0", options: { offset: 0.002 } },
    { method_id: "metal.necking_candidate", method_version: "1.0.0", options: { policy: "manual_index" } },
    { method_id: "metal.engineering_to_true_plastic", method_version: "1.0.0", options: { necking_policy: "manual_index", manual_necking_index: 6 } },
  ];
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
       response: Array.from({ length: options.responseLength ?? selectedPointCount }, () => 1),
      residual: Array.from({ length: options.residualLength ?? 2 }, () => 0.1),
       tangent: Array.from({ length: options.tangentLength ?? selectedPointCount }, () => 1),
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
  const genericSeries = Array.from({ length: observedPointCount }, (_, index) => index / 100);
  const stages = [
    { method_id: "mapping", point_count: observedPointCount, series: [
      { quantity: "strain.engineering", unit: "1", values: genericSeries },
      { quantity: "stress.engineering", unit: "Pa", values: observedStress },
    ] },
    ...processSteps.slice(0, 4).map((step) => ({
      method_id: step.method_id,
      point_count: observedPointCount,
      series: [
        { quantity: "strain.engineering", unit: "1", values: genericSeries },
        { quantity: "stress.engineering", unit: "Pa", values: observedStress },
      ],
    })),
    { method_id: "metal.engineering_to_true_plastic", point_count: observedPointCount, series: [
      { quantity: "strain.true_plastic", unit: "1", values: observedStrain },
      { quantity: "stress.true", unit: "Pa", values: observedStress },
    ] },
    { method_id: fitStep.method_id, point_count: selectedPointCount, series: [
      { quantity: "strain.true_plastic", unit: "1", values: selectedStrain },
      ...families.filter((family) => !family.includes("+")).map((family) => ({
        quantity: `stress.hardening.${family}`,
        unit: "Pa",
        values: selectedStress,
      })),
      { quantity: "stress.hardening.selected", unit: "Pa", values: selectedStress },
    ] },
  ].map((stage, ordinal) => ({
    ordinal,
    method_id: stage.method_id,
    method_version: "1.0.0",
    point_count: stage.point_count,
    series: stage.series,
    diagnostics: [],
    scalar_results: [],
    fit_candidates: ordinal === 6 ? candidates : [],
  }));
  const processSource = {
    processing_output_id: "process-output",
    current_revision: { id: "process-revision" },
    output_sha256: "p".repeat(64),
    source_document: { aggregate_id: "document", revision_id: "document-revision" },
    source_document_sha256: "d".repeat(64),
    mapping_profile: { aggregate_id: "profile", revision_id: "profile-revision" },
    mapping_profile_sha256: "m".repeat(64),
    independent_quantity: "strain.engineering",
    steps: processSteps,
    stage_count: 6,
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
    steps: [...processSteps, fitStep],
    stage_count: 7,
    final_point_count: selectedPointCount,
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
    inconsistent.document.result.stages[6].fit_candidates[1].residual = [0.1, 0.1, 0.1];
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
    tampered.document.result.stages[6].fit_candidates[2].objective_history = [
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

  it("rejects a Fit without persisted true stress/strain and selected hardening series", () => {
    const fixture = fitFixture();
    fixture.document.result.stages[5].series = [
      { quantity: "strain.engineering", unit: "1", values: Array.from({ length: 7 }, (_, index) => index / 100) },
      { quantity: "stress.engineering", unit: "Pa", values: Array.from({ length: 7 }, () => 1) },
    ];
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(fixture.document),
      fixture.output,
      fixture.processSource,
    )).toThrow("missing true plastic strain, true stress, or selected hardening series");
  });

  it("returns the original persisted sample arrays for the metal Fit graph", () => {
    const fixture = fitFixture();
    const parsed = parseExactSavedFitOutput(
      JSON.stringify(fixture.document),
      fixture.output,
      fixture.processSource,
    );
    expect(exactFitPlotData(parsed.preview, parsed.selection!)).toMatchObject({
      observedX: [0, 0.01, 0.025, 0.04, 0.06, 0.08, 0.1],
      observed: [3.2e8, 3.6e8, 4.1e8, 4.5e8, 4.9e8, 5.2e8, 5.45e8],
      selectedX: Array.from({ length: 101 }, (_, index) => index / 100),
      selected: Array.from({ length: 101 }, (_, index) => 3.2e8 + index * 2.5e6),
      xUnit: "1",
      stressUnit: "Pa",
      selectedQuantity: "stress.hardening.voce",
    });
  });

  it("fails closed when persisted plot units are not true-plastic 1 and stress Pa", () => {
    const xUnitMismatch = fitFixture();
    xUnitMismatch.document.result.stages[5].series[0].unit = "mm";
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(xUnitMismatch.document),
      xUnitMismatch.output,
      xUnitMismatch.processSource,
    )).toThrow("matching units");

    const stressUnitMismatch = fitFixture();
    stressUnitMismatch.document.result.stages[6].series[1].unit = "MPa";
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(stressUnitMismatch.document),
      stressUnitMismatch.output,
      stressUnitMismatch.processSource,
    )).toThrow("matching units");
  });

  it("rejects duplicate or ambiguous persisted pair quantities", () => {
    const duplicateObserved = fitFixture();
    duplicateObserved.document.result.stages[5].series.push({
      quantity: "stress.true",
      unit: "Pa",
      values: Array.from({ length: 7 }, () => 1),
    });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(duplicateObserved.document),
      duplicateObserved.output,
      duplicateObserved.processSource,
    )).toThrow("matching units");

    const duplicateSelected = fitFixture();
    duplicateSelected.document.result.stages[6].series.push({
      quantity: "stress.hardening.voce",
      unit: "Pa",
      values: Array.from({ length: 101 }, () => 1),
    });
    expect(() => parseExactSavedFitOutput(
      JSON.stringify(duplicateSelected.document),
      duplicateSelected.output,
      duplicateSelected.processSource,
    )).toThrow("matching units");
  });
});
