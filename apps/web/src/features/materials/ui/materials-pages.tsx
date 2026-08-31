import {
  lazy,
  Suspense,
  type ReactNode,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  getAuthenticatedPrincipal,
  type ApiConfig,
} from "../../../shared/api";
import {
  getCatalogWorkflowGraph,
  getConfigurableCatalogRecord,
  listConfigurableCatalogRecordRevisions,
} from "../../catalog";
import {
  getMaterialDetail,
} from "../api/materials-api";
import type {
  CatalogDataCategory,
  CatalogWorkflowGraphResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableLinkEndpoint,
  ConfigurableRecordValue,
  DomainRevisionBinding,
} from "../../catalog/contracts";
import type {
  MaterialResponse,
  PropertySetResponse,
} from "../contracts";
import {
  CATALOG_DATA_CATEGORIES,
  dataCategoryForEndpoint,
} from "../../../catalog-data-categories";
import { MaterialDatasheetProjection } from "../../../material-datasheet-projection";
import { MaterialsScrollRegion } from "../../../materials-scroll-rail";
import { publishWorkspaceStatus } from "../../../design/application-shell";
import { ResizableSplitPane } from "../../../design/resizable-split-pane";
import { EngineeringIcon } from "../../../design/icon";
import { saveModelingSession } from "../../modeling";
import {
  downloadSolverCardArtifact,
  downloadSolverMappingArtifact,
  loadSolverCardEvidence,
  mappingQuantityLabel,
  previewSolverCardText,
  recordDeliveryActivity,
  type SolverCardEvidence,
  type SolverCardSummary,
} from "../../../solver-card-delivery";
import {
  MappingStatusList,
  NeutralCardCreationPanel,
  SolverCardAction,
} from "../../../solver-card-delivery-ui";
import { ReviewRequestAction } from "../../../review-request-action";
import {
  appendActivityFailure,
  appendActivityOutcome,
  type ActivityRecoveryContext,
} from "../../../activity-recovery";
import {
  exactRecordPath,
  materialDetailPath,
  materialPinQuery,
  materialsReturnPath,
  type MaterialRevisionPin,
  type MaterialTab,
} from "../model/materials-route-state";
import {
  loadMaterialExperience,
  loadPinnedMaterialExperience,
  nodeBindings,
  solverCardSummaryFromEndpoint,
  trueStressPlasticStrainResponseFromNativeCard,
  type MaterialExperience,
} from "../api/load-material-experience";
import {
  loadExactProcessingOutput,
  type ExactProcessingOutput,
} from "../api/load-exact-processing-output";
import {
  ProcessingOutputDetail,
  ProcessingOutputEvidence,
} from "./processing-output-detail";
import { ExactTestDataDetail } from "./exact-test-data-detail";
import { ExactSourceActions } from "./exact-source-actions";

const materialsBrowseTreeModule = import("../../../materials-browse-tree");
const MaterialsBrowseTree = lazy(() =>
  materialsBrowseTreeModule.then((module) => ({
    default: module.MaterialsBrowseTree,
  })),
);

export type {
  MaterialRevisionPin,
  MaterialTab,
} from "../model/materials-route-state";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  locationSearch?: string;
}

interface RelatedExactRecord {
  id: string;
  label: string;
  endpoint: ConfigurableLinkEndpoint;
}

function directRelatedRecords(
  graph: CatalogWorkflowGraphResponse | null,
  recordId?: string,
  revisionId?: string,
): RelatedExactRecord[] {
  if (!graph || !recordId || !revisionId) return [];
  return graph.links
    .filter(
      (link) =>
        (link.source.record_id === recordId &&
          link.source.record_revision_id === revisionId) ||
        (link.target.record_id === recordId &&
          link.target.record_revision_id === revisionId),
    )
    .map((link) => {
      const fromRoot =
        link.source.record_id === recordId &&
        link.source.record_revision_id === revisionId;
      return {
        id: link.record_link_id,
        label: fromRoot
          ? link.link_type_revision.content.forward_label
          : link.link_type_revision.content.reverse_label,
        endpoint: fromRoot ? link.target : link.source,
      };
    });
}

const tabs: ReadonlyArray<{ id: MaterialTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "properties", label: "Properties" },
  { id: "curves", label: "Curves" },
  { id: "cards", label: "CAE Cards" },
  { id: "evidence", label: "Source & history" },
];

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error
    ? cause.message
    : "The material workspace could not be loaded.";
}

function relatedRecordGroups(items: RelatedExactRecord[]): Array<{
  label: string;
  items: RelatedExactRecord[];
}> {
  return [
    ...CATALOG_DATA_CATEGORIES,
    { key: null, label: "Other related records" },
  ]
    .map((category) => ({
      label: category.label,
      items: items.filter(
        (item) => dataCategoryForEndpoint(item.endpoint) === category.key,
      ),
    }))
    .filter((group) => group.items.length > 0);
}

function relatedRecordTypeLabel(endpoint: ConfigurableLinkEndpoint): string {
  const binding = nodeBindings(endpoint)[0];
  if (binding) return domainKindLabel(binding.kind);
  const fallbackByCategory: Partial<Record<CatalogDataCategory, string>> = {
    technical_data: "Technical record",
    test_data: "Test Data",
    simulation_data: "Derived result",
    solver_cards: "Solver Card",
  };
  const category = dataCategoryForEndpoint(endpoint);
  return category ? fallbackByCategory[category] ?? "Related record" : "Related record";
}

function exactModelingContext(
  graph: CatalogWorkflowGraphResponse | null,
  materialStates: MaterialExperience["detail"]["states"] = [],
): {
  material?: { id: string; revisionId: string; revisionNo: number; label: string };
  materialState?: {
    id: string;
    revisionId: string;
    revisionNo: number;
    label: string;
  };
} {
  const uniqueReference = (kind: "material" | "material_state") => {
    if (!graph) return undefined;
    const candidates = [graph.root, ...graph.nodes].flatMap((node) =>
      nodeBindings(node)
        .filter((binding) => binding.kind === kind)
        .map((binding) => ({
          id: binding.object_id,
          revisionId: binding.revision_id,
          revisionNo: node.revision_no,
          label: node.name,
        })),
    );
    const unique = new Map(
      candidates.map((candidate) => [
        `${candidate.id}:${candidate.revisionId}`,
        candidate,
      ]),
    );
    return unique.size === 1 ? [...unique.values()][0] : undefined;
  };
  const graphState = uniqueReference("material_state");
  const domainState =
    !graphState && materialStates.length === 1
      ? {
          id: materialStates[0].material_state_id,
          revisionId: materialStates[0].current_revision.id,
          revisionNo: materialStates[0].current_revision.revision_no,
          label: materialStates[0].current_revision.content.name,
        }
      : undefined;
  return {
    material: uniqueReference("material"),
    materialState: graphState ?? domainState,
  };
}

