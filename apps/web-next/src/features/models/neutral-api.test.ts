import { beforeEach, describe, expect, it, vi } from "vitest";
import { requestJson, requestSemanticJson } from "../../shared/api/http-client";
import { readExactNeutralMaterial } from "./neutral-api";

vi.mock("../../shared/api/http-client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/http-client")>("../../shared/api/http-client");
  return { ...actual, requestJson: vi.fn(), requestSemanticJson: vi.fn() };
});


const neutralId = "neutral-1";
const revisionId = "neutral-revision-1";
const materialId = "material-1";
const document = {
  document_type: "cmp.neutral-material",
  document_id: neutralId,
  content_sha256: "semantic-hash",
  sources: {
    material: { id: materialId, revision_id: "material-revision-1" },
    datasets: [{ dataset: { id: "source-1", revision_id: "source-revision-1" }, role: "processing_input" }],
  },
  candidate_selection: { processing_output: { id: "output-1", revision_id: "output-revision-1" }, selected_series: "stress.hardening.selected" },
  material_model_ir: { model: { id: neutralId, revision_id: revisionId }, model_family: "isotropic_tabulated_plasticity" },
};

describe("exact Neutral Material adapter", () => {
  beforeEach(() => {
    vi.mocked(requestJson).mockReset();
    vi.mocked(requestSemanticJson).mockReset();
  });

  it("uses the candidate relation and validates the semantic document hash", async () => {
    vi.mocked(requestJson).mockResolvedValue({ items: [{ source: { kind: "neutral_material_json", artifact_id: "artifact-1", neutral_material_id: neutralId, neutral_material_revision_id: revisionId }, source_sha256: "sha256:artifact-hash", label: "Neutral JSON" }] });
    vi.mocked(requestSemanticJson).mockResolvedValue({ value: document, semanticSha256: "semantic-hash", headers: new Headers({ "X-Neutral-Material-ID": neutralId, "X-Neutral-Material-Revision-ID": revisionId }) });

    const result = await readExactNeutralMaterial(materialId, neutralId, revisionId);

    expect(result.sourceOutput).toEqual({ id: "output-1", revisionId: "output-revision-1" });
    expect(result.sourceTestData).toEqual({ id: "source-1", revisionId: "source-revision-1" });
    expect(result.semanticSha256).toBe("semantic-hash");
    expect(result.candidate.sourceSha256).toBe("artifact-hash");
    expect(result.candidate.label).toBe("Neutral JSON");
    expect(vi.mocked(requestSemanticJson)).toHaveBeenCalledWith(`/api/v1/neutral-materials/${neutralId}/revisions/${revisionId}/download`, { signal: undefined });
  });

  it("fails closed when identity headers do not match the exact URL", async () => {
    vi.mocked(requestJson).mockResolvedValue({ items: [{ source: { kind: "neutral_material_json", artifact_id: "artifact-1", neutral_material_id: neutralId, neutral_material_revision_id: revisionId, source_sha256: "artifact-hash" } }] });
    vi.mocked(requestSemanticJson).mockResolvedValue({ value: document, semanticSha256: "semantic-hash", headers: new Headers({ "X-Neutral-Material-ID": "other", "X-Neutral-Material-Revision-ID": revisionId }) });

    await expect(readExactNeutralMaterial(materialId, neutralId, revisionId)).rejects.toMatchObject({ code: "NEUTRAL_REVISION_MISMATCH" });
  });

  it("reads a card's exact neutral source without a material or candidate-list dependency", async () => {
    vi.mocked(requestSemanticJson).mockResolvedValue({ value: document, semanticSha256: "semantic-hash", headers: new Headers({ "X-Neutral-Material-ID": neutralId, "X-Neutral-Material-Revision-ID": revisionId }) });
    const result = await readExactNeutralMaterial(undefined, neutralId, revisionId);
    expect(requestJson).not.toHaveBeenCalled();
    expect(result.materialId).toBe(materialId);
    expect(result.sourceTestData?.revisionId).toBe("source-revision-1");
  });
});
