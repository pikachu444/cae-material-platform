import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readdir, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { resolve, relative, sep } from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";

const baseSHA = "6abddd25b9ef8e7f2e0a8d112feaf3846996379b";
const fixtureId = "rd01-reference-steel-reader-v3";
const fixtureSHA = "FE8873B1F6978D5BF30D4936EADBEE9FB3B3BF5CD086E4C827BDF2E6105829A1";
const outputRoot = "../../.artifacts/frontend-redesign-prototype/correction-1";
const manifestRoot = ".artifacts/frontend-redesign-prototype/correction-1";
const screenshotRoot = `${outputRoot}/screenshots`;
const viewports = [
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
  { width: 3840, height: 2160 },
];
const evidence: Array<Record<string, unknown>> = [];
const sourceRoot = resolve(process.cwd(), "..", "..");

type SourceInventory = { files: Array<{ path: string; sha256: string }>; sha256: string };
let sourceInventoryBefore: SourceInventory | undefined;

function hashBytes(bytes: Uint8Array): string { return createHash("sha256").update(bytes).digest("hex"); }
function normalize(value: string): string { return value.split(sep).join("/"); }

async function walk(directory: string, excluded: Set<string>): Promise<string[]> {
  const found: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (entry.name.startsWith(".") && entry.name !== ".storybook") continue;
    if (entry.isDirectory() && excluded.has(entry.name)) continue;
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) found.push(...await walk(entryPath, excluded));
    else if (entry.isFile()) found.push(entryPath);
  }
  return found;
}

async function executableSourceInventory(): Promise<SourceInventory> {
  const appRoot = resolve(sourceRoot, "apps", "web-next");
  const appFiles = await walk(appRoot, new Set(["node_modules", "dist", "dist-prototype", "storybook-static", "coverage", ".artifacts"]));
  const rootFiles = [resolve(sourceRoot, "package.json"), resolve(sourceRoot, "package-lock.json")];
  const files = [...new Set([...appFiles, ...rootFiles])].sort();
  const entries: Array<{ path: string; sha256: string }> = [];
  const aggregate = createHash("sha256");
  for (const file of files) {
    const bytes = await readFile(file);
    const path = normalize(relative(sourceRoot, file));
    const sha256 = hashBytes(bytes);
    entries.push({ path, sha256 });
    aggregate.update(path);
    aggregate.update("\0");
    aggregate.update(bytes);
    aggregate.update("\0");
  }
  return { files: entries, sha256: aggregate.digest("hex") };
}

function dirtyDiffFingerprint(): string {
  try {
    const diff = execFileSync("git", ["diff", "--no-ext-diff"], { encoding: "buffer", stdio: ["ignore", "pipe", "ignore"] });
    return createHash("sha256").update(diff).digest("hex");
  } catch { return "unavailable"; }
}

function taskLocalToolchain(): { node: string; npm: string } {
  let npm = "unavailable";
  try {
    const npmCli = resolve(sourceRoot, ".cache", "runtime", "node_modules", "npm", "bin", "npm-cli.js");
    npm = execFileSync(process.execPath, [npmCli, "--version"], { encoding: "utf8" }).trim();
  } catch { /* The manifest still records the running Node version. */ }
  return { node: process.version, npm };
}

function manifestPath(path: string): string {
  return normalize(path).replace(`${outputRoot}/`, `${manifestRoot}/`);
}

async function hashFile(path: string): Promise<string> { return hashBytes(await readFile(path)); }

async function scopedCapture(locator: Locator, path: string): Promise<Record<string, unknown>> {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  await locator.screenshot({ path });
  return { path: manifestPath(path), sha256: await hashFile(path), rect: box ? { x: box.x, y: box.y, width: box.width, height: box.height } : null };
}

