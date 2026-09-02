import type { Dispatch } from "react";

import type { ApiConfig } from "../../../shared/api";
import {
  getLinearViscoelasticRecommendation,
  getLinearViscoelasticResponseResiduals,
  getLinearViscoelasticRun,
  listLinearViscoelasticCandidates,
  queueLinearViscoelasticRun,
} from "../api/linear-viscoelastic-calibration-api";
import type {
  LinearViscoelasticPlanResponse,
  LinearViscoelasticRunResponse,
} from "../model/linear-viscoelastic-calibration-contracts";
import {
  terminalRunStatus,
  type LinearViscoelasticCalibrationAction,
} from "../model/linear-viscoelastic-calibration-state";
import { linearViscoelasticErrorMessage } from "./linear-viscoelastic-calibration-guards";

interface ExecuteLinearViscoelasticRunOptions {
  config: ApiConfig;
  plan: LinearViscoelasticPlanResponse;
  dispatch: Dispatch<LinearViscoelasticCalibrationAction>;
  isCurrent: () => boolean;
}

export async function executeLinearViscoelasticRun({
  config,
  plan,
  dispatch,
  isCurrent,
}: ExecuteLinearViscoelasticRunOptions): Promise<void> {
  dispatch({ type: "RUN_START" });
  try {
    const accepted = await queueLinearViscoelasticRun(config, plan.plan_id, {
      plan_revision_id: plan.current_revision.id,
      change_reason: "Execute the exact governed polymer calibration Plan",
    });
    if (!isCurrent()) return;
    const acceptedRun: LinearViscoelasticRunResponse = {
      run_id: accepted.data.run_id,
      plan_revision_id: plan.current_revision.id,
      status: accepted.data.status,
      attempts: [],
      candidates: [],
      recommendation: null,
      failure_code: null,
      failure_detail: null,
      recovery_hint: null,
      execution_ledger_sha256: "",
    };
    dispatch({ type: "RUN_ACCEPTED", run: acceptedRun });
    let run = acceptedRun;
    for (let attempt = 0; attempt < 120 && !terminalRunStatus(run.status); attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 800));
      run = (await getLinearViscoelasticRun(config, accepted.data.run_id)).data;
      if (!isCurrent()) return;
      dispatch({ type: "RUN_UPDATE", run });
    }
    if (run.status === "succeeded") {
      const [candidateResult, recommendationResult, responseEvidenceResult] = await Promise.all([
        listLinearViscoelasticCandidates(config, run.run_id),
        getLinearViscoelasticRecommendation(config, run.run_id),
        getLinearViscoelasticResponseResiduals(config, run.run_id),
      ]);
      if (!isCurrent()) return;
      dispatch({
        type: "RUN_SUCCEEDED",
        run,
        candidates: candidateResult.data,
        recommendation: recommendationResult.data,
        responseEvidence: responseEvidenceResult.data,
      });
    } else if (!terminalRunStatus(run.status)) {
      dispatch({
        type: "ERROR",
        error: "The Run did not reach a terminal state within the observation window.",
        recoveryHint: "Try observing this calculation again. If it still does not finish, start a new calculation.",
      });
    } else {
      dispatch({ type: "RUN_FAILED", run });
    }
  } catch (cause) {
    if (isCurrent()) {
      dispatch({
        type: "ERROR",
        error: linearViscoelasticErrorMessage(cause),
        recoveryHint: "The current setup is preserved. Retry the calculation.",
      });
    }
  }
}
