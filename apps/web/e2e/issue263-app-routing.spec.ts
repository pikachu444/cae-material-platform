import { expect, test, type Page, type Route } from "@playwright/test";

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function observeUnexpectedBrowserErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

async function installRouteFixture(page: Page, withStoredSession = true) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/demo-identity/token")) {
      await fulfillJson(route, {
        access_token: "issue-263-demo-token",
        token_type: "Bearer",
        expires_in_seconds: 900,
        persona: "administrator",
      });
      return;
    }
    if (path.endsWith("/product-access/me")) {
      await fulfillJson(route, {
        product_role: "administrator",
        feature_grants: ["schema_configuration", "catalog_editing"],
        legacy_compatible: false,
      });
      return;
    }
    if (path.endsWith("/me")) {
      await fulfillJson(route, {
        principal_id: "issue-263-user",
        principal_type: "user",
        display_name: "Issue 263 User",
        organization_id: "issue-263-org",
        project_id: "issue-263-project",
        groups: [],
        scopes: [],
        request_id: "issue-263-request",
        trace_id: "issue-263-trace",
      });
      return;
    }
    if (path.includes("/review-requests")) {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (path.endsWith("/catalog/records:search")) {
      await fulfillJson(route, {
        items: [],
        total_count: 0,
        offset: 0,
        limit: 50,
        facets: [],
      });
      return;
    }
    if (
      path.endsWith("/catalog/tables") ||
      path.endsWith("/catalog/databases") ||
      path.endsWith("/catalog/link-types") ||
      path.endsWith("/catalog/explorer/tables") ||
      path.endsWith("/product-access/assignments")
    ) {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (path.endsWith("/materials")) {
      await fulfillJson(route, { items: [], total_count: 0 });
      return;
    }
    await fulfillJson(route, { items: [] });
  });
  if (withStoredSession) {
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({
          baseUrl: "/api/v1",
          accessToken: "issue-263-production-token",
        }),
      );
    });
  }
}

test("root, shell navigation and browser popstate keep one exact route truth", async ({
  page,
}) => {
  const browserErrors = observeUnexpectedBrowserErrors(page);
  await installRouteFixture(page);
  await page.goto("/");

  await expect(page).toHaveURL(/\/materials$/);
  await expect(page.locator(".application-shell")).toBeVisible();
  await page.getByRole("button", { name: "Modeling", exact: true }).click();
  await expect(page).toHaveURL(/\/modeling$/);
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(page).toHaveURL(/\/activity$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/modeling$/);
  await expect(
    page.getByRole("button", { name: "Modeling", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await page.goBack();
  await expect(page).toHaveURL(/\/materials$/);
  await page.reload();
  await expect(page).toHaveURL(/\/materials$/);
  await expect(
    page.getByRole("button", { name: "Materials", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  expect(browserErrors).toEqual([]);
});

test("legacy Activity and Administration deep links preserve query and reload composition", async ({
  page,
}) => {
  const browserErrors = observeUnexpectedBrowserErrors(page);
  await installRouteFixture(page);
  const activityQuery = "?candidate_id=candidate-1";
  await page.goto(`/jobs-reviews${activityQuery}`);
  await expect(page.getByRole("heading", { name: "Activity", level: 1 })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/jobs-reviews\\${activityQuery}$`));
  await page.reload();
  await expect(page.getByRole("heading", { name: "Activity", level: 1 })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/jobs-reviews\\${activityQuery}$`));

  const recordsQuery =
    "?table_id=table-1&record_id=record-1&revision_id=record-r3";
  await page.goto(`/catalog/records${recordsQuery}`);
  await expect(
    page.getByRole("navigation", { name: "Administration tasks" }),
  ).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/catalog/records\\${recordsQuery}$`));
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Records", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await expect(page).toHaveURL(new RegExp(`/catalog/records\\${recordsQuery}$`));
  expect(browserErrors).toEqual([]);
});

test("failed demo-session startup exposes one retry and recovers the same route", async ({
  page,
}) => {
  const browserErrors = observeUnexpectedBrowserErrors(page);
  let tokenAttempts = 0;
  await installRouteFixture(page, false);
  await page.unroute("**/api/v1/**");
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/demo-identity/token")) {
      tokenAttempts += 1;
      // React StrictMode starts the initial effect twice in development; both
      // initial attempts fail so the user-visible recovery path remains deterministic.
      if (tokenAttempts <= 2) {
        await fulfillJson(route, { detail: "Synthetic session failure" }, 503);
      } else {
        await fulfillJson(route, {
          access_token: "issue-263-recovered-token",
          token_type: "Bearer",
          expires_in_seconds: 900,
          persona: "administrator",
        });
      }
      return;
    }
    if (path.endsWith("/catalog/records:search")) {
      await fulfillJson(route, {
        items: [],
        total_count: 0,
        offset: 0,
        limit: 50,
        facets: [],
      });
      return;
    }
    if (path.endsWith("/catalog/tables")) {
      await fulfillJson(route, { items: [] });
      return;
    }
    await fulfillJson(route, { items: [] });
  });

  await page.goto("/materials?q=DP780");
  await expect(
    page.getByRole("heading", { name: "Sign in to continue" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toHaveCount(1);
  await page.getByRole("button", { name: "Try again" }).click();

  await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
  await expect(page).toHaveURL(/\/materials\?q=DP780$/);
  expect(tokenAttempts).toBe(3);
  expect(browserErrors).toEqual([
    "Failed to load resource: the server responded with a status of 503 (Service Unavailable)",
    "Failed to load resource: the server responded with a status of 503 (Service Unavailable)",
  ]);
});
