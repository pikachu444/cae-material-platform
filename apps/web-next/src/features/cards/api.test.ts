import { beforeEach, describe, expect, it, vi } from "vitest";
import { requestBytes, requestJson, requestText } from "../../shared/api/http-client";
import { readCard, readCardByIdentity, type SolverCardRow } from "./api";

vi.mock("../../shared/api/http-client", async () => {
  const actual = await vi.importActual<typeof import("../../shared/api/http-client")>("../../shared/api/http-client");
  return { ...actual, requestBytes: vi.fn(), requestJson: vi.fn(), requestText: vi.fn() };
});

const row: SolverCardRow = {
  id: "32e16173-aaa1-4a29-a079-3c2eb03a4276",
  revisionId: "d5343207-3ff3-48db-847b-47c7ce321c1d",
  revisionNo: 1,
  family: "tabulated_plasticity",
  title: "Primary tabulated card",
  schemaId: "cmp.tabulated-plasticity-card",
  contentSha256: "content-hash",
  cardSha256: "native-hash",
  materialId: "material-id",
  materialModelId: "a711f7dc-2cc8-43ec-bc75-d7770a2bdceb",
  materialModelRevisionId: "e939c398-e1b3-4f9c-983a-a9674d7024f0",
  neutralMaterialId: null,
  target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
  solverMaterialId: 1,
  exporterId: "exporter",
  modelFamily: "tabulated",
  neutralFamily: null,
  unsupportedReason: null,
  links: { self: "/api/v1/elastoplastic-solver-cards/32e16173-aaa1-4a29-a079-3c2eb03a4276", preview: "/api/v1/elastoplastic-solver-cards/32e16173-aaa1-4a29-a079-3c2eb03a4276/preview", download: "/api/v1/elastoplastic-solver-cards/32e16173-aaa1-4a29-a079-3c2eb03a4276/download" },
};

const payload = (revisionId = row.revisionId, cardId = row.id) => ({ solver_card_id: cardId, current_revision: { id: revisionId, revision_no: 1, schema_id: row.schemaId, content_hash: row.contentSha256, content: { card_title: row.title, card_sha256: row.cardSha256, target: row.target, solver_material_id: 1 } } });

describe("connected Solver Card identity reads", () => {
  beforeEach(() => { vi.mocked(requestJson).mockReset(); vi.mocked(requestText).mockReset(); vi.mocked(requestBytes).mockReset(); });

  it("fails closed when the aggregate or revision does not match the pinned URL", async () => {
    vi.mocked(requestJson).mockResolvedValue(payload(row.revisionId, "different-card"));
    await expect(readCard(row)).rejects.toMatchObject({ code: "CARD_IDENTITY_MISMATCH" });
    vi.mocked(requestJson).mockResolvedValue(payload("different-revision"));
    await expect(readCard(row)).rejects.toMatchObject({ code: "CARD_REVISION_MISMATCH" });
  });

  it("uses the explicit family route and revision pin for a direct card URL", async () => {
    vi.mocked(requestJson).mockResolvedValue(payload());
    vi.mocked(requestText).mockResolvedValue({ text: "/MAT/LAW\n", contentType: "text/plain", fileName: "card.rad" });
    const detail = await readCardByIdentity(row.id, row.revisionId, "tabulated_plasticity");
    expect(detail.nativeText).toContain("/MAT/LAW");
    expect(vi.mocked(requestJson).mock.calls[0]?.[0]).toContain("/elastoplastic-solver-cards/");
    expect(vi.mocked(requestJson).mock.calls[0]?.[0]).toContain(`revision_id=${row.revisionId}`);
  });

  it("rejects a content or native hash substitution", async () => {
    vi.mocked(requestJson).mockResolvedValue({ ...payload(), current_revision: { ...payload().current_revision, content_hash: "other" } });
    await expect(readCard(row)).rejects.toMatchObject({ code: "CARD_CONTENT_HASH_MISMATCH" });
    vi.mocked(requestJson).mockResolvedValue({ ...payload(), current_revision: { ...payload().current_revision, content: { ...payload().current_revision.content, card_sha256: "other" } } });
    await expect(readCard(row)).rejects.toMatchObject({ code: "CARD_ARTIFACT_HASH_MISMATCH" });
  });
});
