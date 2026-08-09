import { Fragment, type FormEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import {
  ApiError,
  getCatalogWorkflowGraph,
  getConfigurableCatalogRecord,
  getAuthenticatedPrincipal,
  getEffectiveProductAccess,
  getMaterialDetail,
  getMaterialRevisions,
  listCanonicalTestDataDocuments,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogRecordRevisions,
  searchMaterialCatalogRecords,
  listReviewRequests,
  listCommonProcessingBatches,
  retryFailedCommonProcessingBatch,
  listMaterials,
  resolveCatalogDomainRevision,
  createReviewDecision,
  type ApiConfig,
  type MaterialSearchRow,
} from "./api";
import type {
  CatalogWorkflowGraphResponse,
  CanonicalTestDataDocumentResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableAttributeResponse,
  ConfigurableLinkEndpoint,
  ConfigurableRecordValue,
  DomainRevisionBinding,
  MaterialDetail,
  MaterialResponse,
  ProductRole,
  PropertySetResponse,
  ReviewRequestResponse,
  CommonProcessingBatchResponse,
} from "./types";
import { MaterialsBrowseTree, type MaterialsBrowseScope } from "./materials-browse-tree";
import { MaterialDatasheetProjection } from "./material-datasheet-projection";
import { MaterialsScrollRegion } from "./materials-scroll-rail";
import { publishWorkspaceCommandState, publishWorkspaceStatus } from "./design/application-shell";
import { ResizableSplitPane } from "./design/resizable-split-pane";
import { EngineeringColumnResizeHandle } from "./design/engineering-column-resize-handle";
import { EngineeringIcon } from "./design/icon";
import { loadModelingSession, saveModelingSession } from "./modeling-session-context";
import {
  downloadSolverCardArtifact,
  downloadSolverMappingArtifact,
  loadDeliveryActivities,
  loadSolverCardEvidence,
  previewSolverCardText,
  recordDeliveryActivity,
  type SolverCardEvidence,
  type SolverCardSummary,
} from "./solver-card-delivery";
import {
  MappingStatusList,
  NeutralCardCreationPanel,
  SolverCardAction,
} from "./solver-card-delivery-ui";
import { ReviewRequestAction } from "./review-request-action";
import {
  appendActivityFailure,
  appendActivityOutcome,
  readActivityRecoveries,
  type ActivityRecoveryContext,
  type ActivityRecoveryFact,
} from "./activity-recovery";

export type MaterialTab = "overview" | "properties" | "curves" | "cards" | "evidence";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  locationSearch?: string;
}

interface MaterialExperience {
  detail: MaterialDetail;
  graph: CatalogWorkflowGraphResponse | null;
  cards: SolverCardSummary[];
  representativeCurve: Array<{ x: number; y: number }>;
  catalogRecord: ConfigurableCatalogRecordResponse | null;
}

export interface MaterialRevisionPin {
  recordId: string;
  recordRevisionId: string;
  materialRevisionId: string;
}

interface BrowseSelection {
  record: ConfigurableCatalogRecordResponse;
  graph: CatalogWorkflowGraphResponse;
}

const MATERIALS_RETURN_KEY = "cmp.materials.return-path";
const MATERIALS_BROWSE_RECORD_KEY = "cmp.materials.browse-record";

function materialSearchParams(): URLSearchParams {
  return new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);
}

interface MaterialsLocationState {
  query: string;
  materialClass: string;
  provider: string;
  evidenceSource: string;
  scope: MaterialsBrowseScope | null;
  sortKey: "name" | "material_class";
  sortDirection: "ascending" | "descending";
  offset: number;
  leftMode: "filters" | "browse" | "subsets";
  selectedId: string;
}

function materialsPath(state: MaterialsLocationState): string {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.materialClass) params.set("family", state.materialClass);
  if (state.provider) params.set("provider", state.provider);
  if (state.evidenceSource) params.set("source", state.evidenceSource);
  if (state.scope?.tableId) params.set("table", state.scope.tableId);
  if (state.scope?.folderId) params.set("folder", state.scope.folderId);
  if (state.scope?.recordId) params.set("record", state.scope.recordId);
  if (state.sortKey !== "name") params.set("sort", state.sortKey);
  if (state.sortDirection !== "ascending") params.set("direction", state.sortDirection);
  if (state.leftMode !== "browse") params.set("mode", state.leftMode);
  if (state.selectedId) params.set("selected", state.selectedId);
  if (state.offset) params.set("offset", String(state.offset));
  const search = params.toString();
  return search ? `/materials?${search}` : "/materials";
}

function initialNavigatorMode(): "filters" | "browse" | "subsets" {
  const mode = materialSearchParams().get("mode");
  return mode === "filters" || mode === "subsets" ? mode : "browse";
}

function initialSortKey(): "name" | "material_class" {
  const key = materialSearchParams().get("sort");
  return key === "material_class" ? key : "name";
}

function storedBrowseRecord(): ConfigurableLinkEndpoint | null {
  if (typeof window === "undefined") return null;
  try {
    const value = JSON.parse(window.sessionStorage.getItem(MATERIALS_BROWSE_RECORD_KEY) ?? "null") as ConfigurableLinkEndpoint | null;
    return value?.record_id && value.table_id ? value : null;
  } catch {
    return null;
  }
}

function materialsReturnPath(): string {
  if (typeof window === "undefined") return "/materials";
  const stored = window.sessionStorage.getItem(MATERIALS_RETURN_KEY) ?? "";
  return /^\/materials(?:\?|$)/.test(stored) ? stored : "/materials";
}

const tabs: ReadonlyArray<{ id: MaterialTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "properties", label: "Properties" },
  { id: "curves", label: "Curves" },
  { id: "cards", label: "CAE Cards" },
  { id: "evidence", label: "Evidence" },
];

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "The material workspace could not be loaded.";
}

function solverFor(name: string): Pick<SolverCardSummary, "solver" | "extension"> {
  const normalized = name.toLowerCase();
  if (normalized.includes("openradioss") || normalized.includes("radioss")) {
    return { solver: "OpenRadioss", extension: ".rad" };
  }
  if (normalized.includes("abaqus")) return { solver: "Abaqus", extension: ".inp" };
  return { solver: "Solver", extension: ".txt" };
}

