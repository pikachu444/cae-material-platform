import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MaterialSearchPage } from "./features/materials";

vi.mock("./materials-browse-tree", async () => {
  const React = await import("react");
  return {
    MaterialsBrowseTree: ({
      subsetMode,
      onScopeChange,
    }: {
      subsetMode: boolean;
      onScopeChange?: (scope: { tableId: string }) => void;
    }) => {
      React.useEffect(() => {
        const timer = window.setTimeout(
          () => onScopeChange?.({ tableId: "demo-material-records" }),
          0,
        );
        return () => window.clearTimeout(timer);
      }, [onScopeChange]);
      return <div>{subsetMode ? "Saved subsets" : "Browse tree"}</div>;
    },
  };
});

const material = (id: string, name: string) => ({
  material_id: id,
  current_revision: {
    id: `${id}-revision`,
    aggregate_id: id,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "cmp.material",
    schema_version: "1.0.0",
    content_hash: `${id}-hash`,
    created_at: "2026-07-26T00:00:00Z",
    created_by: "test-user",
    change_reason: "fixture",
    organization_id: "org-1",
    project_id: "project-1",
    classification: "internal",
    lifecycle_state: "draft",
    content: {
      name,
      material_code: `${name}-grade`,
      material_class: "metal",
      material_family: "steel",
      description: `${name} description`,
    },
  },
});

const catalogAttributes = [
  {
    attribute_definition_id: "material-class",
    current_revision: { content: { key: "material_class" } },
  },
  {
    attribute_definition_id: "provider",
    current_revision: { content: { key: "provider" } },
  },
  {
    attribute_definition_id: "evidence-source",
    current_revision: { content: { key: "evidence_source" } },
  },
  {
    attribute_definition_id: "material-family",
    current_revision: { content: { key: "material_family" } },
  },
];

const catalogTable = {
  table_id: "demo-material-records",
  current_revision: { content: { key: "demo_material_records" } },
};

function catalogRecord(item: ReturnType<typeof material>) {
  const recordId = `record-${item.material_id}`;
  const recordRevisionId = `${recordId}-revision`;
  return {
    record_id: recordId,
    table_id: "demo-material-records",
    domain_binding: {
      record_id: recordId,
      record_revision_id: recordRevisionId,
      kind: "material",
      object_id: item.material_id,
      revision_id: item.current_revision.id,
    },
    current_revision: {
      ...item.current_revision,
      id: recordRevisionId,
      aggregate_id: recordId,
      revision_no: 3,
      content: {
        table_revision_id: "demo-material-records-r1",
        name: item.current_revision.content.name,
        external_key: item.current_revision.content.material_code,
        description: item.current_revision.content.description,
        folder_id: null,
        folder_revision_id: null,
        values: [
          {
            data_type: "discrete",
            attribute_definition_id: "material-class",
            value: item.current_revision.content.material_class,
          },
          {
            data_type: "text",
            attribute_definition_id: "material-family",
            value: item.current_revision.content.material_family,
          },
          {
            data_type: "text",
            attribute_definition_id: "provider",
            value: "Demo provider",
          },
          {
            data_type: "text",
            attribute_definition_id: "evidence-source",
            value: "Synthetic reference",
          },
        ],
      },
    },
  };
}

