import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  compareConfigurableCatalogRecordRevisions,
  createConfigurableCatalogFolder,
  createConfigurableCatalogRecord,
  createConfigurableCatalogSubset,
  getConfigurableCatalogRecord,
  getMaterialDetail,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogFolders,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogRecordRevisions,
  listConfigurableCatalogSubsets,
  listConfigurableCatalogTables,
  listMaterials,
  previewConfigurableCatalogRecordRegistration,
  publishConfigurableCatalogRecordRegistration,
  reviseConfigurableCatalogFolder,
  reviseConfigurableCatalogRecord,
  searchConfigurableCatalogRecords,
  uploadGovernedTabularFile,
  validateConfigurableCatalogPublication,
  type ApiConfig,
} from "./api";
import type {
  ConfigurableAttributeResponse,
  ConfigurableCatalogFolderResponse,
  ConfigurableCatalogRecordComparison,
  ConfigurableCatalogRecordContent,
  ConfigurableCatalogRecordResponse,
  ConfigurableCatalogRecordSearchResponse,
  ConfigurableLayoutResponse,
  ConfigurableRecordValue,
  ConfigurableSubsetResponse,
  ConfigurableTableResponse,
  DataClassification,
  MaterialResponse,
  MaterialStateResponse,
} from "./model";
import { ReviewRequestAction } from "../../../review-request-action";
import { publishWorkspaceStatus } from "../../../design/application-shell";
import {
  EngineeringPane,
  SemanticStatus,
  SemanticText,
  WorkbenchMessage,
} from "../../../design/semantic-ui";
import {
  parseRecordsRouteSelection,
  recordsRoutePath,
} from "../model/administration-route-state";

interface DraftValue {
  enabled: boolean;
  primary: string;
  secondary: string;
  normalized: string;
}

const valueTypeLabels: Record<
  ConfigurableAttributeResponse["current_revision"]["content"]["data_type"],
  string
> = {
  number: "Number",
  integer: "Whole number",
  text: "Text",
  boolean: "Yes or no",
  date: "Date",
  discrete: "Choice",
  file: "Evidence file",
  curve: "Curve",
  record_reference: "Related record",
};

function message(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The configurable Catalog operation could not be completed.";
}

function valueLabel(value: ConfigurableRecordValue): string {
  if (value.data_type === "number") {
    return `${value.original_value} ${value.original_unit_string} → ${value.normalized_value} ${value.normalized_unit}`;
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return "Evidence attachment";
  }
  if (value.data_type === "record_reference") {
    return "Linked record";
  }
  if (value.data_type === "boolean") {
    return value.value ? "Yes" : "No";
  }
  return String(value.value);
}

function recordCountLabel(count: number): string {
  return `${count} ${count === 1 ? "record" : "records"}`;
}

function lifecycleLabel(value: ConfigurableCatalogRecordResponse): string {
  return value.current_revision.lifecycle_state === "draft" ? "Draft" : "Published";
}

function emptyDraft(attribute: ConfigurableAttributeResponse): DraftValue {
  const content = attribute.current_revision.content;
  return {
    enabled: content.required,
    primary: content.data_type === "boolean" ? "false" : "",
    secondary:
      content.data_type === "number" ? (content.normalized_unit ?? "") : "",
    normalized: "",
  };
}

function valueDraft(value: ConfigurableRecordValue): DraftValue {
  if (value.data_type === "number") {
    return {
      enabled: true,
      primary: value.original_value,
      secondary: value.original_unit_string,
      normalized: value.normalized_value,
    };
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return {
      enabled: true,
      primary: value.artifact_id,
      secondary: value.artifact_sha256,
      normalized: "",
    };
  }
  if (value.data_type === "record_reference") {
    return {
      enabled: true,
      primary: value.target_record_id,
      secondary: value.target_record_revision_id,
      normalized: "",
    };
  }
  return {
    enabled: true,
    primary: String(value.value),
    secondary: "",
    normalized: "",
  };
}

function buildValue(
  attribute: ConfigurableAttributeResponse,
  draft: DraftValue,
): ConfigurableRecordValue | null {
  if (!draft.enabled) {
    return null;
  }
  const definition = attribute.current_revision.content;
  const common = {
    attribute_definition_id: attribute.attribute_definition_id,
    attribute_definition_revision_id: attribute.current_revision.id,
  };
  if (definition.data_type === "number") {
    return {
      ...common,
      data_type: "number",
      original_value: draft.primary,
      original_unit_string: draft.secondary,
      // The service derives the authoritative standard value from the entered value and unit.
      normalized_value: draft.primary,
      normalized_unit: definition.normalized_unit ?? "",
      quantity_semantics: definition.quantity_semantics ?? "",
    };
  }
  if (definition.data_type === "integer") {
    return { ...common, data_type: "integer", value: Number(draft.primary) };
  }
  if (definition.data_type === "boolean") {
    return { ...common, data_type: "boolean", value: draft.primary === "true" };
  }
  if (definition.data_type === "date") {
    return { ...common, data_type: "date", value: draft.primary };
  }
  if (definition.data_type === "discrete") {
    return { ...common, data_type: "discrete", value: draft.primary };
  }
  if (definition.data_type === "file" || definition.data_type === "curve") {
    return {
      ...common,
      data_type: definition.data_type,
      artifact_id: draft.primary,
      artifact_sha256: draft.secondary,
    };
  }
  if (definition.data_type === "record_reference") {
    return {
      ...common,
      data_type: "record_reference",
      target_record_id: draft.primary,
      target_record_revision_id: draft.secondary,
    };
  }
  return { ...common, data_type: "text", value: draft.primary };
}