function nodeBindings(node: CatalogWorkflowGraphResponse["nodes"][number]): DomainRevisionBinding[] {
  const bindings = node.domain_bindings?.length
    ? node.domain_bindings
    : node.domain_binding
      ? [node.domain_binding]
      : [];
  const seen = new Set<string>();
  return bindings.filter((binding) => {
    const key = `${node.record_id}:${node.record_revision_id}:${binding.kind}:${binding.object_id}:${binding.revision_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function cardsFromGraph(graph: CatalogWorkflowGraphResponse | null): SolverCardSummary[] {
  if (!graph) return [];
  return graph.nodes.flatMap((node) => {
    return nodeBindings(node)
      .filter((binding) => binding.kind === "neutral_solver_card" || binding.kind === "solver_card")
      .map((binding) => ({
        id: binding.object_id,
        revisionId: binding.revision_id,
        kind: binding.kind as SolverCardSummary["kind"],
        label: node.name,
        ...solverFor(node.name),
      }));
  }).sort((left, right) => left.solver.localeCompare(right.solver));
}

async function currentCards(
  config: ApiConfig,
  materialId: string,
  graph: CatalogWorkflowGraphResponse | null,
): Promise<SolverCardSummary[]> {
  const merged = new Map(
    cardsFromGraph(graph).map((card) => [`${card.kind}:${card.id}:${card.revisionId}`, card]),
  );
  void config;
  void materialId;
  return [...merged.values()].sort((left, right) =>
    left.solver.localeCompare(right.solver) || left.label.localeCompare(right.label),
  );
}

function curveFromNativeCard(source: string): Array<{ x: number; y: number }> {
  const points: Array<{ x: number; y: number }> = [];
  let readingAbaqus = false;
  let readingRadioss = false;
  for (const rawLine of source.split("\n")) {
    const line = rawLine.trim();
    if (line.startsWith("*PLASTIC")) {
      readingAbaqus = true;
      readingRadioss = false;
      continue;
    }
    if (line.startsWith("/FUNCT/")) {
      readingRadioss = true;
      readingAbaqus = false;
      continue;
    }
    if ((readingAbaqus && line.startsWith("*")) || (readingRadioss && line.startsWith("/END"))) break;
    if (!readingAbaqus && !readingRadioss) continue;
    if (!line || line.startsWith("#") || line.startsWith("CMP_")) continue;
    const values = line.split(/[\s,]+/).filter(Boolean).map(Number);
    if (values.length < 2 || !Number.isFinite(values[0]) || !Number.isFinite(values[1])) continue;
    points.push(readingAbaqus ? { x: values[1], y: values[0] } : { x: values[0], y: values[1] });
  }
  return points;
}

async function loadMaterialExperience(config: ApiConfig, material: MaterialResponse, includeCurve = false): Promise<MaterialExperience> {
  const detailResult = await getMaterialDetail(config, material.material_id);
  const bindingResult = await resolveCatalogDomainRevision(
    config,
    "material",
    material.material_id,
    material.current_revision.id,
  );
  const binding = bindingResult.data;
  if (!binding) throw new Error("This Material revision is not published in Materials.");
  const graph = (await getCatalogWorkflowGraph(
    config,
    binding.record_id,
    binding.record_revision_id,
    6,
    true,
  )).data;
  const graphBinding = graph.root.domain_binding;
  if (
    graph.root.record_id !== binding.record_id
    || graph.root.record_revision_id !== binding.record_revision_id
    || !graphBinding
    || graphBinding.kind !== "material"
    || graphBinding.object_id !== material.material_id
    || graphBinding.revision_id !== material.current_revision.id
  ) {
    throw new Error("This Material revision is not the approved current Materials subject.");
  }
  // Bulk-export candidate discovery is an internal Modeling surface.  Materials
  // cards must come only from the approved exact graph projection.
  const cards = await currentCards(config, material.material_id, graph);
  let representativeCurve: Array<{ x: number; y: number }> = [];
  if (includeCurve && cards.length) {
    const preferred = cards.find((card) => card.solver === "OpenRadioss") ?? cards[0];
    try {
      const preview = await previewSolverCardText(config, preferred);
      representativeCurve = curveFromNativeCard(preview.data);
    } catch {
      representativeCurve = [];
    }
  }
  return { detail: detailResult.data, graph, cards, representativeCurve, catalogRecord: null };
}

function materialPinQuery(pin: MaterialRevisionPin | undefined): string {
  if (!pin) return "";
  return new URLSearchParams({
    record_id: pin.recordId,
    record_revision_id: pin.recordRevisionId,
    material_revision_id: pin.materialRevisionId,
  }).toString();
}

function materialDetailPath(materialId: string, tab: MaterialTab = "overview", pin?: MaterialRevisionPin): string {
  const path = tab === "overview" ? `/materials/${materialId}` : `/materials/${materialId}/${tab}`;
  const query = materialPinQuery(pin);
  return query ? `${path}?${query}` : path;
}

async function loadPinnedMaterialExperience(
  config: ApiConfig,
  materialId: string,
  pin: MaterialRevisionPin,
  includeCurve = false,
): Promise<MaterialExperience> {
  if (!pin.recordId || !pin.recordRevisionId || !pin.materialRevisionId) {
    throw new Error("The selected exact Material revision link is incomplete.");
  }
  const [detailResult, materialRevisionsResult, recordHeadResult, recordRevisionsResult] = await Promise.all([
    getMaterialDetail(config, materialId),
    getMaterialRevisions(config, materialId),
    getConfigurableCatalogRecord(config, pin.recordId),
    listConfigurableCatalogRecordRevisions(config, pin.recordId),
  ]);
  const materialRevision = materialRevisionsResult.data.revisions.find((revision) => revision.id === pin.materialRevisionId);
  if (!materialRevision) throw new Error("The selected Material revision is unavailable.");
  const recordRevision = recordRevisionsResult.data.items.find((revision) => revision.id === pin.recordRevisionId);
  if (!recordRevision) throw new Error("The selected Catalog record revision is unavailable.");
  if (recordHeadResult.data.record_id !== pin.recordId) throw new Error("The selected Catalog record is unavailable.");
  const graphResult = await getCatalogWorkflowGraph(config, pin.recordId, pin.recordRevisionId, 6, true);
  const graph = graphResult.data;
  const graphBinding = graph.root.domain_binding;
  if (
    graph.root.record_id !== pin.recordId
    || graph.root.record_revision_id !== pin.recordRevisionId
    || !graphBinding
    || graphBinding.kind !== "material"
    || graphBinding.object_id !== materialId
    || graphBinding.revision_id !== pin.materialRevisionId
  ) {
    throw new Error("The selected workflow graph does not match the requested Material revision.");
  }
  const record = { ...recordHeadResult.data, current_revision: recordRevision, domain_binding: graphBinding };
  const detail: MaterialDetail = {
    ...detailResult.data,
    material: { ...detailResult.data.material, current_revision: materialRevision },
    states: detailResult.data.states.filter((state) => state.current_revision.content.material_revision_id === pin.materialRevisionId),
  };
  const stateRevisionIds = new Set(detail.states.map((state) => state.current_revision.id));
  detail.property_sets = detailResult.data.property_sets.filter((propertySet) =>
    stateRevisionIds.has(propertySet.current_revision.content.material_state_revision_id),
  );
  const cards = await currentCards(config, materialId, graph);
  let representativeCurve: Array<{ x: number; y: number }> = [];
  if (includeCurve && cards.length) {
    const preferred = cards.find((card) => card.solver === "OpenRadioss") ?? cards[0];
    try {
      const preview = await previewSolverCardText(config, preferred);
      representativeCurve = curveFromNativeCard(preview.data);
    } catch {
      representativeCurve = [];
    }
  }
  return { detail, graph, cards, representativeCurve, catalogRecord: record };
}

function currentProperty(experience: MaterialExperience | undefined): PropertySetResponse | undefined {
  return experience?.detail.property_sets[0];
}

function formatPressure(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value / 1e6)} MPa`;
}

function formatDensity(value: number | undefined): string {
  if (value === undefined) return "—";
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)} kg/m³`;
}

function familyLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "metal") return "Metal";
  if (normalized === "polymer") return "Polymer";
  if (normalized === "elastomer") return "Elastomer";
  return value?.trim() || "Unclassified";
}

function sourceLabel(experience: MaterialExperience | undefined): string {
  const property = currentProperty(experience)?.current_revision.content;
  const source = property?.yield_stress_source ?? property?.youngs_modulus_source ?? property?.density_source;
  return source?.reference || source?.kind.replaceAll("_", " ") || "Not specified";
}

function browsePath(experience: MaterialExperience | undefined): string {
  const root = experience?.graph?.root;
  return root ? `/database/records/${root.record_id}/revisions/${root.record_revision_id}` : "/database";
}

function neutralMaterialBinding(experience: MaterialExperience | null | undefined): DomainRevisionBinding | null {
  return experience?.graph?.nodes
    .map((node) => node.domain_binding)
    .find((binding): binding is DomainRevisionBinding => binding?.kind === "neutral_material") ?? null;
}

function deliveryMaterial(material: MaterialResponse) {
  return {
    materialId: material.material_id,
    materialRevisionId: material.current_revision.id,
    materialLabel: material.current_revision.content.name,
  };
}

function modelingFamily(material: MaterialResponse): "metal" | "polymer" | "elastomer" | null {
  const family = `${material.current_revision.content.material_class} ${material.current_revision.content.material_family ?? ""}`.toLowerCase();
  if (family.includes("elastomer") || family.includes("rubber")) return "elastomer";
  if (family.includes("polymer") || family.includes("plastic")) return "polymer";
  if (family.includes("metal")) return "metal";
  return null;
}

function startModeling(material: MaterialResponse, onNavigate: (path: string) => void): void {
  const family = modelingFamily(material);
  if (!family) return;
  saveModelingSession({
    materialFamily: family,
    objective: `Create a simulation-ready card for ${material.current_revision.content.name}`,
    material: {
      id: material.material_id,
      revisionId: material.current_revision.id,
      revisionNo: material.current_revision.revision_no,
      label: material.current_revision.content.name,
    },
    workspace: {
      activeStage: "data",
      selectedDocumentIds: [],
      selectedStepIndex: 0,
      selectedStageOrdinal: 0,
      plotView: "pipeline",
      settingsOpen: typeof window === "undefined" || window.innerWidth >= 1400,
    },
  });
  onNavigate(`/modeling?stage=data&family=${family}`);
}

function RepresentativeCurve({ points }: { points: Array<{ x: number; y: number }> }) {
  const normalizedPoints = useMemo(() => normalizeLinkedResponsePoints(points), [points]);
  const frameRef = useRef<HTMLDivElement | null>(null);
  const frameSize = useResponsePlotSize(frameRef, normalizedPoints.length);
  if (normalizedPoints.length < 2) return <div className="ux-empty compact"><strong>No representative curve preview.</strong><p>Open Curves or Browse Tree to inspect linked Test Data and model records.</p></div>;
  return <div ref={frameRef} className="material-curve-preview response-plot-frame">
    <ResponsePlotSvg points={normalizedPoints} frameSize={frameSize} ariaLabel="Representative material response showing true stress in MPa versus true plastic strain" titleText="True stress versus true plastic strain for this material." legendLabel="Material response" />
  </div>;
}

function NativeCardPreview({ text }: { text: string }) {
  const previewRef = useRef<HTMLPreElement | null>(null);
  const railRef = useRef<HTMLDivElement | null>(null);
  const thumbRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    const preview = previewRef.current;
    const rail = railRef.current;
    const thumb = thumbRef.current;
    if (!preview || !rail || !thumb) return;
    const updateScrollRail = () => {
      const scrollable = preview.scrollHeight > preview.clientHeight + 1;
      rail.dataset.scrollable = String(scrollable);
      if (!scrollable) {
        thumb.style.height = "0px";
        thumb.style.transform = "translateY(0px)";
        return;
      }
      const trackHeight = Math.max(0, rail.clientHeight);
      const thumbHeight = Math.min(trackHeight, Math.max(22, trackHeight * (preview.clientHeight / preview.scrollHeight)));
      const travel = Math.max(0, trackHeight - thumbHeight);
      const range = Math.max(1, preview.scrollHeight - preview.clientHeight);
      thumb.style.height = `${thumbHeight}px`;
      thumb.style.transform = `translateY(${travel * (preview.scrollTop / range)}px)`;
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "PageDown") {
        event.preventDefault();
        preview.scrollTop += preview.clientHeight;
      } else if (event.key === "PageUp") {
        event.preventDefault();
        preview.scrollTop -= preview.clientHeight;
      } else if (event.key === "End") {
        event.preventDefault();
        preview.scrollTop = preview.scrollHeight;
      } else if (event.key === "Home") {
        event.preventDefault();
        preview.scrollTop = 0;
      }
    };
    preview.addEventListener("scroll", updateScrollRail, { passive: true });
    preview.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", updateScrollRail);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(updateScrollRail);
    observer?.observe(preview);
    observer?.observe(rail);
    const frame = typeof window.requestAnimationFrame === "function" ? window.requestAnimationFrame(updateScrollRail) : 0;
    return () => {
      preview.removeEventListener("scroll", updateScrollRail);
      preview.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", updateScrollRail);
      observer?.disconnect();
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [text]);

  return <div className="preview-scroll-shell">
    <pre ref={previewRef} className="native-card-preview preview-scroll" aria-label="Native solver card preview" tabIndex={0}>{text}</pre>
    <div ref={railRef} className="preview-scroll-rail" data-scrollable="false" aria-hidden="true"><span ref={thumbRef} className="preview-scroll-thumb"/></div>
  </div>;
}

function normalizeLinkedResponsePoints(points: Array<{ x: number; y: number }>): Array<{ x: number; y: number }> {
  const maximumMagnitude = Math.max(...points.map((point) => Math.abs(point.y)), 0);
  const stressScale = maximumMagnitude > 10_000 ? 1e-6 : 1;
  return points.map((point) => ({ x: point.x, y: point.y * stressScale }));
}

function useResponsePlotSize(frameRef: { current: HTMLDivElement | null }, pointCount: number): { width: number; height: number } {
  const [frameSize, setFrameSize] = useState({ width: 720, height: 300 });
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const measure = () => {
      const bounds = frame.getBoundingClientRect();
      setFrameSize((current) => {
        const width = Math.max(1, Math.round(bounds.width));
        const height = Math.max(1, Math.round(bounds.height));
        return current.width === width && current.height === height ? current : { width, height };
      });
    };
    measure();
    window.addEventListener("resize", measure);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(frame);
    return () => {
      window.removeEventListener("resize", measure);
      observer?.disconnect();
    };
  }, [frameRef, pointCount]);
  return frameSize;
}

function plotTicks(minimum: number, maximum: number, step: number): number[] {
  const ticks: number[] = [];
  for (let value = Math.ceil(minimum / step) * step; value <= maximum + step * 0.01; value += step) {
    ticks.push(Number(value.toFixed(6)));
  }
  return ticks;
}

function formatLinkedResponseTick(value: number, axis: "x" | "y"): string {
  if (axis === "x") {
    if (Math.abs(value) < 1e-9) return "0";
    return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  }
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function ResponsePlotSvg({
  points,
  frameSize,
  ariaLabel,
  titleText,
  legendLabel,
}: {
  points: Array<{ x: number; y: number }>;
  frameSize: { width: number; height: number };
  ariaLabel: string;
  titleText: string;
  legendLabel: string;
}) {
  if (points.length < 2) return null;
  const width = Math.max(360, frameSize.width);
  const height = Math.max(220, frameSize.height);
  const margin = { left: 62, right: 24, top: 20, bottom: 44 };
  const plotWidth = Math.max(1, width - margin.left - margin.right);
  const plotHeight = Math.max(1, height - margin.top - margin.bottom);
  const xMaximum = Math.max(...points.map((point) => point.x), 0);
  const xStep = xMaximum <= 0.25 ? 0.025 : xMaximum <= 1 ? 0.1 : 0.5;
  const xDomainStep = xMaximum <= 0.25 ? 0.005 : xStep / 2;
  const xDomainMaximum = Math.max(xDomainStep, Math.ceil((xMaximum + Math.max(xMaximum * 0.05, 0.005)) / xDomainStep) * xDomainStep);
  const yMinimum = Math.min(...points.map((point) => point.y));
  const yMaximum = Math.max(...points.map((point) => point.y));
  const ySpan = Math.max(yMaximum - yMinimum, 1);
  const yPad = Math.max(ySpan * 0.05, 10);
  const yDomainMinimum = Math.max(0, Math.floor((yMinimum - yPad) / 10) * 10);
  const yDomainMaximum = Math.max(yDomainMinimum + 10, Math.ceil((yMaximum + yPad) / 10) * 10);
  const yStep = yDomainMaximum - yDomainMinimum <= 400 ? 50 : yDomainMaximum - yDomainMinimum <= 800 ? 100 : 200;
  const xTicks = plotTicks(0, xDomainMaximum, xStep);
  const yTicks = plotTicks(yDomainMinimum, yDomainMaximum, yStep);
  const scaleX = (value: number) => margin.left + (value / xDomainMaximum) * plotWidth;
  const scaleY = (value: number) => margin.top + (1 - (value - yDomainMinimum) / (yDomainMaximum - yDomainMinimum)) * plotHeight;
  const mappedPoints = points.map((point) => ({ x: scaleX(point.x), y: scaleY(point.y) }));
  const linePoints = mappedPoints.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
  const gridX = xTicks.map((value) => <line key={`grid-x-${value}`} x1={scaleX(value)} y1={margin.top} x2={scaleX(value)} y2={margin.top + plotHeight}/>);
  const gridY = yTicks.map((value) => <line key={`grid-y-${value}`} x1={margin.left} y1={scaleY(value)} x2={margin.left + plotWidth} y2={scaleY(value)}/>);
  const legendWidth = 168;
  const legendCandidates = [
    { x: margin.left + plotWidth - legendWidth - 8, y: margin.top + 16 },
    { x: margin.left + 8, y: margin.top + 16 },
    { x: margin.left + plotWidth - legendWidth - 8, y: margin.top + plotHeight - 8 },
    { x: margin.left + 8, y: margin.top + plotHeight - 8 },
  ];
  const legend = legendCandidates.find((candidate) => !mappedPoints.some((point) => point.x >= candidate.x - 4 && point.x <= candidate.x + legendWidth && point.y >= candidate.y - 16 && point.y <= candidate.y + 4)) ?? legendCandidates[0];

  return <svg className="linked-response-plot response-plot" role="img" aria-label={ariaLabel} viewBox={`0 0 ${width} ${height}`} data-series-rows={points.length} data-x-domain={`0,${xDomainMaximum}`} data-y-domain={`${yDomainMinimum},${yDomainMaximum}`} data-x-label="True plastic strain [1]" data-y-label="True stress (MPa)">
    <title>{titleText}</title>
    <g className="linked-response-grid plot-grid" aria-hidden="true">{gridX}{gridY}</g>
    <path className="linked-response-axis plot-axis" d={`M ${margin.left} ${margin.top} V ${margin.top + plotHeight} H ${margin.left + plotWidth}`}/>
    <g className="linked-response-labels">
      {xTicks.map((value) => <g key={`x-tick-${value}`}><line className="linked-response-tick plot-tick" x1={scaleX(value)} y1={margin.top + plotHeight} x2={scaleX(value)} y2={margin.top + plotHeight + 5}/><text className="linked-response-tick-label plot-tick-label" x={scaleX(value)} y={height - 24} textAnchor="middle">{formatLinkedResponseTick(value, "x")}</text></g>)}
      {yTicks.map((value) => <g key={`y-tick-${value}`}><line className="linked-response-tick plot-tick" x1={margin.left - 5} y1={scaleY(value)} x2={margin.left} y2={scaleY(value)}/><text className="linked-response-tick-label plot-tick-label" x={margin.left - 10} y={scaleY(value) + 4} textAnchor="end">{formatLinkedResponseTick(value, "y")}</text></g>)}
      <text className="linked-response-axis-title plot-axis-title" x={margin.left + plotWidth / 2} y={height - 7} textAnchor="middle">True plastic strain [1]</text>
      <text className="linked-response-axis-title plot-axis-title" transform={`translate(16 ${margin.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle">True stress (MPa)</text>
    </g>
    <polyline className="linked-response-line response-line" points={linePoints} data-series-line="true"/>
    <g className="linked-response-points response-points" aria-hidden="true">{mappedPoints.map((point, index) => <circle key={`point-${index}`} className="linked-response-point response-point" cx={point.x} cy={point.y} r="3"/>)}</g>
    <g className="linked-response-legend plot-legend" transform={`translate(${legend.x} ${legend.y})`}><line x1="0" y1="-4" x2="18" y2="-4"/><text x="26" y="0">{legendLabel}</text></g>
  </svg>;
}

function LinkedResponseGraph({ points }: { points: Array<{ x: number; y: number }> }) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const normalizedPoints = useMemo(() => normalizeLinkedResponsePoints(points), [points]);
  const frameSize = useResponsePlotSize(frameRef, normalizedPoints.length);
  if (normalizedPoints.length < 2) return null;
  return <section className="linked-response-band response-plot-band" aria-labelledby="linked-response-title">
    <header className="linked-response-heading response-plot-heading"><div><h2 id="linked-response-title">Linked response</h2><p>Same values as the selected card preview.</p></div><span className="ux-meta">Card evidence · read only</span></header>
    <div ref={frameRef} className="linked-response-frame response-plot-frame">
      <ResponsePlotSvg points={normalizedPoints} frameSize={frameSize} ariaLabel="Linked response chart showing true stress in MPa versus true plastic strain" titleText="True stress versus true plastic strain from the selected card." legendLabel="Card hardening data" />
    </div>
  </section>;
}

function formatResponsePoint(value: number, axis: "x" | "y"): string {
  if (axis === "x") return value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "") || "0";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value);
}

