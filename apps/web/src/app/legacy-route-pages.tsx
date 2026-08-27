import { lazy, type FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  createMaterial,
  listMaterials,
} from "../api";
import type {
  DataClassification,
  MaterialClass,
  MaterialResponse,
} from "../types";
import type { Navigate } from "./navigation";
import { ProductSessionBoundary } from "./product-session";
import type { ModuleArea } from "./routes";

/**
 * FE-08A bounded compatibility inventory:
 * - ModuleHubPage is consumed only by the legacy /tests, /datasets, /models and
 *   /governance descriptors. #331 may retire its legacy page grammar only after
 *   canonical feature routes replace those consumers.
 * - MaterialCreatePage is consumed only by /materials/new. It leaves app ownership
 *   when a later approved Materials entry-point migration can use the FE-08B/08C
 *   API and type boundaries without changing the create contract.
 * Root api.ts/types.ts imports intentionally remain for FE-08B and FE-08C.
 */

const OperationsDashboard = lazy(() =>
  import("../operations-dashboard").then((module) => ({
    default: module.OperationsDashboard,
  })),
);
const ReleaseWorkbench = lazy(() =>
  import("../release-workbench").then((module) => ({
    default: module.ReleaseWorkbench,
  })),
);
const GovernanceEvidenceWorkbench = lazy(() =>
  import("../governance-evidence-workbench").then((module) => ({
    default: module.GovernanceEvidenceWorkbench,
  })),
);

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

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "The request could not be completed. Try again in a moment.";
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="error-notice" role="alert">
      {message}
    </div>
  );
}

const moduleHubContent: Record<
  ModuleArea,
  {
    kicker: string;
    title: string;
    description: string;
    action: string;
  }
> = {
  testing: {
    kicker: "Testing",
    title: "Test data",
    description:
      "Open a Material to govern campaigns, instruments, source files, and explicit column/unit mappings.",
    action: "Open test workspace",
  },
  datasets: {
    kicker: "Datasets",
    title: "Datasets & Processing",
    description:
      "Review raw, normalized, processed, statistical, and master-curve representations without replacing source curves.",
    action: "Open dataset workspace",
  },
  models: {
    kicker: "Modeling",
    title: "Material Models & Solver Cards",
    description:
      "Create or calibrate solver-neutral IR revisions, inspect mapping status, and download reference cards.",
    action: "Open model workspace",
  },
  governance: {
    kicker: "Governance",
    title: "Evidence, Review & Release",
    description:
      "Inspect immutable provenance and audit evidence before review, approval, release, or impact analysis.",
    action: "Open Material governance",
  },
};

export function ModuleHubPage({
  area,
  config,
  navigate,
  onOpenConnection,
  locationSearch = "",
}: {
  area: ModuleArea;
  config: ApiConfig;
  navigate: Navigate;
  onOpenConnection: () => void;
  locationSearch?: string;
}) {
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const copy = moduleHubContent[area];
  const governedContext = useMemo(() => {
    if (area !== "governance") return [];
    const query = new URLSearchParams(locationSearch);
    return [
      ["Candidate", query.get("candidate_id"), query.get("candidate_revision_id")],
      ["Validation result", query.get("validation_result_id"), null],
      [
        "Solver Card",
        query.get("solver_card_id"),
        query.get("solver_card_revision_id"),
      ],
    ].filter((entry): entry is [string, string, string | null] =>
      Boolean(entry[1]),
    );
  }, [area, locationSearch]);

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
    return (
      <ProductSessionBoundary loading={false} onRetry={onOpenConnection} />
    );
  }

  return (
    <div className="page-stack">
      <section className="page-heading module-heading">
        <div>
          <p className="eyebrow">{copy.kicker}</p>
          <h1>{copy.title}</h1>
          <p>{copy.description}</p>
        </div>
        {area === "datasets" ? (
          <div className="hero-actions">
            <button
              className="button secondary"
              type="button"
              onClick={() => navigate("/datasets/test-json")}
            >
              Import Test Data JSON
            </button>
            <button
              className="button primary"
              type="button"
              onClick={() => navigate("/datasets/processing")}
            >
              Open Processing Workbench
            </button>
          </div>
        ) : null}
      </section>
      {governedContext.length ? (
        <section
          className="content-card"
          aria-label="Exact Modeling governance context"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">Exact Modeling context</p>
              <h2>Governed objects from the current session</h2>
            </div>
            <button
              className="button secondary"
              type="button"
              onClick={() => navigate("/modeling?stage=review")}
            >
              Return to Review / Release
            </button>
          </div>
          <dl className="evidence-grid">
            {governedContext.map(([label, id, revisionId]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>
                  {id}
                  {revisionId ? ` · revision ${revisionId}` : ""}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
      <section className="content-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Material context</p>
            <h2>Select a Material</h2>
          </div>
          <span className="count-chip">
            {totalCount.toLocaleString()} visible
          </span>
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
                <span
                  className={`material-class-chip ${material.current_revision.content.material_class}`}
                >
                  {material.current_revision.content.material_class}
                </span>
                <h3>{material.current_revision.content.name}</h3>
                <p>
                  {material.current_revision.content.material_code ??
                    material.current_revision.content.material_family ??
                    "No material code"}
                </p>
              </div>
              <button
                className="button secondary"
                type="button"
                onClick={() =>
                  navigate(`/materials/${material.material_id}/${area}`)
                }
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
          <ReleaseWorkbench config={config} />
          <GovernanceEvidenceWorkbench config={config} />
        </>
      ) : null}
    </div>
  );
}

export function MaterialCreatePage({
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
  const [classification, setClassification] =
    useState<DataClassification>("internal");
  const [reason, setReason] = useState("Initial Material catalog entry");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!config.accessToken.trim()) {
    return (
      <ProductSessionBoundary loading={false} onRetry={onOpenConnection} />
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!materialClass) {
      setError(
        "Select a Material class before creating the immutable revision.",
      );
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
            Creates one stable Material identity and its first immutable
            revision. It does not replace an existing record.
          </p>
        </div>
      </section>
      <section className="content-card">
        <form className="form-stack" onSubmit={submit}>
          <div className="form-grid">
            <label>
              Material name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                autoFocus
              />
            </label>
            <label>
              Material code
              <input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="Optional"
              />
            </label>
            <label>
              Material family
              <input
                value={family}
                onChange={(event) => setFamily(event.target.value)}
                placeholder="Optional"
              />
            </label>
            <label>
              Material class
              <select
                value={materialClass}
                onChange={(event) =>
                  setMaterialClass(event.target.value as MaterialClass | "")
                }
                required
              >
                <option value="" disabled>
                  Select a governed class
                </option>
                {materialClasses.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Classification
              <select
                value={classification}
                onChange={(event) =>
                  setClassification(event.target.value as DataClassification)
                }
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
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
            />
          </label>
          <label>
            Change reason
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
            />
          </label>
          {error ? <ErrorNotice message={error} /> : null}
          <div className="form-actions">
            <button
              className="button secondary"
              type="button"
              onClick={() => navigate("/materials")}
            >
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
