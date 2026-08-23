import { afterEach, describe, expect, it } from "vitest";

import {
  materialDetailPath,
  materialsPath,
  materialsReturnPath,
  parseMaterialsLocation,
  rememberMaterialsReturnPath,
} from "./materials-route-state";

describe("Materials route state", () => {
  afterEach(() => {
    window.history.replaceState({}, "", "/materials");
    window.sessionStorage.clear();
  });

  it("round-trips query, server scope, navigator, selection, sort, and pagination state", () => {
    const path = materialsPath({
      query: "DP780",
      materialClass: "metal",
      provider: "Demo provider",
      evidenceSource: "Synthetic reference",
      scope: {
        tableId: "demo-material-records",
        folderId: "technical-data",
        recordId: null,
        includeDescendants: true,
      },
      sortKey: "material_class",
      sortDirection: "descending",
      offset: 50,
      leftMode: "filters",
      selectedId: "material-1",
    });

    expect(
      parseMaterialsLocation(new URL(path, "http://localhost").search),
    ).toEqual({
      query: "DP780",
      materialClass: "metal",
      provider: "Demo provider",
      evidenceSource: "Synthetic reference",
      scope: {
        tableId: "demo-material-records",
        folderId: "technical-data",
        recordId: null,
        includeDescendants: true,
      },
      sortKey: "material_class",
      sortDirection: "descending",
      offset: 50,
      leftMode: "filters",
      selectedId: "material-1",
    });
  });

  it("keeps the catalog record revision distinct from the Material revision in exact detail links", () => {
    const path = materialDetailPath("material-1", "curves", {
      recordId: "record-material-1",
      recordRevisionId: "record-material-1-revision-3",
      materialRevisionId: "material-1-revision-7",
    });
    const url = new URL(path, "http://localhost");

    expect(url.pathname).toBe("/materials/material-1/curves");
    expect(url.searchParams.get("record_id")).toBe("record-material-1");
    expect(url.searchParams.get("record_revision_id")).toBe(
      "record-material-1-revision-3",
    );
    expect(url.searchParams.get("material_revision_id")).toBe(
      "material-1-revision-7",
    );
  });

  it("accepts only a Materials-owned return path", () => {
    rememberMaterialsReturnPath("/materials?q=DP780&selected=material-1");
    expect(materialsReturnPath()).toBe(
      "/materials?q=DP780&selected=material-1",
    );

    rememberMaterialsReturnPath("/administration?tab=database");
    expect(materialsReturnPath()).toBe("/materials");
  });
});
