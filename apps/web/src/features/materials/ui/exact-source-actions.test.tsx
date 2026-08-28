// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExactSourceActions } from "./exact-source-actions";

const mocks = vi.hoisted(() => ({
  availability: vi.fn(),
  downloadJson: vi.fn(),
  downloadCsv: vi.fn(),
}));

vi.mock("../api/download-exact-json-source", () => ({
  getExactCatalogSourceAvailability: mocks.availability,
  downloadExactJsonSource: mocks.downloadJson,
  downloadExactCsvSource: mocks.downloadCsv,
}));

const config = { baseUrl: "/api/v1", accessToken: "token" };
const identity = {
  recordId: "40000000-0000-4000-8000-000000000001",
  revisionId: "40000000-0000-4000-8000-000000000002",
};

describe("ExactSourceActions", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.availability.mockResolvedValue({
      data: { available: false, published: true, ready: false },
      etag: null,
    });
  });

  it("keeps legacy or non-ready exact revisions free of source actions", async () => {
    render(<ExactSourceActions config={config} {...identity} />);

    await waitFor(() => expect(mocks.availability).toHaveBeenCalledWith(
      config,
      identity.recordId,
      identity.revisionId,
    ));
    expect(screen.queryByRole("button", { name: "Download JSON" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Download CSV" })).toBeNull();
  });

  it("renders downloads only after the exact source projection is ready", async () => {
    mocks.availability.mockResolvedValue({
      data: { available: true, published: true, ready: true },
      etag: null,
    });
    render(<ExactSourceActions config={config} {...identity} />);

    expect(await screen.findByRole("button", { name: "Download JSON" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download CSV" })).toBeTruthy();
  });

  it("keeps an exact download retryable after a failed response", async () => {
    const user = userEvent.setup();
    const blob = new Blob(["{}"], { type: "application/json" });
    mocks.availability.mockResolvedValue({
      data: { available: true, published: true, ready: true },
      etag: null,
    });
    mocks.downloadJson
      .mockRejectedValueOnce(new Error("source unavailable"))
      .mockResolvedValueOnce({
        data: { blob, filename: "record__r1.json", sha256: "a".repeat(64) },
        etag: null,
      });
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:exact-source");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    render(<ExactSourceActions config={config} {...identity} />);

    await user.click(await screen.findByRole("button", { name: "Download JSON" }));
    expect((await screen.findByRole("alert")).textContent).toContain("source unavailable");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mocks.downloadJson).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
