import { useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  getAuthenticatedPrincipal,
  type ApiConfig,
} from "../../../../../shared/api";
import {
  createExactTargetPreview,
  deliverExactTargetPreview,
  downloadSelectedModelNeutralMaterial,
  getReferenceElastoplasticExportCapabilities,
} from "../../../api/modeling-api";
import type { ExportPrerequisite } from "../../../model/export-eligibility";
import type { ModelingSessionEvent, ModelingSessionSummary } from "../../../model/session-controller";
import { exactFitPlotData, type ExactFitPlotData } from "../../../model/fit-output";
import type { FitDecisionSelection } from "../../../model/fit-decision-contract";
import {
  mappingDisposition,
  projectMappingRows,
} from "../../../../../solver-card-delivery";
import { ReviewRequestAction } from "../../../../../review-request-action";
import { appendActivityFailure, appendActivityOutcome, type ActivityRecoveryContext } from "../../../../../activity-recovery";
import { MaterialsScrollRegion } from "../../../../../materials-scroll-rail";
import type {
  CommonProcessingOutputResponse,
  CommonProcessingPreview,
} from "../../../model/common-processing-contracts";
import type {
  ElastoplasticExportCapabilities,
  ExportTarget,
  MappingItem,
  TargetDeliveryResponse,
  TargetDeliveryLinks,
  TargetPreviewResponse,
} from "../../../model/export-contracts";

type CapabilityTarget = ExportTarget & { label?: string };

async function recordModelingRecovery(
  config: ApiConfig,
  context: ActivityRecoveryContext,
  status: "failed" | "succeeded",
  message: string,
): Promise<void> {
  try {
    const principal = await getAuthenticatedPrincipal(config);
    const args = [
      principal.data.principal_id,
      principal.data.organization_id,
      principal.data.project_id,
      "activity" as const,
      context,
      message,
    ] as const;
    if (status === "failed") appendActivityFailure(...args);
    else appendActivityOutcome(...args);
  } catch {
    // The exact download remains server-authoritative when local recovery storage is unavailable.
  }
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Target preview could not be generated.";
}

function sourceKey(session: ModelingSessionSummary | null | undefined): string {
  return [
    session?.processingOutput?.id,
    session?.processingOutput?.revisionId,
    session?.materialModelIr?.id,
    session?.materialModelIr?.revisionId,
    session?.neutralModel?.id,
    session?.neutralModel?.revisionId,
    session?.material?.id,
    session?.material?.revisionId,
    session?.materialState?.id,
    session?.materialState?.revisionId,
  ].join("/");
}

function targetKey(target: ExportTarget): string {
  return `${target.solver}/${target.version}/${target.unit_system}`;
}

function readCapabilityTargets(value: ElastoplasticExportCapabilities | null): CapabilityTarget[] {
  if (!value || typeof value !== "object") return [];
  const raw = (value as { exporters?: unknown }).exporters;
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const result: CapabilityTarget[] = [];
  for (const candidate of raw) {
    if (!candidate || typeof candidate !== "object") continue;
    const item = candidate as Record<string, unknown>;
    if (typeof item.solver !== "string" || !item.solver
      || typeof item.version !== "string" || !item.version
      || typeof item.unit_system !== "string" || !item.unit_system) continue;
    const target: CapabilityTarget = {
      solver: item.solver,
      version: item.version,
      unit_system: item.unit_system,
    };
    if (seen.has(targetKey(target))) continue;
    seen.add(targetKey(target));
    result.push(target);
  }
  return result;
}

function responseMatchesCurrentSource(
  response: TargetPreviewResponse,
  session: ModelingSessionSummary,
  output: CommonProcessingOutputResponse,
): boolean {
  return response.source.processing_output_id === output.processing_output_id
    && response.source.processing_output_revision_id === output.current_revision.id
    && response.source.processing_output_sha256 === output.output_sha256
    && response.source.material_id === session.material?.id
    && response.source.material_revision_id === session.material?.revisionId
    && response.source.material_state_id === session.materialState?.id
    && response.source.material_state_revision_id === session.materialState?.revisionId
    && response.source.material_model_ir_revision_id === session.materialModelIr?.revisionId
    && response.source.neutral_material_id === session.neutralModel?.id
    && response.source.neutral_material_revision_id === session.neutralModel?.revisionId;
}

function responseMatchesRequestedTarget(
  response: TargetPreviewResponse,
  target: ExportTarget,
  solverMaterialId: number,
  materialName: string,
): boolean {
  return response.delivery_status === "preview_only"
    && response.target.solver === target.solver
    && response.target.version === target.version
    && response.target.unit_system === target.unit_system
    && response.target.solver_material_id === solverMaterialId
    && response.target.material_name === materialName;
}

function sameSourceIdentity(
  left: TargetPreviewResponse["source"],
  right: TargetPreviewResponse["source"],
): boolean {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return leftKeys.join(",") === rightKeys.join(",") && Object.keys(right).every((key) => {
    const name = key as keyof TargetPreviewResponse["source"];
    return left[name] === right[name];
  });
}