function ResponsePointsTable({ points }: { points: Array<{ x: number; y: number }> }) {
  const normalizedPoints = useMemo(() => normalizeLinkedResponsePoints(points), [points]);
  const regionId = `material-response-points-${useId().replaceAll(":", "")}`;
  if (!normalizedPoints.length) return null;
  return <section className="material-response-points" aria-labelledby={`${regionId}-heading`}>
    <div className="material-response-points-heading">
      <div>
        <h3 id={`${regionId}-heading`}>Response points</h3>
        <span className="section-subtitle">Exact ordered series · {normalizedPoints.length} points</span>
      </div>
      <span className="section-context">Engineering units</span>
    </div>
    <MaterialsScrollRegion
      id={regionId}
      className="material-response-points-scroll"
      shellClassName="material-response-points-scroll-shell"
      role="region"
      aria-label="Scrollable representative response points"
    >
      <table aria-label="Representative response points">
        <caption className="sr-only">Representative response points</caption>
        <thead><tr><th scope="col">Point</th><th scope="col">True plastic strain</th><th scope="col">True stress (MPa)</th></tr></thead>
        <tbody>{normalizedPoints.map((point, index) => <tr key={`response-point-${index}`} data-point-index={index + 1} data-x-value={point.x} data-y-value={point.y}><th scope="row">{index + 1}</th><td>{formatResponsePoint(point.x, "x")}</td><td>{formatResponsePoint(point.y, "y")}</td></tr>)}</tbody>
      </table>
    </MaterialsScrollRegion>
  </section>;
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function SolverAvailability({ cards }: { cards: SolverCardSummary[] }) {
  if (!cards.length) return <p className="ux-meta">No released reference card is available yet.</p>;
  return (
    <ul className="solver-availability-list">
      {cards.map((card) => <li key={card.id}><strong>{card.solver}</strong><span className="ux-meta">Native {card.extension}</span></li>)}
    </ul>
  );
}

export function MaterialSearchPage({ config, onNavigate, locationSearch }: Props) {
  const [draftQuery, setDraftQuery] = useState(() => materialSearchParams().get("q") ?? "");
  const [query, setQuery] = useState(() => materialSearchParams().get("q") ?? "");
  const [materialClass, setMaterialClass] = useState(() => materialSearchParams().get("family") ?? "");
  const [provider, setProvider] = useState(() => materialSearchParams().get("provider") ?? "");
  const [evidenceSource, setEvidenceSource] = useState(() => materialSearchParams().get("source") ?? "");
  const [scope, setScope] = useState<MaterialsBrowseScope | null>(() => {
    const params = materialSearchParams();
    const tableId = params.get("table");
    return tableId ? {
      tableId,
      folderId: params.get("folder"),
      recordId: params.get("record"),
      includeDescendants: Boolean(params.get("folder")),
    } : null;
  });
  const [scopeAvailability, setScopeAvailability] = useState<"loading" | "ready" | "unavailable">(() => scope ? "ready" : "loading");
  const [sortKey, setSortKey] = useState<"name" | "material_class">(initialSortKey);
  const [sortDirection, setSortDirection] = useState<"ascending" | "descending">(() => materialSearchParams().get("direction") === "descending" ? "descending" : "ascending");
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [leftMode, setLeftMode] = useState<"filters" | "browse" | "subsets">(initialNavigatorMode);
  const [requestedRecord, setRequestedRecord] = useState<ConfigurableLinkEndpoint | null>(storedBrowseRecord);
  const [browseSelection, setBrowseSelection] = useState<BrowseSelection | null>(null);
  const [materials, setMaterials] = useState<MaterialSearchRow[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [familyFacets, setFamilyFacets] = useState<Array<{ material_class: string; count: number }>>([]);
  const [providerFacets, setProviderFacets] = useState<Array<{ provider: string; count: number }>>([]);
  const [evidenceSourceFacets, setEvidenceSourceFacets] = useState<Array<{ evidence_source: string; count: number }>>([]);
  const [offset, setOffset] = useState(() => Number(materialSearchParams().get("offset") ?? "0") || 0);
  const [selectedId, setSelectedId] = useState(() => materialSearchParams().get("selected") ?? "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [columnWidths, setColumnWidths] = useState({ compare: 68, material: 250, materialClass: 160, summary: 210 });

  useEffect(() => {
    if (locationSearch === undefined) return;
    const params = new URLSearchParams(locationSearch);
    const nextMode = params.get("mode");
    const nextSort = params.get("sort");
    setDraftQuery(params.get("q") ?? "");
    setQuery(params.get("q") ?? "");
    setMaterialClass(params.get("family") ?? "");
    setProvider(params.get("provider") ?? "");
    setEvidenceSource(params.get("source") ?? "");
    const tableId = params.get("table");
    setScope(tableId ? { tableId, folderId: params.get("folder"), recordId: params.get("record"), includeDescendants: Boolean(params.get("folder")) } : null);
    setScopeAvailability(tableId ? "ready" : "loading");
    setSortKey(nextSort === "material_class" ? nextSort : "name");
    setSortDirection(params.get("direction") === "descending" ? "descending" : "ascending");
    setLeftMode(nextMode === "filters" || nextMode === "subsets" ? nextMode : "browse");
    setSelectedId(params.get("selected") ?? "");
    setOffset(Number(params.get("offset") ?? "0") || 0);
  }, [locationSearch]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    if (scopeAvailability !== "ready" || !scope?.tableId) {
      if (scopeAvailability === "unavailable") {
        setLoading(false);
        setError("Materials are not available in this workspace.");
      }
      return () => { active = false; };
    }
    void searchMaterialCatalogRecords(config, {
      query,
      materialClass: materialClass || undefined,
      provider: provider || undefined,
      evidenceSource: evidenceSource || undefined,
      tableId: scope.tableId,
      folderId: scope.folderId,
      recordId: scope.recordId,
      includeDescendants: scope.includeDescendants,
      offset,
      limit: 50,
      sortBy: sortKey,
      sortDirection,
    })
      .then((result) => {
        if (!active) return;
        const items = result.data.items;
        setMaterials(items);
        setTotalCount(result.data.total_count);
        setFamilyFacets(result.data.facets.material_classes);
        setProviderFacets(result.data.facets.providers);
        setEvidenceSourceFacets(result.data.facets.evidence_sources);
        setSelectedId((current) => items.some((item) => item.material_id === current) ? current : items[0]?.material_id ?? "");
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        // Keep the last authorized rows and selection visible while the next
        // query fails; the retry action can recover without losing context.
        setLoading(false);
        setError(messageFor(cause));
      });
    return () => { active = false; };
  }, [config, evidenceSource, loadAttempt, materialClass, offset, provider, query, scope, scopeAvailability, sortDirection, sortKey]);

  useEffect(() => {
    if (typeof window === "undefined" || window.location.pathname !== "/materials") return;
    window.history.replaceState(window.history.state, "", materialsPath({ query, materialClass, provider, evidenceSource, scope, sortKey, sortDirection, offset, leftMode, selectedId }));
  }, [evidenceSource, leftMode, materialClass, offset, provider, query, scope, selectedId, sortDirection, sortKey]);

  useEffect(() => {
    publishWorkspaceCommandState(`materials:${leftMode === "filters" ? "search" : leftMode}`);
  }, [leftMode]);

  const comparedMaterials = materials.filter((material) => compareIds.has(material.material_id));
  const selected = materials.find((item) => item.material_id === selectedId);

  useEffect(() => {
    publishWorkspaceStatus({
      selection: selected ? `${selected.name} · ${selected.material_code ?? "No grade"}` : "No material selected",
      revision: selected ? `r${selected.record_revision_no}` : `${totalCount.toLocaleString()} records`,
      jobs: loading ? "Loading materials" : "No active job",
      warnings: error ? "1 workspace error" : "0 warnings",
      connection: error ? "degraded" : "online",
    });
  }, [error, loading, selected, totalCount]);

  function submit(event: FormEvent): void {
    event.preventDefault();
    setOffset(0);
    setQuery(draftQuery.trim());
  }

  const changeScope = useCallback((nextScope: MaterialsBrowseScope) => {
    setScopeAvailability("ready");
    setScope((current) => current?.tableId === nextScope.tableId
      && current?.folderId === nextScope.folderId
      && current?.recordId === nextScope.recordId
      && current?.includeDescendants === nextScope.includeDescendants ? current : nextScope);
    setOffset(0);
  }, []);

  const changeScopeAvailability = useCallback((availability: "loading" | "ready" | "unavailable") => {
    setScopeAvailability(availability);
  }, []);

  function openBrowseTree(record: ConfigurableLinkEndpoint | null | undefined): void {
    setLeftMode("browse");
    setRequestedRecord(record ?? null);
    if (record) window.sessionStorage.setItem(MATERIALS_BROWSE_RECORD_KEY, JSON.stringify(record));
  }

  function selectBrowseRecord(
    record: ConfigurableCatalogRecordResponse,
    graph: CatalogWorkflowGraphResponse,
  ): void {
    setBrowseSelection({ record, graph });
    window.sessionStorage.setItem(MATERIALS_BROWSE_RECORD_KEY, JSON.stringify(graph.root));
    const materialBinding = graph.root.domain_binding?.kind === "material"
      ? graph.root.domain_binding
      : graph.nodes.find((node) => node.record_id === record.record_id && node.domain_binding?.kind === "material")?.domain_binding;
    if (materialBinding?.kind === "material") {
      const index = materials.findIndex((item) => item.material_id === materialBinding.object_id);
      if (index >= 0) setSelectedId(materialBinding.object_id);
    }
  }

  function openExactRecord(record: ConfigurableCatalogRecordResponse): void {
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, provider, evidenceSource, scope, sortKey, sortDirection, offset, leftMode, selectedId }));
    onNavigate(`/materials/records/${record.record_id}/revisions/${record.current_revision.id}`);
  }

  function changeSort(next: "name" | "material_class"): void {
    if (next === sortKey) setSortDirection((current) => current === "ascending" ? "descending" : "ascending");
    else {
      setSortKey(next);
      setSortDirection("ascending");
    }
    setOffset(0);
  }

  function sortIndicator(column: "name" | "material_class"): ReactNode {
    if (sortKey !== column) return null;
    return <EngineeringIcon name={sortDirection === "ascending" ? "sort-ascending" : "sort-descending"}/>;
  }

  function toggleCompare(materialId: string): void {
    setCompareIds((current) => {
      const next = new Set(current);
      if (next.has(materialId)) next.delete(materialId);
      else if (next.size < 3) next.add(materialId);
      return next;
    });
  }

  function openMaterial(material: MaterialSearchRow): void {
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, provider, evidenceSource, scope, sortKey, sortDirection, offset, leftMode, selectedId: material.material_id }));
    const params = new URLSearchParams({
      record_id: material.record_id,
      record_revision_id: material.record_revision_id,
      material_revision_id: material.material_revision_id,
    });
    onNavigate(`/materials/${material.material_id}?${params.toString()}`);
  }

  const navigator = <aside className="materials-left-pane" aria-label="Materials navigator">
    <nav className="materials-navigator-modes" aria-label="Materials navigator modes">
      <button type="button" className={leftMode === "browse" ? "active" : ""} aria-current={leftMode === "browse" ? "page" : undefined} onClick={() => openBrowseTree(undefined)}>Browse</button>
      <button type="button" className={leftMode === "filters" ? "active" : ""} aria-current={leftMode === "filters" ? "page" : undefined} onClick={() => setLeftMode("filters")}>Filters</button>
      <button type="button" className={leftMode === "subsets" ? "active" : ""} aria-current={leftMode === "subsets" ? "page" : undefined} onClick={() => setLeftMode("subsets")}>Subsets</button>
    </nav>
    {leftMode === "filters" ? <div className="materials-filters">
      <label className="ux-field">Material class<select className="ux-select" name="material-class" value={materialClass} onChange={(event) => { setMaterialClass(event.target.value); setOffset(0); }}><option value="">All classes</option>{familyFacets.map((facet) => <option key={facet.material_class} value={facet.material_class}>{`${familyLabel(facet.material_class)} (${facet.count.toLocaleString()})`}</option>)}</select></label>
      <label className="ux-field">Provider<select className="ux-select" name="provider" value={provider} onChange={(event) => { setProvider(event.target.value); setOffset(0); }}><option value="">All providers</option>{providerFacets.map((facet) => <option key={facet.provider} value={facet.provider}>{`${facet.provider} (${facet.count.toLocaleString()})`}</option>)}</select></label>
      <label className="ux-field">Evidence source<select className="ux-select" name="evidence-source" value={evidenceSource} onChange={(event) => { setEvidenceSource(event.target.value); setOffset(0); }}><option value="">All sources</option>{evidenceSourceFacets.map((facet) => <option key={facet.evidence_source} value={facet.evidence_source}>{`${facet.evidence_source} (${facet.count.toLocaleString()})`}</option>)}</select></label>
      <button className="ux-button tertiary" type="button" onClick={() => { setMaterialClass(""); setProvider(""); setEvidenceSource(""); setOffset(0); }}>Clear filters</button>
    </div> : <MaterialsBrowseTree config={config} subsetMode={leftMode === "subsets"} publishedOnly requestedRecord={requestedRecord} onSelectRecord={selectBrowseRecord} onOpenRecord={openExactRecord} onScopeChange={changeScope} onScopeAvailabilityChange={changeScopeAvailability}/>}
  </aside>;

  const results = <section className="materials-results" aria-labelledby="material-results-title" aria-busy={loading}>
    <div className="materials-results-header"><div><h2 id="material-results-title">Materials</h2><p className="ux-meta">{loading ? "Loading…" : `${totalCount ? `${offset + 1}–${Math.min(offset + materials.length, totalCount)} of ` : ""}${new Intl.NumberFormat().format(totalCount)} matches`}</p></div><span className="ux-meta">Enter opens · select up to 3 to compare</span></div>
    {error ? <div className="ux-notice error" role="alert">{error}<button className="ux-button tertiary" type="button" onClick={() => setLoadAttempt((current) => current + 1)}>Retry</button></div> : null}
    {!loading && !error && !materials.length ? <div className="ux-empty"><strong>No materials match this search.</strong><p>Clear the search to return to the available Materials.</p><button className="ux-button tertiary" type="button" onClick={() => { setDraftQuery(""); setQuery(""); setMaterialClass(""); setProvider(""); setEvidenceSource(""); setOffset(0); }}>Clear search</button></div> : null}
    {comparedMaterials.length > 1 ? <div className="material-compare-strip"><div><strong>Comparing {comparedMaterials.length} materials</strong><span className="ux-meta">Selected materials remain available while you inspect results.</span></div>{comparedMaterials.map((material) => <dl key={material.material_id}><dt>{material.name}</dt><dd>{material.material_family ?? material.material_class}</dd><dd>r{material.record_revision_no}</dd></dl>)}<button className="ux-button tertiary" type="button" onClick={() => setCompareIds(new Set())}>Clear comparison</button></div> : null}
    {browseSelection ? <div className="browse-selection-bar"><span><strong>{browseSelection.record.current_revision.content.name}</strong><small>{domainKindLabel(browseSelection.graph.root.domain_binding?.kind)} · exact revision {browseSelection.record.current_revision.revision_no}</small></span><button className="ux-button tertiary" type="button" onClick={() => openExactRecord(browseSelection.record)}>Open datasheet</button></div> : null}
    <MaterialsScrollRegion id="materials-result-scroll" className="materials-result-table-wrap" shellClassName="materials-result-scroll-shell" aria-label="Scrollable material results">{materials.length ? <table className="materials-result-table" aria-label="Material results"><colgroup>{Object.entries(columnWidths).map(([key, width]) => <col key={key} style={{ width }} />)}</colgroup><thead><tr><th>Compare<EngineeringColumnResizeHandle label="Compare" width={columnWidths.compare} min={60} max={100} onChange={(width) => setColumnWidths((current) => ({ ...current, compare: width }))}/></th><th aria-sort={sortKey === "name" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("name")}>Material / grade {sortIndicator("name")}</button><EngineeringColumnResizeHandle label="Material or grade" width={columnWidths.material} min={180} max={420} onChange={(width) => setColumnWidths((current) => ({ ...current, material: width }))}/></th><th aria-sort={sortKey === "material_class" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("material_class")}>Family {sortIndicator("material_class")}</button><EngineeringColumnResizeHandle label="Family" width={columnWidths.materialClass} min={120} max={280} onChange={(width) => setColumnWidths((current) => ({ ...current, materialClass: width }))}/></th><th>Description<EngineeringColumnResizeHandle label="Description" width={columnWidths.summary} min={160} max={420} onChange={(width) => setColumnWidths((current) => ({ ...current, summary: width }))}/></th></tr></thead><tbody>
      {materials.map((material) => { const materialIdentity = `${material.name} · ${material.material_code ?? "No grade code"}`; return <tr key={material.material_id} className={selectedId === material.material_id ? "selected" : ""} tabIndex={0} aria-selected={selectedId === material.material_id} onClick={() => setSelectedId(material.material_id)} onDoubleClick={() => openMaterial(material)} onKeyDown={(event) => { if (event.key === "Enter") openMaterial(material); }}><td><input type="checkbox" aria-label={`Compare ${material.name}`} checked={compareIds.has(material.material_id)} disabled={!compareIds.has(material.material_id) && compareIds.size >= 3} onClick={(event) => event.stopPropagation()} onChange={() => toggleCompare(material.material_id)}/></td><td><button className="material-result-name" type="button" aria-current={selectedId === material.material_id ? "true" : undefined} title={materialIdentity} onClick={() => setSelectedId(material.material_id)}><span>{material.name}</span><small>{material.material_code ?? "No grade code"}</small></button></td><td title={material.material_class}>{familyLabel(material.material_class)}</td><td>{material.description ?? "—"}</td></tr>; })}
    </tbody></table> : null}</MaterialsScrollRegion>
    {!loading && totalCount > materials.length ? <nav className="materials-pagination" aria-label="Material result pages"><button className="ux-button tertiary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span className="ux-meta">Rows {totalCount ? offset + 1 : 0}–{Math.min(offset + materials.length, totalCount)}</span><button className="ux-button tertiary" type="button" disabled={offset + materials.length >= totalCount} onClick={() => setOffset(offset + 50)}>Next</button></nav> : null}
  </section>;

  const context = <aside className="materials-selection" aria-live="polite">
    {selected ? <>
      <div className="selection-heading"><div><p className="ux-kicker">Selected material</p><h2 title={selected.name}>{selected.name}</h2></div><span className="ux-meta">{selected.material_code ?? "No material code"}</span></div>
      <p>{selected.description ?? "No summary is available."}</p>
      <dl className="selection-context"><dt>Family</dt><dd>{familyLabel(selected.material_class)}</dd></dl>
      <div className="selection-delivery-command">
        <button className="ux-button primary" type="button" onClick={() => openMaterial(selected)}>Open datasheet</button>
      </div>
    </> : <div className="ux-empty"><strong>Select a material</strong><p>Choose a row to open its material record.</p></div>}
  </aside>;

  return (
    <div className="ux-page materials-page">
      <header className="materials-page-header" aria-label="Material query">
        <form className="materials-search-form" role="search" onSubmit={submit}>
          <label className="ux-field" style={{ flex: 1 }}><span className="sr-only">Material name, grade, code, or family</span><input className="ux-input" aria-label="Search materials" name="materials-query" autoComplete="off" value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder="Search material name, grade, code, or family…" /></label>
          <button className="ux-button primary" type="submit">Find</button>
        </form>
      </header>
      <ResizableSplitPane id="cmp-materials-results" navigator={navigator} main={results} context={context} navigatorLabel={leftMode === "filters" ? "filters" : "navigator"} contextLabel="details" />
    </div>
  );
}

