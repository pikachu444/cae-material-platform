import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  downloadNeutralHyperelasticMappingReport,
  downloadNeutralHyperelasticSolverCard,
  getCatalogWorkflowGraph,
  getConfigurableCatalogRecord,
  getMaterialDetail,
  listBulkExportCandidates,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogRecordRevisions,
  listMaterials,
  previewNeutralHyperelasticSolverCard,
  resolveCatalogDomainRevision,
  type ApiConfig,
} from "./api";
import type {
  CatalogWorkflowGraphResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableAttributeResponse,
  ConfigurableLinkEndpoint,
  ConfigurableRecordValue,
  MaterialDetail,
  MaterialResponse,
  PropertySetResponse,
} from "./types";
import { MaterialsBrowseTree } from "./materials-browse-tree";
import { MaterialDatasheetProjection } from "./material-datasheet-projection";
import { publishWorkspaceCommandState, publishWorkspaceStatus } from "./design/application-shell";
import { ResizableSplitPane } from "./design/resizable-split-pane";
import { EngineeringColumnResizeHandle } from "./design/engineering-column-resize-handle";
import { loadModelingSession } from "./modeling-session-context";

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

interface SolverCardSummary {
  id: string;
  revisionId: string;
  label: string;
  solver: "Abaqus" | "OpenRadioss" | "Solver";
  extension: ".inp" | ".rad" | ".txt";
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
  sortKey: "name" | "family" | "yield" | "cards";
  sortDirection: "ascending" | "descending";
  leftMode: "filters" | "browse" | "subsets";
  selectedId: string;
}

function materialsPath(state: MaterialsLocationState): string {
  const params = new URLSearchParams();
  if (state.query) params.set("q", state.query);
  if (state.materialClass) params.set("family", state.materialClass);
  if (state.solver) params.set("solver", state.solver);
  if (state.source) params.set("source", state.source);
  if (state.status) params.set("status", state.status);
  if (state.yieldMin) params.set("yieldMin", state.yieldMin);
  if (state.yieldMax) params.set("yieldMax", state.yieldMax);
  if (state.sortKey !== "name") params.set("sort", state.sortKey);
  if (state.sortDirection !== "ascending") params.set("direction", state.sortDirection);
  if (state.leftMode !== "filters") params.set("mode", state.leftMode);
  if (state.selectedId) params.set("selected", state.selectedId);
  const search = params.toString();
  return search ? `/materials?${search}` : "/materials";
}

function initialNavigatorMode(): "filters" | "browse" | "subsets" {
  const mode = materialSearchParams().get("mode");
  return mode === "browse" || mode === "subsets" ? mode : "filters";
}

