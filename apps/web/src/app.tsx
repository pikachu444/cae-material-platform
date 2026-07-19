import { lazy, Suspense, type FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  compareMaterialRevisions,
  createMaterial,
  createReferenceMaterialModel,
  createMaterialState,
  createPropertySet,
  createSolverCard,
  downloadSolverCard,
  getMaterialDetail,
  getMaterialRevisions,
  getPropertySet,
  listMaterialModels,
  listMaterials,
  listSolverCards,
  defaultApiConfig,
  preflightSolverCardMapping,
  previewSolverCard,
  requestLocalDemoAccessToken,
  reviseMaterial,
  reviseMaterialState,
  revisePropertySet,
} from "./api";
import type {
  DataClassification,
  ExportTarget,
  MaterialDetail,
  MaterialClass,
  MaterialModelResponse,
  MaterialResponse,
  MaterialRevision,
  MaterialStateResponse,
  MappingReport,
  PropertySetResponse,
  PropertySourceKind,
  SolverCardResponse,
} from "./types";
import { DomainWorkflowLinks } from "./domain-workflow-links";

const ReferenceTensileWorkflow = lazy(() =>
  import("./reference-tensile-workflow").then((module) => ({
    default: module.ReferenceTensileWorkflow,
  })),
);
const ReferenceShearRelaxationWorkflow = lazy(() =>
  import("./reference-shear-relaxation-workflow").then((module) => ({
    default: module.ReferenceShearRelaxationWorkflow,
  })),
);
const ReferenceElastoplasticWorkbench = lazy(() =>
  import("./reference-elastoplastic-workbench").then((module) => ({
    default: module.ReferenceElastoplasticWorkbench,
  })),
);
const ReferenceLinearViscoelasticWorkbench = lazy(() =>
  import("./reference-linear-viscoelastic-workbench").then((module) => ({
    default: module.ReferenceLinearViscoelasticWorkbench,
  })),
);
const ReferenceOgdenPronyWorkbench = lazy(() =>
  import("./reference-ogden-prony-workbench").then((module) => ({
    default: module.ReferenceOgdenPronyWorkbench,
  })),
);
const ReferenceCalibrationWorkbench = lazy(() =>
  import("./reference-calibration-workbench").then((module) => ({
    default: module.ReferenceCalibrationWorkbench,
  })),
);
const ReferenceValidationWorkbench = lazy(() =>
  import("./reference-validation-workbench").then((module) => ({
    default: module.ReferenceValidationWorkbench,
  })),
);
const ReviewWorkbench = lazy(() =>
  import("./review-workbench").then((module) => ({ default: module.ReviewWorkbench })),
);
const ReleaseWorkbench = lazy(() =>
  import("./release-workbench").then((module) => ({ default: module.ReleaseWorkbench })),
);
const GovernanceEvidenceWorkbench = lazy(() =>
  import("./governance-evidence-workbench").then((module) => ({
    default: module.GovernanceEvidenceWorkbench,
  })),
);
const CatalogGenealogyWorkbench = lazy(() =>
  import("./catalog-genealogy-workbench").then((module) => ({
    default: module.CatalogGenealogyWorkbench,
  })),
);
const TestContextWorkbench = lazy(() =>
  import("./test-context-workbench").then((module) => ({
    default: module.TestContextWorkbench,
  })),
);
const GovernedImportWorkbench = lazy(() =>
  import("./governed-import-workbench").then((module) => ({
    default: module.GovernedImportWorkbench,
  })),
);
const BulkExportCenter = lazy(() =>
  import("./bulk-export-center").then((module) => ({ default: module.BulkExportCenter })),
);
const OperationsDashboard = lazy(() =>
  import("./operations-dashboard").then((module) => ({
    default: module.OperationsDashboard,
  })),
);
const ConfigurableCatalogAdmin = lazy(() =>
  import("./configurable-catalog-admin").then((module) => ({
    default: module.ConfigurableCatalogAdmin,
  })),
);
const ConfigurableCatalogRecords = lazy(() =>
  import("./configurable-catalog-records").then((module) => ({
    default: module.ConfigurableCatalogRecords,
  })),
);
const CatalogExplorer = lazy(() =>
  import("./catalog-explorer").then((module) => ({
    default: module.CatalogExplorer,
  })),
);
const MaterialDatabaseExplorer = lazy(() =>
  import("./material-database-explorer").then((module) => ({
    default: module.MaterialDatabaseExplorer,
  })),
);
const CanonicalTestDataWorkbench = lazy(() =>
  import("./canonical-test-data-workbench").then((module) => ({
    default: module.CanonicalTestDataWorkbench,
  })),
);
const CommonProcessingWorkbench = lazy(() =>
  import("./common-processing-workbench").then((module) => ({
    default: module.CommonProcessingWorkbench,
  })),
);
const MaterialModelingWorkspace = lazy(() =>
  import("./material-modeling-workspace").then((module) => ({
    default: module.MaterialModelingWorkspace,
  })),
);
const ProductAccessCenter = lazy(() =>
  import("./product-access-center").then((module) => ({
    default: module.ProductAccessCenter,
  })),
);

type Navigate = (path: string) => void;
type MaterialArea = "overview" | "testing" | "datasets" | "models" | "governance";

const materialAreas: ReadonlyArray<{ area: MaterialArea; label: string }> = [
  { area: "overview", label: "Overview" },
  { area: "testing", label: "Test data" },
  { area: "datasets", label: "Datasets & Processing" },
  { area: "models", label: "Models & Cards" },
  { area: "governance", label: "Governance" },
];

const classifications: DataClassification[] = [
  "internal",
  "confidential",
  "restricted",
  "export_controlled",
];

const sourceKinds: PropertySourceKind[] = [
  "manual",
  "supplier_datasheet",
  "test_derived",
  "literature",
  "calibration",
];

const materialClasses: MaterialClass[] = [
  "metal",
  "polymer",
  "elastomer",
  "composite",
  "ceramic",
  "other",
];