function configurableValueText(value: ConfigurableRecordValue): string {
  if (value.data_type === "number") return `${value.original_value} ${value.original_unit_string || ""}`.trim();
  if (value.data_type === "integer" || value.data_type === "boolean") return String(value.value);
  if (value.data_type === "text" || value.data_type === "date" || value.data_type === "discrete") return value.value;
  if (value.data_type === "record_reference") return "Related Record";
  return `${value.data_type === "curve" ? "Curve" : "File"} artifact`;
}

function domainKindLabel(kind: string | null | undefined): string {
  const labels: Record<string, string> = {
    material: "Material",
    material_state: "Material state",
    specimen: "Specimen",
    test_run: "Test run",
    test_data: "Test data",
    processing_output: "Processing result",
    material_model: "Selected model",
    neutral_material: "Selected model",
    solver_card: "Solver card",
    neutral_solver_card: "Solver card",
    release: "Released record",
  };
  return kind ? labels[kind] ?? "Related record" : "Related record";
}

function CardTable({ config, material, cards, onNavigate }: { config: ApiConfig; material: MaterialResponse; cards: SolverCardSummary[]; onNavigate: (path: string) => void }) {
  if (!cards.length) return <div className="ux-empty compact"><strong>No native card is available.</strong><p>Create one from the selected source data below, or continue the selected material in Modeling.</p></div>;
  return <table className="ux-table cae-card-table"><thead><tr><th>Solver</th><th>Card</th><th>Format</th><th>Delivery</th></tr></thead><tbody>{cards.map((card) => <tr key={card.id}><td><strong>{card.solver}</strong></td><td title={card.label}>{card.label}</td><td>Native ASCII {card.extension}</td><td><div className="card-table-actions"><SolverCardAction config={config} card={card} material={deliveryMaterial(material)} onNavigate={onNavigate} directClassName="ux-button" reviewClassName="ux-button" includePreview/></div></td></tr>)}</tbody></table>;
}

