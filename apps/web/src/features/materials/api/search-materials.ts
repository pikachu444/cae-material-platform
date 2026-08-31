import {
  ApiError,
  type ApiConfig,
  type ApiResult,
} from "../../../shared/api";
import {
  listCatalogExplorerTables,
  listConfigurableCatalogAttributes,
  searchConfigurableCatalogRecords,
} from "../../catalog";
import {
  type MaterialSearchRequest,
  type MaterialSearchResponse,
} from "./materials-api";
import type {
  ConfigurableAttributeResponse,
  ConfigurableCatalogRecordResponse,
} from "../../catalog/contracts";

/** Resolve the published Materials projection without depending on Browse UI effects. */
export async function findDefaultMaterialsTableId(
  config: ApiConfig,
): Promise<string | null> {
  const result = await listCatalogExplorerTables(config);
  return (
    result.data.items.find(
      (table) => table.current_revision.content.key === "technical_data",
    )?.table_id ??
    // Keep the legacy fixture as a compatibility fallback for old disposable
    // workspaces.  A source-v2 workspace always selects technical_data above.
    result.data.items.find(
      (table) => table.current_revision.content.key === "demo_material_records",
    )?.table_id ?? null
  );
}

/**
 * A catalog-backed search result keeps the Catalog record revision and the bound
 * Material revision as separate identities.
 */
export interface MaterialSearchRow {
  material_id: string;
  material_revision_id: string;
  table_id: string;
  record_id: string;
  record_revision_id: string;
  record_revision_no: number;
  name: string;
  material_code: string | null;
  description: string | null;
  material_family: string | null;
  material_class: string;
  lifecycle_state: string;
}

export interface MaterialCatalogSearchResponse {
  items: MaterialSearchRow[];
  total_count: number;
  offset: number;
  limit: number;
  facets: MaterialSearchResponse["facets"];
}

function sourceFamilyForMaterialClass(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "polymer") return "Plastic";
  if (normalized === "elastomer") return "Rubber";
  if (normalized === "metal") return "Metal";
  return value;
}

function materialClassForSourceFamily(value: string | null): string {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "plastic") return "polymer";
  if (normalized === "rubber") return "elastomer";
  if (normalized === "metal") return "metal";
  return value ?? "unclassified";
}

