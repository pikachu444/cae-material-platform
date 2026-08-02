import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  getCatalogWorkflowGraph,
  getConfigurableCatalogRecord,
  getAuthenticatedPrincipal,
  getEffectiveProductAccess,
  getMaterialDetail,
  listBulkExportCandidates,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogRecordRevisions,
  listMaterials,
  listReviewRequests,
  resolveCatalogDomainRevision,
  createReviewDecision,
  type ApiConfig,
} from "./api";
import type {
  CatalogWorkflowGraphResponse,
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
} from "./types";
import { MaterialsBrowseTree } from "./materials-browse-tree";
import { MaterialDatasheetProjection } from "./material-datasheet-projection";
import { publishWorkspaceCommandState, publishWorkspaceStatus } from "./design/application-shell";
import { ResizableSplitPane } from "./design/resizable-split-pane";
import { EngineeringColumnResizeHandle } from "./design/engineering-column-resize-handle";
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

function cardsFromGraph(graph: CatalogWorkflowGraphResponse | null): SolverCardSummary[] {
  if (!graph) return [];
  return graph.nodes.flatMap((node) => {
    const binding = node.domain_binding;
    if (binding?.kind !== "neutral_solver_card" && binding?.kind !== "solver_card") return [];
    return [{
      id: binding.object_id,
      revisionId: binding.revision_id,
      kind: binding.kind,
      label: node.name,
      ...solverFor(node.name),
    }];
  }).sort((left, right) => left.solver.localeCompare(right.solver));
}