export function MaterialDetailPage({ config, materialId, activeTab, onNavigate, exactPin }: Props & { materialId: string; activeTab: MaterialTab; exactPin?: MaterialRevisionPin }) {
  const [experience, setExperience] = useState<MaterialExperience | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [browseSelection, setBrowseSelection] = useState<BrowseSelection | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const experiencePromise = exactPin
      ? loadPinnedMaterialExperience(config, materialId, exactPin, true)
      : getMaterialDetail(config, materialId).then((detail) => loadMaterialExperience(config, detail.data.material, true));
    void experiencePromise.then((result) => {
      if (!active) return;
      setExperience(result);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
      setLoading(false);
    });
    return () => { active = false; };
  }, [config, materialId, exactPin?.materialRevisionId, exactPin?.recordId, exactPin?.recordRevisionId]);

  useEffect(() => {
    const material = experience?.detail.material;
    const selectedRevision = exactPin && experience?.catalogRecord
      ? experience.catalogRecord.current_revision
      : material?.current_revision;
    publishWorkspaceStatus({
      selection: material ? `${material.current_revision.content.name} · ${material.current_revision.content.material_code ?? "No grade"}` : "Material record",
      revision: selectedRevision ? `r${selectedRevision.revision_no}` : "Loading revision",
      jobs: "No active job",
      warnings: error ? "1 workspace error" : "0 warnings",
      connection: error ? "degraded" : "online",
    });
  }, [error, exactPin, experience]);

  if (loading) return <div className="ux-page"><div className="material-detail-shell"><p className="loading-state">Loading material…</p></div></div>;
  if (error || !experience) return <div className="ux-page"><div className="material-detail-shell"><div className="ux-notice error" role="alert">{error ?? "Material not found."}</div><button className="ux-button" type="button" onClick={() => onNavigate(materialsReturnPath())}>Back to Materials</button></div></div>;

  const material = experience.detail.material;
  const content = material.current_revision.content;
  const recordContent = experience.catalogRecord?.current_revision.content;
  const displayName = recordContent?.name ?? content.name;
  const displayCode = recordContent?.external_key ?? content.material_code;
  const displayDescription = recordContent?.description ?? content.description;
  const selectedRevision = exactPin && experience.catalogRecord
    ? experience.catalogRecord.current_revision
    : material.current_revision;
  const propertySet = currentProperty(experience);
  const property = propertySet?.current_revision.content;
  const catalogRoot = experience.graph?.root ?? null;
  const preferredCard = experience.cards.find((card) => card.solver === "OpenRadioss") ?? experience.cards[0] ?? null;
  const neutralMaterial = neutralMaterialBinding(experience);
  const relatedLinks = (experience.graph?.links ?? []).filter((link) =>
    link.source.record_id === catalogRoot?.record_id || link.target.record_id === catalogRoot?.record_id,
  ).map((link) => {
    const fromRoot = link.source.record_id === catalogRoot?.record_id;
    return {
      id: link.record_link_id,
      label: fromRoot ? link.link_type_revision.content.forward_label : link.link_type_revision.content.reverse_label,
      endpoint: fromRoot ? link.target : link.source,
    };
  });
  const activePath = materialDetailPath(materialId, activeTab, exactPin);
  const navigateDetail = (path: string): void => {
    if (!exactPin || !path.startsWith(`/materials/${materialId}`)) {
      onNavigate(path);
      return;
    }
    const query = materialPinQuery(exactPin);
    onNavigate(`${path}${path.includes("?") ? "&" : "?"}${query}`);
  };
  const navigator = <aside className="materials-left-pane" aria-label="Materials Browse Tree"><div className="workspace-back-row"><button className="ux-button tertiary" type="button" onClick={() => onNavigate(materialsReturnPath())}><EngineeringIcon name="back"/> <span>Results</span></button><strong>Browse</strong></div><MaterialsBrowseTree config={config} publishedOnly requestedRecord={catalogRoot} onSelectRecord={(record, graph) => setBrowseSelection({ record, graph })} onOpenRecord={(record) => onNavigate(`/materials/records/${record.record_id}/revisions/${record.current_revision.id}`)}/></aside>;
  const context = <aside className="materials-selection material-related-context" aria-label="Related exact records"><p className="ux-kicker">{exactPin ? "Selected revision" : "Current revision"}</p><div className="context-record-title">{displayName}</div><p className="ux-meta">{displayDescription ?? "No summary is available."}</p><dl className="selection-context"><dt>Revision</dt><dd>r{selectedRevision.revision_no}</dd><dt>Related</dt><dd>{relatedLinks.length} {relatedLinks.length === 1 ? "record" : "records"}</dd></dl>{browseSelection ? <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/records/${browseSelection.record.record_id}/revisions/${browseSelection.record.current_revision.id}`)}>Open {browseSelection.record.current_revision.content.name}</button> : null}<h3>Related records</h3><ul className="related-record-list">{relatedLinks.slice(0, 12).map((related) => <li key={related.id}><button type="button" onClick={() => onNavigate(`/materials/records/${related.endpoint.record_id}/revisions/${related.endpoint.record_revision_id}`)}><span>{related.endpoint.name}</span><small>{related.label} · r{related.endpoint.revision_no}</small></button></li>)}</ul></aside>;

  function acceptCreatedCard(card: SolverCardSummary): void {
    setExperience((current) => current ? { ...current, cards: [...current.cards, card] } : current);
    navigateDetail(`/materials/${materialId}/cards/${card.id}`);
  }

  const datasheet = <div className="material-detail-shell">
    <header className="material-detail-header"><div><h1>{displayName}</h1><p>{displayDescription ?? "No summary is available."}</p><div className="material-detail-meta"><span>{displayCode ?? "No grade code"}</span><span>{content.material_family ?? content.material_class}</span><span>{sourceLabel(experience)}</span></div></div><div className="card-action-row">{preferredCard ? <SolverCardAction config={config} card={preferredCard} material={deliveryMaterial(material)} onNavigate={navigateDetail}/> : neutralMaterial ? <button className="ux-button primary" type="button" onClick={() => navigateDetail(`/materials/${materialId}/cards`)}>Create card</button> : modelingFamily(material) ? <button className="ux-button primary" type="button" onClick={() => startModeling(material, onNavigate)}>Start Modeling</button> : <p className="ux-notice" role="status">Modeling is not supported for this family.</p>}<ReviewRequestAction config={config} subject={{ aggregateType: "catalog.material", aggregateId: material.material_id, revisionId: material.current_revision.id, manifestSha256: material.current_revision.content_hash, classification: material.current_revision.classification, lifecycleState: material.current_revision.lifecycle_state }} /></div></header>
    <nav className="ux-tabs" role="tablist" aria-label="Material detail"><input type="hidden" value={activePath} readOnly />{tabs.map((tab) => <button key={tab.id} className="ux-tab" type="button" role="tab" aria-selected={activeTab === tab.id} onClick={() => onNavigate(materialDetailPath(materialId, tab.id, exactPin))}>{tab.label}</button>)}</nav>
    <section className="material-tab-panel" role="tabpanel">
      {activeTab === "overview" ? <div className="overview-grid"><div><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Engineering summary</p><h2>Key properties</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(materialDetailPath(materialId, "properties", exactPin))}>All properties</button></div><div className="overview-property-grid"><div><span>Density</span><strong>{formatDensity(property?.density_kg_per_m3)}</strong></div><div><span>Young’s modulus</span><strong>{formatPressure(property?.youngs_modulus_pa)}</strong></div><div><span>Yield strength</span><strong>{formatPressure(property?.yield_stress_pa)}</strong></div><div><span>Poisson ratio</span><strong>{property?.poisson_ratio ?? "—"}</strong></div></div></section><div className="overview-data-grid"><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Representative curve</p><h2>Linked material response</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(materialDetailPath(materialId, "curves", exactPin))}>All curves</button></div><div className="material-overview-response-cluster"><RepresentativeCurve points={experience.representativeCurve}/><ResponsePointsTable points={experience.representativeCurve}/></div></section><section className="overview-section"><p className="ux-kicker">Application conditions</p><h2>Material states</h2><dl className="condition-summary"><dt>Temperature</dt><dd>{property?.applicability.temperature_min_k ?? "—"}–{property?.applicability.temperature_max_k ?? "—"} K</dd><dt>Strain rate</dt><dd>{property?.applicability.strain_rate_min_per_s ?? "—"}–{property?.applicability.strain_rate_max_per_s ?? "—"} /s</dd></dl>{experience.detail.states.slice(0, 2).map((state) => <p className="condition-state" key={state.material_state_id}><strong>{state.current_revision.content.name}</strong><span>{state.current_revision.content.manufacturing_route ?? "Route not specified"}</span></p>)}</section></div></div><aside><p className="ux-kicker">CAE delivery</p><h2>Ready solver cards</h2><p>Choose a native format. Open a card preview to check delivery notes before downloading.</p><SolverAvailability cards={experience.cards}/><div className="solver-preview-links">{experience.cards.map((card) => <button key={card.id} type="button" onClick={() => navigateDetail(`/materials/${materialId}/cards/${card.id}`)}>Preview {card.solver} {card.extension}</button>)}</div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(browsePath(experience))}>Related records in Browse Tree</button></aside></div> : null}
      {activeTab === "properties" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Material values</p><h2>Engineering properties</h2></div></div>{property ? <table className="ux-table"><thead><tr><th>Property</th><th>Value</th><th>Source</th></tr></thead><tbody><tr><td>Density</td><td>{formatDensity(property.density_kg_per_m3)}</td><td>{property.density_source.reference ?? "Material record"}</td></tr><tr><td>Young’s modulus</td><td>{formatPressure(property.youngs_modulus_pa)}</td><td>{property.youngs_modulus_source.reference ?? "Material record"}</td></tr><tr><td>Poisson ratio</td><td>{property.poisson_ratio}</td><td>{property.poisson_ratio_source.reference ?? "Material record"}</td></tr><tr><td>Yield strength</td><td>{formatPressure(property.yield_stress_pa)}</td><td>{property.yield_stress_source?.reference ?? "Material record"}</td></tr></tbody></table> : <div className="ux-empty">No material values are available.</div>}{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} revisionId={exactPin?.recordRevisionId} mode="properties"/> : null}</> : null}
      {activeTab === "curves" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Test and model data</p><h2>Curves</h2><p>Review available workflow data in the persistent Modeling graph.</p></div><button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Open in Modeling</button></div>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} revisionId={exactPin?.recordRevisionId} mode="curves"/> : null}<table className="ux-table"><thead><tr><th>Related data</th><th>Type</th><th>Use</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).flatMap((node) => nodeBindings(node).filter((binding) => ["test_data", "processing_output", "material_model"].includes(binding.kind)).map((binding) => ({ node, binding }))).map(({ node, binding }) => <tr key={`${node.record_id}:${node.record_revision_id}:${binding.kind}:${binding.object_id}:${binding.revision_id}`}><td>{binding.workbench_path ? <a href={binding.workbench_path}>{node.name}</a> : node.name}</td><td>{domainKindLabel(binding.kind)}</td><td>{binding.kind === "test_data" ? "Observed input" : binding.kind === "processing_output" ? "Processed curve" : "Fitted response"}</td></tr>)}</tbody></table></> : null}
      {activeTab === "cards" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Solver delivery</p><h2>CAE Cards</h2><p>Cards with unchanged values can download directly. Cards with delivery notes open a review before download; values the solver cannot represent remain unavailable.</p></div></div><CardTable config={config} material={material} cards={experience.cards} onNavigate={navigateDetail}/>{neutralMaterial ? <NeutralCardCreationPanel config={config} neutralMaterialId={neutralMaterial.object_id} neutralMaterialRevisionId={neutralMaterial.revision_id} materialName={content.name} materialCode={content.material_code} existingCards={experience.cards} onCreated={acceptCreatedCard}/> : !experience.cards.length && modelingFamily(material) ? <button className="ux-button primary" type="button" onClick={() => startModeling(material, onNavigate)}>Start Modeling</button> : null}</> : null}
      {activeTab === "evidence" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Related · Workflow · Evidence</p><h2>Connected material record</h2><p>Follow related records and the material workflow; open technical identifiers only when needed.</p></div><button className="ux-button" type="button" onClick={() => onNavigate(browsePath(experience))}>Open exact datasheet</button></div><div className="evidence-overview"><section><h3>Related Records</h3>{relatedLinks.length ? <table className="ux-table"><thead><tr><th>Relationship</th><th>Record</th><th>Type</th><th>Revision</th></tr></thead><tbody>{relatedLinks.map((related) => <tr key={related.id}><td>{related.label}</td><td title={related.endpoint.name}>{related.endpoint.domain_binding?.workbench_path ? <a href={related.endpoint.domain_binding.workbench_path}>{related.endpoint.name}</a> : related.endpoint.name}</td><td>{domainKindLabel(related.endpoint.domain_binding?.kind)}</td><td>r{related.endpoint.revision_no}</td></tr>)}</tbody></table> : <p className="ux-meta">No related records are visible in the current view.</p>}</section><section><h3>Workflow</h3><table className="ux-table"><thead><tr><th>Record</th><th>Role</th><th>Revision</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).flatMap((node) => nodeBindings(node).map((binding) => ({ node, binding }))).map(({ node, binding }) => <tr key={`${node.record_id}:${node.record_revision_id}:${binding.kind}:${binding.object_id}:${binding.revision_id}`}><td title={node.name}>{binding.workbench_path ? <a href={binding.workbench_path}>{node.name}</a> : node.name}</td><td>{domainKindLabel(binding.kind)}</td><td>r{node.revision_no}</td></tr>)}</tbody></table></section></div>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} revisionId={exactPin?.recordRevisionId} mode="evidence"/> : null}<details className="ux-disclosure"><summary>Technical revision and provenance identifiers</summary><dl className="evidence-grid"><dt>Material ID</dt><dd>{material.material_id}</dd><dt>Aggregate ID</dt><dd>{material.current_revision.aggregate_id}</dd><dt>Full revision ID</dt><dd>{material.current_revision.id}</dd><dt>Content hash</dt><dd>{material.current_revision.content_hash}</dd><dt>Classification</dt><dd>{material.current_revision.classification}</dd><dt>Change reason</dt><dd>{material.current_revision.change_reason}</dd><dt>Recorded by</dt><dd>{material.current_revision.provenance.recorded_by}</dd></dl></details></> : null}
    </section>
  </div>;
  return <div className="ux-page materials-page materials-datasheet-page"><ResizableSplitPane id="cmp-materials-datasheet" navigator={navigator} main={datasheet} context={context} navigatorLabel="navigator" contextLabel="related records" /></div>;
}

export function ExactRecordDatasheetPage({ config, recordId, revisionId, onNavigate }: Props & { recordId: string; revisionId: string }) {
  const [record, setRecord] = useState<ConfigurableCatalogRecordResponse | null>(null);
  const [revisions, setRevisions] = useState<ConfigurableCatalogRecordResponse["current_revision"][]>([]);
  const [graph, setGraph] = useState<CatalogWorkflowGraphResponse | null>(null);
  const [browseSelection, setBrowseSelection] = useState<BrowseSelection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void getConfigurableCatalogRecord(config, recordId).then(async (head) => {
      const [revisionResult] = await Promise.all([
        listConfigurableCatalogRecordRevisions(config, recordId),
      ]);
      const exact = revisionResult.data.items.find((item) => item.id === revisionId);
      if (!exact) throw new Error("The requested immutable record revision does not exist.");
      // Materials exact datasheets are a published surface.  Keep the private
      // Administration record route separate; a missing/invalidated approved
      // projection must fail closed before rendering any values here.
      const exactGraph = (await getCatalogWorkflowGraph(config, recordId, revisionId, 6, true)).data;
      if (!active) return;
      setRecord({ ...head.data, current_revision: exact });
      setRevisions(revisionResult.data.items);
      setGraph(exactGraph);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
      setLoading(false);
    });
    return () => { active = false; };
  }, [attempt, config, recordId, revisionId]);

  useEffect(() => {
    publishWorkspaceStatus({
      selection: record?.current_revision.content.name ?? "Exact catalog record",
      revision: record ? `r${record.current_revision.revision_no} · exact` : "Loading revision",
      jobs: "No active job",
      warnings: error ? "1 workspace error" : "0 warnings",
      connection: error ? "degraded" : "online",
    });
  }, [error, record]);

  const related = graph ? graph.links.map((link) => {
    const fromRoot = link.source.record_id === recordId;
    return {
      id: link.record_link_id,
      label: fromRoot ? link.link_type_revision.content.forward_label : link.link_type_revision.content.reverse_label,
      endpoint: fromRoot ? link.target : link.source,
    };
  }) : [];
  const navigator = <aside className="materials-left-pane" aria-label="Materials Browse Tree"><div className="workspace-back-row"><button className="ux-button tertiary" type="button" onClick={() => onNavigate(materialsReturnPath())}><EngineeringIcon name="back"/> <span>Results</span></button><strong>Browse</strong></div><MaterialsBrowseTree config={config} publishedOnly requestedRecord={graph?.root ?? null} onSelectRecord={(nextRecord, nextGraph) => setBrowseSelection({ record: nextRecord, graph: nextGraph })} onOpenRecord={(nextRecord) => onNavigate(`/materials/records/${nextRecord.record_id}/revisions/${nextRecord.current_revision.id}`)}/></aside>;
  const main = <section className="exact-record-datasheet material-tab-panel" aria-labelledby="exact-record-title">
    {loading && record ? <div className="datasheet-loading-line">Loading exact revision…</div> : null}
    {loading && !record ? <p className="loading-state">Loading exact record revision…</p> : null}
    {error ? <div className="ux-notice error" role="alert">{error}<button className="ux-button tertiary" type="button" onClick={() => setAttempt((current) => current + 1)}>Retry</button></div> : null}
    {record ? <><header className="exact-record-header"><div><p className="ux-kicker">Exact record revision</p><h1 id="exact-record-title">{record.current_revision.content.name}</h1><p>{record.current_revision.content.description ?? "No record description is available."}</p></div><div className="exact-revision-mark"><strong>r{record.current_revision.revision_no}</strong><span>Immutable</span></div></header>{!record.current_revision.content.values.length ? <div className="ux-empty"><strong>No values in this revision.</strong><p>Revision details remain available in Evidence.</p></div> : null}<MaterialDatasheetProjection config={config} tableId={record.table_id} recordId={record.record_id} revisionId={revisionId} mode="properties"/><details className="ux-disclosure"><summary>Evidence and immutable identifiers</summary><dl className="evidence-grid"><dt>Record ID</dt><dd>{record.record_id}</dd><dt>Revision ID</dt><dd>{record.current_revision.id}</dd><dt>Content hash</dt><dd>{record.current_revision.content_hash}</dd><dt>Classification</dt><dd>{record.current_revision.classification}</dd><dt>Change reason</dt><dd>{record.current_revision.change_reason}</dd></dl></details></> : null}
  </section>;
  const context = <aside className="materials-selection material-related-context" aria-label="Revision and related record context"><p className="ux-kicker">Record context</p><h2>{record?.current_revision.content.name ?? "Catalog record"}</h2>{browseSelection ? <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/records/${browseSelection.record.record_id}/revisions/${browseSelection.record.current_revision.id}`)}>Open selected record</button> : null}<h3>Revisions</h3><ul className="related-record-list">{revisions.map((revision) => <li key={revision.id}><button type="button" aria-current={revision.id === revisionId ? "page" : undefined} onClick={() => onNavigate(`/materials/records/${recordId}/revisions/${revision.id}`)}><span>Revision {revision.revision_no}</span><small>{revision.change_reason}</small></button></li>)}</ul><h3>Related exact records</h3><ul className="related-record-list">{related.slice(0, 12).map((item) => <li key={item.id}><button type="button" onClick={() => onNavigate(`/materials/records/${item.endpoint.record_id}/revisions/${item.endpoint.record_revision_id}`)}><span>{item.endpoint.name}</span><small>{item.label} · r{item.endpoint.revision_no}</small></button></li>)}</ul></aside>;

  return <div className="ux-page materials-page materials-datasheet-page"><ResizableSplitPane id="cmp-materials-exact-record" navigator={navigator} main={main} context={context} navigatorLabel="navigator" contextLabel="record context" /></div>;
}

