import {
  downloadNeutralHyperelasticMappingReport,
  downloadNeutralHyperelasticSolverCard,
  downloadSolverCard,
  getNeutralSolverCard,
  getNeutralSolverMappingReport,
  getSolverCard,
  previewNeutralHyperelasticSolverCard,
  previewSolverCard,
  type ApiConfig,
  type SolverCardDownload,
} from "./api";
import type { ExportTarget, MappingItem, MappingStatus } from "./types";

export type SolverCardKind = "solver_card" | "neutral_solver_card";

export interface SolverCardSummary {
  id: string;
  revisionId: string;
  kind: SolverCardKind;
  label: string;
  solver: "Abaqus" | "OpenRadioss" | "Solver";
  extension: ".inp" | ".rad" | ".txt";
}

export type DeliveryMappingDisposition = "direct" | "review" | "blocked";

export interface SolverCardEvidence {
  card: SolverCardSummary;
  target: ExportTarget;
  lifecycleState: string;
  revisionNo: number;
  mappingItems: MappingItem[];
  mappingReportDocument: unknown;
  mappingReportSha256: string;
  cardSha256: string | null;
  solverMaterialId: number;
  materialName: string;
  disposition: DeliveryMappingDisposition;
}

export interface DeliveryActivity {
  version: 1;
  action: "preview" | "download";
  occurredAt: string;
  materialId: string;
  materialRevisionId: string;
  materialLabel: string;
  cardId: string;
  cardRevisionId: string;
  cardLabel: string;
  solver: SolverCardSummary["solver"];
  extension: SolverCardSummary["extension"];
}

const ACTIVITY_STORAGE_KEY = "cmp.solver-card.recent-activity.v1";
const MAX_ACTIVITY_ITEMS = 20;

export function mappingDisposition(items: ReadonlyArray<Pick<MappingItem, "status">>): DeliveryMappingDisposition {
  if (items.some((item) => item.status === "unsupported")) return "blocked";
  if (items.some((item) => item.status === "approximated" || item.status === "ignored")) return "review";
  return "direct";
}

function mappingItemsFromStatuses(statuses: Record<string, MappingStatus>): MappingItem[] {
  return Object.entries(statuses).map(([name, status]) => ({
    name,
    ir_path: name,
    target_representation: null,
    status,
    detail: "Recorded on the exact immutable solver-card revision.",
  }));
}

export async function loadSolverCardEvidence(
  config: ApiConfig,
  card: SolverCardSummary,
): Promise<SolverCardEvidence> {
  if (card.kind === "solver_card") {
    const result = await getSolverCard(config, card.id);
    const value = result.data;
    const report = value.current_revision.mapping_report;
    return {
      card,
      target: value.target,
      lifecycleState: value.current_revision.lifecycle_state,
      revisionNo: value.current_revision.revision_no,
      mappingItems: report.items,
      mappingReportDocument: report,
      mappingReportSha256: report.mapping_report_sha256,
      cardSha256: value.current_revision.content.card_sha256,
      solverMaterialId: value.solver_material_id,
      materialName: value.current_revision.content.card_title,
      disposition: report.exportable ? mappingDisposition(report.items) : "blocked",
    };
  }

  const [cardResult, reportResult] = await Promise.all([
    getNeutralSolverCard(config, card.id),
    getNeutralSolverMappingReport(config, card.id),
  ]);
  const value = cardResult.data;
  const report = reportResult.data;
  const items = report.report.items.length
    ? report.report.items
    : mappingItemsFromStatuses(value.current_revision.content.mapping_statuses);
  return {
    card,
    target: value.target,
    lifecycleState: value.current_revision.lifecycle_state,
    revisionNo: value.current_revision.revision_no,
    mappingItems: items,
    mappingReportDocument: report.report,
    mappingReportSha256: report.mapping_report_sha256,
    cardSha256: value.current_revision.content.card_sha256,
    solverMaterialId: value.current_revision.content.solver_material_id,
    materialName: value.current_revision.content.material_name,
    disposition: report.exportable ? mappingDisposition(items) : "blocked",
  };
}

export function previewSolverCardText(
  config: ApiConfig,
  card: SolverCardSummary,
) {
  return card.kind === "neutral_solver_card"
    ? previewNeutralHyperelasticSolverCard(config, card.id)
    : previewSolverCard(config, card.id);
}

export function downloadSolverCardArtifact(
  config: ApiConfig,
  card: SolverCardSummary,
): Promise<{ data: SolverCardDownload; etag: string | null }> {
  return card.kind === "neutral_solver_card"
    ? downloadNeutralHyperelasticSolverCard(config, card.id)
    : downloadSolverCard(config, card.id);
}

export async function downloadSolverMappingArtifact(
  config: ApiConfig,
  evidence: SolverCardEvidence,
): Promise<{ blob: Blob; filename: string }> {
  if (evidence.card.kind === "neutral_solver_card") {
    return (await downloadNeutralHyperelasticMappingReport(config, evidence.card.id)).data;
  }
  return {
    blob: new Blob(
      [JSON.stringify(evidence.mappingReportDocument, null, 2)],
      { type: "application/json" },
    ),
    filename: `mapping-report-${evidence.card.id}.json`,
  };
}

function isDeliveryActivity(value: unknown): value is DeliveryActivity {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return item.version === 1
    && (item.action === "preview" || item.action === "download")
    && typeof item.occurredAt === "string"
    && !Number.isNaN(Date.parse(item.occurredAt))
    && ["materialId", "materialRevisionId", "materialLabel", "cardId", "cardRevisionId", "cardLabel", "solver", "extension"]
      .every((key) => typeof item[key] === "string");
}

export function loadDeliveryActivities(): DeliveryActivity[] {
  if (typeof window === "undefined") return [];
  try {
    const value = JSON.parse(window.sessionStorage.getItem(ACTIVITY_STORAGE_KEY) ?? "[]") as unknown;
    if (!Array.isArray(value)) return [];
    return value.filter(isDeliveryActivity).slice(0, MAX_ACTIVITY_ITEMS);
  } catch {
    return [];
  }
}

export function recordDeliveryActivity(
  activity: Omit<DeliveryActivity, "version" | "occurredAt">,
): DeliveryActivity[] {
  if (typeof window === "undefined") return [];
  const entry: DeliveryActivity = {
    ...activity,
    version: 1,
    occurredAt: new Date().toISOString(),
  };
  const next = [
    entry,
    ...loadDeliveryActivities().filter(
      (item) => item.action !== entry.action || item.cardId !== entry.cardId,
    ),
  ].slice(0, MAX_ACTIVITY_ITEMS);
  try {
    window.sessionStorage.setItem(ACTIVITY_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Delivery must not fail when browser-local recent activity is unavailable.
  }
  return next;
}
