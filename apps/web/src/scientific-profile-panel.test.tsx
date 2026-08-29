import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OgdenScientificProfilePanel } from "./scientific-profile-panel";
import type { ScientificProfileResponse } from "./features/modeling/contracts";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const profile: ScientificProfileResponse = {
  scientific_profile_id: "f3000000-0000-4000-8000-000000000001",
  current_revision: {
    id: "f3000000-0000-4000-8000-000000000002",
    aggregate_id: "f3000000-0000-4000-8000-000000000001",
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:modeling:scientific-calibration-profile:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-08-19T00:00:00Z",
    created_by: "f3000000-0000-4000-8000-000000000003",
    change_reason: "Create reference fitting policy",
    organization_id: "f3000000-0000-4000-8000-000000000004",
    project_id: "f3000000-0000-4000-8000-000000000005",
    classification: "internal",
    lifecycle_state: "draft",
    content: {
      profile_label: "Reference elastomer multi-test Ogden",
      family: "elastomer_ogden_prony",
      model_family_id: "urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0",
      approval_status: "reference_unapproved",
      optimizer: "scipy_least_squares_trf",
      residual_definition: "normalized_weighted_least_squares",
      aggregation_order: "point_then_curve_then_mode",
      missing_data_policy: "reject",
      holdout_policy: "explicit_disjoint",
      uncertainty_policy: "jacobian_covariance_or_not_estimable",
      multistart_count: 8,
      seed: 20260716,
      status_note: "Reference only; domain sign-off is not recorded.",
      parameters: {
        mu_initial_pa: 1_200_000,
        mu_lower_pa: 1_000,
        mu_upper_pa: 100_000_000,
        mu_scale_pa: 1_000_000,
        alpha_initial: 2.4,
        alpha_lower: 0.1,
        alpha_upper: 20,
        alpha_scale: 2,
        uniaxial_weight: 1,
        planar_weight: 1,
        biaxial_weight: 1,
      },
    },
  },
  links: {},
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("OgdenScientificProfilePanel", () => {
  it("creates and displays an immutable unapproved reference policy", async () => {
    let created = false;
    const fetchMock = vi.fn<typeof fetch>((_, init) => {
      if (init?.method === "POST") {
        created = true;
        return Promise.resolve(response(profile, 201));
      }
      return Promise.resolve(response({ items: created ? [profile] : [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <OgdenScientificProfilePanel
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
      />,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Create reference scientific profile" }),
    );

    expect(await screen.findByTestId("ogden-scientific-profile")).toBeTruthy();
    expect(screen.getByText("Reference elastomer multi-test Ogden")).toBeTruthy();
    expect(screen.getByText(/reference unapproved/)).toBeTruthy();
    expect(screen.getByText(/jacobian covariance or not estimable/)).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const createCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(createCall?.[1]?.body))).toMatchObject({
      content: {
        family: "elastomer_ogden_prony",
        approval_status: "reference_unapproved",
        multistart_count: 8,
        ogden: { alpha_lower: 0.1, alpha_upper: 20 },
      },
    });
  });
});
