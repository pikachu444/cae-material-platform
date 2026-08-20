import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  createConfigurableCatalogDatabase,
  createConfigurableCatalogProfile,
  createConfigurableCatalogAttribute,
  createConfigurableCatalogLayout,
  createConfigurableCatalogLinkType,
  createConfigurableCatalogSubset,
  createConfigurableCatalogTable,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogDatabases,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogLinkTypes,
  listConfigurableCatalogProfiles,
  listConfigurableCatalogSubsets,
  listConfigurableCatalogTables,
  deleteConfigurableCatalogDraft,
  getDatabaseDesignAccess,
  getConfigurableCatalogAttributeRevision,
  searchConfigurableCatalogRecords,
  reviseConfigurableCatalogAttribute,
  reviseConfigurableCatalogDatabase,
  reviseConfigurableCatalogLayout,
  reviseConfigurableCatalogLinkType,
  reviseConfigurableCatalogProfile,
  reviseConfigurableCatalogSubset,
  reviseConfigurableCatalogTable,
  validateConfigurableCatalogPublication,
  catalogRevisionEtag,
  type ApiConfig,
} from "./api";
import type {
  ConfigurableAttributeDataType,
  ConfigurableAttributeRevision,
  ConfigurableAttributeResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableLayoutResponse,
  ConfigurableLinkCardinality,
  ConfigurableLinkTypeResponse,
  ConfigurableSubsetResponse,
  ConfigurableTableResponse,
  ConfigurableDatabaseResponse,
  ConfigurableProfileResponse,
  DataClassification,
  RevisionMetadata,
} from "../../../types";
import { publishWorkspaceStatus } from "../../../design/application-shell";
import { RecordPreview } from "./record-preview";
import "./database-design.css";

const dataTypes: Array<{ value: ConfigurableAttributeDataType; label: string }> = [
  { value: "number", label: "Number with unit" },
  { value: "integer", label: "Integer" },
  { value: "text", label: "Text" },
  { value: "boolean", label: "Boolean" },
  { value: "date", label: "Date" },
  { value: "discrete", label: "Discrete choice" },
  { value: "file", label: "File artifact" },
  { value: "curve", label: "Curve/table artifact" },
  { value: "record_reference", label: "Record reference" },
];

type DeleteTarget = {
  kind: "database" | "profile" | "table" | "attribute" | "layout" | "subset" | "link-type";
  label: string;
  aggregateId: string;
  revision: RevisionMetadata;
};

function message(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "The Catalog schema operation could not be completed.";
}

