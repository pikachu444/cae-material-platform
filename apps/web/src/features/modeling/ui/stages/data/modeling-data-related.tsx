import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
} from "../../../../../shared/api";
import {
  getCatalogWorkflowGraph,
  resolveCatalogDomainRevision,
} from "../../../../catalog";
import {
  CATALOG_DATA_CATEGORIES,
  dataCategoryForEndpoint,
} from "../../../../../catalog-data-categories";
import type {
  CatalogDataCategory,
  CatalogWorkflowGraphResponse,
  ConfigurableLinkEndpoint,
  DomainRevisionBinding,
} from "../../../../../types";

interface ModelingDataRelatedProps {
  config: ApiConfig;
  documentId: string;
  revisionId: string;
  label: string;
}

function isBinding(value: unknown): value is DomainRevisionBinding {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<DomainRevisionBinding>;
  return typeof candidate.record_id === "string"
    && typeof candidate.record_revision_id === "string"
    && typeof candidate.object_id === "string"
    && typeof candidate.revision_id === "string";
}

function isGraph(value: unknown): value is CatalogWorkflowGraphResponse {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<CatalogWorkflowGraphResponse>;
  return Boolean(candidate.root) && Array.isArray(candidate.nodes) && Array.isArray(candidate.links);
}

function relatedError(error: unknown): string {
  return error instanceof ApiError ? error.message : "Related data could not be loaded.";
}

function destination(node: ConfigurableLinkEndpoint): string {
  return node.domain_binding?.workbench_path
    ?? `/catalog/explorer/records/${node.record_id}/revisions/${node.record_revision_id}`;
}

const NORMAL_SURFACE_KINDS = new Set([
  "material",
  "specimen",
  "test_run",
  "test_data",
  "processing_output",
  "material_model",
  "neutral_material",
  "solver_card",
  "neutral_solver_card",
]);

function visibleBindingKind(node: ConfigurableLinkEndpoint): string | null {
  const bindings = node.domain_bindings?.length
    ? node.domain_bindings
    : node.domain_binding
      ? [node.domain_binding]
      : [];
  return bindings.find((binding) => NORMAL_SURFACE_KINDS.has(binding.kind))?.kind ?? null;
}

function isNormalSurfaceNode(node: ConfigurableLinkEndpoint): boolean {
  return Boolean(visibleBindingKind(node)
    || CATALOG_DATA_CATEGORIES.some((category) => category.key === node.data_category));
}

function displayName(node: ConfigurableLinkEndpoint): string {
  const name = node.name
    .trim()
    .replace(/^CMP(?:[\s_-]+DEMO)?[\s_-]+/iu, "")
    .replace(/\s+(?:Processing Output|Technical Data|Test Data|Simulation Data|Solver Card)$/iu, "")
    || "Related data";
  if (visibleBindingKind(node) !== "material" || /datasheet/i.test(name)) return name;
  const identity = name.split(/\s+/u)[0] || name;
  return `${identity} datasheet`;
}

export function ModelingDataRelated({
  config,
  documentId,
  revisionId,
  label,
}: ModelingDataRelatedProps) {
  const [graph, setGraph] = useState<CatalogWorkflowGraphResponse | null>(null);
  const [rootRecordId, setRootRecordId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setGraph(null);
    setRootRecordId("");
    void resolveCatalogDomainRevision(config, "test_data", documentId, revisionId)
      .then(async (result) => {
        if (!active) return;
        const binding = isBinding(result.data) ? result.data : null;
        if (!binding) return;
        setRootRecordId(binding.record_id);
        const graphResult = await getCatalogWorkflowGraph(
          config,
          binding.record_id,
          binding.record_revision_id,
          5,
        );
        if (!active) return;
        if (!isGraph(graphResult.data)) throw new Error("Invalid related-data response.");
        setGraph(graphResult.data);
      })
      .catch((caught: unknown) => {
        if (active) setError(relatedError(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [attempt, config, documentId, revisionId]);

  const groups = useMemo(() => {
    const grouped = new Map<CatalogDataCategory, ConfigurableLinkEndpoint[]>();
    for (const node of graph?.nodes ?? []) {
      if (node.record_id === rootRecordId) continue;
      if (!isNormalSurfaceNode(node)) continue;
      const category = dataCategoryForEndpoint(node);
      if (!category) continue;
      const current = grouped.get(category) ?? [];
      const label = displayName(node).toLocaleLowerCase();
      if (!current.some((item) => displayName(item).toLocaleLowerCase() === label)) {
        current.push(node);
      }
      grouped.set(category, current);
    }
    return CATALOG_DATA_CATEGORIES
      .map((category) => ({ ...category, items: grouped.get(category.key) ?? [] }))
      .filter((group) => group.items.length > 0);
  }, [graph, rootRecordId]);

  if (loading) return <span className="visually-hidden" role="status">Loading related data…</span>;
  if (error) {
    return (
      <section className="modeling-data-related is-error" aria-label={`${label} related data`}>
        <div className="modeling-data-rail-heading"><h3>Related data</h3></div>
        <p role="alert">{error}</p>
        <button type="button" className="text-button" onClick={() => setAttempt((current) => current + 1)}>Retry</button>
      </section>
    );
  }
  if (!groups.length) return null;

  const count = groups.reduce((total, group) => total + group.items.length, 0);
  return (
    <section className="modeling-data-related" aria-label={`${label} related data`}>
      <div className="modeling-data-rail-heading">
        <h3>Related data</h3>
        <span>{count.toLocaleString()}</span>
      </div>
      <div className="modeling-data-related-scroll">
        {groups.map((group) => (
          <details key={group.key} open>
            <summary><span>{group.label}</span><span>{group.items.length.toLocaleString()}</span></summary>
            <ul>
              {group.items.map((node) => (
                <li key={`${node.record_id}:${node.record_revision_id}`}>
                  <a href={destination(node)} title={displayName(node)}>{displayName(node)}</a>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </section>
  );
}
