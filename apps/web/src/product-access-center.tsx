import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  getEffectiveProductAccess,
  grantProductAccess,
  listProductAccessAssignments,
  revokeProductAccess,
  type ApiConfig,
} from "./api";
import type {
  DataClassification,
  FeatureGrant,
  ProductAccessAssignment,
  ProductAccessSummary,
  ProductRole,
} from "./types";

const features: Array<{ value: FeatureGrant; label: string; detail: string }> = [
  {
    value: "schema_configuration",
    label: "Schema configuration",
    detail: "Configure Tables, Attributes, Layouts, Subsets, and Link Types.",
  },
  {
    value: "catalog_edit",
    label: "Catalog editing",
    detail: "Create and revise catalog, test, and Dataset records.",
  },
  {
    value: "processing_calibration",
    label: "Processing & calibration",
    detail: "Run Recipes, statistics, fitting, and neutral-model promotion.",
  },
  {
    value: "model_approval",
    label: "Model approval",
    detail: "Review and release governed model results.",
  },
  {
    value: "solver_card_export",
    label: "Solver Card export",
    detail: "Generate cards and canonical bulk packages.",
  },
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Product access could not be loaded.";
}

function subjectLabel(assignment: ProductAccessAssignment): string {
  return assignment.subject_type === "principal"
    ? `Principal ${assignment.principal_id ?? "unknown"}`
    : `${assignment.group_name ?? "unknown group"} · ${assignment.group_issuer ?? "unknown issuer"}`;
}

