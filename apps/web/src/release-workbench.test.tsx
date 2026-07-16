import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReleaseWorkbench } from "./release-workbench";

const release = {
  release_id: "00000000-0000-0000-0000-000000000030",
  classification: "internal" as const,
  release_code: "reference-release",
  title: "Reference release",
  channel: "reference" as const,
  lifecycle_state: "released" as const,
  created_at: "2026-07-24T00:00:00Z",
  created_by: "00000000-0000-0000-0000-000000000003",
  manifest: {
    release_manifest_id: "00000000-0000-0000-0000-000000000031",
    release_id: "00000000-0000-0000-0000-000000000030",
    manifest_sha256: "a".repeat(64),
    package_sha256: "b".repeat(64),
    package_size_bytes: 256,
    package_media_type: "application/vnd.cmp.release-manifest+json" as const,
    state: "released" as const,
    material_id: "00000000-0000-0000-0000-000000000010",
    material_revision_id: "00000000-0000-0000-0000-000000000011",
    material_state_id: "00000000-0000-0000-0000-000000000012",
    material_state_revision_id: "00000000-0000-0000-0000-000000000013",
    property_set_id: "00000000-0000-0000-0000-000000000014",
    property_set_revision_id: "00000000-0000-0000-0000-000000000015",
    material_model_id: "00000000-0000-0000-0000-000000000016",
    material_model_revision_id: "00000000-0000-0000-0000-000000000017",
    material_model_content_sha256: "c".repeat(64),
    solver_card_id: "00000000-0000-0000-0000-000000000018",
    solver_card_revision_id: "00000000-0000-0000-0000-000000000019",
    solver_card_content_sha256: "d".repeat(64),
    mapping_report_sha256: "e".repeat(64),
    card_sha256: "f".repeat(64),
    validation_result_id: "00000000-0000-0000-0000-000000000020",
    validation_result_sha256: "1".repeat(64),
    review_request_id: "00000000-0000-0000-0000-000000000021",
    review_manifest_sha256: "2".repeat(64),
    provenance_snapshot_sha256: "3".repeat(64),
    created_at: "2026-07-24T00:00:00Z",
    created_by: "00000000-0000-0000-0000-000000000003",
    reason: "Release exact candidate",
  },
  links: {},
};

describe("Release completeness workbench", () => {
  it("submits explicit candidate references and downloads the immutable package", async () => {
    const linkClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const fetchMock = vi.fn<typeof fetch>();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 201,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => release,
    } as Response);
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({
        "content-type": "application/vnd.cmp.release-manifest+json",
        "content-disposition": 'attachment; filename="reference-release.cmp-release.json"',
        etag: '"sha256:bbbb"',
      }),
      blob: async () => new Blob(["{}"], { type: "application/json" }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    render(<ReleaseWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} />);
    const inputs = screen.getAllByRole("textbox");
    inputs.forEach((input, index) => {
      const placeholder = input.getAttribute("placeholder") ?? "";
      const value = index === 0
        ? "reference-release"
        : index === 1
          ? "Reference release"
          : placeholder.includes("64 lowercase")
            ? "a".repeat(64)
            : index === inputs.length - 1
              ? "Release exact candidate"
              : `00000000-0000-0000-0000-${String(index + 10).padStart(12, "0")}`;
      fireEvent.change(input, { target: { value } });
    });

    fireEvent.click(screen.getByRole("button", { name: "Create immutable Release" }));
    expect(await screen.findByRole("heading", { name: "Reference release" })).toBeTruthy();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/releases");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      release_code: "reference-release",
      material_model_content_sha256: "a".repeat(64),
    });

    fireEvent.click(screen.getByRole("button", { name: "Download release package" }));
    expect(await screen.findByRole("button", { name: "Download release package" })).toBeTruthy();
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/releases/00000000-0000-0000-0000-000000000030/download");
    expect(linkClick).toHaveBeenCalledOnce();
    linkClick.mockRestore();
  });
});