function initialSortKey(): "name" | "family" | "yield" | "cards" {
  const key = materialSearchParams().get("sort");
  return key === "family" || key === "yield" || key === "cards" ? key : "name";
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
    if (binding?.kind !== "neutral_solver_card") return [];
    return [{
      id: binding.object_id,
      revisionId: binding.revision_id,
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
      const preview = await previewNeutralHyperelasticSolverCard(config, preferred.id);
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
  const [sortKey, setSortKey] = useState<"name" | "family" | "yield" | "cards">(initialSortKey);
  const [sortDirection, setSortDirection] = useState<"ascending" | "descending">(() => materialSearchParams().get("direction") === "descending" ? "descending" : "ascending");
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [leftMode, setLeftMode] = useState<"filters" | "browse" | "subsets">(initialNavigatorMode);
  const [requestedRecord, setRequestedRecord] = useState<ConfigurableLinkEndpoint | null>(storedBrowseRecord);
  const [browseSelection, setBrowseSelection] = useState<BrowseSelection | null>(null);
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [experience, setExperience] = useState<Record<string, MaterialExperience>>({});
  const [selectedId, setSelectedId] = useState(() => materialSearchParams().get("selected") ?? "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [columnWidths, setColumnWidths] = useState({ compare: 68, material: 220, family: 150, source: 170, yield: 110, cards: 110 });

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
    setSortKey(nextSort === "family" || nextSort === "yield" || nextSort === "cards" ? nextSort : "name");
    setSortDirection(params.get("direction") === "descending" ? "descending" : "ascending");
    setLeftMode(nextMode === "browse" || nextMode === "subsets" ? nextMode : "filters");
    setSelectedId(params.get("selected") ?? "");
  }, [locationSearch]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void listMaterials(config, query, materialClass || undefined)
      .then(async (result) => {
        if (!active) return;
        const items = [...result.data.items].sort((a, b) => a.current_revision.content.name.localeCompare(b.current_revision.content.name));
        setMaterials(items);
        setTotalCount(result.data.total_count);
        setSelectedId((current) => items.some((item) => item.material_id === current) ? current : items[0]?.material_id ?? "");
        const settled = await Promise.allSettled(items.map((item) => loadMaterialExperience(config, item)));
        if (!active) return;
        const next: Record<string, MaterialExperience> = {};
        settled.forEach((resultItem, index) => {
          if (resultItem.status === "fulfilled") next[items[index].material_id] = resultItem.value;
        });
        setExperience(next);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setMaterials([]);
        setTotalCount(0);
        setExperience({});
        setSelectedId("");
        setLoading(false);
        setError(messageFor(cause));
      });
    return () => { active = false; };
  }, [config, loadAttempt, materialClass, query]);

  useEffect(() => {
    if (typeof window === "undefined" || window.location.pathname !== "/materials") return;
    window.history.replaceState(window.history.state, "", materialsPath({ query, materialClass, solver, source, status, yieldMin, yieldMax, sortKey, sortDirection, leftMode, selectedId }));
  }, [leftMode, materialClass, query, selectedId, solver, sortDirection, sortKey, source, status, yieldMax, yieldMin]);

  useEffect(() => {
    publishWorkspaceCommandState(`materials:${leftMode === "filters" ? "search" : leftMode}`);
  }, [leftMode]);

  const filtered = useMemo(() => materials.filter((material) => {
    const itemExperience = experience[material.material_id];
    const property = currentProperty(itemExperience)?.current_revision.content;
    const yieldMpa = property?.yield_stress_pa == null ? null : property.yield_stress_pa / 1e6;
    if (solver && !itemExperience?.cards.some((card) => card.solver === solver)) return false;
    if (source && sourceLabel(itemExperience) !== source) return false;
    if (status && material.current_revision.lifecycle_state !== status) return false;
    if (yieldMin && (yieldMpa === null || yieldMpa < Number(yieldMin))) return false;
    if (yieldMax && (yieldMpa === null || yieldMpa > Number(yieldMax))) return false;
    return true;
  }).sort((left, right) => {
    const leftExperience = experience[left.material_id];
    const rightExperience = experience[right.material_id];
    const leftProperty = currentProperty(leftExperience)?.current_revision.content;
    const rightProperty = currentProperty(rightExperience)?.current_revision.content;
    const values: Record<typeof sortKey, [string | number, string | number]> = {
      name: [left.current_revision.content.name, right.current_revision.content.name],
      family: [left.current_revision.content.material_family ?? left.current_revision.content.material_class, right.current_revision.content.material_family ?? right.current_revision.content.material_class],
      yield: [leftProperty?.yield_stress_pa ?? -1, rightProperty?.yield_stress_pa ?? -1],
      cards: [leftExperience?.cards.length ?? -1, rightExperience?.cards.length ?? -1],
    };
    const [leftValue, rightValue] = values[sortKey];
    const compared = typeof leftValue === "number" && typeof rightValue === "number" ? leftValue - rightValue : String(leftValue).localeCompare(String(rightValue));
    return sortDirection === "ascending" ? compared : -compared;
  }), [experience, materials, solver, sortDirection, sortKey, source, status, yieldMax, yieldMin]);

  const sourceOptions = useMemo(() => [...new Set(Object.values(experience).map((item) => sourceLabel(item)))].sort(), [experience]);
  const comparedMaterials = filtered.filter((material) => compareIds.has(material.material_id));

  useEffect(() => {
    if (filtered.length && !filtered.some((item) => item.material_id === selectedId)) setSelectedId(filtered[0]!.material_id);
  }, [filtered, selectedId]);

  const selected = filtered.find((item) => item.material_id === selectedId);
  const selectedExperience = selected ? experience[selected.material_id] : undefined;
  const selectedProperty = currentProperty(selectedExperience)?.current_revision.content;

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
        openBrowseTree(selectedExperience?.graph?.root);
      } else if (command === "materials:subsets") {
        setLeftMode("subsets");
      }
    };
    window.addEventListener("cmp:workspace-command", handleCommand);
    return () => window.removeEventListener("cmp:workspace-command", handleCommand);
  }, [selectedExperience]);

  function submit(event: FormEvent): void {
    event.preventDefault();
    setLeftMode("filters");
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
    if (materialBinding?.kind === "material" && materials.some((item) => item.material_id === materialBinding.object_id)) {
      setSelectedId(materialBinding.object_id);
    }
  }

  function openExactRecord(record: ConfigurableCatalogRecordResponse): void {
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, solver, source, status, yieldMin, yieldMax, sortKey, sortDirection, leftMode, selectedId }));
    onNavigate(`/materials/records/${record.record_id}/revisions/${record.current_revision.id}`);
  }

  function changeSort(next: typeof sortKey): void {
    if (next === sortKey) setSortDirection((current) => current === "ascending" ? "descending" : "ascending");
    else {
      setSortKey(next);
      setSortDirection("ascending");
    }
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
    window.sessionStorage.setItem(MATERIALS_RETURN_KEY, materialsPath({ query, materialClass, solver, source, status, yieldMin, yieldMax, sortKey, sortDirection, leftMode, selectedId: materialId }));
    onNavigate(`/materials/${materialId}`);
  }

  const navigator = <aside className="materials-left-pane" aria-label={leftMode === "filters" ? "Material filters" : "Materials Browse Tree"}>
    {leftMode === "filters" ? <div className="materials-filters">
      <label className="ux-field">Material class<select className="ux-select" name="material-family" value={materialClass} onChange={(event) => setMaterialClass(event.target.value)}><option value="">All classes</option><option value="metal">Metal</option><option value="polymer">Polymer</option><option value="elastomer">Elastomer</option><option value="composite">Composite</option><option value="ceramic">Ceramic</option></select></label>
      <label className="ux-field">Manufacturer / source<select className="ux-select" name="material-source" value={source} onChange={(event) => setSource(event.target.value)}><option value="">Any source</option>{sourceOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      <label className="ux-field">CAE card<select className="ux-select" name="solver-availability" value={solver} onChange={(event) => setSolver(event.target.value)}><option value="">Any availability</option><option value="Abaqus">Abaqus available</option><option value="OpenRadioss">OpenRadioss available</option></select></label>
      <label className="ux-field">Validation / release status<select className="ux-select" name="release-status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Any status</option><option value="draft">Draft / reference</option></select></label>
      <fieldset className="ux-field"><legend>Yield strength (MPa)</legend><div className="filter-range"><input className="ux-input" aria-label="Minimum yield strength" name="yield-minimum" autoComplete="off" type="number" value={yieldMin} onChange={(event) => setYieldMin(event.target.value)} placeholder="Min…"/><input className="ux-input" aria-label="Maximum yield strength" name="yield-maximum" autoComplete="off" type="number" value={yieldMax} onChange={(event) => setYieldMax(event.target.value)} placeholder="Max…"/></div></fieldset>
      <button className="ux-button tertiary" type="button" onClick={() => { setMaterialClass(""); setSource(""); setSolver(""); setStatus(""); setYieldMin(""); setYieldMax(""); }}>Clear filters</button>
    </div> : <MaterialsBrowseTree config={config} subsetMode={leftMode === "subsets"} requestedRecord={requestedRecord} onSelectRecord={selectBrowseRecord} onOpenRecord={openExactRecord}/>}
  </aside>;

  const results = <section className="materials-results" aria-labelledby="material-results-title" aria-busy={loading}>
    <div className="materials-results-header"><div><h2 id="material-results-title">Materials</h2><p className="ux-meta">{loading ? "Loading…" : `${filtered.length} shown · ${new Intl.NumberFormat().format(totalCount)} total`}</p></div><span className="ux-meta">Enter opens · select up to 3 to compare</span></div>
    {error ? <div className="ux-notice error" role="alert">{error}<button className="ux-button tertiary" type="button" onClick={() => setLoadAttempt((current) => current + 1)}>Retry</button></div> : null}
    {!loading && !error && !filtered.length ? <div className="ux-empty"><strong>No materials match these filters.</strong><p>Clear a filter or try a material grade, code, or family.</p></div> : null}
    {comparedMaterials.length > 1 ? <div className="material-compare-strip"><div><strong>Comparing {comparedMaterials.length} materials</strong><span className="ux-meta">Key normalized values</span></div>{comparedMaterials.map((material) => { const itemExperience = experience[material.material_id]; const property = currentProperty(itemExperience)?.current_revision.content; return <dl key={material.material_id}><dt>{material.current_revision.content.name}</dt><dd>{formatPressure(property?.yield_stress_pa)}</dd><dd>{formatDensity(property?.density_kg_per_m3)}</dd><dd>{itemExperience?.cards.length ?? 0} cards</dd></dl>; })}<button className="ux-button tertiary" type="button" onClick={() => setCompareIds(new Set())}>Clear comparison</button></div> : null}
    {browseSelection ? <div className="browse-selection-bar"><span><strong>{browseSelection.record.current_revision.content.name}</strong><small>{browseSelection.graph.root.domain_binding?.kind?.replaceAll("_", " ") ?? "Catalog record"} · exact revision {browseSelection.record.current_revision.revision_no}</small></span><button className="ux-button tertiary" type="button" onClick={() => openExactRecord(browseSelection.record)}>Open datasheet</button></div> : null}
    <div className="materials-result-table-wrap"><table className="materials-result-table" aria-label="Material results"><colgroup>{Object.entries(columnWidths).map(([key, width]) => <col key={key} style={{ width }} />)}</colgroup><thead><tr><th>Compare<EngineeringColumnResizeHandle label="Compare" width={columnWidths.compare} min={60} max={100} onChange={(width) => setColumnWidths((current) => ({ ...current, compare: width }))}/></th><th aria-sort={sortKey === "name" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("name")}>Material</button><EngineeringColumnResizeHandle label="Material" width={columnWidths.material} min={160} max={360} onChange={(width) => setColumnWidths((current) => ({ ...current, material: width }))}/></th><th aria-sort={sortKey === "family" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("family")}>Family</button><EngineeringColumnResizeHandle label="Family" width={columnWidths.family} min={110} max={260} onChange={(width) => setColumnWidths((current) => ({ ...current, family: width }))}/></th><th>Source<EngineeringColumnResizeHandle label="Source" width={columnWidths.source} min={120} max={320} onChange={(width) => setColumnWidths((current) => ({ ...current, source: width }))}/></th><th aria-sort={sortKey === "yield" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("yield")}>Yield</button><EngineeringColumnResizeHandle label="Yield" width={columnWidths.yield} min={90} max={180} onChange={(width) => setColumnWidths((current) => ({ ...current, yield: width }))}/></th><th aria-sort={sortKey === "cards" ? sortDirection : undefined}><button type="button" onClick={() => changeSort("cards")}>CAE cards</button><EngineeringColumnResizeHandle label="CAE cards" width={columnWidths.cards} min={90} max={180} onChange={(width) => setColumnWidths((current) => ({ ...current, cards: width }))}/></th></tr></thead><tbody>
      {filtered.map((material) => { const content = material.current_revision.content; const itemExperience = experience[material.material_id]; const property = currentProperty(itemExperience)?.current_revision.content; const materialIdentity = `${content.name} · ${content.material_code ?? "No grade code"}`; return <tr key={material.material_id} className={selectedId === material.material_id ? "selected" : ""} tabIndex={0} aria-selected={selectedId === material.material_id} onClick={() => setSelectedId(material.material_id)} onDoubleClick={() => openMaterial(material.material_id)} onKeyDown={(event) => { if (event.key === "Enter") openMaterial(material.material_id); }}><td><input type="checkbox" aria-label={`Compare ${content.name}`} checked={compareIds.has(material.material_id)} disabled={!compareIds.has(material.material_id) && compareIds.size >= 3} onClick={(event) => event.stopPropagation()} onChange={() => toggleCompare(material.material_id)}/></td><td><button className="material-result-name" type="button" aria-current={selectedId === material.material_id ? "true" : undefined} title={materialIdentity} onClick={() => setSelectedId(material.material_id)}><span>{content.name}</span><small>{content.material_code ?? "No grade code"}</small></button></td><td title={content.material_family ?? content.material_class}>{content.material_family ?? content.material_class}</td><td title={sourceLabel(itemExperience)}>{sourceLabel(itemExperience)}</td><td className="ux-numeric">{formatPressure(property?.yield_stress_pa)}</td><td>{itemExperience ? `${itemExperience.cards.length} cards` : loading ? "Checking…" : "Unavailable"}</td></tr>; })}
    </tbody></table></div>
  </section>;

  const context = <aside className="materials-selection" aria-live="polite">
    {selected ? <><div className="selection-heading"><div><p className="ux-kicker">Selected material</p><h2 title={selected.current_revision.content.name}>{selected.current_revision.content.name}</h2></div><span className="ux-meta">{selected.current_revision.content.material_code ?? "No material code"}</span></div><p>{selected.current_revision.content.description ?? "No summary is available."}</p><div className="selection-property-grid"><div><span>Density</span><strong>{formatDensity(selectedProperty?.density_kg_per_m3)}</strong></div><div><span>Young’s modulus</span><strong>{formatPressure(selectedProperty?.youngs_modulus_pa)}</strong></div><div><span>Yield strength</span><strong>{formatPressure(selectedProperty?.yield_stress_pa)}</strong></div><div><span>Poisson ratio</span><strong>{selectedProperty?.poisson_ratio ?? "—"}</strong></div></div><dl className="selection-context"><dt>Source</dt><dd>{sourceLabel(selectedExperience)}</dd><dt>Status</dt><dd>{selected.current_revision.lifecycle_state}</dd></dl><h3>CAE card availability</h3><SolverAvailability cards={selectedExperience?.cards ?? []}/><button className="ux-button primary" type="button" onClick={() => openMaterial(selected.material_id)}>Open material</button><button className="ux-button tertiary" type="button" onClick={() => openBrowseTree(selectedExperience?.graph?.root)}>Show in Browse Tree</button></> : <div className="ux-empty"><strong>Select a material</strong><p>Key properties and solver-card availability will appear here.</p></div>}
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

function CardTable({ materialId, cards, downloadingId, onNavigate, onDownload }: { materialId: string; cards: SolverCardSummary[]; downloadingId: string; onNavigate: (path: string) => void; onDownload: (card: SolverCardSummary) => void }) {
  if (!cards.length) return <div className="ux-empty"><strong>No native card is available.</strong><p>Open Modeling to process test data, review a model, and create a governed solver card.</p><button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button></div>;
  return <table className="ux-table cae-card-table"><thead><tr><th>Solver</th><th>Card</th><th>Format</th><th>Delivery</th></tr></thead><tbody>{cards.map((card) => <tr key={card.id}><td><strong>{card.solver}</strong></td><td title={card.label}>{card.label}</td><td>Native ASCII {card.extension}</td><td><div className="card-table-actions"><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards/${card.id}`)}>Preview</button><button className="ux-button" type="button" disabled={downloadingId === card.id} onClick={() => onDownload(card)}>{downloadingId === card.id ? "Preparing…" : `Download ${card.extension}`}</button></div></td></tr>)}</tbody></table>;
}

export function MaterialDetailPage({ config, materialId, activeTab, onNavigate }: Props & { materialId: string; activeTab: MaterialTab }) {
  const [experience, setExperience] = useState<MaterialExperience | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState("");
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
      jobs: downloadingId ? "Preparing solver card" : "No active job",
      warnings: error || actionError ? "1 workspace error" : "0 warnings",
      connection: error || actionError ? "degraded" : "online",
    });
  }, [actionError, downloadingId, error, experience]);

  if (loading) return <div className="ux-page"><div className="material-detail-shell"><p className="loading-state">Loading material…</p></div></div>;
  if (error || !experience) return <div className="ux-page"><div className="material-detail-shell"><div className="ux-notice error" role="alert">{error ?? "Material not found."}</div><button className="ux-button" type="button" onClick={() => onNavigate(materialsReturnPath())}>Back to Materials</button></div></div>;

  const material = experience.detail.material;
  const content = material.current_revision.content;
  const propertySet = currentProperty(experience);
  const property = propertySet?.current_revision.content;
  const catalogRoot = experience.graph?.root ?? null;
  const preferredCard = experience.cards.find((card) => card.solver === "OpenRadioss") ?? experience.cards[0] ?? null;
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

  async function downloadCard(card: SolverCardSummary): Promise<void> {
    setDownloadingId(card.id);
    setActionError(null);
    try {
      const result = await downloadNeutralHyperelasticSolverCard(config, card.id);
      triggerDownload(result.data.blob, result.data.filename);
    } catch (cause: unknown) {
      setActionError(messageFor(cause));
    } finally {
      setDownloadingId("");
    }
  }
  const datasheet = <div className="material-detail-shell">
    <header className="material-detail-header"><div><h1>{content.name}</h1><div className="material-detail-meta"><span>{content.material_code ?? "No grade code"}</span><span>{content.material_family ?? content.material_class}</span><span>{sourceLabel(experience)}</span><span>{material.current_revision.lifecycle_state}</span></div></div><div className="card-action-row">{preferredCard ? <><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards/${preferredCard.id}`)}>Preview {preferredCard.solver}</button><button className="ux-button primary" type="button" disabled={downloadingId === preferredCard.id} onClick={() => void downloadCard(preferredCard)}>{downloadingId === preferredCard.id ? "Preparing…" : `Download ${preferredCard.extension}`}</button></> : <button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button>}</div></header>
    <nav className="ux-tabs" role="tablist" aria-label="Material detail"><input type="hidden" value={activePath} readOnly />{tabs.map((tab) => <button key={tab.id} className="ux-tab" type="button" role="tab" aria-selected={activeTab === tab.id} onClick={() => onNavigate(tab.id === "overview" ? `/materials/${materialId}` : `/materials/${materialId}/${tab.id}`)}>{tab.label}</button>)}</nav>
    {actionError ? <div className="ux-notice error material-action-error" role="alert">{actionError}</div> : null}
    <section className="material-tab-panel" role="tabpanel">
      {activeTab === "overview" ? <div className="overview-grid"><div><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Engineering summary</p><h2>Key properties</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/properties`)}>All properties</button></div><div className="overview-property-grid"><div><span>Density</span><strong>{formatDensity(property?.density_kg_per_m3)}</strong></div><div><span>Young’s modulus</span><strong>{formatPressure(property?.youngs_modulus_pa)}</strong></div><div><span>Yield strength</span><strong>{formatPressure(property?.yield_stress_pa)}</strong></div><div><span>Poisson ratio</span><strong>{property?.poisson_ratio ?? "—"}</strong></div></div></section><div className="overview-data-grid"><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Representative curve</p><h2>Linked material response</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/curves`)}>All curves</button></div><RepresentativeCurve points={experience.representativeCurve}/></section><section className="overview-section"><p className="ux-kicker">Application conditions</p><h2>Material states</h2><dl className="condition-summary"><dt>Temperature</dt><dd>{property?.applicability.temperature_min_k ?? "—"}–{property?.applicability.temperature_max_k ?? "—"} K</dd><dt>Strain rate</dt><dd>{property?.applicability.strain_rate_min_per_s ?? "—"}–{property?.applicability.strain_rate_max_per_s ?? "—"} /s</dd></dl>{experience.detail.states.slice(0, 2).map((state) => <p className="condition-state" key={state.material_state_id}><strong>{state.current_revision.content.name}</strong><span>{state.current_revision.content.manufacturing_route ?? "Route not specified"}</span></p>)}</section></div></div><aside><p className="ux-kicker">CAE delivery</p><h2>Ready solver cards</h2><p>Choose a native format. The primary Download action above uses the preferred available solver.</p><SolverAvailability cards={experience.cards}/><div className="solver-preview-links">{experience.cards.map((card) => <button key={card.id} type="button" onClick={() => onNavigate(`/materials/${materialId}/cards/${card.id}`)}>Preview {card.solver} {card.extension}</button>)}</div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(browsePath(experience))}>Related records in Browse Tree</button></aside></div> : null}
      {activeTab === "properties" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Normalized values</p><h2>Engineering properties</h2></div></div>{property ? <table className="ux-table"><thead><tr><th>Property</th><th>Value</th><th>Quantity semantics</th><th>Source</th></tr></thead><tbody><tr><td>Density</td><td>{formatDensity(property.density_kg_per_m3)}</td><td>mass density</td><td>{property.density_source.kind}</td></tr><tr><td>Young’s modulus</td><td>{formatPressure(property.youngs_modulus_pa)}</td><td>elastic modulus</td><td>{property.youngs_modulus_source.kind}</td></tr><tr><td>Poisson ratio</td><td>{property.poisson_ratio}</td><td>dimensionless ratio</td><td>{property.poisson_ratio_source.kind}</td></tr><tr><td>Yield strength</td><td>{formatPressure(property.yield_stress_pa)}</td><td>stress</td><td>{property.yield_stress_source?.kind ?? "—"}</td></tr></tbody></table> : <div className="ux-empty">No typed property set is available.</div>}<p className="ux-meta">Normalized units are shown here. Original unit text and exact source revisions remain preserved in Evidence.</p>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} mode="properties"/> : null}</> : null}
      {activeTab === "curves" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Test and model data</p><h2>Curves</h2><p>Review available workflow data in the persistent Modeling graph.</p></div><button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Open in Modeling</button></div>{catalogRoot ? <MaterialDatasheetProjection config={config} tableId={catalogRoot.table_id} recordId={catalogRoot.record_id} mode="curves"/> : null}<table className="ux-table"><thead><tr><th>Related data</th><th>Type</th><th>Use</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).filter((node) => ["test_data", "processing_output", "material_model"].includes(node.domain_binding?.kind ?? "")).map((node) => <tr key={node.record_id}><td>{node.name}</td><td>{node.domain_binding?.kind.replaceAll("_", " ")}</td><td>{node.domain_binding?.kind === "test_data" ? "Observed input" : node.domain_binding?.kind === "processing_output" ? "Processed curve" : "Fitted response"}</td></tr>)}</tbody></table></> : null}
      {activeTab === "cards" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Solver delivery</p><h2>CAE Cards</h2><p>Preview native ASCII content or download the exact immutable artifact directly.</p></div></div><CardTable materialId={materialId} cards={experience.cards} downloadingId={downloadingId} onNavigate={onNavigate} onDownload={(card) => void downloadCard(card)}/></> : null}
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
  const [preview, setPreview] = useState("");
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void getMaterialDetail(config, materialId).then((detail) => loadMaterialExperience(config, detail.data.material)).then(async (result) => {
      const found = result.cards.find((item) => item.id === cardId) ?? null;
      const previewResult = await previewNeutralHyperelasticSolverCard(config, cardId);
      if (!active) return;
      setMaterial(result.detail.material);
      setCard(found);
      setPreview(previewResult.data);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
      setLoading(false);
    });
    return () => { active = false; };
  }, [cardId, config, materialId]);

  async function downloadCard(): Promise<void> {
    setDownloading(true);
    setError(null);
    try {
      const result = await downloadNeutralHyperelasticSolverCard(config, cardId);
      triggerDownload(result.data.blob, result.data.filename);
    } catch (cause: unknown) {
      setError(messageFor(cause));
    } finally {
      setDownloading(false);
    }
  }

  async function downloadMapping(): Promise<void> {
    try {
      const result = await downloadNeutralHyperelasticMappingReport(config, cardId);
      triggerDownload(result.data.blob, result.data.filename);
    } catch (cause: unknown) {
      setError(messageFor(cause));
    }
  }

  const taskPreview = preview
    .split("\n")
    .filter((line) => !line.startsWith("# CMP material-model-revision") && !line.startsWith("# CMP mapping-report-sha256"))
    .join("\n");

  return <div className="ux-page"><div className="card-preview-shell"><header className="card-preview-header"><div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards`)}>← CAE Cards</button><p className="ux-kicker">{card?.solver ?? "Solver card"} · Native ASCII</p><h1>{card?.label ?? material?.current_revision.content.name ?? "Card preview"}</h1><p>Inspect the generated solver syntax before downloading the immutable native artifact.</p></div><button className="ux-button primary" type="button" disabled={loading || downloading || !preview} onClick={() => void downloadCard()}>{downloading ? "Preparing…" : `Download ${card?.extension ?? "card"}`}</button></header>{error ? <div className="ux-notice error" role="alert">{error}</div> : null}<div className="card-preview-content"><pre className="native-card-preview" aria-label="Native solver card preview">{loading ? "Loading native card preview…" : taskPreview}</pre><aside className="card-preview-actions"><p className="ux-kicker">Delivery</p><h2>{card?.solver ?? "Solver"}</h2><p>The downloaded file is the exact released native artifact. Technical provenance headers remain in that file and are disclosed below.</p><button className="ux-button" type="button" onClick={() => onNavigate(`/materials/${materialId}`)}>Return to material</button><details className="ux-disclosure"><summary>Advanced mapping evidence</summary><p className="ux-meta">The mapping report records exact, transformed, approximated, ignored, and unsupported fields. The downloaded native file retains its exact provenance headers.</p><button className="ux-button" type="button" onClick={() => void downloadMapping()}>Download mapping report</button><dl className="evidence-grid"><dt>Card ID</dt><dd>{cardId}</dd><dt>Exact revision</dt><dd>{card?.revisionId ?? "Available in mapping evidence"}</dd></dl></details></aside></div></div></div>;
}

export function ActivityPage({ onNavigate }: Pick<Props, "onNavigate">) {
  const modelingSession = useMemo(() => loadModelingSession(), []);
  useEffect(() => publishWorkspaceStatus({ selection: "Current workspace activity", revision: "Current user", jobs: "No active job", warnings: "0 warnings", connection: "online" }), []);
  const resumePath = modelingSession ? `/modeling?stage=${modelingSession.workspace.activeStage}&family=${modelingSession.materialFamily}` : "/modeling";
  const stageLabel = modelingSession ? `${modelingSession.workspace.activeStage[0].toUpperCase()}${modelingSession.workspace.activeStage.slice(1)}` : null;
  return <div className="ux-page"><div className="activity-shell"><div className="activity-content"><h2>Current workspace activity</h2>{modelingSession ? <ul className="activity-list"><li data-testid="recent-modeling-session"><span><strong>{modelingSession.material?.label ?? modelingSession.objective ?? "Material modeling session"}</strong><small className="ux-meta">{`${modelingSession.materialFamily} · ${stageLabel} · ${modelingSession.testData ? `${modelingSession.testData.label} r${modelingSession.testData.revisionNo}` : "No exact Test Data"} · ${modelingSession.workspace.selectedDocumentIds.length} selected curves`}</small></span><button className="ux-button" type="button" onClick={() => onNavigate(resumePath)}>{`Resume ${stageLabel}`}</button></li></ul> : <section className="activity-empty-state" role="status" aria-label="No recent Modeling session"><div><strong>No recent Modeling session</strong><p>This browser has no local Data, Process, Fit, or Export session to resume.</p></div><button className="ux-button" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button></section>}<ul className="activity-list activity-destinations"><li><span><strong>Reviews and releases</strong><small className="ux-meta">Open the governed review workspace. Activity attention and queue integration remain pending.</small></span><button className="ux-button" type="button" onClick={() => onNavigate("/jobs-reviews")}>Open review workspace</button></li></ul><details className="ux-disclosure"><summary>Advanced jobs and export packages</summary><p>Inspect batch attempts, technical diagnostics, and checksum-verifiable bulk packages.</p><button className="ux-button" type="button" onClick={() => onNavigate("/exports")}>Open export packages</button></details></div></div></div>;
}
