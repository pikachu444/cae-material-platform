import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  downloadNeutralHyperelasticMappingReport,
  downloadNeutralHyperelasticSolverCard,
  getCatalogWorkflowGraph,
  getMaterialDetail,
  listBulkExportCandidates,
  listMaterials,
  previewNeutralHyperelasticSolverCard,
  resolveCatalogDomainRevision,
  type ApiConfig,
} from "./api";
import type {
  CatalogWorkflowGraphResponse,
  MaterialDetail,
  MaterialResponse,
  PropertySetResponse,
} from "./types";

export type MaterialTab = "overview" | "properties" | "curves" | "cards" | "evidence";

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
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

export function MaterialSearchPage({ config, onNavigate }: Props) {
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [materialClass, setMaterialClass] = useState("");
  const [solver, setSolver] = useState("");
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");
  const [yieldMin, setYieldMin] = useState("");
  const [yieldMax, setYieldMax] = useState("");
  const [sortKey, setSortKey] = useState<"name" | "family" | "yield" | "cards">("name");
  const [sortDirection, setSortDirection] = useState<"ascending" | "descending">("ascending");
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [filtersVisible, setFiltersVisible] = useState(true);
  const [contextVisible, setContextVisible] = useState(
    () => typeof window === "undefined" || window.innerWidth > 1400,
  );
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [experience, setExperience] = useState<Record<string, MaterialExperience>>({});
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        setSelectedId(items[0]?.material_id ?? "");
        setLoading(false);
        const settled = await Promise.allSettled(items.map((item) => loadMaterialExperience(config, item)));
        if (!active) return;
        const next: Record<string, MaterialExperience> = {};
        settled.forEach((resultItem, index) => {
          if (resultItem.status === "fulfilled") next[items[index].material_id] = resultItem.value;
        });
        setExperience(next);
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
  }, [config, materialClass, query]);

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
    if (!filtered.some((item) => item.material_id === selectedId)) setSelectedId(filtered[0]?.material_id ?? "");
  }, [filtered, selectedId]);

  const selected = filtered.find((item) => item.material_id === selectedId);
  const selectedExperience = selected ? experience[selected.material_id] : undefined;
  const selectedProperty = currentProperty(selectedExperience)?.current_revision.content;

  function submit(event: FormEvent): void {
    event.preventDefault();
    setQuery(draftQuery.trim());
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

  return (
    <div className="ux-page">
      <header className="materials-page-header">
        <div><div className="materials-mode-switch" role="group" aria-label="Material discovery mode"><button type="button" className="active">Search</button><button type="button" onClick={() => onNavigate(browsePath(selectedExperience))}>Browse Tree</button></div><h1>Find material data ready for CAE</h1><p>Compare governed material records and open an available native solver card.</p></div>
        <form className="materials-search-form" role="search" onSubmit={submit}>
          <label className="ux-field" style={{ flex: 1 }}><span className="ux-meta">Material name, grade, code, or family</span><input className="ux-input" aria-label="Search materials" value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder="Search DP780, polymer, rubber…" /></label>
          <button className="ux-button primary" type="submit">Search</button>
        </form>
      </header>
      <div className="materials-workspace-toolbar"><button className="ux-button tertiary" type="button" aria-expanded={filtersVisible} onClick={() => setFiltersVisible((current) => !current)}>{filtersVisible ? "Hide filters" : "Show filters"}</button><span className="ux-meta">Search uses governed Material identities; Browse Tree retains Profile, Table, Folder, Layout, Subset, and exact Record links.</span><button className="ux-button tertiary" type="button" aria-expanded={contextVisible} onClick={() => setContextVisible((current) => !current)}>{contextVisible ? "Hide details" : "Show details"}</button></div>
      <div className={`materials-workspace${filtersVisible ? " filters-visible" : ""}${contextVisible ? " context-visible" : ""}`}>
        {filtersVisible ? <aside className="materials-filters" aria-label="Material filters">
          <div><h2>Filters</h2><p className="ux-meta">Facets stay visible while the selected material changes.</p></div>
          <label className="ux-field">Material class<select className="ux-select" value={materialClass} onChange={(event) => setMaterialClass(event.target.value)}><option value="">All classes</option><option value="metal">Metal</option><option value="polymer">Polymer</option><option value="elastomer">Elastomer</option><option value="composite">Composite</option><option value="ceramic">Ceramic</option></select></label>
          <label className="ux-field">Manufacturer / source<select className="ux-select" value={source} onChange={(event) => setSource(event.target.value)}><option value="">Any source</option>{sourceOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <label className="ux-field">CAE card<select className="ux-select" value={solver} onChange={(event) => setSolver(event.target.value)}><option value="">Any availability</option><option value="Abaqus">Abaqus available</option><option value="OpenRadioss">OpenRadioss available</option></select></label>
          <label className="ux-field">Validation / release status<select className="ux-select" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Any status</option><option value="draft">Draft / reference</option></select></label>
          <fieldset className="ux-field"><legend>Yield strength (MPa)</legend><div className="filter-range"><input className="ux-input" aria-label="Minimum yield strength" type="number" value={yieldMin} onChange={(event) => setYieldMin(event.target.value)} placeholder="Min"/><input className="ux-input" aria-label="Maximum yield strength" type="number" value={yieldMax} onChange={(event) => setYieldMax(event.target.value)} placeholder="Max"/></div></fieldset>
          <button className="ux-button tertiary" type="button" onClick={() => { setMaterialClass(""); setSource(""); setSolver(""); setStatus(""); setYieldMin(""); setYieldMax(""); }}>Clear filters</button>
          <div className="browse-tree-entry"><strong>Browse and saved subsets</strong><p className="ux-meta">Navigate Database → Profile → Table → Folder → Record, or apply a governed saved Subset.</p><button className="ux-button" type="button" onClick={() => onNavigate(browsePath(selectedExperience))}>Open Browse Tree</button></div>
        </aside> : null}
        <section className="materials-results" aria-labelledby="material-results-title">
          <div className="materials-results-header"><div><h2 id="material-results-title">Materials</h2><p className="ux-meta">{loading ? "Loading…" : `${filtered.length} shown · ${new Intl.NumberFormat().format(totalCount)} total`}</p></div><span className="ux-meta">Select up to 3 to compare</span></div>
          {error ? <div className="ux-notice error" role="alert">{error}</div> : null}
          {!loading && !error && !filtered.length ? <div className="ux-empty"><strong>No materials match these filters.</strong><p>Clear a filter or try a material grade, code, or family.</p></div> : null}
          {comparedMaterials.length > 1 ? <div className="material-compare-strip"><div><strong>Comparing {comparedMaterials.length} materials</strong><span className="ux-meta">Key normalized values</span></div>{comparedMaterials.map((material) => { const itemExperience = experience[material.material_id]; const property = currentProperty(itemExperience)?.current_revision.content; return <dl key={material.material_id}><dt>{material.current_revision.content.name}</dt><dd>{formatPressure(property?.yield_stress_pa)}</dd><dd>{formatDensity(property?.density_kg_per_m3)}</dd><dd>{itemExperience?.cards.length ?? 0} cards</dd></dl>; })}<button className="ux-button tertiary" type="button" onClick={() => setCompareIds(new Set())}>Clear comparison</button></div> : null}
          <div className="materials-result-table-wrap"><table className="materials-result-table" aria-label="Material results"><thead><tr><th>Compare</th><th><button type="button" aria-sort={sortKey === "name" ? sortDirection : undefined} onClick={() => changeSort("name")}>Material</button></th><th><button type="button" aria-sort={sortKey === "family" ? sortDirection : undefined} onClick={() => changeSort("family")}>Family</button></th><th>Source</th><th><button type="button" aria-sort={sortKey === "yield" ? sortDirection : undefined} onClick={() => changeSort("yield")}>Yield</button></th><th><button type="button" aria-sort={sortKey === "cards" ? sortDirection : undefined} onClick={() => changeSort("cards")}>CAE cards</button></th></tr></thead><tbody>
            {filtered.map((material) => {
              const content = material.current_revision.content;
              const itemExperience = experience[material.material_id];
              const property = currentProperty(itemExperience)?.current_revision.content;
              return <tr key={material.material_id} className={selectedId === material.material_id ? "selected" : ""}><td><input type="checkbox" aria-label={`Compare ${content.name}`} checked={compareIds.has(material.material_id)} disabled={!compareIds.has(material.material_id) && compareIds.size >= 3} onChange={() => toggleCompare(material.material_id)}/></td><td><button className="material-result-name" type="button" aria-current={selectedId === material.material_id ? "true" : undefined} title={content.name} onClick={() => setSelectedId(material.material_id)}><strong>{content.name}</strong><small>{content.material_code ?? "No grade code"}</small></button></td><td title={content.material_family ?? content.material_class}>{content.material_family ?? content.material_class}</td><td title={sourceLabel(itemExperience)}>{sourceLabel(itemExperience)}</td><td className="ux-numeric">{formatPressure(property?.yield_stress_pa)}</td><td>{itemExperience ? `${itemExperience.cards.length} cards` : "Checking…"}</td></tr>;
            })}
          </tbody></table></div>
        </section>
        {contextVisible ? <aside className="materials-selection" aria-live="polite">
          {selected ? <>
            <div className="selection-heading"><div><p className="ux-kicker">Selected material</p><h2 title={selected.current_revision.content.name}>{selected.current_revision.content.name}</h2></div><span className="ux-meta">{selected.current_revision.content.material_code ?? "No material code"}</span></div>
            <p>{selected.current_revision.content.description ?? "No summary is available."}</p>
            <div className="selection-property-grid"><div><span>Density</span><strong>{formatDensity(selectedProperty?.density_kg_per_m3)}</strong></div><div><span>Young’s modulus</span><strong>{formatPressure(selectedProperty?.youngs_modulus_pa)}</strong></div><div><span>Yield strength</span><strong>{formatPressure(selectedProperty?.yield_stress_pa)}</strong></div><div><span>Poisson ratio</span><strong>{selectedProperty?.poisson_ratio ?? "—"}</strong></div></div>
            <dl className="selection-context"><dt>Source</dt><dd>{sourceLabel(selectedExperience)}</dd><dt>Status</dt><dd>{selected.current_revision.lifecycle_state}</dd></dl>
            <h3>CAE card availability</h3><SolverAvailability cards={selectedExperience?.cards ?? []}/>
            <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/${selected.material_id}`)}>Open material</button>
            <button className="ux-button tertiary" type="button" onClick={() => onNavigate(browsePath(selectedExperience))}>Show in Browse Tree</button>
          </> : <div className="ux-empty"><strong>Select a material</strong><p>Key properties and solver-card availability will appear here.</p></div>}
        </aside> : null}
      </div>
    </div>
  );
}

function CardTable({ materialId, cards, onNavigate }: { materialId: string; cards: SolverCardSummary[]; onNavigate: (path: string) => void }) {
  if (!cards.length) return <div className="ux-empty"><strong>No native card is available.</strong><p>Open Modeling to process test data, review a model, and create a governed solver card.</p><button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button></div>;
  return <table className="ux-table"><thead><tr><th>Solver</th><th>Card</th><th>Format</th><th>Action</th></tr></thead><tbody>{cards.map((card) => <tr key={card.id}><td><strong>{card.solver}</strong></td><td>{card.label}</td><td>Native ASCII {card.extension}</td><td><button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards/${card.id}`)}>Preview &amp; download</button></td></tr>)}</tbody></table>;
}

