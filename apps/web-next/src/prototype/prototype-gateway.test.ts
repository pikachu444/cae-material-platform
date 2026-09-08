import { createPrototypeReaderGateway } from "./prototype-gateway";
import { requestScopeKey } from "../shared/api/reader-gateway";

const params = { q: "", kind: "all" as const, sort: "title" as const, direction: "desc" as const, offset: 0, pageSize: 50, scenario: "normal" as const };

describe("prototype reader gateway", () => {
  it("pages through ordinary IDs and resolves a selected curve separately", async () => {
    const gateway = createPrototypeReaderGateway();
    const result = await gateway.searchTestData(params);
    expect(result.rows).toHaveLength(50);
    expect(result.total).toBe(10_000);
    expect(result.rows.every((row) => row.curve === undefined)).toBe(true);
    const selected = await gateway.getTestData("td-00042", { scenario: "normal" });
    expect(selected.id).toBe("td-00042");
    expect(selected.curvePreview?.returned_point_count).toBe(1_000);
    expect(selected.cardIds).toEqual(["card-00001"]);
  });

  it("keeps same-ID metadata edits in memory and preserves links", async () => {
    const gateway = createPrototypeReaderGateway();
    const edited = await gateway.patchDisplayMetadata("test-data", "td-00042", { title: "Renamed reference", description: "Draft applied for this prototype session" });
    expect(edited.id).toBe("td-00042");
    expect(edited.title).toBe("Renamed reference");
    expect((edited as { cardIds: string[] }).cardIds).toEqual(["card-00001"]);
    const readback = await gateway.getTestData("td-00042", { scenario: "normal" });
    expect(readback.title).toBe("Renamed reference");
    expect(readback.cardIds).toEqual(["card-00001"]);
  });

  it("aborts late requests and reports explicit scenario failures", async () => {
    const gateway = createPrototypeReaderGateway();
    const controller = new AbortController();
    const pending = gateway.searchTestData(params, controller.signal);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    await expect(gateway.searchTestData({ ...params, scenario: "error" })).rejects.toMatchObject({ status: 503 });
    await expect(gateway.getTestData("missing-id", { scenario: "normal" })).rejects.toMatchObject({ status: 404 });
  });

  it("builds scope keys from identity and access context without bearer tokens", () => {
    const key = requestScopeKey("prototype", { actorID: "prototype-reviewer", orgID: "cmp", projectID: "rd01", effectiveAccessFingerprint: "dataset-read+export-read", authEpoch: 1 });
    expect(key).toContain("|prototype-reviewer|");
    expect(key).toContain("|dataset-read+export-read|");
    expect(key).not.toContain("token");
  });
});