async function currentCards(
  config: ApiConfig,
  materialId: string,
  graph: CatalogWorkflowGraphResponse | null,
): Promise<SolverCardSummary[]> {
  const merged = new Map(cardsFromGraph(graph).map((card) => [card.id, card]));
  try {
    const result = await listBulkExportCandidates(config, materialId);
    for (const candidate of result.data.items) {
      if (candidate.source.kind !== "neutral_solver_card_native") continue;
      const id = candidate.source.neutral_solver_card_id;
      const revisionId = candidate.source.neutral_solver_card_revision_id;
      if (!id || !revisionId || merged.has(id)) continue;
      const solver = solverFor(`${candidate.label} ${candidate.default_archive_path}`);
      merged.set(id, {
        id,
        revisionId,
        kind: "neutral_solver_card",
        label: candidate.label,
        ...solver,
      });
    }
  } catch {
    // The catalog graph still provides released cards if bulk-candidate discovery is unavailable.
  }
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
  let graph: CatalogWorkflowGraphResponse | null = null;
  try {
    const bindingResult = await resolveCatalogDomainRevision(
      config,
      "material",
      material.material_id,
      material.current_revision.id,
    );
    const binding = bindingResult.data;
    if (binding) {
      graph = (await getCatalogWorkflowGraph(config, binding.record_id, binding.record_revision_id, 6)).data;
    }
  } catch {
    graph = null;
  }
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
  return { detail: detailResult.data, graph, cards, representativeCurve };
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

function lifecycleLabel(state: string): string {
  return state ? `${state.slice(0, 1).toUpperCase()}${state.slice(1).replaceAll("_", " ")}` : "—";
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
  if (points.length < 2) return <div className="ux-empty compact"><strong>No representative curve preview.</strong><p>Open Curves or Browse Tree to inspect linked Test Data and model records.</p></div>;
  const width = 520;
  const height = 170;
  const xMin = Math.min(...points.map((point) => point.x));
  const xMax = Math.max(...points.map((point) => point.x));
  const yMin = Math.min(...points.map((point) => point.y));
  const yMax = Math.max(...points.map((point) => point.y));
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  const polyline = points.map((point) => `${36 + ((point.x - xMin) / xSpan) * (width - 52)},${12 + (1 - (point.y - yMin) / ySpan) * (height - 40)}`).join(" ");
  return <svg className="material-curve-preview" role="img" aria-label="Representative governed material curve" viewBox={`0 0 ${width} ${height}`}><line x1="36" y1="12" x2="36" y2={height - 28}/><line x1="36" y1={height - 28} x2={width - 16} y2={height - 28}/><polyline points={polyline}/><text x="8" y="18">stress</text><text x={width - 48} y={height - 8}>strain</text></svg>;
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

function LinkedResponseGraph({ points }: { points: Array<{ x: number; y: number }> }) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [frameSize, setFrameSize] = useState({ width: 720, height: 300 });
  const normalizedPoints = useMemo(() => normalizeLinkedResponsePoints(points), [points]);

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
  }, [normalizedPoints.length]);

  if (normalizedPoints.length < 2) return null;
  const width = Math.max(360, frameSize.width);
  const height = Math.max(220, frameSize.height);
  const margin = { left: 62, right: 24, top: 20, bottom: 44 };
  const plotWidth = Math.max(1, width - margin.left - margin.right);
  const plotHeight = Math.max(1, height - margin.top - margin.bottom);
  const xMaximum = Math.max(...normalizedPoints.map((point) => point.x), 0);
  const xStep = xMaximum <= 0.25 ? 0.025 : xMaximum <= 1 ? 0.1 : 0.5;
  const xDomainStep = xMaximum <= 0.25 ? 0.005 : xStep / 2;
  const xDomainMaximum = Math.max(xDomainStep, Math.ceil((xMaximum + Math.max(xMaximum * 0.05, 0.005)) / xDomainStep) * xDomainStep);
  const yMinimum = Math.min(...normalizedPoints.map((point) => point.y));
  const yMaximum = Math.max(...normalizedPoints.map((point) => point.y));
  const ySpan = Math.max(yMaximum - yMinimum, 1);
  const yPad = Math.max(ySpan * 0.05, 10);
  const yDomainMinimum = Math.max(0, Math.floor((yMinimum - yPad) / 10) * 10);
  const yDomainMaximum = Math.max(yDomainMinimum + 10, Math.ceil((yMaximum + yPad) / 10) * 10);
  const yStep = yDomainMaximum - yDomainMinimum <= 400 ? 50 : yDomainMaximum - yDomainMinimum <= 800 ? 100 : 200;
  const xTicks = plotTicks(0, xDomainMaximum, xStep);
  const yTicks = plotTicks(yDomainMinimum, yDomainMaximum, yStep);
  const scaleX = (value: number) => margin.left + (value / xDomainMaximum) * plotWidth;
  const scaleY = (value: number) => margin.top + (1 - (value - yDomainMinimum) / (yDomainMaximum - yDomainMinimum)) * plotHeight;
  const mappedPoints = normalizedPoints.map((point) => ({ x: scaleX(point.x), y: scaleY(point.y) }));
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

  return <section className="linked-response-band response-plot-band" aria-labelledby="linked-response-title">
    <header className="linked-response-heading response-plot-heading"><div><h2 id="linked-response-title">Linked response</h2><p>Same values as the selected card preview.</p></div><span className="ux-meta">Card evidence · read only</span></header>
    <div ref={frameRef} className="linked-response-frame response-plot-frame">
      <svg className="linked-response-plot response-plot" role="img" aria-label="Linked response chart showing true stress in MPa versus true plastic strain" viewBox={`0 0 ${width} ${height}`} data-series-rows={normalizedPoints.length} data-x-domain={`0,${xDomainMaximum}`} data-y-domain={`${yDomainMinimum},${yDomainMaximum}`} data-x-label="True plastic strain [1]" data-y-label="True stress (MPa)">
        <title>True stress versus true plastic strain from the selected card.</title>
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
        <g className="linked-response-legend plot-legend" transform={`translate(${legend.x} ${legend.y})`}><line x1="0" y1="-4" x2="18" y2="-4"/><text x="26" y="0">Card hardening data</text></g>
      </svg>
    </div>
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
  const [sortKey, setSortKey] = useState<"name" | "material_class">(initialSortKey);
  const [sortDirection, setSortDirection] = useState<"ascending" | "descending">(() => materialSearchParams().get("direction") === "descending" ? "descending" : "ascending");
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [leftMode, setLeftMode] = useState<"filters" | "browse" | "subsets">(initialNavigatorMode);
  const [requestedRecord, setRequestedRecord] = useState<ConfigurableLinkEndpoint | null>(storedBrowseRecord);
  const [browseSelection, setBrowseSelection] = useState<BrowseSelection | null>(null);
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [familyFacets, setFamilyFacets] = useState<Array<{ material_class: string; count: number }>>([]);
  const [offset, setOffset] = useState(() => Number(materialSearchParams().get("offset") ?? "0") || 0);
  const [selectedId, setSelectedId] = useState(() => materialSearchParams().get("selected") ?? "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [columnWidths, setColumnWidths] = useState({ compare: 68, material: 250, materialClass: 160, summary: 210, revisionStatus: 110 });

  useEffect(() => {
    if (locationSearch === undefined) return;
    const params = new URLSearchParams(locationSearch);
    const nextMode = params.get("mode");
    const nextSort = params.get("sort");
    setDraftQuery(params.get("q") ?? "");
    setQuery(params.get("q") ?? "");
    setMaterialClass(params.get("family") ?? "");
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
    void listMaterials(config, {
      query,
      materialClass: materialClass || undefined,
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
        setSelectedId((current) => items.some((item) => item.material_id === current) ? current : items[0]?.material_id ?? "");
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setMaterials([]);
        setTotalCount(0);
        setFamilyFacets([]);
        setSelectedId("");
        setLoading(false);
        setError(messageFor(cause));
      });
    return () => { active = false; };
  }, [config, loadAttempt, materialClass, offset, query, sortDirection, sortKey]);

  useEffect(() => {
    if (typeof window === "undefined" || window.location.pathname !== "/materials") return;
    window.history.replaceState(window.history.state, "", materialsPath({ query, materialClass, sortKey, sortDirection, offset, leftMode, selectedId }));
  }, [leftMode, materialClass, offset, query, selectedId, sortDirection, sortKey]);

  useEffect(() => {
    publishWorkspaceCommandState(`materials:${leftMode === "filters" ? "search" : leftMode}`);
  }, [leftMode]);

  const comparedMaterials = materials.filter((material) => compareIds.has(material.material_id));
  const selected = materials.find((item) => item.material_id === selectedId);

  useEffect(() => {
    publishWorkspaceStatus({
      selection: selected ? `${selected.current_revision.content.name} · ${selected.current_revision.content.material_code ?? "No grade"}` : "No material selected",
      revision: selected ? `r${selected.current_revision.revision_no} · ${selected.current_revision.lifecycle_state}` : `${totalCount.toLocaleString()} records`,
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
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, sortKey, sortDirection, offset, leftMode, selectedId }));
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

  function toggleCompare(materialId: string): void {
    setCompareIds((current) => {
      const next = new Set(current);
      if (next.has(materialId)) next.delete(materialId);
      else if (next.size < 3) next.add(materialId);
      return next;
    });
  }

  function openMaterial(materialId: string): void {
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, sortKey, sortDirection, offset, leftMode, selectedId: materialId }));
    onNavigate(`/materials/${materialId}`);
  }

  const navigator = <aside className="materials-left-pane" aria-label="Materials navigator">
    <nav className="materials-navigator-modes" aria-label="Materials navigator modes">
      <button type="button" className={leftMode === "browse" ? "active" : ""} aria-current={leftMode === "browse" ? "page" : undefined} onClick={() => openBrowseTree(undefined)}>Browse</button>
      <button type="button" className={leftMode === "filters" ? "active" : ""} aria-current={leftMode === "filters" ? "page" : undefined} onClick={() => setLeftMode("filters")}>Filters</button>
      <button type="button" className={leftMode === "subsets" ? "active" : ""} aria-current={leftMode === "subsets" ? "page" : undefined} onClick={() => setLeftMode("subsets")}>Subsets</button>
    </nav>
    {leftMode === "filters" ? <div className="materials-filters">
      <label className="ux-field">Material class<select className="ux-select" name="material-class" value={materialClass} onChange={(event) => { setMaterialClass(event.target.value); setOffset(0); }}><option value="">All classes</option>{familyFacets.map((facet) => <option key={facet.material_class} value={facet.material_class}>{`${facet.material_class} (${facet.count.toLocaleString()})`}</option>)}</select></label>
      <button className="ux-button tertiary" type="button" onClick={() => { setMaterialClass(""); setOffset(0); }}>Clear class</button>
    </div> : <MaterialsBrowseTree config={config} subsetMode={leftMode === "subsets"} requestedRecord={requestedRecord} onSelectRecord={selectBrowseRecord} onOpenRecord={openExactRecord}/>}
  </aside>;

  const results = <section className="materials-results" aria-labelledby="material-results-title" aria-busy={loading}>
    <div className="materials-results-header"><div><h2 id="material-results-title">Materials</h2><p className="ux-meta">{loading ? "Loading…" : `${totalCount ? `${offset + 1}–${Math.min(offset + materials.length, totalCount)} of ` : ""}${new Intl.NumberFormat().format(totalCount)} matches`}</p></div><span className="ux-meta">Enter opens · select up to 3 to compare</span></div>
    {error ? <div className="ux-notice error" role="alert">{error}<button className="ux-button tertiary" type="button" onClick={() => setLoadAttempt((current) => current + 1)}>Retry</button></div> : null}
    {!loading && !error && !materials.length ? <div className="ux-empty"><strong>No materials match this server query.</strong><p>Clear the class or try a material grade, code, or family.</p></div> : null}
    {comparedMaterials.length > 1 ? <div className="material-compare-strip"><div><strong>Comparing {comparedMaterials.length} materials</strong><span className="ux-meta">Selected materials remain available while you inspect results.</span></div>{comparedMaterials.map((material) => <dl key={material.material_id}><dt>{material.current_revision.content.name}</dt><dd>{material.current_revision.content.material_family ?? material.current_revision.content.material_class}</dd><dd>r{material.current_revision.revision_no}</dd></dl>)}<button className="ux-button tertiary" type="button" onClick={() => setCompareIds(new Set())}>Clear comparison</button></div> : null}
    {browseSelection ? <div className="browse-selection-bar"><span><strong>{browseSelection.record.current_revision.content.name}</strong><small>{browseSelection.graph.root.domain_binding?.kind?.replaceAll("_", " ") ?? "Catalog record"} · exact revision {browseSelection.record.current_revision.revision_no}</small></span><button className="ux-button tertiary" type="button" onClick={() => openExactRecord(browseSelection.record)}>Open datasheet</button></div> : null}
    <div className="materials-result-table-wrap"><table className="materials-result-table" aria-label="Material results"><colgroup>{Object.entries(columnWidths).map(([key, width]) => <col key={key} style={{ width }} />)}</colgroup><thead><tr><th>Compare<EngineeringColumnResizeHandle label="Compare" width={columnWidths.compare} min={60} max={100} onChange={(width) => setColumnWidths((current) => ({ ...current, compare: width }))}/></th><th aria-sort={sortKey === "name" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("name")}>Material / grade</button><EngineeringColumnResizeHandle label="Material or grade" width={columnWidths.material} min={180} max={420} onChange={(width) => setColumnWidths((current) => ({ ...current, material: width }))}/></th><th aria-sort={sortKey === "material_class" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("material_class")}>Family</button><EngineeringColumnResizeHandle label="Family" width={columnWidths.materialClass} min={120} max={280} onChange={(width) => setColumnWidths((current) => ({ ...current, materialClass: width }))}/></th><th>Description<EngineeringColumnResizeHandle label="Description" width={columnWidths.summary} min={160} max={420} onChange={(width) => setColumnWidths((current) => ({ ...current, summary: width }))}/></th><th>Status<EngineeringColumnResizeHandle label="Status" width={columnWidths.revisionStatus} min={90} max={180} onChange={(width) => setColumnWidths((current) => ({ ...current, revisionStatus: width }))}/></th></tr></thead><tbody>
      {materials.map((material) => { const content = material.current_revision.content; const materialIdentity = `${content.name} · ${content.material_code ?? "No grade code"}`; return <tr key={material.material_id} className={selectedId === material.material_id ? "selected" : ""} tabIndex={0} aria-selected={selectedId === material.material_id} onClick={() => setSelectedId(material.material_id)} onDoubleClick={() => openMaterial(material.material_id)} onKeyDown={(event) => { if (event.key === "Enter") openMaterial(material.material_id); }}><td><input type="checkbox" aria-label={`Compare ${content.name}`} checked={compareIds.has(material.material_id)} disabled={!compareIds.has(material.material_id) && compareIds.size >= 3} onClick={(event) => event.stopPropagation()} onChange={() => toggleCompare(material.material_id)}/></td><td><button className="material-result-name" type="button" aria-current={selectedId === material.material_id ? "true" : undefined} title={materialIdentity} onClick={() => setSelectedId(material.material_id)}><span>{content.name}</span><small>{content.material_code ?? "No grade code"}</small></button></td><td title={content.material_class}>{content.material_class}</td><td>{content.description ?? "—"}</td><td>{lifecycleLabel(material.current_revision.lifecycle_state)}</td></tr>; })}
    </tbody></table></div>
    {!loading && totalCount > materials.length ? <nav className="materials-pagination" aria-label="Material result pages"><button className="ux-button tertiary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span className="ux-meta">Rows {totalCount ? offset + 1 : 0}–{Math.min(offset + materials.length, totalCount)}</span><button className="ux-button tertiary" type="button" disabled={offset + materials.length >= totalCount} onClick={() => setOffset(offset + 50)}>Next</button></nav> : null}
  </section>;

  const context = <aside className="materials-selection" aria-live="polite">
    {selected ? <>
      <div className="selection-heading"><div><p className="ux-kicker">Selected material</p><h2 title={selected.current_revision.content.name}>{selected.current_revision.content.name}</h2></div><span className="ux-meta">{selected.current_revision.content.material_code ?? "No material code"}</span></div>
      <p>{selected.current_revision.content.description ?? "No summary is available."}</p>
      <dl className="selection-context"><dt>Family</dt><dd>{selected.current_revision.content.material_class}</dd><dt>Status</dt><dd>{lifecycleLabel(selected.current_revision.lifecycle_state)}</dd></dl>
      <div className="selection-delivery-command">
        <button className="ux-button primary" type="button" onClick={() => openMaterial(selected.material_id)}>Open datasheet</button>
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
  if (value.data_type === "record_reference") return `Record revision ${value.target_record_revision_id}`;
  return `${value.data_type} artifact · ${value.artifact_sha256.slice(0, 12)}…`;
}

function CardTable({ config, material, cards, onNavigate }: { config: ApiConfig; material: MaterialResponse; cards: SolverCardSummary[]; onNavigate: (path: string) => void }) {
  if (!cards.length) return <div className="ux-empty compact"><strong>No native card is available.</strong><p>Create one from the selected source data below, or continue the selected material in Modeling.</p></div>;
  return <table className="ux-table cae-card-table"><thead><tr><th>Solver</th><th>Card</th><th>Format</th><th>Delivery</th></tr></thead><tbody>{cards.map((card) => <tr key={card.id}><td><strong>{card.solver}</strong></td><td title={card.label}>{card.label}</td><td>Native ASCII {card.extension}</td><td><div className="card-table-actions"><SolverCardAction config={config} card={card} material={deliveryMaterial(material)} onNavigate={onNavigate} directClassName="ux-button" reviewClassName="ux-button" includePreview/></div></td></tr>)}</tbody></table>;
}

export function MaterialDetailPage({ config, materialId, activeTab, onNavigate }: Props & { materialId: string; activeTab: MaterialTab }) {
  const [experience, setExperience] = useState<MaterialExperience | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [browseSelection, setBrowseSelection] = useState<BrowseSelection | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void getMaterialDetail(config, materialId).then((detail) => loadMaterialExperience(config, detail.data.material, true)).then((result) => {
      if (!active) return;
      setExperience(result);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
      setLoading(false);
    });
    return () => { active = false; };
  }, [config, materialId]);

  useEffect(() => {
    const material = experience?.detail.material;
    publishWorkspaceStatus({
      selection: material ? `${material.current_revision.content.name} · ${material.current_revision.content.material_code ?? "No grade"}` : "Material record",
      revision: material ? `r${material.current_revision.revision_no} · ${material.current_revision.lifecycle_state}` : "Loading revision",
      jobs: "No active job",
      warnings: error ? "1 workspace error" : "0 warnings",
      connection: error ? "degraded" : "online",
    });
  }, [error, experience]);

  if (loading) return <div className="ux-page"><div className="material-detail-shell"><p className="loading-state">Loading material…</p></div></div>;
  if (error || !experience) return <div className="ux-page"><div className="material-detail-shell"><div className="ux-notice error" role="alert">{error ?? "Material not found."}</div><button className="ux-button" type="button" onClick={() => onNavigate(materialsReturnPath())}>Back to Materials</button></div></div>;

  const material = experience.detail.material;
  const content = material.current_revision.content;
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
  const activePath = activeTab === "overview" ? `/materials/${materialId}` : `/materials/${materialId}/${activeTab}`;
  const navigator = <aside className="materials-left-pane" aria-label="Materials Browse Tree"><div className="workspace-back-row"><button className="ux-button tertiary" type="button" onClick={() => onNavigate(materialsReturnPath())}>← Results</button><strong>Browse</strong></div><MaterialsBrowseTree config={config} requestedRecord={catalogRoot} onSelectRecord={(record, graph) => setBrowseSelection({ record, graph })} onOpenRecord={(record) => onNavigate(`/materials/records/${record.record_id}/revisions/${record.current_revision.id}`)}/></aside>;
  const context = <aside className="materials-selection material-related-context" aria-label="Related exact records"><p className="ux-kicker">Current revision</p><div className="context-record-title">{content.name}</div><dl className="selection-context"><dt>Revision</dt><dd>r{material.current_revision.revision_no}</dd><dt>Status</dt><dd>{material.current_revision.lifecycle_state}</dd><dt>Related</dt><dd>{relatedLinks.length} records</dd></dl>{browseSelection ? <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/records/${browseSelection.record.record_id}/revisions/${browseSelection.record.current_revision.id}`)}>Open {browseSelection.record.current_revision.content.name}</button> : null}<h3>Related records</h3><ul className="related-record-list">{relatedLinks.slice(0, 12).map((related) => <li key={related.id}><button type="button" onClick={() => onNavigate(`/materials/records/${related.endpoint.record_id}/revisions/${related.endpoint.record_revision_id}`)}><span>{related.endpoint.name}</span><small>{related.label} · r{related.endpoint.revision_no}</small></button></li>)}</ul></aside>;

  function acceptCreatedCard(card: SolverCardSummary): void {
    setExperience((current) => current ? { ...current, cards: [...current.cards, card] } : current);
    onNavigate(`/materials/${materialId}/cards/${card.id}`);
  }

  const datasheet = <div className="material-detail-shell">
    <header className="material-detail-header"><div><h1>{content.name}</h1><div className="material-detail-meta"><span>{content.material_code ?? "No grade code"}</span><span>{content.material_family ?? content.material_class}</span><span>{sourceLabel(experience)}</span><span>{material.current_revision.lifecycle_state}</span></div></div><div className="card-action-row">{preferredCard ? <SolverCardAction config={config} card={preferredCard} material={deliveryMaterial(material)} onNavigate={onNavigate}/> : neutralMaterial ? <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards`)}>Create card</button> : modelingFamily(material) ? <button className="ux-button primary" type="button" onClick={() => startModeling(material, onNavigate)}>Start Modeling</button> : <p className="ux-notice" role="status">Modeling is not supported for this family.</p>}<ReviewRequestAction config={config} subject={{ aggregateType: "catalog.material", aggregateId: material.material_id, revisionId: material.current_revision.id, manifestSha256: material.current_revision.content_hash, classification: material.current_revision.classification, lifecycleState: material.current_revision.lifecycle_state }} /></div></header>
    <nav className="ux-tabs" role="tablist" aria-label="Material detail"><input type="hidden" value={activePath} readOnly />{tabs.map((tab) => <button key={tab.id} className="ux-tab" type="button" role="tab" aria-selected={activeTab === tab.id} onClick={() => onNavigate(tab.id === "overview" ? `/materials/${materialId}` : `/materials/${materialId}/${tab.id}`)}>{tab.label}</button>)}</nav>
    <section className="material-tab-panel" role="tabpanel">
      {activeTab === "overview" ? <div className="overview-grid"><div><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Engineering summary</p><h2>Key properties</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/properties`)}>All properties</button></div><div className="overview-property-grid"><div><span>Density</span><strong>{formatDensity(property?.density_kg_per_m3)}</strong></div><div><span>Young’s modulus</span><strong>{formatPressure(property?.youngs_modulus_pa)}</strong></div><div><span>Yield strength</span><strong>{formatPressure(property?.yield_stress_pa)}</strong></div><div><span>Poisson ratio</span><strong>{property?.poisson_ratio ?? "—"}</strong></div></div></section><div className="overview-data-grid"><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Representative curve</p><h2>Linked material response</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/curves`)}>All curves</button></div><RepresentativeCurve points={experience.representativeCurve}/></section><section className="overview-section"><p className="ux-kicker">Application conditions</p><h2>Material states</h2><dl className="condition-summary"><dt>Temperature</dt><dd>{property?.applicability.temperature_min_k ?? "—"}–{property?.applicability.temperature_max_k ?? "—"} K</dd><dt>Strain rate</dt><dd>{property?.applicability.strain_rate_min_per_s ?? "—"}–{property?.applicability.strain_rate_max_per_s ?? "—"} /s</dd></dl>{experience.detail.states.slice(0, 2).map((state) => <p className="condition-state" key={state.material_state_id}><strong>{state.current_revision.content.name}</strong><span>{state.current_revision.content.manufacturing_route ?? "Route not specified"}</span></p>)}</section></div></div><aside><p className="ux-kicker">CAE delivery</p><h2>Ready solver cards</h2><p>Choose a native format. Open a card preview to check delivery notes before downloading.</p><SolverAvailability cards={experience.cards}/><div className="solver-preview-links">{experience.cards.map((card) => <button key={card.id} type="button" onClick={() => onNavigate(`/materials/${materialId}/cards/${card.id}`)}>Preview {card.solver} {card.extension}</button>)}</div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(browsePath(experience))}>Related records in Browse Tree</button></aside></div> : null}
      {activeTab === "properties" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Normalized values</p><h2>Engineering properties</h2></div></div>{property ? <table className="ux-table"><thead><tr><th>Property</th><th>Value</th><th>Quantity semantics</th><th>Source</th></tr></thead><tbody><tr><td>Density</td><td>{formatDensity(property.density_kg_per_m3)}</td><td>mass density</td><td>{property.density_source.kind}</td></tr><tr><td>Young’s modulus</td><td>{formatPressure(property.youngs_modulus_pa)}</td><td>elastic modulus</td><td>{property.youngs_modulus_source.kind}</td></tr><tr><td>Poisson ratio</td><td>{property.poisson_ratio}</td><td>dimensionless ratio</td><td>{property.poisson_ratio_source.kind}</td></tr><tr><td>Yield strength</td><td>{formatPressure(property.yield_stress_pa)}</td><td>stress</td><td>{property.yield_stress_source?.kind ?? "—"}</td></tr></tbody></table> : <div className="ux-empty">No typed property set is available.</div>}<p className="ux-meta">Normalized units are shown here. Original unit text and exact source revisions remain preserved in Evidence.</p>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} mode="properties"/> : null}</> : null}
      {activeTab === "curves" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Test and model data</p><h2>Curves</h2><p>Review available workflow data in the persistent Modeling graph.</p></div><button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Open in Modeling</button></div>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} mode="curves"/> : null}<table className="ux-table"><thead><tr><th>Related data</th><th>Type</th><th>Use</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).filter((node) => ["test_data", "processing_output", "material_model"].includes(node.domain_binding?.kind ?? "")).map((node) => <tr key={node.record_id}><td>{node.name}</td><td>{node.domain_binding?.kind.replaceAll("_", " ")}</td><td>{node.domain_binding?.kind === "test_data" ? "Observed input" : node.domain_binding?.kind === "processing_output" ? "Processed curve" : "Fitted response"}</td></tr>)}</tbody></table></> : null}
      {activeTab === "cards" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Solver delivery</p><h2>CAE Cards</h2><p>Cards with unchanged values can download directly. Cards with delivery notes open a review before download; values the solver cannot represent remain unavailable.</p></div></div><CardTable config={config} material={material} cards={experience.cards} onNavigate={onNavigate}/>{neutralMaterial ? <NeutralCardCreationPanel config={config} neutralMaterialId={neutralMaterial.object_id} neutralMaterialRevisionId={neutralMaterial.revision_id} materialName={content.name} materialCode={content.material_code} existingCards={experience.cards} onCreated={acceptCreatedCard}/> : !experience.cards.length && modelingFamily(material) ? <button className="ux-button primary" type="button" onClick={() => startModeling(material, onNavigate)}>Start Modeling</button> : null}</> : null}
      {activeTab === "evidence" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Related · Workflow · Evidence</p><h2>Connected material record</h2><p>Follow typed Record links and the material workflow; open technical identifiers only when needed.</p></div><button className="ux-button" type="button" onClick={() => onNavigate(browsePath(experience))}>Open exact Layout datasheet</button></div><div className="evidence-overview"><section><h3>Related Records</h3>{relatedLinks.length ? <table className="ux-table"><thead><tr><th>Relationship</th><th>Record</th><th>Type</th><th>Revision</th></tr></thead><tbody>{relatedLinks.map((related) => <tr key={related.id}><td>{related.label}</td><td title={related.endpoint.name}>{related.endpoint.name}</td><td>{related.endpoint.domain_binding?.kind?.replaceAll("_", " ") ?? "Catalog Record"}</td><td>r{related.endpoint.revision_no}</td></tr>)}</tbody></table> : <p className="ux-meta">No related Records are visible in the current scope.</p>}</section><section><h3>Workflow</h3><table className="ux-table"><thead><tr><th>Record</th><th>Role</th><th>Revision</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).map((node) => <tr key={`${node.record_id}:${node.record_revision_id}`}><td title={node.name}>{node.name}</td><td>{node.domain_binding?.kind?.replaceAll("_", " ") ?? "catalog record"}</td><td>r{node.revision_no}</td></tr>)}</tbody></table></section></div>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} mode="evidence"/> : null}<details className="ux-disclosure"><summary>Technical revision and provenance identifiers</summary><dl className="evidence-grid"><dt>Material ID</dt><dd>{material.material_id}</dd><dt>Aggregate ID</dt><dd>{material.current_revision.aggregate_id}</dd><dt>Full revision ID</dt><dd>{material.current_revision.id}</dd><dt>Content hash</dt><dd>{material.current_revision.content_hash}</dd><dt>Classification</dt><dd>{material.current_revision.classification}</dd><dt>Change reason</dt><dd>{material.current_revision.change_reason}</dd><dt>Recorded by</dt><dd>{material.current_revision.provenance.recorded_by}</dd></dl></details></> : null}
    </section>
  </div>;
  return <div className="ux-page materials-page materials-datasheet-page"><ResizableSplitPane id="cmp-materials-datasheet" navigator={navigator} main={datasheet} context={context} navigatorLabel="navigator" contextLabel="related records" /></div>;
}

