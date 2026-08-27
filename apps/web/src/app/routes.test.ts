import { describe, expect, it } from "vitest";
import { parseAppRoute, type AppRoute } from "./routes";

interface RouteCase {
  location: string;
  expected: Partial<AppRoute>;
}

const routeCases: RouteCase[] = [
  { location: "/", expected: { id: "root-redirect", to: "/materials" } },
  {
    location: "/materials?q=DP780&selected=material-1",
    expected: {
      id: "material-search",
      pathname: "/materials",
      search: "?q=DP780&selected=material-1",
    },
  },
  { location: "/materials/new", expected: { id: "material-create" } },
  {
    location: "/materials/material-1",
    expected: {
      id: "material-detail",
      materialId: "material-1",
      tab: "overview",
      source: "canonical",
    },
  },
  {
    location:
      "/materials/material-1/cards?record_id=record-1&record_revision_id=record-r3&material_revision_id=material-r7",
    expected: {
      id: "material-detail",
      materialId: "material-1",
      tab: "cards",
      exactPin: {
        recordId: "record-1",
        recordRevisionId: "record-r3",
        materialRevisionId: "material-r7",
      },
    },
  },
  {
    location: "/materials/material-1/testing",
    expected: {
      id: "material-detail",
      materialId: "material-1",
      tab: "curves",
      source: "legacy-area",
    },
  },
  {
    location: "/materials/material-1/datasets",
    expected: { id: "material-detail", tab: "curves", source: "legacy-area" },
  },
  {
    location: "/materials/material-1/models",
    expected: { id: "material-detail", tab: "cards", source: "legacy-area" },
  },
  {
    location: "/materials/material-1/governance",
    expected: { id: "material-detail", tab: "evidence", source: "legacy-area" },
  },
  {
    location:
      "/materials/material-1/cards/card-2?record_id=record-1&record_revision_id=record-r3&material_revision_id=material-r7",
    expected: {
      id: "material-card",
      materialId: "material-1",
      cardId: "card-2",
      exactPin: {
        recordId: "record-1",
        recordRevisionId: "record-r3",
        materialRevisionId: "material-r7",
      },
    },
  },
  {
    location: "/materials/records/record-1/revisions/record-r3",
    expected: {
      id: "material-record",
      recordId: "record-1",
      revisionId: "record-r3",
    },
  },
  {
    location: "/catalog/explorer",
    expected: { id: "catalog-explorer", recordId: undefined, revisionId: undefined },
  },
  {
    location: "/catalog/explorer/records/record-1/revisions/record-r3",
    expected: {
      id: "catalog-explorer",
      recordId: "record-1",
      revisionId: "record-r3",
    },
  },
  {
    location: "/models/material-models/model-1/revisions/model-r4",
    expected: {
      id: "exact-material-model",
      materialModelId: "model-1",
      revisionId: "model-r4",
    },
  },
  {
    location: "/models/neutral-materials/neutral-1/revisions/neutral-r2",
    expected: {
      id: "exact-neutral-material",
      neutralMaterialId: "neutral-1",
      revisionId: "neutral-r2",
    },
  },
  {
    location: "/exports/cards/card-1/revisions/card-r5?kind=solver_card",
    expected: {
      id: "exact-solver-card",
      cardId: "card-1",
      revisionId: "card-r5",
      kind: "solver_card",
    },
  },
  {
    location: "/exports/cards/card-1/revisions/card-r5?kind=neutral_solver_card",
    expected: { id: "exact-solver-card", kind: "neutral_solver_card" },
  },
  {
    location: "/exports/cards/card-1/revisions/card-r5?kind=unsupported",
    expected: { id: "unknown" },
  },
  {
    location: "/exports/cards/card-1/revisions/card-r5",
    expected: { id: "unknown" },
  },
  { location: "/exports", expected: { id: "bulk-export" } },
  { location: "/tests", expected: { id: "module-hub", area: "testing" } },
  { location: "/datasets", expected: { id: "module-hub", area: "datasets" } },
  { location: "/models", expected: { id: "module-hub", area: "models" } },
  {
    location: "/governance?candidate_id=candidate-1",
    expected: {
      id: "module-hub",
      area: "governance",
      search: "?candidate_id=candidate-1",
    },
  },
  { location: "/datasets/test-json?material_id=material-1", expected: { id: "canonical-test-data" } },
  { location: "/datasets/import", expected: { id: "governed-import" } },
  {
    location: "/modeling?stage=fit&material_id=material-1",
    expected: { id: "modeling", source: "canonical", search: "?stage=fit&material_id=material-1" },
  },
  {
    location: "/datasets/processing?stage=process",
    expected: { id: "modeling", source: "legacy-datasets", search: "?stage=process" },
  },
  { location: "/activity?view=recent", expected: { id: "activity", source: "canonical" } },
  {
    location: "/jobs-reviews?candidate_id=candidate-1",
    expected: { id: "activity", source: "legacy-jobs-reviews", search: "?candidate_id=candidate-1" },
  },
  {
    location: "/administration",
    expected: { id: "administration", section: "database", source: "canonical" },
  },
  {
    location: "/administration/database?database_id=database-1&database_revision_id=database-r2",
    expected: { id: "administration", section: "database", search: "?database_id=database-1&database_revision_id=database-r2" },
  },
  {
    location: "/administration/schema-bundles?application_id=application-1",
    expected: { id: "administration", section: "bundles" },
  },
  { location: "/administration/records", expected: { id: "administration", section: "records" } },
  { location: "/administration/access", expected: { id: "administration", section: "access" } },
  {
    location: "/catalog/schema?table_id=table-1",
    expected: { id: "administration", section: "database", source: "legacy-catalog", search: "?table_id=table-1" },
  },
  {
    location: "/catalog/records?table_id=table-1&record_id=record-1&revision_id=record-r3",
    expected: { id: "administration", section: "records", source: "legacy-catalog", search: "?table_id=table-1&record_id=record-1&revision_id=record-r3" },
  },
  { location: "/access", expected: { id: "administration", section: "access", source: "legacy-access" } },
  {
    location: "/unsupported/path?selected=material-1",
    expected: { id: "unknown", pathname: "/unsupported/path", search: "?selected=material-1" },
  },
];

describe("parseAppRoute", () => {
  it.each(routeCases)("parses $location", ({ location, expected }) => {
    expect(parseAppRoute(location)).toMatchObject(expected);
  });

  it("preserves a partial exact-revision query without inventing missing pins", () => {
    expect(
      parseAppRoute("/materials/material-1?material_revision_id=material-r9"),
    ).toMatchObject({
      id: "material-detail",
      exactPin: {
        recordId: "",
        recordRevisionId: "",
        materialRevisionId: "material-r9",
      },
    });
  });
});