/** Query the Materials projection for the exact scope selected in Browse. */
export async function searchMaterialCatalogRecords(
  config: ApiConfig,
  input: MaterialSearchRequest,
): Promise<ApiResult<MaterialCatalogSearchResponse>> {
  if (!input.tableId) {
    throw new ApiError(
      400,
      "Choose a table in Browse before searching materials.",
    );
  }
  const attributesResult = await listConfigurableCatalogAttributes(
    config,
    input.tableId,
  );
  const attributes = attributesResult.data.items;
  const attributeByKey = new Map(
    attributes.map((attribute) => [
      attribute.current_revision.content.key,
      attribute,
    ]),
  );
  // Source-v2 owns the Materials class projection.  Category and manufacturer
  // are source fields, not Evidence/Provider facets.
  const classAttribute =
    attributeByKey.get("material_information__family") ??
    attributeByKey.get("material_class");
  const sourceV2ClassAttribute = attributeByKey.get(
    "material_information__family",
  );
  const providerAttribute = attributeByKey.get("provider");
  const evidenceSourceAttribute = attributeByKey.get("evidence_source");

  if (input.provider || input.evidenceSource) {
    if (sourceV2ClassAttribute || !providerAttribute || !evidenceSourceAttribute) {
      throw new ApiError(
        400,
        "Unsupported legacy provider/source filters. Clear unsupported filters to continue.",
      );
    }
  }

  const sortBy =
    input.sortBy === "material_class" && classAttribute ? "attribute" : "name";
  const result = await searchConfigurableCatalogRecords(config, {
    table_id: input.tableId,
    text: input.query?.trim() || null,
    folder_id: input.folderId ?? null,
    record_id: input.recordId ?? null,
    discrete_filters: [
      input.materialClass && classAttribute
        ? {
            attribute_definition_id: classAttribute.attribute_definition_id,
            values: [
              sourceV2ClassAttribute
                ? sourceFamilyForMaterialClass(input.materialClass)
                : input.materialClass,
            ],
          }
        : null,
      input.provider && providerAttribute
        ? {
            attribute_definition_id: providerAttribute.attribute_definition_id,
            values: [input.provider],
          }
        : null,
      input.evidenceSource && evidenceSourceAttribute
        ? {
            attribute_definition_id:
              evidenceSourceAttribute.attribute_definition_id,
            values: [input.evidenceSource],
          }
        : null,
    ].filter(
      (value): value is { attribute_definition_id: string; values: string[] } =>
        value !== null,
    ),
    number_filters: [],
    facet_attribute_ids: [
      classAttribute,
      providerAttribute,
      evidenceSourceAttribute,
    ].flatMap((attribute) =>
      attribute ? [attribute.attribute_definition_id] : [],
    ),
    offset: input.offset ?? 0,
    limit: input.limit ?? 50,
    domain_binding_kind: "material",
    include_descendants: input.includeDescendants ?? Boolean(input.folderId),
    sort_by: sortBy,
    sort_attribute_id:
      sortBy === "attribute"
        ? classAttribute?.attribute_definition_id
        : undefined,
    sort_direction: input.sortDirection ?? "ascending",
    // Materials is a published exact-revision surface.  Administration retains
    // the separate draft-capable Catalog search contract.
    published_only: true,
  });

  function valueFor(
    record: ConfigurableCatalogRecordResponse,
    key: string,
  ): string | null {
    const definition = attributeByKey.get(key);
    if (!definition) return null;
    const value = record.current_revision.content.values.find(
      (candidate) =>
        candidate.attribute_definition_id ===
        definition.attribute_definition_id,
    );
    if (!value) return null;
    if (value.data_type === "number") return value.original_value;
    if ("value" in value) return String(value.value);
    return null;
  }

  function rowFromRecord(
    record: ConfigurableCatalogRecordResponse,
  ): MaterialSearchRow | null {
    const binding = record.domain_binding;
    if (!binding || binding.kind !== "material") return null;
    const content = record.current_revision.content;
    return {
      material_id: binding.object_id,
      material_revision_id: binding.revision_id,
      table_id: record.table_id,
      record_id: record.record_id,
      record_revision_id: record.current_revision.id,
      record_revision_no: record.current_revision.revision_no,
      name: content.name,
      material_code: content.external_key,
      description: content.description,
      material_family:
        valueFor(record, "material_information__family") ??
        valueFor(record, "material_family") ??
        valueFor(record, "grade"),
      material_class: sourceV2ClassAttribute
        ? materialClassForSourceFamily(
            valueFor(record, "material_information__family"),
          )
        : valueFor(record, "material_class") ?? "unclassified",
      lifecycle_state: record.current_revision.lifecycle_state,
    };
  }

  const items = result.data.items.flatMap((record) => {
    const row = rowFromRecord(record);
    return row ? [row] : [];
  });
  const facetValues = (attribute: ConfigurableAttributeResponse | undefined) =>
    result.data.facets
      .filter(
        (facet) =>
          attribute?.attribute_definition_id === facet.attribute_definition_id,
      )
      .map((facet) => ({ value: facet.value, count: facet.count }));
  return {
    ...result,
    data: {
      items,
      total_count: result.data.total_count,
      offset: result.data.offset,
      limit: result.data.limit,
      facets: {
        material_classes: facetValues(classAttribute).map(
          ({ value, count }) => ({
            material_class: sourceV2ClassAttribute
              ? materialClassForSourceFamily(value)
              : value,
            count,
          }),
        ),
        providers: facetValues(providerAttribute).map(({ value, count }) => ({
          provider: value,
          count,
        })),
        evidence_sources: facetValues(evidenceSourceAttribute).map(
          ({ value, count }) => ({ evidence_source: value, count }),
        ),
      },
    },
  };
}
