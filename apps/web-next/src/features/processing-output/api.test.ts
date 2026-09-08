import { beforeEach, describe, expect, it, vi } from "vitest";
import { requestBytes, requestJson } from "../../shared/api/http-client";
import { readProcessingOutput } from "./api";

vi.mock("../../shared/api/http-client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/http-client")>("../../shared/api/http-client");
  return { ...actual, requestBytes: vi.fn(), requestJson: vi.fn() };
});

const outputId = "1f9e7596-7f7b-4aab-9eb5-32e3b26206f6";
const revisionId = "26087e6f-d1af-42c7-a5b2-6cafe973b190";

const response = () => ({ processing_output_id: outputId, current_revision: { id: revisionId, revision_no: 1, schema_id: "cmp.processing-output", schema_version: "1.5.0", content_hash: "output-revision", created_at: "2026-01-01T00:00:00Z" }, label: "Primary processing output", source_document: { aggregate_id: "41d6520e-5385-468f-b178-9356b870bfa8", revision_id: "847bf1b2-302e-40b0-8e9c-1580630d98f4" }, source_document_sha256: "source-hash", mapping_profile: null, mapping_profile_sha256: null, steps: [], independent_quantity: "strain.true_plastic", stage_count: 1, final_point_count: 3, output_sha256: "output-hash", export_provenance: null });

describe("connected Processing Output exact reads", () => {
  beforeEach(() => { vi.mocked(requestJson).mockReset(); vi.mocked(requestBytes).mockReset(); });

  it("rejects a revision substitution and does not replace it with current", async () => {
    vi.mocked(requestJson).mockResolvedValue({ ...response(), current_revision: { ...response().current_revision, id: "current-but-not-requested" } });
    vi.mocked(requestBytes).mockResolvedValue({ bytes: new TextEncoder().encode(JSON.stringify({ output_id: outputId })), sha256: "", contentType: "application/json", fileName: "output.json" });
    await expect(readProcessingOutput(outputId, revisionId)).rejects.toMatchObject({ code: "PROCESSING_OUTPUT_REVISION_MISMATCH" });
  });

  it("keeps the declared curve definition and actual x/y arrays together", async () => {
    vi.mocked(requestJson).mockResolvedValue(response());
    vi.mocked(requestBytes).mockResolvedValue({ bytes: new TextEncoder().encode(JSON.stringify({ output_id: outputId, result: { stages: [{ ordinal: 0, method_id: "mapping", point_count: 3, curve_definition: { definition_version: "1.0.0", channels: [{ key: "strain.true_plastic", label: "True plastic strain", quantity_semantics: "strain.true_plastic", axis_role: "independent", unit_contract: "common", dimension: "strain", original_units: [{ unit: "1", scale_to_normalized: "1", offset_to_normalized: "0" }], normalized_unit: "1", display_unit: "1", display_scale: "1", display_offset: "0", value_basis: "derived" }, { key: "stress.hardening.selected", label: "Selected hardening stress", quantity_semantics: "stress.hardening.selected", axis_role: "dependent", unit_contract: "common", dimension: "force_per_area", original_units: [{ unit: "Pa", scale_to_normalized: "1", offset_to_normalized: "0" }], normalized_unit: "Pa", display_unit: "MPa", display_scale: "0.000001", display_offset: "0", value_basis: "derived" }], deviations: [] }, series: [{ quantity: "strain.true_plastic", unit: "1", values: [0, 0.01, 0.1] }, { quantity: "stress.hardening.selected", unit: "Pa", values: [1000000, null, 3000000] }] }] } })), sha256: "", contentType: "application/json", fileName: "output.json" });
    const detail = await readProcessingOutput(outputId, revisionId);
    expect(detail.stages[0]?.curveDefinition?.channels[0]?.key).toBe("strain.true_plastic");
    expect(detail.stages[0]?.curveSeries?.channels[1]?.values).toEqual([1000000, null, 3000000]);
    expect(detail.stages[0]?.curveDefinition?.channels[1]?.display_scale).toBe("0.000001");
  });
});