export function ConfigurableCatalogAdmin({
  config,
  onOpenConnection,
  onNavigate,
  productMode = false,
}: {
  config: ApiConfig;
  onOpenConnection: () => void;
  onNavigate?: (path: string) => void;
  productMode?: boolean;
}) {
  const [tables, setTables] = useState<ConfigurableTableResponse[]>([]);
  const [databases, setDatabases] = useState<ConfigurableDatabaseResponse[]>([]);
  const [profiles, setProfiles] = useState<ConfigurableProfileResponse[]>([]);
  const [selectedTableId, setSelectedTableId] = useState("");
  const [attributes, setAttributes] = useState<ConfigurableAttributeResponse[]>([]);
  const [attributeRevisions, setAttributeRevisions] = useState<ConfigurableAttributeRevision[]>([]);
  const [layouts, setLayouts] = useState<ConfigurableLayoutResponse[]>([]);
  const [subsets, setSubsets] = useState<ConfigurableSubsetResponse[]>([]);
  const [linkTypes, setLinkTypes] = useState<ConfigurableLinkTypeResponse[]>([]);
  const [previewRecords, setPreviewRecords] = useState<ConfigurableCatalogRecordResponse[]>([]);
  const [canConfigure, setCanConfigure] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [duplicateTableDraft, setDuplicateTableDraft] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const definitionRequestId = useRef(0);
  const deleteDialogRef = useRef<HTMLDialogElement>(null);
  const propertyEditorRef = useRef<HTMLElement>(null);

  const [tableKey, setTableKey] = useState("materials");
  const [tableName, setTableName] = useState("Materials");
  const [tableDescription, setTableDescription] = useState(
    "Configurable material datasheets and linked engineering records.",
  );
  const [classification, setClassification] = useState<DataClassification>("internal");

  const [attributeKey, setAttributeKey] = useState("manufacturer");
  const [attributeName, setAttributeName] = useState("Manufacturer");
  const [attributeHelpText, setAttributeHelpText] = useState("");
  const [attributeType, setAttributeType] = useState<ConfigurableAttributeDataType>("text");
  const [required, setRequired] = useState(false);
  const [quantitySemantics, setQuantitySemantics] = useState("");
  const [normalizedUnit, setNormalizedUnit] = useState("");
  const [allowedValues, setAllowedValues] = useState("");
  const [referenceTableId, setReferenceTableId] = useState("");
  const [linkKey, setLinkKey] = useState("has_test_data");
  const [linkName, setLinkName] = useState("Test evidence");
  const [sourceTableId, setSourceTableId] = useState("");
  const [targetTableId, setTargetTableId] = useState("");
  const [forwardLabel, setForwardLabel] = useState("has test evidence");
  const [reverseLabel, setReverseLabel] = useState("tests material");
  const [sourceCardinality, setSourceCardinality] = useState<ConfigurableLinkCardinality>("many");
  const [targetCardinality, setTargetCardinality] = useState<ConfigurableLinkCardinality>("many");
  const [objectKind, setObjectKind] = useState<"databases" | "profiles" | "tables" | "attributes" | "layouts" | "subsets" | "links">("tables");
  const [createMode, setCreateMode] = useState<"none" | "database" | "profile" | "table" | "attribute" | "link">("none");
  const [selectedAttributeId, setSelectedAttributeId] = useState("");
  const [selectedLinkTypeId, setSelectedLinkTypeId] = useState("");
  const [selectedDatabaseId, setSelectedDatabaseId] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [selectedLayoutId, setSelectedLayoutId] = useState("");
  const [selectedSubsetId, setSelectedSubsetId] = useState("");
  const [databaseKey, setDatabaseKey] = useState("materials");
  const [databaseName, setDatabaseName] = useState("Materials");
  const [databaseDescription, setDatabaseDescription] = useState("Material data and engineering properties.");
  const [profileKey, setProfileKey] = useState("general");
  const [profileName, setProfileName] = useState("General");
  const [profileDescription, setProfileDescription] = useState("General material properties.");

  const selectedTable = useMemo(
    () => tables.find((item) => item.table_id === selectedTableId) ?? null,
    [selectedTableId, tables],
  );

  useEffect(() => {
    publishWorkspaceStatus({
      selection: selectedTable ? `Table · ${selectedTable.current_revision.content.name}` : "Database design",
      revision: selectedTable ? `r${selectedTable.current_revision.revision_no} · governed configuration` : `${tables.length} tables`,
      jobs: loading ? "Loading schema" : saving ? "Saving draft" : notice ? "Last operation completed" : "No active job",
      warnings: error ? "1 validation or service error" : "0 validation errors",
      connection: error ? "degraded" : "online",
    });
  }, [error, loading, notice, saving, selectedTable, tables.length]);

  useEffect(() => {
    const dialog = deleteDialogRef.current;
    if (deleteTarget && dialog && !dialog.open) dialog.showModal();
    if (!deleteTarget && dialog?.open) dialog.close();
  }, [deleteTarget]);

  const loadTables = useCallback(async () => {
    if (!config.accessToken.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [result, linkTypeResult, databaseResult, accessResult] = await Promise.all([
        listConfigurableCatalogTables(config),
        listConfigurableCatalogLinkTypes(config),
        listConfigurableCatalogDatabases(config),
        getDatabaseDesignAccess(config),
      ]);
      setTables(result.data.items);
      setLinkTypes(linkTypeResult.data.items);
      setDatabases(databaseResult.data.items);
      setCanConfigure(accessResult.data.feature_grants.includes("schema_configuration"));
      setSelectedDatabaseId((current) =>
        databaseResult.data.items.some((item) => item.database_id === current)
          ? current
          : (databaseResult.data.items[0]?.database_id ?? ""),
      );
      setSelectedTableId((current) =>
        result.data.items.some((item) => item.table_id === current)
          ? current
          : (result.data.items[0]?.table_id ?? ""),
      );
      setSourceTableId((current) => current || result.data.items[0]?.table_id || "");
      setTargetTableId((current) => current || result.data.items[0]?.table_id || "");
    } catch (caught) {
      setError(message(caught));
    } finally {
      setLoading(false);
    }
  }, [config]);

  const loadProfiles = useCallback(async () => {
    if (!selectedDatabaseId || !config.accessToken.trim()) {
      setProfiles([]);
      setSelectedProfileId("");
      return;
    }
    try {
      const result = await listConfigurableCatalogProfiles(config, selectedDatabaseId);
      setProfiles(result.data.items);
      setSelectedProfileId((current) =>
        result.data.items.some((item) => item.profile_id === current)
          ? current
          : (result.data.items[0]?.profile_id ?? ""),
      );
    } catch (caught) {
      setError(message(caught));
    }
  }, [config, selectedDatabaseId]);

  const loadDefinition = useCallback(async () => {
    const requestId = ++definitionRequestId.current;
    if (!selectedTableId || !config.accessToken.trim()) {
      setAttributes([]);
      setAttributeRevisions([]);
      setLayouts([]);
      setSubsets([]);
      setPreviewRecords([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [attributeResult, layoutResult, subsetResult, recordResult] = await Promise.all([
        listConfigurableCatalogAttributes(config, selectedTableId),
        listConfigurableCatalogLayouts(config, selectedTableId),
        listConfigurableCatalogSubsets(config, selectedTableId),
        searchConfigurableCatalogRecords(config, selectedTableId),
      ]);
      const currentRevisionKeys = new Set(
        attributeResult.data.items.map(
          (attribute) => `${attribute.attribute_definition_id}:${attribute.current_revision.id}`,
        ),
      );
      const historicalPins = new Map<string, { attributeId: string; revisionId: string }>();
      for (const layout of layoutResult.data.items) {
        for (const item of layout.items) {
          const key = `${item.attribute_definition_id}:${item.attribute_definition_revision_id}`;
          if (!currentRevisionKeys.has(key)) {
            historicalPins.set(key, {
              attributeId: item.attribute_definition_id,
              revisionId: item.attribute_definition_revision_id,
            });
          }
        }
      }
      const historicalResults = await Promise.all(
        [...historicalPins.values()].map(({ attributeId, revisionId }) =>
          getConfigurableCatalogAttributeRevision(config, attributeId, revisionId),
        ),
      );
      if (requestId !== definitionRequestId.current) {
        return;
      }
      setAttributes(attributeResult.data.items);
      setAttributeRevisions([
        ...attributeResult.data.items.map((attribute) => attribute.current_revision),
        ...historicalResults.map((result) => result.data),
      ]);
      setLayouts(layoutResult.data.items);
      setSubsets(subsetResult.data.items);
      setPreviewRecords(recordResult.data.items);
      setSelectedAttributeId((current) =>
        attributeResult.data.items.some((item) => item.attribute_definition_id === current)
          ? current
          : (attributeResult.data.items[0]?.attribute_definition_id ?? ""),
      );
      setSelectedLayoutId((current) =>
        layoutResult.data.items.some((item) => item.layout_id === current)
          ? current
          : (layoutResult.data.items[0]?.layout_id ?? ""),
      );
      setSelectedSubsetId((current) =>
        subsetResult.data.items.some((item) => item.subset_id === current)
          ? current
          : (subsetResult.data.items[0]?.subset_id ?? ""),
      );
    } catch (caught) {
      if (requestId === definitionRequestId.current) {
        setError(message(caught));
      }
    } finally {
      if (requestId === definitionRequestId.current) {
        setLoading(false);
      }
    }
  }, [config, selectedTableId]);

  useEffect(() => {
    void loadTables();
  }, [loadTables]);

  useEffect(() => {
    void loadProfiles();
  }, [loadProfiles]);

  useEffect(() => {
    void loadDefinition();
    return () => {
      definitionRequestId.current += 1;
    };
  }, [loadDefinition]);

  function requireConfigurationAccess(): boolean {
    if (canConfigure) return true;
    setError("Database design changes require the schema configuration permission.");
    return false;
  }

  async function createTable(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!requireConfigurationAccess()) return;
    if (!duplicateTableDraft && !selectedProfile) {
      setError("Choose the Profile that will contain this Table.");
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createConfigurableCatalogTable(config, {
        classification,
        content: {
          key: tableKey.trim(),
          name: tableName.trim(),
          description: tableDescription.trim() || null,
        },
        change_reason: "Create administrator-defined Catalog Table",
        ...(duplicateTableDraft
          ? {}
          : {
              profile_id: selectedProfile?.profile_id,
              profile_revision_id: selectedProfile?.current_revision.id,
            }),
      });
      setNotice(`${result.data.current_revision.content.name} Table revision 1 created.`);
      setDuplicateTableDraft(false);
      await loadTables();
      setSelectedTableId(result.data.table_id);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createDatabase(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!requireConfigurationAccess()) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createConfigurableCatalogDatabase(config, {
        classification,
        content: { key: databaseKey.trim(), name: databaseName.trim(), description: databaseDescription.trim() || null },
        change_reason: "Create material database",
      });
      setNotice(`${result.data.current_revision.content.name} database created.`);
      await loadTables();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!requireConfigurationAccess()) return;
    const database = databases.find((item) => item.database_id === selectedDatabaseId);
    if (!database) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createConfigurableCatalogProfile(config, {
        classification,
        content: {
          database_id: database.database_id,
          database_revision_id: database.current_revision.id,
          key: profileKey.trim(),
          name: profileName.trim(),
          description: profileDescription.trim() || null,
        },
        change_reason: "Create material profile",
      });
      setNotice(`${result.data.current_revision.content.name} profile created.`);
      await loadTables();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createAttribute(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!requireConfigurationAccess()) return;
    if (!selectedTable) {
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const choices = allowedValues
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const result = await createConfigurableCatalogAttribute(config, selectedTable.table_id, {
        content: {
          table_revision_id: selectedTable.current_revision.id,
          key: attributeKey.trim(),
          name: attributeName.trim(),
          data_type: attributeType,
          required,
          quantity_semantics: quantitySemantics.trim() || null,
          normalized_unit: normalizedUnit.trim() || null,
          minimum_number: null,
          maximum_number: null,
          minimum_length: null,
          maximum_length: null,
          pattern: null,
          allowed_values: attributeType === "discrete" ? choices : [],
          reference_table_id:
            attributeType === "record_reference" ? referenceTableId || null : null,
          help_text: attributeHelpText.trim() || null,
        },
        change_reason: "Add typed Attribute Definition",
      });
      setNotice(`${result.data.current_revision.content.name} Attribute revision 1 created.`);
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createDefaultLayout() {
    if (!requireConfigurationAccess()) return;
    if (!selectedTable || !attributes.length) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createConfigurableCatalogLayout(config, selectedTable.table_id, {
        table_revision_id: selectedTable.current_revision.id,
        name: "Engineering datasheet",
        description: "Default administrator-defined datasheet layout.",
        items: attributes.map((attribute, ordinal) => ({
          attribute_definition_id: attribute.attribute_definition_id,
          attribute_definition_revision_id: attribute.current_revision.id,
          section: "General",
          ordinal,
        })),
        change_reason: "Create default Catalog datasheet Layout",
      });
      setNotice("Engineering datasheet Layout created from the current Attribute revisions.");
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createAllRecordsSubset() {
    if (!requireConfigurationAccess()) return;
    if (!selectedTable) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createConfigurableCatalogSubset(config, selectedTable.table_id, {
        table_revision_id: selectedTable.current_revision.id,
        name: "All records",
        description: "Unfiltered starting subset for this Table.",
        filter_definition: {},
        change_reason: "Create initial saved Catalog Subset",
      });
      setNotice("All records Subset revision 1 created.");
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createLinkType(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!requireConfigurationAccess()) return;
    const sourceTable = tables.find((table) => table.table_id === sourceTableId);
    const targetTable = tables.find((table) => table.table_id === targetTableId);
    if (!sourceTable || !targetTable) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createConfigurableCatalogLinkType(config, {
        classification,
        content: {
          key: linkKey.trim(),
          name: linkName.trim(),
          source_table_id: sourceTable.table_id,
          source_table_revision_id: sourceTable.current_revision.id,
          target_table_id: targetTable.table_id,
          target_table_revision_id: targetTable.current_revision.id,
          forward_label: forwardLabel.trim(),
          reverse_label: reverseLabel.trim(),
          source_cardinality: sourceCardinality,
          target_cardinality: targetCardinality,
          description: null,
        },
        change_reason: "Create administrator-defined exact Record Link Type",
      });
      setNotice(`${result.data.current_revision.content.name} Link Type revision 1 created.`);
      await loadTables();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function perform(action: () => Promise<unknown>, success: string) {
    if (!requireConfigurationAccess()) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      await loadTables();
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function checkOrPublish(
    aggregateType: string,
    aggregateId: string,
    revisionId: string,
    publish: boolean,
  ) {
    if (publish) {
      setNotice("Publish is not configured here. The current draft remains unchanged.");
      return;
    }
    await perform(async () => {
      const input = {
        aggregate_type: aggregateType,
        aggregate_id: aggregateId,
        revision_id: revisionId,
      };
      const result = await validateConfigurableCatalogPublication(config, input);
      if (!result.data.valid) throw new Error(result.data.errors.join(" "));
    }, "No publication errors were found. The draft remains unpublished.");
  }

  async function reviseDatabase(event: React.FormEvent<HTMLFormElement>, item: ConfigurableDatabaseResponse) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await perform(
      () => reviseConfigurableCatalogDatabase(config, item.database_id, catalogRevisionEtag(item.current_revision), {
        content: {
          ...item.current_revision.content,
          name: String(form.get("name") || "").trim(),
          description: String(form.get("description") || "").trim() || null,
        },
        change_reason: "Update material database details",
      }),
      "Database draft updated.",
    );
  }

  async function reviseProfile(event: React.FormEvent<HTMLFormElement>, item: ConfigurableProfileResponse) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await perform(
      () => reviseConfigurableCatalogProfile(config, item.profile_id, catalogRevisionEtag(item.current_revision), {
        content: {
          ...item.current_revision.content,
          name: String(form.get("name") || "").trim(),
          description: String(form.get("description") || "").trim() || null,
        },
        change_reason: "Update material profile details",
      }),
      "Profile draft updated.",
    );
  }

  async function reviseTable(event: React.FormEvent<HTMLFormElement>, item: ConfigurableTableResponse) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await perform(
      () => reviseConfigurableCatalogTable(config, item.table_id, item.current_revision, {
        content: {
          ...item.current_revision.content,
          name: String(form.get("name") || "").trim(),
          description: String(form.get("description") || "").trim() || null,
        },
        change_reason: "Update material table details",
      }),
      "Table draft updated.",
    );
  }

  async function reviseAttribute(event: React.FormEvent<HTMLFormElement>, item: ConfigurableAttributeResponse) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const content = item.current_revision.content;
    await perform(
      () => reviseConfigurableCatalogAttribute(config, item.attribute_definition_id, item.current_revision, {
        content: {
          ...content,
          name: String(form.get("name") || "").trim(),
          required: form.get("required") === "on",
          help_text: String(form.get("help_text") || "").trim() || null,
          quantity_semantics: content.data_type === "number" ? String(form.get("quantity") || "").trim() || null : null,
          normalized_unit: content.data_type === "number" ? String(form.get("unit") || "").trim() || null : null,
        },
        change_reason: "Update material Attribute details",
      }),
      "Attribute draft updated.",
    );
  }

  async function reviseLayout(event: React.FormEvent<HTMLFormElement>, item: ConfigurableLayoutResponse) {
    event.preventDefault();
    if (!selectedTable) return;
    const form = new FormData(event.currentTarget);
    const selected = new Set(form.getAll("layout_attribute").map(String));
    await perform(
      () => reviseConfigurableCatalogLayout(config, item.layout_id, item.revision, {
        table_revision_id: selectedTable.current_revision.id,
        name: String(form.get("name") || "").trim(),
        description: String(form.get("description") || "").trim() || null,
        items: attributes.filter((attribute) => selected.has(attribute.attribute_definition_id)).map((attribute, ordinal) => ({
          attribute_definition_id: attribute.attribute_definition_id,
          attribute_definition_revision_id: attribute.current_revision.id,
          section: "General",
          ordinal,
        })),
        change_reason: "Update datasheet field selection",
      }),
      "Layout draft updated with the selected fields.",
    );
  }

  async function reviseSubset(event: React.FormEvent<HTMLFormElement>, item: ConfigurableSubsetResponse) {
    event.preventDefault();
    if (!selectedTable) return;
    const form = new FormData(event.currentTarget);
    await perform(
      () => reviseConfigurableCatalogSubset(config, item.subset_id, item.revision, {
        table_revision_id: selectedTable.current_revision.id,
        name: String(form.get("name") || "").trim(),
        description: String(form.get("description") || "").trim() || null,
        filter_definition: JSON.parse(String(form.get("filter") || "{}")) as Record<string, unknown>,
        change_reason: "Update saved material view",
      }),
      "Subset draft updated.",
    );
  }

  async function reviseLinkType(event: React.FormEvent<HTMLFormElement>, item: ConfigurableLinkTypeResponse) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await perform(
      () => reviseConfigurableCatalogLinkType(config, item.link_type_id, item.current_revision, {
        content: {
          ...item.current_revision.content,
          name: String(form.get("name") || "").trim(),
          forward_label: String(form.get("forward") || "").trim(),
          reverse_label: String(form.get("reverse") || "").trim(),
          source_cardinality: String(form.get("source_cardinality")) as ConfigurableLinkCardinality,
          target_cardinality: String(form.get("target_cardinality")) as ConfigurableLinkCardinality,
        },
        change_reason: "Update exact Record relationship",
      }),
      "Link Type draft updated.",
    );
  }

  function duplicateKey(value: string): string {
    return `${value.slice(0, 58)}_copy`;
  }

  async function duplicateSelected() {
    if (!requireConfigurationAccess()) return;
    setError(null);
    setNotice(null);
    if (objectKind === "databases") {
      const item = databases.find((candidate) => candidate.database_id === selectedDatabaseId);
      if (!item) return;
      setDatabaseKey(duplicateKey(item.current_revision.content.key));
      setDatabaseName(`${item.current_revision.content.name} copy`);
      setDatabaseDescription(item.current_revision.content.description ?? "");
      setCreateMode("database");
      return;
    }
    if (objectKind === "profiles") {
      const item = profiles.find((candidate) => candidate.profile_id === selectedProfileId);
      if (!item) return;
      setProfileKey(duplicateKey(item.current_revision.content.key));
      setProfileName(`${item.current_revision.content.name} copy`);
      setProfileDescription(item.current_revision.content.description ?? "");
      setCreateMode("profile");
      return;
    }
    if (objectKind === "tables") {
      const item = tables.find((candidate) => candidate.table_id === selectedTableId);
      if (!item) return;
      setTableKey(duplicateKey(item.current_revision.content.key));
      setTableName(`${item.current_revision.content.name} copy`);
      setTableDescription(item.current_revision.content.description ?? "");
      setDuplicateTableDraft(true);
      setCreateMode("table");
      return;
    }
    if (objectKind === "attributes") {
      const item = attributes.find(
        (candidate) => candidate.attribute_definition_id === selectedAttributeId,
      );
      if (!item) return;
      const content = item.current_revision.content;
      setAttributeKey(duplicateKey(content.key));
      setAttributeName(`${content.name} copy`);
      setAttributeHelpText(content.help_text ?? "");
      setAttributeType(content.data_type);
      setRequired(content.required);
      setQuantitySemantics(content.quantity_semantics ?? "");
      setNormalizedUnit(content.normalized_unit ?? "");
      setAllowedValues(content.allowed_values.join(", "));
      setReferenceTableId(content.reference_table_id ?? "");
      setCreateMode("attribute");
      return;
    }
    if (objectKind === "layouts") {
      const item = layouts.find((candidate) => candidate.layout_id === selectedLayoutId);
      if (!item) return;
      await perform(
        () => createConfigurableCatalogLayout(config, item.table_id, {
          table_revision_id: item.table_revision_id,
          name: `${item.name} copy`,
          description: item.description,
          items: item.items,
          change_reason: "Duplicate exact Layout draft",
        }),
        `${item.name} was duplicated as a new revision 1 draft.`,
      );
      return;
    }
    if (objectKind === "subsets") {
      const item = subsets.find((candidate) => candidate.subset_id === selectedSubsetId);
      if (!item) return;
      await perform(
        () => createConfigurableCatalogSubset(config, item.table_id, {
          table_revision_id: item.table_revision_id,
          name: `${item.name} copy`,
          description: item.description,
          filter_definition: item.filter_definition ?? {},
          change_reason: "Duplicate exact Subset draft",
        }),
        `${item.name} was duplicated as a new revision 1 draft.`,
      );
      return;
    }
    const item = linkTypes.find((candidate) => candidate.link_type_id === selectedLinkTypeId);
    if (!item) return;
    const content = item.current_revision.content;
    setLinkKey(duplicateKey(content.key));
    setLinkName(`${content.name} copy`);
    setSourceTableId(content.source_table_id);
    setTargetTableId(content.target_table_id);
    setForwardLabel(content.forward_label);
    setReverseLabel(content.reverse_label);
    setSourceCardinality(content.source_cardinality);
    setTargetCardinality(content.target_cardinality);
    setCreateMode("link");
  }

  async function confirmDraftDelete() {
    if (!deleteTarget) return;
    if (!requireConfigurationAccess()) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await deleteConfigurableCatalogDraft(
        config,
        deleteTarget.kind,
        deleteTarget.aggregateId,
        deleteTarget.revision,
      );
      setNotice(`${deleteTarget.label} unpublished draft was permanently deleted.`);
      const deletedKind = deleteTarget.kind;
      setDeleteTarget(null);
      if (deletedKind === "table") setSelectedTableId("");
      await loadTables();
      if (["attribute", "layout", "subset"].includes(deletedKind)) await loadDefinition();
    } catch (caught) {
      setError(message(caught));
      setDeleteTarget(null);
    } finally {
      setSaving(false);
    }
  }

  if (!config.accessToken.trim()) {
    return (
      <section className="hero-card">
        <p className="eyebrow">Catalog administration</p>
        <h1>Administrator sign-in required</h1>
        <p>Create configurable Tables, typed Attributes, datasheet Layouts and saved Subsets.</p>
        <button className="ux-button primary" type="button" onClick={onOpenConnection}>
          Try again
        </button>
      </section>
    );
  }

  const selectedAttribute = attributes.find((item) => item.attribute_definition_id === selectedAttributeId) ?? null;
  const selectedLinkType = linkTypes.find((item) => item.link_type_id === selectedLinkTypeId) ?? null;
  const selectedDatabase = databases.find((item) => item.database_id === selectedDatabaseId) ?? null;
  const selectedProfile = profiles.find((item) => item.profile_id === selectedProfileId) ?? null;
  const selectedLayout = layouts.find((item) => item.layout_id === selectedLayoutId) ?? null;
  const selectedSubset = subsets.find((item) => item.subset_id === selectedSubsetId) ?? null;
  const selectedLinkSourceTable = selectedLinkType
    ? tables.find((item) => item.table_id === selectedLinkType.current_revision.content.source_table_id) ?? null
    : null;
  const selectedLinkTargetTable = selectedLinkType
    ? tables.find((item) => item.table_id === selectedLinkType.current_revision.content.target_table_id) ?? null
    : null;
  const scopedLinkTypes = linkTypes.filter((item) =>
    item.current_revision.content.source_table_id === selectedTableId
    || item.current_revision.content.target_table_id === selectedTableId,
  );
  const activeDeleteTarget: DeleteTarget | null = objectKind === "databases" && selectedDatabase
    ? { kind: "database", label: selectedDatabase.current_revision.content.name, aggregateId: selectedDatabase.database_id, revision: selectedDatabase.current_revision }
    : objectKind === "profiles" && selectedProfile
      ? { kind: "profile", label: selectedProfile.current_revision.content.name, aggregateId: selectedProfile.profile_id, revision: selectedProfile.current_revision }
      : objectKind === "tables" && selectedTable
        ? { kind: "table", label: selectedTable.current_revision.content.name, aggregateId: selectedTable.table_id, revision: selectedTable.current_revision }
        : objectKind === "attributes" && selectedAttribute
          ? { kind: "attribute", label: selectedAttribute.current_revision.content.name, aggregateId: selectedAttribute.attribute_definition_id, revision: selectedAttribute.current_revision }
          : objectKind === "layouts" && selectedLayout
            ? { kind: "layout", label: selectedLayout.name, aggregateId: selectedLayout.layout_id, revision: selectedLayout.revision }
            : objectKind === "subsets" && selectedSubset
              ? { kind: "subset", label: selectedSubset.name, aggregateId: selectedSubset.subset_id, revision: selectedSubset.revision }
              : objectKind === "links" && selectedLinkType
                ? { kind: "link-type", label: selectedLinkType.current_revision.content.name, aggregateId: selectedLinkType.link_type_id, revision: selectedLinkType.current_revision }
                : null;
  const deleteEligibility = !activeDeleteTarget
    ? "Select an object first."
    : activeDeleteTarget.revision.lifecycle_state !== "draft"
      ? "Published objects and their immutable history cannot be deleted."
      : activeDeleteTarget.revision.revision_no !== 1
        ? "Only an unpublished first draft can be deleted."
        : null;
  const deleteBlockReason = !canConfigure
    ? "Schema configuration permission is required to delete a draft."
    : deleteEligibility;

  if (productMode) {
    const objectRows = objectKind === "databases" ? databases : objectKind === "profiles" ? profiles : objectKind === "tables" ? tables : objectKind === "attributes" ? attributes : objectKind === "layouts" ? layouts : objectKind === "subsets" ? subsets : scopedLinkTypes;
    const objectLabel = objectKind === "databases" ? "Databases" : objectKind === "profiles" ? "Profiles" : objectKind === "tables" ? "Tables" : objectKind === "attributes" ? "Attributes" : objectKind === "layouts" ? "Layouts" : objectKind === "subsets" ? "Subsets" : "Link Types";
    const openCreate = () => {
      setDuplicateTableDraft(false);
      setCreateMode(objectKind === "databases" ? "database" : objectKind === "profiles" ? "profile" : objectKind === "tables" ? "table" : objectKind === "attributes" ? "attribute" : objectKind === "links" ? "link" : "none");
    };
    return (
      <section className="catalog-schema-editor" aria-label="Database design">
        <header className="schema-editor-header">
          <div><h2>Database design</h2><p>Choose an exact identity and revision, complete the task here, and review a real Record beside it.</p></div>
          <div className="schema-command-group">
            <div className="schema-command-bar" aria-label="Database design commands">
              <button className="ux-button" type="button" onClick={() => void loadTables()}>Refresh</button>
              <button className="ux-button" type="button" aria-pressed={previewOpen} onClick={() => setPreviewOpen((current) => !current)}>{previewOpen ? "Close preview" : "Preview datasheet"}</button>
              {objectKind === "layouts" ? <button className="ux-button primary" type="button" disabled={saving || !canConfigure || !attributes.length} onClick={() => void createDefaultLayout()}>Add layout</button> : null}
              {objectKind === "subsets" ? <button className="ux-button primary" type="button" disabled={saving || !canConfigure || !selectedTable} onClick={() => void createAllRecordsSubset()}>Add subset</button> : null}
              {objectKind !== "layouts" && objectKind !== "subsets" ? <button className="ux-button primary" type="button" disabled={saving || !canConfigure || (objectKind === "attributes" && !selectedTable) || (objectKind === "profiles" && !selectedDatabase)} onClick={openCreate}>Add {objectKind === "links" ? "Link Type" : objectKind === "tables" ? "Table" : objectKind === "attributes" ? "Attribute" : objectKind === "databases" ? "Database" : "Profile"}</button> : null}
              <button className="ux-button" type="button" disabled={saving || !canConfigure || !activeDeleteTarget} onClick={() => { setCreateMode("none"); propertyEditorRef.current?.focus(); }}>Edit</button>
              <button className="ux-button" type="button" disabled={saving || !canConfigure || !activeDeleteTarget} onClick={() => void duplicateSelected()}>Duplicate</button>
              <button className="ux-button danger" type="button" aria-describedby={activeDeleteTarget && deleteBlockReason ? "schema-delete-reason" : undefined} title={deleteBlockReason ?? "Permanently delete this unused unpublished first draft."} disabled={saving || Boolean(deleteBlockReason)} onClick={() => setDeleteTarget(activeDeleteTarget)}>Delete draft</button>
            </div>
            {activeDeleteTarget && deleteBlockReason ? <p id="schema-delete-reason" className="schema-delete-reason" role="status">{deleteBlockReason}</p> : null}
          </div>
        </header>
        {error ? <div className="error-banner" role="alert">{error}</div> : null}
        {notice ? <div className="success-banner" role="status">{notice}</div> : null}
        <div className="schema-editor-grid">
          <nav className="schema-object-navigator" aria-label="Database objects">
            <p>Objects</p>
            {(["databases", "profiles", "tables", "attributes", "layouts", "subsets", "links"] as const).map((kind) => {
              const count = kind === "databases" ? databases.length : kind === "profiles" ? profiles.length : kind === "tables" ? tables.length : kind === "attributes" ? attributes.length : kind === "layouts" ? layouts.length : kind === "subsets" ? subsets.length : scopedLinkTypes.length;
              const label = kind === "links" ? "Link Types" : kind[0]!.toUpperCase() + kind.slice(1);
              return <button aria-label={label} className={objectKind === kind ? "active" : ""} type="button" key={kind} onClick={() => { setObjectKind(kind); setCreateMode("none"); }}><span>{label}</span><small>{count}</small></button>;
            })}
            {databases.length ? <div className="schema-table-context">
              <label htmlFor="schema-database-context">Current database</label>
              <select id="schema-database-context" value={selectedDatabaseId} onChange={(event) => { setSelectedDatabaseId(event.target.value); setCreateMode("none"); }}>
                {databases.map((database) => <option key={database.database_id} value={database.database_id}>{database.current_revision.content.name} · r{database.current_revision.revision_no}</option>)}
              </select>
              <p>Profiles are queried from this exact Database selection.</p>
            </div> : null}
            {tables.length ? <div className="schema-table-context">
              <label htmlFor="schema-table-context">Current table</label>
              <select id="schema-table-context" value={selectedTableId} onChange={(event) => { setSelectedTableId(event.target.value); setCreateMode("none"); }}>
                {tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}
              </select>
              <p>Attributes, layouts and subsets follow this table.</p>
            </div> : <div className="schema-table-context" role="status"><strong>No tables yet</strong><p>Add a Table before defining its Attributes, Layouts or Subsets.</p></div>}
          </nav>
          <section className="schema-object-list" aria-label={`${objectLabel} list`}>
            <header><h3>{objectLabel}</h3><span>{loading ? "Loading…" : `${objectRows.length} shown`}</span></header>
            <div className="schema-list-columns" aria-hidden="true"><span>Name</span><span>{objectKind === "links" ? "Cardinality" : "Identity"}</span><span>Rev</span></div>
            <div className="schema-list-rows">
              {objectKind === "databases" ? databases.map((item) => <button title={item.current_revision.content.description ?? undefined} className={selectedDatabaseId === item.database_id ? "active" : ""} type="button" key={item.database_id} onClick={() => { setSelectedDatabaseId(item.database_id); setCreateMode("none"); }}><strong>{item.current_revision.content.name}</strong><small>{item.current_revision.content.key}</small><span>r{item.current_revision.revision_no}</span></button>) : null}
              {objectKind === "profiles" ? profiles.map((item) => <button title={item.current_revision.content.description ?? undefined} className={selectedProfileId === item.profile_id ? "active" : ""} type="button" key={item.profile_id} onClick={() => { setSelectedProfileId(item.profile_id); setCreateMode("none"); }}><strong>{item.current_revision.content.name}</strong><small>{item.current_revision.content.key}</small><span>r{item.current_revision.revision_no}</span></button>) : null}
              {objectKind === "tables" ? tables.map((item) => <button title={item.current_revision.content.description ?? undefined} className={selectedTableId === item.table_id ? "active" : ""} type="button" key={item.table_id} onClick={() => { setSelectedTableId(item.table_id); setCreateMode("none"); }}><strong>{item.current_revision.content.name}</strong><small>{item.current_revision.content.key}</small><span>r{item.current_revision.revision_no}</span></button>) : null}
              {objectKind === "attributes" ? attributes.map((item) => <button title={dataTypes.find((type) => type.value === item.current_revision.content.data_type)?.label} className={selectedAttributeId === item.attribute_definition_id ? "active" : ""} type="button" key={item.attribute_definition_id} onClick={() => { setSelectedAttributeId(item.attribute_definition_id); setCreateMode("none"); }}><strong>{item.current_revision.content.name}</strong><small>{item.current_revision.content.key}</small><span>r{item.current_revision.revision_no}</span></button>) : null}
              {objectKind === "layouts" ? layouts.map((item) => <button title={`${item.items.length} displayed fields`} className={selectedLayoutId === item.layout_id ? "active" : ""} type="button" key={item.layout_id} onClick={() => { setSelectedLayoutId(item.layout_id); setCreateMode("none"); }}><strong>{item.name}</strong><small>{item.layout_id.slice(0, 8)}</small><span>r{item.revision.revision_no}</span></button>) : null}
              {objectKind === "subsets" ? subsets.map((item) => <button title={item.description ?? "Saved starting view"} className={selectedSubsetId === item.subset_id ? "active" : ""} type="button" key={item.subset_id} onClick={() => { setSelectedSubsetId(item.subset_id); setCreateMode("none"); }}><strong>{item.name}</strong><small>{item.subset_id.slice(0, 8)}</small><span>r{item.revision.revision_no}</span></button>) : null}
              {objectKind === "links" ? scopedLinkTypes.map((item) => <button title={`${item.current_revision.content.key} · ${item.current_revision.content.forward_label}`} className={selectedLinkTypeId === item.link_type_id ? "active" : ""} type="button" key={item.link_type_id} onClick={() => { setSelectedLinkTypeId(item.link_type_id); setCreateMode("none"); }}><strong>{item.current_revision.content.name}</strong><small>{item.current_revision.content.source_cardinality} → {item.current_revision.content.target_cardinality}</small><span>r{item.current_revision.revision_no}</span></button>) : null}
              {!loading && !objectRows.length ? <p className="muted">No {objectLabel.toLowerCase()} are available for this selection.</p> : null}
            </div>
          </section>
          <section ref={propertyEditorRef} tabIndex={-1} className="schema-property-editor" aria-label="Object properties">
            {createMode === "database" ? <form className="property-sheet" onSubmit={(event) => void createDatabase(event)}><header><h3>New database</h3><button className="ux-button tertiary" type="button" onClick={() => setCreateMode("none")}>Close</button></header><p>Use a clear name for the material data area that people will browse.</p><div className="property-fields"><label>Display name<input value={databaseName} onChange={(event) => setDatabaseName(event.target.value)} required /></label><label>Reference key<input value={databaseKey} onChange={(event) => setDatabaseKey(event.target.value)} required /></label><label className="wide">Description<textarea value={databaseDescription} onChange={(event) => setDatabaseDescription(event.target.value)} /></label></div><footer><button className="ux-button primary" type="submit" disabled={saving}>Save database</button></footer></form> : null}
            {createMode === "profile" ? <form className="property-sheet" onSubmit={(event) => void createProfile(event)}><header><h3>New profile</h3><button className="ux-button tertiary" type="button" onClick={() => setCreateMode("none")}>Close</button></header><p>Profiles keep related tables together under one database version.</p><div className="property-fields"><label>Display name<input value={profileName} onChange={(event) => setProfileName(event.target.value)} required /></label><label>Reference key<input value={profileKey} onChange={(event) => setProfileKey(event.target.value)} required /></label><label className="wide">Description<textarea value={profileDescription} onChange={(event) => setProfileDescription(event.target.value)} /></label></div><footer><button className="ux-button primary" type="submit" disabled={saving || !databases.length}>Save profile</button></footer></form> : null}
            {createMode === "table" ? <form className="property-sheet" onSubmit={(event) => void createTable(event)}><header><h3>New table</h3><button className="ux-button tertiary" type="button" onClick={() => setCreateMode("none")}>Close</button></header><p>Tables create a stable place for related records. The saved definition is a new revision.</p><div className="property-fields"><label>Display name<input value={tableName} onChange={(event) => setTableName(event.target.value)} required /></label><label>Reference key<input value={tableKey} onChange={(event) => setTableKey(event.target.value)} required /></label><label>Access level<select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}><option value="internal">Internal team</option><option value="confidential">Confidential team</option><option value="restricted">Restricted team</option></select></label><label className="wide">Description<textarea value={tableDescription} onChange={(event) => setTableDescription(event.target.value)} /></label></div><footer><button className="ux-button primary" type="submit" disabled={saving}>Save new Table</button></footer></form> : null}
            {createMode === "attribute" ? <form className="property-sheet" onSubmit={(event) => void createAttribute(event)}><header><h3>New attribute for {selectedTable?.current_revision.content.name}</h3><button className="ux-button tertiary" type="button" onClick={() => setCreateMode("none")}>Close</button></header><p>Only add information that helps someone enter, find or assess a record.</p><div className="property-fields"><label>Display name<input value={attributeName} onChange={(event) => setAttributeName(event.target.value)} required /></label><label>Reference key<input value={attributeKey} onChange={(event) => setAttributeKey(event.target.value)} required /></label><label>Value type<select value={attributeType} onChange={(event) => setAttributeType(event.target.value as ConfigurableAttributeDataType)}>{dataTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label className="checkbox-label"><input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} />Required when creating a record</label><label className="wide">Help for people entering this value<input value={attributeHelpText} onChange={(event) => setAttributeHelpText(event.target.value)} /></label>{attributeType === "number" ? <><label>What the number means<input value={quantitySemantics} onChange={(event) => setQuantitySemantics(event.target.value)} placeholder="for example, density.mass" /></label><label>Standard unit<input value={normalizedUnit} onChange={(event) => setNormalizedUnit(event.target.value)} placeholder="for example, kg/m³" /></label></> : null}{attributeType === "discrete" ? <label className="wide">Allowed choices<input value={allowedValues} onChange={(event) => setAllowedValues(event.target.value)} placeholder="Separate choices with commas" required /></label> : null}{attributeType === "record_reference" ? <label>Related table<select value={referenceTableId} onChange={(event) => setReferenceTableId(event.target.value)} required><option value="">Choose a table</option>{tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}</select></label> : null}</div><footer><button className="ux-button primary" type="submit" disabled={saving}>Save new Attribute</button></footer></form> : null}
            {createMode === "link" ? <form className="property-sheet" onSubmit={(event) => void createLinkType(event)}><header><h3>New Link Type</h3><button className="ux-button tertiary" type="button" onClick={() => setCreateMode("none")}>Close</button></header><p>Describe the relationship people see between two record types. Both endpoints are saved against their current revisions.</p><div className="property-fields"><label>Display name<input value={linkName} onChange={(event) => setLinkName(event.target.value)} required /></label><label>Reference key<input value={linkKey} onChange={(event) => setLinkKey(event.target.value)} required /></label><label>From table<select value={sourceTableId} onChange={(event) => setSourceTableId(event.target.value)}>{tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}</select></label><label>To table<select value={targetTableId} onChange={(event) => setTargetTableId(event.target.value)}>{tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}</select></label><label>Forward wording<input value={forwardLabel} onChange={(event) => setForwardLabel(event.target.value)} required /></label><label>Reverse wording<input value={reverseLabel} onChange={(event) => setReverseLabel(event.target.value)} required /></label><label>From each record<select value={sourceCardinality} onChange={(event) => setSourceCardinality(event.target.value as ConfigurableLinkCardinality)}><option value="one">links to one</option><option value="many">links to many</option></select></label><label>To each record<select value={targetCardinality} onChange={(event) => setTargetCardinality(event.target.value as ConfigurableLinkCardinality)}><option value="one">is linked from one</option><option value="many">is linked from many</option></select></label></div><footer><button className="ux-button primary" type="submit" disabled={saving || !tables.length}>Save new Link Type</button></footer></form> : null}
            {createMode === "none" && objectKind === "databases" && selectedDatabase ? <form key={selectedDatabase.current_revision.id} className="property-sheet" onSubmit={(event) => void reviseDatabase(event, selectedDatabase)}><header><h3>{selectedDatabase.current_revision.content.name}</h3><span>{selectedDatabase.current_revision.lifecycle_state}</span></header><div className="property-fields"><label>Display name<input name="name" defaultValue={selectedDatabase.current_revision.content.name} required /></label><label className="wide">Description<textarea name="description" defaultValue={selectedDatabase.current_revision.content.description ?? ""} /></label></div><footer><button className="ux-button" type="button" disabled={saving} onClick={() => void checkOrPublish("catalog.database", selectedDatabase.database_id, selectedDatabase.current_revision.id, false)}>Check</button><button className="ux-button" type="submit" disabled={saving}>Save draft</button><button className="ux-button primary" type="button" disabled title="Publication is not configured in Database design. The draft remains unchanged.">Publish — Not configured</button></footer></form> : null}
            {createMode === "none" && objectKind === "profiles" && selectedProfile ? <form key={selectedProfile.current_revision.id} className="property-sheet" onSubmit={(event) => void reviseProfile(event, selectedProfile)}><header><h3>{selectedProfile.current_revision.content.name}</h3><span>{selectedProfile.current_revision.lifecycle_state}</span></header><div className="property-fields"><label>Display name<input name="name" defaultValue={selectedProfile.current_revision.content.name} required /></label><label className="wide">Description<textarea name="description" defaultValue={selectedProfile.current_revision.content.description ?? ""} /></label></div><footer><button className="ux-button" type="button" disabled={saving} onClick={() => void checkOrPublish("catalog.profile", selectedProfile.profile_id, selectedProfile.current_revision.id, false)}>Check</button><button className="ux-button" type="submit" disabled={saving}>Save draft</button><button className="ux-button primary" type="button" disabled title="Publication is not configured in Database design. The draft remains unchanged.">Publish — Not configured</button></footer></form> : null}
            {createMode === "none" && objectKind === "tables" && selectedTable ? <form key={selectedTable.current_revision.id} className="property-sheet" onSubmit={(event) => void reviseTable(event, selectedTable)}><header><h3>{selectedTable.current_revision.content.name}</h3><span>{selectedTable.current_revision.lifecycle_state}</span></header><div className="property-fields"><label>Display name<input name="name" defaultValue={selectedTable.current_revision.content.name} required /></label><label className="wide">Description<textarea name="description" defaultValue={selectedTable.current_revision.content.description ?? ""} /></label></div><dl><div><dt>Fields</dt><dd>{attributes.length}</dd></div><div><dt>Datasheet layouts</dt><dd>{layouts.length}</dd></div><div><dt>Saved views</dt><dd>{subsets.length}</dd></div></dl><footer><button className="ux-button" type="button" disabled={saving} onClick={() => void checkOrPublish("catalog.configurable_table", selectedTable.table_id, selectedTable.current_revision.id, false)}>Check</button><button className="ux-button" type="submit" disabled={saving}>Save draft</button><button className="ux-button primary" type="button" disabled title="Publication is not configured in Database design. The draft remains unchanged.">Publish — Not configured</button></footer></form> : null}
            {createMode === "none" && objectKind === "attributes" ? (selectedAttribute ? <form key={selectedAttribute.current_revision.id} className="property-sheet" onSubmit={(event) => void reviseAttribute(event, selectedAttribute)}><header><h3>{selectedAttribute.current_revision.content.name}</h3><span>{selectedAttribute.current_revision.lifecycle_state}</span></header><div className="property-fields"><label>Display name<input name="name" defaultValue={selectedAttribute.current_revision.content.name} required /></label><label>Value type<input value={dataTypes.find((type) => type.value === selectedAttribute.current_revision.content.data_type)?.label} readOnly /></label><label className="checkbox-label"><input name="required" type="checkbox" defaultChecked={selectedAttribute.current_revision.content.required} />Required when creating a record</label><label className="wide">Entry guidance<input name="help_text" defaultValue={selectedAttribute.current_revision.content.help_text ?? ""} /></label>{selectedAttribute.current_revision.content.data_type === "number" ? <><label>Quantity meaning<input name="quantity" defaultValue={selectedAttribute.current_revision.content.quantity_semantics ?? ""} required /></label><label>Standard unit<input name="unit" defaultValue={selectedAttribute.current_revision.content.normalized_unit ?? ""} required /></label></> : null}</div><footer><button className="ux-button" type="button" disabled={saving} onClick={() => void checkOrPublish("catalog.attribute_definition", selectedAttribute.attribute_definition_id, selectedAttribute.current_revision.id, false)}>Check</button><button className="ux-button" type="submit" disabled={saving}>Save draft</button><button className="ux-button primary" type="button" disabled title="Publication is not configured in Database design. The draft remains unchanged.">Publish — Not configured</button></footer></form> : <div className="property-sheet empty"><h3>Select an Attribute</h3><p>Its entry rules appear here.</p></div>) : null}
            {createMode === "none" && objectKind === "layouts" ? (selectedLayout ? <form key={selectedLayout.revision.id} className="property-sheet" onSubmit={(event) => void reviseLayout(event, selectedLayout)}><header><h3>{selectedLayout.name}</h3><span>{selectedLayout.revision.lifecycle_state}</span></header><div className="property-fields"><label>Layout name<input name="name" defaultValue={selectedLayout.name} required /></label><label className="wide">Description<textarea name="description" defaultValue={selectedLayout.description ?? ""} /></label></div><fieldset className="layout-field-picker"><legend>Fields shown on the datasheet</legend>{attributes.map((attribute) => <label key={attribute.attribute_definition_id}><input name="layout_attribute" type="checkbox" value={attribute.attribute_definition_id} defaultChecked={selectedLayout.items.some((item) => item.attribute_definition_id === attribute.attribute_definition_id)} /><span>{attribute.current_revision.content.name}</span><small>{dataTypes.find((type) => type.value === attribute.current_revision.content.data_type)?.label}{attribute.current_revision.content.normalized_unit ? ` · ${attribute.current_revision.content.normalized_unit}` : ""}</small></label>)}</fieldset><footer><button className="ux-button" type="button" disabled={saving} onClick={() => void checkOrPublish("catalog.layout", selectedLayout.layout_id, selectedLayout.revision.id, false)}>Check</button><button className="ux-button" type="submit" disabled={saving}>Save draft</button><button className="ux-button primary" type="button" disabled title="Publication is not configured in Database design. The draft remains unchanged.">Publish — Not configured</button></footer></form> : <div className="property-sheet empty"><h3>Select a layout</h3><p>Choose the fields people should see on a datasheet.</p></div>) : null}
            {createMode === "none" && objectKind === "subsets" ? (selectedSubset ? <form key={selectedSubset.revision.id} className="property-sheet" onSubmit={(event) => void reviseSubset(event, selectedSubset)}><header><h3>{selectedSubset.name}</h3><span>{selectedSubset.revision.lifecycle_state}</span></header><div className="property-fields"><label>Saved view name<input name="name" defaultValue={selectedSubset.name} required /></label><label className="wide">Description<textarea name="description" defaultValue={selectedSubset.description ?? ""} /></label><label className="wide">Starting filters<textarea name="filter" defaultValue={JSON.stringify(selectedSubset.filter_definition ?? {}, null, 2)} /></label></div><footer><button className="ux-button" type="button" disabled={saving} onClick={() => void checkOrPublish("catalog.subset", selectedSubset.subset_id, selectedSubset.revision.id, false)}>Check</button><button className="ux-button" type="submit" disabled={saving}>Save draft</button><button className="ux-button primary" type="button" disabled title="Publication is not configured in Database design. The draft remains unchanged.">Publish — Not configured</button></footer></form> : <div className="property-sheet empty"><h3>Select a saved view</h3><p>Its starting filters appear here.</p></div>) : null}
            {createMode === "none" && objectKind === "links" ? (selectedLinkType ? <form key={selectedLinkType.current_revision.id} className="property-sheet" onSubmit={(event) => void reviseLinkType(event, selectedLinkType)}><header><h3>{selectedLinkType.current_revision.content.name}</h3><span>{selectedLinkType.current_revision.lifecycle_state}</span></header><div className="property-fields"><label>Display name<input name="name" defaultValue={selectedLinkType.current_revision.content.name} required /></label><label>Forward wording<input name="forward" defaultValue={selectedLinkType.current_revision.content.forward_label} required /></label><label>Reverse wording<input name="reverse" defaultValue={selectedLinkType.current_revision.content.reverse_label} required /></label><label>From each record<select name="source_cardinality" defaultValue={selectedLinkType.current_revision.content.source_cardinality}><option value="one">links to one</option><option value="many">links to many</option></select></label><label>To each record<select name="target_cardinality" defaultValue={selectedLinkType.current_revision.content.target_cardinality}><option value="one">is linked from one</option><option value="many">is linked from many</option></select></label></div><footer><button className="ux-button" type="button" disabled={saving} onClick={() => void checkOrPublish("catalog.link_type", selectedLinkType.link_type_id, selectedLinkType.current_revision.id, false)}>Check</button><button className="ux-button" type="submit" disabled={saving}>Save draft</button><button className="ux-button primary" type="button" disabled title="Publication is not configured in Database design. The draft remains unchanged.">Publish — Not configured</button></footer></form> : <div className="property-sheet empty"><h3>Select a Link Type</h3><p>Its direction and relationship rules appear here.</p></div>) : null}
            {createMode === "none" && objectKind === "links" && selectedLinkType ? <dl className="schema-link-endpoints"><div><dt>Source Table revision</dt><dd>{selectedLinkSourceTable?.current_revision.id === selectedLinkType.current_revision.content.source_table_revision_id ? `${selectedLinkSourceTable.current_revision.content.name} · r${selectedLinkSourceTable.current_revision.revision_no}` : `Pinned revision ${selectedLinkType.current_revision.content.source_table_revision_id.slice(0, 8)}`}</dd></div><div><dt>Target Table revision</dt><dd>{selectedLinkTargetTable?.current_revision.id === selectedLinkType.current_revision.content.target_table_revision_id ? `${selectedLinkTargetTable.current_revision.content.name} · r${selectedLinkTargetTable.current_revision.revision_no}` : `Pinned revision ${selectedLinkType.current_revision.content.target_table_revision_id.slice(0, 8)}`}</dd></div></dl> : null}
          </section>
          {previewOpen ? <RecordPreview record={previewRecords[0] ?? null} layout={selectedLayout} attributes={attributes} attributeRevisions={attributeRevisions} onClose={() => setPreviewOpen(false)} /> : null}
        </div>
        <dialog ref={deleteDialogRef} className="schema-delete-dialog" onCancel={() => setDeleteTarget(null)} aria-labelledby="schema-delete-title">
          <form method="dialog" onSubmit={(event) => event.preventDefault()}>
            <header><h3 id="schema-delete-title">Delete unpublished draft?</h3></header>
            <p><strong>{deleteTarget?.label}</strong> will be permanently deleted.</p>
            <p>Deletion succeeds only for revision 1 with no publication history, Records, Links, references or dependencies. If the server finds any use, this draft and your current selection remain unchanged.</p>
            <footer>
              <button className="ux-button" type="button" onClick={() => setDeleteTarget(null)}>Cancel</button>
              <button className="ux-button danger" type="button" disabled={saving} onClick={() => void confirmDraftDelete()}>Delete draft permanently</button>
            </footer>
          </form>
        </dialog>
      </section>
    );
  }

  return (
    <div className="catalog-schema-workbench">
      {!productMode ? <section className="hero-card compact-hero">
        <p className="eyebrow">Material data administration</p>
        <h1>Catalog schema designer</h1>
        <p>
          Add governed record types and typed attributes without a database migration. Published
          definitions remain immutable revisions.
        </p>
        {onNavigate ? (
          <div className="hero-actions">
            <button
              className="ux-button"
              type="button"
              onClick={() => onNavigate("/catalog/explorer")}
            >
              Open Explorer
            </button>
            <button
              className="ux-button"
              type="button"
              onClick={() => onNavigate("/catalog/records")}
            >
              Open Catalog records
            </button>
          </div>
        ) : null}
      </section> : <header className="workspace-section-heading"><h2>Tables, Attributes and relationships</h2>{onNavigate ? <button className="ux-button" type="button" onClick={() => onNavigate("/materials")}>Preview Materials</button> : null}</header>}

      {error ? <div className="error-banner">{error}</div> : null}
      {notice ? <div className="success-banner">{notice}</div> : null}

      <div className="detail-grid">
        <section className="content-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Table definitions</p>
              <h2>{tables.length} configurable Tables</h2>
            </div>
            <button className="ux-button tertiary" type="button" onClick={() => void loadTables()}>
              Refresh
            </button>
          </div>
          {loading && !tables.length ? <p className="muted">Loading schema…</p> : null}
          <div className="schema-table-list">
            {tables.map((table) => (
              <button
                className={table.table_id === selectedTableId ? "schema-table-row active" : "schema-table-row"}
                type="button"
                key={table.table_id}
                onClick={() => setSelectedTableId(table.table_id)}
              >
                <strong>{table.current_revision.content.name}</strong>
                <span>{table.current_revision.content.key}</span>
                <small>r{table.current_revision.revision_no}</small>
              </button>
            ))}
            {!tables.length ? <p className="muted">Create the first record Table.</p> : null}
          </div>

          <form className="form-stack" onSubmit={(event) => void createTable(event)}>
            <h3>Create Table</h3>
            <div className="form-grid">
              <label>
                Stable key
                <input value={tableKey} onChange={(event) => setTableKey(event.target.value)} required />
              </label>
              <label>
                Display name
                <input value={tableName} onChange={(event) => setTableName(event.target.value)} required />
              </label>
              <label>
                Classification
                <select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}>
                  <option value="internal">Internal</option>
                  <option value="confidential">Confidential</option>
                  <option value="restricted">Restricted</option>
                </select>
              </label>
            </div>
            <label>
              Description
              <textarea value={tableDescription} onChange={(event) => setTableDescription(event.target.value)} />
            </label>
            <button className="ux-button primary" type="submit" disabled={saving}>
              Create Table revision 1
            </button>
          </form>
        </section>

        <section className="content-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Typed definitions</p>
              <h2>{selectedTable?.current_revision.content.name ?? "Select a Table"}</h2>
            </div>
          </div>
          {selectedTable ? (
            <>
              <div className="schema-metrics">
                <span><strong>{attributes.length}</strong> Attributes</span>
                <span><strong>{layouts.length}</strong> Layouts</span>
                <span><strong>{subsets.length}</strong> Subsets</span>
              </div>
              <div className="attribute-list">
                {attributes.map((attribute) => (
                  <article key={attribute.attribute_definition_id} className="attribute-card">
                    <div>
                      <strong>{attribute.current_revision.content.name}</strong>
                      <small>{attribute.current_revision.content.key}</small>
                    </div>
                    <span className="status-badge neutral">{attribute.current_revision.content.data_type}</span>
                    <p>
                      {attribute.current_revision.content.quantity_semantics ?? "No quantity semantic"}
                      {attribute.current_revision.content.normalized_unit
                        ? ` · ${attribute.current_revision.content.normalized_unit}`
                        : ""}
                    </p>
                  </article>
                ))}
              </div>

              <form className="form-stack" onSubmit={(event) => void createAttribute(event)}>
                <h3>Add Attribute</h3>
                <div className="form-grid">
                  <label>
                    Stable key
                    <input value={attributeKey} onChange={(event) => setAttributeKey(event.target.value)} required />
                  </label>
                  <label>
                    Display name
                    <input value={attributeName} onChange={(event) => setAttributeName(event.target.value)} required />
                  </label>
                  <label className="attribute-description-field">
                    Description
                    <input value={attributeHelpText} onChange={(event) => setAttributeHelpText(event.target.value)} placeholder="How this value should be interpreted" />
                  </label>
                  <label>
                    Data type
                    <select value={attributeType} onChange={(event) => setAttributeType(event.target.value as ConfigurableAttributeDataType)}>
                      {dataTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} />
                    Required value
                  </label>
                  {attributeType === "number" ? (
                    <>
                      <label>
                        Quantity semantic
                        <input value={quantitySemantics} onChange={(event) => setQuantitySemantics(event.target.value)} placeholder="density.mass" />
                      </label>
                      <label>
                        Normalized unit
                        <input value={normalizedUnit} onChange={(event) => setNormalizedUnit(event.target.value)} placeholder="kg/m3" />
                      </label>
                    </>
                  ) : null}
                  {attributeType === "discrete" ? (
                    <label>
                      Allowed values (comma separated)
                      <input value={allowedValues} onChange={(event) => setAllowedValues(event.target.value)} required />
                    </label>
                  ) : null}
                  {attributeType === "record_reference" ? (
                    <label>
                      Target Table
                      <select value={referenceTableId} onChange={(event) => setReferenceTableId(event.target.value)} required>
                        <option value="">Select target…</option>
                        {tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}
                      </select>
                    </label>
                  ) : null}
                </div>
                <button className="ux-button primary" type="submit" disabled={saving}>
                  Add Attribute revision 1
                </button>
              </form>

              <div className="schema-actions">
                <button className="ux-button" type="button" disabled={saving || !attributes.length} onClick={() => void createDefaultLayout()}>
                  Create datasheet Layout
                </button>
                <button className="ux-button" type="button" disabled={saving} onClick={() => void createAllRecordsSubset()}>
                  Create All records Subset
                </button>
              </div>
            </>
          ) : (
            <p className="muted">Select or create a Table before adding Attribute Definitions.</p>
          )}
        </section>
      </div>
      <section className="content-card link-type-administration">
        <div className="section-heading"><div><p className="eyebrow">Record relationships</p><h2>Link Types</h2><p>Define how records may be connected. Every created link pins exact source and target revisions.</p></div><span className="revision-chip">{linkTypes.length}</span></div>
        <div className="link-type-admin-grid">
          <div className="attribute-list">
            {linkTypes.map((linkType) => <article className="attribute-card" key={linkType.link_type_id}><div><strong>{linkType.current_revision.content.name}</strong><small>{linkType.current_revision.content.key} · r{linkType.current_revision.revision_no}</small></div><span className="status-badge neutral">{linkType.current_revision.content.source_cardinality}:{linkType.current_revision.content.target_cardinality}</span><p>{linkType.current_revision.content.forward_label} / {linkType.current_revision.content.reverse_label}</p></article>)}
            {!linkTypes.length ? <p className="muted">No Link Types are defined yet.</p> : null}
          </div>
          <form className="form-stack" onSubmit={(event) => void createLinkType(event)}>
            <h3>Create Link Type</h3>
            <div className="form-grid">
              <label>Stable key<input value={linkKey} onChange={(event) => setLinkKey(event.target.value)} required /></label>
              <label>Display name<input value={linkName} onChange={(event) => setLinkName(event.target.value)} required /></label>
              <label>From Table<select value={sourceTableId} onChange={(event) => setSourceTableId(event.target.value)} required>{tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}</select></label>
              <label>To Table<select value={targetTableId} onChange={(event) => setTargetTableId(event.target.value)} required>{tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}</select></label>
              <label>Forward label<input value={forwardLabel} onChange={(event) => setForwardLabel(event.target.value)} required /></label>
              <label>Reverse label<input value={reverseLabel} onChange={(event) => setReverseLabel(event.target.value)} required /></label>
              <label>From cardinality<select value={sourceCardinality} onChange={(event) => setSourceCardinality(event.target.value as ConfigurableLinkCardinality)}><option value="one">One</option><option value="many">Many</option></select></label>
              <label>To cardinality<select value={targetCardinality} onChange={(event) => setTargetCardinality(event.target.value as ConfigurableLinkCardinality)}><option value="one">One</option><option value="many">Many</option></select></label>
            </div>
            <button className="ux-button primary" type="submit" disabled={saving || !tables.length}>Create Link Type revision 1</button>
          </form>
        </div>
      </section>
    </div>
  );
}