function sameTargetIdentity(
  left: TargetPreviewResponse["target"],
  right: TargetPreviewResponse["target"],
): boolean {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  return leftKeys.join(",") === rightKeys.join(",")
    && left.solver === right.solver
    && left.version === right.version
    && left.unit_system === right.unit_system
    && left.solver_material_id === right.solver_material_id
    && left.material_name === right.material_name;
}

function expectedDeliveryLinks(response: TargetDeliveryResponse): TargetDeliveryLinks {
  const root = `/api/v1/neutral-solver-cards/${response.solver_card_id}`;
  return {
    solver_card: root,
    preview: `${root}/preview`,
    download: `${root}/download`,
    receipt: `/api/v1/exporting/target-deliveries/${response.receipt_id}`,
  };
}

function deliveryMatchesPreview(
  response: TargetDeliveryResponse,
  current: TargetPreviewResponse,
): boolean {
  const links = response.links;
  const expectedLinks = expectedDeliveryLinks(response);
  const linkKeys = Object.keys(links).sort();
  if (linkKeys.join(",") !== ["download", "preview", "receipt", "solver_card"].join(",")) return false;
  if (!Object.entries(expectedLinks).every(([key, value]) => links[key as keyof TargetDeliveryLinks] === value)) return false;
  return response.delivery_status === "delivered"
    && response.delivery_identity === current.preview_identity
    && response.native_sha256 === current.native_sha256
    && response.mapping_report_sha256 === current.mapping_report_sha256
    && sameSourceIdentity(response.source, current.source)
    && sameTargetIdentity(response.target, current.target);
}

function formatTarget(target: CapabilityTarget): string {
  return target.label ?? `${target.solver} ${target.version} · ${target.unit_system.replaceAll("_", "-")}`;
}

function statusForPreview(preview: TargetPreviewResponse | null, acknowledged: boolean): "Ready to create" | "Review required" | "Cannot create" {
  if (!preview) return "Cannot create";
  const disposition = mappingDisposition(preview.mapping.items);
  if (disposition === "blocked") return "Cannot create";
  if (disposition === "review" && !acknowledged) return "Review required";
  return "Ready to create";
}

function mappingVisibleStatus(status: MappingItem["status"]): string {
  switch (status) {
    case "exact": return "Exact";
    case "transformed": return "Converted";
    case "approximated":
    case "ignored": return "Reviewed";
    case "unsupported": return "Blocked";
    case "not_applicable": return "N/A";
    default: return "Review";
  }
}

function sourceStatus(
  prerequisites: ExportPrerequisite[],
  session: ModelingSessionSummary | null | undefined,
  output: CommonProcessingOutputResponse | undefined,
  fitSourceReady: boolean,
  fitRestoreError: string | null,
): string | null {
  const current = prerequisites
    .filter((item) => item.label !== "Ephemeral target preview producer")
    .every((item) => item.status === "current");
  const refs = Boolean(
    output
      && session?.processingOutput
      && session.material
      && session.materialState
      && session.materialModelIr
      && session.neutralModel,
  );
  if (!current || !refs) return "Select a model in Fit and save the Process result before exporting.";
  if (!fitSourceReady) return `Fit result unavailable${fitRestoreError ? ` · ${fitRestoreError}` : " · Return to Fit and retry"}.`;
  return null;
}

function MappingDetails({ items }: { items: MappingItem[] }) {
  const rows = projectMappingRows(items);
  return <section className="export-mapping mapping-sheet" aria-label="Mapping details">
    <div className="export-context-heading"><h3>Mapping details</h3></div>
    {rows.length ? <MaterialsScrollRegion
      id="modeling-export-mapping-viewport"
      className="mapping-scroll export-mapping-viewport"
      shellClassName="modeling-target-preview-mapping-scroll-shell"
      aria-label="Mapping details"
      tabIndex={0}
    >
      <ul className="export-mapping-list">
        {rows.map((row) => <li className="export-mapping-row" key={`${row.item.name}:${row.item.ir_path}`}>
          <div><strong>{row.quantity}</strong><span>{row.expression}</span></div>
          <span className={`export-mapping-status ${row.item.status}`}>{mappingVisibleStatus(row.item.status)}</span>
        </li>)}
      </ul>
    </MaterialsScrollRegion> : <p className="muted">Mapping details appear after a current preview.</p>}
    {rows.length ? <details className="export-advanced"><summary>Advanced mapping evidence</summary><ul>{rows.map((row) => <li key={`${row.item.name}:${row.item.ir_path}:advanced`}><strong>{row.item.name}</strong><small>{row.item.status} · {row.item.detail}</small><code>{row.item.ir_path}</code></li>)}</ul></details> : null}
  </section>;
}

function domainWithHeadroom(values: number[]): [number, number] {
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum;
  // Keep a visible margin around persisted samples, including the valid
  // constant-series case. The same domain is shared by both curves.
  const padding = span > Number.EPSILON
    ? span * 0.05
    : Math.max(Math.abs(minimum) * 0.05, 0.05);
  return [minimum - padding, maximum + padding];
}

