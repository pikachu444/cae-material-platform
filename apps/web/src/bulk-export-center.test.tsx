import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BulkExportCenter } from "./bulk-export-center";

const materialId = "10000000-0000-4000-8000-000000000001";
const revisionId = "10000000-0000-4000-8000-000000000002";
const modelId = "10000000-0000-4000-8000-000000000003";
const modelRevisionId = "10000000-0000-4000-8000-000000000004";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const material = {
  material_id: materialId,
  current_revision: {
    id: revisionId,
    aggregate_id: materialId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:material:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-16T00:00:00Z",
    created_by: materialId,
    change_reason: "fixture",
    organization_id: materialId,
    project_id: revisionId,
    classification: "internal",
    lifecycle_state: "draft",
    content: {
      name: "DP780 production trial",
      material_code: "DP780",
      material_family: "steel",
      description: null,
      material_class: "metal",
    },
    provenance: {
      entity_type: "catalog.material.revision",
      reference_type: "catalog.material.revision",
      revision_id: revisionId,
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-07-16T00:00:00Z",
      recorded_by: materialId,
    },
  },
  links: {},
};

const source = {
  kind: "model_ir_json",
  raw_asset_id: null,
  artifact_id: null,
  dataset_id: null,
  dataset_revision_id: null,
  material_model_id: modelId,
  material_model_revision_id: modelRevisionId,
  solver_card_id: null,
  solver_card_revision_id: null,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("BulkExportCenter", () => {
  it("discovers exact revisions and sends an explicit immutable selection", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes("/materials?")) return response({ items: [material] });
      if (url.endsWith(`/bulk-export-candidates?material_id=${materialId}`)) {
        return response({
          items: [{
            source,
            classification: "internal",
            source_sha256: `sha256:${"b".repeat(64)}`,
            source_size_bytes: 512,
            media_type: "application/json",
            default_archive_path: `models/${modelId}/${modelRevisionId}/ir.json`,
            label: "Reference tabulated plasticity IR r2",
          }],
        });
      }
      if (url.endsWith("/export-selections") && init?.method === "POST") {
        return response({ export_selection_id: materialId });
      }
      if (url.endsWith("/export-jobs") && init?.method === "POST") {
        return response({
          export_job_id: modelId,
          state: "succeeded",
          bundle_id: revisionId,
        });
      }
      if (url.endsWith("/export-jobs")) return response({ items: [] });
      if (url.endsWith("/export-bundles")) return response({ items: [] });
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BulkExportCenter
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByText("Reference tabulated plasticity IR r2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Select all" }));
    fireEvent.click(screen.getByRole("button", { name: "Create immutable ZIP" }));
    expect(await screen.findByText(/assembled from 1 exact revisions/)).toBeTruthy();

    const selectionCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/export-selections"));
    expect(selectionCall).toBeTruthy();
    expect(JSON.parse(String(selectionCall?.[1]?.body))).toMatchObject({
      classification: "internal",
      members: [{ ordinal: 1, required: true, source }],
    });
  });

  it("keeps committed output visible while a later Bundle step awaits reconciliation", async () => {
    const digest = `sha256:${"c".repeat(64)}`;
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.includes("/materials?")) return response({ items: [material] });
      if (url.endsWith(`/bulk-export-candidates?material_id=${materialId}`)) {
        return response({ items: [] });
      }
      if (url.endsWith("/export-bundles")) return response({ items: [] });
      if (url.endsWith("/export-jobs")) {
        return response({
          items: [{
            export_job_id: modelId,
            classification: "internal",
            export_selection_id: materialId,
            export_selection_revision_id: revisionId,
            state: "reconciliation_required",
            attempt_count: 1,
            bundle_id: null,
            failure_code: "committed_output_pending",
            failure_detail: "Bundle projection will be retried",
            submitted_at: "2026-07-16T00:00:00Z",
            submitted_by: materialId,
            started_at: "2026-07-16T00:00:01Z",
            completed_at: "2026-07-16T00:00:02Z",
            lease_expires_at: null,
            heartbeat_at: null,
            committed_output: {
              output_commit_id: revisionId,
              archive_artifact_id: modelRevisionId,
              archive_sha256: digest,
              archive_size_bytes: 2_097_152,
              manifest_sha256: `sha256:${"d".repeat(64)}`,
              committed_at: "2026-07-16T00:00:02Z",
              committed_by: materialId,
            },
            links: {},
          }],
        });
      }
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BulkExportCenter
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByText("output preserved")).toBeTruthy();
    expect(screen.getByText(digest)).toBeTruthy();
    expect(screen.getByText(/Bundle projection will be retried/)).toBeTruthy();
  });

  it("shows the active worker heartbeat and deterministic recovery deadline", async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.includes("/materials?")) return response({ items: [material] });
      if (url.endsWith(`/bulk-export-candidates?material_id=${materialId}`)) {
        return response({ items: [] });
      }
      if (url.endsWith("/export-bundles")) return response({ items: [] });
      if (url.endsWith("/export-jobs")) {
        return response({
          items: [{
            export_job_id: modelId,
            classification: "internal",
            export_selection_id: materialId,
            export_selection_revision_id: revisionId,
            state: "running",
            attempt_count: 2,
            bundle_id: null,
            failure_code: null,
            failure_detail: null,
            submitted_at: "2026-07-16T00:00:00Z",
            submitted_by: materialId,
            started_at: "2026-07-16T00:00:01Z",
            completed_at: null,
            lease_expires_at: "2026-07-16T00:02:15Z",
            heartbeat_at: "2026-07-16T00:02:00Z",
            committed_output: null,
            links: {},
          }],
        });
      }
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <BulkExportCenter
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByText(/Worker heartbeat/)).toBeTruthy();
    expect(screen.getByText(/recoverable after/)).toBeTruthy();
    expect(screen.getByText(/attempt 2/)).toBeTruthy();
  });
});