export function SolverCardPreviewPage({ config, materialId, cardId, exactPin, onNavigate }: Props & { materialId: string; cardId: string; exactPin?: MaterialRevisionPin }) {
  const [material, setMaterial] = useState<MaterialResponse | null>(null);
  const [card, setCard] = useState<SolverCardSummary | null>(null);
  const [evidence, setEvidence] = useState<SolverCardEvidence | null>(null);
  const [preview, setPreview] = useState("");
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setAcknowledged(false);
    const experiencePromise = exactPin
      ? loadPinnedMaterialExperience(config, materialId, exactPin)
      : getMaterialDetail(config, materialId).then((detail) => loadMaterialExperience(config, detail.data.material));
    void experiencePromise
      .then(async (result) => {
      const found = result.cards.find((item) => item.id === cardId);
      if (!found) throw new Error("The requested solver card is not linked to this material revision.");
      const [previewResult, evidenceResult] = await Promise.all([
        previewSolverCardText(config, found),
        loadSolverCardEvidence(config, found),
      ]);
      if (!active) return;
      setMaterial(result.detail.material);
      setCard(found);
      setPreview(previewResult.data);
      setEvidence(evidenceResult);
      recordDeliveryActivity({
        action: "preview",
        ...deliveryMaterial(result.detail.material),
        cardId: found.id,
        cardRevisionId: found.revisionId,
        cardLabel: found.label,
        solver: found.solver,
        extension: found.extension,
      });
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
      void recordActivityRecovery(
        config,
        { kind: "solver_card", path: `/materials/${materialId}/cards/${cardId}`, materialId, solverCardId: cardId },
        "failed",
        messageFor(cause),
      );
      setLoading(false);
    });
    return () => { active = false; };
  }, [cardId, config, exactPin?.materialRevisionId, exactPin?.recordId, exactPin?.recordRevisionId, materialId]);

  async function downloadCard(): Promise<void> {
    if (!card || !material || !evidence || evidence.disposition === "blocked") return;
    if (evidence.disposition === "review" && !acknowledged) return;
    setDownloading(true);
    setError(null);
    try {
      const result = await downloadSolverCardArtifact(config, card);
      triggerDownload(result.data.blob, result.data.filename);
      recordDeliveryActivity({
        action: "download",
        ...deliveryMaterial(material),
        cardId: card.id,
        cardRevisionId: card.revisionId,
        cardLabel: card.label,
        solver: card.solver,
        extension: card.extension,
      });
      void recordActivityRecovery(
        config,
        {
          kind: "solver_card",
          path: `/materials/${materialId}/cards/${card.id}`,
          materialId,
          materialRevisionId: material.current_revision.id,
          solverCardId: card.id,
          solverCardRevisionId: card.revisionId,
        },
        "succeeded",
        `Downloaded exact ${card.label}.`,
      );
    } catch (cause: unknown) {
      setError(messageFor(cause));
      void recordActivityRecovery(
        config,
        {
          kind: "solver_card",
          path: `/materials/${materialId}/cards/${card?.id ?? cardId}`,
          materialId,
          materialRevisionId: material.current_revision.id,
          solverCardId: card?.id ?? cardId,
          solverCardRevisionId: card?.revisionId,
        },
        "failed",
        messageFor(cause),
      );
    } finally {
      setDownloading(false);
    }
  }

  async function downloadMapping(): Promise<void> {
    if (!evidence) return;
    try {
      const result = await downloadSolverMappingArtifact(config, evidence);
      triggerDownload(result.blob, result.filename);
      void recordActivityRecovery(
        config,
        {
          kind: "solver_card",
          path: `/materials/${materialId}/cards/${card?.id ?? cardId}`,
          materialId,
          materialRevisionId: material?.current_revision.id,
          solverCardId: card?.id ?? cardId,
          solverCardRevisionId: card?.revisionId,
        },
        "succeeded",
        "Downloaded the exact solver mapping report.",
      );
    } catch (cause: unknown) {
      setError(messageFor(cause));
      void recordActivityRecovery(
        config,
        {
          kind: "solver_card",
          path: `/materials/${materialId}/cards/${card?.id ?? cardId}`,
          materialId,
          materialRevisionId: material?.current_revision.id,
          solverCardId: card?.id ?? cardId,
          solverCardRevisionId: card?.revisionId,
        },
        "failed",
        messageFor(cause),
      );
    }
  }

  const taskPreview = preview
    .split("\n")
    .filter((line) => !/^(?:#|\*\*) CMP/.test(line))
    .join("\n");

  const reviewRequired = evidence?.disposition === "review";
  const blocked = evidence?.disposition === "blocked";
  const linkedResponsePoints = blocked ? [] : curveFromNativeCard(preview);
  const downloadDisabled = loading || downloading || !preview || !evidence || blocked || (reviewRequired && !acknowledged);
  const downloadLabel = blocked ? "Download blocked" : downloading ? "Preparing…" : `Download ${card?.extension ?? "card"}`;
  const downloadConsequence = loading || !evidence
    ? "Delivery checks are loading before this card can be downloaded."
    : blocked
      ? "This card cannot be downloaded because some values are not supported by the selected solver."
      : reviewRequired
        ? "Review the highlighted delivery note, then acknowledge it to enable this download."
        : "Delivery checks pass for this target, so this download is ready.";

  return <div className="ux-page"><div className="card-preview-shell">
    <header className="card-preview-header">
      <div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(materialDetailPath(materialId, "cards", exactPin))}><EngineeringIcon name="back"/> <span>CAE Cards</span></button><p className="ux-kicker">{card?.solver ?? "Solver card"} · Native ASCII</p><h1>{card?.label ?? material?.current_revision.content.name ?? "Card preview"}</h1><p>Check the saved card and delivery details before downloading.</p></div>
      <div className="card-action-row"><ReviewRequestAction config={config} subject={evidence ? { aggregateType: evidence.reviewAggregateType, aggregateId: card?.id ?? cardId, revisionId: evidence.reviewRevisionId, manifestSha256: evidence.reviewContentHash, classification: evidence.reviewClassification, lifecycleState: evidence.lifecycleState } : null} /></div>
    </header>
    {error ? <div className="ux-notice error" role="alert">{error}</div> : null}
    <div className="card-preview-content">
      <section className={`native-preview${linkedResponsePoints.length >= 2 ? " has-linked-response" : ""}`} aria-label="Native card and linked response">
        <NativeCardPreview text={loading ? "Loading native card preview…" : taskPreview}/>
        <LinkedResponseGraph points={linkedResponsePoints}/>
      </section>
      <aside className="card-preview-actions">
        <p className="ux-kicker">Delivery properties</p>
        <h2>{card?.solver ?? "Solver"}</h2>
        {evidence ? <dl className="delivery-card-properties"><div><dt>Target</dt><dd>{evidence.target.solver} {evidence.target.version}</dd></div><div><dt>Format</dt><dd>Native {card?.extension ?? "card"}</dd></div><div><dt>Unit system</dt><dd>{evidence.target.unit_system.replaceAll("_", " · ")}</dd></div></dl> : <p className="delivery-progress-line">Loading delivery checks…</p>}
        <div className="card-preview-delivery-command">
          <button className="ux-button primary" type="button" disabled={downloadDisabled} onClick={() => void downloadCard()}>{downloadLabel}</button>
          <p className={`card-preview-delivery-consequence${blocked ? " blocked" : reviewRequired ? " review" : ""}`} {...(blocked ? { role: "alert" } : {})}>{downloadConsequence}</p>
        </div>
        {evidence ? <><h3>Delivery check</h3><MappingStatusList items={evidence.mappingItems} reviewAcknowledgement={reviewRequired ? <label className="delivery-acknowledgement"><input name="mapping-delivery-acknowledgement" type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)}/>I reviewed the delivery notes before downloading this card.</label> : undefined}/></> : null}
        <button className="ux-button" type="button" onClick={() => onNavigate(materialDetailPath(materialId, "overview", exactPin))}>Return to material</button>
        <details className="ux-disclosure"><summary>Advanced mapping evidence</summary><p className="ux-meta">The mapping report records exact, transformed, approximated, ignored, and unsupported fields. The native file retains its provenance headers.</p><button className="ux-button" type="button" disabled={!evidence} onClick={() => void downloadMapping()}>Download mapping report</button><dl className="evidence-grid"><dt>Card ID</dt><dd>{cardId}</dd><dt>Exact revision</dt><dd>{card?.revisionId ?? "Loading…"}</dd><dt>Card checksum</dt><dd>{evidence?.cardSha256 ?? "Recorded after generation"}</dd><dt>Mapping checksum</dt><dd>{evidence?.mappingReportSha256 ?? "Loading…"}</dd></dl></details>
      </aside>
    </div>
  </div></div>;
}

type ActivityView = "needs-attention" | "in-progress" | "recent-outcomes";

const ACTIVITY_VIEWS: Array<{ id: ActivityView; label: string }> = [
  { id: "needs-attention", label: "Needs attention" },
  { id: "in-progress", label: "In progress" },
  { id: "recent-outcomes", label: "Recent outcomes" },
];