export function ExactRecordDatasheetPage({ config, recordId, revisionId, onNavigate }: Props & { recordId: string; revisionId: string }) {
  const [record, setRecord] = useState<ConfigurableCatalogRecordResponse | null>(null);
  const [revisions, setRevisions] = useState<ConfigurableCatalogRecordResponse["current_revision"][]>([]);
  const [attributes, setAttributes] = useState<ConfigurableAttributeResponse[]>([]);
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
      const [revisionResult, attributeResult] = await Promise.all([
        listConfigurableCatalogRecordRevisions(config, recordId),
        listConfigurableCatalogAttributes(config, head.data.table_id),
      ]);
      const exact = revisionResult.data.items.find((item) => item.id === revisionId);
      if (!exact) throw new Error("The requested immutable record revision does not exist.");
      let exactGraph: CatalogWorkflowGraphResponse | null = null;
      try {
        exactGraph = (await getCatalogWorkflowGraph(config, recordId, revisionId, 6)).data;
      } catch {
        exactGraph = null;
      }
      if (!active) return;
      setRecord({ ...head.data, current_revision: exact });
      setRevisions(revisionResult.data.items);
      setAttributes(attributeResult.data.items);
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
  const attributeById = new Map(attributes.map((attribute) => [attribute.attribute_definition_id, attribute]));
  const navigator = <aside className="materials-left-pane" aria-label="Materials Browse Tree"><div className="workspace-back-row"><button className="ux-button tertiary" type="button" onClick={() => onNavigate(materialsReturnPath())}>← Results</button><strong>Browse</strong></div><MaterialsBrowseTree config={config} requestedRecord={graph?.root ?? null} onSelectRecord={(nextRecord, nextGraph) => setBrowseSelection({ record: nextRecord, graph: nextGraph })} onOpenRecord={(nextRecord) => onNavigate(`/materials/records/${nextRecord.record_id}/revisions/${nextRecord.current_revision.id}`)}/></aside>;
  const main = <section className="exact-record-datasheet material-tab-panel" aria-labelledby="exact-record-title">
    {loading && record ? <div className="datasheet-loading-line">Loading exact revision…</div> : null}
    {loading && !record ? <p className="loading-state">Loading exact record revision…</p> : null}
    {error ? <div className="ux-notice error" role="alert">{error}<button className="ux-button tertiary" type="button" onClick={() => setAttempt((current) => current + 1)}>Retry</button></div> : null}
    {record ? <><header className="exact-record-header"><div><p className="ux-kicker">Exact catalog revision</p><h1 id="exact-record-title">{record.current_revision.content.name}</h1><p>{record.current_revision.content.description ?? "No record description is available."}</p></div><div className="exact-revision-mark"><strong>r{record.current_revision.revision_no}</strong><span>Immutable</span></div></header><table className="ux-table exact-value-table"><thead><tr><th>Attribute</th><th>Original value</th><th>Normalized / semantics</th></tr></thead><tbody>{record.current_revision.content.values.map((value) => { const definition = attributeById.get(value.attribute_definition_id)?.current_revision.content; return <tr key={value.attribute_definition_id}><td><strong>{definition?.name ?? definition?.key ?? "Catalog attribute"}</strong></td><td>{configurableValueText(value)}</td><td>{value.data_type === "number" ? `${value.normalized_value} ${value.normalized_unit} · ${value.quantity_semantics}` : definition?.quantity_semantics ?? value.data_type.replaceAll("_", " ")}</td></tr>; })}</tbody></table>{!record.current_revision.content.values.length ? <div className="ux-empty"><strong>No values in this revision.</strong><p>The immutable record metadata remains available in Evidence.</p></div> : null}<details className="ux-disclosure"><summary>Evidence and immutable identifiers</summary><dl className="evidence-grid"><dt>Record ID</dt><dd>{record.record_id}</dd><dt>Revision ID</dt><dd>{record.current_revision.id}</dd><dt>Content hash</dt><dd>{record.current_revision.content_hash}</dd><dt>Classification</dt><dd>{record.current_revision.classification}</dd><dt>Change reason</dt><dd>{record.current_revision.change_reason}</dd></dl></details></> : null}
  </section>;
  const context = <aside className="materials-selection material-related-context" aria-label="Revision and related record context"><p className="ux-kicker">Record context</p><h2>{record?.current_revision.content.name ?? "Catalog record"}</h2>{browseSelection ? <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/records/${browseSelection.record.record_id}/revisions/${browseSelection.record.current_revision.id}`)}>Open selected record</button> : null}<h3>Revisions</h3><ul className="related-record-list">{revisions.map((revision) => <li key={revision.id}><button type="button" aria-current={revision.id === revisionId ? "page" : undefined} onClick={() => onNavigate(`/materials/records/${recordId}/revisions/${revision.id}`)}><span>Revision {revision.revision_no}</span><small>{revision.lifecycle_state} · {revision.change_reason}</small></button></li>)}</ul><h3>Related exact records</h3><ul className="related-record-list">{related.slice(0, 12).map((item) => <li key={item.id}><button type="button" onClick={() => onNavigate(`/materials/records/${item.endpoint.record_id}/revisions/${item.endpoint.record_revision_id}`)}><span>{item.endpoint.name}</span><small>{item.label} · r{item.endpoint.revision_no}</small></button></li>)}</ul></aside>;

  return <div className="ux-page materials-page materials-datasheet-page"><ResizableSplitPane id="cmp-materials-exact-record" navigator={navigator} main={main} context={context} navigatorLabel="navigator" contextLabel="record context" /></div>;
}

export function SolverCardPreviewPage({ config, materialId, cardId, onNavigate }: Props & { materialId: string; cardId: string }) {
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
    void getMaterialDetail(config, materialId)
      .then((detail) => loadMaterialExperience(config, detail.data.material))
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
      setLoading(false);
    });
    return () => { active = false; };
  }, [cardId, config, materialId]);

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
    } catch (cause: unknown) {
      setError(messageFor(cause));
    } finally {
      setDownloading(false);
    }
  }

  async function downloadMapping(): Promise<void> {
    if (!evidence) return;
    try {
      const result = await downloadSolverMappingArtifact(config, evidence);
      triggerDownload(result.blob, result.filename);
    } catch (cause: unknown) {
      setError(messageFor(cause));
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
      <div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards`)}>← CAE Cards</button><p className="ux-kicker">{card?.solver ?? "Solver card"} · Native ASCII</p><h1>{card?.label ?? material?.current_revision.content.name ?? "Card preview"}</h1><p>Check the saved card and delivery details before downloading.</p></div>
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
        <button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${materialId}`)}>Return to material</button>
        <details className="ux-disclosure"><summary>Advanced mapping evidence</summary><p className="ux-meta">The mapping report records exact, transformed, approximated, ignored, and unsupported fields. The native file retains its provenance headers.</p><button className="ux-button" type="button" disabled={!evidence} onClick={() => void downloadMapping()}>Download mapping report</button><dl className="evidence-grid"><dt>Card ID</dt><dd>{cardId}</dd><dt>Exact revision</dt><dd>{card?.revisionId ?? "Loading…"}</dd><dt>Card checksum</dt><dd>{evidence?.cardSha256 ?? "Recorded after generation"}</dd><dt>Mapping checksum</dt><dd>{evidence?.mappingReportSha256 ?? "Loading…"}</dd></dl></details>
      </aside>
    </div>
  </div></div>;
}

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
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [queueError, setQueueError] = useState<string | null>(null);
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);
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
    try {
      const [accessResult, principalResult, requestsResult] = await Promise.all([
        getEffectiveProductAccess(config),
        getAuthenticatedPrincipal(config),
        listReviewRequests(config, { limit: 50 }),
      ]);
      if (sequence !== requestSequence.current) return;
      setRole(accessResult.data.product_role);
      setPrincipalId(principalResult.data.principal_id);
      setReviewRequests(requestsResult.data.items);
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
    } catch (cause) {
      setDecisionError(messageFor(cause));
    } finally {
      setDecidingId(null);
    }
  }

  const resumePath = modelingSession ? `/modeling?stage=${modelingSession.workspace.activeStage}&family=${modelingSession.materialFamily}` : "/modeling";
  const stageLabel = modelingSession ? `${modelingSession.workspace.activeStage[0].toUpperCase()}${modelingSession.workspace.activeStage.slice(1)}` : null;
  const canDecide = role === "reviewer" || role === "administrator";
  const visibleRequests = canDecide
    ? reviewRequests
    : reviewRequests.filter((request) => request.requested_by === principalId);
  const pendingRequests = visibleRequests.filter((request) => request.decision === null);
  const decidedRequests = visibleRequests.filter((request) => request.decision !== null);
  const needsAttention = canDecide ? pendingRequests : [];
  const inProgress = canDecide ? [] : pendingRequests;

  return <div className="ux-page"><div className="activity-shell"><div className="activity-content">
    <header className="activity-heading"><div><h1>Activity</h1><p>Resume your work, review submitted material data, and find completed outcomes.</p></div><button className="ux-button tertiary" type="button" onClick={() => void loadQueue()} disabled={loadingQueue}>{loadingQueue ? "Refreshing…" : "Refresh"}</button></header>
    {queueError ? <div className="activity-queue-error" role="alert"><span>{queueError}</span><button className="ux-button" type="button" onClick={() => void loadQueue()}>Retry</button></div> : null}
    <ActivityQueueSection title="Needs attention" description={canDecide ? "Submitted work waiting for your review." : "No review actions are assigned to this role."} loading={loadingQueue} emptyMessage="Nothing needs your attention." items={needsAttention} action={canDecide ? (request) => <ReviewAction request={request} reviewing={reviewingId === request.review_request_id} deciding={decidingId === request.review_request_id} reason={decisionReason} error={reviewingId === request.review_request_id ? decisionError : null} onOpen={() => { setReviewingId(request.review_request_id); setDecisionReason(""); setDecisionError(null); }} onCancel={() => { setReviewingId(null); setDecisionReason(""); setDecisionError(null); }} onReasonChange={setDecisionReason} onDecide={(decision) => void decide(request, decision)} /> : undefined} />
    <section className="activity-section" aria-labelledby="activity-in-progress"><div className="activity-section-heading"><h2 id="activity-in-progress">In progress</h2><p>Work you can resume and review requests still awaiting a decision.</p></div>
      {modelingSession ? <ul className="activity-list"><li data-testid="recent-modeling-session"><span><strong>{modelingSession.material?.label ?? modelingSession.objective ?? "Material modeling session"}</strong><small className="ux-meta">{`${modelingSession.materialFamily} · ${stageLabel} · ${modelingSession.testData ? `${modelingSession.testData.label} r${modelingSession.testData.revisionNo}` : "No exact Test Data"} · ${modelingSession.workspace.selectedDocumentIds.length} selected curves`}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(resumePath)}>{`Resume ${stageLabel}`}</button></li></ul> : null}
      {!loadingQueue && inProgress.length ? <ActivityRows items={inProgress} /> : null}
      {!modelingSession && !loadingQueue && !inProgress.length ? <section className="activity-empty-state" role="status" aria-label="No work in progress"><div><strong>No work in progress</strong><p>Start a Modeling session or submit an available item for review from its workspace.</p></div><button className="ux-button" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button></section> : null}
      {loadingQueue && !modelingSession ? <ActivityQueueLoading /> : null}
    </section>
    <section className="activity-section" aria-labelledby="activity-outcomes"><div className="activity-section-heading"><h2 id="activity-outcomes">Recent outcomes</h2><p>Completed review decisions and solver cards opened in this browser.</p></div>
      {!loadingQueue && decidedRequests.length ? <ActivityRows items={decidedRequests} /> : null}
      {deliveryActivities.length ? <ul className="activity-list">{deliveryActivities.map((activity) => <li key={`${activity.action}:${activity.cardId}`} data-testid="recent-solver-card-activity"><span><strong>{activity.action === "download" ? "Downloaded solver card" : "Previewed solver card"} · {activity.cardLabel}</strong><small className="ux-meta">{activity.materialLabel} · {activity.solver} {activity.extension} · {formatActivityTime(activity.occurredAt)}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${activity.materialId}/cards/${activity.cardId}`)}>Open card</button></li>)}</ul> : null}
      {!loadingQueue && !decidedRequests.length && !deliveryActivities.length ? <p className="activity-empty-line" role="status">No recent outcomes yet.</p> : null}
      {loadingQueue ? <ActivityQueueLoading /> : null}
    </section>
    {governedContext.length ? <section className="activity-context-line" aria-label="Modeling review context"><span>A modeling review or validation context is available.</span><button className="ux-button" type="button" onClick={() => onNavigate(`/modeling?stage=validate&family=${modelingSession?.materialFamily ?? "metal"}`)}>Resume validation</button><details className="ux-disclosure"><summary>Advanced context</summary><dl className="evidence-grid">{governedContext.map(([label, id, revisionId]) => <div key={label}><dt>{label}</dt><dd>{id}{revisionId ? ` · revision ${revisionId}` : ""}</dd></div>)}</dl></details></section> : null}
    <details className="ux-disclosure activity-advanced"><summary>Advanced activity evidence</summary><p>Review requests currently expose immutable revision evidence, but this API does not provide display names for the submitted item or people. Those identifiers remain here until the work projection supplies readable names.</p><button className="ux-button" type="button" onClick={() => onNavigate("/exports")}>Open export packages</button></details>
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

function formatActivityTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function ActivityQueueLoading() {
  return <div className="activity-queue-loading" aria-busy="true" aria-label="Loading activity queue"><span /><span /><span /></div>;
}

function ActivityRows({ items, action }: { items: ReviewRequestResponse[]; action?: (request: ReviewRequestResponse) => ReactNode }) {
  return <ul className="activity-list activity-review-list">{items.map((request) => <li key={request.review_request_id}><span><strong>{reviewTaskLabel(request.aggregate_type)}</strong><small className="ux-meta">{reviewStatus(request)} · {request.reason || "No request reason was provided."} · {formatActivityTime(request.decision?.decided_at ?? request.requested_at)}</small></span>{action ? action(request) : <span className="activity-row-state">{reviewStatus(request)}</span>}</li>)}</ul>;
}

function ActivityQueueSection({ title, description, loading, emptyMessage, items, action }: { title: string; description: string; loading: boolean; emptyMessage: string; items: ReviewRequestResponse[]; action?: (request: ReviewRequestResponse) => ReactNode }) {
  const headingId = `activity-${title.toLowerCase().replaceAll(" ", "-")}`;
  return <section className="activity-section" aria-labelledby={headingId}><div className="activity-section-heading"><h2 id={headingId}>{title}</h2><p>{description}</p></div>{loading ? <ActivityQueueLoading /> : items.length ? <ActivityRows items={items} action={action} /> : <p className="activity-empty-line" role="status">{emptyMessage}</p>}</section>;
}

function ReviewAction({ request, reviewing, deciding, reason, error, onOpen, onCancel, onReasonChange, onDecide }: { request: ReviewRequestResponse; reviewing: boolean; deciding: boolean; reason: string; error: string | null; onOpen: () => void; onCancel: () => void; onReasonChange: (value: string) => void; onDecide: (decision: "approved" | "changes_requested") => void }) {
  if (!reviewing) return <button className="ux-button primary" type="button" onClick={onOpen}>Review</button>;
  return <form className="activity-review-form" onSubmit={(event: FormEvent<HTMLFormElement>) => { event.preventDefault(); onDecide("approved"); }}><label>Review reason<textarea value={reason} onChange={(event) => onReasonChange(event.target.value)} placeholder="Explain the approval or requested change" required disabled={deciding} /></label>{error ? <p role="alert">{error}</p> : null}<div><button className="ux-button primary" type="submit" disabled={deciding}>{deciding ? "Saving…" : "Approve"}</button><button className="ux-button" type="button" disabled={deciding} onClick={() => onDecide("changes_requested")}>Request changes</button><button className="ux-button tertiary" type="button" disabled={deciding} onClick={onCancel}>Cancel</button></div></form>;
}
