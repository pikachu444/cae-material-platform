import { useCallback, useEffect, useRef, useState } from "react";
import {
  type ApiConfig,
  defaultApiConfig,
  inspectLocalDemoAccessToken,
  loadApiConfig,
  requestLocalDemoAccessToken,
  saveApiConfig,
} from "../api";

export type ProductSessionStatus = "loading" | "ready" | "signed_out";

export interface ProductSession {
  config: ApiConfig;
  status: ProductSessionStatus;
  retry: () => void;
}

export function ProductSessionBoundary({
  loading,
  onRetry,
}: {
  loading: boolean;
  onRetry: () => void;
}) {
  return (
    <section className="product-session-boundary" aria-live="polite">
      <span className="brand-mark">CMP</span>
      <p className="eyebrow">CAE Material Platform</p>
      <h1>{loading ? "Preparing your workspace…" : "Sign in to continue"}</h1>
      <p>
        {loading
          ? "Loading the Material Database and modeling tools."
          : "The workspace session could not be started."}
      </p>
      {!loading ? (
        <button className="button primary" type="button" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </section>
  );
}

export function useProductSession(): ProductSession {
  const [config, setConfig] = useState<ApiConfig>(() => loadApiConfig());
  const configRef = useRef(config);
  const [status, setStatus] = useState<ProductSessionStatus>(() =>
    config.accessToken.trim() &&
    !inspectLocalDemoAccessToken(config.accessToken)
      ? "ready"
      : "loading",
  );
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    let refreshTimer: number | undefined;

    function scheduleRefresh(
      persona: "administrator" | "user" | "reviewer",
      delay: number,
    ): void {
      refreshTimer = window.setTimeout(
        () => void refreshDemoSession(persona),
        delay,
      );
    }

    async function refreshDemoSession(
      persona: "administrator" | "user" | "reviewer",
    ): Promise<void> {
      try {
        const currentConfig = configRef.current;
        const result = await requestLocalDemoAccessToken(
          { baseUrl: currentConfig.baseUrl || defaultApiConfig.baseUrl },
          persona,
        );
        if (!current) return;
        const nextConfig = {
          ...currentConfig,
          accessToken: result.data.access_token,
        };
        configRef.current = nextConfig;
        setConfig(nextConfig);
        saveApiConfig(nextConfig);
        setStatus("ready");
        const refreshAfter =
          Math.max(60, result.data.expires_in_seconds - 120) * 1000;
        scheduleRefresh(result.data.persona ?? persona, refreshAfter);
      } catch {
        if (current) setStatus("signed_out");
      }
    }

    const currentConfig = configRef.current;
    const storedDemoSession = inspectLocalDemoAccessToken(
      currentConfig.accessToken,
    );
    if (currentConfig.accessToken.trim() && !storedDemoSession) {
      setStatus("ready");
    } else if (storedDemoSession && attempt === 0) {
      const refreshAfter = storedDemoSession.expiresAt - Date.now() - 120_000;
      if (refreshAfter > 0) {
        setStatus("ready");
        scheduleRefresh(storedDemoSession.persona, refreshAfter);
      } else {
        setStatus("loading");
        void refreshDemoSession(storedDemoSession.persona);
      }
    } else {
      setStatus("loading");
      void refreshDemoSession(storedDemoSession?.persona ?? "administrator");
    }

    return () => {
      current = false;
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer);
    };
  }, [attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { config, status, retry };
}
