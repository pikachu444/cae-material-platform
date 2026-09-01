import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProcessedLinearViscoelasticFitInput } from "../model/linear-viscoelastic-calibration-contracts";
import { useLinearViscoelasticFitInput } from "./use-linear-viscoelastic-fit-input";

const config = { baseUrl: "/api/v1", accessToken: "token" };

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

function fitInput(coordinate: number): ProcessedLinearViscoelasticFitInput {
  return {
    mode: "dma_frequency_master_curve",
    coordinate_quantity: "frequency.angular.reduced",
    coordinate_unit: "rad/s",
    response_channels: [
      { channel: "dma_storage", quantity: "mechanics.modulus.storage", unit: "Pa" },
      { channel: "dma_loss", quantity: "mechanics.modulus.loss", unit: "Pa" },
    ],
    reference_temperature_k: "313.15",
    rows: [{
      ordinal: 0,
      coordinate,
      storage_modulus_pa: 3_000_000,
      loss_modulus_pa: 100_000,
      partition: "CALIBRATION",
      exclusion_reason: null,
    }],
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((fulfil) => { resolve = fulfil; });
  return { promise, resolve };
}

afterEach(() => vi.restoreAllMocks());

describe("useLinearViscoelasticFitInput", () => {
  it("keeps only the response for the currently pinned Processing Output revision", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => first.promise)
      .mockImplementationOnce(() => second.promise);
    const { result, rerender } = renderHook(
      ({ source }) => useLinearViscoelasticFitInput(config, source),
      { initialProps: { source: { id: "output-a", revisionId: "revision-a" } } },
    );

    rerender({ source: { id: "output-b", revisionId: "revision-b" } });
    await act(async () => second.resolve(response(fitInput(2))));
    await waitFor(() => expect(result.current.data?.rows[0].coordinate).toBe(2));
    await act(async () => first.resolve(response(fitInput(1))));
    await Promise.resolve();

    expect(result.current.data?.rows[0].coordinate).toBe(2);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      "/api/v1/processing-outputs/output-a/revisions/revision-a/linear-viscoelastic-fit-input",
      "/api/v1/processing-outputs/output-b/revisions/revision-b/linear-viscoelastic-fit-input",
    ]);
  });

  it("reports a failed exact read without falling back to raw Test Data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ detail: "Exact output revision is unavailable." }, 404));
    const { result } = renderHook(() => useLinearViscoelasticFitInput(config, {
      id: "missing-output",
      revisionId: "missing-revision",
    }));

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toContain("Exact output revision is unavailable");
  });
});
