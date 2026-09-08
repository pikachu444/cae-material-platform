import { fireEvent, render, screen, within } from "@testing-library/react";
import { vi } from "vitest";
import type { TestDataRow } from "../api";
import { TestDataTree } from "./TestDataTree";

it("keeps same-named specimens from distinct saved material states separate and selects the exact test", () => {
  const first: TestDataRow = {
    id: "test-a", revisionId: "input-a", documentKey: "인장 시험 A", materialId: "material",
    materialStateId: "state-a", materialStateRevisionId: "state-a-pin", specimenId: "시편 1",
    materialMaker: "", materialGrade: "DP780", lotBatch: null, testDate: "2026-09-08", operator: "",
    laboratory: "", method: "인장", pointCount: 12, channels: [],
    revision: { id: "input-a", revision_no: 1, schema_id: "test", schema_version: "1", content_hash: "a", created_at: "2026-09-08" },
  };
  const second = { ...first, id: "test-b", revisionId: "input-b", documentKey: "인장 시험 B", materialStateId: "state-b", materialStateRevisionId: "state-b-pin" };
  const onSelect = vi.fn();
  render(<TestDataTree rows={[first, second]} selectedId={first.id} onSelect={onSelect} />);
  const groups = screen.getAllByText("시편 1").map(name => name.closest("details")!);
  expect(groups).toHaveLength(2);
  expect(within(groups[0]).queryByText(second.documentKey)).toBeNull();
  fireEvent.click(groups[1].querySelector("summary")!);
  fireEvent.click(screen.getByRole("button", { name: second.documentKey }));
  expect(onSelect).toHaveBeenCalledWith(second);
});
