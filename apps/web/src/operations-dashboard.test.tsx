import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { OperationsDashboard } from "./operations-dashboard";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("renders only the bounded operational snapshot and refreshes it", async () => {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => ({
      service: "cmp-api",
      version: "0.32.0",
      started_at: "2026-07-16T00:00:00Z",
      observed_at: "2026-07-16T00:01:00Z",
      active_requests: 1,
      request_count: 12,
      error_count: 1,
      series: [{
        method: "GET",
        route: "/api/v1/materials/{material_id}",
        status_family: "2xx",
        request_count: 12,
        error_count: 0,
        duration_sum_ms: 240,
        p95_upper_bound_ms: 50,
      }],
    }),
  } as Response);
  vi.stubGlobal("fetch", fetchMock);

  render(<OperationsDashboard config={{ baseUrl: "/api/v1", accessToken: "audit-token" }} />);

  expect(await screen.findByText("/api/v1/materials/{material_id}")).toBeTruthy();
  expect(screen.getAllByText("12")).toHaveLength(2);
  expect(screen.getByText(/never exposes URLs/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Refresh snapshot" }));
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