function response(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("MaterialSearchPage navigator and results", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/materials");
  });

  it("defaults plain /materials to Browse, retains mode when finding, and keeps comparison local", async () => {
    window.history.replaceState({}, "", "/materials");
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(1440);
    const items = [
      material("material-1", "DP780"),
      material("material-2", "DP980"),
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input) => {
        const url = String(input);
        if (
          url.endsWith("/catalog/tables") ||
          url.endsWith("/catalog/explorer/tables")
        )
          return response({ items: [catalogTable] });
        if (url.endsWith("/catalog/tables/demo-material-records/attributes"))
          return response({ items: catalogAttributes });
        if (url.endsWith("/catalog/records:search"))
          return response({
            items: items.map(catalogRecord),
            total_count: 2,
            offset: 0,
            limit: 50,
            facets: [
              {
                attribute_definition_id: "material-class",
                value: "metal",
                count: 2,
              },
              {
                attribute_definition_id: "provider",
                value: "Demo provider",
                count: 2,
              },
              {
                attribute_definition_id: "evidence-source",
                value: "Synthetic reference",
                count: 2,
              },
            ],
          });
        return response({});
      }),
    );

    const workspaceStatusUpdates: Array<{ revision?: string }> = [];
    const observeWorkspaceStatus = (event: Event) => {
      workspaceStatusUpdates.push(
        (event as CustomEvent<{ revision?: string }>).detail,
      );
    };
    window.addEventListener("cmp:workspace-status", observeWorkspaceStatus);
    render(
      <MaterialSearchPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        onNavigate={vi.fn()}
        locationSearch=""
      />,
    );

    expect(await screen.findByText("Browse tree")).toBeTruthy();
    expect(
      await screen.findByRole("checkbox", { name: "Compare DP780" }),
    ).toBeTruthy();
    await waitFor(() =>
      expect(
        workspaceStatusUpdates.some(({ revision }) => revision === "r3"),
      ).toBe(true),
    );
    const selectedStatus = workspaceStatusUpdates.find(
      ({ revision }) => revision === "r3",
    );
    expect(selectedStatus?.revision).toBe("r3");
    expect(selectedStatus?.revision).not.toMatch(/\bdraft\b/i);
    expect(screen.queryByRole("columnheader", { name: "Status" })).toBeNull();
    expect(
      screen.getByRole("table", { name: "Material results" }).textContent,
    ).not.toMatch(/\bdraft\b/i);
    expect(document.querySelector(".materials-selection")).toBeNull();
    expect(screen.queryByRole("button", { name: /details pane/i })).toBeNull();
    window.removeEventListener("cmp:workspace-status", observeWorkspaceStatus);
    expect(screen.getAllByText("Metal").length).toBeGreaterThan(0);
    expect(screen.queryByText("metal")).toBeNull();
    expect(
      screen
        .getByRole("button", { name: "Browse" })
        .getAttribute("aria-current"),
    ).toBe("page");
    fireEvent.click(screen.getByRole("button", { name: "Filters" }));
    fireEvent.change(
      screen.getByRole("textbox", { name: "Search materials" }),
      { target: { value: "DP780" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Find" }));
    expect(
      screen
        .getByRole("button", { name: "Filters" })
        .getAttribute("aria-current"),
    ).toBe("page");

    fireEvent.click(screen.getByRole("checkbox", { name: "Compare DP780" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Compare DP980" }));
    expect(await screen.findByText("Comparing 2 materials")).toBeTruthy();
    expect(screen.getByText("Provider")).toBeTruthy();
    expect(screen.queryByText("Validation availability")).toBeNull();
    expect(screen.queryByText("Yield")).toBeNull();

    const materialSortButton = screen.getByRole("button", {
      name: "Material / grade",
    });
    const familySortButton = screen.getByRole("button", { name: "Family" });
    expect(materialSortButton.querySelectorAll("svg")).toHaveLength(1);
    expect(familySortButton.querySelectorAll("svg")).toHaveLength(0);
    const ascendingPath = materialSortButton
      .querySelector("svg path:last-child")
      ?.getAttribute("d");
    fireEvent.click(materialSortButton);
    await waitFor(() =>
      expect(window.location.search).toContain("direction=descending"),
    );
    const descendingPath = materialSortButton
      .querySelector("svg path:last-child")
      ?.getAttribute("d");
    expect(descendingPath).toBeTruthy();
    expect(descendingPath).not.toBe(ascendingPath);
    fireEvent.click(familySortButton);
    await waitFor(() =>
      expect(window.location.search).toContain("sort=material_class"),
    );
    expect(materialSortButton.querySelectorAll("svg")).toHaveLength(0);
    expect(familySortButton.querySelectorAll("svg")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Filters" }));
    const familySelect = await screen.findByRole("combobox", {
      name: "Material class",
    });
    expect(screen.getByRole("option", { name: "Metal (2)" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "metal (2)" })).toBeNull();
    fireEvent.change(familySelect, { target: { value: "metal" } });
    expect((familySelect as HTMLSelectElement).value).toBe("metal");
    await waitFor(() =>
      expect(new URLSearchParams(window.location.search).get("family")).toBe(
        "metal",
      ),
    );
  });

  it("restores Filters and Subsets from the URL without exposing shell commands", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input) => {
        const url = String(input);
        if (
          url.endsWith("/catalog/tables") ||
          url.endsWith("/catalog/explorer/tables")
        )
          return response({ items: [catalogTable] });
        if (url.endsWith("/catalog/tables/demo-material-records/attributes"))
          return response({ items: catalogAttributes });
        if (url.endsWith("/catalog/records:search"))
          return response({
            items: [],
            total_count: 0,
            offset: 0,
            limit: 50,
            facets: [],
          });
        return response({});
      }),
    );
    const view = render(
      <MaterialSearchPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        onNavigate={vi.fn()}
        locationSearch="?mode=filters"
      />,
    );
    expect(
      (await screen.findByRole("button", { name: "Filters" })).getAttribute(
        "aria-current",
      ),
    ).toBe("page");
    view.rerender(
      <MaterialSearchPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        onNavigate={vi.fn()}
        locationSearch="?mode=subsets"
      />,
    );
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "Subsets" })
          .getAttribute("aria-current"),
      ).toBe("page"),
    );
    expect(screen.getByText("Saved subsets")).toBeTruthy();
  });

  it("opens the selected catalog row with distinct exact record and Material revision pins", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input) => {
        const url = String(input);
        if (
          url.endsWith("/catalog/tables") ||
          url.endsWith("/catalog/explorer/tables")
        )
          return response({ items: [catalogTable] });
        if (url.endsWith("/catalog/tables/demo-material-records/attributes"))
          return response({ items: catalogAttributes });
        if (url.endsWith("/catalog/records:search"))
          return response({
            items: [catalogRecord(material("material-1", "DP780"))],
            total_count: 1,
            offset: 0,
            limit: 50,
            facets: [],
          });
        return response({});
      }),
    );
    const onNavigate = vi.fn();
    render(
      <MaterialSearchPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        onNavigate={onNavigate}
        locationSearch=""
      />,
    );

    const row = await screen.findByRole("row", { name: /DP780/ });
    fireEvent.keyDown(row, { key: "Enter" });
    expect(onNavigate).toHaveBeenLastCalledWith(
      expect.stringContaining("/materials/material-1?"),
    );
    const enterUrl = new URL(
      onNavigate.mock.lastCall?.[0] ?? "/",
      "http://localhost",
    );
    expect(enterUrl.searchParams.get("record_id")).toBe("record-material-1");
    expect(enterUrl.searchParams.get("record_revision_id")).toBe(
      "record-material-1-revision",
    );
    expect(enterUrl.searchParams.get("material_revision_id")).toBe(
      "material-1-revision",
    );

    fireEvent.click(row);
    expect(onNavigate).toHaveBeenLastCalledWith(
      expect.stringContaining("record_revision_id=record-material-1-revision"),
    );
    expect(onNavigate).toHaveBeenLastCalledWith(
      expect.stringContaining("material_revision_id=material-1-revision"),
    );
  });

  it("preserves the last authorized rows and exact selection while a failed query is retried", async () => {
    let failSearch = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input) => {
        const url = String(input);
        if (
          url.endsWith("/catalog/tables") ||
          url.endsWith("/catalog/explorer/tables")
        )
          return response({ items: [catalogTable] });
        if (url.endsWith("/catalog/tables/demo-material-records/attributes"))
          return response({ items: catalogAttributes });
        if (url.endsWith("/catalog/records:search")) {
          if (failSearch) throw new Error("Temporary catalog outage");
          return response({
            items: [catalogRecord(material("material-1", "DP780"))],
            total_count: 1,
            offset: 0,
            limit: 50,
            facets: [],
          });
        }
        return response({});
      }),
    );

    render(
      <MaterialSearchPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        onNavigate={vi.fn()}
        locationSearch="?mode=filters"
      />,
    );
    const row = await screen.findByRole("row", { name: /DP780/ });
    expect(row.getAttribute("aria-selected")).toBe("true");

    failSearch = true;
    fireEvent.change(
      screen.getByRole("textbox", { name: "Search materials" }),
      { target: { value: "DP780 steel" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Find" }));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Temporary catalog outage",
    );
    expect(
      screen.getByRole("row", { name: /DP780/ }).getAttribute("aria-selected"),
    ).toBe("true");
    expect(new URLSearchParams(window.location.search).get("selected")).toBe(
      "material-1",
    );

    failSearch = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(
      screen.getByRole("row", { name: /DP780/ }).getAttribute("aria-selected"),
    ).toBe("true");
  });
});
