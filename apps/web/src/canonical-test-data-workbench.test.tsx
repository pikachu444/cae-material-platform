import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CanonicalTestDataWorkbench } from "./canonical-test-data-workbench";

const mocks = vi.hoisted(() => ({
  validate: vi.fn(),
  importDocument: vi.fn(),
  listDocuments: vi.fn(),
  downloadDocument: vi.fn(),
  reviseDocument: vi.fn(),
  downloadPackage: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    validateCanonicalTestData: mocks.validate,
    importCanonicalTestData: mocks.importDocument,
    listCanonicalTestDataDocuments: mocks.listDocuments,
    downloadCanonicalTestDataDocument: mocks.downloadDocument,
    reviseCanonicalTestData: mocks.reviseDocument,
    downloadCanonicalTestDataPackage: mocks.downloadPackage,
  };
});

describe("CanonicalTestDataWorkbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.validate.mockResolvedValue({
      data: {
        status: "valid",
        document_sha256: "a".repeat(64),
        canonical_size_bytes: 1200,
        point_count: 3,
        condition_count: 1,
        material_maker: "CMP Demo Metals",
        material_grade: "DP600",
        test_date: "2026-07-18",
        operator: "Kim Tester",
        laboratory: "CMP Laboratory",
        method: "uniaxial tensile reference method",
        specimen_id: "S-01",
        channels: [
          {
            key: "engineering_stress",
            name: "Engineering stress",
            quantity_semantics: "mechanics.stress.engineering",
            axis_role: "dependent",
            original_unit_string: "MPa",
            normalized_unit: "Pa",
            point_count: 3,
            missing_count: 1,
          },
        ],
        canonical_document: { document_id: "DP600-TENSILE-01" },
      },
      etag: null,
    });
    mocks.listDocuments.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.importDocument.mockResolvedValue({
      data: {
        test_data_document_id: "document-1",
        document_key: "DP600-TENSILE-01",
        current_revision: { id: "revision-1", revision_no: 1 },
      },
      etag: '"revision-1"',
    });
    mocks.reviseDocument.mockResolvedValue({
      data: {
        test_data_document_id: "document-1",
        document_key: "DP600-TENSILE-01",
        current_revision: { id: "revision-2", revision_no: 2 },
      },
      etag: '"revision:2:sha256:updated"',
    });
    mocks.downloadPackage.mockResolvedValue({
      data: { blob: new Blob(["package"]), filename: "cmp-test-data-package.zip" },
      etag: null,
    });
  });

  it("validates the editable JSON through the API and exposes unit/missing evidence", async () => {
    const user = userEvent.setup();
    render(
      <CanonicalTestDataWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "dataset-token" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Validate with server" }));
    await waitFor(() => expect(mocks.validate).toHaveBeenCalledOnce());
    expect(await screen.findByRole("heading", { name: "CMP Demo Metals · DP600" })).toBeTruthy();
    expect(screen.getByText("MPa → Pa")).toBeTruthy();
    expect(screen.getByText("1 missing")).toBeTruthy();
    expect(screen.getByText("Kim Tester")).toBeTruthy();
  });

  it("imports a validated document as an immutable revision and refreshes the list", async () => {
    const user = userEvent.setup();
    render(
      <CanonicalTestDataWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "dataset-token" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Validate with server" }));
    await user.click(await screen.findByRole("button", { name: "Import immutable revision" }));
    await waitFor(() => expect(mocks.importDocument).toHaveBeenCalledOnce());
    expect(mocks.importDocument).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        classification: "internal",
        change_reason: "Initial canonical Test Data import",
      }),
    );
    expect(await screen.findByText(/immutable revision 1/)).toBeTruthy();
    expect(mocks.listDocuments).toHaveBeenCalledTimes(2);
  });

  it("appends a revision when the canonical document identity already exists", async () => {
    mocks.listDocuments.mockResolvedValue({
      data: {
        items: [
          {
            test_data_document_id: "document-1",
            document_key: "DP600-TENSILE-01",
            material_maker: "CMP Demo Metals",
            material_grade: "DP600",
            specimen_id: "S-01",
            point_count: 3,
            canonical_sha256: "b".repeat(64),
            current_revision: {
              id: "revision-1",
              revision_no: 1,
              content_hash: "c".repeat(64),
            },
          },
        ],
      },
      etag: null,
    });
    const user = userEvent.setup();
    render(
      <CanonicalTestDataWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "dataset-token" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    await screen.findByText("1 documents");
    await user.click(screen.getByRole("button", { name: "Validate with server" }));
    await user.click(await screen.findByRole("button", { name: "Append immutable revision" }));
    await waitFor(() => expect(mocks.reviseDocument).toHaveBeenCalledOnce());
    expect(mocks.reviseDocument.mock.calls[0][2]).toBe(
      `"revision:1:sha256:${"c".repeat(64)}"`,
    );
    expect(mocks.importDocument).not.toHaveBeenCalled();

    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    await user.click(screen.getByRole("button", { name: "Download current JSON+ZIP" }));
    await waitFor(() => expect(mocks.downloadPackage).toHaveBeenCalledOnce());
    expect(mocks.downloadPackage.mock.calls[0][1]).toEqual([
      { document_id: "document-1", revision_id: "revision-1" },
    ]);
    click.mockRestore();
  });
});