function persistedFitBounds(selection: FitDecisionSelection): [number, number] | null {
  const withBounds = selection as FitDecisionSelection & {
    fitMinimum?: unknown;
    fitMaximum?: unknown;
  };
  if (typeof withBounds.fitMinimum === "number" && Number.isFinite(withBounds.fitMinimum)
    && typeof withBounds.fitMaximum === "number" && Number.isFinite(withBounds.fitMaximum)
    && withBounds.fitMinimum <= withBounds.fitMaximum) {
    return [withBounds.fitMinimum, withBounds.fitMaximum];
  }
  // Unsaved selections expose the same persisted range as a human-readable
  // string.  Use it only as a compatibility fallback; never infer bounds from
  // the rendered samples themselves.
  const match = selection.fitRange.match(
    /^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*[–-]\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)/,
  );
  if (!match) return null;
  const minimum = Number(match[1]);
  const maximum = Number(match[2]);
  return Number.isFinite(minimum) && Number.isFinite(maximum) && minimum <= maximum
    ? [minimum, maximum]
    : null;
}

function filterPersistedSamples(
  x: number[],
  y: number[],
  bounds: [number, number] | null,
): { x: number[]; y: number[] } {
  if (!bounds) return { x: [...x], y: [...y] };
  const [minimum, maximum] = bounds;
  const filteredX: number[] = [];
  const filteredY: number[] = [];
  x.forEach((value, index) => {
    if (value >= minimum && value <= maximum) {
      filteredX.push(value);
      filteredY.push(y[index]);
    }
  });
  return { x: filteredX, y: filteredY };
}

function FitSource({
  preview,
  selection,
  fitSourceReady,
  fitRestoreError,
}: {
  preview: CommonProcessingPreview | null;
  selection: FitDecisionSelection | null;
  fitSourceReady: boolean;
  fitRestoreError: string | null;
}) {
  const plot = useMemo<ExactFitPlotData | null>(() => {
    if (!preview || !selection || !fitSourceReady) return null;
    try {
      return exactFitPlotData(preview, selection);
    } catch {
      return null;
    }
  }, [fitSourceReady, preview, selection]);
  const coordinates = useMemo(() => {
    if (!plot) return null;
    // The persisted values remain in Pa. Convert only the rendered coordinates
    // to MPa, and use one combined y domain for observed and selected curves.
    const bounds = persistedFitBounds(selection!);
    const observedSamples = filterPersistedSamples(plot.observedX, plot.observed, bounds);
    const selectedSamples = filterPersistedSamples(plot.selectedX, plot.selected, bounds);
    const observed = observedSamples.y.map((value) => value / 1_000_000);
    const selected = selectedSamples.y.map((value) => value / 1_000_000);
    const domainX = [...observedSamples.x, ...selectedSamples.x];
    const domainY = [...observed, ...selected];
    // Keep the axis honest if a persisted fit bound excludes every point: no
    // synthetic endpoint is added, and only the original samples determine a
    // fallback domain for the empty paths.
    const [xMin, xMax] = domainWithHeadroom(domainX.length ? domainX : [...plot.observedX, ...plot.selectedX]);
    const [yMin, yMax] = domainWithHeadroom(domainY.length ? domainY : [...plot.observed, ...plot.selected].map((value) => value / 1_000_000));
    const xSpan = Math.max(xMax - xMin, Number.EPSILON);
    const ySpan = Math.max(yMax - yMin, Number.EPSILON);
    const pointCoordinates = (xValues: number[], values: number[]): string => values.map((value, index) => {
      const x = 40 + ((xValues[index] - xMin) / xSpan) * 272;
      const y = 174 - ((value - yMin) / ySpan) * 154;
      return `${x.toFixed(3)},${y.toFixed(3)}`;
    }).join(" ");
    const formatTick = (value: number, axis: "x" | "y"): string => {
      if (axis === "x") {
        const places = Math.abs(xSpan) < 0.1 ? 3 : 2;
        return value.toFixed(places).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
      }
      if (Math.abs(value) >= 10) return Math.round(value).toString();
      return value.toFixed(1).replace(/\.0$/, "");
    };
    return {
      observed: pointCoordinates(observedSamples.x, observed),
      selected: pointCoordinates(selectedSamples.x, selected),
      xTicks: [xMin, xMin + xSpan / 2, xMax].map((value) => ({ value, label: formatTick(value, "x") })),
      yTicks: [yMin, yMin + ySpan / 2, yMax].map((value) => ({ value, label: formatTick(value, "y") })),
    };
  }, [plot, selection]);
  const observedPoints = coordinates?.observed ?? "";
  const selectedPoints = coordinates?.selected ?? "";
  const sourceUnavailable = !fitSourceReady || !plot;
  return <section className="export-fit-source" aria-label="Fit source">
    <div className="export-context-heading"><h3>Fit curve</h3></div>
    {sourceUnavailable ? <div className="export-fit-source-blocked" role="status"><strong>Fit result unavailable</strong><span>{fitRestoreError ?? "Return to Fit and retry before creating a solver card."}</span></div> : <>
      <div className="fit-source-plot" aria-label="True plastic strain and true stress response">
        <svg className="fit-source-graph" role="img" aria-label="True plastic strain and true stress response" viewBox="0 0 320 210" preserveAspectRatio="xMidYMid meet">
          <title>True stress versus true plastic strain</title>
          <desc>Test Data and selected model curves; stress displayed in MPa.</desc>
          <rect className="fit-source-frame" x="40" y="20" width="272" height="154" />
          <g className="fit-source-grid" aria-hidden="true">
            {coordinates?.yTicks.map((tick) => <line key={`y-grid-${tick.value}`} x1="40" x2="312" y1={174 - ((tick.value - (coordinates.yTicks[0]?.value ?? 0)) / Math.max((coordinates.yTicks.at(-1)?.value ?? 1) - (coordinates.yTicks[0]?.value ?? 0), Number.EPSILON)) * 154} y2={174 - ((tick.value - (coordinates.yTicks[0]?.value ?? 0)) / Math.max((coordinates.yTicks.at(-1)?.value ?? 1) - (coordinates.yTicks[0]?.value ?? 0), Number.EPSILON)) * 154} />)}
            {coordinates?.xTicks.map((tick) => <line key={`x-grid-${tick.value}`} y1="20" y2="174" x1={40 + ((tick.value - (coordinates.xTicks[0]?.value ?? 0)) / Math.max((coordinates.xTicks.at(-1)?.value ?? 1) - (coordinates.xTicks[0]?.value ?? 0), Number.EPSILON)) * 272} x2={40 + ((tick.value - (coordinates.xTicks[0]?.value ?? 0)) / Math.max((coordinates.xTicks.at(-1)?.value ?? 1) - (coordinates.xTicks[0]?.value ?? 0), Number.EPSILON)) * 272} />)}
          </g>
          <g className="fit-source-ticks" aria-hidden="true">
            {coordinates?.yTicks.map((tick, index) => {
              const y = 174 - (index / Math.max((coordinates.yTicks.length - 1), 1)) * 154;
              return <g key={`y-tick-${tick.value}`}><line x1="36" x2="40" y1={y} y2={y} /><text className="fit-source-tick" x="33" y={y + 3} textAnchor="end">{tick.label}</text></g>;
            })}
            {coordinates?.xTicks.map((tick, index) => {
              const x = 40 + (index / Math.max((coordinates.xTicks.length - 1), 1)) * 272;
              return <g key={`x-tick-${tick.value}`}><line y1="174" y2="178" x1={x} x2={x} /><text className="fit-source-tick" x={x} y="189" textAnchor="middle">{tick.label}</text></g>;
            })}
          </g>
          <text className="fit-source-axis-title" x="40" y="12">True stress (MPa)</text>
          <text className="fit-source-axis-title" x="176" y="205" textAnchor="middle">True plastic strain [1]</text>
          {observedPoints ? <polyline className="fit-source-observed" points={observedPoints} /> : null}
          {selectedPoints ? <polyline className="fit-source-selected" points={selectedPoints} /> : null}
          <g className="fit-source-svg-legend fit-source-legend" aria-label="Curve legend">
            <line className="fit-source-legend-line fit-source-legend-observed" x1="214" x2="230" y1="136" y2="136" />
            <text x="234" y="139">Test Data</text>
            <line className="fit-source-legend-line fit-source-legend-selected" x1="214" x2="230" y1="150" y2="150" />
            <text x="234" y="153">Selected hardening</text>
          </g>
        </svg>
      </div>
    </>}
  </section>;
}

