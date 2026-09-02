import { expect, type APIRequestContext } from "@playwright/test";

interface ExactRevision {
  id: string;
  revisionId: string;
}

interface SyntheticDmaSetupInput {
  request: APIRequestContext;
  webUrl: string;
  material: ExactRevision;
  materialState: ExactRevision;
  processingOutput: ExactRevision;
}

interface SyntheticRelaxationSetupInput {
  request: APIRequestContext;
  webUrl: string;
  material: ExactRevision;
  materialState: ExactRevision;
  testData: ExactRevision;
}

interface PlanResponse {
  plan_id: string;
  current_revision: { id: string; content_hash: string };
}

interface ReviewRequestResponse {
  review_request_id: string;
}

async function demoToken(
  request: APIRequestContext,
  webUrl: string,
  persona: "administrator" | "plan_author" | "reviewer",
): Promise<string> {
  const response = await request.get(`${webUrl}/api/v1/demo-identity/token?persona=${persona}`);
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { access_token: string }).access_token;
}

function authorization(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

function parameterBounds(termCount: number) {
  const truthTau = 1 / (2 * Math.PI);
  const tauStarts = termCount === 1
    ? [truthTau]
    : Array.from({ length: termCount }, (_, index) => 10 ** (-10 + (12 * index / (termCount - 1))));
  if (termCount > 1) {
    const closest = tauStarts.reduce(
      (best, value, index) => Math.abs(Math.log10(value) - Math.log10(truthTau))
        < Math.abs(Math.log10(tauStarts[best]) - Math.log10(truthTau)) ? index : best,
      0,
    );
    tauStarts[closest] = truthTau;
    tauStarts.sort((left, right) => left - right);
  }
  return [
    { name: "G_inf_pa", lower: 10_000, start: 1_000_000, upper: 10_000_000, unit: "Pa", transform: "ln" },
    ...Array.from({ length: termCount }, (_, index) => ({
      name: `G_${index + 1}_pa`,
      lower: 1,
      start: 2_000_000 / termCount,
      upper: 10_000_000,
      unit: "Pa",
      transform: "ln",
    })),
    ...tauStarts.map((start, index) => {
      const lowerBoundary = index === 0
        ? start / 100
        : Math.sqrt(tauStarts[index - 1] * start) * 1.0001;
      const upperBoundary = index === tauStarts.length - 1
        ? start * 100
        : Math.sqrt(start * tauStarts[index + 1]) / 1.0001;
      return {
        name: `tau_${index + 1}_s`,
        lower: lowerBoundary,
        start,
        upper: upperBoundary,
        unit: "s",
        transform: "ln",
      };
    }),
  ];
}

/**
 * Restore the exact reviewed setup for whichever immutable revision the repeated
 * stale-input browser journey left current. This keeps the acceptance flow
 * repeatable without weakening the production exact-revision resolver.
 */
export async function ensureSyntheticRelaxationFitSetup({
  request,
  webUrl,
  material,
  materialState,
  testData,
}: SyntheticRelaxationSetupInput): Promise<void> {
  const [administratorToken, authorToken, reviewerToken] = await Promise.all([
    demoToken(request, webUrl, "administrator"),
    demoToken(request, webUrl, "plan_author"),
    demoToken(request, webUrl, "reviewer"),
  ]);
  const exactContext = {
    material: { id: material.id, revision_id: material.revisionId },
    material_state: { id: materialState.id, revision_id: materialState.revisionId },
    test_data: { id: testData.id, revision_id: testData.revisionId },
    processing_output: null,
    input_mode: "relaxation",
  };
  const resolvedResponse = await request.post(
    `${webUrl}/api/v1/linear-viscoelastic-calibration-plans/resolve`,
    { headers: authorization(administratorToken), data: exactContext },
  );
  expect(resolvedResponse.ok(), await resolvedResponse.text()).toBeTruthy();
  const resolved = (await resolvedResponse.json()) as {
    matches: Array<{ approval: { state: string } }>;
  };
  if (resolved.matches.some((match) => match.approval.state === "active")) return;

  const termCounts = Array.from({ length: 10 }, (_, index) => index + 1);
  const bounds = Object.fromEntries(termCounts.map((term) => [String(term), parameterBounds(term)]));
  const excluded = new Set([4, 20, 36]);
  const holdout = new Set(Array.from({ length: 5 }, (_, index) => index + 38));
  const planResponse = await request.post(
    `${webUrl}/api/v1/linear-viscoelastic-calibration-plans`,
    {
      headers: {
        ...authorization(authorToken),
        "Idempotency-Key": `polymer-relaxation-ui-${testData.revisionId}`,
      },
      data: {
        setup_name: "Reviewed synthetic relaxation comparison",
        ...exactContext,
        processing_output: undefined,
        selected_temperature_k: 296.15,
        candidate_scope_mode: "automatic",
        point_dispositions: Array.from({ length: 43 }, (_, ordinal) => ({
          ordinal,
          partition: excluded.has(ordinal)
            ? "EXCLUDED"
            : holdout.has(ordinal) ? "HOLDOUT" : "CALIBRATION",
          exclusion_reason: excluded.has(ordinal)
            ? "Reserved synthetic non-production exclusion"
            : null,
        })),
        availability: {
          ramp: "NOT_PROVIDED",
          sweep: "NOT_PROVIDED",
          preconditioning: "NOT_PROVIDED",
          linear_range: "NOT_PROVIDED",
        },
        term_counts: termCounts,
        parameter_bounds: bounds,
        start_vectors: Object.fromEntries(termCounts.map((term) => [
          String(term),
          [bounds[String(term)].map((item) => item.start)],
        ])),
        weights: {
          relaxation_weight: "1",
          dma_storage_weight: "0.5",
          dma_loss_weight: "0.5",
          relaxation_scale_pa: "1000000000",
          dma_storage_scale_pa: "1000000000",
          dma_loss_scale_pa: "1000000000",
          q_rule_version: "equal_per_point@1.0.0",
        },
        optimizer: {
          method: "trf",
          x_scale: "jac",
          transform: "ln",
          ftol: 1e-8,
          xtol: 1e-8,
          gtol: 1e-8,
          max_nfev: 5000,
        },
        recommendation_policy: "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0",
        change_reason: "Review the exact synthetic relaxation input for browser acceptance.",
      },
    },
  );
  expect(planResponse.ok(), await planResponse.text()).toBeTruthy();
  const plan = (await planResponse.json()) as PlanResponse;

  const reviewResponse = await request.post(`${webUrl}/api/v1/review-requests`, {
    headers: authorization(administratorToken),
    data: {
      classification: "internal",
      aggregate_type: "modeling.linear_viscoelastic_calibration_plan",
      aggregate_id: plan.plan_id,
      revision_id: plan.current_revision.id,
      manifest_sha256: plan.current_revision.content_hash,
      reason: "Submit the exact synthetic relaxation setup for browser acceptance.",
    },
  });
  expect(reviewResponse.ok(), await reviewResponse.text()).toBeTruthy();
  const review = (await reviewResponse.json()) as ReviewRequestResponse;

  const decisionResponse = await request.post(
    `${webUrl}/api/v1/review-requests/${review.review_request_id}/decisions`,
    {
      headers: authorization(reviewerToken),
      data: {
        expected_manifest_sha256: plan.current_revision.content_hash,
        decision: "approved",
        reason: "Approve the fixture-declared synthetic relaxation setup.",
      },
    },
  );
  expect(decisionResponse.ok(), await decisionResponse.text()).toBeTruthy();
}

/**
 * Establish the external governance precondition for the synthetic DMA browser journey.
 * This is deliberately test-only: production users never receive an automatic approval,
 * and the application still resolves one exact reviewed Processing Output revision.
 */
export async function approveSyntheticDmaFitSetup({
  request,
  webUrl,
  material,
  materialState,
  processingOutput,
}: SyntheticDmaSetupInput): Promise<void> {
  const [administratorToken, authorToken, reviewerToken] = await Promise.all([
    demoToken(request, webUrl, "administrator"),
    demoToken(request, webUrl, "plan_author"),
    demoToken(request, webUrl, "reviewer"),
  ]);
  const termCounts = Array.from({ length: 10 }, (_, index) => index + 1);
  const bounds = Object.fromEntries(termCounts.map((term) => [String(term), parameterBounds(term)]));
  const planResponse = await request.post(
    `${webUrl}/api/v1/linear-viscoelastic-calibration-plans/from-processing-output`,
    {
      headers: {
        ...authorization(authorToken),
        "Idempotency-Key": `polymer-dma-ui-${processingOutput.revisionId}`,
      },
      data: {
        setup_name: "Reviewed synthetic DMA comparison",
        material: { id: material.id, revision_id: material.revisionId },
        material_state: { id: materialState.id, revision_id: materialState.revisionId },
        input_mode: "dma_frequency_master_curve",
        processing_output: { id: processingOutput.id, revision_id: processingOutput.revisionId },
        candidate_scope_mode: "automatic",
        availability: {
          ramp: "NOT_PROVIDED",
          sweep: "PROVIDED",
          preconditioning: "NOT_PROVIDED",
          linear_range: "NOT_PROVIDED",
        },
        term_counts: termCounts,
        parameter_bounds: bounds,
        start_vectors: Object.fromEntries(termCounts.map((term) => [
          String(term),
          [bounds[String(term)].map((item) => item.start)],
        ])),
        weights: {
          relaxation_weight: "1",
          dma_storage_weight: "0.5",
          dma_loss_weight: "0.5",
          relaxation_scale_pa: "1000000",
          dma_storage_scale_pa: "1000000",
          dma_loss_scale_pa: "1000000",
          q_rule_version: "equal_per_point@1.0.0",
        },
        optimizer: {
          method: "trf",
          x_scale: "jac",
          transform: "ln",
          ftol: 1e-8,
          xtol: 1e-8,
          gtol: 1e-8,
          max_nfev: 5000,
        },
        recommendation_policy: "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0",
        change_reason: "Review the exact synthetic shifted DMA response for browser acceptance.",
      },
    },
  );
  expect(planResponse.ok(), await planResponse.text()).toBeTruthy();
  const plan = (await planResponse.json()) as PlanResponse;

  const reviewResponse = await request.post(`${webUrl}/api/v1/review-requests`, {
    headers: authorization(administratorToken),
    data: {
      classification: "internal",
      aggregate_type: "modeling.linear_viscoelastic_calibration_plan",
      aggregate_id: plan.plan_id,
      revision_id: plan.current_revision.id,
      manifest_sha256: plan.current_revision.content_hash,
      reason: "Submit the exact synthetic DMA calculation setup for browser acceptance.",
    },
  });
  expect(reviewResponse.ok(), await reviewResponse.text()).toBeTruthy();
  const review = (await reviewResponse.json()) as ReviewRequestResponse;

  const decisionResponse = await request.post(
    `${webUrl}/api/v1/review-requests/${review.review_request_id}/decisions`,
    {
      headers: authorization(reviewerToken),
      data: {
        expected_manifest_sha256: plan.current_revision.content_hash,
        decision: "approved",
        reason: "Approve the fixture-declared synthetic DMA calculation setup.",
      },
    },
  );
  expect(decisionResponse.ok(), await decisionResponse.text()).toBeTruthy();

  const approvalResponse = await request.get(
    `${webUrl}/api/v1/linear-viscoelastic-calibration-plans/${plan.plan_id}/approval?plan_revision_id=${plan.current_revision.id}`,
    { headers: authorization(reviewerToken) },
  );
  expect(approvalResponse.ok(), await approvalResponse.text()).toBeTruthy();
  expect((await approvalResponse.json()) as { state: string }).toMatchObject({ state: "active" });
}
