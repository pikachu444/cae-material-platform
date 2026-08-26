import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  EngineeringPane,
  SemanticStatus,
  SemanticText,
  WorkbenchMessage,
} from "../../../design/semantic-ui";
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
} from "./model";

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

const rolePresets: Record<ProductRole, { label: string; tasks: string; grants: FeatureGrant[] }> = {
  user: {
    label: "User",
    tasks: "Find, view, download, request review, and process or fit material data.",
    grants: ["processing_calibration", "solver_card_export"],
  },
  reviewer: {
    label: "Reviewer",
    tasks: "Do User work and request changes, approve, or publish material and Solver Card reviews.",
    grants: ["processing_calibration", "model_approval", "solver_card_export"],
  },
  administrator: {
    label: "Administrator",
    tasks: "Configure the workspace and manage all material, review, publication, and access work.",
    grants: features.map((feature) => feature.value),
  },
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Product access could not be loaded.";
}

function subjectLabel(assignment: ProductAccessAssignment): string {
  return assignment.subject_type === "principal"
    ? assignment.principal_id ?? "Unknown member"
    : assignment.group_name ?? "Unknown member";
}

function featureLabel(value: FeatureGrant): string {
  return features.find((feature) => feature.value === value)?.label ?? value;
}

export function ProductAccessCenter({
  config,
  onOpenConnection,
  productMode = false,
}: {
  config: ApiConfig;
  onOpenConnection: () => void;
  productMode?: boolean;
}) {
  const [summary, setSummary] = useState<ProductAccessSummary | null>(null);
  const [assignments, setAssignments] = useState<ProductAccessAssignment[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [assignmentEditorOpen, setAssignmentEditorOpen] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<ProductAccessAssignment | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [subjectType, setSubjectType] = useState<"principal" | "group">("group");
  const [principalId, setPrincipalId] = useState("");
  const [groupIssuer, setGroupIssuer] = useState("urn:cmp:demo-identity");
  const [groupName, setGroupName] = useState("material-users");
  const [productRole, setProductRole] = useState<ProductRole>("user");
  const [classification, setClassification] = useState<Exclude<DataClassification, "export_controlled">>(
    "confidential",
  );
  const [organizationWide, setOrganizationWide] = useState(false);
  const [reason, setReason] = useState("Grant role-based access for the current project.");

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
        feature_grants: rolePresets[productRole].grants,
        max_classification: classification,
        allow_export_controlled: false,
        organization_wide: organizationWide,
        expires_at: null,
        grant_reason: reason.trim(),
      });
      setNotice(`Access granted to ${subjectLabel(result.data)}.`);
      setAssignmentEditorOpen(false);
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
        revokeReason.trim(),
      );
      setNotice(`Access removed from ${subjectLabel(assignment)}. The assignment remains in history.`);
      setRevokeTarget(null);
      setRevokeReason("");
      await load();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  if (!config.accessToken.trim()) {
    return (
      <EngineeringPane className="access-auth-required" label="Product access sign-in">
        <SemanticText semanticRole="sectionHeading">Sign in before inspecting product access.</SemanticText>
        <button className="ux-button primary" type="button" onClick={onOpenConnection}>
          Try again
        </button>
      </EngineeringPane>
    );
  }

  const activeAssignments = assignments.filter((assignment) => !assignment.revoked_at);
  const activeAssignmentCount = `${activeAssignments.length} active ${activeAssignments.length === 1 ? "assignment" : "assignments"}`;

  return (
    <div className={productMode ? "administration-access-workbench" : "page-stack"}>
      {!productMode ? <section className="page-heading">
        <div>
          <h2>Product roles & feature grants</h2>
          <p>
            Assign a task-based User, Reviewer, or Administrator role. Detailed enforcement stays
            behind this workspace setting.
          </p>
        </div>
        {summary ? <span className="reference-chip">{summary.product_role}</span> : null}
      </section> : null}

      {error ? <WorkbenchMessage kind="error" title="Access action failed">{error}</WorkbenchMessage> : null}
      {notice ? <SemanticStatus status="success" label={notice} /> : null}
      {loading ? <WorkbenchMessage kind="loading" title="Loading access">Reading current assignments…</WorkbenchMessage> : null}

      {summary && !productMode ? (
        <section className="content-card">
          <div className="section-heading">
            <div>
              <h2>{rolePresets[summary.product_role].label}</h2>
            </div>
            {!productMode && summary.legacy_compatible ? <span className="revision-chip">legacy compatible</span> : null}
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
          {(!productMode || assignmentEditorOpen) ? <EngineeringPane className={productMode ? "access-assignment-panel" : "content-card"} label="Grant access">
            <div className="section-heading">
              <SemanticText semanticRole="sectionHeading">Grant access</SemanticText>
              {productMode ? <button className="ux-button tertiary" type="button" onClick={() => setAssignmentEditorOpen(false)}>Close</button> : null}
            </div>
            <form className="ux-form product-access-form" onSubmit={(event) => void submit(event)}>
              <div className="ux-field-grid">
                <label className="ux-field">
                  Member type
                  <select className="ux-select" value={subjectType} onChange={(event) => setSubjectType(event.target.value as "principal" | "group")}>
                    <option value="group">Team</option>
                    <option value="principal">User ID</option>
                  </select>
                </label>
                <label className="ux-field">
                  Role
                  <select className="ux-select" aria-describedby="role-permissions" value={productRole} onChange={(event) => setProductRole(event.target.value as ProductRole)}>
                    <option value="user">User</option>
                    <option value="reviewer">Reviewer</option>
                    <option value="administrator">Administrator</option>
                  </select>
                </label>
              </div>
              <div className="access-effective-grants" id="role-permissions" aria-live="polite">
                <SemanticText semanticRole="label">Permissions</SemanticText>
                <SemanticText semanticRole="value">{rolePresets[productRole].grants.map(featureLabel).join(" · ")}</SemanticText>
              </div>
              {subjectType === "group" ? (
                <>
                  <label className="ux-field">
                    Team name
                    <input className="ux-input" value={groupName} onChange={(event) => setGroupName(event.target.value)} required />
                  </label>
                  <details className="ux-disclosure access-advanced">
                    <summary>Advanced</summary>
                    <label className="ux-field">
                      Identity provider
                      <input className="ux-input" value={groupIssuer} onChange={(event) => setGroupIssuer(event.target.value)} required />
                    </label>
                  </details>
                </>
              ) : (
                <label className="ux-field">
                  User ID
                  <input className="ux-input" value={principalId} onChange={(event) => setPrincipalId(event.target.value)} required />
                </label>
              )}
              <div className="ux-field-grid">
                <label className="ux-field">
                  Maximum classification
                  <select className="ux-select" value={classification} onChange={(event) => setClassification(event.target.value as Exclude<DataClassification, "export_controlled">)}>
                    <option value="internal">Internal</option>
                    <option value="confidential">Confidential</option>
                    <option value="restricted">Restricted</option>
                  </select>
                </label>
                <label className="ux-checkbox">
                  <input type="checkbox" checked={organizationWide} onChange={(event) => setOrganizationWide(event.target.checked)} />
                  Grant across the organization
                </label>
              </div>
              <label className="ux-field">
                Reason
                <input className="ux-input" value={reason} onChange={(event) => setReason(event.target.value)} required />
              </label>
              <div className="ux-action-row">
                <button className="ux-button primary" type="submit" disabled={saving} aria-busy={saving}>
                  {saving ? "Granting…" : "Grant access"}
                </button>
              </div>
            </form>
          </EngineeringPane> : null}

          <EngineeringPane className={productMode ? "access-assignments-table" : "content-card access-assignments-table"} label="Active access assignments">
            <div className="section-heading">
              <div>
                <SemanticText semanticRole="sectionHeading">Access</SemanticText>
                <SemanticText semanticRole="metadata">{activeAssignmentCount}</SemanticText>
              </div>
              {productMode && !assignmentEditorOpen && !revokeTarget ? <button className="ux-button primary" type="button" onClick={() => setAssignmentEditorOpen(true)}>Grant access</button> : null}
            </div>
            <div className="assignment-table" role="table" aria-label="Access grants">
              <div className="assignment-table-heading" role="row">
                <span role="columnheader">Member</span>
                <span role="columnheader">Role</span>
                <span role="columnheader">Permissions</span>
                <span role="columnheader">Action</span>
              </div>
              {activeAssignments.map((assignment) => (
                <div className="assignment-table-row" role="row" key={assignment.assignment_id}>
                  <span className="assignment-subject" role="cell">
                    <strong>{assignment.subject_type === "group" ? assignment.group_name : assignment.principal_id}</strong>
                  </span>
                  <span role="cell">{rolePresets[assignment.product_role].label}</span>
                  <span className="assignment-capabilities" role="cell">
                    <small>{assignment.feature_grants.map(featureLabel).join(" · ") || "Read-only user"}</small>
                  </span>
                  <span role="cell"><button className="ux-button danger" type="button" disabled={saving} onClick={() => { setRevokeTarget(assignment); setRevokeReason(""); }}>
                      Remove access
                    </button></span>
                </div>
              ))}
            </div>
          </EngineeringPane>
          {revokeTarget ? (
            <EngineeringPane className={productMode ? "access-revoke-panel" : "content-card access-revoke-panel"} label="Remove access">
              <div className="section-heading">
                <SemanticText semanticRole="sectionHeading">Remove access for {subjectLabel(revokeTarget)}?</SemanticText>
                <button className="ux-button tertiary" type="button" onClick={() => setRevokeTarget(null)}>Cancel</button>
              </div>
              <label className="ux-field">
                Reason
                <input className="ux-input" value={revokeReason} onChange={(event) => setRevokeReason(event.target.value)} required />
              </label>
              <div className="ux-action-row">
                <button className="ux-button danger" type="button" disabled={saving || !revokeReason.trim()} onClick={() => void revoke(revokeTarget)}>Remove access</button>
              </div>
            </EngineeringPane>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
