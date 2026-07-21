import { lazy, Suspense, type FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  createMaterial,
  getMaterialDetail,
  listMaterials,
  defaultApiConfig,
  requestLocalDemoAccessToken,
} from "./api";
import type {
  DataClassification,
  MaterialClass,
  MaterialResponse,
} from "./types";
import type { MaterialTab } from "./material-library";

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
const GovernedImportRoute = lazy(() =>
  import("./governed-import-route").then((module) => ({
    default: module.GovernedImportRoute,
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
const MaterialSearchPage = lazy(() =>
  import("./material-library").then((module) => ({ default: module.MaterialSearchPage })),
);
const SearchFirstMaterialDetailPage = lazy(() =>
  import("./material-library").then((module) => ({ default: module.MaterialDetailPage })),
);
const SolverCardPreviewPage = lazy(() =>
  import("./material-library").then((module) => ({ default: module.SolverCardPreviewPage })),
);
const ActivityPage = lazy(() =>
  import("./material-library").then((module) => ({ default: module.ActivityPage })),
);

type Navigate = (path: string) => void;
type ModuleArea = "testing" | "datasets" | "models" | "governance";
type LegacyMaterialArea = "testing" | "datasets" | "models" | "governance";

const classifications: DataClassification[] = [
  "internal",
  "confidential",
  "restricted",
  "export_controlled",
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
    if (!window.navigator.userAgent.includes("jsdom") && typeof window.scrollTo === "function") {
      window.scrollTo({ top: 0, left: 0 });
    }
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

function Header({
  path,
  navigate,
}: {
  path: string;
  navigate: Navigate;
}) {
  const navigation = [
    {
      label: "Materials",
      target: "/materials",
      active: path.startsWith("/materials") || path.startsWith("/database") || path.startsWith("/catalog"),
    },
    {
      label: "Modeling",
      target: "/modeling",
      active: path.startsWith("/modeling") || path.startsWith("/datasets") || path.startsWith("/models"),
    },
    {
      label: "Activity",
      target: "/activity",
      active: path.startsWith("/activity") || path.startsWith("/jobs-reviews") || path.startsWith("/governance") || path.startsWith("/exports"),
    },
  ];
  return (
    <header className="app-header">
      <button className="brand" type="button" onClick={() => navigate("/materials")}>
        <span className="brand-mark">CMP</span>
        <span>
          <strong>CAE Material Platform</strong>
          <small>Materials and solver delivery</small>
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
      <details className="product-user-menu">
        <summary>Demo workspace</summary>
        <div>
          <strong>Workspace settings</strong>
          <button type="button" onClick={() => navigate("/administration")}>Administration</button>
          <button type="button" onClick={() => navigate("/database")}>Browse Material Database</button>
        </div>
      </details>
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


function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="error-notice" role="alert">
      {message}
    </div>
  );
}


const moduleHubContent: Record<ModuleArea, {
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
  area: ModuleArea;
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


export function App() {
  const [path, navigate] = useLocationPath();
  const [config, setConfig] = useState<ApiConfig>(defaultApiConfig);
  const [sessionStatus, setSessionStatus] = useState<"loading" | "ready" | "signed_out">("loading");
  const [sessionAttempt, setSessionAttempt] = useState(0);

  useEffect(() => {
    if (path !== "/") return;
    window.history.replaceState({}, "", "/materials");
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, [path]);

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
  const legacyMaterialRoute = useMemo(() => {
    const match = path.match(/^\/materials\/([^/]+)\/(testing|datasets|models|governance)$/);
    return match ? {
      materialId: match[1],
      area: match[2] as LegacyMaterialArea,
    } : null;
  }, [path]);
  const searchFirstMaterialRoute = useMemo(() => {
    const match = path.match(/^\/materials\/([^/]+)(?:\/(overview|properties|curves|cards|evidence))?$/);
    return match ? { materialId: match[1], tab: (match[2] ?? "overview") as MaterialTab } : null;
  }, [path]);
  const solverCardRoute = useMemo(() => {
    const match = path.match(/^\/materials\/([^/]+)\/cards\/([^/]+)$/);
    return match ? { materialId: match[1], cardId: match[2] } : null;
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
  if (solverCardRoute) {
    page = <SolverCardPreviewPage config={config} materialId={solverCardRoute.materialId} cardId={solverCardRoute.cardId} onNavigate={navigate} />;
  } else if (materialDatabaseRoute) {
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
  } else if (searchFirstMaterialRoute) {
    page = <SearchFirstMaterialDetailPage config={config} materialId={searchFirstMaterialRoute.materialId} activeTab={searchFirstMaterialRoute.tab} onNavigate={navigate} />;
  } else if (legacyMaterialRoute) {
    const legacyTab: Record<LegacyMaterialArea, MaterialTab> = {
      testing: "curves",
      datasets: "curves",
      models: "cards",
      governance: "evidence",
    };
    page = <SearchFirstMaterialDetailPage config={config} materialId={legacyMaterialRoute.materialId} activeTab={legacyTab[legacyMaterialRoute.area]} onNavigate={navigate} />;
  } else if (path === "/materials") {
    page = <MaterialSearchPage config={config} onNavigate={navigate} />;
  } else if (path === "/catalog/schema") {
    page = <AdministrationWorkspace config={config} navigate={navigate} onOpenConnection={retrySession} section="database" />;
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
  } else if (path === "/datasets/import") {
    page = (
      <GovernedImportRoute
        config={config}
        onNavigate={navigate}
        onOpenConnection={retrySession}
      />
    );
  } else if (path === "/datasets/processing") {
    page = <MaterialModelingWorkspace config={config} onNavigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/datasets") {
    page = <ModuleHubPage area="datasets" config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/models") {
    page = <ModuleHubPage area="models" config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/modeling") {
    page = <MaterialModelingWorkspace config={config} onNavigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/activity") {
    page = <ActivityPage onNavigate={navigate} />;
  } else if (path === "/governance" || path === "/jobs-reviews") {
    page = <ModuleHubPage area="governance" config={config} navigate={navigate} onOpenConnection={retrySession} />;
  } else if (path === "/access" || path === "/administration/access") {
    page = <AdministrationWorkspace config={config} navigate={navigate} onOpenConnection={retrySession} section="access" />;
  } else if (path === "/administration/database") {
    page = <AdministrationWorkspace config={config} navigate={navigate} onOpenConnection={retrySession} section="database" />;
  } else if (path === "/administration") {
    page = <AdministrationWorkspace config={config} navigate={navigate} onOpenConnection={retrySession} section="overview" />;
  } else {
    page = <MaterialSearchPage config={config} onNavigate={navigate} />;
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
