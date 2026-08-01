import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const abaqusOutput = process.env.CMP_T88_ABAQUS_SCREENSHOT
  ?? "docs/17-evidence/images/historical-task-screenshots/t88-abaqus-card-delivery.png";
const radiossOutput = process.env.CMP_T88_RADIOSS_SCREENSHOT
  ?? "docs/17-evidence/images/historical-task-screenshots/t88-openradioss-card-delivery.png";

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  let tokenResponse = null;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    try {
      const response = await context.request.get(`${webUrl}/api/v1/demo-identity/token`);
      if (response.ok()) {
        tokenResponse = response;
        break;
      }
    } catch {
      // The freshly recreated web proxy can take a moment to accept requests.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  if (!tokenResponse) throw new Error("local demo identity is unavailable");
  const { access_token: accessToken } = await tokenResponse.json();
  const page = await context.newPage();
  await page.addInitScript(
    ({ token }) => window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: token }),
    ),
    { token: accessToken },
  );

  await page.goto(`${webUrl}/modeling`);
  await page.getByRole("heading", { name: "Test curves to material model" }).waitFor();
  await page.getByRole("button", { name: "Card", exact: true }).click();
  await page.getByRole("heading", { name: "Neutral model to solver-native material card" }).waitFor();
  await page.getByLabel("Reviewed Neutral Material and solver card delivery").waitFor({ timeout: 30_000 });
  await page.getByText(/Exact Neutral JSON r\d+ restored/).waitFor({ timeout: 30_000 });
  await page.getByLabel("Solver target").selectOption("abaqus");
  await page.getByRole("button", { name: "Run mapping preflight" }).click();
  await page.getByLabel("Neutral Material solver mapping report").waitFor();
  const acknowledgement = page.getByLabel(/I reviewed every approximated or ignored mapping state/);
  if (await acknowledgement.count()) await acknowledgement.check();
  await page.getByRole("button", { name: "Create solver card" }).click();
  await page.getByText(/abaqus card r\d+ created/).waitFor({ timeout: 30_000 });
  const abaqusPreview = page.getByLabel("Solver card preview");
  await abaqusPreview.waitFor();
  await page.evaluate(() => window.document.getElementById("modeling-card")?.scrollIntoView({ block: "start" }));
  await page.evaluate(() => window.scrollBy(0, -72));
  await page.screenshot({ path: abaqusOutput, fullPage: false });
  const abaqusDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download native ASCII card" }).click();
  const abaqusDownload = await abaqusDownloadPromise;
  if (!abaqusDownload.suggestedFilename().endsWith(".inp")) throw new Error("Abaqus card did not download as .inp");
  const reportDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download mapping report JSON" }).click();
  const reportDownload = await reportDownloadPromise;
  if (!reportDownload.suggestedFilename().endsWith(".json")) throw new Error("mapping report did not download as JSON");

  await page.getByLabel("Solver target").selectOption("openradioss");
  await page.getByRole("button", { name: "Run mapping preflight" }).click();
  await page.getByLabel("Neutral Material solver mapping report").waitFor();
  if (await acknowledgement.count()) await acknowledgement.check();
  await page.getByRole("button", { name: "Create solver card" }).click();
  await page.getByText(/openradioss card r\d+ created/).waitFor({ timeout: 30_000 });
  const radiossPreview = page.getByLabel("Solver card preview");
  await radiossPreview.waitFor();
  await radiossPreview.scrollIntoViewIfNeeded();
  await page.screenshot({ path: radiossOutput, fullPage: false });
  const radiossDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download native ASCII card" }).click();
  const radiossDownload = await radiossDownloadPromise;
  if (!radiossDownload.suggestedFilename().endsWith(".rad")) throw new Error("OpenRadioss card did not download as .rad");

  console.log(`captured ${abaqusOutput}`);
  console.log(`captured ${radiossOutput}`);
  console.log(`verified ${abaqusDownload.suggestedFilename()}, ${radiossDownload.suggestedFilename()}, and ${reportDownload.suggestedFilename()}`);
} finally {
  await browser.close();
}
