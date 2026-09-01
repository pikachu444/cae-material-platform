import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { ApiConfig } from "../../../shared/api";
import {
  getLinearViscoelasticPlan,
  resolveLinearViscoelasticPlanContext,
} from "../api/linear-viscoelastic-calibration-api";
import type {
  LinearViscoelasticPlanContextMatch,
  LinearViscoelasticPlanContextRequest,
  LinearViscoelasticPlanResponse,
} from "../model/linear-viscoelastic-calibration-contracts";

export type LinearViscoelasticApprovedSetupStatus =
  | "unavailable"
  | "loading"
  | "missing"
  | "multiple"
  | "ready"
  | "error";

interface ApprovedSetupState {
  status: LinearViscoelasticApprovedSetupStatus;
  matches: LinearViscoelasticPlanContextMatch[];
  selected: LinearViscoelasticPlanContextMatch | null;
  plan: LinearViscoelasticPlanResponse | null;
  error: string | null;
}

const EMPTY_STATE: ApprovedSetupState = {
  status: "unavailable",
  matches: [],
  selected: null,
  plan: null,
  error: null,
};

function errorMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Approved calculation setup could not be loaded.";
}

function contextKey(context: LinearViscoelasticPlanContextRequest | null): string {
  if (!context) return "";
  return [
    context.material.id,
    context.material.revision_id,
    context.material_state.id,
    context.material_state.revision_id,
    context.test_data.id,
    context.test_data.revision_id,
    context.processing_output?.id ?? "",
    context.processing_output?.revision_id ?? "",
    context.input_mode,
  ].join(":");
}

export function useLinearViscoelasticApprovedSetup(
  config: ApiConfig,
  context: LinearViscoelasticPlanContextRequest | null,
) {
  const [state, setState] = useState<ApprovedSetupState>(EMPTY_STATE);
  const [reload, setReload] = useState(0);
  const requestSequence = useRef(0);
  const exactContextKey = contextKey(context);

  useEffect(() => {
    const sequence = ++requestSequence.current;
    setState(context
      ? { ...EMPTY_STATE, status: "loading" }
      : EMPTY_STATE);
    if (!context) return;

    void resolveLinearViscoelasticPlanContext(config, context)
      .then(async (result) => {
        if (sequence !== requestSequence.current) return;
        const matches = result.data.matches.filter((item) => item.approval.state === "active");
        if (!matches.length) {
          setState({ ...EMPTY_STATE, status: "missing" });
          return;
        }
        if (matches.length > 1) {
          setState({ ...EMPTY_STATE, status: "multiple", matches });
          return;
        }
        const selected = matches[0];
        const planResult = await getLinearViscoelasticPlan(config, selected.plan_id);
        if (sequence !== requestSequence.current) return;
        if (planResult.data.current_revision.id !== selected.plan_revision_id
          || planResult.data.current_revision.content_hash !== selected.plan_sha256) {
          throw new Error("The approved setup no longer matches its exact Plan revision.");
        }
        setState({ status: "ready", matches, selected, plan: planResult.data, error: null });
      })
      .catch((cause: unknown) => {
        if (sequence === requestSequence.current) {
          setState({ ...EMPTY_STATE, status: "error", error: errorMessage(cause) });
        }
      });

    return () => { requestSequence.current += 1; };
  }, [config.accessToken, config.baseUrl, exactContextKey, reload]);

  const choose = useCallback((planRevisionId: string) => {
    const selected = state.matches.find((item) => item.plan_revision_id === planRevisionId);
    if (!selected || selected.approval.state !== "active") return;
    const sequence = ++requestSequence.current;
    setState((current) => ({ ...current, status: "loading", selected, plan: null, error: null }));
    void getLinearViscoelasticPlan(config, selected.plan_id)
      .then((result) => {
        if (sequence !== requestSequence.current) return;
        if (result.data.current_revision.id !== selected.plan_revision_id
          || result.data.current_revision.content_hash !== selected.plan_sha256) {
          throw new Error("The chosen setup no longer matches its exact Plan revision.");
        }
        setState((current) => ({ ...current, status: "ready", selected, plan: result.data, error: null }));
      })
      .catch((cause: unknown) => {
        if (sequence === requestSequence.current) {
          setState((current) => ({ ...current, status: "error", plan: null, error: errorMessage(cause) }));
        }
      });
  }, [config, state.matches]);
  const retry = useCallback(() => setReload((value) => value + 1), []);

  return useMemo(() => ({ ...state, choose, retry }), [choose, retry, state]);
}
