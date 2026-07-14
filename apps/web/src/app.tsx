import { type FormEvent, useEffect, useMemo, useState } from "react";
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
  loadApiConfig,
  preflightSolverCardMapping,
  previewSolverCard,
  requestLocalDemoAccessToken,
  revisePropertySet,
  saveApiConfig,
} from "./api";
import { ReferenceTensileWorkflow } from "./reference-tensile-workflow";
import { ReferenceElastoplasticWorkbench } from "./reference-elastoplastic-workbench";
import { ReferenceCalibrationWorkbench } from "./reference-calibration-workbench";
import { ReferenceValidationWorkbench } from "./reference-validation-workbench";
import { ReviewWorkbench } from "./review-workbench";
import { ReleaseWorkbench } from "./release-workbench";
import { GovernanceEvidenceWorkbench } from "./governance-evidence-workbench";
import type {
  DataClassification,
  ExportTarget,
  MaterialDetail,
  MaterialModelResponse,
  MaterialResponse,
  MaterialRevision,
  MaterialStateResponse,
  MappingReport,
  PropertySetResponse,
  PropertySourceKind,
  SolverCardResponse,
} from "./types";

type Navigate = (path: string) => void;

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
    setPath(nextPath);
  };
  return [path, navigate];
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return "The catalog request could not be completed. Check the API connection and try again.";
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
  connected,
  onOpenConnection,
}: {
  path: string;
  navigate: Navigate;
  connected: boolean;
  onOpenConnection: () => void;
}) {
  const isMaterials = path === "/materials" || path.startsWith("/materials/");
  return (
    <header className="app-header">
      <button className="brand" type="button" onClick={() => navigate("/")}>
        <span className="brand-mark">CMP</span>
        <span>
          <strong>CAE Material Platform</strong>
          <small>Material Catalog · reference workflow</small>
        </span>
      </button>
      <nav aria-label="Primary navigation">
        <button
          className={path === "/" ? "nav-link active" : "nav-link"}
          type="button"
          onClick={() => navigate("/")}
        >
          Dashboard
        </button>
        <button
          className={isMaterials ? "nav-link active" : "nav-link"}
          type="button"
          onClick={() => navigate("/materials")}
        >
          Materials
        </button>
      </nav>
      <button className="connection-button" type="button" onClick={onOpenConnection}>
        <span className={connected ? "connection-dot online" : "connection-dot"} />
        {connected ? "Connected token" : "Connection"}
      </button>
    </header>
  );
}

