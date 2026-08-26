import { describe, expect, it } from "vitest";

import {
  databaseRoutePath,
  definitionBundleRoutePath,
  parseDatabaseRouteSelection,
  parseDefinitionBundleRouteSelection,
  parseRecordsRouteSelection,
  recordsRoutePath,
} from "./administration-route-state";

describe("Administration route state", () => {
  it("preserves explicit stable selections without inventing defaults", () => {
    expect(parseDatabaseRouteSelection("")).toEqual({
      databaseId: "",
      databaseRevisionId: "",
      profileId: "",
      profileRevisionId: "",
      tableId: "",
      tableRevisionId: "",
      objectKind: "tables",
      objectId: "",
      objectRevisionId: "",
      recordId: "",
      recordRevisionId: "",
    });
    expect(
      databaseRoutePath({
        databaseId: "db-1",
        databaseRevisionId: "db-revision-1",
        profileId: "profile-1",
        profileRevisionId: "profile-revision-1",
        tableId: "table-1",
        tableRevisionId: "table-revision-1",
        objectKind: "attributes",
        objectId: "attribute-1",
        objectRevisionId: "attribute-revision-1",
        recordId: "record-1",
        recordRevisionId: "record-revision-2",
      }),
    ).toBe(
      "/administration/database?database_id=db-1&database_revision_id=db-revision-1&profile_id=profile-1&profile_revision_id=profile-revision-1&table_id=table-1&table_revision_id=table-revision-1&object_kind=attributes&object_id=attribute-1&object_revision_id=attribute-revision-1&record_id=record-1&record_revision_id=record-revision-2",
    );
  });

  it("canonicalizes the legacy revision_id name without changing its exact value", () => {
    expect(parseRecordsRouteSelection("?table_id=table-1&record_id=record-1&revision_id=revision-3")).toEqual({
      tableId: "table-1",
      tableRevisionId: "",
      folderId: "",
      folderRevisionId: "",
      recordId: "record-1",
      recordRevisionId: "revision-3",
    });
    expect(
      recordsRoutePath({ tableId: "table-1", recordId: "record-1", recordRevisionId: "revision-3" }),
    ).toBe(
      "/administration/records?table_id=table-1&record_id=record-1&record_revision_id=revision-3",
    );
  });

  it("round-trips the exact format-definition application identity", () => {
    expect(parseDefinitionBundleRouteSelection("?application_id=application-7")).toEqual({
      applicationId: "application-7",
    });
    expect(definitionBundleRoutePath({ applicationId: "application-7" })).toBe(
      "/administration/schema-bundles?application_id=application-7",
    );
  });
});
