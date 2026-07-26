import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MaterialSearchPage } from "./material-library";

vi.mock("./materials-browse-tree", () => ({
  MaterialsBrowseTree: ({ subsetMode }: { subsetMode: boolean }) => <div>{subsetMode ? "Saved subsets" : "Browse tree"}</div>,
}));

const material = (id: string, name: string) => ({
  material_id: id,
  current_revision: {
    id: `${id}-revision`, aggregate_id: id, revision_no: 1, based_on_revision_id: null,
    schema_id: "cmp.material", schema_version: "1.0.0", content_hash: `${id}-hash`,
    created_at: "2026-07-26T00:00:00Z", created_by: "test-user", change_reason: "fixture",
    organization_id: "org-1", project_id: "project-1", classification: "internal", lifecycle_state: "published",
    content: { name, material_code: `${name}-grade`, material_class: "metal", material_family: "steel", description: `${name} description` },
  },
});

function response(data: unknown): Response {
  return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("MaterialSearchPage navigator and results", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/materials");
  });

  it("defaults plain /materials to Browse, retains mode when finding, and keeps comparison local", async () => {
    window.history.replaceState({}, "", "/materials");
    vi.stubGlobal("fetch", vi.fn(async () => response({
      items: [material("material-1", "DP780"), material("material-2", "DP980")],
      total_count: 2,
      facets: { material_classes: [{ material_class: "metal", count: 2 }] },
    })));

    render(<MaterialSearchPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} onNavigate={vi.fn()} locationSearch="" />);

    expect(await screen.findByText("Browse tree")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Browse" }).getAttribute("aria-current")).toBe("page");
    fireEvent.change(screen.getByRole("textbox", { name: "Search materials" }), { target: { value: "DP780" } });
    fireEvent.click(screen.getByRole("button", { name: "Find" }));
    expect(screen.getByRole("button", { name: "Browse" }).getAttribute("aria-current")).toBe("page");

    fireEvent.click(screen.getByRole("checkbox", { name: "Compare DP780" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Compare DP980" }));
    expect(await screen.findByText("Comparing 2 materials")).toBeTruthy();
    expect(screen.queryByText("Provider")).toBeNull();
    expect(screen.queryByText("Validation availability")).toBeNull();
    expect(screen.queryByText("Yield")).toBeNull();
  });

  it("restores Filters and Subsets from the URL without exposing shell commands", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ items: [], total_count: 0, facets: { material_classes: [] } })));
    const view = render(<MaterialSearchPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} onNavigate={vi.fn()} locationSearch="?mode=filters" />);
    expect((await screen.findByRole("button", { name: "Filters" })).getAttribute("aria-current")).toBe("page");
    view.rerender(<MaterialSearchPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} onNavigate={vi.fn()} locationSearch="?mode=subsets" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Subsets" }).getAttribute("aria-current")).toBe("page"));
    expect(screen.getByText("Saved subsets")).toBeTruthy();
  });
});
