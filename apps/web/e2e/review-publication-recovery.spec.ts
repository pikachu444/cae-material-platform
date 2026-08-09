import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const apiPath = (path: string): string => `${webUrl}/api/v1${path}`;

type JsonObject = Record<string, unknown>;

interface Revision {
  id: string;
  content_hash: string;
  classification: string;
  lifecycle_state: string;
  revision_no: number;
  content: JsonObject;
}

interface Binding {
  binding_id?: string;
  record_id: string;
  record_revision_id: string;
  kind: string;
  object_id: string;
  revision_id: string;
}

interface CatalogRecord {
  record_id: string;
  table_id: string;
  current_revision: Revision;
  domain_binding?: Binding | null;
  domain_bindings?: Binding[];
}

interface CatalogTable {
  table_id: string;
  current_revision: { content: JsonObject };
}

interface ReviewRequest {
  review_request_id: string;
  aggregate_type: string;
  aggregate_id: string;
  revision_id: string;
  manifest_sha256: string;
  lifecycle_state: string;
  decision: { decision: string } | null;
}

interface SearchResponse {
  items: CatalogRecord[];
  total_count: number;
}

interface LinkType {
  link_type_id: string;
  current_revision: Revision & { content: JsonObject };
}

interface RecordLinkContent {
  link_type_id: string;
  link_type_revision_id: string;
  source_record_id: string;
  source_record_revision_id: string;
  target_record_id: string;
  target_record_revision_id: string;
  active: boolean;
  note?: string | null;
}

interface RecordLink {
  record_link_id: string;
  current_revision: Revision & { content: RecordLinkContent };
}

interface WorkflowGraph {
  root: { record_id: string; record_revision_id: string };
  nodes: JsonObject[];
  links: JsonObject[];
}

function revisionEtag(revision: Pick<Revision, "revision_no" | "content_hash">): string {
  return `"revision:${revision.revision_no}:sha256:${revision.content_hash}"`;
}

function requiredString(value: unknown, label: string): string {
  expect(typeof value, `${label} should be a string`).toBe("string");
  return value as string;
}

function requiredObject(value: unknown, label: string): JsonObject {
  expect(value, `${label} should be an object`).toBeTruthy();
  expect(Array.isArray(value), `${label} should not be an array`).toBe(false);
  return value as JsonObject;
}

async function callJson<T>(
  request: APIRequestContext,
  token: string,
  path: string,
  options: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
): Promise<{ data: T; headers: Record<string, string> }> {
  const response = await request.fetch(apiPath(path), {
    method: options.method ?? "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(options.headers ?? {}),
    },
    data: options.body,
  });
  const raw = await response.text();
  expect(response.ok(), `${options.method ?? "GET"} ${path}: ${raw}`).toBeTruthy();
  return {
    data: (raw ? JSON.parse(raw) : {}) as T,
    headers: response.headers(),
  };
}

async function expectNotFound(request: APIRequestContext, token: string, path: string): Promise<void> {
  const response = await request.get(apiPath(path), { headers: { Authorization: `Bearer ${token}` } });
  const raw = await response.text();
  expect(response.status(), `GET ${path}: ${raw}`).toBe(404);
}

async function issueToken(request: APIRequestContext, persona: "administrator" | "user" | "reviewer"): Promise<string> {
  const response = await request.get(`${apiPath("/demo-identity/token")}?persona=${persona}`);
  const raw = await response.text();
  expect(response.ok(), `demo identity ${persona}: ${raw}`).toBeTruthy();
  return requiredString((JSON.parse(raw) as JsonObject).access_token, `${persona} access token`);
}

async function installToken(page: Page, accessToken: string): Promise<void> {
  await page.addInitScript(
    ({ token }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken: token }),
      );
    },
    { token: accessToken },
  );
}

async function expectMaterialsReady(page: Page): Promise<void> {
  await expect(page.locator(".materials-results")).toHaveAttribute("aria-busy", "false", { timeout: 20_000 });
  await expect(page.getByText("Checking…", { exact: true })).toHaveCount(0, { timeout: 20_000 });
}

