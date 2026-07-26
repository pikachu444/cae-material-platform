import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModelingExportPrerequisites } from "./modeling-export-prerequisites";

describe("ModelingExportPrerequisites", () => {
  it("shows a recovery checklist without exposing artifact controls", () => {
    render(<ModelingExportPrerequisites prerequisites={[
      { label: "Material", status: "missing", detail: "Current session Material revision" },
      { label: "Server provenance proof", status: "not-supported", detail: "API contract unavailable" },
    ]} />);

    expect(screen.getByRole("status", { name: "Export prerequisites" })).toBeTruthy();
    expect(screen.getByText("Server provenance proof")).toBeTruthy();
    expect(screen.getByText("Required lineage")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /preview|deliver|create/i })).toBeNull();
  });

  it("renders mismatched exact pins as stale recovery states", () => {
    render(<ModelingExportPrerequisites prerequisites={[
      { label: "Processing Output", status: "stale", detail: "Loaded output differs from the session revision" },
      { label: "Server provenance proof", status: "not-supported", detail: "API contract unavailable" },
    ]} />);

    expect(screen.getAllByText("stale").length).toBeGreaterThan(0);
    expect(screen.getByText(/Loaded output differs/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /preview|deliver|create/i })).toBeNull();
  });
});
