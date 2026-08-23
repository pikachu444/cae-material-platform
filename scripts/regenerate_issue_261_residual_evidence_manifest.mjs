import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const manifestPath = "docs/17-evidence/images/issue-261-fe06-residual-owner-boundary-consolidation/manifest.json";
const livePath = "docs/17-evidence/images/issue-261-fe06-residual-owner-boundary-consolidation/live/manifest.json";
const fixture = JSON.parse(readFileSync(resolve(ROOT, "scripts/fixtures/issue-261-residual-owner-boundary.json"), "utf8"));
const manifest = JSON.parse(readFileSync(resolve(ROOT, manifestPath), "utf8"));
const live = JSON.parse(readFileSync(resolve(ROOT, livePath), "utf8"));

const visualFiles = [...new Set([
  ...fixture.legacySources.map(({ path }) => path),
  ...Object.values(fixture.owners).map(({ path }) => path),
])].sort();
const sha256 = (path) => createHash("sha256").update(readFileSync(resolve(ROOT, path))).digest("hex");
const imageRoots = [
  "docs/00-research",
  "docs/17-evidence/images",
  "docs/user-guide/images",
];
const imageExtensions = new Set([".png", ".jpg", ".jpeg"]);
const walk = (relativeRoot) => readdirSync(resolve(ROOT, relativeRoot)).flatMap((name) => {
  const relativePath = `${relativeRoot}/${name}`;
  const absolutePath = resolve(ROOT, relativePath);
  return statSync(absolutePath).isDirectory() ? walk(relativePath) : [relativePath];
});

manifest.implementation_base = fixture.baseSha;
manifest.status = "ACCEPTED_MAIN_VISUAL_AND_RUNTIME";
manifest.live_capture = {
  manifest: livePath,
  harness_schema: live.schemaVersion,
  note: "The established M4 topology harness is reused; the FE-06 fixture is authoritative for ownership counts.",
  status: live.status,
  topology_count: live.capturePlan.topologyCount,
  viewport_count: live.viewports.length,
  image_count: live.imageInventory.registeredCount,
  pair_count: live.comparison.artifactPairs,
  pixel_identical_pairs: live.comparison.pixelIdenticalPairs,
  browser_zoom_percent: live.browserZoomPercent,
  device_pixel_ratio: live.devicePixelRatio,
  physical_windows_4k_readability: live.physicalWindows4KReadability,
};
manifest.ownership = {
  migrated_rows: fixture.targetRows.rows,
  migrated_groups: fixture.targetRows.groups,
  accepted_in_place_rows: fixture.acceptedInPlace.rows,
  original_m6_rows: fixture.originalM6Handoff.rows,
  m6_handoff_rows: fixture.m6Handoff.rows,
  m6_handoff_groups: fixture.m6Handoff.groups,
  target_tuple_sha256: fixture.targetRows.tupleSha256,
  m6_tuple_sha256: fixture.m6Handoff.tupleSha256,
};
const historicalImages = manifest.images.filter((entry) => !entry.path.includes("/issue-261-fe06-residual-owner-boundary-consolidation/live/"));
manifest.images = historicalImages;
manifest.documentation_impact.visual_files = visualFiles;
manifest.documentation_impact.visual_file_sha256 = Object.fromEntries(visualFiles.map((path) => [path, sha256(path)]));
manifest.documentation_impact.classification = "behavior-preserving-css-migration";
delete manifest.documentation_impact.live_capture_manifest;

const hashes = new Map();
for (const path of imageRoots.flatMap(walk).filter((path) => imageExtensions.has(path.slice(path.lastIndexOf(".")).toLowerCase()))) {
  const digest = sha256(path);
  hashes.set(digest, [...(hashes.get(digest) ?? []), path]);
}
const liveRoot = "docs/17-evidence/images/issue-261-fe06-residual-owner-boundary-consolidation/live/";
manifest.allowed_duplicate_groups = [...hashes.values()]
  .map((paths) => paths.sort())
  .filter((paths) => paths.length > 1 && paths.some((path) => path.startsWith(liveRoot)))
  .sort((left, right) => left[0].localeCompare(right[0]))
  .map((images) => ({
    rationale: "FE-06 preserves byte-identical before/after and historical accepted evidence for the same rendered route/state.",
    images,
  }));

writeFileSync(resolve(ROOT, manifestPath), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`WROTE ${manifestPath}`);