export function ConfigurableCatalogRecords({
  config,
  onNavigate,
  onOpenConnection,
  productMode = false,
  locationSearch = "",
}: {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
  productMode?: boolean;
  locationSearch?: string;
}) {
  const requestedSelection = useMemo(
    () => parseRecordsRouteSelection(locationSearch),
    [locationSearch],
  );
  const [tables, setTables] = useState<ConfigurableTableResponse[]>([]);
  const [tablesLoaded, setTablesLoaded] = useState(false);
  const [tableId, setTableId] = useState(requestedSelection.tableId);
  const [attributes, setAttributes] = useState<ConfigurableAttributeResponse[]>(
    [],
  );
  const [layouts, setLayouts] = useState<ConfigurableLayoutResponse[]>([]);
  const [layoutId, setLayoutId] = useState("");
  const [folders, setFolders] = useState<ConfigurableCatalogFolderResponse[]>(
    [],
  );
  const [definitionLoaded, setDefinitionLoaded] = useState(false);
  const [subsets, setSubsets] = useState<ConfigurableSubsetResponse[]>([]);
  const [results, setResults] =
    useState<ConfigurableCatalogRecordSearchResponse | null>(null);
  const [selected, setSelected] =
    useState<ConfigurableCatalogRecordResponse | null>(null);
  const [selectedEtag, setSelectedEtag] = useState("");
  const [selectedIsHistorical, setSelectedIsHistorical] = useState(false);
  const [comparison, setComparison] =
    useState<ConfigurableCatalogRecordComparison | null>(null);
  const [query, setQuery] = useState("");
  const [folderFilter, setFolderFilter] = useState("");
  const [facetFilters, setFacetFilters] = useState<Record<string, string>>({});
  const [numberAttributeId, setNumberAttributeId] = useState("");
  const [numberMinimum, setNumberMinimum] = useState("");
  const [numberMaximum, setNumberMaximum] = useState("");
  const [recordName, setRecordName] = useState("");
  const [externalKey, setExternalKey] = useState("");
  const [description, setDescription] = useState("");
  const [recordFolderId, setRecordFolderId] = useState("");
  const [classification, setClassification] =
    useState<DataClassification>("internal");
  const [drafts, setDrafts] = useState<Record<string, DraftValue>>({});
  const [folderName, setFolderName] = useState("");
  const [folderParentId, setFolderParentId] = useState("");
  const [subsetName, setSubsetName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [entryMode, setEntryMode] = useState<"closed" | "single" | "multiple">(
    requestedSelection.recordId ? "single" : "closed",
  );
  const previousRouteRecordId = useRef(requestedSelection.recordId);
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkFormat, setBulkFormat] = useState<"csv" | "tsv" | "xlsx">("csv");
  const [bulkSource, setBulkSource] = useState<{
    raw_asset_id: string;
    raw_artifact_id: string;
  } | null>(null);
  const [bulkColumns, setBulkColumns] = useState<string[]>([]);
  const [bulkMapping, setBulkMapping] = useState<Record<string, string>>({});
  const [bulkUnits, setBulkUnits] = useState<Record<string, string>>({});
  const [bulkHeaderRow, setBulkHeaderRow] = useState(1);
  const [bulkDelimiter, setBulkDelimiter] = useState(",");
  const [bulkDecimal, setBulkDecimal] = useState<"." | ",">(".");
  const [bulkCorrections, setBulkCorrections] = useState<
    Record<number, Record<string, string>>
  >({});
  const [materials, setMaterials] = useState<MaterialResponse[]>([]);
  const [materialId, setMaterialId] = useState("");
  const [materialStates, setMaterialStates] = useState<MaterialStateResponse[]>(
    [],
  );
  const [materialStateId, setMaterialStateId] = useState("");
  const [selectedFolderId, setSelectedFolderId] = useState(requestedSelection.folderId ?? "");
  const [bulkPreview, setBulkPreview] = useState<
    | Awaited<
        ReturnType<typeof previewConfigurableCatalogRecordRegistration>
      >["data"]
    | null
  >(null);

  const tableCandidate = useMemo(
    () => tables.find((item) => item.table_id === tableId) ?? null,
    [tableId, tables],
  );
  const table = useMemo(() => {
    if (
      tableCandidate
      && requestedSelection.tableId === tableCandidate.table_id
    ) {
      if (!requestedSelection.tableRevisionId) return null;
      if (requestedSelection.tableRevisionId !== tableCandidate.current_revision.id) return null;
    }
    return tableCandidate;
  }, [requestedSelection.tableId, requestedSelection.tableRevisionId, tableCandidate]);
  const activeTableId = requestedSelection.tableId === tableId
    ? table?.table_id ?? ""
    : tableId;
  const layout = useMemo(
    () => layouts.find((item) => item.layout_id === layoutId) ?? null,
    [layoutId, layouts],
  );
  const identifierAttribute = useMemo(
    () => attributes.find((item) => item.current_revision.content.key === "material_code")
      ?? attributes.find((item) => item.current_revision.content.business_key)
      ?? null,
    [attributes],
  );
  const identifierLabel = identifierAttribute?.current_revision.content.name ?? "Record code";

  function recordIdentifierValue(record: ConfigurableCatalogRecordResponse): string {
    if (!identifierAttribute) return record.current_revision.content.external_key ?? "—";
    const value = record.current_revision.content.values.find((candidate) => (
      candidate.attribute_definition_id === identifierAttribute.attribute_definition_id
      && candidate.attribute_definition_revision_id === identifierAttribute.current_revision.id
    ));
    return value ? valueLabel(value) : "—";
  }
  const selectedFolderCandidate = useMemo(
    () => folders.find((item) => item.folder_id === selectedFolderId) ?? null,
    [folders, selectedFolderId],
  );
  const selectedFolder = useMemo(() => {
    if (
      selectedFolderCandidate
      && requestedSelection.folderId === selectedFolderCandidate.folder_id
    ) {
      if (!requestedSelection.folderRevisionId) return null;
      if (requestedSelection.folderRevisionId !== selectedFolderCandidate.current_revision.id) return null;
    }
    return selectedFolderCandidate;
  }, [requestedSelection.folderId, requestedSelection.folderRevisionId, selectedFolderCandidate]);
  const exactRouteError = useMemo(() => {
    if (tablesLoaded && requestedSelection.tableId) {
      const requestedTable = tables.find((item) => item.table_id === requestedSelection.tableId);
      if (!requestedTable) return "The exact Record type in this route is not available.";
      if (!requestedSelection.tableRevisionId) {
        return "Choose the exact Record type revision before using this link.";
      }
      if (
        requestedSelection.tableRevisionId
        && requestedTable.current_revision.id !== requestedSelection.tableRevisionId
      ) return "The exact Record type revision in this route is not available.";
    }
    if (definitionLoaded && requestedSelection.folderId) {
      const requestedFolder = folders.find((item) => item.folder_id === requestedSelection.folderId);
      if (!requestedFolder) return "The exact Folder in this route is not available for this Table.";
      if (!requestedSelection.folderRevisionId) {
        return "Choose the exact Folder revision before using this link.";
      }
      if (
        requestedSelection.folderRevisionId
        && requestedFolder.current_revision.id !== requestedSelection.folderRevisionId
      ) return "The exact Folder revision in this route is not available.";
    }
    if (requestedSelection.recordId && !requestedSelection.recordRevisionId) {
      return "Choose the exact Record revision before using this link.";
    }
    return null;
  }, [definitionLoaded, folders, requestedSelection, tables, tablesLoaded]);

  function exactRecordsPath(
    overrides: Partial<ReturnType<typeof parseRecordsRouteSelection>> = {},
  ): string {
    const nextTableId = overrides.tableId ?? tableId;
    const nextTable = tables.find((item) => item.table_id === nextTableId) ?? null;
    const nextFolderId = overrides.folderId ?? selectedFolderId;
    const nextFolder = folders.find((item) => item.folder_id === nextFolderId) ?? null;
    return recordsRoutePath({
      tableId: nextTableId,
      tableRevisionId:
        overrides.tableRevisionId
        ?? nextTable?.current_revision.id
        ?? (nextTableId === requestedSelection.tableId ? requestedSelection.tableRevisionId : ""),
      folderId: nextFolderId,
      folderRevisionId:
        overrides.folderRevisionId
        ?? nextFolder?.current_revision.id
        ?? (nextFolderId === requestedSelection.folderId ? requestedSelection.folderRevisionId : ""),
      recordId: overrides.recordId ?? selected?.record_id ?? requestedSelection.recordId,
      recordRevisionId:
        overrides.recordRevisionId
        ?? selected?.current_revision.id
        ?? requestedSelection.recordRevisionId,
    });
  }
  const orderedAttributes = useMemo(() => {
    if (!layout) {
      return attributes;
    }
    const positions = new Map(
      layout.items.map((item) => [item.attribute_definition_id, item.ordinal]),
    );
    return attributes
      .filter((attribute) => positions.has(attribute.attribute_definition_id))
      .sort(
        (left, right) =>
          (positions.get(left.attribute_definition_id) ??
            Number.MAX_SAFE_INTEGER) -
          (positions.get(right.attribute_definition_id) ??
            Number.MAX_SAFE_INTEGER),
      );
  }, [attributes, layout]);
  const numberAttributes = useMemo(
    () =>
      attributes.filter(
        (attribute) =>
          attribute.current_revision.content.data_type === "number",
      ),
    [attributes],
  );
  const discreteAttributes = useMemo(
    () =>
      attributes.filter(
        (attribute) =>
          attribute.current_revision.content.data_type === "discrete",
      ),
    [attributes],
  );

  const loadTables = useCallback(async () => {
    if (!config.accessToken.trim()) return;
    try {
      const [tableResult, materialResult] = await Promise.allSettled([
        listConfigurableCatalogTables(config),
        listMaterials(config, { limit: 100, offset: 0 }),
      ]);
      if (tableResult.status === "rejected") {
        throw tableResult.reason;
      }
      const response = tableResult.value;
      setTables(response.data.items);
      setTablesLoaded(true);
      if (materialResult.status === "fulfilled") {
        const materialItems = materialResult.value.data.items;
        setMaterials(materialItems);
        setMaterialId((current) =>
          materialItems.some((item) => item.material_id === current)
            ? current
            : "",
        );
      } else {
        setMaterials([]);
        setMaterialId("");
      }
      setTableId((current) =>
        response.data.items.some((item) => item.table_id === current)
          ? current
          : "",
      );
    } catch (caught) {
      setError(message(caught));
      setTablesLoaded(true);
    }
  }, [config]);

  useEffect(() => {
    if (!materialId || !config.accessToken.trim()) {
      setMaterialStates([]);
      setMaterialStateId("");
      return;
    }
    void getMaterialDetail(config, materialId)
      .then((response) => {
        setMaterialStates(response.data.states);
        setMaterialStateId((current) =>
          response.data.states.some(
            (item) => item.material_state_id === current,
          )
            ? current
            : "",
        );
      })
      .catch((caught) => setError(message(caught)));
  }, [config, materialId]);

  const loadDefinition = useCallback(async () => {
    if (!activeTableId || !config.accessToken.trim()) {
      setAttributes([]);
      setLayouts([]);
      setLayoutId("");
      setFolders([]);
      setSubsets([]);
      setSelected(null);
      setSelectedIsHistorical(false);
      setResults(null);
      setDefinitionLoaded(true);
      return;
    }
    setBusy(true);
    setDefinitionLoaded(false);
    try {
      const [
        attributeResponse,
        layoutResponse,
        folderResponse,
        subsetResponse,
      ] = await Promise.all([
        listConfigurableCatalogAttributes(config, activeTableId),
        listConfigurableCatalogLayouts(config, activeTableId),
        listConfigurableCatalogFolders(config, activeTableId),
        listConfigurableCatalogSubsets(config, activeTableId),
      ]);
      setAttributes(attributeResponse.data.items);
      setLayouts(layoutResponse.data.items);
      setLayoutId((current) =>
        layoutResponse.data.items.some((item) => item.layout_id === current)
          ? current
          : "",
      );
      setFolders(folderResponse.data.items);
      setSubsets(subsetResponse.data.items);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setDefinitionLoaded(true);
      setBusy(false);
    }
  }, [activeTableId, config]);

  const search = useCallback(async () => {
    if (!activeTableId || !config.accessToken.trim()) {
      setResults(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await searchConfigurableCatalogRecords(config, {
        table_id: activeTableId,
        text: query.trim() || null,
        folder_id: folderFilter || null,
        discrete_filters: Object.entries(facetFilters).map(
          ([attributeId, value]) => ({
            attribute_definition_id: attributeId,
            values: [value],
          }),
        ),
        number_filters:
          numberAttributeId && (numberMinimum || numberMaximum)
            ? [
                {
                  attribute_definition_id: numberAttributeId,
                  minimum: numberMinimum || null,
                  maximum: numberMaximum || null,
                },
              ]
            : [],
        facet_attribute_ids: discreteAttributes.map(
          (attribute) => attribute.attribute_definition_id,
        ),
        limit: 50,
      });
      setResults(response.data);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }, [
    config,
    discreteAttributes,
    facetFilters,
    folderFilter,
    numberAttributeId,
    numberMaximum,
    numberMinimum,
    query,
    activeTableId,
  ]);

  useEffect(() => void loadTables(), [loadTables]);
  useEffect(() => {
    setTableId(requestedSelection.tableId);
  }, [requestedSelection.tableId]);
  useEffect(() => {
    setSelectedFolderId(requestedSelection.folderId ?? "");
  }, [requestedSelection.folderId]);
  useEffect(() => void loadDefinition(), [loadDefinition]);
  useEffect(() => {
    publishWorkspaceStatus({
      selection: table
        ? `${table.current_revision.content.name} · Revision ${table.current_revision.revision_no}`
        : "Records",
      revision: "",
      jobs: busy ? "Operation in progress" : "",
      warnings: error || exactRouteError ? "1 action required" : "",
      connection: "online",
    });
  }, [busy, error, exactRouteError, table]);
  useEffect(() => {
    setDrafts((current) =>
      Object.fromEntries(
        attributes.map((attribute) => [
          attribute.attribute_definition_id,
          current[attribute.attribute_definition_id] ?? emptyDraft(attribute),
        ]),
      ),
    );
  }, [attributes]);
  useEffect(() => void search(), [search]);
  useEffect(() => {
    const priorRecordId = previousRouteRecordId.current;
    previousRouteRecordId.current = requestedSelection.recordId;
    if (requestedSelection.recordId && !requestedSelection.tableId) {
      setError("Choose the exact Record type before opening a Record link.");
      return;
    }
    if (!requestedSelection.recordId) {
      if (priorRecordId) resetEditor(false);
      return;
    }
    if (!requestedSelection.recordRevisionId || exactRouteError) {
      setSelected(null);
      setSelectedEtag("");
      setSelectedIsHistorical(false);
      setEntryMode("closed");
      return;
    }
    if (attributes.length === 0) return;
    if (
      selected?.record_id === requestedSelection.recordId
      && selected.current_revision.id === requestedSelection.recordRevisionId
    ) return;
    void selectRecord(
      requestedSelection.recordId,
      requestedSelection.recordRevisionId,
    );
  }, [
    attributes.length,
    exactRouteError,
    requestedSelection.recordId,
    requestedSelection.recordRevisionId,
    requestedSelection.tableId,
    selected?.current_revision.id,
    selected?.record_id,
  ]);

  function resetEditor(openForCreate = false) {
    setSelected(null);
    setSelectedEtag("");
    setSelectedIsHistorical(false);
    setComparison(null);
    setRecordName("");
    setExternalKey("");
    setDescription("");
    setRecordFolderId("");
    setEntryMode(openForCreate ? "single" : "closed");
    onNavigate(exactRecordsPath({ recordId: "", recordRevisionId: "" }));
    setDrafts(
      Object.fromEntries(
        attributes.map((attribute) => [
          attribute.attribute_definition_id,
          emptyDraft(attribute),
        ]),
      ),
    );
  }

  async function selectRecord(
    recordId: string,
    recordRevisionId: string,
  ): Promise<ConfigurableCatalogRecordResponse | null> {
    setBusy(true);
    setError(null);
    try {
      const [detail, revisions] = await Promise.all([
        getConfigurableCatalogRecord(config, recordId),
        listConfigurableCatalogRecordRevisions(config, recordId),
      ]);
      if (tableId && detail.data.table_id !== tableId) {
        throw new Error("The selected Record does not belong to the exact Record type in this route.");
      }
      const requestedRevision = revisions.data.items.find(
        (revision) => revision.id === recordRevisionId,
      );
      if (!requestedRevision) {
        throw new Error("The exact Record revision is not available for this selection.");
      }
      const record = { ...detail.data, current_revision: requestedRevision };
      const historical = requestedRevision.id !== detail.data.current_revision.id;
      setSelected(record);
      setEntryMode("single");
      setSelectedEtag(historical ? "" : (detail.etag ?? ""));
      setSelectedIsHistorical(historical);
      setComparison(null);
      setRecordName(record.current_revision.content.name);
      setExternalKey(record.current_revision.content.external_key ?? "");
      setDescription(record.current_revision.content.description ?? "");
      setRecordFolderId(record.current_revision.content.folder_id ?? "");
      const valueMap = new Map(
        record.current_revision.content.values.map((value) => [
          value.attribute_definition_id,
          value,
        ]),
      );
      setDrafts(
        Object.fromEntries(
          attributes.map((attribute) => {
            const value = valueMap.get(attribute.attribute_definition_id);
            return [
              attribute.attribute_definition_id,
              value ? valueDraft(value) : emptyDraft(attribute),
            ];
          }),
        ),
      );
      const firstRevision = revisions.data.items.find((revision) => revision.revision_no === 1);
      if (firstRevision && firstRevision.id !== requestedRevision.id) {
        const compared = await compareConfigurableCatalogRecordRevisions(
          config,
          recordId,
          firstRevision.id,
          requestedRevision.id,
        );
        setComparison(compared.data);
      }
      return record;
    } catch (caught) {
      setSelected(null);
      setSelectedEtag("");
      setSelectedIsHistorical(false);
      setError(message(caught));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function selectCurrentRecord(
    recordId: string,
  ): Promise<ConfigurableCatalogRecordResponse | null> {
    setBusy(true);
    setError(null);
    try {
      const detail = await getConfigurableCatalogRecord(config, recordId);
      return await selectRecord(recordId, detail.data.current_revision.id);
    } catch (caught) {
      setError(message(caught));
      return null;
    } finally {
      setBusy(false);
    }
  }

  function updateDraft(attributeId: string, patch: Partial<DraftValue>) {
    setDrafts((current) => ({
      ...current,
      [attributeId]: {
        ...(current[attributeId] ?? {
          enabled: false,
          primary: "",
          secondary: "",
          normalized: "",
        }),
        ...patch,
      },
    }));
  }

  async function previewBulkRegistration() {
    if (!table || (!bulkSource && !bulkFile)) return;
    setBusy(true);
    setError(null);
    try {
      let source = bulkSource;
      const corrections = source ? bulkCorrections : {};
      if (!source && bulkFile) {
        const uploaded = await uploadGovernedTabularFile(config, {
          file: bulkFile,
          file_format: bulkFormat,
          classification,
          test_run_revision_id: null,
        });
        if (!uploaded.data.available_artifact_id) {
          throw new Error(
            "The uploaded source has not completed integrity verification.",
          );
        }
        source = {
          raw_asset_id: uploaded.data.raw_asset.raw_asset_id,
          raw_artifact_id: uploaded.data.available_artifact_id,
        };
        setBulkSource(source);
        setBulkCorrections({});
      }
      if (!source) return;
      const mapping = Object.fromEntries(
        Object.entries(bulkMapping)
          .filter(([, target]) => target)
          .map(([column, target]) => {
            const attribute = attributes.find(
              (item) => item.current_revision.content.key === target,
            );
            return [
              column,
              attribute?.current_revision.content.data_type === "number"
                ? {
                    attribute: target,
                    unit:
                      bulkUnits[column] ||
                      attribute.current_revision.content.normalized_unit,
                  }
                : target,
            ];
          }),
      );
      const material = materials.find(
        (item) => item.material_id === materialId,
      );
      const state = materialStates.find(
        (item) => item.material_state_id === materialStateId,
      );
      const result = await previewConfigurableCatalogRecordRegistration(
        config,
        {
          table_id: table.table_id,
          table_revision_id: table.current_revision.id,
          mapping,
          raw_asset_id: source.raw_asset_id,
          raw_artifact_id: source.raw_artifact_id,
          file_format: bulkFormat,
          sheet_name: null,
          header_row: bulkHeaderRow,
          encoding: bulkFormat === "xlsx" ? "binary" : "utf-8",
          delimiter:
            bulkFormat === "csv"
              ? bulkDelimiter
              : bulkFormat === "tsv"
                ? "\t"
                : null,
          decimal_separator: bulkDecimal,
          corrections,
          common_material_state:
            material && state
              ? {
                  material_id: material.material_id,
                  material_revision_id: material.current_revision.id,
                  state_id: state.material_state_id,
                  state_revision_id: state.current_revision.id,
                }
              : null,
        },
      );
      setBulkPreview(result.data);
      setBulkColumns(result.data.source_columns);
      if (!Object.keys(bulkMapping).length) {
        setBulkMapping(
          Object.fromEntries(
            result.data.source_columns.map((column) => {
              const normalized = column.trim().toLowerCase();
              return [
                column,
                normalized.includes("state")
                  ? "existing_state_name"
                  : normalized.includes("material") &&
                      normalized.includes("code")
                    ? "existing_material_code"
                    : normalized.includes("code")
                      ? "code"
                      : normalized.includes("name")
                        ? "name"
                        : "",
              ];
            }),
          ),
        );
      }
      setNotice(
        result.data.valid
          ? `${result.data.rows.length} rows are ready to register.`
          : "Correct the listed cells or complete the column mapping, then check again.",
      );
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function publishBulkRegistration() {
    if (!table || !bulkPreview?.valid) return;
    setBusy(true);
    setError(null);
    try {
      await publishConfigurableCatalogRecordRegistration(config, {
        token: bulkPreview.token,
        table_id: table.table_id,
        table_revision_id: table.current_revision.id,
        change_reason: "Register material data rows",
        classification,
      });
      setNotice(`${bulkPreview.rows.length} rows registered.`);
      setBulkPreview(null);
      setBulkFile(null);
      setBulkSource(null);
      setBulkColumns([]);
      setBulkMapping({});
      setBulkUnits({});
      setBulkCorrections({});
      await search();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function saveRecord(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!table) return;
    if (selectedIsHistorical) {
      setError("Historical Record revisions are read-only. Open the current revision before editing.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const folder =
        folders.find((item) => item.folder_id === recordFolderId) ?? null;
      const values = orderedAttributes
        .map((attribute) =>
          buildValue(
            attribute,
            drafts[attribute.attribute_definition_id] ?? emptyDraft(attribute),
          ),
        )
        .filter((value): value is ConfigurableRecordValue => value !== null);
      const content: ConfigurableCatalogRecordContent = {
        table_revision_id: table.current_revision.id,
        name: recordName.trim(),
        external_key: externalKey.trim() || null,
        description: description.trim() || null,
        folder_id: folder?.folder_id ?? null,
        folder_revision_id: folder?.current_revision.id ?? null,
        values,
      };
      const result = selected
        ? await reviseConfigurableCatalogRecord(
            config,
            selected.record_id,
            selectedEtag,
            {
              content,
              change_reason: "Revise configurable Catalog datasheet",
            },
          )
        : await createConfigurableCatalogRecord(config, table.table_id, {
            classification,
            content,
            change_reason: "Create configurable Catalog record",
          });
      setNotice(
        `${result.data.current_revision.content.name} revision ${result.data.current_revision.revision_no} saved.`,
      );
      await search();
      await selectRecord(result.data.record_id, result.data.current_revision.id);
      onNavigate(
        recordsRoutePath({
          tableId: result.data.table_id,
          tableRevisionId: result.data.current_revision.content.table_revision_id,
          folderId: result.data.current_revision.content.folder_id ?? "",
          folderRevisionId: result.data.current_revision.content.folder_revision_id ?? "",
          recordId: result.data.record_id,
          recordRevisionId: result.data.current_revision.id,
        }),
      );
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function createFolder(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!table) return;
    setBusy(true);
    try {
      const parent =
        folders.find((item) => item.folder_id === folderParentId) ?? null;
      const result = await createConfigurableCatalogFolder(config, table.table_id, {
        classification,
        content: {
          table_revision_id: table.current_revision.id,
          name: folderName.trim(),
          description: null,
          parent_folder_id: parent?.folder_id ?? null,
          parent_folder_revision_id: parent?.current_revision.id ?? null,
        },
        change_reason: "Create Catalog Folder",
      });
      setFolderName("");
      setSelectedFolderId(result.data.folder_id);
      setNotice("Folder revision created.");
      await loadDefinition();
      onNavigate(exactRecordsPath({
        tableId: result.data.table_id,
        tableRevisionId: result.data.content.table_revision_id,
        folderId: result.data.folder_id,
        folderRevisionId: result.data.current_revision.id,
      }));
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function reviseFolder(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!table) return;
    const folder = folders.find((item) => item.folder_id === selectedFolderId);
    if (!folder) return;
    const form = new FormData(event.currentTarget);
    const parent = folders.find(
      (item) => item.folder_id === String(form.get("parent")),
    );
    setBusy(true);
    setError(null);
    try {
      const result = await reviseConfigurableCatalogFolder(
        config,
        folder.folder_id,
        folder.current_revision,
        {
          content: {
            table_revision_id: table.current_revision.id,
            name: String(form.get("name") || "").trim(),
            description: String(form.get("description") || "").trim() || null,
            parent_folder_id: parent?.folder_id ?? null,
            parent_folder_revision_id: parent?.current_revision.id ?? null,
          },
          change_reason: "Update material folder",
        },
      );
      setNotice("Folder draft updated.");
      await loadDefinition();
      onNavigate(exactRecordsPath({
        tableId: result.data.table_id,
        tableRevisionId: result.data.content.table_revision_id,
        folderId: result.data.folder_id,
        folderRevisionId: result.data.current_revision.id,
      }));
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function checkOrPublishResource(
    aggregateType: string,
    aggregateId: string,
    revisionId: string,
  ) {
    setBusy(true);
    setError(null);
    try {
      const input = {
        aggregate_type: aggregateType,
        aggregate_id: aggregateId,
        revision_id: revisionId,
      };
      const result = await validateConfigurableCatalogPublication(config, input);
      if (!result.data.valid) throw new Error(result.data.errors.join(" "));
      setNotice("No publication errors were found. Request review to publish this revision.");
      await loadDefinition();
      await search();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function saveSubset() {
    if (!table || !subsetName.trim()) return;
    setBusy(true);
    try {
      await createConfigurableCatalogSubset(config, table.table_id, {
        table_revision_id: table.current_revision.id,
        name: subsetName.trim(),
        description: "Saved from Catalog record search",
        filter_definition: {
          text: query.trim() || null,
          folder_id: folderFilter || null,
          discrete_filters: facetFilters,
          number_attribute_id: numberAttributeId || null,
          number_minimum: numberMinimum || null,
          number_maximum: numberMaximum || null,
        },
        change_reason: "Save Catalog record search as Subset",
      });
      setSubsetName("");
      setNotice("Search saved as an immutable Subset revision.");
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  function applySubset(subset: ConfigurableSubsetResponse) {
    const filter = subset.filter_definition ?? {};
    setQuery(typeof filter.text === "string" ? filter.text : "");
    setFolderFilter(
      typeof filter.folder_id === "string" ? filter.folder_id : "",
    );
    setFacetFilters(
      filter.discrete_filters && typeof filter.discrete_filters === "object"
        ? (filter.discrete_filters as Record<string, string>)
        : {},
    );
    setNumberAttributeId(
      typeof filter.number_attribute_id === "string"
        ? filter.number_attribute_id
        : "",
    );
    setNumberMinimum(
      typeof filter.number_minimum === "string" ? filter.number_minimum : "",
    );
    setNumberMaximum(
      typeof filter.number_maximum === "string" ? filter.number_maximum : "",
    );
  }

  if (!config.accessToken.trim()) {
    return (
      <EngineeringPane className={productMode ? "record-auth-required" : "hero-card"} label="Material Database sign-in">
        <SemanticText semanticRole="sectionHeading" as="h1">Sign in to open the Material Database</SemanticText>
        <button
          className="ux-button primary"
          type="button"
          onClick={onOpenConnection}
        >
          Try again
        </button>
      </EngineeringPane>
    );
  }

  return (
    <div
      className={
        productMode
          ? "catalog-record-workbench administration-record-workbench"
          : "catalog-record-workbench"
      }
    >
      {!productMode ? (
        <section className="hero-card compact-hero catalog-record-hero">
          <div>
            <h1>Material records</h1>
            <p>
              Search typed records, edit Layout-driven datasheets and compare
              exact revisions.
            </p>
          </div>
          <div className="hero-actions">
            <button
              className="ux-button"
              type="button"
              onClick={() => onNavigate("/catalog/explorer")}
            >
              Explorer
            </button>
            <button
              className="ux-button"
              type="button"
              onClick={() => onNavigate("/catalog/schema")}
            >
              Schema designer
            </button>
          </div>
        </section>
      ) : null}
      {error || exactRouteError ? <WorkbenchMessage className="record-workbench-message" kind="error" title="Record action failed">{error ?? exactRouteError}</WorkbenchMessage> : null}
      {notice ? <SemanticStatus className="record-workbench-message" status="success" label={notice} /> : null}

      <EngineeringPane className="catalog-search-panel" label="Record scope and search">
        <div className="record-scope-row">
          <label className="ux-field">
            Record type
            <select
              className="ux-select"
              value={tableId}
              onChange={(event) => {
                const nextTableId = event.target.value;
                const nextTable = tables.find((item) => item.table_id === nextTableId) ?? null;
                setTableId(nextTableId);
                setSelectedFolderId("");
                onNavigate(exactRecordsPath({
                  tableId: nextTableId,
                  tableRevisionId: nextTable?.current_revision.id ?? "",
                  folderId: "",
                  folderRevisionId: "",
                  recordId: "",
                  recordRevisionId: "",
                }));
              }}
            >
              <option value="">Choose a record type</option>
              {tables.map((item) => (
                <option key={item.table_id} value={item.table_id}>
                  {item.current_revision.content.name} (Revision {item.current_revision.revision_no})
                </option>
              ))}
            </select>
          </label>
        </div>
        <form
          className="record-search-row"
          onSubmit={(event) => {
            event.preventDefault();
            void search();
          }}
        >
          <label className="ux-field">
            Search
            <input
              className="ux-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={`Search by name or ${identifierLabel.toLowerCase()}…`}
            />
          </label>
          <button
            className="ux-button tertiary local-action record-search-action"
            type="submit"
            disabled={busy}
          >
            Search
          </button>
        </form>
      </EngineeringPane>

      {entryMode === "multiple" ? (
        <EngineeringPane className="registration-panel" label="Record import">
          <div className="section-heading">
            <SemanticText semanticRole="sectionHeading">Import multiple records</SemanticText>
            <button
              className="ux-button tertiary"
              type="button"
              onClick={() => setEntryMode("closed")}
            >
              Close
            </button>
          </div>
          <div className="registration-file-workflow">
            <div className="registration-source-fields">
              <label className="ux-field">
                Source file
                <input
                  className="ux-input"
                  type="file"
                  accept=".csv,.tsv,.xlsx"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    setBulkFile(file);
                    setBulkSource(null);
                    setBulkPreview(null);
                    setBulkColumns([]);
                    setBulkMapping({});
                    if (file?.name.toLowerCase().endsWith(".xlsx"))
                      setBulkFormat("xlsx");
                    else if (file?.name.toLowerCase().endsWith(".tsv"))
                      setBulkFormat("tsv");
                    else setBulkFormat("csv");
                  }}
                />
              </label>
              <label className="ux-field">
                Header row
                <input
                  className="ux-input"
                  type="number"
                  min={1}
                  max={100}
                  value={bulkHeaderRow}
                  onChange={(event) =>
                    setBulkHeaderRow(Number(event.target.value))
                  }
                />
              </label>
              {bulkFormat === "csv" ? (
                <label className="ux-field">
                  Column separator
                  <select
                    className="ux-select"
                    value={bulkDelimiter}
                    onChange={(event) => setBulkDelimiter(event.target.value)}
                  >
                    <option value=",">Comma</option>
                    <option value=";">Semicolon</option>
                  </select>
                </label>
              ) : null}
              <label className="ux-field">
                Decimal separator
                <select
                  className="ux-select"
                  value={bulkDecimal}
                  onChange={(event) =>
                    setBulkDecimal(event.target.value as "." | ",")
                  }
                >
                  <option value=".">Point</option>
                  <option value=",">Comma</option>
                </select>
              </label>
              <label className="ux-field">
                Existing material
                <select
                  className="ux-select"
                  value={materialId}
                  onChange={(event) => setMaterialId(event.target.value)}
                >
                  <option value="">No material link</option>
                  {materials.map((item) => (
                    <option key={item.material_id} value={item.material_id}>
                      {item.current_revision.content.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="ux-field">
                Material state
                <select
                  className="ux-select"
                  value={materialStateId}
                  onChange={(event) => setMaterialStateId(event.target.value)}
                  disabled={!materialId}
                >
                  <option value="">No state link</option>
                  {materialStates.map((item) => (
                    <option
                      key={item.material_state_id}
                      value={item.material_state_id}
                    >
                      {item.current_revision.content.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {bulkColumns.length ? (
              <div className="registration-mapping">
                {bulkColumns.map((column) => {
                  const target = bulkMapping[column] ?? "";
                  const attribute = attributes.find(
                    (item) => item.current_revision.content.key === target,
                  );
                  return (
                    <div className="registration-column" key={column}>
                      <strong>{column}</strong>
                      <label className="ux-field">
                        Use as
                        <select
                          className="ux-select"
                          aria-label={`${column} field`}
                          value={target}
                          onChange={(event) =>
                            setBulkMapping((current) => ({
                              ...current,
                              [column]: event.target.value,
                            }))
                          }
                        >
                          <option value="">Do not import</option>
                          <option value="name">Record name</option>
                          <option value="code">Record code</option>
                          <option value="existing_material_code">
                            Existing material code
                          </option>
                          <option value="existing_state_name">
                            Existing state name
                          </option>
                          {attributes.map((item) => (
                            <option
                              key={item.attribute_definition_id}
                              value={item.current_revision.content.key}
                            >
                              {item.current_revision.content.name} ·{" "}
                              {
                                valueTypeLabels[
                                  item.current_revision.content.data_type
                                ]
                              }
                            </option>
                          ))}
                        </select>
                      </label>
                      {attribute?.current_revision.content.data_type ===
                      "number" ? (
                        <label className="ux-field">
                          Original unit
                          <input
                            className="ux-input"
                            aria-label={`${column} original unit`}
                            value={
                              bulkUnits[column] ??
                              attribute.current_revision.content
                                .normalized_unit ??
                              ""
                            }
                            onChange={(event) =>
                              setBulkUnits((current) => ({
                                ...current,
                                [column]: event.target.value,
                              }))
                            }
                            required
                          />
                        </label>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : null}
            <div className="ux-action-row">
              <button
                className="ux-button"
                type="button"
                onClick={() => void previewBulkRegistration()}
                disabled={busy || (!bulkFile && !bulkSource)}
              >
                {bulkColumns.length ? "Validate records" : "Read file columns"}
              </button>
              <button
                className="ux-button primary"
                type="button"
                onClick={() => void publishBulkRegistration()}
                disabled={busy || !bulkPreview?.valid}
              >
                Import validated records
              </button>
            </div>
            {bulkPreview?.sample_rows.length ? (
              <div className="registration-preview-table">
                <table>
                  <thead>
                    <tr>
                      {bulkPreview.source_columns.map((column) => (
                        <th key={column}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {bulkPreview.sample_rows.map((row, index) => (
                      <tr key={index}>
                        {bulkPreview.source_columns.map((column) => (
                          <td key={column}>{String(row[column] ?? "")}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
          {bulkPreview ? (
          <div
            className={
              bulkPreview.valid ? "record-workbench-message success-banner" : "registration-errors"
            }
            role="status"
          >
            {bulkPreview.valid ? (
              "All rows are valid."
            ) : (
              <>
                <h3>Rows to correct</h3>
                {bulkPreview.errors.map((item, index) =>
                  bulkPreview.source_columns.includes(item.column) ? (
                    <label className="ux-field" key={`${item.row}-${item.column}-${index}`}>
                      <span>
                        <strong>
                          Row {item.row}, {item.column}
                        </strong>{" "}
                        · {item.message}
                      </span>
                      <input
                        className="ux-input"
                        aria-label={`Correction for row ${item.row}, ${item.column}`}
                        value={bulkCorrections[item.row]?.[item.column] ?? ""}
                        onChange={(event) =>
                          setBulkCorrections((current) => ({
                            ...current,
                            [item.row]: {
                              ...(current[item.row] ?? {}),
                              [item.column]: event.target.value,
                            },
                          }))
                        }
                        placeholder={item.action}
                      />
                    </label>
                  ) : (
                    <p key={`${item.row}-${item.column}-${index}`}>
                      <strong>{item.column}</strong> · {item.message}{" "}
                      {item.action}
                    </p>
                  ),
                )}
              </>
            )}
          </div>
          ) : null}
      </EngineeringPane>
      ) : null}

      <div className={`catalog-record-grid ${entryMode === "single" ? "has-editor" : ""}`}>
        <details className="ux-engineering-pane catalog-facets">
          <summary>Filters</summary>
          <div className="record-filter-content">
          <section className="record-filter-group">
            <h3>Folder</h3>
            <label className="ux-field">
              Folder
              <select className="ux-select" value={folderFilter} onChange={(event) => setFolderFilter(event.target.value)}>
                <option value="">All folders</option>
                {folders.map((folder) => (
                  <option key={folder.folder_id} value={folder.folder_id}>
                    {folder.content.name}
                  </option>
                ))}
              </select>
            </label>
          </section>
          <section className="record-filter-group">
            <h3>Attribute filters</h3>
            <div className="range-filter-row">
              <select
                className="ux-select"
                aria-label="Numeric field"
                value={numberAttributeId}
                onChange={(event) => setNumberAttributeId(event.target.value)}
              >
                <option value="">No numeric range</option>
                {numberAttributes.map((attribute) => (
                  <option key={attribute.attribute_definition_id} value={attribute.attribute_definition_id}>
                    {attribute.current_revision.content.name}
                  </option>
                ))}
              </select>
              <input
                className="ux-input"
                aria-label="Minimum"
                value={numberMinimum}
                onChange={(event) => setNumberMinimum(event.target.value)}
                placeholder="Minimum in standard unit"
              />
              <input
                className="ux-input"
                aria-label="Maximum"
                value={numberMaximum}
                onChange={(event) => setNumberMaximum(event.target.value)}
                placeholder="Maximum in standard unit"
              />
            </div>
          {discreteAttributes.map((attribute) => {
            const buckets =
              results?.facets.filter(
                (item) =>
                  item.attribute_definition_id ===
                  attribute.attribute_definition_id,
              ) ?? [];
            return (
              <div
                className="facet-group"
                key={attribute.attribute_definition_id}
              >
                <strong>{attribute.current_revision.content.name}</strong>
                {buckets.map((bucket) => (
                  <button
                    className={
                      facetFilters[attribute.attribute_definition_id] ===
                      bucket.value
                        ? "facet-row active"
                        : "facet-row"
                    }
                    type="button"
                    key={bucket.value}
                    onClick={() =>
                      setFacetFilters((current) =>
                        current[attribute.attribute_definition_id] ===
                        bucket.value
                          ? Object.fromEntries(
                              Object.entries(current).filter(
                                ([key]) =>
                                  key !== attribute.attribute_definition_id,
                              ),
                            )
                          : {
                              ...current,
                              [attribute.attribute_definition_id]: bucket.value,
                            },
                      )
                    }
                  >
                    <span>{bucket.value}</span>
                    <small>{bucket.count}</small>
                  </button>
                ))}
              </div>
            );
          })}
          </section>
          <section className="record-filter-group">
            <h3>Saved views</h3>
            <div className="saved-subset-row">
              {subsets.map((subset) => (
                <button
                  className="ux-button tertiary local-action"
                  type="button"
                  key={subset.subset_id}
                  onClick={() => applySubset(subset)}
                >
                  {subset.name}
                </button>
              ))}
              <input
                className="ux-input"
                aria-label="View name"
                value={subsetName}
                onChange={(event) => setSubsetName(event.target.value)}
                placeholder="Save current search as…"
              />
              <button
                className="ux-button tertiary local-action"
                type="button"
                onClick={() => void saveSubset()}
              >
                Save view
              </button>
            </div>
          </section>
          <div className="folder-maker">
            <div className="section-heading">
              <h3>Manage folders</h3>
              <button
                className="ux-button tertiary local-action"
                type="button"
                onClick={() => {
                  setSelectedFolderId("");
                  onNavigate(exactRecordsPath({ folderId: "", folderRevisionId: "" }));
                }}
              >
                New folder
              </button>
            </div>
            <div className="folder-admin-list">
              {folders.map((folder) => (
                <button
                  className={
                    selectedFolderId === folder.folder_id ? "active" : ""
                  }
                  type="button"
                  key={folder.folder_id}
                  onClick={() => {
                    setSelectedFolderId(folder.folder_id);
                    onNavigate(exactRecordsPath({
                      folderId: folder.folder_id,
                      folderRevisionId: folder.current_revision.id,
                    }));
                  }}
                >
                  {folder.content.name}
                </button>
              ))}
            </div>
            {selectedFolder ? (
              <form
                key={selectedFolder.current_revision.id}
                className="ux-form"
                onSubmit={(event) => void reviseFolder(event)}
              >
                <input
                  className="ux-input"
                  name="name"
                  defaultValue={selectedFolder.content.name}
                  aria-label="Folder name"
                  required
                />
                <textarea
                  className="ux-textarea"
                  name="description"
                  defaultValue={selectedFolder.content.description ?? ""}
                  aria-label="Folder description"
                />
                <select
                  className="ux-select"
                  name="parent"
                  defaultValue={selectedFolder.content.parent_folder_id ?? ""}
                >
                  <option value="">Root folder</option>
                  {folders
                    .filter(
                      (folder) => folder.folder_id !== selectedFolder.folder_id,
                    )
                    .map((folder) => (
                      <option value={folder.folder_id} key={folder.folder_id}>
                        {folder.content.name}
                      </option>
                    ))}
                </select>
                <div className="ux-action-row">
                  <button
                    className="ux-button tertiary local-action"
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void checkOrPublishResource(
                        "catalog.folder",
                        selectedFolder.folder_id,
                        selectedFolder.current_revision.id,
                      )
                    }
                  >
                    Validate folder revision
                  </button>
                  <button
                    className="ux-button tertiary local-action"
                    type="submit"
                    disabled={busy}
                  >
                    Save new folder revision
                  </button>
                </div>
              </form>
            ) : exactRouteError ? null : (
              <form
                className="ux-form"
                onSubmit={(event) => void createFolder(event)}
              >
                <input
                  className="ux-input"
                  value={folderName}
                  onChange={(event) => setFolderName(event.target.value)}
                  placeholder="Folder name"
                  required
                />
                <select
                  className="ux-select"
                  value={folderParentId}
                  onChange={(event) => setFolderParentId(event.target.value)}
                >
                  <option value="">Root folder</option>
                  {folders.map((folder) => (
                    <option value={folder.folder_id} key={folder.folder_id}>
                      {folder.content.name}
                    </option>
                  ))}
                </select>
                <button
                  className="ux-button tertiary local-action"
                  type="submit"
                  disabled={busy}
                >
                  Create folder
                </button>
              </form>
            )}
          </div>
          </div>
        </details>

        <EngineeringPane className="catalog-record-list" label="Record results">
          <div className="section-heading">
            <div>
              <SemanticText semanticRole="sectionHeading">
                {table?.current_revision.content.name ?? "Select a record type"}
              </SemanticText>
              <SemanticText semanticRole="metadata">{recordCountLabel(results?.total_count ?? 0)}</SemanticText>
            </div>
            <div className="record-list-actions">
              <label className="ux-field record-display-layout">
                Display layout
                <select className="ux-select" value={layoutId} onChange={(event) => setLayoutId(event.target.value)}>
                  <option value="">All record type fields</option>
                  {layouts.map((item) => (
                    <option key={item.layout_id} value={item.layout_id}>
                      {item.name} (Revision {item.revision.revision_no})
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="ux-button tertiary local-action"
                type="button"
                onClick={() => setEntryMode("multiple")}
                disabled={!table}
              >
                Import records
              </button>
              <button
                className="ux-button primary"
                type="button"
                onClick={() => resetEditor(true)}
                disabled={!table}
              >
                Create record
              </button>
            </div>
          </div>
          <div className="record-result-table">
            <div className="record-result-heading" aria-hidden="true">
              <span>Name</span>
              <span>{identifierLabel}</span>
              <span>Revision</span>
              <span>Status</span>
            </div>
            {results?.items.map((record) => (
              <button
                className={
                  selected?.record_id === record.record_id
                    ? "record-result active"
                    : "record-result"
                }
                type="button"
                key={record.record_id}
                onClick={() => {
                  onNavigate(
                    recordsRoutePath({
                      tableId: record.table_id,
                      tableRevisionId: record.current_revision.content.table_revision_id,
                      folderId: selectedFolder?.folder_id ?? "",
                      folderRevisionId: selectedFolder?.current_revision.id ?? "",
                      recordId: record.record_id,
                      recordRevisionId: record.current_revision.id,
                    }),
                  );
                  void selectRecord(record.record_id, record.current_revision.id);
                }}
              >
                <span className="record-result-name">{record.current_revision.content.name}</span>
                <span>{recordIdentifierValue(record)}</span>
                <span>{record.current_revision.revision_no}</span>
                <span>{lifecycleLabel(record)}</span>
              </button>
            ))}
            {!results?.items.length ? (
              <p className="muted">No records match this typed query.</p>
            ) : null}
          </div>
        </EngineeringPane>

        {entryMode === "single" ? <EngineeringPane className="catalog-datasheet" label={selected ? `Edit ${selected.current_revision.content.name}` : "Create record"}>
          <div className="section-heading">
            <div>
              <SemanticText semanticRole="sectionHeading">
                {selected ? selected.current_revision.content.name : "Create record"}
              </SemanticText>
              {selected ? <SemanticText semanticRole="metadata">{lifecycleLabel(selected)} · Revision {selected.current_revision.revision_no}</SemanticText> : null}
            </div>
            <div className="record-editor-actions">
            {selectedIsHistorical && selected ? (
              <button
                className="ux-button tertiary local-action"
                disabled={busy}
                onClick={() => void selectCurrentRecord(selected.record_id).then((current) => {
                  if (!current) return;
                  onNavigate(recordsRoutePath({
                    tableId: current.table_id,
                    tableRevisionId: current.current_revision.content.table_revision_id,
                    folderId: current.current_revision.content.folder_id ?? "",
                    folderRevisionId: current.current_revision.content.folder_revision_id ?? "",
                    recordId: current.record_id,
                    recordRevisionId: current.current_revision.id,
                  }));
                })}
                type="button"
              >
                Open current revision
              </button>
            ) : null}
            <button
              className="ux-button tertiary local-action"
              type="button"
              onClick={() => resetEditor(false)}
            >
              Close
            </button>
            </div>
          </div>
          <form
            className="ux-form"
            onSubmit={(event) => void saveRecord(event)}
          >
            <fieldset disabled={selectedIsHistorical} className="record-edit-fields">
            <div className="ux-field-grid">
              <label className="ux-field">
                Name
                <input
                  className="ux-input"
                  value={recordName}
                  onChange={(event) => setRecordName(event.target.value)}
                  required
                />
              </label>
              <label className="ux-field">
                Record code
                <input
                  className="ux-input"
                  value={externalKey}
                  onChange={(event) => setExternalKey(event.target.value)}
                />
              </label>
              <label className="ux-field">
                Folder
                <select
                  className="ux-select"
                  value={recordFolderId}
                  onChange={(event) => setRecordFolderId(event.target.value)}
                >
                  <option value="">Unfiled</option>
                  {folders.map((folder) => (
                    <option key={folder.folder_id} value={folder.folder_id}>
                      {folder.content.name}
                    </option>
                  ))}
                </select>
              </label>
              {!selected ? (
                <label className="ux-field">
                  Access level
                  <select
                    className="ux-select"
                    value={classification}
                    onChange={(event) =>
                      setClassification(
                        event.target.value as DataClassification,
                      )
                    }
                  >
                    <option value="internal">Internal</option>
                    <option value="confidential">Confidential</option>
                    <option value="restricted">Restricted</option>
                  </select>
                </label>
              ) : null}
            </div>
            <label className="ux-field">
              Description
              <textarea
                className="ux-textarea"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
            <div className="record-attribute-fields">
              {orderedAttributes.map((attribute) => {
                const definition = attribute.current_revision.content;
                const draft =
                  drafts[attribute.attribute_definition_id] ??
                  emptyDraft(attribute);
                return (
                  <fieldset
                    key={attribute.attribute_definition_id}
                    className="record-attribute-field"
                  >
                    <legend className="sr-only">{definition.name}{definition.required ? " *" : ""}</legend>
                    <div className="record-attribute-heading">
                      <label className="ux-text-label" htmlFor={`record-attribute-${attribute.attribute_definition_id}`}>
                        {definition.name}{definition.required ? " *" : ""}
                      </label>
                      <label className="ux-checkbox">
                        <input
                          type="checkbox"
                          checked={draft.enabled}
                          disabled={definition.required}
                          onChange={(event) =>
                            updateDraft(attribute.attribute_definition_id, {
                              enabled: event.target.checked,
                            })
                          }
                        />
                        Include
                      </label>
                    </div>
                    {draft.enabled ? (
                      <div className="record-attribute-value">
                        <AttributeEditor
                          attribute={attribute}
                          draft={draft}
                          inputId={`record-attribute-${attribute.attribute_definition_id}`}
                          update={(patch) =>
                            updateDraft(attribute.attribute_definition_id, patch)
                          }
                        />
                      </div>
                    ) : null}
                  </fieldset>
                );
              })}
            </div>
            </fieldset>
            <div className="ux-action-row">
              <button
                className="ux-button tertiary local-action"
                type="submit"
                disabled={busy || selectedIsHistorical || !recordName.trim()}
              >
                {selected ? "Save new revision" : "Save new record"}
              </button>
              {selected ? (
                <>
                  <button
                    className="ux-button tertiary local-action"
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void checkOrPublishResource(
                        "catalog.configurable_record",
                        selected.record_id,
                        selected.current_revision.id,
                      )
                    }
                  >
                    Validate revision
                  </button>
                  <ReviewRequestAction
                    config={config}
                    subject={{
                      aggregateType: "catalog.configurable_record",
                      aggregateId: selected.record_id,
                      revisionId: selected.current_revision.id,
                      manifestSha256: selected.current_revision.content_hash,
                      classification: selected.current_revision.classification,
                      lifecycleState: selected.current_revision.lifecycle_state,
                    }}
                  />
                </>
              ) : null}
            </div>
          </form>
          {selected ? (
            <details className="revision-summary">
              <summary>{layout?.name ?? "Exact revision values"}</summary>
              {orderedAttributes.map((attribute) => {
                const value = selected.current_revision.content.values.find(
                  (item) =>
                    item.attribute_definition_id ===
                    attribute.attribute_definition_id,
                );
                return (
                  <div
                    className="revision-value-row"
                    key={attribute.attribute_definition_id}
                  >
                    <strong>{attribute.current_revision.content.name}</strong>
                    <span>{value ? valueLabel(value) : "Not entered"}</span>
                  </div>
                );
              })}
            </details>
          ) : null}
          {comparison ? (
            <details className="comparison-panel">
              <summary>Changes since revision 1</summary>
              {comparison.value_differences
                .filter((item) => item.status !== "unchanged")
                .map((difference) => {
                  const attribute = attributes.find(
                    (item) =>
                      item.attribute_definition_id ===
                      difference.attribute_definition_id,
                  );
                  return (
                    <div
                      className="comparison-row"
                      key={difference.attribute_definition_id}
                    >
                      <strong>
                        {attribute?.current_revision.content.name ??
                          "Attribute"}
                      </strong>
                      <small>
                        {difference.before
                          ? valueLabel(difference.before)
                          : "—"}{" "}
                        →{" "}
                        {difference.after ? valueLabel(difference.after) : "—"}
                      </small>
                    </div>
                  );
                })}
            </details>
          ) : null}
          {orderedAttributes.some((attribute) => attribute.current_revision.content.help_text) ? (
            <details className="record-field-definitions">
              <summary>Field definitions</summary>
              <dl>
                {orderedAttributes
                  .filter((attribute) => attribute.current_revision.content.help_text)
                  .map((attribute) => (
                    <div key={attribute.attribute_definition_id}>
                      <dt>{attribute.current_revision.content.name}</dt>
                      <dd>{attribute.current_revision.content.help_text}</dd>
                    </div>
                  ))}
              </dl>
            </details>
          ) : null}
        </EngineeringPane> : null}
      </div>
    </div>
  );
}

function AttributeEditor({
  attribute,
  draft,
  inputId,
  update,
}: {
  attribute: ConfigurableAttributeResponse;
  draft: DraftValue;
  inputId: string;
  update: (patch: Partial<DraftValue>) => void;
}) {
  const definition = attribute.current_revision.content;
  if (definition.data_type === "boolean") {
    return (
      <select
        className="ux-select"
        id={inputId}
        value={draft.primary}
        onChange={(event) => update({ primary: event.target.value })}
      >
        <option value="false">No</option>
        <option value="true">Yes</option>
      </select>
    );
  }
  if (definition.data_type === "discrete") {
    return (
      <select
        className="ux-select"
        id={inputId}
        value={draft.primary}
        onChange={(event) => update({ primary: event.target.value })}
        required={definition.required}
      >
        <option value="">Select…</option>
        {definition.allowed_values.map((value) => (
          <option value={value} key={value}>
            {value}
          </option>
        ))}
      </select>
    );
  }
  if (definition.data_type === "number") {
    return (
      <div className="number-value-grid">
        <input
          className="ux-input"
          id={inputId}
          type="number"
          step="any"
          value={draft.primary}
          onChange={(event) => update({ primary: event.target.value })}
          aria-label="Entered value"
          placeholder="Entered value"
          required={definition.required}
        />
        <input
          className="ux-input"
          value={draft.secondary}
          onChange={(event) => update({ secondary: event.target.value })}
          aria-label="Entered unit"
          placeholder="Entered unit"
          required={definition.required}
        />
      </div>
    );
  }
  if (definition.data_type === "file" || definition.data_type === "curve") {
    return (
      <details className="advanced-field">
        <summary>Evidence file</summary>
        <div className="number-value-grid">
          <input
            className="ux-input"
            id={inputId}
            value={draft.primary}
            onChange={(event) => update({ primary: event.target.value })}
            aria-label="Evidence file reference"
            placeholder="Evidence file reference"
            required={definition.required}
          />
          <input
            className="ux-input"
            value={draft.secondary}
            onChange={(event) => update({ secondary: event.target.value })}
            aria-label="Evidence file checksum"
            placeholder="Evidence file checksum"
            required={definition.required}
          />
        </div>
      </details>
    );
  }

  if (definition.data_type === "record_reference") {
    return (
      <details className="advanced-field">
        <summary>Advanced exact record reference</summary>
        <div className="number-value-grid">
          <input
            className="ux-input"
            id={inputId}
            value={draft.primary}
            onChange={(event) => update({ primary: event.target.value })}
            aria-label="Target record reference"
            placeholder="Target record reference"
            required={definition.required}
          />
          <input
            className="ux-input"
            value={draft.secondary}
            onChange={(event) => update({ secondary: event.target.value })}
            aria-label="Target version reference"
            placeholder="Target version reference"
            required={definition.required}
          />
        </div>
      </details>
    );
  }
  return (
    <input
      className="ux-input"
      id={inputId}
      type={
        definition.data_type === "date"
          ? "date"
          : definition.data_type === "integer"
            ? "number"
            : "text"
      }
      value={draft.primary}
      onChange={(event) => update({ primary: event.target.value })}
      required={definition.required}
    />
  );
}
