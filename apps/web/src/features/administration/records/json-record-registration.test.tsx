// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JsonRecordRegistrationPanel } from "./json-record-registration";
import { detectSourceFamily } from "./json-registration-controller";

const mocks = vi.hoisted(() => ({
  uploadFiles: vi.fn(),
  preview: vi.fn(),
  save: vi.fn(),
}));

vi.mock("./json-registration-api", () => ({
  uploadJsonRegistrationFiles: mocks.uploadFiles,
  previewJsonRecordRegistration: mocks.preview,
  saveJsonRecordRegistration: mocks.save,
}));

const config = { baseUrl: "/api/v1", accessToken: "token" };
const artifact = {
  filename: "json-record-registration.zip",
  artifact_id: "20000000-0000-4000-8000-000000000001",
  sha256: "c".repeat(64),
  media_type: "application/zip" as const,
  size_bytes: 28,
};

function response(valid: boolean) {
  return {
    $schema: "https://cmp.example/contracts/catalog/json-record-registration.schema.json",
    contract_version: "1.0.0" as const,
    preview_token: "preview-1",
    expires_at: "2026-08-27T10:00:00Z",
    package: { media_type: "application/zip" as const, sha256: "d".repeat(64) },
    format_revision_id: "10000000-0000-4000-8000-000000000002",
    detected_record_type: "technical_data",
    format: null,
    valid,
    files: [{
      filename: "record.json",
      sha256: "c".repeat(64),
      size_bytes: 28,
      valid,
      record_name: valid ? "Record one" : null,
      warnings: [],
      errors: valid ? [] : [{
        filename: "record.json",
        code: "unit_invalid",
        message: "The declared unit is not installed for this binding.",
        recovery: "Correct the source unit and preview again.",
        json_pointer: "/technical/modulus",
        line: 2,
        column: 4,
        severity: "error" as const,
      }],
      fields: valid ? [{
        section: "Data information",
        label: "Record name",
        pointer: "/record/name",
        kind: "text",
        value: "Record one",
        unit: null,
        summary: null,
      }] : [],
    }],
  };
}

