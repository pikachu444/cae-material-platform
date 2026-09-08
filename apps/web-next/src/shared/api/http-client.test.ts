describe("connected HTTP transport", () => {
  beforeEach(() => {
    vi.resetModules();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("does not mint an identity for an ordinary read", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ items: [] }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { requestJson } = await import("./http-client");

    await expect(requestJson<{ items: unknown[] }>("/api/v1/materials")).resolves.toEqual({ items: [] });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/materials");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).headers).not.toHaveProperty("Authorization");
  });

  it("deduplicates explicit local-demo sign-in and keeps the bearer after a 403", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes("demo-identity/token")) return new Response(JSON.stringify({ access_token: "demo-token" }), { status: 200 });
      if (path.endsWith("/protected")) return new Response(JSON.stringify({ detail: "forbidden" }), { status: 403 });
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { connectDemoSession, requestJson } = await import("./http-client");

    await expect(Promise.all([connectDemoSession("reviewer"), connectDemoSession("reviewer")])).resolves.toEqual([true, true]);
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("demo-identity/token"))).toHaveLength(1);
    await expect(requestJson("/protected")).rejects.toMatchObject({ status: 403 });
    await expect(requestJson("/after-forbidden")).resolves.toEqual({ ok: true });
    const afterForbidden = fetchMock.mock.calls.at(-1)?.[1] as RequestInit;
    expect(new Headers(afterForbidden.headers).get("Authorization")).toBe("Bearer demo-token");
  });
});
