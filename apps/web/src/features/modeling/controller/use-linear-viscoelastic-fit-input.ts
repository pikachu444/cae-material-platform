import { useEffect, useState } from "react";

import type { ApiConfig } from "../../../shared/api";
import { ApiError } from "../../../shared/api";
import { getProcessedLinearViscoelasticFitInput } from "../api/linear-viscoelastic-calibration-api";
import type { ProcessedLinearViscoelasticFitInput } from "../model/linear-viscoelastic-calibration-contracts";

interface ExactProcessingOutputRef {
  id: string;
  revisionId: string;
}

export interface LinearViscoelasticFitInputState {
  status: "idle" | "loading" | "ready" | "error";
  data: ProcessedLinearViscoelasticFitInput | null;
  error: string | null;
}

const IDLE: LinearViscoelasticFitInputState = { status: "idle", data: null, error: null };

function message(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "The exact DMA / TTS Fit input could not be read.";
}

export function useLinearViscoelasticFitInput(
  config: ApiConfig,
  source?: ExactProcessingOutputRef,
): LinearViscoelasticFitInputState {
  const [state, setState] = useState<LinearViscoelasticFitInputState>(IDLE);

  useEffect(() => {
    let current = true;
    if (!source?.id || !source.revisionId) {
      setState(IDLE);
      return () => { current = false; };
    }
    setState({ status: "loading", data: null, error: null });
    void getProcessedLinearViscoelasticFitInput(config, source.id, source.revisionId)
      .then((result) => {
        if (current) setState({ status: "ready", data: result.data, error: null });
      })
      .catch((cause: unknown) => {
        if (current) setState({ status: "error", data: null, error: message(cause) });
      });
    return () => { current = false; };
  }, [config.accessToken, config.baseUrl, source?.id, source?.revisionId]);

  return state;
}
