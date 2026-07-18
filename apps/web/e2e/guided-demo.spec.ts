import { expect, test } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";

test("clean demo exposes three material-family journeys and bulk entry", async ({ page, request }) => {
  const tokenResponse = await request.get(`${webUrl}/api/v1/demo-identity/token`);
  expect(tokenResponse.ok()).toBeTruthy();
  const tokenPayload = (await tokenResponse.json()) as { access_token: string };

  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: tokenPayload.access_token },
  );

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Choose a material family and follow the evidence." }),
  ).toBeVisible();
  await expect(page.getByText("CMP-DEMO-DP780", { exact: true })).toBeVisible();
  await expect(page.getByText("CMP-DEMO-POLYMER-PRONY", { exact: true })).toBeVisible();
  await expect(page.getByText("CMP-DEMO-ELASTOMER-OGDEN", { exact: true })).toBeVisible();

  for (const [action, materialCode] of [
    ["Open metal journey", "CMP-DEMO-DP780"],
    ["Open polymer journey", "CMP-DEMO-POLYMER-PRONY"],
    ["Open elastomer journey", "CMP-DEMO-ELASTOMER-OGDEN"],
  ] as const) {
    await expect(page.getByText(materialCode, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: action }).click();
    await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\/models$/);
    await page.goto("/");
  }

  await page.getByRole("button", { name: "Open bulk downloads" }).click();
  await expect(page).toHaveURL(/\/exports$/);
});