async function selectExactRecordEditor(
  page: Page,
  description: string,
  revisionNo: number,
): Promise<void> {
  const resultButton = page
    .locator(".record-result-table .record-result")
    .filter({ hasText: "DP780 synthetic reference steel" })
    .filter({ hasText: "CMP-DEMO-DP780" });
  await expect(resultButton, "current DP780 Material Record result").toBeVisible({ timeout: 20_000 });
  await expect(resultButton).toContainText(`r${revisionNo}`);
  await resultButton.click();
  await expect(resultButton).toHaveClass(/active/, { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: `Edit revision ${revisionNo + 1}`, exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel("Record code")).toHaveValue("CMP-DEMO-DP780");
  await expect(page.getByRole("textbox", { name: "Description", exact: true })).toHaveValue(description);
}

async function ensureApprovedCard(
  request: APIRequestContext,
  administratorToken: string,
  reviewerToken: string,
  card: CatalogRecord,
  runId: string,
): Promise<void> {
  const binding = (card.domain_bindings ?? (card.domain_binding ? [card.domain_binding] : [])).find(
    (candidate) => candidate.kind === "neutral_solver_card",
  );
  expect(binding, `card ${card.record_id} has an exact Neutral Solver Card binding`).toBeTruthy();
  const cardObject = binding!.object_id;
  const cardRevision = binding!.revision_id;
  const current = await callJson<JsonObject>(request, administratorToken, `/neutral-solver-cards/${cardObject}`);
  const currentRevision = requiredObject(current.data.current_revision, "card current revision") as unknown as Revision;
  const requests = await callJson<{ items: ReviewRequest[] }>(
    request,
    administratorToken,
    `/review-requests?aggregate_type=exporting.neutral_solver_card&aggregate_id=${cardObject}&revision_id=${cardRevision}&limit=20`,
  );
  let review = requests.data.items.find((item) => item.aggregate_type === "exporting.neutral_solver_card" && item.revision_id === cardRevision);
  if (review?.decision?.decision === "approved") return;
  if (!review) {
    review = (
      await callJson<ReviewRequest>(request, administratorToken, "/review-requests", {
        method: "POST",
        body: {
          aggregate_type: "exporting.neutral_solver_card",
          aggregate_id: cardObject,
          revision_id: cardRevision,
          classification: currentRevision.classification,
          manifest_sha256: currentRevision.content_hash,
          reason: `Prepare exact card for review publication recovery ${runId}`,
        },
      })
    ).data;
  }
  expect(review.decision, "card review should still be pending before setup approval").toBeNull();
  await callJson<ReviewRequest>(request, reviewerToken, `/review-requests/${review.review_request_id}/decisions`, {
    method: "POST",
    body: {
      expected_manifest_sha256: review.manifest_sha256,
      decision: "approved",
      reason: `Exact card prerequisite approved for review publication recovery ${runId}`,
    },
  });
}

test("User submits an exact review, Reviewer publishes Materials, and recovery preserves revision history", async ({ page, request, browser }) => {
  test.setTimeout(120_000);
  const [administratorToken, userToken, reviewerToken] = await Promise.all([
    issueToken(request, "administrator"),
    issueToken(request, "user"),
    issueToken(request, "reviewer"),
  ]);
  const runId = `e2e-review-${Date.now()}`;

  const tables = await callJson<{ items: CatalogTable[] }>(request, administratorToken, "/catalog/tables?limit=50");
  const table = tables.data.items.find((candidate) => candidate.current_revision.content.key === "demo_material_records");
  expect(table, "clean-demo Material Records table").toBeTruthy();
  const tableId = table!.table_id;

  const materialSearch = await callJson<SearchResponse>(request, administratorToken, "/catalog/records:search", {
    method: "POST",
    body: {
      table_id: tableId,
      text: "CMP-DEMO-DP780",
      domain_binding_kind: "material",
      published_only: false,
      limit: 100,
    },
  });
  const sourceRecord = materialSearch.data.items.find(
    (candidate) => candidate.domain_binding?.kind === "material" && candidate.current_revision.content.external_key === "CMP-DEMO-DP780",
  );
  expect(sourceRecord, "clean-demo DP780 Material Record").toBeTruthy();

  const neutralSearch = await callJson<SearchResponse>(request, administratorToken, "/catalog/records:search", {
    method: "POST",
    body: {
      table_id: tableId,
      text: "CMP-DEMO-DP780-NEUTRAL",
      domain_binding_kind: "neutral_material",
      published_only: false,
      limit: 20,
    },
  });
  const neutralRecord = neutralSearch.data.items.find((candidate) => candidate.domain_binding?.kind === "neutral_material");
  expect(neutralRecord, "clean-demo exact Neutral Material record").toBeTruthy();
  const neutralBinding = neutralRecord!.domain_binding!;

  const cardSearch = await callJson<SearchResponse>(request, administratorToken, "/catalog/records:search", {
    method: "POST",
    body: {
      table_id: tableId,
      text: "Abaqus",
      domain_binding_kind: "neutral_solver_card",
      published_only: false,
      limit: 20,
    },
  });
  const cardRecord = cardSearch.data.items.find((candidate) => /Abaqus/i.test(String(candidate.current_revision.content.name)));
  expect(cardRecord, "clean-demo Abaqus card record").toBeTruthy();
  await ensureApprovedCard(request, administratorToken, reviewerToken, cardRecord!, runId);
  const cardBinding = cardRecord!.domain_binding!;

  const neutralDetail = await callJson<CatalogRecord>(request, administratorToken, `/catalog/records/${neutralRecord!.record_id}`);
  const neutralEtag = neutralDetail.headers.etag;
  expect(neutralEtag, "Neutral Material record ETag").toBeTruthy();
  const neutralContent = requiredObject(neutralDetail.data.current_revision.content, "Neutral Material record content");
  const neutralDescription = `${String(neutralContent.description ?? "Exact governed Neutral Material workflow node.")} · ${runId}`;
  const neutralRevision = await callJson<CatalogRecord>(request, administratorToken, `/catalog/records/${neutralRecord!.record_id}/revisions`, {
    method: "POST",
    headers: { "If-Match": neutralEtag },
    body: {
      content: { ...neutralContent, description: neutralDescription },
      change_reason: `Create exact Neutral Material review prerequisite revision ${runId}`,
    },
  });
  const neutralRevisionId = neutralRevision.data.current_revision.id;
  await callJson<Binding>(request, administratorToken, `/catalog/records/${neutralRecord!.record_id}/revisions/${neutralRevisionId}/domain-binding`, {
    method: "POST",
    body: { kind: "neutral_material", object_id: neutralBinding.object_id, revision_id: neutralBinding.revision_id },
  });

  const neutralWorkflowPath = `/catalog/workflow-explorer/${neutralRecord!.record_id}/revisions/${neutralRevisionId}?depth=3&published_only=true`;
  await expectNotFound(request, userToken, neutralWorkflowPath);
  const neutralReviewReason = `Please review exact Neutral Material record ${runId}`;
  const neutralReview = await callJson<ReviewRequest>(request, userToken, "/review-requests", {
    method: "POST",
    body: {
      aggregate_type: "catalog.configurable_record",
      aggregate_id: neutralRecord!.record_id,
      revision_id: neutralRevisionId,
      classification: neutralRevision.data.current_revision.classification,
      manifest_sha256: neutralRevision.data.current_revision.content_hash,
      reason: neutralReviewReason,
    },
  });
  expect(neutralReview.data.decision, "Neutral Material review should be pending").toBeNull();
  await callJson<ReviewRequest>(request, reviewerToken, `/review-requests/${neutralReview.data.review_request_id}/decisions`, {
    method: "POST",
    body: {
      expected_manifest_sha256: neutralReview.data.manifest_sha256,
      decision: "approved",
      reason: `Approved exact Neutral Material prerequisite ${runId}`,
    },
  });
  const publishedNeutralGraph = await callJson<WorkflowGraph>(request, userToken, neutralWorkflowPath);
  expect(publishedNeutralGraph.data.root.record_id).toBe(neutralRecord!.record_id);
  expect(publishedNeutralGraph.data.root.record_revision_id).toBe(neutralRevisionId);

  const sourceDetail = await callJson<CatalogRecord>(request, administratorToken, `/catalog/records/${sourceRecord!.record_id}`);
  const sourceEtag = sourceDetail.headers.etag;
  expect(sourceEtag, "source record ETag").toBeTruthy();
  const sourceContent = requiredObject(sourceDetail.data.current_revision.content, "source record content");
  const sourceDescription = String(sourceContent.description ?? "");
  const reviewDescription = `${sourceDescription} · ${runId}`;
  const reviewRecord = await callJson<CatalogRecord>(request, administratorToken, `/catalog/records/${sourceRecord!.record_id}/revisions`, {
    method: "POST",
    headers: { "If-Match": sourceEtag },
    body: {
      content: { ...sourceContent, description: reviewDescription },
      change_reason: `Create exact review-publication recovery revision ${runId}`,
    },
  });
  const recordId = reviewRecord.data.record_id;
  const reviewRevisionId = reviewRecord.data.current_revision.id;

  const sourceMaterialBinding = sourceRecord!.domain_binding!;
  await callJson<Binding>(request, administratorToken, `/catalog/records/${recordId}/revisions/${reviewRevisionId}/domain-binding`, {
    method: "POST",
    body: { kind: "material", object_id: sourceMaterialBinding.object_id, revision_id: sourceMaterialBinding.revision_id },
  });

  const linkTypes = await callJson<{ items: LinkType[] }>(request, administratorToken, "/catalog/link-types");
  const linkType = linkTypes.data.items[0];
  expect(linkType, "clean-demo workflow Link Type").toBeTruthy();
  const linkTypeRevision = linkType!.current_revision;
  const exactLinkContent: RecordLinkContent = {
    link_type_id: linkType!.link_type_id,
    link_type_revision_id: linkTypeRevision.id,
    source_record_id: recordId,
    source_record_revision_id: reviewRevisionId,
    target_record_id: cardRecord!.record_id,
    target_record_revision_id: cardRecord!.current_revision.id,
    active: true,
    note: `Exact card delivery link for review publication recovery ${runId}`,
  };
  const existingLinks = await callJson<{ items: RecordLink[] }>(
    request,
    administratorToken,
    `/catalog/records/${recordId}/links?include_inactive=true`,
  );
  const existingLink = existingLinks.data.items.find(
    (item) =>
      item.current_revision.content.link_type_id === linkType!.link_type_id &&
      item.current_revision.content.source_record_id === recordId &&
      item.current_revision.content.target_record_id === cardRecord!.record_id,
  );
  if (existingLink) {
    await callJson<JsonObject>(
      request,
      administratorToken,
      `/catalog/record-links/${existingLink.record_link_id}/revisions`,
      {
        method: "POST",
        headers: { "If-Match": revisionEtag(existingLink.current_revision) },
        body: {
          content: exactLinkContent,
          change_reason: `Reconnect exact card to review-publication recovery revision ${runId}`,
        },
      },
    );
  } else {
    await callJson<JsonObject>(request, administratorToken, "/catalog/record-links", {
      method: "POST",
      body: {
        classification: sourceRecord!.current_revision.classification,
        content: exactLinkContent,
        change_reason: `Connect exact card to review-publication recovery revision ${runId}`,
      },
    });
  }

  await installToken(page, userToken);
  const reviewReason = `Please review exact Materials record ${runId}`;
  await page.goto(`/catalog/records?record_id=${recordId}&revision_id=${reviewRevisionId}`);
  await selectExactRecordEditor(page, reviewDescription, reviewRecord.data.current_revision.revision_no);
  await expect(page.getByRole("button", { name: "Request review", exact: true })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Request review", exact: true }).click();
  await page.getByRole("textbox", { name: "Review request reason" }).fill(reviewReason);
  await page.getByRole("button", { name: "Send request", exact: true }).click();
  await expect(page.locator('[role="status"]').filter({ hasText: "Waiting for review" })).toBeVisible({ timeout: 20_000 });

  const reviewerContext = await browser.newContext({ baseURL: webUrl, viewport: { width: 1440, height: 900 } });
  const reviewerPage = await reviewerContext.newPage();
  try {
    await installToken(reviewerPage, reviewerToken);
    await reviewerPage.goto("/activity");
    await expect(reviewerPage.getByRole("heading", { name: "Activity", exact: true })).toBeVisible({ timeout: 20_000 });
    const reviewRow = reviewerPage.getByRole("row").filter({ hasText: reviewReason });
    await expect(reviewRow).toBeVisible({ timeout: 20_000 });
    await reviewRow.getByRole("button", { name: "Review", exact: true }).click();
    const decisionRow = reviewRow.locator("xpath=following-sibling::tr[contains(concat(' ', normalize-space(@class), ' '), ' activity-decision-row ')][1]");
    await expect(decisionRow).toBeVisible({ timeout: 20_000 });
    await decisionRow.getByText("Evidence and affected Materials", { exact: true }).click();
    await expect(decisionRow).toContainText(recordId);
    await expect(decisionRow).toContainText(reviewRevisionId);
    await decisionRow.getByRole("textbox", { name: "Review reason" }).fill(`Approved exact evidence ${runId}`);
    await decisionRow.getByRole("button", { name: "Approve", exact: true }).click();
    const recentOutcomes = reviewerPage.getByRole("tab", { name: "Recent outcomes", exact: true });
    await expect(recentOutcomes).toHaveAttribute("aria-selected", "true", { timeout: 20_000 });
    const approvedRow = reviewerPage.getByRole("row").filter({ hasText: reviewReason });
    await expect(approvedRow).toBeVisible({ timeout: 20_000 });
    await expect(approvedRow).toContainText("Approved");
  } finally {
    await reviewerContext.close();
  }

  await page.goto(`/materials?q=CMP-DEMO-DP780`);
  await expect(page.getByRole("heading", { name: "Materials", exact: true })).toBeVisible({ timeout: 20_000 });
  await expectMaterialsReady(page);
  const resultRow = page.getByRole("row").filter({ hasText: reviewDescription });
  await expect(resultRow).toBeVisible({ timeout: 20_000 });
  await resultRow.getByRole("button").click();
  await page.getByRole("button", { name: "Open datasheet", exact: true }).click();
  await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);
  await expect(page.locator(".material-detail-header")).toContainText(reviewDescription);

  await page.getByRole("tab", { name: "CAE Cards", exact: true }).click();
  const abaqusRow = page.getByRole("row").filter({ hasText: "Abaqus" }).filter({ hasText: ".inp" });
  await expect(abaqusRow).toBeVisible({ timeout: 20_000 });
  await abaqusRow.getByRole("button", { name: "Preview card", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Abaqus", exact: true })).toBeVisible({ timeout: 20_000 });
  const deliveryNotesAcknowledgement = page.getByRole("checkbox", { name: "I reviewed the delivery notes before downloading this card.", exact: true });
  await expect(deliveryNotesAcknowledgement).toBeVisible({ timeout: 20_000 });
  const downloadButton = page.getByRole("button", { name: "Download .inp", exact: true });
  await expect(downloadButton).toBeDisabled();
  await deliveryNotesAcknowledgement.check();
  await expect(downloadButton).toBeEnabled();
  const cardDownload = page.waitForEvent("download");
  await downloadButton.click();
  expect((await cardDownload).suggestedFilename()).toMatch(/\.inp$/);

  await page.goto(`/models/neutral-materials/${neutralBinding.object_id}/revisions/${neutralBinding.revision_id}`);
  await expect(page.getByRole("heading", { name: "Neutral Material", exact: true })).toBeVisible({ timeout: 20_000 });
  const neutralDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Neutral JSON", exact: true }).click();
  expect((await neutralDownload).suggestedFilename()).toMatch(/\.json$/);

  const latestDetail = await callJson<CatalogRecord>(request, administratorToken, `/catalog/records/${recordId}`);
  const latestEtag = latestDetail.headers.etag;
  expect(latestEtag, "published record ETag before upstream revision").toBeTruthy();
  const latestContent = requiredObject(latestDetail.data.current_revision.content, "published record content");
  const recoveryDescription = `${reviewDescription} · recovery-${runId}`;
  const recoveryRecord = await callJson<CatalogRecord>(request, administratorToken, `/catalog/records/${recordId}/revisions`, {
    method: "POST",
    headers: { "If-Match": latestEtag },
    body: {
      content: { ...latestContent, description: recoveryDescription },
      change_reason: `Advance immutable upstream record revision for recovery ${runId}`,
    },
  });
  const recoveryRevisionId = recoveryRecord.data.current_revision.id;
  await callJson<Binding>(request, administratorToken, `/catalog/records/${recordId}/revisions/${recoveryRevisionId}/domain-binding`, {
    method: "POST",
    body: { kind: "material", object_id: sourceMaterialBinding.object_id, revision_id: sourceMaterialBinding.revision_id },
  });

  const publishedAfterAdvance = await callJson<SearchResponse>(request, userToken, "/catalog/records:search", {
    method: "POST",
    body: {
      table_id: tableId,
      text: "CMP-DEMO-DP780",
      domain_binding_kind: "material",
      published_only: true,
      limit: 100,
    },
  });
  expect(publishedAfterAdvance.data.items.some((item) => item.record_id === recordId)).toBe(false);
  const revisionHistory = await callJson<{ items: Revision[] }>(request, userToken, `/catalog/records/${recordId}/revisions`);
  expect(revisionHistory.data.items.length).toBeGreaterThanOrEqual(3);

  const recoveryReason = `Resubmit exact recovered context ${runId}`;
  await page.goto(`/catalog/records?record_id=${recordId}&revision_id=${recoveryRevisionId}`);
  await selectExactRecordEditor(page, recoveryDescription, recoveryRecord.data.current_revision.revision_no);
  await expect(page.getByRole("button", { name: "Request review", exact: true })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Request review", exact: true }).click();
  await page.getByRole("textbox", { name: "Review request reason" }).fill(recoveryReason);
  await page.getByRole("button", { name: "Send request", exact: true }).click();
  await expect(page.locator('[role="status"]').filter({ hasText: "Waiting for review" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(`${revisionHistory.data.items.length} revisions`, { exact: true })).toBeVisible();
});