async function waitForState(page: Page, state: "list" | "test-detail" | "card-detail" | "empty" | "error" | "unsupported" | "long-name"): Promise<void> {
  if (state === "list") await expect(page.locator("table")).toBeVisible();
  if (state === "test-detail") {
    await expect(page.getByRole("heading", { name: /Reference tensile coupon/ })).toBeVisible();
    await expect(page.locator('[data-testid="curve-plot"]')).toBeVisible();
    await expect(page.getByRole("heading", { name: "Associated Solver Cards" })).toBeVisible();
  }
  if (state === "card-detail") {
    await expect(page.getByRole("heading", { name: /OpenRadioss linear elastic reference card/ })).toBeVisible();
    await expect(page.locator('[data-testid="native-preview"]')).toBeVisible();
  }
  if (state === "empty") await expect(page.getByRole("heading", { name: "No Test Data matches" })).toBeVisible();
  if (state === "error") await expect(page.getByRole("alert")).toContainText("Reader unavailable");
  if (state === "unsupported") await expect(page.getByRole("alert").filter({ hasText: "Download blocked" })).toContainText("Download blocked");
  if (state === "long-name") {
    await expect(page.getByRole("heading", { name: /장기 반복 인장/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Associated Solver Cards" })).toBeVisible();
  }
}

async function capture(page: Page, layout: "A" | "B", state: "list" | "test-detail" | "card-detail", viewport: { width: number; height: number }): Promise<void> {
  const label = `${layout}-${state}-${viewport.width}x${viewport.height}`;
  const imagePath = `${screenshotRoot}/${label}.png`;
  await page.screenshot({ path: imagePath, fullPage: false });
  const crops = [
    await scopedCapture(page.locator("header").first(), `${screenshotRoot}/${label}-header.png`),
    await scopedCapture(page.locator("aside"), `${screenshotRoot}/${label}-nav.png`),
    await scopedCapture(state === "list" ? page.locator("table").first() : state === "test-detail" ? page.locator('[data-testid="curve-plot"]') : page.locator('[data-testid="native-preview"]'), `${screenshotRoot}/${label}-primary.png`),
  ];
  evidence.push({
    layout,
    state,
    scenario: state === "list" ? "dense" : "normal",
    url: page.url(),
    viewport,
    dpr: await page.evaluate(() => window.devicePixelRatio),
    image: manifestPath(imagePath),
    imageSha256: await hashFile(imagePath),
    crops,
    fixtureId,
    fixtureSHA256: fixtureSHA,
    baseSHA,
    dirtyDiffFingerprint: dirtyDiffFingerprint(),
    toolchain: taskLocalToolchain(),
  });
}

test.describe("P1 visual evidence matrix", () => {
  test.beforeAll(async () => {
    await mkdir(screenshotRoot, { recursive: true });
    sourceInventoryBefore = await executableSourceInventory();
  });

  for (const layout of ["A", "B"] as const) {
    for (const state of ["list", "test-detail", "card-detail"] as const) {
      for (const viewport of viewports) {
        test(`${layout} ${state} ${viewport.width}x${viewport.height}`, async ({ page }) => {
          await page.setViewportSize(viewport);
          const url = state === "list"
            ? `/test-data?layout=${layout}&scenario=dense`
            : state === "test-detail"
              ? `/test-data/td-00042?layout=${layout}&scenario=normal&q=Reference%20tensile%20coupon`
              : `/cards/card-00001?layout=${layout}&scenario=normal&q=OpenRadioss`;
          await page.goto(url);
          await waitForState(page, state);
          await capture(page, layout, state, viewport);
        });
      }
    }
  }

  test("negative states at 1920x1080", async ({ page }) => {
    const viewport = { width: 1920, height: 1080 };
    await page.setViewportSize(viewport);
    const states = [
      { name: "empty", url: "/test-data?layout=A&scenario=empty", state: "empty" as const },
      { name: "error", url: "/test-data?layout=A&scenario=error", state: "error" as const },
      { name: "unsupported", url: "/cards/card-00003?layout=B&scenario=unsupported&q=Unsupported", state: "unsupported" as const },
      { name: "long-name", url: "/test-data/td-00017?layout=A&scenario=long-name&q=%EC%9E%A5%EA%B8%B0&selection=td-00017", state: "long-name" as const },
    ];
    for (const item of states) {
      await page.goto(item.url);
      await waitForState(page, item.state);
      const label = `negative-${item.name}-1920x1080`;
      const imagePath = `${screenshotRoot}/${label}.png`;
      await page.screenshot({ path: imagePath, fullPage: false });
      const crops = item.name === "long-name"
        ? [await scopedCapture(page.locator('[data-testid="test-data-detail-header"]'), `${screenshotRoot}/${label}-detail-header.png`), await scopedCapture(page.locator('[data-testid="curve-plot"]'), `${screenshotRoot}/${label}-curve.png`)]
        : [await scopedCapture(page.locator("header").first(), `${screenshotRoot}/${label}-header.png`), await scopedCapture(page.locator("aside"), `${screenshotRoot}/${label}-nav.png`)];
      evidence.push({
        layout: item.name === "unsupported" ? "B" : "A",
        state: item.name,
        scenario: item.name,
        url: page.url(),
        viewport,
        dpr: await page.evaluate(() => window.devicePixelRatio),
        image: manifestPath(imagePath),
        imageSha256: await hashFile(imagePath),
        crops,
        fixtureId,
        fixtureSHA256: fixtureSHA,
        baseSHA,
        dirtyDiffFingerprint: dirtyDiffFingerprint(),
        toolchain: taskLocalToolchain(),
      });
    }
  });

  test.afterAll(async () => {
    const sourceInventoryAfter = await executableSourceInventory();
    const sourceInventoryStable = JSON.stringify(sourceInventoryBefore) === JSON.stringify(sourceInventoryAfter);
    await writeFile(`${outputRoot}/screenshot-manifest.json`, JSON.stringify({
      generatedAt: new Date().toISOString(),
      baseSHA,
      fixtureId,
      fixtureSHA256: fixtureSHA,
      sourceInventoryBefore,
      sourceInventoryAfter,
      sourceInventoryStable,
      toolchain: taskLocalToolchain(),
      screenshotCount: evidence.filter((entry) => ["list", "test-detail", "card-detail"].includes(String(entry.state))).length,
      negativeStateCount: evidence.filter((entry) => ["empty", "error", "unsupported", "long-name"].includes(String(entry.state))).length,
      entries: evidence,
    }, null, 2));
    expect(sourceInventoryStable).toBe(true);
  });
});