function ConnectionPanel({
  config,
  open,
  onClose,
  onSave,
}: {
  config: ApiConfig;
  open: boolean;
  onClose: () => void;
  onSave: (value: ApiConfig) => void;
}) {
  const [baseUrl, setBaseUrl] = useState(config.baseUrl);
  const [accessToken, setAccessToken] = useState(config.accessToken);
  const [requestingDemoToken, setRequestingDemoToken] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setBaseUrl(config.baseUrl);
      setAccessToken(config.accessToken);
      setDemoError(null);
    }
  }, [config, open]);

  if (!open) {
    return null;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave({
      baseUrl: baseUrl.trim().replace(/\/$/, "") || "/api/v1",
      accessToken: accessToken.trim(),
    });
    onClose();
  }

  async function useLocalDemoIdentity(): Promise<void> {
    setRequestingDemoToken(true);
    setDemoError(null);
    try {
      const normalizedBaseUrl = baseUrl.trim().replace(/\/$/, "") || "/api/v1";
      const token = await requestLocalDemoAccessToken({ baseUrl: normalizedBaseUrl });
      setBaseUrl(normalizedBaseUrl);
      setAccessToken(token.data.access_token);
    } catch (cause) {
      setDemoError(
        cause instanceof ApiError
          ? "The local demo identity is unavailable for this API endpoint."
          : "The local demo identity could not be requested.",
      );
    } finally {
      setRequestingDemoToken(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="connection-panel" aria-labelledby="connection-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Tenant-aware connection</p>
            <h2 id="connection-title">API connection</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close connection settings">
            ×
          </button>
        </div>
        <p className="muted">
          The workbench sends the bearer token only to this API endpoint. It does not create a
          development bypass for authorization, tenant scope, or classification RLS.
        </p>
        <form onSubmit={submit} className="form-stack">
          <label>
            API base URL
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="/api/v1 or http://127.0.0.1:8000/api/v1"
              required
            />
          </label>
          <label>
            Bearer access token
            <textarea
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              placeholder="Paste a short-lived OIDC access token"
              rows={5}
            />
          </label>
          <p className="form-hint">
            Stored only in this browser&apos;s local storage for local development. Production identity
            integration remains an operator concern.
          </p>
          <div className="demo-identity-action">
            <button
              className="button secondary"
              type="button"
              onClick={() => void useLocalDemoIdentity()}
              disabled={requestingDemoToken}
            >
              {requestingDemoToken ? "Requesting demo token…" : "Use local demo identity"}
            </button>
            <small>
              Available only from the explicit Docker Compose demo; it still uses signed JWT,
              authorization, and tenant RLS.
            </small>
          </div>
          {demoError ? <p className="error-notice" role="alert">{demoError}</p> : null}
          <div className="form-actions">
            <button className="button secondary" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="button primary" type="submit">
              Save connection
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function ConnectionRequired({ onOpenConnection }: { onOpenConnection: () => void }) {
  return (
    <section className="empty-state">
      <p className="eyebrow">Connection required</p>
      <h2>Connect this workbench to the protected Material Catalog.</h2>
      <p>
        Use a short-lived OIDC access token with an organization and project claim. Material data is
        never shown before the API applies its authorization and RLS policy.
      </p>
      <button className="button primary" type="button" onClick={onOpenConnection}>
        Configure connection
      </button>
    </section>
  );
}

function DashboardPage({
  config,
  navigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  navigate: Navigate;
  onOpenConnection: () => void;
}) {
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!config.accessToken.trim()) {
      setMaterials([]);
      return;
    }
    let current = true;
    setLoading(true);
    setError(null);
    void listMaterials(config, "")
      .then((result) => {
        if (current) {
          setMaterials(result.data.items.slice(0, 5));
        }
      })
      .catch((reason: unknown) => current && setError(errorMessage(reason)))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
  }, [config]);

  if (!config.accessToken.trim()) {
    return <ConnectionRequired onOpenConnection={onOpenConnection} />;
  }

  return (
    <div className="page-stack">
      <section className="hero-card">
        <div>
          <p className="eyebrow">Product vertical slice</p>
          <h1>Material data, made ready for CAE.</h1>
          <p>
            Register a Material, bind a manufacturing state, record typed basic properties, and retain
            immutable revision provenance. The same Material State can then create a reference IR,
            inspect an explicit OpenRadioss mapping, and download its immutable Solver Card.
          </p>
        </div>
        <div className="hero-actions">
          <button className="button primary" type="button" onClick={() => navigate("/materials/new")}>
            Create material
          </button>
          <button className="button secondary" type="button" onClick={() => navigate("/materials")}>
            Browse catalog
          </button>
        </div>
      </section>
      <section className="metrics-grid" aria-label="Catalog summary">
        <article className="metric-card">
          <span>Visible materials</span>
          <strong>{loading ? "…" : materials.length}</strong>
          <small>Current tenant and classification scope</small>
        </article>
        <article className="metric-card">
          <span>Core property model</span>
          <strong>Typed</strong>
          <small>ρ, E, ν, optional yield stress — SI units</small>
        </article>
        <article className="metric-card">
          <span>Revision policy</span>
          <strong>Immutable</strong>
          <small>Stable identity points to an append-only head</small>
        </article>
      </section>
      <section className="content-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Catalog</p>
            <h2>Recently visible materials</h2>
          </div>
          <button className="text-button" type="button" onClick={() => navigate("/materials")}>
            View all
          </button>
        </div>
        {error ? <ErrorNotice message={error} /> : null}
        {loading ? <p className="muted">Loading catalog…</p> : null}
        {!loading && !error && materials.length === 0 ? (
          <p className="muted">No Material is visible in this tenant yet. Create the first one.</p>
        ) : null}
        <div className="material-list compact">
          {materials.map((material) => (
            <MaterialRow key={material.material_id} material={material} navigate={navigate} />
          ))}
        </div>
      </section>
      <ReviewWorkbench config={config} />
      <ReleaseWorkbench config={config} />
      <GovernanceEvidenceWorkbench config={config} />
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
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (nextQuery: string) => {
    if (!config.accessToken.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    void listMaterials(config, nextQuery)
      .then((result) => setMaterials(result.data.items))
      .catch((reason: unknown) => setError(errorMessage(reason)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load("");
    // Reload only when an explicit connection is saved; searches run on form submit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config]);

  if (!config.accessToken.trim()) {
    return <ConnectionRequired onOpenConnection={onOpenConnection} />;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    load(query);
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
          <button className="button secondary" type="submit">
            Search
          </button>
        </form>
        {error ? <ErrorNotice message={error} /> : null}
        {loading ? <p className="muted">Loading materials…</p> : null}
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
  const [description, setDescription] = useState("");
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [reason, setReason] = useState("Initial Material catalog entry");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!config.accessToken.trim()) {
    return <ConnectionRequired onOpenConnection={onOpenConnection} />;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
  navigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  materialId: string;
  navigate: Navigate;
  onOpenConnection: () => void;
}) {
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [revisions, setRevisions] = useState<MaterialRevision[]>([]);
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
    return <ConnectionRequired onOpenConnection={onOpenConnection} />;
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
      {error ? <ErrorNotice message={error} /> : null}
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
      <section className="section-heading inline-heading">
        <div>
          <p className="eyebrow">Material states</p>
          <h2>Manufacturing, heat treatment, and basic properties</h2>
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
            onChanged={reload}
          />
        ))}
      </div>
      <MaterialStateCreateForm
        config={config}
        materialId={material.material_id}
        materialRevisionId={current.id}
        onCreated={reload}
      />
    </div>
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
  onChanged,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse | undefined;
  onChanged: () => void;
}) {
  const [editorOpen, setEditorOpen] = useState(false);
  const content = state.current_revision.content;
  const property = propertySet?.current_revision.content;
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
      {property && propertySet ? (
        <>
          <section className="property-summary">
            <div className="section-heading compact-heading">
              <div><p className="eyebrow">Typed property set</p><h4>Basic mechanical properties</h4></div>
              <button className="text-button" type="button" onClick={() => setEditorOpen((value) => !value)}>
                {editorOpen ? "Close editor" : "Revise"}
              </button>
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
          <ModelToCardWorkflow
            key={propertySet.current_revision.id}
            config={config}
            state={state}
            propertySet={propertySet}
          />
        </>
      ) : (
        <section className="property-summary empty-properties">
          <p className="eyebrow">Typed property set</p>
          <h4>No basic properties yet</h4>
          <p>Add explicit SI values and their source before the reference IR/card workflow.</p>
          <button className="text-button" type="button" onClick={() => setEditorOpen(true)}>Add properties</button>
        </section>
      )}
      <ReferenceTensileWorkflow config={config} state={state} />
      {propertySet ? (
        <ReferenceElastoplasticWorkbench
          key={`elastoplastic-${propertySet.current_revision.id}`}
          config={config}
          state={state}
          propertySet={propertySet}
        />
      ) : null}
      <ReferenceCalibrationWorkbench config={config} state={state} />
      <ReferenceValidationWorkbench config={config} state={state} />
      {editorOpen ? (
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
  const [config, setConfig] = useState<ApiConfig>(() => loadApiConfig());
  const [connectionOpen, setConnectionOpen] = useState(false);
  const materialId = useMemo(() => {
    const match = path.match(/^\/materials\/([^/]+)$/);
    return match?.[1] ?? null;
  }, [path]);

  function persistConfig(nextConfig: ApiConfig): void {
    saveApiConfig(nextConfig);
    setConfig(nextConfig);
  }

  let page: React.ReactNode;
  if (path === "/materials/new") {
    page = <MaterialCreatePage config={config} navigate={navigate} onOpenConnection={() => setConnectionOpen(true)} />;
  } else if (materialId) {
    page = <MaterialDetailPage config={config} materialId={materialId} navigate={navigate} onOpenConnection={() => setConnectionOpen(true)} />;
  } else if (path === "/materials") {
    page = <MaterialListPage config={config} navigate={navigate} onOpenConnection={() => setConnectionOpen(true)} />;
  } else {
    page = <DashboardPage config={config} navigate={navigate} onOpenConnection={() => setConnectionOpen(true)} />;
  }

  return (
    <div className="app-shell">
      <Header path={path} navigate={navigate} connected={Boolean(config.accessToken.trim())} onOpenConnection={() => setConnectionOpen(true)} />
      <main>{page}</main>
      <ConnectionPanel config={config} open={connectionOpen} onClose={() => setConnectionOpen(false)} onSave={persistConfig} />
    </div>
  );
}
