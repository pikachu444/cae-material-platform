import { beforeEach, describe, expect, it } from "vitest";

import {
  appendActivityFailure,
  appendActivityOutcome,
  readActivityRecoveries,
  resolveActivityRecovery,
} from "./activity-recovery";

const principal = "principal-160";
const organization = "organization-160";
const project = "project-160";

describe("activity recovery facts", () => {
  beforeEach(() => window.localStorage.clear());

  it("preserves failed exact context until the user resolves it", () => {
    const failed = appendActivityFailure(
      principal,
      organization,
      project,
      "activity",
      { kind: "selected_model_json", path: "/modeling?stage=export", materialModelId: "model", materialModelRevisionId: "model-r1" },
      "Selected model download failed",
    );
    appendActivityOutcome(
      principal,
      organization,
      project,
      "activity",
      { kind: "selected_model_json", path: "/modeling?stage=export", materialModelId: "model", materialModelRevisionId: "model-r1" },
      "Selected model downloaded",
    );

    const recoveries = readActivityRecoveries(principal, organization, project);
    expect(recoveries).toHaveLength(2);
    expect(recoveries.find((item) => item.id === failed.id)?.status).toBe("resolved");
    resolveActivityRecovery(principal, organization, project, "activity", failed.id);
    expect(readActivityRecoveries(principal, organization, project).find((item) => item.id === failed.id)?.status).toBe("resolved");
  });

  it("matches a richer successful retry to the original exact selection", () => {
    const failed = appendActivityFailure(
      principal,
      organization,
      project,
      "activity",
      { kind: "solver_card", path: "/materials/material/cards/card", materialId: "material", materialRevisionId: "material-r2", solverCardId: "card", solverCardRevisionId: "card-r3", target: "openradioss-2025" },
      "Preview failed",
    );
    appendActivityOutcome(
      principal,
      organization,
      project,
      "activity",
      { kind: "solver_card", path: "/materials/material/cards/card", materialId: "material", materialRevisionId: "material-r2", solverCardId: "card", solverCardRevisionId: "card-r3", target: "openradioss-2025" },
      "Downloaded exact solver card",
    );
    expect(readActivityRecoveries(principal, organization, project).find((item) => item.id === failed.id)?.status).toBe("resolved");
  });

  it("does not resolve a failure when a stable card has a different exact revision", () => {
    const failed = appendActivityFailure(
      principal,
      organization,
      project,
      "activity",
      { kind: "solver_card", path: "/materials/material/cards/card", materialId: "material", materialRevisionId: "material-r1", solverCardId: "card", solverCardRevisionId: "card-r2", target: "openradioss-2025" },
      "Preview failed",
    );
    appendActivityOutcome(
      principal,
      organization,
      project,
      "activity",
      { kind: "solver_card", path: "/materials/material/cards/card", materialId: "material", materialRevisionId: "material-r2", solverCardId: "card", solverCardRevisionId: "card-r3", target: "openradioss-2025" },
      "Downloaded newer solver card",
    );
    expect(readActivityRecoveries(principal, organization, project).find((item) => item.id === failed.id)?.status).toBe("failed");
  });
});