export function MaterialDetailPage({ config, materialId, activeTab, onNavigate }: Props & { materialId: string; activeTab: MaterialTab }) {
  const [experience, setExperience] = useState<MaterialExperience | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (loading) return <div className="ux-page"><div className="material-detail-shell"><p className="loading-state">Loading material…</p></div></div>;
  if (error || !experience) return <div className="ux-page"><div className="material-detail-shell"><div className="ux-notice error" role="alert">{error ?? "Material not found."}</div><button className="ux-button" type="button" onClick={() => onNavigate("/materials")}>Back to Materials</button></div></div>;

  const material = experience.detail.material;
  const content = material.current_revision.content;
  const propertySet = currentProperty(experience);
  const property = propertySet?.current_revision.content;
  const activePath = activeTab === "overview" ? `/materials/${materialId}` : `/materials/${materialId}/${activeTab}`;
  return <div className="ux-page"><div className="material-detail-shell">
    <header className="material-detail-header"><div><button className="ux-button tertiary" type="button" onClick={() => onNavigate("/materials")}>← Materials</button><p className="ux-kicker">{content.material_family ?? content.material_class}</p><h1>{content.name}</h1><div className="material-detail-meta"><span>{content.material_code ?? "No grade code"}</span><span>{sourceLabel(experience)}</span><span>{material.current_revision.lifecycle_state}</span></div><p>{content.description ?? "Governed material record and CAE delivery."}</p></div><div className="card-action-row">{experience.cards[0] ? <button className="ux-button primary" type="button" onClick={() => onNavigate(`/materials/${materialId}/cards/${experience.cards[0].id}`)}>Preview CAE card</button> : <button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Start Modeling</button>}</div></header>
    <nav className="ux-tabs" role="tablist" aria-label="Material detail"><input type="hidden" value={activePath} readOnly />{tabs.map((tab) => <button key={tab.id} className="ux-tab" type="button" role="tab" aria-selected={activeTab === tab.id} onClick={() => onNavigate(tab.id === "overview" ? `/materials/${materialId}` : `/materials/${materialId}/${tab.id}`)}>{tab.label}</button>)}</nav>
    <section className="material-tab-panel" role="tabpanel">
      {activeTab === "overview" ? <div className="overview-grid"><div><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Engineering summary</p><h2>Key properties</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/properties`)}>All properties</button></div><div className="overview-property-grid"><div><span>Density</span><strong>{formatDensity(property?.density_kg_per_m3)}</strong></div><div><span>Young’s modulus</span><strong>{formatPressure(property?.youngs_modulus_pa)}</strong></div><div><span>Yield strength</span><strong>{formatPressure(property?.yield_stress_pa)}</strong></div><div><span>Poisson ratio</span><strong>{property?.poisson_ratio ?? "—"}</strong></div></div></section><div className="overview-data-grid"><section className="overview-section"><div className="detail-section-heading"><div><p className="ux-kicker">Representative curve</p><h2>Linked material response</h2></div><button className="ux-button tertiary" type="button" onClick={() => onNavigate(`/materials/${materialId}/curves`)}>All curves</button></div><RepresentativeCurve points={experience.representativeCurve}/></section><section className="overview-section"><p className="ux-kicker">Application conditions</p><h2>Material states</h2><dl className="condition-summary"><dt>Temperature</dt><dd>{property?.applicability.temperature_min_k ?? "—"}–{property?.applicability.temperature_max_k ?? "—"} K</dd><dt>Strain rate</dt><dd>{property?.applicability.strain_rate_min_per_s ?? "—"}–{property?.applicability.strain_rate_max_per_s ?? "—"} /s</dd></dl>{experience.detail.states.slice(0, 2).map((state) => <p className="condition-state" key={state.material_state_id}><strong>{state.current_revision.content.name}</strong><span>{state.current_revision.content.manufacturing_route ?? "Route not specified"}</span></p>)}</section></div></div><aside><p className="ux-kicker">CAE delivery</p><h2>Ready solver cards</h2><p>Preview the native content before downloading it for your solver workflow.</p><SolverAvailability cards={experience.cards}/>{experience.cards.map((card) => <button key={card.id} className="ux-button" type="button" style={{ width: "100%", marginBottom: 8 }} onClick={() => onNavigate(`/materials/${materialId}/cards/${card.id}`)}>{card.solver} preview &amp; download</button>)}<button className="ux-button tertiary" type="button" onClick={() => onNavigate(browsePath(experience))}>Related records in Browse Tree</button></aside></div> : null}
      {activeTab === "properties" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Normalized values</p><h2>Engineering properties</h2></div></div>{property ? <table className="ux-table"><thead><tr><th>Property</th><th>Value</th><th>Quantity semantics</th><th>Source</th></tr></thead><tbody><tr><td>Density</td><td>{formatDensity(property.density_kg_per_m3)}</td><td>mass density</td><td>{property.density_source.kind}</td></tr><tr><td>Young’s modulus</td><td>{formatPressure(property.youngs_modulus_pa)}</td><td>elastic modulus</td><td>{property.youngs_modulus_source.kind}</td></tr><tr><td>Poisson ratio</td><td>{property.poisson_ratio}</td><td>dimensionless ratio</td><td>{property.poisson_ratio_source.kind}</td></tr><tr><td>Yield strength</td><td>{formatPressure(property.yield_stress_pa)}</td><td>stress</td><td>{property.yield_stress_source?.kind ?? "—"}</td></tr></tbody></table> : <div className="ux-empty">No typed property set is available.</div>}<p className="ux-meta">Normalized units are shown here. Original unit text and exact source revisions remain preserved in Evidence.</p></> : null}
      {activeTab === "curves" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Test and model data</p><h2>Curves</h2><p>Review available workflow data in the persistent Modeling graph.</p></div><button className="ux-button primary" type="button" onClick={() => onNavigate("/modeling")}>Open in Modeling</button></div><table className="ux-table"><thead><tr><th>Related data</th><th>Type</th><th>Use</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).filter((node) => ["test_data", "processing_output", "material_model"].includes(node.domain_binding?.kind ?? "")).map((node) => <tr key={node.record_id}><td>{node.name}</td><td>{node.domain_binding?.kind.replaceAll("_", " ")}</td><td>{node.domain_binding?.kind === "test_data" ? "Observed input" : node.domain_binding?.kind === "processing_output" ? "Processed curve" : "Fitted response"}</td></tr>)}</tbody></table></> : null}
      {activeTab === "cards" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Solver delivery</p><h2>CAE Cards</h2><p>Review native ASCII content and download a card without leaving this material.</p></div></div><CardTable materialId={materialId} cards={experience.cards} onNavigate={onNavigate}/></> : null}
      {activeTab === "evidence" ? <><div className="detail-section-heading"><div><p className="ux-kicker">Related · Workflow · Evidence</p><h2>Revision and provenance</h2><p>Technical identifiers remain available without competing with the normal material review.</p></div><button className="ux-button" type="button" onClick={() => onNavigate(browsePath(experience))}>Open Layout datasheet</button></div><dl className="evidence-grid"><dt>Material ID</dt><dd>{material.material_id}</dd><dt>Aggregate ID</dt><dd>{material.current_revision.aggregate_id}</dd><dt>Full revision ID</dt><dd>{material.current_revision.id}</dd><dt>Content hash</dt><dd>{material.current_revision.content_hash}</dd><dt>Classification</dt><dd>{material.current_revision.classification}</dd><dt>Change reason</dt><dd>{material.current_revision.change_reason}</dd><dt>Recorded by</dt><dd>{material.current_revision.provenance.recorded_by}</dd></dl><details className="ux-disclosure"><summary>Related exact revisions and material workflow</summary><table className="ux-table"><thead><tr><th>Related record</th><th>Kind</th><th>Exact revision</th></tr></thead><tbody>{(experience.graph?.nodes ?? []).map((node) => <tr key={`${node.record_id}:${node.record_revision_id}`}><td title={node.name}>{node.name}</td><td>{node.domain_binding?.kind ?? "catalog record"}</td><td>{node.domain_binding?.revision_id ?? node.record_revision_id}</td></tr>)}</tbody></table></details><details className="ux-disclosure"><summary>Browse Tree, Layouts, Subsets, and link direction</summary><p>Open the preserved configurable database to inspect Profile/Table/Folder context, administrator Layouts, saved Subsets, and forward/reverse exact-revision Link Types.</p><button className="ux-button" type="button" onClick={() => onNavigate(browsePath(experience))}>Open selected Record in Browse Tree</button></details></> : null}
    </section>
  </div></div>;
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
  return <div className="ux-page"><div className="activity-shell"><header className="activity-header"><p className="ux-kicker">Activity</p><h1>Jobs, reviews, and recent work</h1><p>Resume work that needs attention without exposing workflow internals in the primary navigation.</p></header><div className="activity-content"><h2>Current workspace activity</h2><ul className="activity-list"><li><span><strong>Material modeling sessions</strong><small className="ux-meta">Resume the latest data, process, fit, or export task.</small></span><button className="ux-button" type="button" onClick={() => onNavigate("/modeling")}>Open Modeling</button></li><li><span><strong>Reviews and releases</strong><small className="ux-meta">Review governed outputs and release decisions.</small></span><button className="ux-button" type="button" onClick={() => onNavigate("/jobs-reviews")}>Open reviews</button></li></ul><details className="ux-disclosure"><summary>Advanced jobs and export packages</summary><p>Inspect batch attempts, technical diagnostics, and checksum-verifiable bulk packages.</p><button className="ux-button" type="button" onClick={() => onNavigate("/exports")}>Open export packages</button></details></div></div></div>;
}