describe("JsonRecordRegistrationPanel", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.uploadFiles.mockResolvedValue({ data: artifact, etag: null });
  });

  it("classifies mixed source families without discarding the selected files", () => {
    expect(
      detectSourceFamily([
        new File(["{}"], "record.json", { type: "application/json" }),
        new File(["a,b"], "records.csv", { type: "text/csv" }),
      ]),
    ).toBe("mixed");
  });

  it("projects preview artifacts to the four backend fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    try {
      const actual = await vi.importActual<typeof import("./json-registration-api")>(
        "./json-registration-api",
      );
      await actual.previewJsonRecordRegistration(config, {
        format_revision_id: "format-revision",
        classification: "internal",
        files: [artifact],
      });

      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(JSON.parse(String(init.body))).toEqual({
        format_revision_id: "format-revision",
        classification: "internal",
        files: [{
          filename: artifact.filename,
          artifact_id: artifact.artifact_id,
          sha256: artifact.sha256,
          media_type: artifact.media_type,
        }],
      });
      expect(JSON.stringify(init.body)).not.toContain("size_bytes");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("keeps multiple selected filenames and renders exact server diagnostics", async () => {
    const user = userEvent.setup();
    mocks.preview.mockResolvedValue({ data: response(false), etag: null });
    render(<JsonRecordRegistrationPanel config={config} onClose={vi.fn()} />);

    const picker = screen.getByLabelText("Add files");
    await user.upload(picker, [
      new File(["{}"], "record.json", { type: "application/json" }),
      new File(["{}"], "second.json", { type: "application/json" }),
    ]);
    expect(await screen.findByText("second.json")).toBeTruthy();
    expect(mocks.uploadFiles).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText(/unit_invalid/)).toBeTruthy();
    expect(screen.getByRole("row", { name: /record\.json/ })).toBeTruthy();
    expect(screen.getByText(/\/technical\/modulus/)).toBeTruthy();
    expect(screen.getByText(/line 2, column 4/)).toBeTruthy();
    expect(screen.getByText(/Cause: The declared unit/)).toBeTruthy();
    expect(screen.getByText(/Recovery: Correct the source unit/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("saves a valid preview without client format selectors and keeps the save view sparse", async () => {
    const user = userEvent.setup();
    mocks.preview.mockResolvedValue({ data: { ...response(true), preview_token: "preview-2" }, etag: null });
    mocks.save.mockResolvedValue({
      data: {
        batch_id: "30000000-0000-4000-8000-000000000001",
        replayed: false,
        package_sha256: "d".repeat(64),
        lifecycle: "DRAFT" as const,
        records: [{
          record_id: "40000000-0000-4000-8000-000000000001",
          record_revision_id: "40000000-0000-4000-8000-000000000002",
          revision_no: 1,
          external_key: "CMP-246-TECH-DP780",
        }],
        publication: { state: "DRAFT" as const, allowed: false },
      },
      etag: null,
    });
    render(<JsonRecordRegistrationPanel config={config} onClose={vi.fn()} />);
    await user.upload(screen.getByLabelText("Add files"), new File(["{}"], "record.json", { type: "application/json" }));
    await user.click(screen.getByRole("button", { name: "Preview" }));
    expect(screen.queryByRole("button", { name: "Preview" })).toBeNull();
    expect(screen.getByRole("row", { name: /record\.json, Record one/ })).toBeTruthy();
    expect(screen.getByTitle("record.json").getAttribute("aria-label")).toBe("record.json");
    expect(screen.getByTitle("Record one").getAttribute("aria-label")).toBe("Record one");
    expect(screen.getByText("Detected content", { exact: true })).toBeTruthy();
    expect(screen.getAllByText("Technical data", { exact: true })).toHaveLength(1);
    expect(screen.getByRole("status").textContent).toContain("1 selected · 1 valid");
    await user.type(await screen.findByLabelText("Reason for change"), "Approved source registration");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(mocks.save).toHaveBeenCalledOnce());
    expect(mocks.save).toHaveBeenCalledWith(
      expect.anything(),
      "preview-2",
      expect.objectContaining({ package_sha256: "d".repeat(64) }),
    );
    expect(await screen.findByText("Draft records saved.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "JSON" })).toBeNull();
    expect(screen.queryByRole("link", { name: "CSV" })).toBeNull();
  });

  it("opens the exact saved table revision without selecting a saved record", async () => {
    const user = userEvent.setup();
    const onOpenRecords = vi.fn();
    mocks.preview.mockResolvedValue({
      data: {
        ...response(true),
        format: { table: { id: "table-exact", revision_id: "table-revision-exact" } },
      },
      etag: null,
    });
    mocks.save.mockResolvedValue({
      data: {
        batch_id: "30000000-0000-4000-8000-000000000001",
        replayed: false,
        package_sha256: "d".repeat(64),
        lifecycle: "DRAFT" as const,
        records: [{
          record_id: "40000000-0000-4000-8000-000000000001",
          record_revision_id: "40000000-0000-4000-8000-000000000002",
          revision_no: 1,
          external_key: "CMP-246-TECH-DP780",
        }],
        publication: { state: "DRAFT" as const, allowed: false },
      },
      etag: null,
    });
    render(
      <JsonRecordRegistrationPanel
        config={config}
        onClose={vi.fn()}
        onOpenRecords={onOpenRecords}
      />,
    );

    await user.upload(
      screen.getByLabelText("Add files"),
      new File(["{}"], "record.json", { type: "application/json" }),
    );
    await user.click(screen.getByRole("button", { name: "Preview" }));
    await user.type(await screen.findByLabelText("Reason for change"), "Approved source registration");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await user.click(await screen.findByRole("button", { name: "Open records" }));

    expect(onOpenRecords).toHaveBeenCalledWith({
      tableId: "table-exact",
      tableRevisionId: "table-revision-exact",
    });
    expect(onOpenRecords.mock.calls[0]?.[0]).not.toHaveProperty("records");
  });

  it("keeps a tabular selection while record type is chosen", async () => {
    const user = userEvent.setup();
    const chooseRecordType = vi.fn();
    render(
      <JsonRecordRegistrationPanel
        config={config}
        onClose={vi.fn()}
        onChooseRecordType={chooseRecordType}
      />,
    );
    await user.upload(
      screen.getByLabelText("Add files"),
      new File(["a,b\n1,2"], "records.csv", { type: "text/csv" }),
    );
    expect(await screen.findByText("records.csv")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Choose Record type" }));
    expect(chooseRecordType).toHaveBeenCalledOnce();
    expect(screen.getByText("records.csv")).toBeTruthy();
  });

  it("retains staged files and permits retry after upload failure", async () => {
    const user = userEvent.setup();
    mocks.uploadFiles
      .mockRejectedValueOnce(new Error("upload failed"))
      .mockResolvedValueOnce({ data: artifact, etag: null });
    render(<JsonRecordRegistrationPanel config={config} onClose={vi.fn()} />);

    await user.upload(
      screen.getByLabelText("Add files"),
      new File(["{}"], "record.json", { type: "application/json" }),
    );
    expect(await screen.findByText("upload failed")).toBeTruthy();
    expect(screen.getByText("record.json")).toBeTruthy();
    expect(screen.getByRole("row", { name: /record\.json, —, Selected/ })).toBeTruthy();
    expect(screen.getAllByRole("listitem").find((item) => item.textContent?.includes("Files"))?.className).toContain("is-current");
    const retry = screen.getByRole("button", { name: "Retry" });
    expect((retry as HTMLButtonElement).disabled).toBe(false);

    await user.click(retry);
    await waitFor(() => expect(mocks.uploadFiles).toHaveBeenCalledTimes(2));
    expect(screen.queryByText("upload failed")).toBeNull();
    expect(screen.getByText("record.json")).toBeTruthy();
  });

  it("keeps a server preview failure in Preview step and hides the old valid count", async () => {
    const user = userEvent.setup();
    mocks.preview.mockRejectedValueOnce(new Error("preview unavailable"));
    render(<JsonRecordRegistrationPanel config={config} onClose={vi.fn()} />);

    await user.upload(
      screen.getByLabelText("Add files"),
      new File(["{}"], "record.json", { type: "application/json" }),
    );
    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("preview unavailable")).toBeTruthy();
    expect(screen.getAllByRole("listitem").find((item) => item.textContent?.includes("Preview"))?.className).toContain("is-current");
    expect(screen.getAllByRole("listitem").find((item) => item.textContent?.includes("Files"))?.className).not.toContain("is-current");
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toBe("1 selected");
  });

  it("uses Preview after a changed selection instead of retrying the old preview", async () => {
    const user = userEvent.setup();
    mocks.preview.mockResolvedValueOnce({ data: response(true), etag: null });
    render(<JsonRecordRegistrationPanel config={config} onClose={vi.fn()} />);

    await user.upload(
      screen.getByLabelText("Add files"),
      new File(["{}"], "record.json", { type: "application/json" }),
    );
    await waitFor(() => expect((screen.getByRole("button", { name: "Preview" }) as HTMLButtonElement).disabled).toBe(false));
    await user.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByRole("row", { name: /record\.json, Record one/ })).toBeTruthy();

    await user.upload(
      screen.getByLabelText("Add files"),
      new File(["{}"], "replacement.json", { type: "application/json" }),
    );
    await waitFor(() => expect(mocks.uploadFiles).toHaveBeenCalledTimes(2));

    expect(screen.getByRole("button", { name: "Preview" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(screen.getByRole("status").textContent).toBe("1 selected");
  });

  it("uses an available exact table without showing a missing-type blocker", async () => {
    const user = userEvent.setup();
    const onTabularFiles = vi.fn();
    const table = {
      tableId: "50000000-0000-4000-8000-000000000001",
      revisionId: "50000000-0000-4000-8000-000000000002",
    };
    render(
      <JsonRecordRegistrationPanel
        config={config}
        onClose={vi.fn()}
        selectedTable={table}
        onTabularFiles={onTabularFiles}
      />,
    );
    const file = new File(["a,b\n1,2"], "records.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Add files"), file);

    expect(screen.queryByText("Choose the exact Record type to continue.")).toBeNull();
    expect(screen.getByRole("button", { name: "Continue" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(onTabularFiles).toHaveBeenCalledWith([file], table);
  });

  it("clears a missing-type blocker when the exact table is selected later", async () => {
    const user = userEvent.setup();
    const onTabularFiles = vi.fn();
    const table = {
      tableId: "50000000-0000-4000-8000-000000000001",
      revisionId: "50000000-0000-4000-8000-000000000002",
    };
    const { rerender } = render(
      <JsonRecordRegistrationPanel
        config={config}
        onClose={vi.fn()}
        onTabularFiles={onTabularFiles}
      />,
    );
    const file = new File(["a,b\n1,2"], "records.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Add files"), file);
    expect(await screen.findByText("Choose the exact Record type to continue.")).toBeTruthy();

    rerender(
      <JsonRecordRegistrationPanel
        config={config}
        onClose={vi.fn()}
        selectedTable={table}
        onTabularFiles={onTabularFiles}
      />,
    );
    await waitFor(() => {
      expect(screen.queryByText("Choose the exact Record type to continue.")).toBeNull();
      expect(screen.getByRole("button", { name: "Continue" })).toBeTruthy();
    });
    expect(screen.getByText("records.csv")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(onTabularFiles).toHaveBeenCalledWith([file], table);
  });

  it("does not expose ZIP in normal picking or family detection", () => {
    const picker = render(<JsonRecordRegistrationPanel config={config} onClose={vi.fn()} />);
    expect(picker.getByLabelText("Add files").getAttribute("accept") ?? "").not.toContain("zip");
    expect(
      detectSourceFamily([new File(["{}"], "records.zip", { type: "application/zip" })]),
    ).toBe("unsupported");
  });
});
