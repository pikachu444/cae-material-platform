import {
  createReviewRequest,
  listReviewRequests,
} from "../../activity";
import type { ReviewRequestResponse } from "../../activity/contracts";
import type { ApiConfig } from "../../../shared/api";
import type { LinearViscoelasticPlanResponse } from "../model/linear-viscoelastic-calibration-contracts";

export const LINEAR_VISCOELASTIC_PLAN_REVIEW_TYPE = "modeling.linear_viscoelastic_calibration_plan";

/** Reuses an exact existing request after an uncertain response instead of creating a duplicate. */
export async function requestLinearViscoelasticPlanReview(
  config: ApiConfig,
  plan: LinearViscoelasticPlanResponse,
  reason: string,
): Promise<ReviewRequestResponse> {
  const current = plan.current_revision;
  const existing = await listReviewRequests(config, {
    aggregate_type: LINEAR_VISCOELASTIC_PLAN_REVIEW_TYPE,
    aggregate_id: plan.plan_id,
    revision_id: current.id,
    limit: 10,
  });
  const exact = existing.data.items.find((item) => (
    item.aggregate_type === LINEAR_VISCOELASTIC_PLAN_REVIEW_TYPE
    && item.aggregate_id === plan.plan_id
    && item.revision_id === current.id
  ));
  if (exact) return exact;
  return (await createReviewRequest(config, {
    aggregate_type: LINEAR_VISCOELASTIC_PLAN_REVIEW_TYPE,
    aggregate_id: plan.plan_id,
    revision_id: current.id,
    classification: current.classification,
    manifest_sha256: current.content_hash,
    reason,
  })).data;
}