function RelatedExactRecordList({
  items,
  onNavigate,
}: {
  items: RelatedExactRecord[];
  onNavigate: (path: string) => void;
}) {
  return (
    <div className="related-record-groups">
      {relatedRecordGroups(items).map((group) => (
        <section className="related-record-group" key={group.label}>
          <h3>
            {group.label} <span className="ux-meta">{group.items.length}</span>
          </h3>
          <ul className="related-record-list">
            {group.items.slice(0, 12).map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() =>
                    onNavigate(
                      exactRecordPath(
                        item.endpoint.record_id,
                        item.endpoint.record_revision_id,
                      ),
                    )
                  }
                >
                  <span>{item.endpoint.name}</span>
                  <small>
                    {relatedRecordTypeLabel(item.endpoint)} · {item.label} · r
                    {item.endpoint.revision_no}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ExactLinkedRecordTable({
  items,
  onNavigate,
}: {
  items: RelatedExactRecord[];
  onNavigate: (path: string) => void;
}) {
  return (
    <table className="ux-table exact-record-link-table">
      <thead>
        <tr>
          <th>Relation</th>
          <th>Record</th>
          <th>Type</th>
          <th>Exact revision</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td>{item.label}</td>
            <td>
              <button
                className="exact-record-link-button"
                type="button"
                onClick={() => onNavigate(exactRecordPath(
                  item.endpoint.record_id,
                  item.endpoint.record_revision_id,
                ))}
              >
                {item.endpoint.external_key ?? item.endpoint.name}
              </button>
            </td>
            <td>{domainKindLabel(nodeBindings(item.endpoint)[0]?.kind)}</td>
            <td>r{item.endpoint.revision_no}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function currentProperty(
  experience: MaterialExperience | undefined,
): PropertySetResponse | undefined {
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

function formatApplicabilityRange(
  minimum: number | null | undefined,
  maximum: number | null | undefined,
  unit: string,
): string {
  if (minimum === null || minimum === undefined) {
    return maximum === null || maximum === undefined
      ? "—"
      : `≤ ${maximum} ${unit}`;
  }
  if (maximum === null || maximum === undefined) return `≥ ${minimum} ${unit}`;
  if (minimum === maximum) return `${minimum} ${unit}`;
  return `${minimum}–${maximum} ${unit}`;
}

function sourceLabel(experience: MaterialExperience | undefined): string {
  const property = currentProperty(experience)?.current_revision.content;
  const source =
    property?.yield_stress_source ??
    property?.youngs_modulus_source ??
    property?.density_source;
  return (
    source?.reference || source?.kind.replaceAll("_", " ") || "Not specified"
  );
}

function browsePath(experience: MaterialExperience | undefined): string {
  const root = experience?.graph?.root;
  return root
    ? exactRecordPath(root.record_id, root.record_revision_id)
    : "/materials";
}

function neutralMaterialBinding(
  experience: MaterialExperience | null | undefined,
): DomainRevisionBinding | null {
  return (
    experience?.graph?.nodes
      .map((node) => node.domain_binding)
      .find(
        (binding): binding is DomainRevisionBinding =>
          binding?.kind === "neutral_material",
      ) ?? null
  );
}

function deliveryMaterial(material: MaterialResponse) {
  return {
    materialId: material.material_id,
    materialRevisionId: material.current_revision.id,
    materialLabel: material.current_revision.content.name,
  };
}

function modelingFamily(
  material: MaterialResponse,
): "metal" | "polymer" | "elastomer" | null {
  const family =
    `${material.current_revision.content.material_class} ${material.current_revision.content.material_family ?? ""}`.toLowerCase();
  if (family.includes("elastomer") || family.includes("rubber"))
    return "elastomer";
  if (family.includes("polymer") || family.includes("plastic"))
    return "polymer";
  if (family.includes("metal")) return "metal";
  return null;
}

function startModeling(
  material: MaterialResponse,
  onNavigate: (path: string) => void,
  materialState?: {
    id: string;
    revisionId: string;
    revisionNo: number;
    label: string;
  },
): void {
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
    materialState,
    contextSelectionRequired: !materialState,
    workspace: {
      activeStage: "data",
      selectedDocumentIds: [],
      selectedStepIndex: 0,
      selectedStageOrdinal: 0,
      plotView: "pipeline",
      settingsOpen: typeof window === "undefined" || window.innerWidth >= 1400,
    },
  });
  const query = new URLSearchParams({
    stage: "data",
    family,
    material_id: material.material_id,
    material_revision_id: material.current_revision.id,
  });
  if (materialState) {
    query.set("material_state_id", materialState.id);
    query.set("material_state_revision_id", materialState.revisionId);
  }
  onNavigate(`/modeling?${query.toString()}`);
}

function RepresentativeCurve({
  points,
}: {
  points: Array<{ x: number; y: number }>;
}) {
  const normalizedPoints = useMemo(
    () => normalizeLinkedResponsePoints(points),
    [points],
  );
  const frameRef = useRef<HTMLDivElement | null>(null);
  const frameSize = useResponsePlotSize(frameRef, normalizedPoints.length);
  if (normalizedPoints.length < 2)
    return null;
  return (
    <div ref={frameRef} className="material-curve-preview response-plot-frame">
      <ResponsePlotSvg
        points={normalizedPoints}
        frameSize={frameSize}
        ariaLabel="Representative material response showing true stress in MPa versus true plastic strain"
        titleText="True stress versus true plastic strain for this material."
        legendLabel="Material response"
      />
    </div>
  );
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
      const thumbHeight = Math.min(
        trackHeight,
        Math.max(
          22,
          trackHeight * (preview.clientHeight / preview.scrollHeight),
        ),
      );
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
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(updateScrollRail);
    observer?.observe(preview);
    observer?.observe(rail);
    const frame =
      typeof window.requestAnimationFrame === "function"
        ? window.requestAnimationFrame(updateScrollRail)
        : 0;
    return () => {
      preview.removeEventListener("scroll", updateScrollRail);
      preview.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", updateScrollRail);
      observer?.disconnect();
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [text]);

  return (
    <div className="preview-scroll-shell">
      <pre
        ref={previewRef}
        className="native-card-preview preview-scroll"
        aria-label="Native solver card preview"
        tabIndex={0}
      >
        {text}
      </pre>
      <div
        ref={railRef}
        className="preview-scroll-rail"
        data-scrollable="false"
        aria-hidden="true"
      >
        <span ref={thumbRef} className="preview-scroll-thumb" />
      </div>
    </div>
  );
}

function normalizeLinkedResponsePoints(
  points: Array<{ x: number; y: number }>,
): Array<{ x: number; y: number }> {
  const maximumMagnitude = Math.max(
    ...points.map((point) => Math.abs(point.y)),
    0,
  );
  const stressScale = maximumMagnitude > 10_000 ? 1e-6 : 1;
  return points.map((point) => ({ x: point.x, y: point.y * stressScale }));
}

function useResponsePlotSize(
  frameRef: { current: HTMLDivElement | null },
  pointCount: number,
): { width: number; height: number } {
  const [frameSize, setFrameSize] = useState({ width: 720, height: 300 });
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const measure = () => {
      const bounds = frame.getBoundingClientRect();
      setFrameSize((current) => {
        const width = Math.max(1, Math.round(bounds.width));
        const height = Math.max(1, Math.round(bounds.height));
        return current.width === width && current.height === height
          ? current
          : { width, height };
      });
    };
    measure();
    window.addEventListener("resize", measure);
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(measure);
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
  for (
    let value = Math.ceil(minimum / step) * step;
    value <= maximum + step * 0.01;
    value += step
  ) {
    ticks.push(Number(value.toFixed(6)));
  }
  return ticks;
}

function formatLinkedResponseTick(value: number, axis: "x" | "y"): string {
  if (axis === "x") {
    if (Math.abs(value) < 1e-9) return "0";
    return value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  }
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(
    value,
  );
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
  const xDomainMaximum = Math.max(
    xDomainStep,
    Math.ceil((xMaximum + Math.max(xMaximum * 0.05, 0.005)) / xDomainStep) *
      xDomainStep,
  );
  const yMinimum = Math.min(...points.map((point) => point.y));
  const yMaximum = Math.max(...points.map((point) => point.y));
  const ySpan = Math.max(yMaximum - yMinimum, 1);
  const yPad = Math.max(ySpan * 0.05, 10);
  const yDomainMinimum = Math.max(0, Math.floor((yMinimum - yPad) / 10) * 10);
  const yDomainMaximum = Math.max(
    yDomainMinimum + 10,
    Math.ceil((yMaximum + yPad) / 10) * 10,
  );
  const yStep =
    yDomainMaximum - yDomainMinimum <= 400
      ? 50
      : yDomainMaximum - yDomainMinimum <= 800
        ? 100
        : 200;
  const xTicks = plotTicks(0, xDomainMaximum, xStep);
  const yTicks = plotTicks(yDomainMinimum, yDomainMaximum, yStep);
  const scaleX = (value: number) =>
    margin.left + (value / xDomainMaximum) * plotWidth;
  const scaleY = (value: number) =>
    margin.top +
    (1 - (value - yDomainMinimum) / (yDomainMaximum - yDomainMinimum)) *
      plotHeight;
  const mappedPoints = points.map((point) => ({
    x: scaleX(point.x),
    y: scaleY(point.y),
  }));
  const linePoints = mappedPoints
    .map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");
  const gridX = xTicks.map((value) => (
    <line
      key={`grid-x-${value}`}
      x1={scaleX(value)}
      y1={margin.top}
      x2={scaleX(value)}
      y2={margin.top + plotHeight}
    />
  ));
  const gridY = yTicks.map((value) => (
    <line
      key={`grid-y-${value}`}
      x1={margin.left}
      y1={scaleY(value)}
      x2={margin.left + plotWidth}
      y2={scaleY(value)}
    />
  ));
  const legendWidth = 168;
  const legendCandidates = [
    { x: margin.left + plotWidth - legendWidth - 8, y: margin.top + 16 },
    { x: margin.left + 8, y: margin.top + 16 },
    {
      x: margin.left + plotWidth - legendWidth - 8,
      y: margin.top + plotHeight - 8,
    },
    { x: margin.left + 8, y: margin.top + plotHeight - 8 },
  ];
  const legend =
    legendCandidates.find(
      (candidate) =>
        !mappedPoints.some(
          (point) =>
            point.x >= candidate.x - 4 &&
            point.x <= candidate.x + legendWidth &&
            point.y >= candidate.y - 16 &&
            point.y <= candidate.y + 4,
        ),
    ) ?? legendCandidates[0];

  return (
    <svg
      className="linked-response-plot response-plot"
      role="img"
      aria-label={ariaLabel}
      viewBox={`0 0 ${width} ${height}`}
      data-series-rows={points.length}
      data-x-domain={`0,${xDomainMaximum}`}
      data-y-domain={`${yDomainMinimum},${yDomainMaximum}`}
      data-x-label="True plastic strain [1]"
      data-y-label="True stress (MPa)"
    >
      <title>{titleText}</title>
      <g className="linked-response-grid plot-grid" aria-hidden="true">
        {gridX}
        {gridY}
      </g>
      <path
        className="linked-response-axis plot-axis"
        d={`M ${margin.left} ${margin.top} V ${margin.top + plotHeight} H ${margin.left + plotWidth}`}
      />
      <g className="linked-response-labels">
        {xTicks.map((value) => (
          <g key={`x-tick-${value}`}>
            <line
              className="linked-response-tick plot-tick"
              x1={scaleX(value)}
              y1={margin.top + plotHeight}
              x2={scaleX(value)}
              y2={margin.top + plotHeight + 5}
            />
            <text
              className="linked-response-tick-label plot-tick-label"
              x={scaleX(value)}
              y={height - 24}
              textAnchor="middle"
            >
              {formatLinkedResponseTick(value, "x")}
            </text>
          </g>
        ))}
        {yTicks.map((value) => (
          <g key={`y-tick-${value}`}>
            <line
              className="linked-response-tick plot-tick"
              x1={margin.left - 5}
              y1={scaleY(value)}
              x2={margin.left}
              y2={scaleY(value)}
            />
            <text
              className="linked-response-tick-label plot-tick-label"
              x={margin.left - 10}
              y={scaleY(value) + 4}
              textAnchor="end"
            >
              {formatLinkedResponseTick(value, "y")}
            </text>
          </g>
        ))}
        <text
          className="linked-response-axis-title plot-axis-title"
          x={margin.left + plotWidth / 2}
          y={height - 7}
          textAnchor="middle"
        >
          True plastic strain [1]
        </text>
        <text
          className="linked-response-axis-title plot-axis-title"
          transform={`translate(16 ${margin.top + plotHeight / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          True stress (MPa)
        </text>
      </g>
      <polyline
        className="linked-response-line response-line"
        points={linePoints}
        data-series-line="true"
      />
      <g className="linked-response-points response-points" aria-hidden="true">
        {mappedPoints.map((point, index) => (
          <circle
            key={`point-${index}`}
            className="linked-response-point response-point"
            cx={point.x}
            cy={point.y}
            r="3"
          />
        ))}
      </g>
      <g
        className="linked-response-legend plot-legend"
        transform={`translate(${legend.x} ${legend.y})`}
      >
        <line x1="0" y1="-4" x2="18" y2="-4" />
        <text x="26" y="0">
          {legendLabel}
        </text>
      </g>
    </svg>
  );
}

function LinkedResponseGraph({
  points,
}: {
  points: Array<{ x: number; y: number }>;
}) {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const normalizedPoints = useMemo(
    () => normalizeLinkedResponsePoints(points),
    [points],
  );
  const frameSize = useResponsePlotSize(frameRef, normalizedPoints.length);
  if (normalizedPoints.length < 2) return null;
  return (
    <section
      className="linked-response-band response-plot-band"
      aria-labelledby="linked-response-title"
    >
      <header className="linked-response-heading response-plot-heading">
        <div>
          <h2 id="linked-response-title">Linked response</h2>
          <p>Same values as the selected card preview.</p>
        </div>
        <span className="ux-meta">Card evidence · read only</span>
      </header>
      <div ref={frameRef} className="linked-response-frame response-plot-frame">
        <ResponsePlotSvg
          points={normalizedPoints}
          frameSize={frameSize}
          ariaLabel="Linked response chart showing true stress in MPa versus true plastic strain"
          titleText="True stress versus true plastic strain from the selected card."
          legendLabel="Card hardening data"
        />
      </div>
    </section>
  );
}

function formatResponsePoint(value: number, axis: "x" | "y"): string {
  if (axis === "x")
    return value.toFixed(6).replace(/0+$/, "").replace(/\.$/, "") || "0";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(
    value,
  );
}

function ResponsePointsTable({
  points,
}: {
  points: Array<{ x: number; y: number }>;
}) {
  const normalizedPoints = useMemo(
    () => normalizeLinkedResponsePoints(points),
    [points],
  );
  const regionId = `material-response-points-${useId().replaceAll(":", "")}`;
  if (!normalizedPoints.length) return null;
  return (
    <section
      className="material-response-points"
      aria-labelledby={`${regionId}-heading`}
    >
      <div className="material-response-points-heading">
        <div>
          <h3 id={`${regionId}-heading`}>Response points</h3>
          <span className="section-subtitle">
            Exact ordered series · {normalizedPoints.length} points
          </span>
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
          <thead>
            <tr>
              <th scope="col">Point</th>
              <th scope="col">True plastic strain</th>
              <th scope="col">True stress (MPa)</th>
            </tr>
          </thead>
          <tbody>
            {normalizedPoints.map((point, index) => (
              <tr
                key={`response-point-${index}`}
                data-point-index={index + 1}
                data-x-value={point.x}
                data-y-value={point.y}
              >
                <th scope="row">{index + 1}</th>
                <td>{formatResponsePoint(point.x, "x")}</td>
                <td>{formatResponsePoint(point.y, "y")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </MaterialsScrollRegion>
    </section>
  );
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

function SolverAvailability({
  config,
  cards,
  materialId,
  onNavigate,
}: {
  config: ApiConfig;
  cards: SolverCardSummary[];
  materialId: string;
  onNavigate: (path: string) => void;
}) {
  const [evidence, setEvidence] = useState<
    Map<string, SolverCardEvidence> | null
  >(null);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!cards.length) {
      setEvidence(new Map());
      setLoadError(false);
      return;
    }
    let active = true;
    setEvidence(null);
    setLoadError(false);
    void Promise.allSettled(
      cards.map((card) => loadSolverCardEvidence(config, card)),
    ).then((results) => {
      if (!active) return;
      const loaded = new Map<string, SolverCardEvidence>();
      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          loaded.set(cards[index].revisionId, result.value);
        }
      });
      setEvidence(loaded);
      setLoadError(loaded.size !== cards.length);
    });
    return () => {
      active = false;
    };
  }, [attempt, cards, config]);

  if (!cards.length)
    return (
      <p className="ux-meta">No released reference card is available yet.</p>
    );
  if (!evidence)
    return (
      <p className="delivery-progress-line" role="status">
        Loading solver card state…
      </p>
    );
  return (
    <>
      <ul className="solver-availability-list">
        {cards.map((card) => {
          const cardEvidence = evidence.get(card.revisionId);
          return (
            <li key={card.id}>
              <dl>
                <div>
                  <dt>Target</dt>
                  <dd>
                    {cardEvidence
                      ? `${card.solver} ${cardEvidence.target.version}`
                      : card.solver}
                  </dd>
                </div>
                <div>
                  <dt>Format</dt>
                  <dd>Native ASCII {card.extension}</dd>
                </div>
                <div>
                  <dt>Unit system</dt>
                  <dd>
                    {cardEvidence?.target.unit_system.replaceAll("_", " · ") ??
                      "—"}
                  </dd>
                </div>
                <div>
                  <dt>Release state</dt>
                  <dd>
                    {cardEvidence?.lifecycleState.replaceAll("_", " ") ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt>Action</dt>
                  <dd>
                    <button
                      className="ux-button tertiary"
                      type="button"
                      onClick={() =>
                        onNavigate(`/materials/${materialId}/cards/${card.id}`)
                      }
                    >
                      Preview card
                    </button>
                  </dd>
                </div>
              </dl>
            </li>
          );
        })}
      </ul>
      {loadError ? (
        <div className="solver-availability-error" role="alert">
          <span>Some solver card states could not be loaded.</span>
          <button
            className="ux-button tertiary"
            type="button"
            onClick={() => setAttempt((current) => current + 1)}
          >
            Retry
          </button>
        </div>
      ) : null}
    </>
  );
}

function ExactSolverCardDelivery({
  config,
  card,
}: {
  config: ApiConfig;
  card: SolverCardSummary;
}) {
  const [evidence, setEvidence] = useState<SolverCardEvidence | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState<"download" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [acknowledged, setAcknowledged] = useState(false);
  const [previewExpanded, setPreviewExpanded] = useState(false);

  useEffect(() => {
    let active = true;
    setEvidence(null);
    setPreview(null);
    setError(null);
    setAcknowledged(false);
    setPreviewExpanded(false);
    void Promise.all([
      loadSolverCardEvidence(config, card),
      previewSolverCardText(config, card),
    ])
      .then(([evidenceResult, previewResult]) => {
        if (!active) return;
        setEvidence(evidenceResult);
        setPreview(previewResult.data);
      })
      .catch((cause: unknown) => {
        if (active) setError(messageFor(cause));
      });
    return () => {
      active = false;
    };
  }, [attempt, card, config]);

  async function download(): Promise<void> {
    if (!evidence || evidence.disposition === "blocked") return;
    setBusy("download");
    setError(null);
    try {
      const result = await downloadSolverCardArtifact(config, card);
      triggerDownload(result.data.blob, result.data.filename);
    } catch (cause: unknown) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  const blockers =
    evidence?.mappingItems
      .filter((item) => item.status === "unsupported")
      .map((item) => mappingQuantityLabel(item.name)) ?? [];
  const reviewItems =
    evidence?.mappingItems
      .filter(
        (item) => item.status === "approximated" || item.status === "ignored",
      )
      .map((item) => mappingQuantityLabel(item.name)) ?? [];
  const blocked = evidence?.disposition === "blocked";
  const reviewRequired = evidence?.disposition === "review";
  const downloadDisabled =
    !evidence ||
    busy !== null ||
    blocked ||
    (reviewRequired && !acknowledged);
  return (
    <section
      className={`exact-solver-card-delivery${previewExpanded ? " preview-expanded" : ""}`}
    >
      <div className="detail-section-heading">
        <h2>Solver Card details</h2>
      </div>
      {evidence ? (
        <dl className="exact-solver-card-properties">
          <div>
            <dt>Target</dt>
            <dd>
              {card.solver} {evidence.target.version}
            </dd>
          </div>
          <div>
            <dt>Format</dt>
            <dd>Native ASCII {card.extension}</dd>
          </div>
          <div>
            <dt>Unit system</dt>
            <dd>{evidence.target.unit_system.replaceAll("_", " · ")}</dd>
          </div>
          <div>
            <dt>Release state</dt>
            <dd>{evidence.lifecycleState.replaceAll("_", " ")}</dd>
          </div>
          <div>
            <dt>Exact revision</dt>
            <dd>r{evidence.revisionNo}</dd>
          </div>
          {reviewRequired ? (
            <div>
              <dt>Review required</dt>
              <dd>{reviewItems.join(", ") || "Delivery mapping"}</dd>
            </div>
          ) : null}
        </dl>
      ) : error ? null : (
        <p className="delivery-progress-line" role="status">
          Loading solver card state…
        </p>
      )}
      {blocked ? (
        <p className="ux-notice error" role="alert">
          Download blocked: {blockers.join(", ") || "unsupported source values"}.
        </p>
      ) : null}
      {reviewRequired ? (
        <label className="delivery-acknowledgement">
          <input
            type="checkbox"
            name="exact-card-delivery-acknowledgement"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
          Reviewed
        </label>
      ) : null}
      <div className="card-action-row">
        <button
          className="ux-button primary"
          type="button"
          disabled={downloadDisabled}
          onClick={() => void download()}
        >
          {busy === "download"
            ? "Preparing…"
            : blocked
              ? "Download blocked"
              : `Download ${card.extension}`}
        </button>
        <button
          className="ux-button"
          type="button"
          disabled={preview === null}
          aria-expanded={previewExpanded}
          onClick={() => setPreviewExpanded((current) => !current)}
        >
          {previewExpanded ? "Collapse preview" : "Expand preview"}
        </button>
      </div>
      {error ? (
        <div className="ux-notice error" role="alert">
          <span>{error}</span>
          <button
            className="ux-button tertiary"
            type="button"
            onClick={() => setAttempt((current) => current + 1)}
          >
            Retry
          </button>
        </div>
      ) : null}
      {preview !== null ? (
        <NativeCardPreview text={preview} />
      ) : error ? null : (
        <p className="delivery-progress-line" role="status">
          Loading exact solver card preview…
        </p>
      )}
      {evidence ? (
        <details className="ux-disclosure">
          <summary>Exact source and technical details</summary>
          <dl className="evidence-grid">
            <dt>Source type</dt>
            <dd>
              {evidence.source.kind === "neutral_material"
                ? "Neutral Material"
                : "Material Model"}
            </dd>
            <dt>Source ID</dt>
            <dd>{evidence.source.id}</dd>
            <dt>Source revision</dt>
            <dd>{evidence.source.revisionId}</dd>
          </dl>
        </details>
      ) : null}
    </section>
  );
}

function configurableValueText(value: ConfigurableRecordValue): string {
  if (value.data_type === "number")
    return `${value.original_value} ${value.original_unit_string || ""}`.trim();
  if (value.data_type === "integer" || value.data_type === "boolean")
    return String(value.value);
  if (
    value.data_type === "text" ||
    value.data_type === "date" ||
    value.data_type === "discrete"
  )
    return value.value;
  if (value.data_type === "record_reference") return "Related Record";
  return `${value.data_type === "curve" ? "Curve" : "File"} artifact`;
}

function domainKindLabel(kind: string | null | undefined): string {
  const labels: Record<string, string> = {
    material: "Material",
    material_state: "Material state",
    specimen: "Specimen",
    test_run: "Test run",
    test_data: "Test Data",
    processing_output: "Processing Output",
    material_model: "Selected Material Model",
    neutral_material: "Neutral Material",
    solver_card: "Solver Card",
    neutral_solver_card: "Solver Card",
    release: "Released record",
  };
  return kind ? (labels[kind] ?? "Related record") : "Related record";
}

function CardTable({
  config,
  material,
  cards,
  onNavigate,
}: {
  config: ApiConfig;
  material: MaterialResponse;
  cards: SolverCardSummary[];
  onNavigate: (path: string) => void;
}) {
  if (!cards.length)
    return (
      <div className="ux-empty compact">
        <strong>No native card is available.</strong>
        <p>
          Create one from the selected source data below, or continue the
          selected material in Modeling.
        </p>
      </div>
    );
  return (
    <table className="ux-table cae-card-table">
      <thead>
        <tr>
          <th>Solver</th>
          <th>Card</th>
          <th>Format</th>
          <th>Delivery</th>
        </tr>
      </thead>
      <tbody>
        {cards.map((card) => (
          <tr key={card.id}>
            <td>
              <strong>{card.solver}</strong>
            </td>
            <td title={card.label}>{card.label}</td>
            <td>Native ASCII {card.extension}</td>
            <td>
              <div className="card-table-actions">
                <SolverCardAction
                  config={config}
                  card={card}
                  material={deliveryMaterial(material)}
                  onNavigate={onNavigate}
                  directClassName="ux-button"
                  reviewClassName="ux-button"
                  includePreview
                />
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MaterialDetailPage({
  config,
  materialId,
  activeTab,
  onNavigate,
  exactPin,
}: Props & {
  materialId: string;
  activeTab: MaterialTab;
  exactPin?: MaterialRevisionPin;
}) {
  const [experience, setExperience] = useState<MaterialExperience | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const experiencePromise = exactPin
      ? loadPinnedMaterialExperience(config, materialId, exactPin, true)
      : getMaterialDetail(config, materialId).then((detail) =>
          loadMaterialExperience(config, detail.data.material, true),
        );
    void experiencePromise
      .then((result) => {
        if (!active) return;
        setExperience(result);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(messageFor(cause));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    config,
    materialId,
    exactPin?.materialRevisionId,
    exactPin?.recordId,
    exactPin?.recordRevisionId,
  ]);

  useEffect(() => {
    const material = experience?.detail.material;
    const selectedRevision =
      exactPin && experience?.catalogRecord
        ? experience.catalogRecord.current_revision
        : material?.current_revision;
    publishWorkspaceStatus({
      selection: material ? (activeTab === "curves" ? "Curves" : "Material") : "Material record",
      revision: selectedRevision
        ? `r${selectedRevision.revision_no}`
        : "Loading revision",
      jobs: "No active job",
      warnings: error ? "1 workspace error" : "0 warnings",
      connection: error ? "degraded" : "online",
    });
  }, [activeTab, error, exactPin, experience]);

  if (loading)
    return (
      <div className="ux-page">
        <div className="material-detail-shell">
          <p className="loading-state">Loading material…</p>
        </div>
      </div>
    );
  if (error || !experience)
    return (
      <div className="ux-page">
        <div className="material-detail-shell">
          <div className="ux-notice error" role="alert">
            {error ?? "Material not found."}
          </div>
          <button
            className="ux-button"
            type="button"
            onClick={() => onNavigate(materialsReturnPath())}
          >
            Back to Materials
          </button>
        </div>
      </div>
    );

  const material = experience.detail.material;
  const content = material.current_revision.content;
  const recordContent = experience.catalogRecord?.current_revision.content;
  const displayName = recordContent?.name ?? content.name;
  const displayCode = recordContent?.external_key ?? content.material_code;
  const displayDescription = recordContent?.description ?? content.description;
  const selectedRevision =
    exactPin && experience.catalogRecord
      ? experience.catalogRecord.current_revision
      : material.current_revision;
  const propertySet = currentProperty(experience);
  const property = propertySet?.current_revision.content;
  const catalogRoot = experience.graph?.root ?? null;
  // A direct header action is unambiguous only when this exact Material
  // revision owns one card.  With multiple bound cards, keep all identities
  // visible in the Cards tab instead of selecting a solver or first item by
  // inference.
  const soleCard = experience.cards.length === 1 ? experience.cards[0] : null;
  const neutralMaterial = neutralMaterialBinding(experience);
  const relatedLinks = directRelatedRecords(
    experience.graph,
    catalogRoot?.record_id,
    catalogRoot?.record_revision_id,
  );
  const modelingContext = exactModelingContext(
    experience.graph,
    experience.detail.states,
  );
  const representativeResponse = experience.representativeResponse;
  const activePath = materialDetailPath(materialId, activeTab, exactPin);
  const navigateDetail = (path: string): void => {
    if (!exactPin || !path.startsWith(`/materials/${materialId}`)) {
      onNavigate(path);
      return;
    }
    const query = materialPinQuery(exactPin);
    onNavigate(`${path}${path.includes("?") ? "&" : "?"}${query}`);
  };
  const navigator = (
    <aside className="materials-left-pane" aria-label="Materials Browse Tree">
      <div className="workspace-back-row">
        <button
          className="ux-button tertiary"
          type="button"
          onClick={() => onNavigate(materialsReturnPath())}
        >
          <EngineeringIcon name="back" /> <span>Results</span>
        </button>
        <strong>Browse</strong>
      </div>
      <Suspense
        fallback={<p className="loading-state">Loading Browse tree…</p>}
      >
        <MaterialsBrowseTree
          config={config}
          publishedOnly
          requestedRecord={catalogRoot}
          onSelectRecord={(_record, _graph) => undefined}
          onOpenRecord={(record) =>
            onNavigate(
              exactRecordPath(record.record_id, record.current_revision.id),
            )
          }
        />
      </Suspense>
    </aside>
  );

  function acceptCreatedCard(card: SolverCardSummary): void {
    setExperience((current) =>
      current ? { ...current, cards: [...current.cards, card] } : current,
    );
    navigateDetail(`/materials/${materialId}/cards/${card.id}`);
  }

  const datasheet = (
    <div className="material-detail-shell">
      <header className="material-detail-header">
        <div>
          <h1>{displayName}</h1>
          {displayDescription?.trim() ? <p>{displayDescription}</p> : null}
          {activeTab !== "curves" ? (
            <div className="material-detail-meta">
              <span>Code {displayCode ?? "—"}</span>
              <span>{content.material_family ?? content.material_class}</span>
            </div>
          ) : null}
        </div>
        <div className="card-action-row">
          {soleCard ? (
            <SolverCardAction
              config={config}
              card={soleCard}
              material={deliveryMaterial(material)}
              onNavigate={navigateDetail}
            />
          ) : experience.cards.length > 1 ? (
            <button
              className="ux-button primary"
              type="button"
              onClick={() => navigateDetail(`/materials/${materialId}/cards`)}
            >
              View solver cards
            </button>
          ) : neutralMaterial ? (
            <button
              className="ux-button primary"
              type="button"
              onClick={() => navigateDetail(`/materials/${materialId}/cards`)}
            >
              Create card
            </button>
          ) : modelingFamily(material) ? (
            <button
              className="ux-button primary"
              type="button"
              onClick={() =>
                startModeling(material, onNavigate, modelingContext.materialState)
              }
            >
              Start Modeling
            </button>
          ) : (
            <p className="ux-notice" role="status">
              Modeling is not supported for this family.
            </p>
          )}
          <ReviewRequestAction
            config={config}
            subject={{
              aggregateType: "catalog.material",
              aggregateId: material.material_id,
              revisionId: material.current_revision.id,
              manifestSha256: material.current_revision.content_hash,
              classification: material.current_revision.classification,
              lifecycleState: material.current_revision.lifecycle_state,
            }}
          />
        </div>
      </header>
      <nav className="ux-tabs" role="tablist" aria-label="Material detail">
        <input type="hidden" value={activePath} readOnly />
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className="ux-tab"
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() =>
              onNavigate(materialDetailPath(materialId, tab.id, exactPin))
            }
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <section className="material-tab-panel" role="tabpanel">
        {activeTab === "overview" ? (
          <>
            <div className="overview-grid">
              <div>
                <section className="overview-section">
                  <div className="detail-section-heading">
                    <h2>Key properties</h2>
                    <button
                      className="ux-button tertiary"
                      type="button"
                      onClick={() =>
                        onNavigate(
                          materialDetailPath(
                            materialId,
                            "properties",
                            exactPin,
                          ),
                        )
                      }
                    >
                      All properties
                    </button>
                  </div>
                  <dl className="overview-property-list">
                    <div>
                      <dt>Density</dt>
                      <dd>
                        {formatDensity(property?.density_kg_per_m3)}
                      </dd>
                    </div>
                    <div>
                      <dt>Young’s modulus</dt>
                      <dd>
                        {formatPressure(property?.youngs_modulus_pa)}
                      </dd>
                    </div>
                    <div>
                      <dt>Yield strength</dt>
                      <dd>
                        {formatPressure(property?.yield_stress_pa)}
                      </dd>
                    </div>
                    <div>
                      <dt>Poisson ratio</dt>
                      <dd>{property?.poisson_ratio ?? "—"}</dd>
                    </div>
                  </dl>
                </section>
                <div
                  className={`overview-data-grid${representativeResponse ? "" : " conditions-only"}`}
                >
                  {representativeResponse ? (
                    <section className="overview-section">
                      <div className="detail-section-heading">
                        <h2>True stress–plastic strain response</h2>
                        <button
                          className="ux-button tertiary"
                          type="button"
                          onClick={() =>
                            onNavigate(
                              materialDetailPath(
                                materialId,
                                "curves",
                                exactPin,
                              ),
                            )
                          }
                        >
                          All curves
                        </button>
                      </div>
                      <div className="material-overview-response-cluster">
                        <RepresentativeCurve
                          points={representativeResponse.points}
                        />
                        <ResponsePointsTable
                          points={representativeResponse.points}
                        />
                      </div>
                    </section>
                  ) : null}
                  <section className="overview-section">
                    <h2>Applicable conditions and material states</h2>
                    <dl className="condition-summary">
                      <div>
                        <dt>Temperature</dt>
                        <dd>
                          {formatApplicabilityRange(
                            property?.applicability.temperature_min_k,
                            property?.applicability.temperature_max_k,
                            "K",
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>Strain rate</dt>
                        <dd>
                          {formatApplicabilityRange(
                            property?.applicability.strain_rate_min_per_s,
                            property?.applicability.strain_rate_max_per_s,
                            "/s",
                          )}
                        </dd>
                      </div>
                      {experience.detail.states.slice(0, 2).map((state) => (
                        <div key={state.material_state_id}>
                          <dt>State</dt>
                          <dd>{state.current_revision.content.name}</dd>
                          <dt>Manufacturing route</dt>
                          <dd>
                            {state.current_revision.content.manufacturing_route ??
                              "—"}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                </div>
              </div>
              <aside>
                <h2>Available solver cards</h2>
                <SolverAvailability
                  config={config}
                  cards={experience.cards}
                  materialId={materialId}
                  onNavigate={navigateDetail}
                />
                <button
                  className="ux-button tertiary"
                  type="button"
                  onClick={() => onNavigate(browsePath(experience))}
                >
                  Open exact source record
                </button>
              </aside>
            </div>
            <section
              className="material-linked-data"
              aria-label="Related data"
            >
              <div className="detail-section-heading">
                <div>
                  <h2 id="material-linked-data-title">Related data</h2>
                </div>
                <span className="ux-meta">
                  Revision r{selectedRevision.revision_no}
                </span>
              </div>
              {relatedLinks.length ? (
                <RelatedExactRecordList
                  items={relatedLinks}
                  onNavigate={onNavigate}
                />
              ) : (
                <p className="ux-meta">No directly linked data.</p>
              )}
            </section>
          </>
        ) : null}
        {activeTab === "properties" ? (
          <>
            <div className="detail-section-heading">
              <h2>Engineering properties</h2>
            </div>
            {property ? (
              <table className="ux-table">
                <thead>
                  <tr>
                    <th>Property</th>
                    <th>Value</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Density</td>
                    <td>{formatDensity(property.density_kg_per_m3)}</td>
                    <td>
                      {property.density_source.reference ?? "Material record"}
                    </td>
                  </tr>
                  <tr>
                    <td>Young’s modulus</td>
                    <td>{formatPressure(property.youngs_modulus_pa)}</td>
                    <td>
                      {property.youngs_modulus_source.reference ??
                        "Material record"}
                    </td>
                  </tr>
                  <tr>
                    <td>Poisson ratio</td>
                    <td>{property.poisson_ratio}</td>
                    <td>
                      {property.poisson_ratio_source.reference ??
                        "Material record"}
                    </td>
                  </tr>
                  <tr>
                    <td>Yield strength</td>
                    <td>{formatPressure(property.yield_stress_pa)}</td>
                    <td>
                      {property.yield_stress_source?.reference ??
                        "Material record"}
                    </td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <div className="ux-empty">No material values are available.</div>
            )}
            {catalogRoot ? (
              <MaterialDatasheetProjection
                config={config}
                tableId={catalogRoot.table_id}
                recordId={catalogRoot.record_id}
                revisionId={exactPin?.recordRevisionId}
                mode="properties"
              />
            ) : null}
            <section
              className="material-linked-data compact"
              aria-label="Related data"
            >
              <div className="detail-section-heading">
                <div>
                  <h2 id="property-linked-data-title">Related data</h2>
                </div>
                <span className="ux-meta">
                  Revision r{selectedRevision.revision_no}
                </span>
              </div>
              {relatedLinks.length ? (
                <RelatedExactRecordList
                  items={relatedLinks}
                  onNavigate={onNavigate}
                />
              ) : (
                <p className="ux-meta">No directly linked data.</p>
              )}
            </section>
          </>
        ) : null}
        {activeTab === "curves" ? (
          <>
            {catalogRoot ? (
              <MaterialDatasheetProjection
                config={config}
                tableId={catalogRoot.table_id}
                recordId={catalogRoot.record_id}
                revisionId={exactPin?.recordRevisionId}
                mode="curves"
                onNavigate={onNavigate}
                modelingContext={modelingContext}
              />
            ) : null}
            <table className="ux-table" aria-label="Modeling inputs">
              <thead>
                <tr>
                  <th>Modeling input</th>
                  <th>Type</th>
                  <th>Use</th>
                </tr>
              </thead>
              <tbody>
                {(experience.graph?.nodes ?? [])
                  .flatMap((node) =>
                    nodeBindings(node)
                      .filter((binding) =>
                        [
                          "test_data",
                          "processing_output",
                          "material_model",
                        ].includes(binding.kind),
                      )
                      .map((binding) => ({ node, binding })),
                  )
                  .map(({ node, binding }) => (
                    <tr
                      key={`${node.record_id}:${node.record_revision_id}:${binding.kind}:${binding.object_id}:${binding.revision_id}`}
                    >
                      <td>
                        {binding.workbench_path ? (
                          <a href={binding.workbench_path}>{node.name}</a>
                        ) : (
                          node.name
                        )}
                      </td>
                      <td>{domainKindLabel(binding.kind)}</td>
                      <td>
                        {binding.kind === "test_data"
                          ? "Measured test input"
                          : binding.kind === "processing_output"
                            ? "Processed curve"
                            : "Fitted response"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <section
              className="material-linked-data compact"
              aria-label="Related data"
            >
              <div className="detail-section-heading">
                <h2 id="curve-linked-data-title">Exact source records</h2>
                <span className="ux-meta">
                  Revision r{selectedRevision.revision_no}
                </span>
              </div>
              {relatedLinks.length ? (
                <RelatedExactRecordList
                  items={relatedLinks}
                  onNavigate={onNavigate}
                />
              ) : (
                <p className="ux-meta">No directly linked source data.</p>
              )}
            </section>
          </>
        ) : null}
        {activeTab === "cards" ? (
          <>
            <div className="detail-section-heading">
              <div>
                <h2>CAE Cards</h2>
                <p>
                  Cards with unchanged values can download directly. Cards with
                  delivery notes open a review before download; values the
                  solver cannot represent remain unavailable.
                </p>
              </div>
            </div>
            <CardTable
              config={config}
              material={material}
              cards={experience.cards}
              onNavigate={navigateDetail}
            />
            {neutralMaterial ? (
              <NeutralCardCreationPanel
                config={config}
                neutralMaterialId={neutralMaterial.object_id}
                neutralMaterialRevisionId={neutralMaterial.revision_id}
                materialName={content.name}
                materialCode={content.material_code}
                existingCards={experience.cards}
                onCreated={acceptCreatedCard}
              />
            ) : !experience.cards.length && modelingFamily(material) ? (
              <button
                className="ux-button primary"
                type="button"
                onClick={() =>
                  startModeling(
                    material,
                    onNavigate,
                    modelingContext.materialState,
                  )
                }
              >
                Start Modeling
              </button>
            ) : null}
          </>
        ) : null}
        {activeTab === "evidence" ? (
          <>
            <div className="detail-section-heading">
              <div>
                <h2>Linked records</h2>
              </div>
              <button
                className="ux-button"
                type="button"
                onClick={() => onNavigate(browsePath(experience))}
              >
                Open exact datasheet
              </button>
            </div>
            <div className="evidence-overview">
              <section>
                {relatedLinks.length ? (
                  <table className="ux-table">
                    <thead>
                      <tr>
                        <th>Relation</th>
                        <th>Target record</th>
                        <th>Type</th>
                        <th>Exact revision</th>
                      </tr>
                    </thead>
                    <tbody>
                      {relatedLinks.map((related) => (
                        <tr key={related.id}>
                          <td>{related.label}</td>
                          <td title={related.endpoint.name}>
                            {related.endpoint.domain_binding?.workbench_path ? (
                              <a
                                href={
                                  related.endpoint.domain_binding.workbench_path
                                }
                              >
                                {related.endpoint.name}
                              </a>
                            ) : (
                              related.endpoint.name
                            )}
                          </td>
                          <td>
                            {domainKindLabel(
                              related.endpoint.domain_binding?.kind,
                            )}
                          </td>
                          <td>r{related.endpoint.revision_no}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="ux-meta">
                    No related records are visible in the current view.
                  </p>
                )}
              </section>
            </div>
            <details className="ux-disclosure full-lineage">
              <summary>Full lineage</summary>
              <div className="ux-disclosure-body">
                <table className="ux-table">
                  <thead>
                    <tr>
                      <th>Record</th>
                      <th>Role</th>
                      <th>Revision</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(experience.graph?.nodes ?? [])
                      .flatMap((node) =>
                        nodeBindings(node).map((binding) => ({
                          node,
                          binding,
                        })),
                      )
                      .map(({ node, binding }) => (
                        <tr
                          key={`${node.record_id}:${node.record_revision_id}:${binding.kind}:${binding.object_id}:${binding.revision_id}`}
                        >
                          <td title={node.name}>
                            {binding.workbench_path ? (
                              <a href={binding.workbench_path}>{node.name}</a>
                            ) : (
                              node.name
                            )}
                          </td>
                          <td>{domainKindLabel(binding.kind)}</td>
                          <td>r{node.revision_no}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </details>
            {catalogRoot ? (
              <MaterialDatasheetProjection
                config={config}
                tableId={catalogRoot.table_id}
                recordId={catalogRoot.record_id}
                revisionId={exactPin?.recordRevisionId}
                mode="evidence"
              />
            ) : null}
            <details className="ux-disclosure">
              <summary>Technical revision and provenance identifiers</summary>
              <dl className="evidence-grid">
                <dt>Property source</dt>
                <dd>{sourceLabel(experience)}</dd>
                <dt>Material ID</dt>
                <dd>{material.material_id}</dd>
                <dt>Aggregate ID</dt>
                <dd>{material.current_revision.aggregate_id}</dd>
                <dt>Full revision ID</dt>
                <dd>{material.current_revision.id}</dd>
                <dt>Content hash</dt>
                <dd>{material.current_revision.content_hash}</dd>
                <dt>Classification</dt>
                <dd>{material.current_revision.classification}</dd>
                <dt>Change reason</dt>
                <dd>{material.current_revision.change_reason}</dd>
                <dt>Recorded by</dt>
                <dd>{material.current_revision.provenance.recorded_by}</dd>
              </dl>
            </details>
          </>
        ) : null}
      </section>
    </div>
  );
  return (
    <div className="ux-page materials-page materials-datasheet-page">
      <ResizableSplitPane
        id="cmp-materials-datasheet"
        navigator={navigator}
        main={datasheet}
        navigatorLabel="navigator"
      />
    </div>
  );
}

export function ExactRecordDatasheetPage({
  config,
  recordId,
  revisionId,
  onNavigate,
}: Props & { recordId: string; revisionId: string }) {
  const [record, setRecord] =
    useState<ConfigurableCatalogRecordResponse | null>(null);
  const [revisions, setRevisions] = useState<
    ConfigurableCatalogRecordResponse["current_revision"][]
  >([]);
  const [graph, setGraph] = useState<CatalogWorkflowGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [processingOutput, setProcessingOutput] =
    useState<ExactProcessingOutput | null>(null);
  const [processingLoading, setProcessingLoading] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [processingAttempt, setProcessingAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void getConfigurableCatalogRecord(config, recordId)
      .then(async (head) => {
        const [revisionResult] = await Promise.all([
          listConfigurableCatalogRecordRevisions(config, recordId),
        ]);
        const exact = revisionResult.data.items.find(
          (item) => item.id === revisionId,
        );
        if (!exact)
          throw new Error(
            "The requested immutable record revision does not exist.",
          );
        // Materials exact datasheets are a published surface.  Keep the private
        // Administration record route separate; a missing/invalidated approved
        // projection must fail closed before rendering any values here.
        const exactGraph = (
          await getCatalogWorkflowGraph(config, recordId, revisionId, 6, true)
        ).data;
        if (!active) return;
        setRecord({ ...head.data, current_revision: exact });
        setRevisions(revisionResult.data.items);
        setGraph(exactGraph);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(messageFor(cause));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [attempt, config, recordId, revisionId]);

  const rootBinding = graph ? nodeBindings(graph.root)[0] : undefined;
  const rootBindingKind = rootBinding?.kind;
  const recordType = graph ? relatedRecordTypeLabel(graph.root) : "Record";
  const semanticHeaderKinds = new Set([
    "test_data",
    "processing_output",
    "material_model",
    "neutral_material",
    "solver_card",
    "neutral_solver_card",
  ]);
  const usesSemanticHeader = rootBindingKind
    ? semanticHeaderKinds.has(rootBindingKind)
    : false;
  const semanticPageTitle = rootBindingKind === "solver_card" ||
    rootBindingKind === "neutral_solver_card"
    ? "Solver Card"
    : graph?.root.data_category === "simulation_data"
      ? "Simulation Data"
      : recordType;

  useEffect(() => {
    let active = true;
    if (rootBindingKind !== "processing_output" || !rootBinding) {
      setProcessingOutput(null);
      setProcessingError(null);
      setProcessingLoading(false);
      return () => {
        active = false;
      };
    }
    setProcessingLoading(true);
    setProcessingError(null);
    void loadExactProcessingOutput(
      config,
      rootBinding.object_id,
      rootBinding.revision_id,
    ).then((value) => {
      if (!active) return;
      setProcessingOutput(value);
      setProcessingLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setProcessingOutput(null);
      setProcessingError(messageFor(cause));
      setProcessingLoading(false);
    });
    return () => {
      active = false;
    };
  }, [config, processingAttempt, rootBinding?.object_id, rootBinding?.revision_id, rootBindingKind]);

  useEffect(() => {
    publishWorkspaceStatus({
      selection: record
        ? (usesSemanticHeader ? semanticPageTitle : "Exact record")
        : "Exact catalog record",
      revision: record
        ? `r${record.current_revision.revision_no} · exact`
        : "Loading revision",
      jobs: "No active job",
      warnings: error || processingError ? "1 workspace error" : "0 warnings",
      connection: error || processingError ? "degraded" : "online",
    });
  }, [error, processingError, record, semanticPageTitle, usesSemanticHeader]);

  const related = directRelatedRecords(graph, recordId, revisionId);
  const modelingContext = exactModelingContext(graph);
  const solverCard = graph ? solverCardSummaryFromEndpoint(graph.root) : null;
  const hasCurveValues = Boolean(
    record?.current_revision.content.values.some(
      (value) => value.data_type === "curve",
    ),
  );
  const navigator = (
    <aside className="materials-left-pane" aria-label="Materials Browse Tree">
      <div className="workspace-back-row">
        <button
          className="ux-button tertiary"
          type="button"
          onClick={() => onNavigate(materialsReturnPath())}
        >
          <EngineeringIcon name="back" /> <span>Results</span>
        </button>
        <strong>Browse</strong>
      </div>
      <Suspense
        fallback={<p className="loading-state">Loading Browse tree…</p>}
      >
        <MaterialsBrowseTree
          config={config}
          publishedOnly
          requestedRecord={graph?.root ?? null}
          onSelectRecord={(_nextRecord, _nextGraph) => undefined}
          onOpenRecord={(nextRecord) =>
            onNavigate(
              exactRecordPath(
                nextRecord.record_id,
                nextRecord.current_revision.id,
              ),
            )
          }
        />
      </Suspense>
    </aside>
  );
  const main = (
    <section
      className="exact-record-datasheet material-tab-panel"
      aria-labelledby="exact-record-title"
    >
      {loading && record ? (
        <div className="datasheet-loading-line">Loading exact revision…</div>
      ) : null}
      {loading && !record ? (
        <p className="loading-state">Loading exact record revision…</p>
      ) : null}
      {error ? (
        <div className="ux-notice error" role="alert">
          {error}
          <button
            className="ux-button tertiary"
            type="button"
            onClick={() => setAttempt((current) => current + 1)}
          >
            Retry
          </button>
        </div>
      ) : null}
      {record ? (
        <>
          <header className="exact-record-header">
            <div>
              <h1 id="exact-record-title">
                {usesSemanticHeader
                  ? semanticPageTitle
                  : record.current_revision.content.name}
              </h1>
              {!usesSemanticHeader && record.current_revision.content.description ? (
                <p>{record.current_revision.content.description}</p>
              ) : null}
              {!usesSemanticHeader ? (
                <div className="material-detail-meta">
                  <span>Type {recordType}</span>
                  <span>
                    Code {record.current_revision.content.external_key ?? "—"}
                  </span>
                </div>
              ) : null}
            </div>
            <div className="exact-revision-mark">
              <strong>r{record.current_revision.revision_no}</strong>
              <span>Immutable</span>
            </div>
            <ExactSourceActions
              config={config}
              recordId={record.record_id}
              revisionId={revisionId}
            />
          </header>
          {!record.current_revision.content.values.length &&
          !solverCard &&
          rootBindingKind !== "processing_output" &&
          rootBindingKind !== "test_data" ? (
            <div className="ux-empty">
              <strong>No values in this revision.</strong>
            </div>
          ) : null}
          {rootBindingKind === "test_data" && rootBinding ? (
            <ExactTestDataDetail
              config={config}
              documentId={rootBinding.object_id}
              revisionId={rootBinding.revision_id}
            />
          ) : rootBindingKind === "processing_output" ? (
            processingLoading ? (
              <p className="loading-state">Loading exact Processing Output…</p>
            ) : processingError ? (
              <div className="ux-notice error" role="alert">
                {processingError}
                <button
                  className="ux-button tertiary"
                  type="button"
                  onClick={() => setProcessingAttempt((current) => current + 1)}
                >
                  Retry
                </button>
              </div>
            ) : processingOutput ? (
              <ProcessingOutputDetail data={processingOutput} />
            ) : null
          ) : solverCard ? (
            <ExactSolverCardDelivery config={config} card={solverCard} />
          ) : rootBindingKind !== "test_data" ? (
            <MaterialDatasheetProjection
              config={config}
              tableId={record.table_id}
              recordId={record.record_id}
              revisionId={revisionId}
              mode="properties"
              recordKind={rootBindingKind}
            />
          ) : null}
          {rootBindingKind === "test_data" ? (
            <MaterialDatasheetProjection
              config={config}
              tableId={record.table_id}
              recordId={record.record_id}
              revisionId={revisionId}
              mode="properties"
              recordKind={rootBindingKind}
            />
          ) : null}
          {hasCurveValues ? (
            <MaterialDatasheetProjection
              config={config}
              tableId={record.table_id}
              recordId={record.record_id}
              revisionId={revisionId}
              mode="curves"
              onNavigate={onNavigate}
              modelingContext={modelingContext}
            />
          ) : null}
          <section
            className="exact-record-related"
            aria-labelledby="exact-record-related-title"
          >
            <div className="detail-section-heading">
              <h2 id="exact-record-related-title">
                {rootBindingKind === "processing_output" ? "Linked records" : "Related data"}
              </h2>
            </div>
            {related.length ? (
              rootBindingKind === "processing_output" ? (
                <ExactLinkedRecordTable items={related} onNavigate={onNavigate} />
              ) : (
                <RelatedExactRecordList items={related} onNavigate={onNavigate} />
              )
            ) : (
              <p className="ux-meta">No directly linked records.</p>
            )}
          </section>
          <details className="ux-disclosure">
            <summary>Revision history and technical details</summary>
            <h3>Revisions</h3>
            <ul className="related-record-list">
              {revisions.map((revision) => (
                <li key={revision.id}>
                  <button
                    type="button"
                    aria-current={
                      revision.id === revisionId ? "page" : undefined
                    }
                    onClick={() =>
                      onNavigate(exactRecordPath(recordId, revision.id))
                    }
                  >
                    <span>Revision {revision.revision_no}</span>
                    <small>{revision.change_reason}</small>
                  </button>
                </li>
              ))}
            </ul>
            <dl className="evidence-grid">
              <dt>Record ID</dt>
              <dd>{record.record_id}</dd>
              <dt>Revision ID</dt>
              <dd>{record.current_revision.id}</dd>
              <dt>Content hash</dt>
              <dd>{record.current_revision.content_hash}</dd>
              <dt>Classification</dt>
              <dd>{record.current_revision.classification}</dd>
              <dt>Change reason</dt>
              <dd>{record.current_revision.change_reason}</dd>
            </dl>
            {processingOutput ? <ProcessingOutputEvidence data={processingOutput} /> : null}
          </details>
        </>
      ) : null}
    </section>
  );
  return (
    <div className="ux-page materials-page materials-datasheet-page">
      <ResizableSplitPane
        id="cmp-materials-exact-record"
        navigator={navigator}
        main={main}
        navigatorLabel="navigator"
      />
    </div>
  );
}

export function SolverCardPreviewPage({
  config,
  materialId,
  cardId,
  exactPin,
  onNavigate,
}: Props & {
  materialId: string;
  cardId: string;
  exactPin?: MaterialRevisionPin;
}) {
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
      : getMaterialDetail(config, materialId).then((detail) =>
          loadMaterialExperience(config, detail.data.material),
        );
    void experiencePromise
      .then(async (result) => {
        const found = result.cards.find((item) => item.id === cardId);
        if (!found)
          throw new Error(
            "The requested solver card is not linked to this material revision.",
          );
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
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(messageFor(cause));
        void recordActivityRecovery(
          config,
          {
            kind: "solver_card",
            path: `/materials/${materialId}/cards/${cardId}`,
            materialId,
            solverCardId: cardId,
          },
          "failed",
          messageFor(cause),
        );
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    cardId,
    config,
    exactPin?.materialRevisionId,
    exactPin?.recordId,
    exactPin?.recordRevisionId,
    materialId,
  ]);

  async function downloadCard(): Promise<void> {
    if (!card || !material || !evidence || evidence.disposition === "blocked")
      return;
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
  const linkedResponse = blocked
    ? null
    : trueStressPlasticStrainResponseFromNativeCard(preview);
  const linkedResponsePoints = linkedResponse?.points ?? [];
  const downloadDisabled =
    loading ||
    downloading ||
    !preview ||
    !evidence ||
    blocked ||
    (reviewRequired && !acknowledged);
  const downloadLabel = blocked
    ? "Download blocked"
    : downloading
      ? "Preparing…"
      : `Download ${card?.extension ?? "card"}`;
  const downloadConsequence =
    loading || !evidence
      ? "Delivery checks are loading before this card can be downloaded."
      : blocked
        ? "This card cannot be downloaded because some values are not supported by the selected solver."
        : reviewRequired
          ? "Review the highlighted delivery note, then acknowledge it to enable this download."
          : "Delivery checks pass for this target, so this download is ready.";

  return (
    <div className="ux-page">
      <div className="card-preview-shell">
        <header className="card-preview-header">
          <div>
            <button
              className="ux-button tertiary"
              type="button"
              onClick={() =>
                onNavigate(materialDetailPath(materialId, "cards", exactPin))
              }
            >
              <EngineeringIcon name="back" /> <span>CAE Cards</span>
            </button>
            <h1>
              {card?.label ??
                material?.current_revision.content.name ??
                "Card preview"}
            </h1>
          </div>
          <div className="card-action-row">
            <ReviewRequestAction
              config={config}
              subject={
                evidence
                  ? {
                      aggregateType: evidence.reviewAggregateType,
                      aggregateId: card?.id ?? cardId,
                      revisionId: evidence.reviewRevisionId,
                      manifestSha256: evidence.reviewContentHash,
                      classification: evidence.reviewClassification,
                      lifecycleState: evidence.lifecycleState,
                    }
                  : null
              }
            />
          </div>
        </header>
        {error ? (
          <div className="ux-notice error" role="alert">
            {error}
          </div>
        ) : null}
        <div className="card-preview-content">
          <section
            className={`native-preview${linkedResponsePoints.length >= 2 ? " has-linked-response" : ""}`}
            aria-label="Native card and linked response"
          >
            <NativeCardPreview
              text={loading ? "Loading native card preview…" : taskPreview}
            />
            <LinkedResponseGraph points={linkedResponsePoints} />
          </section>
          <aside className="card-preview-actions">
            <h2>{card?.solver ?? "Solver"}</h2>
            {evidence ? (
              <dl className="delivery-card-properties">
                <div>
                  <dt>Target</dt>
                  <dd>
                    {evidence.target.solver} {evidence.target.version}
                  </dd>
                </div>
                <div>
                  <dt>Format</dt>
                  <dd>Native {card?.extension ?? "card"}</dd>
                </div>
                <div>
                  <dt>Unit system</dt>
                  <dd>{evidence.target.unit_system.replaceAll("_", " · ")}</dd>
                </div>
              </dl>
            ) : (
              <p className="delivery-progress-line">Loading delivery checks…</p>
            )}
            <div className="card-preview-delivery-command">
              <button
                className="ux-button primary"
                type="button"
                disabled={downloadDisabled}
                onClick={() => void downloadCard()}
              >
                {downloadLabel}
              </button>
              <p
                className={`card-preview-delivery-consequence${blocked ? " blocked" : reviewRequired ? " review" : ""}`}
                {...(blocked ? { role: "alert" } : {})}
              >
                {downloadConsequence}
              </p>
            </div>
            {evidence ? (
              <>
                <h3>Delivery check</h3>
                <MappingStatusList
                  items={evidence.mappingItems}
                  reviewAcknowledgement={
                    reviewRequired ? (
                      <label className="delivery-acknowledgement">
                        <input
                          name="mapping-delivery-acknowledgement"
                          type="checkbox"
                          checked={acknowledged}
                          onChange={(event) =>
                            setAcknowledged(event.target.checked)
                          }
                        />
                        I reviewed the delivery notes before downloading this
                        card.
                      </label>
                    ) : undefined
                  }
                />
              </>
            ) : null}
            <button
              className="ux-button"
              type="button"
              onClick={() =>
                onNavigate(materialDetailPath(materialId, "overview", exactPin))
              }
            >
              Return to material
            </button>
            <details className="ux-disclosure">
              <summary>Advanced mapping evidence</summary>
              <p className="ux-meta">
                The mapping report records exact, transformed, approximated,
                ignored, and unsupported fields. The native file retains its
                provenance headers.
              </p>
              <button
                className="ux-button"
                type="button"
                disabled={!evidence}
                onClick={() => void downloadMapping()}
              >
                Download mapping report
              </button>
              <dl className="evidence-grid">
                <dt>Card ID</dt>
                <dd>{cardId}</dd>
                <dt>Exact revision</dt>
                <dd>{card?.revisionId ?? "Loading…"}</dd>
                <dt>Card checksum</dt>
                <dd>{evidence?.cardSha256 ?? "Recorded after generation"}</dd>
                <dt>Mapping checksum</dt>
                <dd>{evidence?.mappingReportSha256 ?? "Loading…"}</dd>
              </dl>
            </details>
          </aside>
        </div>
      </div>
    </div>
  );
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
