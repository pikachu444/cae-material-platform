import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProductAccessCenter } from "./product-access-center";

const mocks = vi.hoisted(() => ({
  getEffective: vi.fn(),
  listAssignments: vi.fn(),
  grant: vi.fn(),
  revoke: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    getEffectiveProductAccess: mocks.getEffective,
    listProductAccessAssignments: mocks.listAssignments,
    grantProductAccess: mocks.grant,
    revokeProductAccess: mocks.revoke,
  };
});

describe("ProductAccessCenter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getEffective.mockResolvedValue({
      data: {
        product_role: "administrator",
        feature_grants: [
          "schema_configuration",
          "catalog_edit",
          "processing_calibration",
          "model_approval",
          "solver_card_export",
        ],
        legacy_compatible: true,
      },
      etag: null,
    });
    mocks.listAssignments.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.grant.mockResolvedValue({
      data: {
        assignment_id: "59000000-0000-4000-8000-000000000001",
        organization_id: "59000000-0000-4000-8000-000000000002",
        project_id: "59000000-0000-4000-8000-000000000003",
        subject_type: "group",
        principal_id: null,
        group_issuer: "http://cmp-demo-idp.local",
        group_name: "material-users",
        product_role: "user",
        feature_grants: ["catalog_edit", "processing_calibration", "solver_card_export"],
        max_classification: "confidential",
        allow_export_controlled: false,
        valid_from: "2026-09-09T09:00:00Z",
        expires_at: null,
        revoked_at: null,
      },
      etag: null,
    });
  });

  it("shows the simple product vocabulary and creates a feature assignment", async () => {
    const user = userEvent.setup();
    render(
      <ProductAccessCenter
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Administrator" })).toBeTruthy();
    expect(screen.getAllByText("Schema configuration")).toHaveLength(2);
    expect(screen.getAllByText("Solver Card export")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Create assignment" }));

    await waitFor(() => expect(mocks.grant).toHaveBeenCalledOnce());
    expect(mocks.grant).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        product_role: "user",
        group_name: "material-users",
        feature_grants: ["catalog_edit", "processing_calibration", "solver_card_export"],
      }),
    );
  });

  it("does not expose assignment management to a normal User", async () => {
    mocks.getEffective.mockResolvedValue({
      data: {
        product_role: "user",
        feature_grants: ["solver_card_export"],
        legacy_compatible: false,
      },
      etag: null,
    });

    render(
      <ProductAccessCenter
        config={{ baseUrl: "/api/v1", accessToken: "user-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByRole("heading", { name: "User" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Assign product access" })).toBeNull();
    expect(mocks.listAssignments).not.toHaveBeenCalled();
  });
});
