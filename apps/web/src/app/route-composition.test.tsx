import { Suspense } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  type ApiConfig,
} from "../shared/api";
import { RouteComposition } from "./route-composition";
import { parseAppRoute } from "./routes";

vi.mock("../features/materials", () => ({
  MaterialSearchPage: ({ locationSearch }: { locationSearch: string }) => (
    <output data-testid="material-search">{locationSearch}</output>
  ),
  MaterialDetailPage: ({
    materialId,
    activeTab,
    exactPin,
  }: {
    materialId: string;
    activeTab: string;
    exactPin?: unknown;
  }) => (
    <output data-testid="material-detail">
      {JSON.stringify({ materialId, activeTab, exactPin })}
    </output>
  ),
  ExactRecordDatasheetPage: () => <output data-testid="material-record" />,
  SolverCardPreviewPage: () => <output data-testid="material-card" />,
}));

vi.mock("../features/administration", () => ({
  AdministrationWorkspace: ({
    section,
    locationSearch,
  }: {
    section: string;
    locationSearch: string;
  }) => (
    <output data-testid="administration">
      {JSON.stringify({ section, locationSearch })}
    </output>
  ),
}));

vi.mock("../material-modeling-workspace", () => ({
  MaterialModelingWorkspace: ({ locationSearch }: { locationSearch: string }) => (
    <output data-testid="modeling">{locationSearch}</output>
  ),
}));

vi.mock("../material-library", () => ({
  ActivityPage: ({ locationSearch }: { locationSearch: string }) => (
    <output data-testid="activity">{locationSearch}</output>
  ),
}));

vi.mock("../exact-domain-pages", () => ({
  ExactMaterialModelPage: () => <output data-testid="exact-model" />,
  ExactNeutralMaterialPage: () => <output data-testid="exact-neutral" />,
  ExactSolverCardPage: ({
    cardId,
    revisionId,
    kind,
  }: {
    cardId: string;
    revisionId: string;
    kind: string;
  }) => (
    <output data-testid="exact-card">
      {JSON.stringify({ cardId, revisionId, kind })}
    </output>
  ),
}));

vi.mock("./legacy-route-pages", () => ({
  ModuleHubPage: ({
    area,
    locationSearch,
  }: {
    area: string;
    locationSearch: string;
  }) => (
    <output data-testid="module-hub">
      {JSON.stringify({ area, locationSearch })}
    </output>
  ),
  MaterialCreatePage: () => <output data-testid="material-create" />,
}));

const config: ApiConfig = { baseUrl: "/api/v1", accessToken: "test-token" };

function renderLocation(location: string) {
  render(
    <Suspense fallback={<p>Loading route</p>}>
      <RouteComposition
        route={parseAppRoute(location)}
        config={config}
        navigate={vi.fn()}
        onOpenConnection={vi.fn()}
      />
    </Suspense>,
  );
}

describe("RouteComposition", () => {
  afterEach(cleanup);

  it("passes canonical Material identity, tab and exact revision pins through the public feature entry", async () => {
    renderLocation(
      "/materials/material-1/cards?record_id=record-1&record_revision_id=record-r3&material_revision_id=material-r7",
    );

    expect(JSON.parse((await screen.findByTestId("material-detail")).textContent ?? "{}")).toEqual({
      materialId: "material-1",
      activeTab: "cards",
      exactPin: {
        recordId: "record-1",
        recordRevisionId: "record-r3",
        materialRevisionId: "material-r7",
      },
    });
  });

  it("maps a legacy Material area to the same canonical detail composition", async () => {
    renderLocation("/materials/material-1/models");

    expect(JSON.parse((await screen.findByTestId("material-detail")).textContent ?? "{}")).toMatchObject({
      materialId: "material-1",
      activeTab: "cards",
    });
  });

  it("preserves Modeling stage query composition on canonical and compatibility paths", async () => {
    renderLocation("/datasets/processing?stage=fit&material_id=material-1");

    expect((await screen.findByTestId("modeling")).textContent).toBe(
      "?stage=fit&material_id=material-1",
    );
  });

  it("routes the legacy review path to Activity with its query unchanged", async () => {
    renderLocation("/jobs-reviews?candidate_id=candidate-1");

    expect((await screen.findByTestId("activity")).textContent).toBe(
      "?candidate_id=candidate-1",
    );
  });

  it("passes exact legacy Administration record selection to the canonical workspace", async () => {
    const query = "?table_id=table-1&record_id=record-1&revision_id=record-r3";
    renderLocation(`/catalog/records${query}`);

    expect(JSON.parse((await screen.findByTestId("administration")).textContent ?? "{}")).toEqual({
      section: "records",
      locationSearch: query,
    });
  });

  it("composes exact card identity only for a supported card kind", async () => {
    renderLocation(
      "/exports/cards/card-1/revisions/card-r5?kind=neutral_solver_card",
    );

    expect(JSON.parse((await screen.findByTestId("exact-card")).textContent ?? "{}")).toEqual({
      cardId: "card-1",
      revisionId: "card-r5",
      kind: "neutral_solver_card",
    });
  });

  it("uses the historical Materials fallback for malformed and unknown routes without losing the query", async () => {
    renderLocation(
      "/exports/cards/card-1/revisions/card-r5?kind=unsupported&selected=material-1",
    );

    expect((await screen.findByTestId("material-search")).textContent).toBe(
      "?kind=unsupported&selected=material-1",
    );
  });

  it("keeps the legacy governance hub query at its bounded compatibility page", async () => {
    renderLocation("/governance?solver_card_id=card-1&solver_card_revision_id=card-r5");

    expect(JSON.parse((await screen.findByTestId("module-hub")).textContent ?? "{}")).toEqual({
      area: "governance",
      locationSearch: "?solver_card_id=card-1&solver_card_revision_id=card-r5",
    });
  });
});
