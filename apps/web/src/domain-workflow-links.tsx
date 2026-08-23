import { useEffect, useState } from "react";

import "./domain-workflow-links.css";

import {
  ApiError,
  getCatalogWorkflowGraph,
  resolveCatalogDomainRevision,
  type ApiConfig,
} from "./api";
import type {
  CatalogWorkflowGraphResponse,
  DomainBindingKind,
  DomainRevisionBinding,
} from "./types";

export interface DomainWorkflowTarget {
  kind: DomainBindingKind;
  objectId: string;
  revisionId: string;
  label: string;
}

interface DomainWorkflowLinksProps {
  config: ApiConfig;
  target: DomainWorkflowTarget;
  compact?: boolean;
}

function explorerPath(binding: DomainRevisionBinding): string {
  return `/catalog/explorer/records/${binding.record_id}/revisions/${binding.record_revision_id}`;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The related-data graph could not be loaded.";
}

function isDomainRevisionBinding(value: unknown): value is DomainRevisionBinding {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<DomainRevisionBinding>;
  return typeof candidate.record_id === "string"
    && typeof candidate.record_revision_id === "string"
    && typeof candidate.object_id === "string"
    && typeof candidate.revision_id === "string";
}

function isWorkflowGraph(value: unknown): value is CatalogWorkflowGraphResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<CatalogWorkflowGraphResponse>;
  return Boolean(candidate.root) && Array.isArray(candidate.nodes) && Array.isArray(candidate.links);
}

export function DomainWorkflowLinks({ config, target, compact = false }: DomainWorkflowLinksProps) {
  const [binding, setBinding] = useState<DomainRevisionBinding | null>(null);
  const [graph, setGraph] = useState<CatalogWorkflowGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const resolutionState = loading ? "loading" : error ? "error" : binding ? "resolved" : "unprojected";

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void resolveCatalogDomainRevision(config, target.kind, target.objectId, target.revisionId)
      .then(async (result) => {
        if (!active) return;
        const resolvedBinding = isDomainRevisionBinding(result.data) ? result.data : null;
        setBinding(resolvedBinding);
        if (!resolvedBinding) {
          setGraph(null);
          return;
        }
        const graphResult = await getCatalogWorkflowGraph(
          config,
          resolvedBinding.record_id,
          resolvedBinding.record_revision_id,
          5,
        );
        if (active) {
          if (!isWorkflowGraph(graphResult.data)) {
            throw new Error("The Catalog workflow graph response was invalid.");
          }
          setGraph(graphResult.data);
        }
      })
      .catch((caught: unknown) => {
        if (active) setError(errorMessage(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [config, target.kind, target.objectId, target.revisionId]);

  return (
    <section
      className={`domain-workflow-links${compact ? " compact" : ""}`}
      aria-label={`${target.label} related governed data`}
      aria-busy={loading}
      data-resolution-state={resolutionState}
    >
      <div className="domain-workflow-heading">
        <div>
          <span className="eyebrow">Exact linked data</span>
          <strong>{target.label}</strong>
        </div>
        {binding ? <a className="button secondary" href={explorerPath(binding)}>Open Workflow Explorer</a> : null}
      </div>
      {loading ? (
        <p className="muted" role="status" aria-live="polite">
          Resolving the exact Catalog node…
        </p>
      ) : null}
      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && !error && !binding ? (
        <p className="muted">This exact revision is not yet projected into a configurable Workflow Explorer record.</p>
      ) : null}
      {graph ? (
        <div className="domain-workflow-node-list">
          {graph.nodes.map((node) => {
            const destination = node.domain_binding?.workbench_path
              ?? `/catalog/explorer/records/${node.record_id}/revisions/${node.record_revision_id}`;
            return (
              <a
                href={destination}
                key={`${node.record_id}:${node.record_revision_id}`}
                className={node.record_id === binding?.record_id ? "current" : ""}
              >
                <span>{node.domain_binding?.kind.replaceAll("_", " ") ?? "catalog record"}</span>
                <strong>{node.name}</strong>
                <small>exact r{node.revision_no} · {node.record_revision_id.slice(0, 8)}…</small>
              </a>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