function useLocationPath(): [string, Navigate] {
  const [path, setPath] = useState(() => window.location.pathname || "/");

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname || "/");
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate: Navigate = (nextPath) => {
    if (nextPath === window.location.pathname) {
      return;
    }
    window.history.pushState({}, "", nextPath);
    setPath(window.location.pathname || "/");
  };
  return [path, navigate];
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The request could not be completed. Try again in a moment.";
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : null;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function formatPressurePa(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(value / 1e6)} MPa`;
}

function Header({
  path,
  navigate,
}: {
  path: string;
  navigate: Navigate;
}) {
  const navigation = [
    { label: "Dashboard", target: "/", active: path === "/" },
    {
      label: "Material Database",
      target: "/database",
      active: path.startsWith("/database") || path.startsWith("/catalog") || path.startsWith("/materials"),
    },
    {
      label: "Material Modeling",
      target: "/modeling",
      active: path.startsWith("/modeling") || path.startsWith("/datasets") || path.startsWith("/models"),
    },
    {
      label: "Jobs & Reviews",
      target: "/jobs-reviews",
      active: path.startsWith("/jobs-reviews") || path.startsWith("/governance") || path.startsWith("/exports"),
    },
    {
      label: "Administration",
      target: "/administration",
      active: path.startsWith("/administration") || path.startsWith("/access"),
    },
  ];
  return (
    <header className="app-header">
      <button className="brand" type="button" onClick={() => navigate("/")}>
        <span className="brand-mark">CMP</span>
        <span>
          <strong>CAE Material Platform</strong>
          <small>Material Database &amp; Modeling</small>
        </span>
      </button>
      <nav aria-label="Primary navigation">
        {navigation.map((item) => (
          <button
            key={item.target}
            className={item.active ? "nav-link active" : "nav-link"}
            type="button"
            aria-current={item.active ? "page" : undefined}
            onClick={() => navigate(item.target)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <span className="product-user-badge" aria-label="Current workspace">Demo workspace</span>
    </header>
  );
}

function ProductSessionBoundary({ loading, onRetry }: { loading: boolean; onRetry: () => void }) {
  return (
    <section className="product-session-boundary" aria-live="polite">
      <span className="brand-mark">CMP</span>
      <p className="eyebrow">CAE Material Platform</p>
      <h1>{loading ? "Preparing your workspace…" : "Sign in to continue"}</h1>
      <p>{loading ? "Loading the Material Database and modeling tools." : "The workspace session could not be started."}</p>
      {!loading ? <button className="button primary" type="button" onClick={onRetry}>Try again</button> : null}
    </section>
  );
}

function AdministrationWorkspace({
  config,
  navigate,
  onOpenConnection,
  section,
}: {
  config: ApiConfig;
  navigate: Navigate;
  onOpenConnection: () => void;
  section: "overview" | "database" | "access";
}) {
  return (
    <div className="administration-workspace">
      <aside className="administration-navigation">
        <div>
          <p className="eyebrow">Administration</p>
          <h2>Workspace setup</h2>
        </div>
        <nav aria-label="Administration areas">
          <button className={section === "overview" ? "active" : ""} type="button" onClick={() => navigate("/administration")}>
            <span>01</span><strong>Overview</strong>
          </button>
          <button className={section === "database" ? "active" : ""} type="button" onClick={() => navigate("/administration/database")}>
            <span>02</span><strong>Database design</strong>
          </button>
          <button className={section === "access" ? "active" : ""} type="button" onClick={() => navigate("/administration/access")}>
            <span>03</span><strong>Users &amp; access</strong>
          </button>
        </nav>
        <button className="text-button" type="button" onClick={() => navigate("/database")}>Open Material Database</button>
      </aside>
      <section className="administration-content">
        {section === "overview" ? <>
          <header className="page-heading">
            <div><p className="eyebrow">Administration</p><h1>Configure the material workspace</h1><p>Define what information is stored and who can work with it. Infrastructure settings stay out of the product interface.</p></div>
          </header>
          <section className="administration-task-grid" aria-label="Administration tasks">
            <button type="button" onClick={() => navigate("/administration/database")}><span className="workspace-choice-icon">DB</span><span><small>Material information system</small><strong>Design the database</strong><p>Add Tables, typed Attributes, datasheet Layouts, saved Subsets and exact Record Link Types without a migration.</p></span><em>Configure ›</em></button>
            <button type="button" onClick={() => navigate("/administration/access")}><span className="workspace-choice-icon">US</span><span><small>People and capabilities</small><strong>Manage access</strong><p>Assign Administrator or User and enable only the product features each team needs.</p></span><em>Manage ›</em></button>
          </section>
          <section className="administration-principle"><p className="eyebrow">Designed for extension</p><h2>Simple now, granular when needed.</h2><p>The product surface uses two roles and five understandable feature permissions. The existing resource/action/scope enforcement remains an internal extension point, so later policies do not require a Catalog schema rewrite.</p></section>
        </> : null}
        {section === "database" ? <ConfigurableCatalogAdmin config={config} onNavigate={navigate} onOpenConnection={onOpenConnection} productMode /> : null}
        {section === "access" ? <ProductAccessCenter config={config} onOpenConnection={onOpenConnection} productMode /> : null}
      </section>
    </div>
  );
}

function DashboardPage({
  config,
  navigate,
}: {
  config: ApiConfig;
  navigate: Navigate;
}) {
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let current = true;
    setLoading(true);
    setError(null);
    void listMaterials(config, "")
      .then((result) => {
        if (current) {
          setMaterials(result.data.items.slice(0, 5));
          setTotalCount(result.data.total_count);
        }
      })
      .catch((reason: unknown) => current && setError(errorMessage(reason)))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, [config]);

  function searchMaterials(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setLoading(true);
    setError(null);
    void listMaterials(config, searchQuery)
      .then((result) => {
        setMaterials(result.data.items.slice(0, 8));
        setTotalCount(result.data.total_count);
      })
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  }

  const demoMaterial = (materialClass: MaterialClass) =>
    materials.find((material) => material.current_revision.content.material_class === materialClass);
  const demoJourneys: Array<{
    materialClass: MaterialClass;
    eyebrow: string;
    title: string;
    description: string;
    action: string;
  }> = [
    {
      materialClass: "metal",
      eyebrow: "Metal · elastoplastic",
      title: "Tensile data to Abaqus and OpenRadioss",
      description: "Inspect repeated tensile curves, processing choices, tabulated hardening IR, and two native cards.",
      action: "Open metal journey",
    },
    {
      materialClass: "polymer",
      eyebrow: "Polymer · viscoelastic",
      title: "Relaxation data to Prony material",
      description: "Review temperature replicates, the master curve, two-term Prony response, and the Abaqus card.",
      action: "Open polymer journey",
    },
    {
      materialClass: "elastomer",
      eyebrow: "Elastomer · hyper-viscoelastic",
      title: "Multi-mode fitting to reviewed solver cards",
      description: "Compare uniaxial, planar, biaxial and holdout curves before opening the promoted Ogden-Prony IR.",
      action: "Open elastomer journey",
    },
  ];

  return (
    <div className="page-stack">
      <section className="workspace-home-intro">
        <div><p className="eyebrow">Workspace home</p><h1>Material data to solver-ready models</h1></div>
        <p>Choose the work you need to do. The database path finds trusted material knowledge; the modeling path turns linked test curves into reviewed Neutral JSON and solver cards.</p>
      </section>
      <section className="workspace-lane-grid" aria-label="Primary material workspace tasks">
        <article className="workspace-lane database-lane">
          <header><span>01</span><div><p className="eyebrow">Material Database · {loading ? "Loading" : `${totalCount.toLocaleString()} records`}</p><h2>Find and inspect material data</h2></div></header>
          <p>Browse the Contents Tree or search by material, grade, maker and standard. Open a Datasheet to follow exact links to tests, models and cards.</p>
          <form className="dashboard-material-search" onSubmit={searchMaterials}>
            <span aria-hidden="true">⌕</span>
            <input
              aria-label="Search materials"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Material, grade, maker or standard"
            />
            <button className="button primary" type="submit">Search database</button>
          </form>
          <button className="text-button lane-primary-action" type="button" onClick={() => navigate("/database")}>Open Contents Tree and Datasheets ›</button>
        </article>
        <article className="workspace-lane modeling-lane">
          <header><span>02</span><div><p className="eyebrow">Material Modeling</p><h2>Process test curves and create cards</h2></div></header>
          <p>Map test channels, prepare curves, compare fitting and extrapolation candidates, then create Neutral JSON and Abaqus/OpenRadioss cards.</p>
          <div className="modeling-lane-flow" aria-label="Material Modeling workflow"><span>Prepare</span><span>Fit</span><span>Extrapolate</span><span>Card</span></div>
          <div className="workspace-lane-actions"><button className="button primary" type="button" onClick={() => navigate("/modeling")}>Continue modeling</button><button className="button secondary" type="button" onClick={() => navigate("/datasets/test-json")}>Import test data</button></div>
        </article>
      </section>
      <section className="content-card guided-demo-card" aria-labelledby="guided-demo-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Reference workflows by material family</p>
            <h2 id="guided-demo-title">Start with an engineering example</h2>
            <p className="muted">
              Open a realistic example with linked test data, processing choices, model candidates and native solver cards.
            </p>
          </div>
          <button className="button secondary" type="button" onClick={() => navigate("/exports")}>
            Download center
          </button>
        </div>
        <div className="demo-journey-grid">
          {demoJourneys.map((journey) => {
            const material = demoMaterial(journey.materialClass);
            return (
              <article className={`demo-journey ${journey.materialClass}`} key={journey.materialClass}>
                <p className="eyebrow">{journey.eyebrow}</p>
                <h3>{journey.title}</h3>
                <p>{journey.description}</p>
                <button
                  className="text-button"
                  type="button"
                  onClick={() =>
                    navigate(material ? `/materials/${material.material_id}/models` : "/materials")
                  }
                >
                  {journey.action}
                </button>
              </article>
            );
          })}
        </div>
        <div className="demo-evidence-path" aria-label="Guided demo evidence path">
          <span>Material</span><span>Test JSON</span><span>Recipe / fitting</span>
          <span>Neutral IR</span><span>Solver card</span><span>Bulk ZIP</span>
        </div>
      </section>
      <section className="content-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Material Database · {loading ? "Loading" : `${totalCount.toLocaleString()} records`}</p>
            <h2>{searchQuery ? `Results for “${searchQuery}”` : "Materials in this workspace"}</h2>
          </div>
          <button className="text-button" type="button" onClick={() => navigate("/database")}>
            Open database
          </button>
        </div>
        {error ? <ErrorNotice message={error} /> : null}
        {loading ? <p className="muted">Loading catalog…</p> : null}
        {!loading && !error && materials.length === 0 ? (
          <p className="muted">No matching material was found. Try another term or create a new material record.</p>
        ) : null}
        <div className="material-list compact">
          {materials.map((material) => (
            <MaterialRow key={material.material_id} material={material} navigate={navigate} />
          ))}
        </div>
      </section>
    </div>
  );
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="error-notice" role="alert">
      {message}
    </div>
  );
}

function MaterialRow({ material, navigate }: { material: MaterialResponse; navigate: Navigate }) {
  const content = material.current_revision.content;
  return (
    <button
      className="material-row"
      type="button"
      onClick={() => navigate(`/materials/${material.material_id}`)}
    >
      <span className="material-monogram">{content.name.slice(0, 2).toUpperCase()}</span>
      <span className="material-row-main">
        <strong>{content.name}</strong>
        <small>{content.material_code ?? content.material_family ?? "Unclassified material"}</small>
      </span>
      <span className={`material-class-chip ${content.material_class}`}>
        {content.material_class.replaceAll("_", " ")}
      </span>
      <span className="revision-chip">r{material.current_revision.revision_no}</span>
      <span className="material-chevron">›</span>
    </button>
  );
}

function MaterialListPage({
  config,
  navigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  navigate: Navigate;
  onOpenConnection: () => void;
}) {
  const [query, setQuery] = useState("");
  const [materialClass, setMaterialClass] = useState<MaterialClass | "">("");
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (nextQuery: string, nextClass = materialClass) => {
    if (!config.accessToken.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    void listMaterials(config, nextQuery, nextClass)
      .then((result) => {
        setMaterials(result.data.items);
        setTotalCount(result.data.total_count);
      })
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load("");
    // Reload when the product session changes; searches run on form submit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config]);

  if (!config.accessToken.trim()) {
    return <ProductSessionBoundary loading={false} onRetry={onOpenConnection} />;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    load(query, materialClass);
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Catalog</p>
          <h1>Materials</h1>
          <p>Search current revisions visible to the selected organization, project, and clearance.</p>
        </div>
        <button className="button primary" type="button" onClick={() => navigate("/materials/new")}>
          Create material
        </button>
      </section>
      <section className="content-card">
        <form className="search-form" onSubmit={submit}>
          <label className="search-label">
            Search name, code, or family
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. DP780, aluminum, PA6"
            />
          </label>
          <label>
            Material class
            <select
              value={materialClass}
              onChange={(event) => setMaterialClass(event.target.value as MaterialClass | "")}
            >
              <option value="">All classes</option>
              <option value="unclassified">unclassified</option>
              {materialClasses.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <button className="button secondary" type="submit">
            Search
          </button>
        </form>
        {error ? <ErrorNotice message={error} /> : null}
        {loading ? <p className="muted">Loading materials…</p> : null}
        {!loading && !error && totalCount > 0 ? (
          <p className="muted" aria-live="polite">
            Showing {materials.length.toLocaleString()} of {totalCount.toLocaleString()} Materials
            visible in this authorization scope.
          </p>
        ) : null}
        {!loading && !error && materials.length === 0 ? (
          <p className="muted">No Material matches this search in the current scope.</p>
        ) : null}
        <div className="material-list">
          {materials.map((material) => (
            <MaterialRow key={material.material_id} material={material} navigate={navigate} />
          ))}
        </div>
      </section>
    </div>
  );
}

const moduleHubContent: Record<Exclude<MaterialArea, "overview">, {
  eyebrow: string;
  title: string;
  description: string;
  action: string;
}> = {
  testing: {
    eyebrow: "Testing",
    title: "Test data",
    description: "Open a Material to govern campaigns, instruments, source files, and explicit column/unit mappings.",
    action: "Open test workspace",
  },
  datasets: {
    eyebrow: "Datasets",
    title: "Datasets & Processing",
    description: "Review raw, normalized, processed, statistical, and master-curve representations without replacing source curves.",
    action: "Open dataset workspace",
  },
  models: {
    eyebrow: "Modeling",
    title: "Material Models & Solver Cards",
    description: "Create or calibrate solver-neutral IR revisions, inspect mapping status, and download reference cards.",
    action: "Open model workspace",
  },
  governance: {
    eyebrow: "Governance",
    title: "Evidence, Review & Release",
    description: "Inspect immutable provenance and audit evidence before review, approval, release, or impact analysis.",
    action: "Open Material governance",
  },
};

function ModuleHubPage({
  area,
  config,
  navigate,
  onOpenConnection,
}: {
  area: Exclude<MaterialArea, "overview">;
  config: ApiConfig;
  navigate: Navigate;
  onOpenConnection: () => void;
}) {
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const copy = moduleHubContent[area];

  useEffect(() => {
    if (!config.accessToken.trim()) {
      setMaterials([]);
      setTotalCount(0);
      return;
    }
    let current = true;
    setLoading(true);
    setError(null);
    void listMaterials(config, "")
      .then((result) => {
        if (current) {
          setMaterials(result.data.items);
          setTotalCount(result.data.total_count);
        }
      })
      .catch((cause: unknown) => current && setError(errorMessage(cause)))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, [config, area]);

  if (!config.accessToken.trim()) {
    return <ProductSessionBoundary loading={false} onRetry={onOpenConnection} />;
  }

  return (
    <div className="page-stack">
      <section className="page-heading module-heading">
        <div>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h1>{copy.title}</h1>
          <p>{copy.description}</p>
        </div>
        {area === "datasets" ? (
          <div className="hero-actions"><button className="button secondary" type="button" onClick={() => navigate("/datasets/test-json")}>Import Test Data JSON</button><button className="button primary" type="button" onClick={() => navigate("/datasets/processing")}>Open Processing Workbench</button></div>
        ) : null}
      </section>
      <section className="content-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Material context</p>
            <h2>Select a Material</h2>
          </div>
          <span className="count-chip">{totalCount.toLocaleString()} visible</span>
        </div>
        {error ? <ErrorNotice message={error} /> : null}
        {loading ? <p className="muted">Loading Material contexts…</p> : null}
        {!loading && !error && materials.length === 0 ? (
          <p className="muted">No Material is available in this workspace.</p>
        ) : null}
        <div className="module-material-grid">
          {materials.map((material) => (
            <article className="module-material-card" key={material.material_id}>
              <div>
                <span className={`material-class-chip ${material.current_revision.content.material_class}`}>
                  {material.current_revision.content.material_class}
                </span>
                <h3>{material.current_revision.content.name}</h3>
                <p>{material.current_revision.content.material_code ?? material.current_revision.content.material_family ?? "No material code"}</p>
              </div>
              <button
                className="button secondary"
                type="button"
                onClick={() => navigate(`/materials/${material.material_id}/${area}`)}
              >
                {copy.action}
              </button>
            </article>
          ))}
        </div>
      </section>
      {area === "governance" ? (
        <>
          <OperationsDashboard config={config} />
          <ReviewWorkbench config={config} />
          <ReleaseWorkbench config={config} />
          <GovernanceEvidenceWorkbench config={config} />
        </>
      ) : null}
    </div>
  );
}

function MaterialCreatePage({
  config,
  navigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  navigate: Navigate;
  onOpenConnection: () => void;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [family, setFamily] = useState("");
  const [materialClass, setMaterialClass] = useState<MaterialClass | "">("");
  const [description, setDescription] = useState("");
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [reason, setReason] = useState("Initial Material catalog entry");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!config.accessToken.trim()) {
    return <ProductSessionBoundary loading={false} onRetry={onOpenConnection} />;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!materialClass) {
      setError("Select a Material class before creating the immutable revision.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await createMaterial(config, {
        classification,
        content: {
          name: name.trim(),
          material_code: blankToNull(code),
          material_family: blankToNull(family),
          description: blankToNull(description),
          material_class: materialClass,
        },
        change_reason: reason.trim(),
      });
      navigate(`/materials/${result.data.material_id}`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-stack narrow">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Catalog / New</p>
          <h1>Create Material</h1>
          <p>
            Creates one stable Material identity and its first immutable revision. It does not replace
            an existing record.
          </p>
        </div>
      </section>
      <section className="content-card">
        <form className="form-stack" onSubmit={submit}>
          <div className="form-grid">
            <label>
              Material name
              <input value={name} onChange={(event) => setName(event.target.value)} required autoFocus />
            </label>
            <label>
              Material code
              <input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Optional" />
            </label>
            <label>
              Material family
              <input value={family} onChange={(event) => setFamily(event.target.value)} placeholder="Optional" />
            </label>
            <label>
              Material class
              <select
                value={materialClass}
                onChange={(event) => setMaterialClass(event.target.value as MaterialClass | "")}
                required
              >
                <option value="" disabled>Select a governed class</option>
                {materialClasses.map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
            <label>
              Classification
              <select
                value={classification}
                onChange={(event) => setClassification(event.target.value as DataClassification)}
              >
                {classifications.map((value) => (
                  <option key={value} value={value}>
                    {value.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Description
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
          </label>
          <label>
            Change reason
            <input value={reason} onChange={(event) => setReason(event.target.value)} required />
          </label>
          {error ? <ErrorNotice message={error} /> : null}
          <div className="form-actions">
            <button className="button secondary" type="button" onClick={() => navigate("/materials")}>
              Cancel
            </button>
            <button className="button primary" type="submit" disabled={saving}>
              {saving ? "Creating…" : "Create immutable revision"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function MaterialDetailPage({
  config,
  materialId,
  activeArea,
  navigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  materialId: string;
  activeArea: MaterialArea;
  navigate: Navigate;
  onOpenConnection: () => void;
}) {
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [revisions, setRevisions] = useState<MaterialRevision[]>([]);
  const [materialEtag, setMaterialEtag] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = () => {
    if (!config.accessToken.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    void Promise.all([getMaterialDetail(config, materialId), getMaterialRevisions(config, materialId)])
      .then(([detailResult, revisionResult]) => {
        setDetail(detailResult.data);
        setMaterialEtag(detailResult.etag);
        setRevisions(revisionResult.data.revisions);
      })
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
    // API configuration and identity scope are deliberately part of reload state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, materialId]);

  if (!config.accessToken.trim()) {
    return <ProductSessionBoundary loading={false} onRetry={onOpenConnection} />;
  }
  if (loading && !detail) {
    return <section className="empty-state"><p>Loading Material revision…</p></section>;
  }
  if (error && !detail) {
    return (
      <section className="empty-state">
        <ErrorNotice message={error} />
        <button className="button secondary" type="button" onClick={() => navigate("/materials")}>
          Back to catalog
        </button>
      </section>
    );
  }
  if (!detail) {
    return null;
  }

  const material = detail.material;
  const current = material.current_revision;
  return (
    <div className="page-stack">
      <section className="detail-hero">
        <div>
          <button className="back-link" type="button" onClick={() => navigate("/materials")}>
            ‹ Materials
          </button>
          <p className="eyebrow">Material / {current.classification.replaceAll("_", " ")}</p>
          <h1>{current.content.name}</h1>
          <span className={`material-class-chip ${current.content.material_class}`}>
            {current.content.material_class.replaceAll("_", " ")}
          </span>
          <p className="detail-subtitle">
            {[current.content.material_code, current.content.material_family].filter(Boolean).join(" · ") ||
              "Material catalog entry"}
          </p>
          {current.content.description ? <p>{current.content.description}</p> : null}
        </div>
        <div className="revision-summary">
          <span className="revision-chip">Revision {current.revision_no}</span>
          <strong>{current.lifecycle_state}</strong>
          <small>Recorded {formatDate(current.created_at)}</small>
          <small>Hash {shortId(current.content_hash)}</small>
        </div>
      </section>
      <DomainWorkflowLinks
        config={config}
        target={{
          kind: "material",
          objectId: material.material_id,
          revisionId: current.id,
          label: `${current.content.name} r${current.revision_no}`,
        }}
      />
      {error ? <ErrorNotice message={error} /> : null}
      <nav className="material-context-tabs" aria-label="Material workspace">
        {materialAreas.map((item) => {
          const target = item.area === "overview"
            ? `/materials/${material.material_id}`
            : `/materials/${material.material_id}/${item.area}`;
          return (
            <button
              key={item.area}
              type="button"
              className={item.area === activeArea ? "active" : ""}
              aria-current={item.area === activeArea ? "page" : undefined}
              onClick={() => navigate(target)}
            >
              {item.label}
            </button>
          );
        })}
      </nav>
      {activeArea === "overview" ? (
        <>
          <MaterialRevisionEditor
            key={current.id}
            config={config}
            material={material}
            etag={materialEtag}
            onSaved={reload}
          />
          <section className="detail-grid">
            <article className="content-card provenance-card">
              <p className="eyebrow">Provenance summary</p>
              <h2>Immutable revision fact</h2>
              <dl className="definition-list">
                <div><dt>Revision ID</dt><dd title={current.id}>{shortId(current.id)}</dd></div>
                <div><dt>Based on</dt><dd>{current.based_on_revision_id ? shortId(current.based_on_revision_id) : "Initial revision"}</dd></div>
                <div><dt>Recorded by</dt><dd title={current.created_by}>{shortId(current.created_by)}</dd></div>
                <div><dt>Reason</dt><dd>{current.change_reason}</dd></div>
                <div><dt>Schema</dt><dd>{current.schema_id}</dd></div>
              </dl>
            </article>
            <RevisionHistory
              config={config}
              materialId={material.material_id}
              revisions={revisions}
            />
          </section>
        </>
      ) : null}
      <section className="section-heading inline-heading">
        <div>
          <p className="eyebrow">Material states · {materialAreas.find((item) => item.area === activeArea)?.label}</p>
          <h2>{activeArea === "overview" ? "Manufacturing, heat treatment, and basic properties" : "Work in an exact Material State context"}</h2>
        </div>
      </section>
      {detail.states.length === 0 ? <p className="muted">No Material State is registered yet.</p> : null}
      <div className="state-grid">
        {detail.states.map((state) => (
          <MaterialStateCard
            key={state.material_state_id}
            config={config}
            state={state}
            propertySet={detail.property_sets.find(
              (propertySet) => propertySet.material_state_id === state.material_state_id,
            )}
            materialClass={
              revisions.find(
                (revision) => revision.id === state.current_revision.content.material_revision_id,
              )?.content.material_class ?? "unclassified"
            }
            currentMaterialRevisionId={current.id}
            currentMaterialClass={current.content.material_class}
            activeArea={activeArea}
            onChanged={reload}
          />
        ))}
      </div>
      {activeArea === "overview" ? (
        <MaterialStateCreateForm
          config={config}
          materialId={material.material_id}
          materialRevisionId={current.id}
          onCreated={reload}
        />
      ) : null}
    </div>
  );
}

function MaterialRevisionEditor({
  config,
  material,
  etag,
  onSaved,
}: {
  config: ApiConfig;
  material: MaterialResponse;
  etag: string | null;
  onSaved: () => void;
}) {
  const current = material.current_revision.content;
  const [open, setOpen] = useState(current.material_class === "unclassified");
  const [name, setName] = useState(current.name);
  const [code, setCode] = useState(current.material_code ?? "");
  const [family, setFamily] = useState(current.material_family ?? "");
  const [description, setDescription] = useState(current.description ?? "");
  const [materialClass, setMaterialClass] = useState<MaterialClass | "">(
    current.material_class === "unclassified" ? "" : current.material_class,
  );
  const [reason, setReason] = useState(
    current.material_class === "unclassified"
      ? "Classify legacy Material without changing prior revisions"
      : "Revise Material metadata",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!etag || !materialClass) {
      setError("A current revision ETag and explicit Material class are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await reviseMaterial(config, material.material_id, etag, {
        content: {
          name: name.trim(),
          material_code: blankToNull(code),
          material_family: blankToNull(family),
          description: blankToNull(description),
          material_class: materialClass,
        },
        change_reason: reason.trim(),
      });
      setOpen(false);
      onSaved();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="button secondary" type="button" onClick={() => setOpen(true)}>
        Revise Material metadata
      </button>
    );
  }

  return (
    <section className="content-card">
      <p className="eyebrow">Append-only Material revision</p>
      <h2>{current.material_class === "unclassified" ? "Classify this Material" : "Revise metadata"}</h2>
      <p className="muted">The current and earlier revisions remain immutable.</p>
      <form className="form-stack" onSubmit={submit}>
        <div className="form-grid">
          <label>Material name<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
          <label>Material code<input value={code} onChange={(event) => setCode(event.target.value)} /></label>
          <label>Material family<input value={family} onChange={(event) => setFamily(event.target.value)} /></label>
          <label>
            Material class
            <select value={materialClass} onChange={(event) => setMaterialClass(event.target.value as MaterialClass | "")} required>
              <option value="" disabled>Select a governed class</option>
              {materialClasses.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
        </div>
        <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} /></label>
        <label>Change reason<input value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
        {error ? <ErrorNotice message={error} /> : null}
        <div className="form-actions">
          <button className="button secondary" type="button" onClick={() => setOpen(false)}>Cancel</button>
          <button className="button primary" type="submit" disabled={saving}>{saving ? "Saving…" : "Append revision"}</button>
        </div>
      </form>
    </section>
  );
}

function RevisionHistory({
  config,
  materialId,
  revisions,
}: {
  config: ApiConfig;
  materialId: string;
  revisions: MaterialRevision[];
}) {
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [comparison, setComparison] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (revisions.length > 0) {
      setLeft((current) => current || revisions[0].id);
      setRight((current) => current || revisions.at(-1)?.id || revisions[0].id);
    }
  }, [revisions]);

  async function compare(): Promise<void> {
    if (!left || !right || left === right) {
      setComparison([]);
      return;
    }
    try {
      const result = await compareMaterialRevisions(config, materialId, left, right);
      setComparison(result.data.changed_fields);
      setError(null);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  return (
    <article className="content-card history-card">
      <p className="eyebrow">Revision history</p>
      <h2>{revisions.length} immutable revision{revisions.length === 1 ? "" : "s"}</h2>
      <ol className="revision-list">
        {revisions.map((revision) => (
          <li key={revision.id}>
            <span className="revision-dot" />
            <div>
              <strong>r{revision.revision_no}</strong>
              <small>{formatDate(revision.created_at)} · {revision.change_reason}</small>
            </div>
          </li>
        ))}
      </ol>
      {revisions.length > 1 ? (
        <div className="compare-box">
          <p>Compare concrete revisions</p>
          <div className="compare-controls">
            <select value={left} onChange={(event) => setLeft(event.target.value)} aria-label="Left revision">
              {revisions.map((revision) => <option key={revision.id} value={revision.id}>r{revision.revision_no}</option>)}
            </select>
            <span>to</span>
            <select value={right} onChange={(event) => setRight(event.target.value)} aria-label="Right revision">
              {revisions.map((revision) => <option key={revision.id} value={revision.id}>r{revision.revision_no}</option>)}
            </select>
            <button className="text-button" type="button" onClick={() => void compare()}>Compare</button>
          </div>
          {comparison ? <small>{comparison.length ? `Changed: ${comparison.join(", ")}` : "No content fields changed."}</small> : null}
          {error ? <ErrorNotice message={error} /> : null}
        </div>
      ) : null}
    </article>
  );
}

function MaterialStateCreateForm({
  config,
  materialId,
  materialRevisionId,
  onCreated,
}: {
  config: ApiConfig;
  materialId: string;
  materialRevisionId: string;
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [route, setRoute] = useState("");
  const [heatTreatment, setHeatTreatment] = useState("");
  const [lot, setLot] = useState("");
  const [description, setDescription] = useState("");
  const [reason, setReason] = useState("Initial Material State");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createMaterialState(config, materialId, {
        content: {
          material_revision_id: materialRevisionId,
          name: name.trim(),
          manufacturing_route: blankToNull(route),
          heat_treatment: blankToNull(heatTreatment),
          lot_or_batch: blankToNull(lot),
          description: blankToNull(description),
        },
        change_reason: reason.trim(),
      });
      setOpen(false);
      setName("");
      onCreated();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="add-card" type="button" onClick={() => setOpen(true)}>
        <span>+</span>
        <strong>Add Material State</strong>
        <small>Bind process condition and concrete Material revision</small>
      </button>
    );
  }

  return (
    <section className="content-card create-state-card">
      <div className="section-heading">
        <div><p className="eyebrow">New state</p><h2>Add Material State</h2></div>
        <button className="text-button" type="button" onClick={() => setOpen(false)}>Cancel</button>
      </div>
      <form className="form-stack" onSubmit={submit}>
        <div className="form-grid">
          <label>State name<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
          <label>Manufacturing route<input value={route} onChange={(event) => setRoute(event.target.value)} /></label>
          <label>Heat treatment<input value={heatTreatment} onChange={(event) => setHeatTreatment(event.target.value)} /></label>
          <label>Lot or batch<input value={lot} onChange={(event) => setLot(event.target.value)} /></label>
        </div>
        <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={2} /></label>
        <label>Change reason<input value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
        {error ? <ErrorNotice message={error} /> : null}
        <div className="form-actions"><button className="button primary" type="submit" disabled={saving}>{saving ? "Saving…" : "Create state revision"}</button></div>
      </form>
    </section>
  );
}

function MaterialStateCard({
  config,
  state,
  propertySet,
  materialClass,
  currentMaterialRevisionId,
  currentMaterialClass,
  activeArea,
  onChanged,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse | undefined;
  materialClass: MaterialClass;
  currentMaterialRevisionId: string;
  currentMaterialClass: MaterialClass;
  activeArea: MaterialArea;
  onChanged: () => void;
}) {
  const [editorOpen, setEditorOpen] = useState(false);
  const [rebasing, setRebasing] = useState(false);
  const [rebaseError, setRebaseError] = useState<string | null>(null);
  const content = state.current_revision.content;
  const property = propertySet?.current_revision.content;
  const stateUsesCurrentMaterial = content.material_revision_id === currentMaterialRevisionId;

  async function rebaseState(): Promise<void> {
    setRebasing(true);
    setRebaseError(null);
    const revision = state.current_revision;
    try {
      await reviseMaterialState(
        config,
        state.material_state_id,
        `"revision:${revision.revision_no}:sha256:${revision.content_hash}"`,
        {
          content: {
            material_revision_id: currentMaterialRevisionId,
            name: content.name,
            manufacturing_route: content.manufacturing_route,
            heat_treatment: content.heat_treatment,
            lot_or_batch: content.lot_or_batch,
            description: content.description,
          },
          change_reason: `Rebase State to explicitly classified ${currentMaterialClass} Material revision`,
        },
      );
      onChanged();
    } catch (cause) {
      setRebaseError(errorMessage(cause));
    } finally {
      setRebasing(false);
    }
  }
  return (
    <article className="state-card">
      <div className="state-heading">
        <div>
          <p className="eyebrow">State r{state.current_revision.revision_no}</p>
          <h3>{content.name}</h3>
        </div>
        <span className="revision-chip">draft</span>
      </div>
      <dl className="state-meta">
        <div><dt>Route</dt><dd>{content.manufacturing_route ?? "—"}</dd></div>
        <div><dt>Heat treatment</dt><dd>{content.heat_treatment ?? "—"}</dd></div>
        <div><dt>Lot / batch</dt><dd>{content.lot_or_batch ?? "—"}</dd></div>
      </dl>
      {content.description ? <p className="state-description">{content.description}</p> : null}
      {activeArea === "overview" ? <CatalogGenealogyWorkbench config={config} state={state} /> : null}
      {activeArea === "testing" ? (
        <>
          <TestContextWorkbench config={config} state={state} />
          <GovernedImportWorkbench config={config} state={state} />
        </>
      ) : null}
      {activeArea === "overview" && !stateUsesCurrentMaterial ? (
        <section className="property-summary compatibility-notice">
          <p className="eyebrow">Pinned Material revision</p>
          <h4>This State uses an earlier {materialClass} Material revision</h4>
          <p>
            Append a State revision to adopt the current {currentMaterialClass} classification.
            The earlier State and Material revisions remain unchanged.
          </p>
          {rebaseError ? <ErrorNotice message={rebaseError} /> : null}
          <button className="text-button" type="button" onClick={() => void rebaseState()} disabled={rebasing}>
            {rebasing ? "Appending…" : "Append State revision with current Material"}
          </button>
        </section>
      ) : null}
      {property && propertySet && (activeArea === "overview" || activeArea === "models") ? (
        <>
          <section className="property-summary">
            <div className="section-heading compact-heading">
              <div><p className="eyebrow">Typed property set</p><h4>Basic mechanical properties</h4></div>
              {activeArea === "overview" ? (
                <button className="text-button" type="button" onClick={() => setEditorOpen((value) => !value)}>
                  {editorOpen ? "Close editor" : "Revise"}
                </button>
              ) : null}
            </div>
            <div className="property-grid">
              <div><span>Density</span><strong>{new Intl.NumberFormat().format(property.density_kg_per_m3)} kg/m³</strong></div>
              <div><span>Young&apos;s modulus</span><strong>{formatPressurePa(property.youngs_modulus_pa)}</strong></div>
              <div><span>Poisson&apos;s ratio</span><strong>{property.poisson_ratio}</strong></div>
              <div><span>Yield stress</span><strong>{formatPressurePa(property.yield_stress_pa)}</strong></div>
            </div>
            <small className="source-line">
              Sources: ρ {property.density_source.kind}, E {property.youngs_modulus_source.kind}, ν {property.poisson_ratio_source.kind}
            </small>
          </section>
          {activeArea === "models" ? (
            <ModelToCardWorkflow
              key={propertySet.current_revision.id}
              config={config}
              state={state}
              propertySet={propertySet}
            />
          ) : null}
        </>
      ) : activeArea === "overview" ? (
        <section className="property-summary empty-properties">
          <p className="eyebrow">Typed property set</p>
          <h4>No basic properties yet</h4>
          <p>Add explicit SI values and their source before the reference IR/card workflow.</p>
          <button className="text-button" type="button" onClick={() => setEditorOpen(true)}>Add properties</button>
        </section>
      ) : null}
      {activeArea === "datasets" ? (
        <ReferenceTensileWorkflow config={config} state={state} propertySet={propertySet} />
      ) : null}
      {activeArea === "models" && propertySet ? (
        materialClass === "metal" ? (
          <ReferenceElastoplasticWorkbench
            key={`elastoplastic-${propertySet.current_revision.id}`}
            config={config}
            state={state}
            propertySet={propertySet}
          />
        ) : (
          <section className="property-summary compatibility-notice">
            <p className="eyebrow">Model compatibility</p>
            <h4>Steel elastoplastic workflow unavailable</h4>
            <p>
              This State pins a {materialClass} Material revision. LAW36 and Abaqus isotropic
              plasticity require an explicitly metal-classified revision; no model is inferred
              from its name or family.
            </p>
          </section>
        )
      ) : null}
      {activeArea === "datasets" && propertySet && (materialClass === "polymer" || materialClass === "elastomer") ? (
        <ReferenceShearRelaxationWorkflow config={config} state={state} />
      ) : null}
      {activeArea === "models" && propertySet && (materialClass === "polymer" || materialClass === "elastomer") ? (
        <>
          <ReferenceLinearViscoelasticWorkbench
            key={`linear-viscoelastic-${propertySet.current_revision.id}`}
            config={config}
            state={state}
            propertySet={propertySet}
          />
        </>
      ) : null}
      {activeArea === "models" && propertySet && materialClass === "elastomer" ? (
        <ReferenceOgdenPronyWorkbench
          key={`ogden-prony-${propertySet.current_revision.id}`}
          config={config}
          state={state}
          propertySet={propertySet}
        />
      ) : null}
      {activeArea === "models" ? <ReferenceCalibrationWorkbench config={config} state={state} /> : null}
      {activeArea === "governance" ? <ReferenceValidationWorkbench config={config} state={state} /> : null}
      {activeArea === "overview" && editorOpen ? (
        <PropertySetEditor
          key={propertySet?.property_set_id ?? `new-${state.material_state_id}`}
          config={config}
          state={state}
          propertySet={propertySet}
          onSaved={() => { setEditorOpen(false); onChanged(); }}
        />
      ) : null}
    </article>
  );
}

function PropertySetEditor({
  config,
  state,
  propertySet,
  onSaved,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse | undefined;
  onSaved: () => void;
}) {
  const existing = propertySet?.current_revision.content;
  const [density, setDensity] = useState(String(existing?.density_kg_per_m3 ?? "7850"));
  const [youngsModulusGpa, setYoungsModulusGpa] = useState(String((existing?.youngs_modulus_pa ?? 210_000_000_000) / 1e9));
  const [poissonRatio, setPoissonRatio] = useState(String(existing?.poisson_ratio ?? "0.3"));
  const [yieldStressMpa, setYieldStressMpa] = useState(existing?.yield_stress_pa ? String(existing.yield_stress_pa / 1e6) : "");
  const [sourceKind, setSourceKind] = useState<PropertySourceKind>(existing?.density_source.kind ?? "manual");
  const [sourceReference, setSourceReference] = useState(existing?.density_source.reference ?? "");
  const [temperatureMin, setTemperatureMin] = useState(String(existing?.applicability.temperature_min_k ?? ""));
  const [temperatureMax, setTemperatureMax] = useState(String(existing?.applicability.temperature_max_k ?? ""));
  const [strainRateMin, setStrainRateMin] = useState(String(existing?.applicability.strain_rate_min_per_s ?? ""));
  const [strainRateMax, setStrainRateMax] = useState(String(existing?.applicability.strain_rate_max_per_s ?? ""));
  const [note, setNote] = useState(existing?.applicability.note ?? "");
  const [reason, setReason] = useState(propertySet ? "Revise typed basic properties" : "Initial typed basic properties");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const source = { kind: sourceKind, reference: blankToNull(sourceReference) };
      const yieldStress = optionalNumber(yieldStressMpa);
      const input = {
        content: {
          material_state_revision_id: state.current_revision.id,
          density_kg_per_m3: Number(density),
          density_source: source,
          youngs_modulus_pa: Number(youngsModulusGpa) * 1e9,
          youngs_modulus_source: source,
          poisson_ratio: Number(poissonRatio),
          poisson_ratio_source: source,
          yield_stress_pa: yieldStress === null ? null : yieldStress * 1e6,
          yield_stress_source: yieldStress === null ? null : source,
          applicability: {
            temperature_min_k: optionalNumber(temperatureMin),
            temperature_max_k: optionalNumber(temperatureMax),
            strain_rate_min_per_s: optionalNumber(strainRateMin),
            strain_rate_max_per_s: optionalNumber(strainRateMax),
            note: blankToNull(note),
          },
        },
        change_reason: reason.trim(),
      };
      if (propertySet) {
        const latest = await getPropertySet(config, propertySet.property_set_id);
        if (!latest.etag) {
          throw new ApiError(409, "The property set response did not include the required strong ETag.");
        }
        await revisePropertySet(config, propertySet.property_set_id, latest.etag, input);
      } else {
        await createPropertySet(config, state.material_state_id, input);
      }
      onSaved();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="property-editor">
      <p className="eyebrow">{propertySet ? "Append property revision" : "Initial property revision"}</p>
      <h4>{propertySet ? "Revise basic properties" : "Add basic properties"}</h4>
      <p className="form-hint">Values are stored in SI. This editor applies the selected source independently to each entered core value.</p>
      <form className="form-stack" onSubmit={submit}>
        <div className="form-grid">
          <label>Density (kg/m³)<input type="number" min="0" step="any" value={density} onChange={(event) => setDensity(event.target.value)} required /></label>
          <label>Young&apos;s modulus (GPa)<input type="number" min="0" step="any" value={youngsModulusGpa} onChange={(event) => setYoungsModulusGpa(event.target.value)} required /></label>
          <label>Poisson&apos;s ratio<input type="number" min="-0.999" max="0.499" step="any" value={poissonRatio} onChange={(event) => setPoissonRatio(event.target.value)} required /></label>
          <label>Yield stress (MPa)<input type="number" min="0" step="any" value={yieldStressMpa} onChange={(event) => setYieldStressMpa(event.target.value)} /></label>
          <label>Property source<select value={sourceKind} onChange={(event) => setSourceKind(event.target.value as PropertySourceKind)}>{sourceKinds.map((kind) => <option key={kind} value={kind}>{kind.replaceAll("_", " ")}</option>)}</select></label>
          <label>Source reference<input value={sourceReference} onChange={(event) => setSourceReference(event.target.value)} placeholder="Required except manual entry" /></label>
        </div>
        <details>
          <summary>Applicability range (optional)</summary>
          <div className="form-grid details-grid">
            <label>Minimum temperature (K)<input type="number" min="0" step="any" value={temperatureMin} onChange={(event) => setTemperatureMin(event.target.value)} /></label>
            <label>Maximum temperature (K)<input type="number" min="0" step="any" value={temperatureMax} onChange={(event) => setTemperatureMax(event.target.value)} /></label>
            <label>Minimum strain rate (1/s)<input type="number" min="0" step="any" value={strainRateMin} onChange={(event) => setStrainRateMin(event.target.value)} /></label>
            <label>Maximum strain rate (1/s)<input type="number" min="0" step="any" value={strainRateMax} onChange={(event) => setStrainRateMax(event.target.value)} /></label>
          </div>
          <label>Applicability note<input value={note} onChange={(event) => setNote(event.target.value)} /></label>
        </details>
        <label>Change reason<input value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
        {error ? <ErrorNotice message={error} /> : null}
        <div className="form-actions"><button className="button primary" type="submit" disabled={saving}>{saving ? "Saving…" : propertySet ? "Append property revision" : "Create property set"}</button></div>
      </form>
    </section>
  );
}

const referenceTarget: ExportTarget = {
  solver: "openradioss",
  version: "2025",
  unit_system: "kg_m_s",
};

function readableMappingStatus(status: string): string {
  return status.replaceAll("_", " ");
}

function ModelToCardWorkflow({
  config,
  state,
  propertySet,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse;
}) {
  const [models, setModels] = useState<MaterialModelResponse[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [cards, setCards] = useState<SolverCardResponse[]>([]);
  const [report, setReport] = useState<MappingReport | null>(null);
  const [modelReason, setModelReason] = useState("Create reference Material Model IR");
  const [cardTitle, setCardTitle] = useState(`${state.current_revision.content.name} elastic`);
  const [solverMaterialId, setSolverMaterialId] = useState("1");
  const [cardReason, setCardReason] = useState("Generate OpenRadioss reference card");
  const [targetKey, setTargetKey] = useState("openradioss-2025-kg_m_s");
  const [loadingModels, setLoadingModels] = useState(false);
  const [savingModel, setSavingModel] = useState(false);
  const [runningPreflight, setRunningPreflight] = useState(false);
  const [savingCard, setSavingCard] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewCardId, setPreviewCardId] = useState<string | null>(null);
  const [downloadingCardId, setDownloadingCardId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setLoadingModels(true);
    setError(null);
    void listMaterialModels(config, state.material_state_id)
      .then((result) => {
        if (!current) {
          return;
        }
        setModels(result.data.items);
        setSelectedModelId((selected) => selected || result.data.items[0]?.material_model_id || "");
      })
      .catch((cause: unknown) => current && setError(errorMessage(cause)))
      .finally(() => current && setLoadingModels(false));
    return () => {
      current = false;
    };
  }, [config, state.material_state_id]);

  const selectedModel = models.find((model) => model.material_model_id === selectedModelId) ?? null;

  useEffect(() => {
    if (!selectedModel) {
      setCards([]);
      setReport(null);
      return;
    }
    let current = true;
    setPreview(null);
    setPreviewCardId(null);
    setReport(null);
    void listSolverCards(config, selectedModel.material_model_id)
      .then((result) => current && setCards(result.data.items))
      .catch((cause: unknown) => current && setError(errorMessage(cause)));
    return () => {
      current = false;
    };
  }, [config, selectedModel?.material_model_id]);

  async function createModel(): Promise<void> {
    setSavingModel(true);
    setError(null);
    try {
      const result = await createReferenceMaterialModel(config, state.material_state_id, {
        property_set_revision_id: propertySet.current_revision.id,
        change_reason: modelReason.trim(),
      });
      setModels((current) => [result.data, ...current]);
      setSelectedModelId(result.data.material_model_id);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSavingModel(false);
    }
  }

  async function runPreflight(): Promise<void> {
    if (!selectedModel || targetKey !== "openradioss-2025-kg_m_s") {
      return;
    }
    setRunningPreflight(true);
    setError(null);
    try {
      const result = await preflightSolverCardMapping(
        config,
        selectedModel.material_model_id,
        referenceTarget,
      );
      setReport(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setRunningPreflight(false);
    }
  }

  async function createCard(): Promise<void> {
    if (!selectedModel || !report) {
      return;
    }
    setSavingCard(true);
    setError(null);
    try {
      const result = await createSolverCard(config, selectedModel.material_model_id, {
        material_model_revision_id: selectedModel.current_revision.id,
        target: referenceTarget,
        expected_mapping_report_sha256: report.mapping_report_sha256,
        solver_material_id: Number(solverMaterialId),
        card_title: cardTitle.trim(),
        change_reason: cardReason.trim(),
      });
      setCards((current) => [result.data, ...current]);
      setPreview(null);
      setPreviewCardId(null);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSavingCard(false);
    }
  }

  async function showPreview(card: SolverCardResponse): Promise<void> {
    setError(null);
    try {
      const result = await previewSolverCard(config, card.solver_card_id);
      setPreview(result.data);
      setPreviewCardId(card.solver_card_id);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  async function download(card: SolverCardResponse): Promise<void> {
    setDownloadingCardId(card.solver_card_id);
    setError(null);
    try {
      const result = await downloadSolverCard(config, card.solver_card_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setDownloadingCardId(null);
    }
  }

  return (
    <section className="model-card-workflow" aria-label="Material Model and Solver Card workflow">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">CAE workflow</p>
          <h4>Material Model IR → Solver Card</h4>
        </div>
        <span className="reference-chip">Reference only</span>
      </div>
      <p className="form-hint">
        This narrow workflow creates a solver-neutral, non-production isotropic linear-elastic IR
        from this exact Property Set revision. It never changes the source Material or properties.
      </p>
      {error ? <ErrorNotice message={error} /> : null}
      {loadingModels ? <p className="muted">Loading Material Model IRs…</p> : null}
      {!loadingModels && models.length === 0 ? (
        <div className="workflow-step">
          <strong>1. Create a Material Model IR</strong>
          <small>Uses density, Young&apos;s modulus, and Poisson&apos;s ratio from this frozen Property Set.</small>
          <label>
            Change reason
            <input value={modelReason} onChange={(event) => setModelReason(event.target.value)} required />
          </label>
          <button className="button primary" type="button" onClick={() => void createModel()} disabled={savingModel}>
            {savingModel ? "Creating IR…" : "Create reference IR"}
          </button>
        </div>
      ) : null}
      {models.length > 0 ? (
        <div className="workflow-stack">
          <div className="workflow-step">
            <strong>1. Select immutable Material Model IR</strong>
            <label>
              Material Model revision
              <select
                value={selectedModelId}
                onChange={(event) => setSelectedModelId(event.target.value)}
              >
                {models.map((model) => (
                  <option key={model.material_model_id} value={model.material_model_id}>
                    r{model.current_revision.revision_no} · {shortId(model.current_revision.id)} · reference linear elasticity
                  </option>
                ))}
              </select>
            </label>
            {selectedModel ? (
              <small className="source-line">
                Source Property Set revision {shortId(selectedModel.current_revision.content.property_set_revision_id)}
              </small>
            ) : null}
          </div>
          <div className="workflow-step">
            <strong>2. Choose target and inspect mapping</strong>
            <label>
              Solver target
              <select value={targetKey} onChange={(event) => setTargetKey(event.target.value)}>
                <option value="openradioss-2025-kg_m_s">OpenRadioss 2025 · /MAT/ELAST · kg / m / s</option>
              </select>
            </label>
            <button
              className="button secondary"
              type="button"
              onClick={() => void runPreflight()}
              disabled={!selectedModel || runningPreflight}
            >
              {runningPreflight ? "Checking mapping…" : "Run mapping preflight"}
            </button>
            {report ? <MappingReportPanel report={report} /> : null}
          </div>
          <div className="workflow-step">
            <strong>3. Generate immutable Solver Card</strong>
            <small>Acknowledges the exact mapping report digest shown above; no default or approximation is hidden.</small>
            <div className="form-grid">
              <label>
                Solver material ID
                <input
                  type="number"
                  min="1"
                  max="9999999999"
                  value={solverMaterialId}
                  onChange={(event) => setSolverMaterialId(event.target.value)}
                  required
                />
              </label>
              <label>
                Card title
                <input value={cardTitle} onChange={(event) => setCardTitle(event.target.value)} required />
              </label>
            </div>
            <label>
              Change reason
              <input value={cardReason} onChange={(event) => setCardReason(event.target.value)} required />
            </label>
            <button
              className="button primary"
              type="button"
              onClick={() => void createCard()}
              disabled={!report?.exportable || savingCard}
            >
              {savingCard ? "Generating card…" : "Generate Solver Card"}
            </button>
          </div>
          <SolverCardPanel
            cards={cards}
            preview={preview}
            previewCardId={previewCardId}
            downloadingCardId={downloadingCardId}
            onPreview={showPreview}
            onDownload={download}
          />
        </div>
      ) : null}
    </section>
  );
}

function MappingReportPanel({ report }: { report: MappingReport }) {
  return (
    <section className="mapping-report" aria-label="Solver mapping report">
      <div className="mapping-report-heading">
        <strong>{report.exportable ? "Exportable mapping" : "Mapping requires attention"}</strong>
        <span className={report.exportable ? "mapping-status exact" : "mapping-status unsupported"}>
          {report.exportable ? "exportable" : "blocked"}
        </span>
      </div>
      <small>Report SHA-256: {shortId(report.mapping_report_sha256)}</small>
      <ul className="mapping-list">
        {report.items.map((item) => (
          <li key={item.name}>
            <span className={`mapping-status ${item.status}`}>{readableMappingStatus(item.status)}</span>
            <div>
              <strong>{item.name.replaceAll("_", " ")}</strong>
              <small>{item.detail}</small>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SolverCardPanel({
  cards,
  preview,
  previewCardId,
  downloadingCardId,
  onPreview,
  onDownload,
}: {
  cards: SolverCardResponse[];
  preview: string | null;
  previewCardId: string | null;
  downloadingCardId: string | null;
  onPreview: (card: SolverCardResponse) => Promise<void>;
  onDownload: (card: SolverCardResponse) => Promise<void>;
}) {
  return (
    <section className="solver-card-results">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Generated Solver Cards</p>
          <h4>{cards.length ? `${cards.length} immutable card${cards.length === 1 ? "" : "s"}` : "No Solver Card yet"}</h4>
        </div>
      </div>
      {!cards.length ? <p className="muted">Run a successful mapping preflight, then generate the first card.</p> : null}
      <div className="solver-card-list">
        {cards.map((card) => (
          <article key={card.solver_card_id} className="solver-card-item">
            <div>
              <strong>/MAT/ELAST/{card.solver_material_id}</strong>
              <small>r{card.current_revision.revision_no} · {shortId(card.current_revision.id)} · {card.current_revision.content.card_title}</small>
            </div>
            <div className="card-actions">
              <button className="text-button" type="button" onClick={() => void onPreview(card)}>
                Preview
              </button>
              <button
                className="button secondary"
                type="button"
                onClick={() => void onDownload(card)}
                disabled={downloadingCardId === card.solver_card_id}
              >
                {downloadingCardId === card.solver_card_id ? "Preparing…" : "Download .rad"}
              </button>
            </div>
            {previewCardId === card.solver_card_id && preview ? (
              <pre className="solver-card-preview">{preview}</pre>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

export function App() {
  const [path, navigate] = useLocationPath();
  const [config, setConfig] = useState<ApiConfig>(defaultApiConfig);
  const [sessionStatus, setSessionStatus] = useState<"loading" | "ready" | "signed_out">("loading");
  const [sessionAttempt, setSessionAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    let refreshTimer: number | undefined;

    async function establishSession(): Promise<void> {
      setSessionStatus("loading");
      try {
        const result = await requestLocalDemoAccessToken({ baseUrl: defaultApiConfig.baseUrl });
        if (!current) return;
        setConfig({ ...defaultApiConfig, accessToken: result.data.access_token });
        setSessionStatus("ready");
        const refreshAfter = Math.max(60, result.data.expires_in_seconds - 120) * 1000;
        refreshTimer = window.setTimeout(() => void establishSession(), refreshAfter);
      } catch {
        if (current) setSessionStatus("signed_out");
      }
    }

    void establishSession();
    return () => {
      current = false;
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer);
    };
  }, [sessionAttempt]);

  const retrySession = () => setSessionAttempt((attempt) => attempt + 1);
  const materialRoute = useMemo(() => {
    const match = path.match(/^\/materials\/([^/]+)(?:\/(testing|datasets|models|governance))?$/);
    return match ? {
      materialId: match[1],
      area: (match[2] ?? "overview") as MaterialArea,
    } : null;
  }, [path]);
  const catalogExplorerRoute = useMemo(() => {
    const match = path.match(/^\/catalog\/explorer(?:\/records\/([^/]+)\/revisions\/([^/]+))?$/);
    return match
      ? { recordId: match[1] as string | undefined, revisionId: match[2] as string | undefined }
      : null;
  }, [path]);
  const materialDatabaseRoute = useMemo(() => {
    const match = path.match(/^\/database(?:\/records\/([^/]+)\/revisions\/([^/]+))?$/);
    return match
      ? { recordId: match[1] as string | undefined, revisionId: match[2] as string | undefined }
      : null;
  }, [path]);

  if (sessionStatus !== "ready") {
    return (
      <div className="app-shell session-shell">
        <main><ProductSessionBoundary loading={sessionStatus === "loading"} onRetry={retrySession} /></main>
      </div>
    );
  }

  let page: React.ReactNode;
  if (materialDatabaseRoute) {
    page = (
      <MaterialDatabaseExplorer
        config={config}
        initialRecordId={materialDatabaseRoute.recordId}
        initialRevisionId={materialDatabaseRoute.revisionId}
        onNavigate={navigate}
        onRetry={retrySession}
      />
    );
  } else if (catalogExplorerRoute) {
    page = (
      <CatalogExplorer
        config={config}
        initialRecordId={catalogExplorerRoute.recordId}
        initialRevisionId={catalogExplorerRoute.revisionId}
        onNavigate={navigate}
        onOpenConnection={retrySession}
      />
    );
  } else if (path === "/materials/new") {
    page = <MaterialCreatePage config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (materialRoute) {
    page = <MaterialDetailPage config={config} materialId={materialRoute.materialId} activeArea={materialRoute.area} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/materials") {
    page = <MaterialListPage config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/catalog/schema") {
    page = (
      <ConfigurableCatalogAdmin
        config={config}
        onNavigate={navigate}
        onOpenConnection={retrySession}
      />
    );
  } else if (path === "/catalog/records") {
    page = (
      <ConfigurableCatalogRecords
        config={config}
        onNavigate={navigate}
        onOpenConnection={retrySession}
      />
    );
  } else if (path === "/exports") {
    page = <BulkExportCenter config={config} onOpenConnection={retrySession} />;
  } else if (path === "/tests") {
    page = <ModuleHubPage area="testing" config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/datasets/test-json") {
    page = (
      <CanonicalTestDataWorkbench
        config={config}
        onNavigate={navigate}
        onOpenConnection={retrySession}
      />
    );
  } else if (path === "/datasets/processing") {
    page = (
      <CommonProcessingWorkbench
        config={config}
        onNavigate={navigate}
        onOpenConnection={retrySession}
      />
    );
  } else if (path === "/datasets") {
    page = <ModuleHubPage area="datasets" config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/models") {
    page = <ModuleHubPage area="models" config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/modeling") {
    page = <MaterialModelingWorkspace config={config} onNavigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/governance" || path === "/jobs-reviews") {
    page = <ModuleHubPage area="governance" config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/access" || path === "/administration/access") {
    page = <AdministrationWorkspace config={config} navigate={navigate} onOpenConnection={retrySession} section="access" />;
  } else if (path === "/administration/database") {
    page = <AdministrationWorkspace config={config} navigate={navigate} onOpenConnection={retrySession} section="database" />;
  } else if (path === "/administration") {
    page = <AdministrationWorkspace config={config} navigate={navigate} onOpenConnection={retrySession} section="overview" />;
  } else {
    page = <DashboardPage config={config} navigate={navigate} />;
  }

  return (
    <div className="app-shell">
      <Header path={path} navigate={navigate} />
      <main>
        <Suspense fallback={<p className="loading-state">Loading workspace…</p>}>{page}</Suspense>
      </main>
    </div>
  );
}
