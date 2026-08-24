import { act, render, screen, waitFor } from "@testing-library/react";
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

  it("shows the simple product vocabulary and creates a User task preset", async () => {
    const user = userEvent.setup();
    render(
      <ProductAccessCenter
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Administrator" })).toBeTruthy();
    expect(screen.getAllByText("Schema configuration")).toHaveLength(1);
    expect(screen.getAllByText("Solver Card export")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Create assignment" }));

    await waitFor(() => expect(mocks.grant).toHaveBeenCalledOnce());
    expect(mocks.grant).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        product_role: "user",
        group_name: "material-users",
        feature_grants: ["processing_calibration", "solver_card_export"],
      }),
    );
  });

  it("changes to the Reviewer preset without exposing technical feature checkboxes", async () => {
    const user = userEvent.setup();
    render(
      <ProductAccessCenter
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Assignments" });
    await user.click(screen.getByRole("button", { name: "Add assignment" }));
    await user.selectOptions(screen.getByLabelText("Role"), "reviewer");
    expect(screen.getByText(/Model approval/, { selector: "#role-task-summary span" })).toBeTruthy();
    expect(screen.getByText("Effective capabilities", { selector: "#role-task-summary strong" })).toBeTruthy();
    expect(screen.queryByRole("group", { name: "Feature grants" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Create assignment" }));

    await waitFor(() => expect(mocks.grant).toHaveBeenCalledOnce());
    expect(mocks.grant).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        product_role: "reviewer",
        feature_grants: ["processing_calibration", "model_approval", "solver_card_export"],
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

  it("shows contract-backed assignment identity and policy fields only when requested", async () => {
    const user = userEvent.setup();
    render(
      <ProductAccessCenter
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(await screen.findByRole("heading", { name: "Assignments" })).toBeTruthy();
    expect(screen.queryByLabelText("Group issuer")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Add assignment" }));
    expect(screen.getByLabelText("Subject type")).toBeTruthy();
    expect(screen.getByLabelText("Group issuer")).toBeTruthy();
    expect(screen.getByLabelText("Group name")).toBeTruthy();
    expect(screen.queryByLabelText("Principal ID")).toBeNull();
    expect(screen.getByLabelText("Maximum classification")).toBeTruthy();
    expect(screen.queryByText("legacy compatible")).toBeNull();
  });

  it("uses shared primary, loading, and danger semantics for access commands", async () => {
    let resolveGrant!: (value: Awaited<ReturnType<typeof mocks.grant>>) => void;
    const pendingGrant = new Promise<Awaited<ReturnType<typeof mocks.grant>>>((resolve) => {
      resolveGrant = resolve;
    });
    mocks.grant.mockReturnValue(pendingGrant);
    mocks.listAssignments.mockResolvedValue({
      data: {
        items: [
          {
            assignment_id: "59000000-0000-4000-8000-000000000011",
            subject_type: "group",
            principal_id: null,
            group_issuer: "http://cmp-demo-idp.local",
            group_name: "material-reviewers",
            product_role: "reviewer",
            feature_grants: ["model_approval"],
            revoked_at: null,
          },
        ],
      },
      etag: null,
    });
    const user = userEvent.setup();
    render(
      <ProductAccessCenter
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Assignments" });
    await user.click(screen.getByRole("button", { name: "Add assignment" }));
    const create = screen.getByRole("button", { name: "Create assignment" });
    const revoke = screen.getByRole("button", { name: "Revoke" });
    expect(create.className).toBe("ux-button primary");
    expect(create.getAttribute("aria-busy")).toBe("false");
    expect(revoke.className).toBe("ux-button danger");

    await user.click(create);
    expect(await screen.findByRole("button", { name: "Saving…" })).toBe(create);
    expect((create as HTMLButtonElement).disabled).toBe(true);
    expect(create.getAttribute("aria-busy")).toBe("true");

    await act(async () => {
      resolveGrant({
        data: {
          assignment_id: "59000000-0000-4000-8000-000000000001",
          organization_id: "59000000-0000-4000-8000-000000000002",
          project_id: "59000000-0000-4000-8000-000000000003",
          subject_type: "group",
          principal_id: null,
          group_issuer: "http://cmp-demo-idp.local",
          group_name: "material-users",
          product_role: "user",
          feature_grants: ["processing_calibration", "solver_card_export"],
          max_classification: "confidential",
          allow_export_controlled: false,
          valid_from: "2026-09-09T09:00:00Z",
          expires_at: null,
          revoked_at: null,
        },
        etag: null,
      });
      await pendingGrant;
    });
    await waitFor(() => expect(screen.getByRole("button", { name: "Add assignment" })).toBeTruthy());
  });
});
