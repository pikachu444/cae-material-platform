import { modelFamilyLabel } from "../../shared/model/engineering-labels";
import type { SolverCardRow } from "./api";

/** API source families select adapters; model content selects the product grouping. */
export function cardModelFamily(row: Pick<SolverCardRow, "family" | "neutralFamily">): string {
  if (row.family === "unsupported") return "미지원";
  return modelFamilyLabel(row.neutralFamily ?? row.family);
}
