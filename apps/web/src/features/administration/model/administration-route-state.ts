export type AdministrationObjectKind =
  | "databases"
  | "profiles"
  | "tables"
  | "attributes"
  | "layouts"
  | "subsets"
  | "links";

const objectKinds = new Set<AdministrationObjectKind>([
  "databases",
  "profiles",
  "tables",
  "attributes",
  "layouts",
  "subsets",
  "links",
]);

function value(parameters: URLSearchParams, key: string): string {
  return parameters.get(key)?.trim() ?? "";
}

export interface DatabaseRouteSelection {
  databaseId: string;
  databaseRevisionId: string;
  profileId: string;
  profileRevisionId: string;
  tableId: string;
  tableRevisionId: string;
  objectKind: AdministrationObjectKind;
  objectId: string;
  objectRevisionId: string;
  recordId: string;
  recordRevisionId: string;
}

export function parseDatabaseRouteSelection(search: string): DatabaseRouteSelection {
  const parameters = new URLSearchParams(search);
  const requestedKind = value(parameters, "object_kind") as AdministrationObjectKind;
  return {
    databaseId: value(parameters, "database_id"),
    databaseRevisionId: value(parameters, "database_revision_id"),
    profileId: value(parameters, "profile_id"),
    profileRevisionId: value(parameters, "profile_revision_id"),
    tableId: value(parameters, "table_id"),
    tableRevisionId: value(parameters, "table_revision_id"),
    objectKind: objectKinds.has(requestedKind) ? requestedKind : "tables",
    objectId: value(parameters, "object_id"),
    objectRevisionId: value(parameters, "object_revision_id"),
    recordId: value(parameters, "record_id"),
    recordRevisionId: value(parameters, "record_revision_id"),
  };
}

export interface RecordsRouteSelection {
  tableId: string;
  tableRevisionId?: string;
  folderId?: string;
  folderRevisionId?: string;
  recordId: string;
  recordRevisionId: string;
}

export function parseRecordsRouteSelection(search: string): RecordsRouteSelection {
  const parameters = new URLSearchParams(search);
  return {
    tableId: value(parameters, "table_id"),
    tableRevisionId: value(parameters, "table_revision_id"),
    folderId: value(parameters, "folder_id"),
    folderRevisionId: value(parameters, "folder_revision_id"),
    recordId: value(parameters, "record_id"),
    recordRevisionId:
      value(parameters, "record_revision_id") || value(parameters, "revision_id"),
  };
}

function withParameters(path: string, entries: Record<string, string>): string {
  const parameters = new URLSearchParams();
  for (const [key, entry] of Object.entries(entries)) {
    if (entry) parameters.set(key, entry);
  }
  const query = parameters.toString();
  return query ? `${path}?${query}` : path;
}

export function databaseRoutePath(selection: DatabaseRouteSelection): string {
  return withParameters("/administration/database", {
    database_id: selection.databaseId,
    database_revision_id: selection.databaseRevisionId,
    profile_id: selection.profileId,
    profile_revision_id: selection.profileRevisionId,
    table_id: selection.tableId,
    table_revision_id: selection.tableRevisionId,
    object_kind: selection.objectKind,
    object_id: selection.objectId,
    object_revision_id: selection.objectRevisionId,
    record_id: selection.recordId,
    record_revision_id: selection.recordRevisionId,
  });
}

export function recordsRoutePath(selection: RecordsRouteSelection): string {
  return withParameters("/administration/records", {
    table_id: selection.tableId,
    table_revision_id: selection.tableRevisionId ?? "",
    folder_id: selection.folderId ?? "",
    folder_revision_id: selection.folderRevisionId ?? "",
    record_id: selection.recordId,
    record_revision_id: selection.recordRevisionId,
  });
}

export interface DefinitionBundleRouteSelection {
  applicationId: string;
}

export function parseDefinitionBundleRouteSelection(search: string): DefinitionBundleRouteSelection {
  return {
    applicationId: value(new URLSearchParams(search), "application_id"),
  };
}

export function definitionBundleRoutePath(selection: DefinitionBundleRouteSelection): string {
  return withParameters("/administration/schema-bundles", {
    application_id: selection.applicationId,
  });
}