export function ProductAccessCenter({
  config,
  onOpenConnection,
}: {
  config: ApiConfig;
  onOpenConnection: () => void;
}) {
  const [summary, setSummary] = useState<ProductAccessSummary | null>(null);
  const [assignments, setAssignments] = useState<ProductAccessAssignment[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [subjectType, setSubjectType] = useState<"principal" | "group">("group");
  const [principalId, setPrincipalId] = useState("");
  const [groupIssuer, setGroupIssuer] = useState("urn:cmp:demo-identity");
  const [groupName, setGroupName] = useState("material-users");
  const [productRole, setProductRole] = useState<ProductRole>("user");
  const [selectedFeatures, setSelectedFeatures] = useState<FeatureGrant[]>([
    "catalog_edit",
    "processing_calibration",
    "solver_card_export",
  ]);
  const [classification, setClassification] = useState<Exclude<DataClassification, "export_controlled">>(
    "confidential",
  );
  const [organizationWide, setOrganizationWide] = useState(false);
  const [reason, setReason] = useState("Assign product capabilities for the current project.");

  const load = useCallback(async () => {
    if (!config.accessToken.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const access = await getEffectiveProductAccess(config);
      setSummary(access.data);
      if (access.data.product_role === "administrator") {
        const result = await listProductAccessAssignments(config);
        setAssignments(result.data.items);
      } else {
        setAssignments([]);
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [config]);

  useEffect(() => {
    void load();
  }, [load]);

  function toggleFeature(feature: FeatureGrant): void {
    setSelectedFeatures((current) =>
      current.includes(feature)
        ? current.filter((item) => item !== feature)
        : [...current, feature],
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await grantProductAccess(config, {
        subject_type: subjectType,
        principal_id: subjectType === "principal" ? principalId.trim() : null,
        group_issuer: subjectType === "group" ? groupIssuer.trim() : null,
        group_name: subjectType === "group" ? groupName.trim() : null,
        product_role: productRole,
        feature_grants: productRole === "administrator" ? [] : selectedFeatures,
        max_classification: classification,
        allow_export_controlled: false,
        organization_wide: organizationWide,
        expires_at: null,
        grant_reason: reason.trim(),
      });
      setNotice(`Created ${result.data.product_role} assignment ${result.data.assignment_id.slice(0, 8)}.`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  async function revoke(assignment: ProductAccessAssignment): Promise<void> {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await revokeProductAccess(
        config,
        assignment.assignment_id,
        "Revoke the product assignment from the access administration screen.",
      );
      setNotice(`Revoked assignment ${assignment.assignment_id.slice(0, 8)}.`);
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  if (!config.accessToken.trim()) {
    return (
      <section className="empty-state">
        <p className="eyebrow">Connection required</p>
        <h2>Connect before inspecting product access.</h2>
        <button className="button primary" type="button" onClick={onOpenConnection}>
          Configure connection
        </button>
      </section>
    );
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Access</p>
          <h1>Product roles & feature grants</h1>
          <p>
            Work with Administrator and User roles. Detailed internal permissions remain an
            implementation detail behind these five product capabilities.
          </p>
        </div>
        {summary ? <span className="reference-chip">{summary.product_role}</span> : null}
      </section>

      {error ? <p className="error-notice" role="alert">{error}</p> : null}
      {notice ? <p className="success-notice">{notice}</p> : null}
      {loading ? <p className="loading-state">Loading product access…</p> : null}

      {summary ? (
        <section className="content-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">My access</p>
              <h2>{summary.product_role === "administrator" ? "Administrator" : "User"}</h2>
            </div>
            {summary.legacy_compatible ? <span className="revision-chip">legacy compatible</span> : null}
          </div>
          <div className="metrics-grid">
            {features.map((feature) => {
              const enabled = summary.feature_grants.includes(feature.value);
              return (
                <article className="metric-card" key={feature.value}>
                  <span>{feature.label}</span>
                  <strong>{enabled ? "Enabled" : "Not granted"}</strong>
                  <small>{feature.detail}</small>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      {summary?.product_role === "administrator" ? (
        <>
          <section className="content-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Administrator</p>
                <h2>Assign product access</h2>
              </div>
            </div>
            <form className="form-stack" onSubmit={(event) => void submit(event)}>
              <div className="form-grid">
                <label>
                  Subject type
                  <select value={subjectType} onChange={(event) => setSubjectType(event.target.value as "principal" | "group")}>
                    <option value="group">Identity-provider group</option>
                    <option value="principal">Principal ID</option>
                  </select>
                </label>
                <label>
                  Product role
                  <select value={productRole} onChange={(event) => setProductRole(event.target.value as ProductRole)}>
                    <option value="user">User</option>
                    <option value="administrator">Administrator</option>
                  </select>
                </label>
              </div>
              {subjectType === "group" ? (
                <div className="form-grid">
                  <label>
                    Group issuer
                    <input value={groupIssuer} onChange={(event) => setGroupIssuer(event.target.value)} required />
                  </label>
                  <label>
                    Group name
                    <input value={groupName} onChange={(event) => setGroupName(event.target.value)} required />
                  </label>
                </div>
              ) : (
                <label>
                  Principal ID
                  <input value={principalId} onChange={(event) => setPrincipalId(event.target.value)} required />
                </label>
              )}
              <div className="form-grid">
                <label>
                  Maximum classification
                  <select value={classification} onChange={(event) => setClassification(event.target.value as Exclude<DataClassification, "export_controlled">)}>
                    <option value="internal">Internal</option>
                    <option value="confidential">Confidential</option>
                    <option value="restricted">Restricted</option>
                  </select>
                </label>
                <label className="checkbox-label">
                  <input type="checkbox" checked={organizationWide} onChange={(event) => setOrganizationWide(event.target.checked)} />
                  Organization-wide assignment
                </label>
              </div>
              <fieldset disabled={productRole === "administrator"}>
                <legend>Feature grants</legend>
                <div className="metrics-grid">
                  {features.map((feature) => (
                    <label className="metric-card checkbox-label" key={feature.value}>
                      <input
                        type="checkbox"
                        checked={productRole === "administrator" || selectedFeatures.includes(feature.value)}
                        onChange={() => toggleFeature(feature.value)}
                      />
                      <span>{feature.label}</span>
                      <small>{feature.detail}</small>
                    </label>
                  ))}
                </div>
              </fieldset>
              <label>
                Reason
                <input value={reason} onChange={(event) => setReason(event.target.value)} required />
              </label>
              <button className="button primary" type="submit" disabled={saving}>
                {saving ? "Saving…" : "Create assignment"}
              </button>
            </form>
          </section>

          <section className="content-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Current scope</p>
                <h2>Assignments</h2>
              </div>
              <span className="revision-chip">{assignments.length}</span>
            </div>
            <div className="material-list">
              {assignments.map((assignment) => (
                <article className="material-row" key={assignment.assignment_id}>
                  <span className="material-monogram">{assignment.product_role === "administrator" ? "AD" : "US"}</span>
                  <span className="material-row-main">
                    <strong>{subjectLabel(assignment)}</strong>
                    <small>{assignment.feature_grants.join(" · ") || "read-only user"}</small>
                  </span>
                  <span className="revision-chip">{assignment.product_role}</span>
                  {assignment.revoked_at ? (
                    <span className="mapping-status ignored">revoked</span>
                  ) : (
                    <button className="button secondary" type="button" disabled={saving} onClick={() => void revoke(assignment)}>
                      Revoke
                    </button>
                  )}
                </article>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