function ExactEvidence({
  session,
  output,
  fitPreview,
  selection,
  preview,
}: {
  session: ModelingSessionSummary | null | undefined;
  output: CommonProcessingOutputResponse | undefined;
  fitPreview: CommonProcessingPreview | null;
  selection: FitDecisionSelection | null;
  preview: TargetPreviewResponse | null;
}) {
  const stages = fitPreview?.stages ?? [];
  const stageSummary = stages.map((stage) => {
    const quantities = [...new Set(stage.series.map((series) => `${series.quantity} [${series.unit}]`))];
    const candidates = stage.fit_candidates?.length ?? 0;
    return `${stage.ordinal}: ${stage.method_id} · ${quantities.join(", ")}${candidates ? ` · ${candidates} candidates` : ""}`;
  });
  const fitDecision = output?.fit_decision;
  const mappingProfile = output?.mapping_profile;
  return <details className="export-advanced"><summary>Technical details</summary><dl>
    {output ? <>
      <dt>Processing Output</dt><dd><code>{output.processing_output_id} · {output.current_revision.id}</code></dd>
      <dt>Output SHA-256</dt><dd><code>{output.output_sha256}</code></dd>
      <dt>Mapping Profile</dt><dd>{mappingProfile ? <>{session?.mappingProfile?.label ?? "Saved Mapping Profile"} · r{session?.mappingProfile?.revisionNo ?? output.current_revision?.revision_no ?? "?"}<code>{mappingProfile.aggregate_id} · {mappingProfile.revision_id} · {output.mapping_profile_sha256 ?? "unavailable"}</code></> : "Exact Mapping Profile evidence unavailable"}</dd>
      <dt>Recipe</dt><dd>{session?.recipe ? `${session.recipe.label} · r${session.recipe.revisionNo}` : <><strong>No separate saved Recipe</strong><code>{JSON.stringify(output.steps)}</code></>}</dd>
      <dt>Fit stages</dt><dd>{stageSummary.length ? <ul>{stageSummary.map((item) => <li key={item}>{item}</li>)}</ul> : "No saved Fit stages"}</dd>
      <dt>Selected Fit</dt><dd>{selection?.displayLabel ?? fitDecision?.candidate_key ?? "Not selected"}<code>{fitDecision ? `${fitDecision.mode} · ${fitDecision.metric_definition}=${fitDecision.metric_value}` : ""}</code></dd>
      <dt>Applicability / fit range</dt><dd>{selection?.fitRange ?? (fitDecision ? `${fitDecision.fit_minimum}–${fitDecision.fit_maximum} · ${fitDecision.extrapolation_policy}` : "Unavailable")}</dd>
      <dt>Material Model IR</dt><dd><code>{session?.materialModelIr?.id ?? "unavailable"} · {session?.materialModelIr?.revisionId ?? "unavailable"}</code></dd>
      <dt>Neutral revision</dt><dd><code>{session?.neutralModel?.id ?? "unavailable"} · {session?.neutralModel?.revisionId ?? "unavailable"}</code></dd>
    </> : <dt>Exact Fit evidence</dt>}
    {!output ? <dd>Exact Fit evidence unavailable.</dd> : null}
    {preview ? <><dt>Accepted C1 mapping</dt><dd><code>{preview.mapping_report_sha256}</code><span>{preview.mapping.items.length} mapping dispositions</span></dd></> : null}
  </dl></details>;
}

