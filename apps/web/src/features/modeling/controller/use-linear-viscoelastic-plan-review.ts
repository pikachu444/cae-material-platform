import { useCallback, useState } from "react";

import type { ApiConfig } from "../../../shared/api";
import type { LinearViscoelasticPlanResponse } from "../model/linear-viscoelastic-calibration-contracts";
import { linearViscoelasticErrorMessage } from "./linear-viscoelastic-calibration-guards";
import { requestLinearViscoelasticPlanReview } from "./request-linear-viscoelastic-plan-review";

export interface LinearViscoelasticPlanReviewState {
  status: "idle" | "submitting" | "pending" | "error";
  plan: LinearViscoelasticPlanResponse | null;
  requestId: string | null;
  error: string | null;
  reason: string;
}

const EMPTY_REVIEW: LinearViscoelasticPlanReviewState = {
  status: "idle",
  plan: null,
  requestId: null,
  error: null,
  reason: "",
};

export function useLinearViscoelasticPlanReview(config: ApiConfig) {
  const [state, setState] = useState(EMPTY_REVIEW);

  const submit = useCallback(async (plan: LinearViscoelasticPlanResponse, reason: string) => {
    setState({ status: "submitting", plan, requestId: null, error: null, reason });
    try {
      const review = await requestLinearViscoelasticPlanReview(config, plan, reason);
      setState({ status: "pending", plan, requestId: review.review_request_id, error: null, reason });
      return { ok: true as const, error: null };
    } catch (cause) {
      const error = linearViscoelasticErrorMessage(cause);
      setState({ status: "error", plan, requestId: null, error, reason });
      return { ok: false as const, error };
    }
  }, [config]);

  const retry = useCallback(() => (
    state.plan && state.reason ? submit(state.plan, state.reason) : Promise.resolve({ ok: false as const, error: "Review request is unavailable." })
  ), [state.plan, state.reason, submit]);
  const clear = useCallback(() => setState(EMPTY_REVIEW), []);

  return { state, submit, retry, clear };
}
