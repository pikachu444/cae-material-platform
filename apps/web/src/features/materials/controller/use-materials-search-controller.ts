import { type FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError, type ApiConfig } from "../../../api";
import type {
  CatalogWorkflowGraphResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableLinkEndpoint,
} from "../../../types";
import type {
  MaterialsBrowseResults,
  MaterialsBrowseScope,
} from "../../../materials-browse-tree";
import {
  publishWorkspaceCommandState,
  publishWorkspaceStatus,
} from "../../../design/application-shell";
import {
  findDefaultMaterialsTableId,
  searchMaterialCatalogRecords,
  type MaterialSearchRow,
} from "../api/search-materials";
import {
  exactRecordPath,
  materialsPath,
  parseMaterialsLocation,
  rememberBrowseRecord,
  rememberMaterialsReturnPath,
  storedBrowseRecord,
  type MaterialsLocationState,
  type MaterialsNavigatorMode,
  type MaterialsSortKey,
} from "../model/materials-route-state";

export interface BrowseSelection {
  record: ConfigurableCatalogRecordResponse;
  graph: CatalogWorkflowGraphResponse;
}

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error
    ? cause.message
    : "The material query could not be loaded.";
}

export function useMaterialsSearchController(
  config: ApiConfig,
  onNavigate: (path: string) => void,
  locationSearch?: string,
) {
  const initial = parseMaterialsLocation(locationSearch);
  const [draftQuery, setDraftQuery] = useState(initial.query);
  const [query, setQuery] = useState(initial.query);
  const [materialClass, setMaterialClass] = useState(initial.materialClass);
  const [provider, setProvider] = useState(initial.provider);
  const [evidenceSource, setEvidenceSource] = useState(initial.evidenceSource);
  const [scope, setScope] = useState<MaterialsBrowseScope | null>(
    initial.scope,
  );
  const [scopeAvailability, setScopeAvailability] = useState<
    "loading" | "ready" | "unavailable"
  >(initial.scope ? "ready" : "loading");
  const [sortKey, setSortKey] = useState(initial.sortKey);
  const [sortDirection, setSortDirection] = useState(initial.sortDirection);
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [leftMode, setLeftMode] = useState<MaterialsNavigatorMode>(
    initial.leftMode,
  );
  const [requestedRecord, setRequestedRecord] =
    useState<ConfigurableLinkEndpoint | null>(storedBrowseRecord);
  const [browseSelection, setBrowseSelection] =
    useState<BrowseSelection | null>(null);
  const [browseResults, setBrowseResults] =
    useState<MaterialsBrowseResults | null>(null);
  const [materials, setMaterials] = useState<MaterialSearchRow[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [familyFacets, setFamilyFacets] = useState<
    Array<{ material_class: string; count: number }>
  >([]);
  const [providerFacets, setProviderFacets] = useState<
    Array<{ provider: string; count: number }>
  >([]);
  const [evidenceSourceFacets, setEvidenceSourceFacets] = useState<
    Array<{ evidence_source: string; count: number }>
  >([]);
  const [offset, setOffset] = useState(initial.offset);
  const [selectedId, setSelectedId] = useState(initial.selectedId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    if (locationSearch === undefined) return;
    const next = parseMaterialsLocation(locationSearch);
    setDraftQuery(next.query);
    setQuery(next.query);
    setMaterialClass(next.materialClass);
    setProvider(next.provider);
    setEvidenceSource(next.evidenceSource);
    setScope(next.scope);
    setScopeAvailability(next.scope ? "ready" : "loading");
    setSortKey(next.sortKey);
    setSortDirection(next.sortDirection);
    setLeftMode(next.leftMode);
    setSelectedId(next.selectedId);
    setOffset(next.offset);
  }, [locationSearch]);

  useEffect(() => {
    if (scopeAvailability !== "loading" || scope?.tableId) return;
    let active = true;
    void findDefaultMaterialsTableId(config)
      .then((tableId) => {
        if (!active) return;
        if (tableId) {
          setScope({ tableId });
          setScopeAvailability("ready");
        } else {
          setScopeAvailability("unavailable");
        }
      })
      .catch(() => {
        if (active) setScopeAvailability("unavailable");
      });
    return () => {
      active = false;
    };
  }, [config, scope?.tableId, scopeAvailability]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    if (scopeAvailability !== "ready" || !scope?.tableId) {
      if (scopeAvailability === "unavailable") {
        setLoading(false);
        setError("Materials are not available in this workspace.");
      }
      return () => {
        active = false;
      };
    }
    void searchMaterialCatalogRecords(config, {
      query,
      materialClass: materialClass || undefined,
      provider: provider || undefined,
      evidenceSource: evidenceSource || undefined,
      tableId: scope.tableId,
      folderId: scope.folderId,
      recordId: scope.recordId,
      includeDescendants: scope.includeDescendants,
      offset,
      limit: 50,
      sortBy: sortKey,
      sortDirection,
    })
      .then((result) => {
        if (!active) return;
        const items = result.data.items;
        setMaterials(items);
        setTotalCount(result.data.total_count);
        setFamilyFacets(result.data.facets.material_classes);
        setProviderFacets(result.data.facets.providers);
        setEvidenceSourceFacets(result.data.facets.evidence_sources);
        setSelectedId((current) =>
          items.some((item) => item.material_id === current)
            ? current
            : (items[0]?.material_id ?? ""),
        );
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        // Keep the last authorized rows and selection while retry remains available.
        setLoading(false);
        setError(messageFor(cause));
      });
    return () => {
      active = false;
    };
  }, [
    config,
    evidenceSource,
    loadAttempt,
    materialClass,
    offset,
    provider,
    query,
    scope,
    scopeAvailability,
    sortDirection,
    sortKey,
  ]);

  const state = (): MaterialsLocationState => ({
    query,
    materialClass,
    provider,
    evidenceSource,
    scope,
    sortKey,
    sortDirection,
    offset,
    leftMode,
    selectedId,
  });

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      window.location.pathname !== "/materials"
    )
      return;
    window.history.replaceState(
      window.history.state,
      "",
      materialsPath(state()),
    );
  }, [
    evidenceSource,
    leftMode,
    materialClass,
    offset,
    provider,
    query,
    scope,
    selectedId,
    sortDirection,
    sortKey,
  ]);

  useEffect(() => {
    publishWorkspaceCommandState(
      `materials:${leftMode === "filters" ? "search" : leftMode}`,
    );
  }, [leftMode]);

  const selected = materials.find((item) => item.material_id === selectedId);
  const comparedMaterials = materials.filter((material) =>
    compareIds.has(material.material_id),
  );

  useEffect(() => {
    publishWorkspaceStatus({
      selection: selected
        ? `${selected.name} · Code ${selected.material_code ?? "—"}`
        : "No material selected",
      revision: selected
        ? `r${selected.record_revision_no}`
        : `${totalCount.toLocaleString()} records`,
      jobs: loading ? "Loading materials" : "No active job",
      warnings: error ? "1 workspace error" : "0 warnings",
      connection: error ? "degraded" : "online",
    });
  }, [error, loading, selected, totalCount]);

  function submit(event: FormEvent): void {
    event.preventDefault();
    setOffset(0);
    setQuery(draftQuery.trim());
  }

  const changeScope = useCallback((nextScope: MaterialsBrowseScope) => {
    setScopeAvailability("ready");
    setScope((current) =>
      current?.tableId === nextScope.tableId &&
      current?.folderId === nextScope.folderId &&
      current?.recordId === nextScope.recordId &&
      current?.includeDescendants === nextScope.includeDescendants
        ? current
        : nextScope,
    );
    setOffset(0);
  }, []);

  const changeScopeAvailability = useCallback(
    (availability: "loading" | "ready" | "unavailable") => {
      setScopeAvailability(availability);
    },
    [],
  );

  function openBrowseTree(
    record: ConfigurableLinkEndpoint | null | undefined,
  ): void {
    setLeftMode("browse");
    setRequestedRecord(record ?? null);
    if (record) rememberBrowseRecord(record);
  }

  function selectBrowseRecord(
    record: ConfigurableCatalogRecordResponse,
    graph: CatalogWorkflowGraphResponse,
  ): void {
    setBrowseSelection({ record, graph });
    rememberBrowseRecord(graph.root);
    const materialBinding =
      graph.root.domain_binding?.kind === "material"
        ? graph.root.domain_binding
        : graph.nodes.find(
            (node) =>
              node.record_id === record.record_id &&
              node.domain_binding?.kind === "material",
          )?.domain_binding;
    if (
      materialBinding?.kind === "material" &&
      materials.some((item) => item.material_id === materialBinding.object_id)
    ) {
      setSelectedId(materialBinding.object_id);
    }
  }

  function openExactRecord(record: ConfigurableCatalogRecordResponse): void {
    rememberMaterialsReturnPath(materialsPath(state()));
    onNavigate(exactRecordPath(record.record_id, record.current_revision.id));
  }

  function changeSort(next: MaterialsSortKey): void {
    if (next === sortKey) {
      setSortDirection((current) =>
        current === "ascending" ? "descending" : "ascending",
      );
    } else {
      setSortKey(next);
      setSortDirection("ascending");
    }
    setOffset(0);
  }

  function toggleCompare(materialId: string): void {
    setCompareIds((current) => {
      const next = new Set(current);
      if (next.has(materialId)) next.delete(materialId);
      else if (next.size < 3) next.add(materialId);
      return next;
    });
  }

  function clearComparison(): void {
    setCompareIds(new Set());
  }

  function clearFilters(): void {
    setMaterialClass("");
    setProvider("");
    setEvidenceSource("");
    setOffset(0);
  }

  function clearSearch(): void {
    setDraftQuery("");
    setQuery("");
    clearFilters();
  }

  function openMaterial(material: MaterialSearchRow): void {
    rememberMaterialsReturnPath(
      materialsPath({ ...state(), selectedId: material.material_id }),
    );
    const params = new URLSearchParams({
      record_id: material.record_id,
      record_revision_id: material.record_revision_id,
      material_revision_id: material.material_revision_id,
    });
    onNavigate(`/materials/${material.material_id}?${params.toString()}`);
  }

  return {
    browseResults,
    browseSelection,
    changeScope,
    changeScopeAvailability,
    changeSort,
    clearComparison,
    clearFilters,
    clearSearch,
    compareIds,
    comparedMaterials,
    draftQuery,
    error,
    evidenceSource,
    evidenceSourceFacets,
    familyFacets,
    leftMode,
    loading,
    materialClass,
    materials,
    offset,
    openBrowseTree,
    openExactRecord,
    openMaterial,
    provider,
    providerFacets,
    requestedRecord,
    retry: () => {
      if (!scope?.tableId) setScopeAvailability("loading");
      setLoadAttempt((current) => current + 1);
    },
    selectedId,
    setBrowseResults,
    setDraftQuery,
    setEvidenceSource: (value: string) => {
      setEvidenceSource(value);
      setOffset(0);
    },
    setLeftMode,
    setMaterialClass: (value: string) => {
      setMaterialClass(value);
      setOffset(0);
    },
    setOffset,
    setProvider: (value: string) => {
      setProvider(value);
      setOffset(0);
    },
    sortDirection,
    sortKey,
    submit,
    toggleCompare,
    totalCount,
    selectBrowseRecord,
    selectBrowseResult: openExactRecord,
  };
}
