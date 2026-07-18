import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CanonicalTestDataWorkbench } from "./canonical-test-data-workbench";

const mocks = vi.hoisted(() => ({ validate: vi.fn() }));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return { ...original, validateCanonicalTestData: mocks.validate };
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
        canonical_document: {},
      },
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
});
