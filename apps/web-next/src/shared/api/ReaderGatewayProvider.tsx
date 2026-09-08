import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import type { ReaderGateway } from "./reader-gateway";

export interface ReaderScope {
  mode: "prototype" | "live";
  actorID: string;
  orgID: string;
  projectID: string;
  effectiveAccessFingerprint: string;
  authEpoch: number;
}

export interface ReaderGatewaySession {
  gateway: ReaderGateway;
  scope: ReaderScope;
  scopeKey: string;
  availability: "active" | "session-recovery" | "library-read-only" | "logged-out";
  canRead: boolean;
  changeScope: (changes: Partial<Omit<ReaderScope, "mode">>) => Promise<void>;
  logout: () => Promise<void>;
  handleAuthFailure: (status: 401 | 403) => Promise<"session-recovery" | "library-return">;
}

const ReaderGatewayContext = createContext<ReaderGatewaySession | null>(null);

export function readerScopeKey(scope: ReaderScope): string {
  // Identity/access context is cache material. Tokens and bearer credentials
  // are intentionally excluded.
  return [scope.mode, scope.actorID, scope.orgID, scope.projectID, scope.effectiveAccessFingerprint, `auth:${scope.authEpoch}`].join("|");
}

export function ReaderGatewayProvider({ gateway, children }: PropsWithChildren<{ gateway: ReaderGateway }>) {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<ReaderScope>({
    mode: gateway.mode,
    actorID: gateway.mode === "prototype" ? "prototype-reviewer" : "live-user",
    orgID: "cmp",
    projectID: "rd01",
    effectiveAccessFingerprint: gateway.mode === "prototype" ? "dataset-read+export-read" : "observed-live-access",
    authEpoch: 1,
  });
  const [availability, setAvailability] = useState<ReaderGatewaySession["availability"]>("active");
  const clearQueryState = useCallback(async () => {
    await queryClient.cancelQueries();
    queryClient.clear();
  }, [queryClient]);
  const changeScope = useCallback(async (changes: Partial<Omit<ReaderScope, "mode">>) => {
    await clearQueryState();
    setScope((current) => ({ ...current, ...changes, authEpoch: current.authEpoch + 1 }));
    setAvailability("active");
  }, [clearQueryState]);
  const logout = useCallback(async () => {
    await clearQueryState();
    setScope((current) => ({ ...current, actorID: "anonymous", effectiveAccessFingerprint: "none", authEpoch: current.authEpoch + 1 }));
    setAvailability("logged-out");
  }, [clearQueryState]);
  const handleAuthFailure = useCallback(async (status: 401 | 403) => {
    await clearQueryState();
    if (status === 401) {
      setScope((current) => ({ ...current, actorID: "session-recovery", effectiveAccessFingerprint: "none", authEpoch: current.authEpoch + 1 }));
      setAvailability("session-recovery");
      return "session-recovery" as const;
    }
    setScope((current) => ({ ...current, effectiveAccessFingerprint: "library-read-only", authEpoch: current.authEpoch + 1 }));
    setAvailability("library-read-only");
    return "library-return" as const;
  }, [clearQueryState]);
  const session = useMemo<ReaderGatewaySession>(() => ({ gateway, scope, scopeKey: readerScopeKey(scope), availability, canRead: availability === "active", changeScope, logout, handleAuthFailure }), [availability, changeScope, gateway, handleAuthFailure, logout, scope]);
  return <ReaderGatewayContext.Provider value={session}>{children}</ReaderGatewayContext.Provider>;
}

export function useReaderSession(): ReaderGatewaySession {
  const session = useContext(ReaderGatewayContext);
  if (!session) throw new Error("ReaderGatewayProvider is required");
  return session;
}

export function useReaderGateway(): ReaderGateway { return useReaderSession().gateway; }
export function useReaderScope(): ReaderScope { return useReaderSession().scope; }