function DeliveryDetails({ delivery }: { delivery: TargetDeliveryResponse | null }) {
  if (!delivery) return null;
  const resources: Array<[keyof TargetDeliveryLinks, string]> = [
    ["solver_card", "solver_card"],
    ["preview", "preview"],
    ["download", "download"],
    ["receipt", "receipt"],
  ];
  return <details className="export-delivery-details export-advanced">
    <summary>Delivery details</summary>
    <dl>
      <dt>Solver card</dt><dd><code>{delivery.solver_card_id}</code></dd>
      <dt>Card revision</dt><dd><code>{delivery.solver_card_revision_id}</code></dd>
      <dt>Receipt</dt><dd><code>{delivery.receipt_id}</code></dd>
      <dt>Native digest</dt><dd><code>{delivery.native_sha256}</code></dd>
      <dt>Mapping digest</dt><dd><code>{delivery.mapping_report_sha256}</code></dd>
      <dt>API resources</dt><dd><ul>{resources.map(([key, label]) => <li key={key}><a href={delivery.links[key]}>{label}</a></li>)}</ul></dd>
    </dl>
  </details>;
}

export function ModelingTargetPreview({
  config,
  session,
  output,
  prerequisites,
  onSessionEvent,
  capabilityManifest,
  onNavigate,
  fitPreview = null,
  fitSelection = null,
  fitSourceReady = true,
  fitRestoreError = null,
  onRetryFitSource,
}: {
  config: ApiConfig;
  session: ModelingSessionSummary | null | undefined;
  output: CommonProcessingOutputResponse | undefined;
  prerequisites: ExportPrerequisite[];
  onSessionEvent?: (event: ModelingSessionEvent) => void;
  capabilityManifest?: ElastoplasticExportCapabilities;
  onNavigate?: (path: string) => void;
  fitPreview?: CommonProcessingPreview | null;
  fitSelection?: FitDecisionSelection | null;
  fitSourceReady?: boolean;
  fitRestoreError?: string | null;
  onRetryFitSource?: () => void;
}) {
  const [capability, setCapability] = useState<ElastoplasticExportCapabilities | null>(capabilityManifest ?? null);
  const [capabilityError, setCapabilityError] = useState<string | null>(null);
  const [capabilityLoading, setCapabilityLoading] = useState(!capabilityManifest);
  const [capabilityReload, setCapabilityReload] = useState(0);
  const [targetKeyValue, setTargetKeyValue] = useState("");
  const [solverMaterialId, setSolverMaterialId] = useState("1");
  const [materialName, setMaterialName] = useState("");
  const [preview, setPreview] = useState<TargetPreviewResponse | null>(null);
  const [lastValidPreview, setLastValidPreview] = useState<TargetPreviewResponse | null>(null);
  const [previewStale, setPreviewStale] = useState(false);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [delivery, setDelivery] = useState<TargetDeliveryResponse | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState<"preview" | "delivery" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deliveryError, setDeliveryError] = useState(false);
  const [neutralDownloadBusy, setNeutralDownloadBusy] = useState(false);
  const requestGeneration = useRef(0);
  const currentSourceKey = sourceKey(session);

  useEffect(() => {
    if (capabilityManifest) {
      setCapability(capabilityManifest);
      setCapabilityLoading(false);
      setCapabilityError(null);
      return;
    }
    let active = true;
    setCapabilityLoading(true);
    setCapabilityError(null);
    void getReferenceElastoplasticExportCapabilities(config).then((result) => {
      if (!active) return;
      setCapability(result.data);
      setCapabilityLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setCapabilityError(errorMessage(cause));
      setCapabilityLoading(false);
    });
    return () => { active = false; };
  }, [capabilityManifest, capabilityReload, config]);

  const targets = useMemo(() => readCapabilityTargets(capability), [capability]);
  const selectedTarget = targets.find((target) => targetKey(target) === targetKeyValue) ?? null;
  const sourceBlocked = sourceStatus(prerequisites, session, output, fitSourceReady, fitRestoreError);
  const currentPreview = preview ?? lastValidPreview;
  const currentStatus = capabilityLoading || capabilityError || !targets.length || sourceBlocked || !selectedTarget
    ? "Cannot create"
    : previewStale ? "Review required" : statusForPreview(currentPreview, acknowledged);
  const requiresAcknowledgement = currentPreview
    ? mappingDisposition(currentPreview.mapping.items) === "review"
    : false;
  const canPreview = Boolean(
    !capabilityLoading
      && !capabilityError
      && targets.length
      && selectedTarget
      && !sourceBlocked
      && /^[1-9][0-9]{0,9}$/.test(solverMaterialId)
      && /^[A-Za-z][A-Za-z0-9_-]{0,79}$/.test(materialName)
      && !busy,
  );
  const canDeliver = Boolean(
    currentPreview
      && !delivery
      && !previewStale
      && currentPreview.delivery_status === "preview_only"
      && currentStatus === "Ready to create"
      && !busy,
  );
  const primaryAction = delivery
    ? "Open solver card"
    : sourceBlocked || capabilityLoading || capabilityError || !targets.length
      ? null
      : deliveryError && currentPreview
        ? "Retry create"
        : currentPreview && !previewStale
          ? "Create solver card"
          : previewFailed || previewStale
            ? "Retry Export check"
            : "Run Export check";
  const primaryActionDisabled = primaryAction === "Open solver card"
    ? false
    : primaryAction === "Create solver card" || primaryAction === "Retry create"
      ? !canDeliver
      : !canPreview;

  async function downloadSelectedNeutral(): Promise<void> {
    if (!session?.materialModelIr || !session.neutralModel || neutralDownloadBusy) return;
    const context: ActivityRecoveryContext = {
      kind: "selected_model_json",
      path: "/modeling?stage=export",
      materialModelId: session.materialModelIr.id,
      materialModelRevisionId: session.materialModelIr.revisionId,
      neutralMaterialId: session.neutralModel.id,
      neutralMaterialRevisionId: session.neutralModel.revisionId,
    };
    setNeutralDownloadBusy(true);
    setError(null);
    try {
      const result = await downloadSelectedModelNeutralMaterial(
        config,
        session.neutralModel.id,
        session.neutralModel.revisionId,
      );
      triggerBlobDownload(result.data.blob, result.data.filename);
      void recordModelingRecovery(config, context, "succeeded", "Downloaded the exact selected-model Neutral JSON.");
    } catch (cause: unknown) {
      const message = errorMessage(cause);
      setError(message);
      void recordModelingRecovery(config, context, "failed", message);
    } finally {
      setNeutralDownloadBusy(false);
    }
  }

  useEffect(() => {
    requestGeneration.current += 1;
    setPreview(null);
    setLastValidPreview(null);
    setPreviewStale(false);
    setPreviewFailed(false);
    setDelivery(null);
    setAcknowledged(false);
    setDeliveryError(false);
    setError(null);
  }, [currentSourceKey]);

  useEffect(() => {
    if (!selectedTarget && targets.length === 1) {
      setTargetKeyValue(targetKey(targets[0]));
    }
  }, [selectedTarget, targets]);

  function invalidateDownstream(): void {
    requestGeneration.current += 1;
    setPreview(null);
    setLastValidPreview(null);
    setPreviewStale(false);
    setPreviewFailed(false);
    setDelivery(null);
    setAcknowledged(false);
    setDeliveryError(false);
    setError(null);
  }

  function changeTarget(value: string): void {
    // Keep compatibility with older deep links that carried only the solver
    // name while the visible control is now a capability-backed tuple.
    const legacyTarget = targets.find((target) => target.solver === value);
    setTargetKeyValue(legacyTarget ? targetKey(legacyTarget) : value);
    invalidateDownstream();
    onSessionEvent?.({ type: "CHANGE_EXPORT_TARGET" });
  }

  async function generate(): Promise<void> {
    if (!canPreview || !output || !selectedTarget || !session?.processingOutput || !session.neutralModel) return;
    // A changed DOM value must not bypass the fetched capability contract.
    const declared = targets.some((target) => targetKey(target) === targetKey(selectedTarget));
    if (!declared) {
      setError("Selected destination is no longer available from the exporter capability.");
      return;
    }
    const generation = requestGeneration.current + 1;
    requestGeneration.current = generation;
    const requestedTarget: ExportTarget = {
      solver: selectedTarget.solver,
      version: selectedTarget.version,
      unit_system: selectedTarget.unit_system,
    };
    const requestedSolverMaterialId = Number(solverMaterialId);
    const requestedMaterialName = materialName;
    setBusy("preview");
    setError(null);
    try {
      const result = await createExactTargetPreview(config, {
        processing_output_id: session.processingOutput.id,
        processing_output_revision_id: session.processingOutput.revisionId,
        neutral_material_id: session.neutralModel.id,
        neutral_material_revision_id: session.neutralModel.revisionId,
        target: requestedTarget,
        solver_material_id: requestedSolverMaterialId,
        material_name: requestedMaterialName,
      });
      if (generation !== requestGeneration.current) return;
      if (!responseMatchesCurrentSource(result.data, session, output)
        || !responseMatchesRequestedTarget(result.data, requestedTarget, requestedSolverMaterialId, requestedMaterialName)) {
        throw new Error("The server response does not match the current exact Export request.");
      }
      setPreview(result.data);
      setLastValidPreview(result.data);
      setPreviewStale(false);
      setPreviewFailed(false);
      setDelivery(null);
      setAcknowledged(false);
      setDeliveryError(false);
    } catch (cause: unknown) {
      if (generation !== requestGeneration.current) return;
      setError(errorMessage(cause));
      // A failed refresh keeps the last valid exact preview visible and marks it stale.
      setPreview(null);
      setPreviewStale(Boolean(lastValidPreview));
      setPreviewFailed(true);
    } finally {
      if (generation === requestGeneration.current) setBusy(null);
    }
  }

  async function deliver(): Promise<void> {
    if (!canDeliver || !currentPreview || !output || !selectedTarget || !session?.processingOutput || !session.neutralModel) return;
    const generation = requestGeneration.current;
    setBusy("delivery");
    setDeliveryError(false);
    setError(null);
    try {
      const result = await deliverExactTargetPreview(config, {
        processing_output_id: session.processingOutput.id,
        processing_output_revision_id: session.processingOutput.revisionId,
        neutral_material_id: session.neutralModel.id,
        neutral_material_revision_id: session.neutralModel.revisionId,
        target: {
          solver: currentPreview.target.solver,
          version: currentPreview.target.version,
          unit_system: currentPreview.target.unit_system,
        },
        solver_material_id: currentPreview.target.solver_material_id,
        material_name: currentPreview.target.material_name,
        preview_identity: currentPreview.preview_identity,
        expected_mapping_report_sha256: currentPreview.mapping_report_sha256,
        acknowledgement_identity: requiresAcknowledgement && acknowledged
          ? currentPreview.acknowledgement_identity ?? undefined
          : undefined,
      });
      if (generation !== requestGeneration.current) return;
      if (!deliveryMatchesPreview(result.data, currentPreview)) {
        throw new Error("Create failed: the delivery receipt does not match the current exact source, target, or typed links.");
      }
      setDelivery(result.data);
      void recordModelingRecovery(
        config,
        {
          kind: "receipt_json",
          path: result.data.links.receipt,
          receiptId: result.data.receipt_id,
          deliveryId: result.data.delivery_identity,
          solverCardId: result.data.solver_card_id,
          solverCardRevisionId: result.data.solver_card_revision_id,
        },
        "succeeded",
        "Created the immutable target-delivery receipt.",
      );
      onSessionEvent?.({ type: "SET_CURRENT", key: "exportArtifact", value: { id: result.data.solver_card_id, revisionId: result.data.solver_card_revision_id, label: result.data.filename, revisionNo: 1 } });
    } catch (cause: unknown) {
      if (generation === requestGeneration.current) {
        setDeliveryError(true);
        const message = errorMessage(cause);
        setError(message);
        void recordModelingRecovery(
          config,
          {
            kind: "receipt_json",
            path: "/modeling?stage=export",
          },
          "failed",
          message,
        );
      }
    } finally {
      if (generation === requestGeneration.current) setBusy(null);
    }
  }

  const statusMessage = capabilityError
    ? "Exporter capability could not be loaded. Retry to discover supported solver/version/unit choices."
    : capabilityLoading
      ? "Loading declared exporter capabilities…"
      : !targets.length
        ? "No other unit systems available."
        : sourceBlocked
          ? sourceBlocked
          : !selectedTarget
            ? "Select a destination declared by the exporter capability."
            : currentPreview && previewStale
              ? "The preview is out of date. Retry Export check or change the destination."
              : null;

  return <section className="modeling-target-preview export-workspace" aria-label="Modeling Export workspace">
    <div className="export-workspace-grid">
      <aside className="export-properties" aria-label="Export setup">
        <div className="export-pane-heading"><h3>Export setup</h3></div>
        <div className="export-subsection-heading">Selected model</div>
        <div className="export-property-row"><span>Model</span><strong>{fitSelection?.displayLabel ?? "No model selected"}</strong></div>
        <button type="button" className="text-button" onClick={() => onNavigate?.("/modeling?stage=fit")}>Open in Fit</button>
        {session?.materialModelIr && session.neutralModel ? <button
          type="button"
          className="text-button"
          disabled={neutralDownloadBusy}
          onClick={() => void downloadSelectedNeutral()}
        >{neutralDownloadBusy ? "Preparing selected model…" : "Download selected model"}</button> : null}
        <div className="export-subsection-heading">Destination</div>
        <label className="export-field"><span>Solver / format</span><select aria-label="Solver target" value={targetKeyValue} disabled={capabilityLoading || Boolean(capabilityError) || !targets.length} onChange={(event) => changeTarget(event.target.value)}><option value="">Select a destination</option>{targets.map((target) => <option key={targetKey(target)} value={targetKey(target)}>{formatTarget(target)}</option>)}</select></label>
        <label className="export-field"><span>Output unit system</span><select aria-label="Output unit system" value={selectedTarget?.unit_system ?? ""} disabled={!selectedTarget}>{selectedTarget ? <option value={selectedTarget.unit_system}>{selectedTarget.unit_system.replaceAll("_", " · ")}</option> : <option value="">Select a solver first</option>}<option disabled value="__other_units_unavailable">No other unit systems available</option></select></label>
        <div className="export-check" aria-label="Export check"><div className="export-pane-heading"><p className="workspace-caption">Export check</p><h3 className="visually-hidden">Solver card creation status</h3><strong className={`export-status export-status-${currentStatus.toLowerCase().replaceAll(" ", "-")}`}>{currentStatus}</strong></div>{statusMessage ? <p className="ux-notice" role="status">{statusMessage}</p> : null}{deliveryError ? <p className="ux-notice error" role="alert">Create failed. The current preview and selected model remain available.</p> : null}{requiresAcknowledgement && currentPreview && !delivery ? <p className="ux-notice" role="status">Review the mapped approximations before creating the solver card.</p> : null}{!fitSourceReady ? <><button type="button" className="text-button" onClick={() => onNavigate?.("/modeling?stage=fit")}>Open in Fit</button>{onRetryFitSource ? <button type="button" className="text-button" onClick={onRetryFitSource}>Retry Fit result</button> : null}</> : null}{capabilityError ? <button type="button" className="text-button" onClick={() => { setCapability(null); setCapabilityError(null); setCapabilityReload((value) => value + 1); }}>Retry destination lookup</button> : null}{requiresAcknowledgement && currentPreview && !delivery ? <label className="delivery-acknowledgement"><input aria-label="Acknowledge mapped approximations" type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />I reviewed the approximations.</label> : null}<div className="export-action-row">{primaryAction ? <button className="ux-button primary" type="button" disabled={primaryActionDisabled || busy !== null} onClick={() => { if (primaryAction === "Open solver card") onNavigate?.(`/materials/${delivery?.source.material_id}/cards/${delivery?.solver_card_id}`); else if (primaryAction === "Create solver card" || primaryAction === "Retry create") void deliver(); else void generate(); }}>{busy === "preview" ? (primaryAction === "Retry Export check" ? "Retry Export check" : "Run Export check") : busy === "delivery" ? (primaryAction === "Retry create" ? "Retry create" : "Create solver card") : primaryAction}</button> : null}</div></div>
        <details className="export-advanced export-advanced-input"><summary>Native card options</summary><label className="export-field"><span>Solver material ID</span><input aria-label="Solver material ID" value={solverMaterialId} inputMode="numeric" onChange={(event) => { setSolverMaterialId(event.target.value); invalidateDownstream(); }} /></label><label className="export-field"><span>Material name</span><input aria-label="Native material name" value={materialName} onChange={(event) => { setMaterialName(event.target.value); invalidateDownstream(); }} /></label></details>
        <ExactEvidence session={session} output={output} fitPreview={fitPreview} selection={fitSelection} preview={currentPreview} />
      </aside>
      <div className="export-divider" aria-hidden="true" />
      <main className="export-main" aria-label="Native preview workspace">
        <div className="export-pane-heading export-preview-heading">
          <div className="export-heading-copy">
            <h3>Solver card preview</h3>
            {selectedTarget ? <span>{selectedTarget.solver} {selectedTarget.version} · {selectedTarget.unit_system.replaceAll("_", " · ")}</span> : null}
          </div>
          <span className="export-preview-state">{delivery ? "Solver card created" : currentPreview ? "Not created" : "Run Export check to preview"}</span>
        </div>
        <div id="modeling-process" className="export-native-preview-shell"><MaterialsScrollRegion
          id="modeling-export-native-preview-viewport"
          className="native-preview preview-scroll export-native-preview-viewport"
          shellClassName="modeling-target-preview-native-scroll-shell"
          tabIndex={0}
          aria-label="Native preview"
        >
          <pre>{currentPreview?.native_text ?? "Select a destination and run Export check."}</pre>
        </MaterialsScrollRegion></div>
        {error ? <p className="ux-notice error" role="alert">{error}</p> : null}
        {delivery ? <p className="ux-notice success" role="status"><strong>Solver card created</strong> · {delivery.filename}</p> : null}
        {delivery && output ? <ReviewRequestAction
          config={config}
          subject={{
            aggregateType: "exporting.neutral_solver_card",
            aggregateId: delivery.solver_card_id,
            revisionId: delivery.solver_card_revision_id,
            classification: output.current_revision.classification,
            lifecycleState: "draft",
          }}
        /> : null}
        <DeliveryDetails delivery={delivery} />
      </main>
      <aside className="export-result" aria-label="Export result context">
        <MappingDetails items={currentPreview?.mapping.items ?? []} />
        <FitSource preview={fitPreview} selection={fitSelection} fitSourceReady={fitSourceReady} fitRestoreError={fitRestoreError} />
      </aside>
    </div>
  </section>;
}
