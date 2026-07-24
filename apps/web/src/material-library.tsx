import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  getCatalogWorkflowGraph,
  getConfigurableCatalogRecord,
  getMaterialDetail,
  listBulkExportCandidates,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogRecordRevisions,
  listMaterials,
  resolveCatalogDomainRevision,
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
  PropertySetResponse,
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
  solver: string;
  source: string;
  status: string;
  yieldMin: string;
  yieldMax: string;
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
  if (state.solver) params.set("solver", state.solver);
  // Provider/evidence, release/validation, and condition-aware property facets
  // are intentionally not serialized until a governed server projection exists.
  if (state.sortKey !== "name") params.set("sort", state.sortKey);
  if (state.sortDirection !== "ascending") params.set("direction", state.sortDirection);
  if (state.leftMode !== "filters") params.set("mode", state.leftMode);
  if (state.selectedId) params.set("selected", state.selectedId);
  if (state.offset) params.set("offset", String(state.offset));
  const search = params.toString();
  return search ? `/materials?${search}` : "/materials";
}

function initialNavigatorMode(): "filters" | "browse" | "subsets" {
  const mode = materialSearchParams().get("mode");
  return mode === "browse" || mode === "subsets" ? mode : "filters";
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
  const [solver, setSolver] = useState(() => materialSearchParams().get("solver") ?? "");
  const [source, setSource] = useState(() => materialSearchParams().get("source") ?? "");
  const [status, setStatus] = useState(() => materialSearchParams().get("status") ?? "");
  const [yieldMin, setYieldMin] = useState(() => materialSearchParams().get("yieldMin") ?? "");
  const [yieldMax, setYieldMax] = useState(() => materialSearchParams().get("yieldMax") ?? "");
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
    setSolver(params.get("solver") ?? "");
    setSource(params.get("source") ?? "");
    setStatus(params.get("status") ?? "");
    setYieldMin(params.get("yieldMin") ?? "");
    setYieldMax(params.get("yieldMax") ?? "");
    setSortKey(nextSort === "material_class" ? nextSort : "name");
    setSortDirection(params.get("direction") === "descending" ? "descending" : "ascending");
    setLeftMode(nextMode === "browse" || nextMode === "subsets" ? nextMode : "filters");
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
    window.history.replaceState(window.history.state, "", materialsPath({ query, materialClass, solver, source, status, yieldMin, yieldMax, sortKey, sortDirection, offset, leftMode, selectedId }));
  }, [leftMode, materialClass, offset, query, selectedId, solver, sortDirection, sortKey, source, status, yieldMax, yieldMin]);

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

  useEffect(() => {
    const handleCommand = (event: Event) => {
      const command = (event as CustomEvent<{ command?: string }>).detail?.command;
      if (command === "materials:search") {
        setLeftMode("filters");
      } else if (command === "materials:browse") {
        openBrowseTree(undefined);
      } else if (command === "materials:subsets") {
        setLeftMode("subsets");
      }
    };
    window.addEventListener("cmp:workspace-command", handleCommand);
    return () => window.removeEventListener("cmp:workspace-command", handleCommand);
  }, []);

  function submit(event: FormEvent): void {
    event.preventDefault();
    setLeftMode("filters");
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
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, solver, source, status, yieldMin, yieldMax, sortKey, sortDirection, offset, leftMode, selectedId }));
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
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, solver, source, status, yieldMin, yieldMax, sortKey, sortDirection, offset, leftMode, selectedId: materialId }));
    onNavigate(`/materials/${materialId}`);
  }

  const navigator = <aside className="materials-left-pane" aria-label={leftMode === "filters" ? "Material filters" : "Materials Browse Tree"}>
    {leftMode === "filters" ? <div className="materials-filters">
      <label className="ux-field">Material class<select className="ux-select" name="material-class" value={materialClass} onChange={(event) => { setMaterialClass(event.target.value); setOffset(0); }}><option value="">All classes</option>{familyFacets.map((facet) => <option key={facet.material_class} value={facet.material_class}>{`${facet.material_class} (${facet.count.toLocaleString()})`}</option>)}</select></label>
      <div className="material-query-gap" role="status"><strong>Provider</strong><span>Not available in the governed material query.</span></div>
      <div className="material-query-gap" role="status"><strong>Evidence source</strong><span>Not available in the governed material query.</span></div>
      <div className="material-query-gap" role="status"><strong>Revision status</strong><span>Shown per revision in results; no release facet is defined.</span></div>
      <div className="material-query-gap" role="status"><strong>Validation availability</strong><span>Not configured in the material query.</span></div>
      <p className="ux-meta">Property ranges, including Yield, remain hidden until the server supplies quantity definition, condition, unit, and source revision.</p>
      <button className="ux-button tertiary" type="button" onClick={() => { setMaterialClass(""); setOffset(0); }}>Clear class</button>
    </div> : <MaterialsBrowseTree config={config} subsetMode={leftMode === "subsets"} requestedRecord={requestedRecord} onSelectRecord={selectBrowseRecord} onOpenRecord={openExactRecord}/>}
  </aside>;

  const results = <section className="materials-results" aria-labelledby="material-results-title" aria-busy={loading}>
    <div className="materials-results-header"><div><h2 id="material-results-title">Materials</h2><p className="ux-meta">{loading ? "Loading…" : `${totalCount ? `${offset + 1}–${Math.min(offset + materials.length, totalCount)} of ` : ""}${new Intl.NumberFormat().format(totalCount)} matches`}</p></div><span className="ux-meta">Server-scoped query · Enter opens · select up to 3 to compare</span></div>
    {error ? <div className="ux-notice error" role="alert">{error}<button className="ux-button tertiary" type="button" onClick={() => setLoadAttempt((current) => current + 1)}>Retry</button></div> : null}
    {!loading && !error && !materials.length ? <div className="ux-empty"><strong>No materials match this server query.</strong><p>Clear the class or try a material grade, code, or family.</p></div> : null}
    {comparedMaterials.length > 1 ? <div className="material-compare-strip"><div><strong>Comparing {comparedMaterials.length} materials</strong><span className="ux-meta">Open comparison to inspect exact property revisions.</span></div>{comparedMaterials.map((material) => <dl key={material.material_id}><dt>{material.current_revision.content.name}</dt><dd>{material.current_revision.content.material_family ?? material.current_revision.content.material_class}</dd><dd>r{material.current_revision.revision_no}</dd></dl>)}<button className="ux-button tertiary" type="button" onClick={() => setCompareIds(new Set())}>Clear comparison</button></div> : null}
    {browseSelection ? <div className="browse-selection-bar"><span><strong>{browseSelection.record.current_revision.content.name}</strong><small>{browseSelection.graph.root.domain_binding?.kind?.replaceAll("_", " ") ?? "Catalog record"} · exact revision {browseSelection.record.current_revision.revision_no}</small></span><button className="ux-button tertiary" type="button" onClick={() => openExactRecord(browseSelection.record)}>Open datasheet</button></div> : null}
    <div className="materials-result-table-wrap"><table className="materials-result-table" aria-label="Material results"><colgroup>{Object.entries(columnWidths).map(([key, width]) => <col key={key} style={{ width }} />)}</colgroup><thead><tr><th>Compare<EngineeringColumnResizeHandle label="Compare" width={columnWidths.compare} min={60} max={100} onChange={(width) => setColumnWidths((current) => ({ ...current, compare: width }))}/></th><th aria-sort={sortKey === "name" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("name")}>Material</button><EngineeringColumnResizeHandle label="Material" width={columnWidths.material} min={160} max={360} onChange={(width) => setColumnWidths((current) => ({ ...current, material: width }))}/></th><th aria-sort={sortKey === "material_class" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("material_class")}>Material class</button><EngineeringColumnResizeHandle label="Material class" width={columnWidths.materialClass} min={110} max={260} onChange={(width) => setColumnWidths((current) => ({ ...current, materialClass: width }))}/></th><th>Summary<EngineeringColumnResizeHandle label="Summary" width={columnWidths.summary} min={140} max={320} onChange={(width) => setColumnWidths((current) => ({ ...current, summary: width }))}/></th><th>Revision status<EngineeringColumnResizeHandle label="Revision status" width={columnWidths.revisionStatus} min={90} max={160} onChange={(width) => setColumnWidths((current) => ({ ...current, revisionStatus: width }))}/></th></tr></thead><tbody>
      {materials.map((material) => { const content = material.current_revision.content; const materialIdentity = `${content.name} · ${content.material_code ?? "No grade code"}`; return <tr key={material.material_id} className={selectedId === material.material_id ? "selected" : ""} tabIndex={0} aria-selected={selectedId === material.material_id} onClick={() => setSelectedId(material.material_id)} onDoubleClick={() => openMaterial(material.material_id)} onKeyDown={(event) => { if (event.key === "Enter") openMaterial(material.material_id); }}><td><input type="checkbox" aria-label={`Compare ${content.name}`} checked={compareIds.has(material.material_id)} disabled={!compareIds.has(material.material_id) && compareIds.size >= 3} onClick={(event) => event.stopPropagation()} onChange={() => toggleCompare(material.material_id)}/></td><td><button className="material-result-name" type="button" aria-current={selectedId === material.material_id ? "true" : undefined} title={materialIdentity} onClick={() => setSelectedId(material.material_id)}><span>{content.name}</span><small>{content.material_code ?? "No grade code"}</small></button></td><td title={content.material_class}>{content.material_class}</td><td>{content.description ?? "Not projected"}</td><td>{material.current_revision.lifecycle_state}</td></tr>; })}
    </tbody></table></div>
    {!loading && totalCount > materials.length ? <nav className="materials-pagination" aria-label="Material result pages"><button className="ux-button tertiary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span className="ux-meta">Rows {totalCount ? offset + 1 : 0}–{Math.min(offset + materials.length, totalCount)}</span><button className="ux-button tertiary" type="button" disabled={offset + materials.length >= totalCount} onClick={() => setOffset(offset + 50)}>Next</button></nav> : null}
  </section>;

  const context = <aside className="materials-selection" aria-live="polite">
    {selected ? <>
      <div className="selection-heading"><div><p className="ux-kicker">Selected material</p><h2 title={selected.current_revision.content.name}>{selected.current_revision.content.name}</h2></div><span className="ux-meta">{selected.current_revision.content.material_code ?? "No material code"}</span></div>
      <p>{selected.current_revision.content.description ?? "No summary is available."}</p>
      <dl className="selection-context"><dt>Material class</dt><dd>{selected.current_revision.content.material_class}</dd><dt>Provider</dt><dd>Not projected</dd><dt>Evidence source</dt><dd>Not projected</dd><dt>Revision status</dt><dd>{selected.current_revision.lifecycle_state}</dd><dt>Validation availability</dt><dd>Not configured</dd><dt>Revision</dt><dd>r{selected.current_revision.revision_no}</dd></dl>
      <p className="ux-meta">Open the exact datasheet for governed properties, conditions, evidence, and card readiness.</p>
      <div className="selection-delivery-command">
        {modelingFamily(selected) ? <button className="ux-button primary" type="button" onClick={() => startModeling(selected, onNavigate)}>Start Modeling</button> : <p className="ux-notice" role="status">Modeling is not supported for this family.</p>}
        <button className="ux-button" type="button" onClick={() => openMaterial(selected.material_id)}>Open material</button>
        <button className="ux-button tertiary" type="button" onClick={() => openBrowseTree(undefined)}>Show in Browse Tree</button>
      </div>
    </> : <div className="ux-empty"><strong>Select a material</strong><p>Key properties and solver-card availability will appear here.</p></div>}
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
  if (!cards.length) return <div className="ux-empty compact"><strong>No native card is available.</strong><p>Create one from the exact Neutral Material below, or continue the selected material in Modeling.</p></div>;
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
    <header className="material-detail-header"><div><h1>{content.name}</h1><div className="material-detail-meta"><span>{content.material_code ?? "No grade code"}</span><span>{content.material_family ?? content.material_class}</span><span>{sourceLabel(experience)}</span><span>{material.current_revision.lifecycle_state}</span></div></div><div className="card-action-row">{preferredCard ? <SolverCardAction config={config} card={preferredCard} material={deliveryMaterial(material)} onNavigate={onNavigate}/> : neutralMaterial ? <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards`)}>Create card</button> : modelingFamily(material) ? <button className="ux-button primary" type="button" onClick={() => startModeling(material, onNavigate)}>Start Modeling</button> : <p className="ux-notice" role="status">Modeling is not supported for this family.</p>}</div></header>
    <nav className="ux-tabs" role="tablist" aria-label="Material detail"><input type="hidden" value={activePath} readOnly />{tabs.map((tab) => <button key={tab.id} className="ux-tab" type="button" role="tab" aria-selected={activeTab === tab.id} onClick={() => onNavigate(tab.id === "overview" ? `/materials/${materialId}` : `/materials/${materialId}/${tab.id}`)}>{tab.label}</button>)}</nav>
    <section className="material-tab-panel" role="tabpanel">
      {activeTab === "overview" ? <div className="overview-grid"><div><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Engineering summary</p><h2>Key properties</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/properties`)}>All properties</button></div><div className="overview-property-grid"><div><span>Density</span><strong>{formatDensity(property?.density_kg_per_m3)}</strong></div><div><span>Young’s modulus</span><strong>{formatPressure(property?.youngs_modulus_pa)}</strong></div><div><span>Yield strength</span><strong>{formatPressure(property?.yield_stress_pa)}</strong></div><div><span>Poisson ratio</span><strong>{property?.poisson_ratio ?? "—"}</strong></div></div></section><div className="overview-data-grid"><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Representative curve</p><h2>Linked material response</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/curves`)}>All curves</button></div><RepresentativeCurve points={experience.representativeCurve}/></section><section className="overview-section"><p className="ux-kicker">Application conditions</p><h2>Material states</h2><dl className="condition-summary"><dt>Temperature</dt><dd>{property?.applicability.temperature_min_k ?? "—"}–{property?.applicability.temperature_max_k ?? "—"} K</dd><dt>Strain rate</dt><dd>{property?.applicability.strain_rate_min_per_s ?? "—"}–{property?.applicability.strain_rate_max_per_s ?? "—"} /s</dd></dl>{experience.detail.states.slice(0, 2).map((state) => <p className="condition-state" key={state.material_state_id}><strong>{state.current_revision.content.name}</strong><span>{state.current_revision.content.manufacturing_route ?? "Route not specified"}</span></p>)}</section></div></div><aside><p className="ux-kicker">CAE delivery</p><h2>Ready solver cards</h2><p>Choose a native format. The primary Download action above uses the preferred available solver.</p><SolverAvailability cards={experience.cards}/><div className="solver-preview-links">{experience.cards.map((card) => <button key={card.id} type="button" onClick={() => onNavigate(`/materials/${materialId}/cards/${card.id}`)}>Preview {card.solver} {card.extension}</button>)}</div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(browsePath(experience))}>Related records in Browse Tree</button></aside></div> : null}
      {activeTab === "properties" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Normalized values</p><h2>Engineering properties</h2></div></div>{property ? <table className="ux-table"><thead><tr><th>Property</th><th>Value</th><th>Quantity semantics</th><th>Source</th></tr></thead><tbody><tr><td>Density</td><td>{formatDensity(property.density_kg_per_m3)}</td><td>mass density</td><td>{property.density_source.kind}</td></tr><tr><td>Young’s modulus</td><td>{formatPressure(property.youngs_modulus_pa)}</td><td>elastic modulus</td><td>{property.youngs_modulus_source.kind}</td></tr><tr><td>Poisson ratio</td><td>{property.poisson_ratio}</td><td>dimensionless ratio</td><td>{property.poisson_ratio_source.kind}</td></tr><tr><td>Yield strength</td><td>{formatPressure(property.yield_stress_pa)}</td><td>stress</td><td>{property.yield_stress_source?.kind ?? "—"}</td></tr></tbody></table> : <div className="ux-empty">No typed property set is available.</div>}<p className="ux-meta">Normalized units are shown here. Original unit text and exact source revisions remain preserved in Evidence.</p>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} mode="properties"/> : null}</> : null}
      {activeTab === "curves" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Test and model data</p><h2>Curves</h2><p>Review available workflow data in the persistent Modeling graph.</p></div><button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Open in Modeling</button></div>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} mode="curves"/> : null}<table className="ux-table"><thead><tr><th>Related data</th><th>Type</th><th>Use</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).filter((node) => ["test_data", "processing_output", "material_model"].includes(node.domain_binding?.kind ?? "")).map((node) => <tr key={node.record_id}><td>{node.name}</td><td>{node.domain_binding?.kind.replaceAll("_", " ")}</td><td>{node.domain_binding?.kind === "test_data" ? "Observed input" : node.domain_binding?.kind === "processing_output" ? "Processed curve" : "Fitted response"}</td></tr>)}</tbody></table></> : null}
      {activeTab === "cards" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Solver delivery</p><h2>CAE Cards</h2><p>Exact mappings download directly. Approximated or ignored mappings require review; unsupported mappings remain blocked.</p></div></div><CardTable config={config} material={material} cards={experience.cards} onNavigate={onNavigate}/>{neutralMaterial ? <NeutralCardCreationPanel config={config} neutralMaterialId={neutralMaterial.object_id} neutralMaterialRevisionId={neutralMaterial.revision_id} materialName={content.name} materialCode={content.material_code} existingCards={experience.cards} onCreated={acceptCreatedCard}/> : !experience.cards.length && modelingFamily(material) ? <button className="ux-button primary" type="button" onClick={() => startModeling(material, onNavigate)}>Start Modeling</button> : null}</> : null}
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
    .filter((line) => !line.startsWith("# CMP material-model-revision") && !line.startsWith("# CMP mapping-report-sha256"))
    .join("\n");

  const reviewRequired = evidence?.disposition === "review";
  const blocked = evidence?.disposition === "blocked";
  const downloadDisabled = loading || downloading || !preview || !evidence || blocked || (reviewRequired && !acknowledged);
  const downloadLabel = blocked ? "Download blocked" : downloading ? "Preparing…" : `Download ${card?.extension ?? "card"}`;

  return <div className="ux-page"><div className="card-preview-shell">
    <header className="card-preview-header">
      <div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards`)}>← CAE Cards</button><p className="ux-kicker">{card?.solver ?? "Solver card"} · Native ASCII</p><h1>{card?.label ?? material?.current_revision.content.name ?? "Card preview"}</h1><p>Inspect the native syntax and mapping states tied to this exact card revision.</p></div>
      <button className="ux-button primary" type="button" disabled={downloadDisabled} onClick={() => void downloadCard()}>{downloadLabel}</button>
    </header>
    {error ? <div className="ux-notice error" role="alert">{error}</div> : null}
    <div className="card-preview-content">
      <pre className="native-card-preview" aria-label="Native solver card preview">{loading ? "Loading native card preview…" : taskPreview}</pre>
      <aside className="card-preview-actions">
        <p className="ux-kicker">Delivery properties</p>
        <h2>{card?.solver ?? "Solver"}</h2>
        {evidence ? <dl className="delivery-card-properties"><dt>Target</dt><dd>{evidence.target.solver} {evidence.target.version}</dd><dt>Unit system</dt><dd>{evidence.target.unit_system.replaceAll("_", " · ")}</dd><dt>Card revision</dt><dd>r{evidence.revisionNo}</dd><dt>Lifecycle</dt><dd>{evidence.lifecycleState}</dd><dt>Material ID</dt><dd>{evidence.solverMaterialId}</dd></dl> : <p className="delivery-progress-line">Loading mapping evidence…</p>}
        {evidence ? <><h3>Mapping status</h3><MappingStatusList items={evidence.mappingItems}/></> : null}
        {reviewRequired ? <label className="delivery-acknowledgement"><input name="mapping-delivery-acknowledgement" type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)}/>I reviewed every approximated or ignored mapping state.</label> : null}
        {blocked ? <p className="ux-notice error" role="alert">Delivery is blocked because this exact revision contains unsupported solver mappings.</p> : null}
        <button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${materialId}`)}>Return to material</button>
        <details className="ux-disclosure"><summary>Advanced mapping evidence</summary><p className="ux-meta">The mapping report records exact, transformed, approximated, ignored, and unsupported fields. The native file retains its provenance headers.</p><button className="ux-button" type="button" disabled={!evidence} onClick={() => void downloadMapping()}>Download mapping report</button><dl className="evidence-grid"><dt>Card ID</dt><dd>{cardId}</dd><dt>Exact revision</dt><dd>{card?.revisionId ?? "Loading…"}</dd><dt>Card checksum</dt><dd>{evidence?.cardSha256 ?? "Recorded after generation"}</dd><dt>Mapping checksum</dt><dd>{evidence?.mappingReportSha256 ?? "Loading…"}</dd></dl></details>
      </aside>
    </div>
  </div></div>;
}

export function ActivityPage({ onNavigate }: Pick<Props, "onNavigate">) {
  const modelingSession = useMemo(() => loadModelingSession(), []);
  const deliveryActivities = useMemo(() => loadDeliveryActivities(), []);
  useEffect(() => publishWorkspaceStatus({ selection: "Current workspace activity", revision: "Current user", jobs: "No active job", warnings: "0 warnings", connection: "online" }), []);
  const resumePath = modelingSession ? `/modeling?stage=${modelingSession.workspace.activeStage}&family=${modelingSession.materialFamily}` : "/modeling";
  const stageLabel = modelingSession ? `${modelingSession.workspace.activeStage[0].toUpperCase()}${modelingSession.workspace.activeStage.slice(1)}` : null;
  return <div className="ux-page"><div className="activity-shell"><div className="activity-content"><h2>Current workspace activity</h2>
    {deliveryActivities.length ? <section className="activity-delivery-section"><h3>Recent solver-card delivery</h3><ul className="activity-list">{deliveryActivities.map((activity) => <li key={`${activity.action}:${activity.cardId}`} data-testid="recent-solver-card-activity"><span><strong>{activity.action === "download" ? "Downloaded" : "Previewed"} · {activity.cardLabel}</strong><small className="ux-meta">{activity.materialLabel} · {activity.solver} {activity.extension} · exact revision retained · {new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(activity.occurredAt))}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${activity.materialId}/cards/${activity.cardId}`)}>Open card</button></li>)}</ul></section> : null}
    {modelingSession ? <ul className="activity-list"><li data-testid="recent-modeling-session"><span><strong>{modelingSession.material?.label ?? modelingSession.objective ?? "Material modeling session"}</strong><small className="ux-meta">{`${modelingSession.materialFamily} · ${stageLabel} · ${modelingSession.testData ? `${modelingSession.testData.label} r${modelingSession.testData.revisionNo}` : "No exact Test Data"} · ${modelingSession.workspace.selectedDocumentIds.length} selected curves`}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(resumePath)}>{`Resume ${stageLabel}`}</button></li></ul> : <section className="activity-empty-state" role="status" aria-label="No recent Modeling session"><div><strong>No recent Modeling session</strong><p>This browser has no local Data, Process, Fit, or Export session to resume.</p></div><button className="ux-button" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button></section>}
    <ul className="activity-list activity-destinations"><li><span><strong>Reviews and releases</strong><small className="ux-meta">Open the governed review workspace. Activity attention and queue integration remain pending.</small></span><button className="ux-button" type="button" onClick={() => onNavigate("/jobs-reviews")}>Open review workspace</button></li></ul><details className="ux-disclosure"><summary>Advanced jobs and export packages</summary><p>Inspect batch attempts, technical diagnostics, and checksum-verifiable bulk packages.</p><button className="ux-button" type="button" onClick={() => onNavigate("/exports")}>Open export packages</button></details>
  </div></div></div>;
}
