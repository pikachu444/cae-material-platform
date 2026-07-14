import { type FormEvent, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  getAuditIntegrity,
  getProvenanceCompleteness,
  getProvenanceEntity,
  getProvenanceImpact,
  getProvenanceLineage,
  listAuditEvents,
} from "./api";
import type {
  AuditEvent,
  AuditIntegrityReport,
  AuditOutcome,
  ProvenanceCompletenessReport,
  ProvenanceEntityResponse,
  ProvenanceLineagePage,
} from "./types";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return error instanceof Error ? error.message : "Governance evidence could not be loaded.";
}

function shortId(value: string): string {
  return value.length > 18 ? `${value.slice(0, 8)}??{value.slice(-8)}` : value;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function GraphResult({ page, title }: { page: ProvenanceLineagePage; title: string }) {
  return (
    <section className="evidence-result" aria-label={title}>
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">{page.direction} evidence</p>
          <h4>{title}</h4>
        </div>
        <span className="reference-chip">{page.nodes.length} visible nodes</span>
      </div>
      <p className="source-line">
        Discovered {page.total_discovered.toLocaleString()} node{page.total_discovered === 1 ? "" : "s"}
        {page.graph_truncated ? "; graph limit reached" : "; bounded graph complete"}.
      </p>
      {page.graph_truncated ? (
        <p className="warning-notice">The graph was truncated by the bounded query policy. Do not treat this page as a complete dependency graph.</p>
      ) : null}
      <ul className="evidence-node-list">
        {page.nodes.map((node) => (
          <li key={node.entity_id}>
            <div>
              <strong>{node.entity_type}</strong>
              <small>
                depth {node.depth} · {node.reference.kind} · {shortId(node.reference.id)} · {node.completeness.state}
              </small>
            </div>
            <span className="reference-chip">{node.via_relation ?? "root"}</span>
          </li>
        ))}
      </ul>
      {!page.nodes.length ? <p className="muted">No visible nodes were returned in this tenant and classification scope.</p> : null}
    </section>
  );
}

function EntitySummary({ entity }: { entity: ProvenanceEntityResponse }) {
  return (
    <section className="evidence-result" aria-label="Provenance entity summary">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Pinned immutable entity</p>
          <h4>{entity.entity_type}</h4>
        </div>
        <span className={`mapping-status ${entity.completeness.state === "complete" ? "exact" : "unsupported"}`}>
          {entity.completeness.state}
        </span>
      </div>
      <dl className="state-meta">
        <div><dt>Entity</dt><dd>{shortId(entity.entity_id)}</dd></div>
        <div><dt>Reference</dt><dd>{entity.reference.kind} · {shortId(entity.reference.id)}</dd></div>
        <div><dt>Scope</dt><dd>{shortId(entity.organization_id)} · {shortId(entity.project_id)}</dd></div>
        <div><dt>Content SHA-256</dt><dd>{shortId(entity.reference.sha256)}</dd></div>
      </dl>
      {entity.completeness.issues.length ? (
        <ul className="qc-list" aria-label="Entity completeness issues">
          {entity.completeness.issues.map((issue) => <li key={issue} className="failed">{issue}</li>)}
        </ul>
      ) : <p className="muted">No entity-level completeness issue is recorded.</p>}
    </section>
  );
}

function AuditSummary({ integrity }: { integrity: AuditIntegrityReport }) {
  return (
    <section className="evidence-result" aria-label="Audit integrity summary">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Append-only chain</p>
          <h4>Audit integrity</h4>
        </div>
        <span className={`mapping-status ${integrity.state === "valid" ? "exact" : "unsupported"}`}>
          {integrity.state}
        </span>
      </div>
      <dl className="metric-grid">
        <div><dt>Events</dt><dd>{integrity.event_count.toLocaleString()}</dd></div>
        <div><dt>Last sequence</dt><dd>{integrity.last_sequence_no.toLocaleString()}</dd></div>
        <div><dt>Sealed through</dt><dd>{integrity.sealed_through_sequence_no.toLocaleString()}</dd></div>
        <div><dt>Unsealed</dt><dd>{integrity.unsealed_event_count.toLocaleString()}</dd></div>
      </dl>
      {integrity.issues.length ? (
        <ul className="qc-list" aria-label="Audit integrity issues">
          {integrity.issues.map((issue, index) => <li key={`${issue.code}-${index}`} className="failed">{issue.code}</li>)}
        </ul>
      ) : <p className="muted">No chain integrity issue is visible in this project scope.</p>}
    </section>
  );
}

function AuditEvents({ events }: { events: AuditEvent[] }) {
  if (!events.length) {
    return <p className="muted">No audit events matched the current project scope and filters.</p>;
  }
  return (
    <div className="audit-event-list" aria-label="Audit events">
      {events.map((event) => (
        <article className="audit-event" key={event.event_id}>
          <div>
            <strong>#{event.sequence_no} · {event.action}</strong>
            <small>{formatDate(event.occurred_at)} · {event.target.type} · {event.target.id ? shortId(event.target.id) : "no target id"}</small>
          </div>
          <span className={`mapping-status ${event.outcome === "success" ? "exact" : "unsupported"}`}>{event.outcome}</span>
        </article>
      ))}
    </div>
  );
}

export function GovernanceEvidenceWorkbench({ config }: { config: ApiConfig }) {
  const [entityId, setEntityId] = useState("");
  const [targetEntityType, setTargetEntityType] = useState("");
  const [maxDepth, setMaxDepth] = useState("10");
  const [limit, setLimit] = useState("100");
  const [entity, setEntity] = useState<ProvenanceEntityResponse | null>(null);
  const [lineage, setLineage] = useState<ProvenanceLineagePage | null>(null);
  const [impact, setImpact] = useState<ProvenanceLineagePage | null>(null);
  const [completeness, setCompleteness] = useState<ProvenanceCompletenessReport | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [integrity, setIntegrity] = useState<AuditIntegrityReport | null>(null);
  const [auditAction, setAuditAction] = useState("");
  const [auditOutcome, setAuditOutcome] = useState<AuditOutcome | "">("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function parsedGraphQuery() {
    const depth = Number(maxDepth);
    const pageLimit = Number(limit);
    if (!Number.isInteger(depth) || depth < 1 || depth > 20 || !Number.isInteger(pageLimit) || pageLimit < 1 || pageLimit > 1_000) {
      throw new Error("Depth must be 1–20 and page size must be 1–1,000.");
    }
    return {
      max_depth: depth,
      limit: pageLimit,
      target_entity_type: targetEntityType.trim() || null,
    };
  }

  async function inspectEntity(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!entityId.trim()) return;
    setBusy("entity");
    setError(null);
    try {
      const result = await getProvenanceEntity(config, entityId.trim());
      setEntity(result.data);
      setLineage(null);
      setImpact(null);
      setCompleteness(null);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(null);
    }
  }

  async function loadLineage(direction: "upstream" | "downstream"): Promise<void> {
    if (!entityId.trim()) return;
    setBusy(direction);
    setError(null);
    try {
      const result = direction === "upstream"
        ? await getProvenanceLineage(config, entityId.trim(), { ...parsedGraphQuery(), direction })
        : await getProvenanceImpact(config, entityId.trim(), parsedGraphQuery());
      if (direction === "upstream") setLineage(result.data);
      else setImpact(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(null);
    }
  }

  async function loadCompleteness(): Promise<void> {
    if (!entityId.trim()) return;
    setBusy("completeness");
    setError(null);
    try {
      const result = await getProvenanceCompleteness(config, entityId.trim());
      setCompleteness(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(null);
    }
  }

  async function loadAudit(): Promise<void> {
    setBusy("audit");
    setError(null);
    try {
      const result = await listAuditEvents(config, {
        limit: 25,
        action: auditAction.trim() || null,
        outcome: auditOutcome || null,
      });
      setEvents(result.data.events);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(null);
    }
  }

  async function loadIntegrity(): Promise<void> {
    setBusy("integrity");
    setError(null);
    try {
      const result = await getAuditIntegrity(config);
      setIntegrity(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="content-card governance-evidence-workbench" aria-labelledby="governance-evidence-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Governance · evidence</p>
          <h2 id="governance-evidence-title">Lineage and audit inspector</h2>
        </div>
      </div>
      <p className="muted">
        Inspect one immutable provenance Entity, its bounded evidence path, and the project audit chain before making a Review or Release decision. The browser never reconstructs a graph or hides a truncated result.
      </p>
      <form className="form-stack" onSubmit={(event) => void inspectEntity(event)}>
        <div className="form-grid">
          <label>
            Provenance Entity ID
            <input value={entityId} onChange={(event) => setEntityId(event.target.value)} placeholder="UUID from a revision or artifact evidence link" required />
          </label>
          <label>
            Target entity type (optional)
            <input value={targetEntityType} onChange={(event) => setTargetEntityType(event.target.value)} placeholder="e.g. exporting.solver_card.revision" />
          </label>
          <label>
            Max lineage depth
            <input type="number" min="1" max="20" value={maxDepth} onChange={(event) => setMaxDepth(event.target.value)} />
          </label>
          <label>
            Page size
            <input type="number" min="1" max="1000" value={limit} onChange={(event) => setLimit(event.target.value)} />
          </label>
        </div>
        {error ? <p className="error-notice" role="alert">{error}</p> : null}
        <div className="form-actions">
          <button className="button primary" type="submit" disabled={busy !== null || !entityId.trim()}>{busy === "entity" ? "Loading entity…" : "Inspect entity"}</button>
          <button className="button secondary" type="button" onClick={() => void loadLineage("upstream")} disabled={busy !== null || !entityId.trim()}>{busy === "upstream" ? "Loading…" : "Load upstream lineage"}</button>
          <button className="button secondary" type="button" onClick={() => void loadLineage("downstream")} disabled={busy !== null || !entityId.trim()}>{busy === "downstream" ? "Loading…" : "Load downstream impact"}</button>
          <button className="text-button" type="button" onClick={() => void loadCompleteness()} disabled={busy !== null || !entityId.trim()}>{busy === "completeness" ? "Checking…" : "Check completeness"}</button>
        </div>
      </form>
      {entity ? <EntitySummary entity={entity} /> : null}
      {completeness ? (
        <section className="evidence-result" aria-label="Provenance completeness report">
          <div className="section-heading compact-heading">
            <div><p className="eyebrow">Upstream gate</p><h4>Completeness report</h4></div>
            <span className={`mapping-status ${completeness.eligible ? "exact" : "unsupported"}`}>{completeness.state}</span>
          </div>
          <p className="source-line">{completeness.nodes_evaluated.toLocaleString()} nodes · {completeness.edges_evaluated.toLocaleString()} edges · max depth {completeness.max_depth_reached}</p>
          {completeness.issues.length ? <ul className="qc-list">{completeness.issues.map((issue, index) => <li key={`${issue.code}-${index}`} className="failed">{issue.code}</li>)}</ul> : <p className="muted">No completeness issue was returned.</p>}
        </section>
      ) : null}
      {lineage ? <GraphResult page={lineage} title="Upstream lineage" /> : null}
      {impact ? <GraphResult page={impact} title="Downstream impact" /> : null}
      <section className="evidence-audit-section">
        <div className="section-heading compact-heading">
          <div><p className="eyebrow">Auditor view</p><h4>Project audit evidence</h4></div>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={() => void loadIntegrity()} disabled={busy !== null}>{busy === "integrity" ? "Checking…" : "Verify chain"}</button>
            <button className="text-button" type="button" onClick={() => void loadAudit()} disabled={busy !== null}>{busy === "audit" ? "Loading…" : "Load events"}</button>
          </div>
        </div>
        <div className="form-grid">
          <label>Action filter<input value={auditAction} onChange={(event) => setAuditAction(event.target.value)} placeholder="e.g. catalog.material.create" /></label>
          <label>Outcome filter<select value={auditOutcome} onChange={(event) => setAuditOutcome(event.target.value as AuditOutcome | "")}><option value="">All outcomes</option><option value="success">Success</option><option value="failure">Failure</option><option value="denied">Denied</option></select></label>
        </div>
        {integrity ? <AuditSummary integrity={integrity} /> : null}
        <AuditEvents events={events} />
      </section>
    </section>
  );
}
