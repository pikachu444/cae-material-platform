import { afterEach, describe, expect, it } from "vitest";

import {
  loadDeliveryActivities,
  mappingDisposition,
  recordDeliveryActivity,
} from "./solver-card-delivery";

describe("solver-card delivery policy", () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  it("classifies every delivery mapping state without silently downgrading it", () => {
    expect(mappingDisposition([{ status: "exact" }, { status: "transformed" }])).toBe("direct");
    expect(mappingDisposition([{ status: "exact" }, { status: "approximated" }])).toBe("review");
    expect(mappingDisposition([{ status: "ignored" }])).toBe("review");
    expect(mappingDisposition([{ status: "ignored" }, { status: "unsupported" }])).toBe("blocked");
  });

  it("records exact Material and Solver Card revisions without duplicating the same action", () => {
    const activity = {
      action: "preview" as const,
      materialId: "material-1",
      materialRevisionId: "material-r3",
      materialLabel: "DP780",
      cardId: "card-1",
      cardRevisionId: "card-r2",
      cardLabel: "DP780 OpenRadioss card",
      solver: "OpenRadioss" as const,
      extension: ".rad" as const,
    };

    recordDeliveryActivity(activity);
    recordDeliveryActivity(activity);

    expect(loadDeliveryActivities()).toMatchObject([{
      version: 1,
      ...activity,
    }]);
  });
});