export function ActivityPage({
  config,
  onNavigate,
  locationSearch = "",
}: Pick<Props, "config" | "onNavigate"> & { locationSearch?: string }) {
  const modelingSession = useMemo(() => loadModelingSession(), []);
  const deliveryActivities = useMemo(() => loadDeliveryActivities(), []);
  const [role, setRole] = useState<ProductRole | null>(null);
  const [principalId, setPrincipalId] = useState<string | null>(null);
  const [reviewRequests, setReviewRequests] = useState<ReviewRequestResponse[]>([]);
  const [processingBatches, setProcessingBatches] = useState<CommonProcessingBatchResponse[]>([]);
  const [processingBatchContexts, setProcessingBatchContexts] = useState<Record<string, ProcessingBatchMaterialContext>>({});
  const [processingBatchError, setProcessingBatchError] = useState<string | null>(null);
  const [recoveryFacts, setRecoveryFacts] = useState<ActivityRecoveryFact[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [retryingBatchId, setRetryingBatchId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ActivityView>("in-progress");
  const initializedRole = useRef<ProductRole | null>(null);
  const activityViewButtons = useRef<Partial<Record<ActivityView, HTMLButtonElement>>>({});
  const requestSequence = useRef(0);
  const governedContext = useMemo(() => {
    const query = new URLSearchParams(locationSearch);
    return [
      ["Candidate", query.get("candidate_id"), query.get("candidate_revision_id")],
      ["Validation result", query.get("validation_result_id"), null],
      ["Solver Card", query.get("solver_card_id"), query.get("solver_card_revision_id")],
    ].filter((entry): entry is [string, string, string | null] => Boolean(entry[1]));
  }, [locationSearch]);
  useEffect(() => publishWorkspaceStatus({ selection: "Current workspace activity", revision: "Current user", jobs: "No active job", warnings: "0 warnings", connection: "online" }), []);

  async function loadQueue(): Promise<void> {
    const sequence = ++requestSequence.current;
    setLoadingQueue(true);
    setQueueError(null);
    setProcessingBatchError(null);
    try {
      const [accessResult, principalResult, requestsResult, batchResult, documentsResult, metalMaterials, polymerMaterials, elastomerMaterials] = await Promise.all([
        getEffectiveProductAccess(config),
        getAuthenticatedPrincipal(config),
        listReviewRequests(config, { limit: 50 }),
        listCommonProcessingBatches(config)
          .then((result) => ({ result, error: null as string | null }))
          .catch((cause: unknown) => ({ result: null, error: messageFor(cause) })),
        listCanonicalTestDataDocuments(config).catch(() => null),
        listMaterials(config, "", "metal").catch(() => null),
        listMaterials(config, "", "polymer").catch(() => null),
        listMaterials(config, "", "elastomer").catch(() => null),
      ]);
      if (sequence !== requestSequence.current) return;
      const nextRole = accessResult.data.product_role;
      // Seed the role default in the same render as the access result so a
      // reviewer never sees the User/Admin panel during the access handshake.
      // The effect below still handles a later role change without overriding
      // a tab the user has already selected.
      if (initializedRole.current === null) {
        initializedRole.current = nextRole;
        setActiveView(nextRole === "reviewer" ? "needs-attention" : "in-progress");
      }
      setRole(nextRole);
      setPrincipalId(principalResult.data.principal_id);
      setReviewRequests(requestsResult.data.items);
      setProcessingBatches(batchResult.result?.data.items ?? []);
      setProcessingBatchError(batchResult.error);
      const documents = documentsResult?.data.items ?? [];
      const materialsByFamily = {
        metal: metalMaterials?.data.items ?? [],
        polymer: polymerMaterials?.data.items ?? [],
        elastomer: elastomerMaterials?.data.items ?? [],
      } satisfies Record<ProcessingBatchMaterialContext["family"], MaterialResponse[]>;
      setProcessingBatchContexts(Object.fromEntries(
        (batchResult.result?.data.items ?? []).flatMap((batch) => {
          const context = processingBatchMaterialContext(batch, documents, materialsByFamily);
          return context ? [[batch.batch_id, context] as const] : [];
        }),
      ));
      setRecoveryFacts(readActivityRecoveries(
        principalResult.data.principal_id,
        principalResult.data.organization_id,
        principalResult.data.project_id,
      ));
    } catch (cause) {
      if (sequence !== requestSequence.current) return;
      setQueueError(messageFor(cause));
    } finally {
      if (sequence === requestSequence.current) setLoadingQueue(false);
    }
  }

  useEffect(() => {
    void loadQueue();
    return () => { requestSequence.current += 1; };
  }, [config.baseUrl, config.accessToken]);

  useEffect(() => {
    if (!role || initializedRole.current === role) return;
    initializedRole.current = role;
    setActiveView(role === "reviewer" ? "needs-attention" : "in-progress");
  }, [role]);

  async function decide(request: ReviewRequestResponse, decision: "approved" | "changes_requested"): Promise<void> {
    const reason = decisionReason.trim();
    if (!reason) {
      setDecisionError("Add a reason before recording this review decision.");
      return;
    }
    setDecidingId(request.review_request_id);
    setDecisionError(null);
    try {
      const result = await createReviewDecision(config, request.review_request_id, {
        expected_manifest_sha256: request.manifest_sha256,
        decision,
        reason,
      });
      setReviewRequests((items) => items.map((item) => item.review_request_id === result.data.review_request_id ? result.data : item));
      setReviewingId(null);
      setDecisionReason("");
      setActiveView("recent-outcomes");
    } catch (cause) {
      setDecisionError(messageFor(cause));
    } finally {
      setDecidingId(null);
    }
  }

  async function retryFailedBatch(batch: CommonProcessingBatchResponse): Promise<void> {
    setRetryingBatchId(batch.batch_id);
    try {
      const result = await retryFailedCommonProcessingBatch(config, batch.batch_id);
      setProcessingBatches((items) => items.map((item) => item.batch_id === result.data.batch_id ? result.data : item));
      setActiveView("recent-outcomes");
    } catch (cause) {
      setQueueError(messageFor(cause));
    } finally {
      setRetryingBatchId(null);
    }
  }

  function processingBatchPath(batch: CommonProcessingBatchResponse): string {
    const context = processingBatchContexts[batch.batch_id];
    const query = new URLSearchParams({
      stage: "process",
      batch_id: batch.batch_id,
      classification: batch.classification,
      recipe_id: batch.recipe_id,
      recipe_revision_id: batch.recipe_revision_id,
    });
    if (context) {
      query.set("family", context.family);
      query.set("material_id", context.materialId);
      query.set("material_revision_id", context.materialRevisionId);
      query.set("material_state_id", context.materialStateId);
      query.set("material_state_revision_id", context.materialStateRevisionId);
    }
    batch.members.forEach((member) => {
      query.append("source_document_id", member.source.document_id);
      query.append("source_revision_id", member.source.revision_id);
    });
    return `/modeling?${query.toString()}`;
  }

  const resumePath = modelingSession ? `/modeling?stage=${modelingSession.workspace.activeStage}&family=${modelingSession.materialFamily}` : "/modeling";
  const stageLabel = modelingSession ? `${modelingSession.workspace.activeStage[0].toUpperCase()}${modelingSession.workspace.activeStage.slice(1)}` : null;
  // Visibility is server/RLS scoped. Keep a defensive owner filter for non-reviewers
  // so an accidentally over-broad response cannot expose another user's request;
  // Reviewer queues remain the server-authorized decision surface.
  const canDecide = role === "reviewer";
  const visibleRequests = canDecide
    ? reviewRequests
    : reviewRequests.filter((request) => request.requested_by === principalId);
  const pendingRequests = visibleRequests.filter((request) => request.decision === null);
  const decidedRequests = visibleRequests.filter((request) => request.decision !== null);
  const failedBatches = processingBatches.filter((batch) => batch.status === "failed" || batch.status === "partial");
  const recoveredBatches = processingBatches.filter((batch) => batch.status === "succeeded" && batch.attempts.some((attempt) => attempt.attempt_no > 1));
  const activeRecoveryFacts = recoveryFacts.filter((fact) => fact.status === "failed");
  const recoveryOutcomes = recoveryFacts.filter((fact) => fact.status === "succeeded");
  const needsAttention = canDecide ? pendingRequests : [];
  const inProgress = canDecide ? [] : pendingRequests;
  const roleLabel = role === "reviewer" ? "Reviewer queue" : role ? "User queue" : "Activity queue";
  const roleDescription = role === "reviewer"
    ? "Requests awaiting a decision, plus local work and outcomes."
    : "Your pending requests and browser-local work.";
  const activateView = (view: ActivityView, focus = false) => {
    setActiveView(view);
    if (focus) window.requestAnimationFrame(() => activityViewButtons.current[view]?.focus());
  };
  const handleViewKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, current: ActivityView) => {
    const index = ACTIVITY_VIEWS.findIndex((view) => view.id === current);
    const next = event.key === "ArrowRight" || event.key === "ArrowDown"
      ? ACTIVITY_VIEWS[(index + 1) % ACTIVITY_VIEWS.length].id
      : event.key === "ArrowLeft" || event.key === "ArrowUp"
        ? ACTIVITY_VIEWS[(index - 1 + ACTIVITY_VIEWS.length) % ACTIVITY_VIEWS.length].id
        : event.key === "Home"
          ? ACTIVITY_VIEWS[0].id
          : event.key === "End"
            ? ACTIVITY_VIEWS[ACTIVITY_VIEWS.length - 1].id
            : null;
    if (!next) return;
    event.preventDefault();
    activateView(next, true);
  };
  const reviewAction = canDecide
    ? (request: ReviewRequestResponse) => <button className="ux-button primary" type="button" aria-expanded={reviewingId === request.review_request_id} onClick={() => { setReviewingId(request.review_request_id); setDecisionReason(""); setDecisionError(null); }}>Review</button>
    : undefined;
  const reviewExpanded = canDecide
    ? (request: ReviewRequestResponse) => <ReviewAction request={request} reviewing={true} deciding={decidingId === request.review_request_id} reason={decisionReason} error={reviewingId === request.review_request_id ? decisionError : null} onOpen={() => undefined} onCancel={() => { setReviewingId(null); setDecisionReason(""); setDecisionError(null); }} onReasonChange={setDecisionReason} onDecide={(decision) => void decide(request, decision)} />
    : undefined;
  const recoveryNeeds = <>
    {!loadingQueue && activeRecoveryFacts.length ? <section className="activity-recovery-group" aria-labelledby="activity-recovery-needed"><div className="activity-section-heading"><h3 id="activity-recovery-needed">Recovery needed</h3><p>Failed work keeps its exact selection until it succeeds or you resolve it.</p></div><ul className="activity-list activity-recovery-list">{activeRecoveryFacts.map((fact) => <li key={fact.id}><span><strong>{activityRecoveryLabel(fact.context.kind)}</strong><small className="ux-meta">{fact.message} · Failed · {formatActivityTime(fact.occurredAt)}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(fact.context.path)}>Open exact selection</button></li>)}</ul></section> : null}
    {!loadingQueue && failedBatches.length ? <div className="activity-batch-recovery"><div className="activity-section-heading"><h3>Processing recovery</h3><p>Failed and partial batches retain their exact Recipe and Test Data revisions until the failed members succeed.</p></div><ul className="activity-list activity-job-list">{failedBatches.map((batch) => { const context = processingBatchContexts[batch.batch_id]; const failedAttempt = [...batch.attempts].reverse().find((attempt) => attempt.status === "failed"); return <li key={batch.batch_id}><span><strong>{batch.label}</strong><small className="ux-meta">Process · {processingBatchStatusLabel(batch.status)} · {batch.members.length} exact Test Data source{batch.members.length === 1 ? "" : "s"} · {batch.attempts.filter((attempt) => attempt.status === "failed").length} failed attempt{batch.attempts.filter((attempt) => attempt.status === "failed").length === 1 ? "" : "s"}</small><small className="ux-meta">{failedAttempt?.error_detail ?? "Retry the failed members to continue."}</small>{context?.reason ? <small className="ux-meta">{context.reason}</small> : !context ? <small className="ux-meta">Governed Material context is unavailable; exact reopening is blocked.</small> : null}<details className="ux-disclosure"><summary>Exact revision evidence</summary><dl className="evidence-grid"><dt>Recipe</dt><dd><code>{batch.recipe_id} · {batch.recipe_revision_id}</code></dd><dt>Test Data</dt><dd><code>{batch.members.map((member) => `${member.source.document_id} · ${member.source.revision_id}`).join("; ")}</code></dd>{context ? <><dt>Material context</dt><dd><code>{context.materialId} · {context.materialRevisionId}</code></dd><dt>Material State</dt><dd><code>{context.materialStateId} · {context.materialStateRevisionId}</code></dd></> : null}</dl></details></span><span className="activity-row-actions"><button className="ux-button" type="button" disabled={!context?.exact} onClick={() => onNavigate(processingBatchPath(batch))}>{context?.exact ? "Open exact Process" : "Exact context unavailable"}</button><button className="ux-button" type="button" disabled={retryingBatchId === batch.batch_id} onClick={() => void retryFailedBatch(batch)}>{retryingBatchId === batch.batch_id ? "Retrying…" : "Retry failed"}</button></span></li>; })}</ul></div> : null}
  </>;
  const needsPanel = <ActivityQueueSection id="section-needs-attention" title="Needs attention" description={canDecide ? "Submitted work waiting for your review." : "Failed Processing batches and recovery actions that need attention."} loading={loadingQueue} emptyMessage={activeRecoveryFacts.length || failedBatches.length ? "No review requests need attention." : "Nothing needs your attention."} items={needsAttention} action={reviewAction} expandedId={reviewingId} expanded={reviewExpanded} extra={recoveryNeeds} />;
  const inProgressPanel = <section id="section-in-progress" className="activity-section" role="tabpanel" tabIndex={0} aria-labelledby="activity-in-progress-heading"><div className="activity-section-heading"><div><h2 id="activity-in-progress-heading">In progress</h2><p>Work you can resume and review requests still awaiting a decision.</p></div><span className="activity-section-count">{loadingQueue ? "Loading…" : `${inProgress.length + (modelingSession ? 1 : 0)} ${inProgress.length + (modelingSession ? 1 : 0) === 1 ? "item" : "items"}`}</span></div>
    {modelingSession ? <ActivityWorkTable caption="In progress work" rows={[{ key: "modeling-session", task: modelingSession.material?.label ?? modelingSession.objective ?? "Material modeling session", reason: `${modelingSession.materialFamily} · ${stageLabel} · ${modelingSession.testData ? `${modelingSession.testData.label} r${modelingSession.testData.revisionNo}` : "No exact Test Data"} · ${modelingSession.workspace.selectedDocumentIds.length} selected curves`, status: "Local session", updated: "This browser", action: <button className="ux-button" type="button" onClick={() => onNavigate(resumePath)}>{`Resume ${stageLabel}`}</button>, testId: "recent-modeling-session" }]} /> : null}
    {!loadingQueue && inProgress.length ? <ActivityRows items={inProgress} caption="In progress review requests" /> : null}
    {!modelingSession && !loadingQueue && !inProgress.length ? <section className="activity-empty-state" role="status" aria-label="No work in progress"><div><strong>No work in progress</strong><p>Start a Modeling session or submit an available item for review from its workspace.</p></div><button className="ux-button" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button></section> : null}
    {loadingQueue && !modelingSession ? <ActivityQueueLoading /> : null}
  </section>;
  const recentPanel = <section id="section-recent-outcomes" className="activity-section" role="tabpanel" tabIndex={0} aria-labelledby="activity-recent-outcomes-heading"><div className="activity-section-heading"><div><h2 id="activity-recent-outcomes-heading">Recent outcomes</h2><p>Completed review decisions and solver cards opened in this browser.</p></div><span className="activity-section-count">{loadingQueue ? "Loading…" : `${decidedRequests.length + deliveryActivities.length + recoveryOutcomes.length + recoveredBatches.length} ${decidedRequests.length + deliveryActivities.length + recoveryOutcomes.length + recoveredBatches.length === 1 ? "item" : "items"}`}</span></div>
    {!loadingQueue && decidedRequests.length ? <ActivityRows items={decidedRequests} caption="Recent review outcomes" action={(request) => { const action = request.decision?.decision === "changes_requested" ? reviewRevisionAction(request) : null; return action ? <button className="ux-button" type="button" onClick={() => onNavigate(action.path)}>{action.label}</button> : undefined; }} /> : null}
    {deliveryActivities.length ? <ActivityWorkTable caption="Recent solver card outcomes" rows={deliveryActivities.map((activity) => ({ key: `${activity.action}:${activity.cardId}`, task: `${activity.action === "download" ? "Downloaded solver card" : "Previewed solver card"} · ${activity.cardLabel}`, reason: `${activity.materialLabel} · ${activity.solver} ${activity.extension}`, status: "Delivered", updated: formatActivityTime(activity.occurredAt), action: <button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${activity.materialId}/cards/${activity.cardId}`)}>Open card</button>, testId: "recent-solver-card-activity" }))} /> : null}
    {!loadingQueue && !decidedRequests.length && !deliveryActivities.length && !recoveryOutcomes.length && !recoveredBatches.length ? <p className="activity-empty-line" role="status">No recent outcomes yet.</p> : null}
    {!loadingQueue && recoveryOutcomes.length ? <section className="activity-recovery-group" aria-labelledby="activity-recovery-outcomes"><div className="activity-section-heading"><h3 id="activity-recovery-outcomes">Recovery outcomes</h3><p>Successful retries remain in history while their matching failure is resolved.</p></div><ul className="activity-list activity-recovery-list">{recoveryOutcomes.map((fact) => <li key={fact.id}><span><strong>{activityRecoveryLabel(fact.context.kind)}</strong><small className="ux-meta">{fact.message} · Succeeded · {formatActivityTime(fact.occurredAt)}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(fact.context.path)}>Open exact selection</button></li>)}</ul></section> : null}
    {!loadingQueue && recoveredBatches.length ? <section className="activity-recovery-group" aria-labelledby="activity-processing-outcomes"><div className="activity-section-heading"><h3 id="activity-processing-outcomes">Processing outcomes</h3><p>Successful retries remain in the server projection with their append-only attempts.</p></div><ul className="activity-list activity-recovery-list">{recoveredBatches.map((batch) => <li key={batch.batch_id}><span><strong>{batch.label}</strong><small className="ux-meta">Process · Succeeded · {batch.members.length} exact Test Data source{batch.members.length === 1 ? "" : "s"} · {batch.attempts.length} attempts recorded</small><details className="ux-disclosure"><summary>Exact revision evidence</summary><dl className="evidence-grid"><dt>Recipe</dt><dd><code>{batch.recipe_id} · {batch.recipe_revision_id}</code></dd><dt>Test Data</dt><dd><code>{batch.members.map((member) => `${member.source.document_id} · ${member.source.revision_id}`).join("; ")}</code></dd></dl></details></span><button className="ux-button" type="button" onClick={() => onNavigate(processingBatchPath(batch))}>Open exact Process</button></li>)}</ul></section> : null}
    {loadingQueue ? <ActivityQueueLoading /> : null}
  </section>;
  const activePanel = activeView === "needs-attention" ? needsPanel : activeView === "in-progress" ? inProgressPanel : recentPanel;
  return <div className="ux-page"><div className="activity-shell"><div className="activity-content">
    <header className="activity-heading"><div><div className="activity-heading-line"><h1>Activity</h1><span className="activity-role-context">{roleLabel}</span></div><p>{roleDescription}</p></div><div className="activity-heading-actions"><span className="activity-queue-status" role="status" aria-live="polite">{loadingQueue ? "Loading…" : queueError ? "Queue unavailable" : "Ready"}</span><button className="ux-button tertiary" type="button" onClick={() => void loadQueue()} disabled={loadingQueue}>{loadingQueue ? "Refreshing…" : "Refresh"}</button></div></header>
    {queueError ? <div className="activity-queue-error" role="alert"><span>{queueError}</span><button className="ux-button" type="button" onClick={() => void loadQueue()}>Retry</button></div> : null}
    {processingBatchError ? <div className="activity-queue-error" role="alert"><span>Processing recovery unavailable: {processingBatchError}</span><button className="ux-button" type="button" onClick={() => void loadQueue()}>Retry Processing recovery</button></div> : null}
    <nav className="activity-saved-views" role="tablist" aria-label="Activity saved views">{ACTIVITY_VIEWS.map((view) => <button key={view.id} ref={(button) => { if (button) activityViewButtons.current[view.id] = button; }} id={`view-${view.id}`} className={`activity-saved-view${activeView === view.id ? " is-active" : ""}`} type="button" role="tab" aria-controls={`section-${view.id}`} aria-selected={activeView === view.id} tabIndex={activeView === view.id ? 0 : -1} onClick={() => activateView(view.id)} onKeyDown={(event) => handleViewKeyDown(event, view.id)}>{view.label}</button>)}</nav>
    <div className="activity-queue-region"><MaterialsScrollRegion id="activity-queue-scroll" className="activity-queue-scroll" shellClassName="activity-queue-scroll-shell" aria-label="Scrollable Activity queue">{activePanel}</MaterialsScrollRegion></div>
    {governedContext.length ? <section className="activity-context-line" aria-label="Modeling review context"><span>A modeling review or validation context is available.</span><button className="ux-button" type="button" onClick={() => onNavigate(`/modeling?stage=validate&family=${modelingSession?.materialFamily ?? "metal"}`)}>Resume validation</button><details className="ux-disclosure"><summary>Advanced context</summary><dl className="evidence-grid">{governedContext.map(([label, id, revisionId]) => <div key={label}><dt>{label}</dt><dd>{id}{revisionId ? ` · revision ${revisionId}` : ""}</dd></div>)}</dl></details></section> : null}
    <details className="ux-disclosure activity-advanced"><summary>Advanced activity evidence</summary><p>Immutable IDs and revisions remain available here for audit and exact re-opening.</p><button className="ux-button" type="button" onClick={() => onNavigate("/exports")}>Open export packages</button></details>
  </div></div></div>;
}

function reviewTaskLabel(aggregateType: string): string {
  const normalized = aggregateType.toLowerCase();
  if (normalized === "modeling.material_model") return "Selected model review";
  if (normalized.includes("solver") || normalized.includes("card")) return "Solver card review";
  if (normalized.includes("test") || normalized.includes("dataset")) return "Test data review";
  return "Material data review";
}

function reviewStatus(request: ReviewRequestResponse): string {
  if (request.decision?.decision === "approved") return "Approved";
  if (request.decision?.decision === "changes_requested") return "Changes requested";
  return request.lifecycle_state === "changes_requested" ? "Changes requested" : "Waiting for review";
}

function reviewRevisionAction(request: ReviewRequestResponse): { path: string; label: string } | null {
  const params = new URLSearchParams({
    record_id: request.evidence?.affected_materials.record_id ?? request.aggregate_id,
    record_revision_id: request.evidence?.affected_materials.record_revision_id ?? request.revision_id,
    material_revision_id: request.revision_id,
  });
  if (request.aggregate_type === "catalog.material") {
    return { path: `/materials/${request.aggregate_id}?${params.toString()}`, label: "Return to material" };
  }
  if (request.aggregate_type === "catalog.configurable_record") {
    return { path: `/catalog/records?record_id=${encodeURIComponent(request.aggregate_id)}&revision_id=${encodeURIComponent(request.revision_id)}`, label: "Revise and resubmit" };
  }
  if (request.aggregate_type === "datasets.test_data_document") {
    return { path: `/datasets/test-json?document_id=${encodeURIComponent(request.aggregate_id)}&revision_id=${encodeURIComponent(request.revision_id)}`, label: "Revise and resubmit" };
  }
  return request.evidence?.affected_materials.path ? { path: request.evidence.affected_materials.path, label: "Review exact revision" } : null;
}

function formatActivityTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function ActivityQueueLoading() {
  return <div className="activity-queue-loading" aria-busy="true" aria-label="Loading activity queue"><span /><span /><span /></div>;
}

interface ActivityTableRow {
  key: string;
  task: string;
  reason: string;
  status: string;
  updated: string;
  action?: ReactNode;
  testId?: string;
}

function ActivityTable({
  caption,
  rows,
  expandedKey,
  expanded,
}: {
  caption: string;
  rows: ActivityTableRow[];
  expandedKey?: string | null;
  expanded?: (row: ActivityTableRow) => ReactNode;
}) {
  return <table className="activity-table"><caption className="visually-hidden">{caption}</caption><colgroup><col className="activity-column-task" /><col className="activity-column-reason" /><col className="activity-column-status" /><col className="activity-column-updated" /><col className="activity-column-action" /></colgroup><thead><tr><th scope="col">Task</th><th scope="col">Request/recovery reason</th><th scope="col">Status</th><th scope="col">Updated</th><th scope="col">Action</th></tr></thead><tbody>{rows.map((row) => <Fragment key={row.key}>
    <tr key={row.key} data-testid={row.testId}>
      <td className="activity-cell-task"><strong>{row.task}</strong></td>
      <td className="activity-cell-reason">{row.reason}</td>
      <td className="activity-cell-status"><strong>{row.status}</strong></td>
      <td className="activity-cell-updated"><time>{row.updated}</time></td>
      <td className="activity-cell-action">{row.action ?? <span className="activity-row-state" role="img" aria-label="No available action">—</span>}</td>
    </tr>
    {expandedKey === row.key && expanded ? <tr key={`${row.key}:expanded`} className="activity-decision-row"><td colSpan={5}><div className="activity-decision-panel">{expanded(row)}</div></td></tr> : null}
  </Fragment>)}</tbody></table>;
}

function ActivityRows({
  items,
  action,
  caption = "Activity requests",
  expandedId,
  expanded,
}: {
  items: ReviewRequestResponse[];
  action?: (request: ReviewRequestResponse) => ReactNode;
  caption?: string;
  expandedId?: string | null;
  expanded?: (request: ReviewRequestResponse) => ReactNode;
}) {
  const rows = items.map((request) => {
    const requester = (request as ReviewRequestResponse & { requested_by_display_name?: string }).requested_by_display_name ?? "Requester name unavailable";
    return {
      key: request.review_request_id,
      task: reviewTaskLabel(request.aggregate_type),
      reason: `${request.reason || "No request reason was provided."}${request.decision ? ` · Decision: ${request.decision.reason || "No decision reason was provided."}` : ""} · Requested by: ${requester}`,
      status: reviewStatus(request),
      updated: formatActivityTime(request.decision?.decided_at ?? request.requested_at),
      action: action ? action(request) : undefined,
    } satisfies ActivityTableRow;
  });
  return <ActivityTable caption={caption} rows={rows} expandedKey={expandedId} expanded={expanded ? (row) => {
    const request = items.find((item) => item.review_request_id === row.key);
    return request ? expanded(request) : null;
  } : undefined} />;
}

function ActivityWorkTable({ caption, rows }: { caption: string; rows: ActivityTableRow[] }) {
  return <ActivityTable caption={caption} rows={rows} />;
}

function activityRecoveryLabel(kind: ActivityRecoveryContext["kind"]): string {
  if (kind === "test_data_json") return "Test Data download";
  if (kind === "selected_model_json") return "Selected model download";
  if (kind === "solver_card") return "Solver card delivery";
  if (kind === "csv_blob") return "CSV download";
  if (kind === "receipt_json") return "Delivery receipt download";
  return "Release manifest download";
}

function processingBatchStatusLabel(status: CommonProcessingBatchResponse["status"]): string {
  if (status === "partial") return "Partly completed";
  if (status === "failed") return "Failed";
  if (status === "succeeded") return "Succeeded";
  if (status === "running") return "Running";
  return "Planned";
}

interface ProcessingBatchMaterialContext {
  family: "metal" | "polymer" | "elastomer";
  materialId: string;
  materialRevisionId: string;
  materialStateId: string;
  materialStateRevisionId: string;
  exact: boolean;
  reason?: string;
}

function processingBatchMaterialContext(
  batch: CommonProcessingBatchResponse,
  documents: CanonicalTestDataDocumentResponse[],
  materialsByFamily: Record<ProcessingBatchMaterialContext["family"], MaterialResponse[]>,
): ProcessingBatchMaterialContext | null {
  const sources = batch.members.map((member) => {
    const document = documents.find((item) => item.test_data_document_id === member.source.document_id);
    return { member, document };
  });
  const first = sources[0]?.document?.governed_source;
  if (!first) return null;
  if (sources.some(({ member, document }) => !document || document.current_revision.id !== member.source.revision_id)) {
    return {
      family: "metal",
      materialId: first.material.aggregate_id,
      materialRevisionId: first.material.revision_id,
      materialStateId: first.material_state.aggregate_id,
      materialStateRevisionId: first.material_state.revision_id,
      exact: false,
      reason: "One or more Test Data revisions are no longer current; the batch is preserved as evidence and cannot be reopened silently.",
    };
  }
  if (sources.some(({ document }) => {
    const source = document?.governed_source;
    return !source
      || source.material.aggregate_id !== first.material.aggregate_id
      || source.material.revision_id !== first.material.revision_id
      || source.material_state.aggregate_id !== first.material_state.aggregate_id
      || source.material_state.revision_id !== first.material_state.revision_id;
  })) {
    return {
      family: "metal",
      materialId: first.material.aggregate_id,
      materialRevisionId: first.material.revision_id,
      materialStateId: first.material_state.aggregate_id,
      materialStateRevisionId: first.material_state.revision_id,
      exact: false,
      reason: "Batch members do not share one governed Material and Material State context.",
    };
  }
  const familyEntry = (Object.entries(materialsByFamily) as Array<[ProcessingBatchMaterialContext["family"], MaterialResponse[]]>).find(([, items]) => items.some((item) => item.material_id === first.material.aggregate_id));
  const material = familyEntry?.[1].find((item) => item.material_id === first.material.aggregate_id);
  if (!familyEntry || !material || material.current_revision.id !== first.material.revision_id) {
    return {
      family: familyEntry?.[0] ?? "metal",
      materialId: first.material.aggregate_id,
      materialRevisionId: first.material.revision_id,
      materialStateId: first.material_state.aggregate_id,
      materialStateRevisionId: first.material_state.revision_id,
      exact: false,
      reason: "The governed Material revision is no longer the current selectable head.",
    };
  }
  return {
    family: familyEntry[0],
    materialId: first.material.aggregate_id,
    materialRevisionId: first.material.revision_id,
    materialStateId: first.material_state.aggregate_id,
    materialStateRevisionId: first.material_state.revision_id,
    exact: true,
  };
}

function ActivityQueueSection({ id, title, description, loading, emptyMessage, items, action, expandedId, expanded, extra }: { id: string; title: string; description: string; loading: boolean; emptyMessage: string; items: ReviewRequestResponse[]; action?: (request: ReviewRequestResponse) => ReactNode; expandedId?: string | null; expanded?: (request: ReviewRequestResponse) => ReactNode; extra?: ReactNode }) {
  const headingId = `activity-${id.replace(/^section-/, "")}-heading`;
  return <section id={id} className="activity-section" role="tabpanel" tabIndex={0} aria-labelledby={headingId}><div className="activity-section-heading"><div><h2 id={headingId}>{title}</h2><p>{description}</p></div><span className="activity-section-count">{loading ? "Loading…" : `${items.length} ${items.length === 1 ? "item" : "items"}`}</span></div>{loading ? <ActivityQueueLoading /> : items.length ? <ActivityRows items={items} action={action} expandedId={expandedId} expanded={expanded} /> : <p className="activity-empty-line" role="status">{emptyMessage}</p>}{extra}</section>;
}

function ReviewAction({ request, reviewing, deciding, reason, error, onOpen, onCancel, onReasonChange, onDecide }: { request: ReviewRequestResponse; reviewing: boolean; deciding: boolean; reason: string; error: string | null; onOpen: () => void; onCancel: () => void; onReasonChange: (value: string) => void; onDecide: (decision: "approved" | "changes_requested") => void }) {
  if (!reviewing) return <button className="ux-button primary" type="button" onClick={onOpen}>Review</button>;
  return <form className="activity-review-form" onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); onDecide("approved"); }}><label>Review reason<textarea value={reason} onChange={(event) => onReasonChange(event.target.value)} placeholder="Explain the approval or requested change" required disabled={deciding} /></label>{request.evidence ? <details className="activity-review-evidence"><summary>Evidence and affected Materials</summary><dl className="evidence-grid"><div><dt>Schema</dt><dd>{request.evidence.schema.ref} · {request.evidence.schema.version}</dd></div><div><dt>Validation</dt><dd>{request.evidence.validation.status} · {request.evidence.validation.summary}</dd></div><div><dt>Materials path</dt><dd>{request.evidence.affected_materials.path ?? "Not attached"}</dd></div><div><dt>Record table</dt><dd><code>{request.evidence.affected_table_id && request.evidence.affected_table_revision_id ? `${request.evidence.affected_table_id} · ${request.evidence.affected_table_revision_id}` : "Not attached"}</code></dd></div><div><dt>Source Artifact</dt><dd>{request.evidence.source_artifact.state}{request.evidence.source_artifact.sha256 ? ` · ${request.evidence.source_artifact.sha256}` : ""}</dd></div><div><dt>Output Artifact</dt><dd><code>{request.evidence.output_artifact_sha256 ?? "Not provided"}</code></dd></div><div><dt>Created</dt><dd>{request.evidence.created.at} · {request.evidence.created.by}</dd></div><div><dt>Change reason</dt><dd>{request.evidence.change_reason}</dd></div><div><dt>Exact input use</dt><dd><ul className="activity-evidence-list">{request.evidence.exact_input_use.map((item) => <li key={item}><code>{item}</code></li>)}</ul></dd></div><div><dt>Requester ID</dt><dd><code>{request.requested_by}</code></dd></div><div><dt>Exact identity</dt><dd><code>{request.evidence.subject_id} · {request.evidence.subject_revision_id}</code></dd></div></dl></details> : null}{error ? <p role="alert">{error}</p> : null}<div><button className="ux-button primary" type="submit" disabled={deciding}>{deciding ? "Saving…" : "Approve"}</button><button className="ux-button" type="button" disabled={deciding} onClick={() => onDecide("changes_requested")}>Request changes</button><button className="ux-button tertiary" type="button" disabled={deciding} onClick={onCancel}>Cancel</button></div></form>;
}

async function recordActivityRecovery(
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
    // Recovery telemetry is best-effort; the server Activity queue remains authoritative.
  }
}
