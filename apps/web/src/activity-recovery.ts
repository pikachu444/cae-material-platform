/** Versioned browser-local recovery facts for durable Activity outcomes.
 *
 * Server review/job/receipt/release history remains authoritative.  This store only keeps the
 * exact selection and failure/outcome needed to restore a browser after a failed download; a
 * successful retry resolves the active recovery without deleting historical failure facts.
 */

export const ACTIVITY_RECOVERY_SCHEMA_VERSION = 1 as const;

export type RecoveryArtifactKind =
  | "csv_blob"
  | "test_data_json"
  | "selected_model_json"
  | "solver_card"
  | "receipt_json"
  | "release_manifest";

export interface ActivityRecoveryContext {
  kind: RecoveryArtifactKind;
  recordId?: string;
  recordRevisionId?: string;
  layoutId?: string;
  path: string;
  documentId?: string;
  documentRevisionId?: string;
  materialModelId?: string;
  materialModelRevisionId?: string;
  neutralMaterialId?: string;
  neutralMaterialRevisionId?: string;
  solverCardId?: string;
  solverCardRevisionId?: string;
  materialId?: string;
  materialRevisionId?: string;
  target?: string;
  deliveryId?: string;
  receiptId?: string;
  releaseId?: string;
}

export interface ActivityRecoveryFact {
  schemaVersion: typeof ACTIVITY_RECOVERY_SCHEMA_VERSION;
  id: string;
  principalId: string;
  organizationId: string;
  projectId: string;
  workspace: "materials" | "modeling" | "activity";
  context: ActivityRecoveryContext;
  status: "failed" | "succeeded" | "resolved";
  message: string;
  occurredAt: string;
  resolvedAt?: string;
}

function storageKey(principalId: string, organizationId: string, projectId: string, workspace: string): string {
  return `cmp.activity.recovery.v${ACTIVITY_RECOVERY_SCHEMA_VERSION}:${organizationId}:${projectId}:${principalId}:${workspace}`;
}

function read(key: string): ActivityRecoveryFact[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter((item): item is ActivityRecoveryFact => Boolean(item && typeof item === "object")) : [];
  } catch {
    return [];
  }
}

function write(key: string, facts: ActivityRecoveryFact[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(facts.slice(-200)));
  } catch {
    // Browser quota/privacy failures do not block the server-authoritative Activity surface.
  }
}

function contextKey(context: ActivityRecoveryContext): string {
  const identity = context.kind === "csv_blob"
    ? [context.recordId, context.recordRevisionId, context.layoutId]
      : context.kind === "test_data_json"
        ? [context.documentId, context.documentRevisionId]
      : context.kind === "selected_model_json"
        ? [
          context.materialModelId,
          context.materialModelRevisionId,
          context.neutralMaterialId,
          context.neutralMaterialRevisionId,
          context.target,
        ]
        : context.kind === "solver_card"
          ? [
            context.materialId,
            context.materialRevisionId,
            context.solverCardId,
            context.solverCardRevisionId,
            context.target,
          ]
          : context.kind === "receipt_json"
            ? [context.deliveryId ?? context.receiptId, context.target]
            : [context.releaseId];
  return JSON.stringify([context.kind, identity]);
}

export function readActivityRecoveries(
  principalId: string,
  organizationId: string,
  projectId: string,
  workspace: "materials" | "modeling" | "activity" = "activity",
): ActivityRecoveryFact[] {
  return read(storageKey(principalId, organizationId, projectId, workspace)).sort((a, b) => b.occurredAt.localeCompare(a.occurredAt));
}

export function appendActivityFailure(
  principalId: string,
  organizationId: string,
  projectId: string,
  workspace: "materials" | "modeling" | "activity",
  context: ActivityRecoveryContext,
  message: string,
): ActivityRecoveryFact {
  const key = storageKey(principalId, organizationId, projectId, workspace);
  const fact: ActivityRecoveryFact = {
    schemaVersion: ACTIVITY_RECOVERY_SCHEMA_VERSION,
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
    principalId,
    organizationId,
    projectId,
    workspace,
    context,
    status: "failed",
    message,
    occurredAt: new Date().toISOString(),
  };
  write(key, [...read(key), fact]);
  return fact;
}

export function appendActivityOutcome(
  principalId: string,
  organizationId: string,
  projectId: string,
  workspace: "materials" | "modeling" | "activity",
  context: ActivityRecoveryContext,
  message: string,
): ActivityRecoveryFact {
  const key = storageKey(principalId, organizationId, projectId, workspace);
  const occurredAt = new Date().toISOString();
  const fact: ActivityRecoveryFact = {
    schemaVersion: ACTIVITY_RECOVERY_SCHEMA_VERSION,
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
    principalId,
    organizationId,
    projectId,
    workspace,
    context,
    status: "succeeded",
    message,
    occurredAt,
  };
  const successfulContext = contextKey(context);
  const resolved = read(key).map((item) => (
    item.status === "failed" && contextKey(item.context) === successfulContext
      ? { ...item, status: "resolved" as const, resolvedAt: occurredAt }
      : item
  ));
  write(key, [...resolved, fact]);
  return fact;
}

export function resolveActivityRecovery(
  principalId: string,
  organizationId: string,
  projectId: string,
  workspace: "materials" | "modeling" | "activity",
  recoveryId: string,
): void {
  const key = storageKey(principalId, organizationId, projectId, workspace);
  const resolvedAt = new Date().toISOString();
  write(key, read(key).map((item) => item.id === recoveryId && item.status === "failed" ? { ...item, status: "resolved", resolvedAt } : item));
}
