import { createHash } from "node:crypto";
import { cpus, release } from "node:os";
import { createServer } from "node:http";
import { gzipSync } from "node:zlib";
import { readFile, readdir, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, extname, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import { chromium } from "playwright";

import { collectBundleBudget, DEFAULT_ASSETS_DIR } from "./check_web_bundle.mjs";
import {
  ROUTES,
  SESSION_STORAGE_KEY,
  createModelingFixture,
  modelingSession,
} from "./fixtures/modeling_route_fixture.mjs";

const repository = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const scriptPath = fileURLToPath(import.meta.url);
const fixturePath = resolve(repository, "scripts", "fixtures", "modeling_route_fixture.mjs");
const baselineSchemaVersion = "cmp.web-modeling-route-baseline.v1";
const baselineCompareCommand = "npm run measure:modeling-route --workspace @cmp/web -- --compare docs/14-testing/baselines/modeling-web-route.json";
const REGRESSION_METRICS = ["requiredChunks", "transferBytes", "transferSpanMs", "parseMs", "executeMs"];

export const MEASUREMENT_PROFILE = {
  version: "cmp.web-modeling-route-profile.v1",
  window: "cold_route_plus_required_action",
  routes: ROUTES.map((route) => ({
    id: route.id,
    path: route.path,
    actions: [...route.actions],
    readinessSelectors: [...route.readinessSelectors],
    requiredChunks: [...route.requiredChunks],
  })),
  sampleCount: 5,
  timeoutMs: 15000,
  settleMs: 400,
  browser: {
    headless: true,
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "en-US",
    colorScheme: "light",
    reducedMotion: "reduce",
    cacheDisabled: true,
    serviceWorkers: "block",
  },
  network: {
    downloadBitsPerSecond: 10_000_000,
    uploadBitsPerSecond: 5_000_000,
    latencyMs: 40,
  },
  cpu: { throttleRate: 4, profilerSampleIntervalUs: 100 },
  gzip: { level: 9 },
  formulas: {
    transferBytes: "sum(resourceTiming.encodedBodySize)",
    transferSpanMs: "max(startTime+duration)-min(startTime)",
    parseMs: "sum(trace.v8.parseOnBackground+trace.v8.compileModule dur)/1000",
    executeMs: "(Performance.ScriptDuration_after-Performance.ScriptDuration_before)*1000",
    sampledCpuMs: "leafCpuSamples*0.1",
  },
  categories: ["devtools.timeline", "v8", "disabled-by-default-v8.compile", "blink.user_timing"],
  events: ["v8.parseOnBackground", "v8.compileModule", "ResourceTiming", "Performance.ScriptDuration", "Profiler.cpuProfile"],
  aggregation: { median: "sorted_middle_of_5", bytes: "integer", milliseconds: "round_3_after_median" },
  regressionOrder: ["requiredChunks", "transferBytes", "transferSpanMs", "parseMs", "executeMs"],
  regressionThresholds: {
    transferBytes: { relative: 0.05, absolute: 4096 },
    transferSpanMs: { relative: 0.1, absolute: 20 },
    parseMs: { relative: 0.1, absolute: 2 },
    executeMs: { relative: 0.1, absolute: 10 },
  },
};

export class ModelingRouteMeasurementError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "ModelingRouteMeasurementError";
    this.code = code;
  }
}

export function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0).map(([key, nested]) => [key, canonicalize(nested)]));
  }
  return value;
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

export function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

export function median(values) {
  if (!Array.isArray(values) || values.length === 0 || values.length % 2 === 0 || values.some((value) => typeof value !== "number" || !Number.isFinite(value))) {
    throw new ModelingRouteMeasurementError("TRACE", "median requires a non-empty odd finite sample set");
  }
  return [...values].sort((left, right) => left - right)[Math.floor(values.length / 2)];
}

export function roundMilliseconds(value) {
  return Number(Number(value).toFixed(3));
}

function compareCodePoint(left, right) { return left < right ? -1 : left > right ? 1 : 0; }
function sortStrings(values) { return [...values].sort(compareCodePoint); }

export async function fingerprintBuild(assetsDir = DEFAULT_ASSETS_DIR) {
  const directory = resolve(String(assetsDir));
  let entries;
  try { entries = await readdir(directory, { withFileTypes: true }); } catch { throw new ModelingRouteMeasurementError("DIST", `dist assets directory is unavailable: ${directory}`); }
  const files = entries.filter((entry) => entry.isFile() && extname(entry.name) === ".js").sort((left, right) => compareCodePoint(left.name, right.name));
  if (!files.length) throw new ModelingRouteMeasurementError("DIST", `no JavaScript files found in ${directory}`);
  const digest = createHash("sha256");
  const emittedFiles = [];
  for (const file of files) {
    const bytes = await readFile(join(directory, file.name));
    digest.update(Buffer.from(file.name, "utf8"));
    digest.update(Buffer.from([0]));
    digest.update(bytes);
    digest.update(Buffer.from([0]));
    emittedFiles.push(file.name);
  }
  return { sha256: digest.digest("hex"), emittedFiles };
}

export async function integrityHashes({ script = scriptPath, fixture = fixturePath } = {}) {
  const [scriptBytes, fixtureBytes] = await Promise.all([readFile(script), readFile(fixture)]);
  return {
    fixtureSha256: sha256(fixtureBytes),
    harnessSha256: sha256(Buffer.concat([scriptBytes, Buffer.from([0]), fixtureBytes, Buffer.from([0])])),
  };
}

export function measurementProfileSha256(profile = MEASUREMENT_PROFILE) {
  return sha256(Buffer.from(canonicalJson(profile), "utf8"));
}

export function environmentSnapshot(chromiumVersion = "unknown") {
  const cpuModel = cpus()[0]?.model || "unknown";
  return {
    nodeVersion: process.version,
    platform: process.platform,
    osRelease: release(),
    arch: process.arch,
    cpuModel,
    chromiumVersion,
    headless: true,
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "en-US",
    colorScheme: "light",
    reducedMotion: "reduce",
    cpuThrottleRate: 4,
    network: { downloadBitsPerSecond: 10_000_000, uploadBitsPerSecond: 5_000_000, latencyMs: 40 },
    profilerSampleIntervalUs: 100,
    sampleCount: 5,
    gzipLevel: 9,
  };
}

function policyFromBundle(bundle) { return bundle.policy; }
function bundleSnapshot(bundle) { return { observations: bundle.observations, summary: bundle.summary }; }

function lookupObservation(bundle, emittedFile) {
  return bundle.observations.find((item) => item.emittedFile === emittedFile);
}

export function joinChunkMetrics({ bundle, resources, parseByFile = {}, cpuByFile = {} }) {
  const byFile = new Map();
  for (const resource of resources) {
    if (!resource.emittedFile) continue;
    const current = byFile.get(resource.emittedFile) ?? { transferBytes: 0, transferDurationMs: 0 };
    current.transferBytes += Number(resource.transferBytes ?? resource.encodedBodySize ?? 0);
    current.transferDurationMs += Number(resource.transferDurationMs ?? resource.duration ?? 0);
    byFile.set(resource.emittedFile, current);
  }
  return [...byFile.entries()].map(([emittedFile, value]) => {
    const observation = lookupObservation(bundle, emittedFile);
    if (!observation) throw new ModelingRouteMeasurementError("RESOURCE", `loaded asset is missing from bundle snapshot: ${emittedFile}`);
    return {
      logicalName: observation.logicalName,
      emittedFile,
      rawBytes: observation.rawBytes,
      gzipBytes: observation.gzipBytes,
      policyStatus: observation.status,
      headroomBytes: observation.headroomBytes,
      transferBytes: Math.round(value.transferBytes),
      transferDurationMs: roundMilliseconds(value.transferDurationMs),
      parseMs: roundMilliseconds(parseByFile[emittedFile] ?? 0),
      sampledCpuMs: roundMilliseconds(cpuByFile[emittedFile] ?? 0),
    };
  }).sort((left, right) => compareCodePoint(left.logicalName, right.logicalName) || compareCodePoint(left.emittedFile, right.emittedFile));
}

export function aggregateRouteSamples(routeProfile, samples, bundle) {
  if (!Array.isArray(samples) || samples.length !== 5) throw new ModelingRouteMeasurementError("TRACE", `route ${routeProfile.id} requires exactly five samples`);
  const loaded = samples.map((sample) => sortStrings(sample.loadedChunks ?? []));
  const firstLoaded = JSON.stringify(loaded[0]);
  if (loaded.some((value) => JSON.stringify(value) !== firstLoaded)) throw new ModelingRouteMeasurementError("TRACE", `route ${routeProfile.id} changed its loaded chunk set across samples`);
  const chunkSets = samples.map((sample) => sortStrings((sample.chunks ?? []).map((chunk) => `${chunk.logicalName}\u0000${chunk.emittedFile}`)));
  const firstChunkSet = JSON.stringify(chunkSets[0]);
  if (chunkSets.some((value) => JSON.stringify(value) !== firstChunkSet)) throw new ModelingRouteMeasurementError("TRACE", `route ${routeProfile.id} changed its chunk attribution set across samples`);
  const chunkNames = loaded[0];
  const allChunks = new Map();
  for (const sample of samples) for (const chunk of sample.chunks ?? []) {
    const key = `${chunk.logicalName}\u0000${chunk.emittedFile}`;
    const bucket = allChunks.get(key) ?? { ...chunk, transferBytes: [], transferDurationMs: [], parseMs: [], sampledCpuMs: [] };
    bucket.transferBytes.push(Number(chunk.transferBytes));
    bucket.transferDurationMs.push(Number(chunk.transferDurationMs));
    bucket.parseMs.push(Number(chunk.parseMs));
    bucket.sampledCpuMs.push(Number(chunk.sampledCpuMs));
    allChunks.set(key, bucket);
  }
  const chunks = [...allChunks.values()].map((chunk) => ({
    logicalName: chunk.logicalName,
    emittedFile: chunk.emittedFile,
    rawBytes: chunk.rawBytes,
    gzipBytes: chunk.gzipBytes,
    policyStatus: chunk.policyStatus,
    headroomBytes: chunk.headroomBytes,
    transferBytes: Math.round(median(chunk.transferBytes)),
    transferDurationMs: roundMilliseconds(median(chunk.transferDurationMs)),
    parseMs: roundMilliseconds(median(chunk.parseMs)),
    sampledCpuMs: roundMilliseconds(median(chunk.sampledCpuMs)),
  })).sort((left, right) => compareCodePoint(left.logicalName, right.logicalName) || compareCodePoint(left.emittedFile, right.emittedFile));
  const transferValues = samples.map((sample) => Number(sample.transferBytes));
  const spanValues = samples.map((sample) => Number(sample.transferSpanMs));
  const parseValues = samples.map((sample) => Number(sample.parseMs));
  const executeValues = samples.map((sample) => Number(sample.executeMs));
  return {
    id: routeProfile.id,
    path: routeProfile.path,
    window: "cold_route_plus_required_action",
    readinessSelectors: [...routeProfile.readinessSelectors],
    actions: [...routeProfile.actions],
    requiredChunks: [...routeProfile.requiredChunks],
    sampleCount: 5,
    loadedChunks: chunkNames,
    transferBytes: Math.round(median(transferValues)),
    transferSpanMs: roundMilliseconds(median(spanValues)),
    parseMs: roundMilliseconds(median(parseValues)),
    executeMs: roundMilliseconds(median(executeValues)),
    chunks,
  };
}

function relativeIncrease(current, baseline) { return typeof current === "number" && typeof baseline === "number" && Number.isFinite(current) && Number.isFinite(baseline) && baseline !== 0 ? (current - baseline) / baseline : null; }
function absoluteIncrease(current, baseline) { return typeof current === "number" && typeof baseline === "number" && Number.isFinite(current) && Number.isFinite(baseline) ? current - baseline : null; }

function candidate(routeId, metric, baselineValue, currentValue, threshold) {
  const numeric = typeof baselineValue === "number" && typeof currentValue === "number";
  const relative = numeric ? relativeIncrease(currentValue, baselineValue) : null;
  const absolute = numeric ? absoluteIncrease(currentValue, baselineValue) : null;
  const isArrayCandidate = Array.isArray(baselineValue) || Array.isArray(currentValue);
  const qualifies = isArrayCandidate ? JSON.stringify(baselineValue) !== JSON.stringify(currentValue) : Boolean(relative !== null && absolute !== null && relative > threshold.relative && absolute > threshold.absolute);
  return qualifies ? {
    routeId,
    metric,
    baseline: baselineValue,
    current: currentValue,
    relativeIncrease: relative,
    absoluteIncrease: absolute,
    relativeThreshold: isArrayCandidate ? null : threshold.relative,
    absoluteThreshold: isArrayCandidate ? null : threshold.absolute,
  } : null;
}

function routeById(routes, id) { return routes.find((route) => route.id === id); }

function sortDiagnostics(diagnostics) {
  return [...(diagnostics ?? [])].sort((left, right) => compareCodePoint(String(left?.code ?? ""), String(right?.code ?? ""))
    || compareCodePoint(String(left?.field ?? ""), String(right?.field ?? ""))
    || compareCodePoint(String(left?.message ?? ""), String(right?.message ?? "")));
}

function sortRouteCandidates(candidates, profile = MEASUREMENT_PROFILE) {
  const routeOrder = new Map(profile.routes.map((route, index) => [route.id, index]));
  const metricOrder = new Map(REGRESSION_METRICS.map((metric, index) => [metric, index]));
  return [...(candidates ?? [])].sort((left, right) =>
    (routeOrder.get(left?.routeId) ?? Number.MAX_SAFE_INTEGER) - (routeOrder.get(right?.routeId) ?? Number.MAX_SAFE_INTEGER)
    || (metricOrder.get(left?.metric) ?? Number.MAX_SAFE_INTEGER) - (metricOrder.get(right?.metric) ?? Number.MAX_SAFE_INTEGER)
    || compareCodePoint(String(left?.routeId ?? ""), String(right?.routeId ?? ""))
    || compareCodePoint(String(left?.metric ?? ""), String(right?.metric ?? "")));
}

export function compareRoutes(currentRoutes, baselineRoutes, profile = MEASUREMENT_PROFILE) {
  const candidates = [];
  const metrics = [...REGRESSION_METRICS];
  for (const routeProfile of profile.routes) {
    const current = routeById(currentRoutes, routeProfile.id);
    const baseline = routeById(baselineRoutes, routeProfile.id);
    if (!current || !baseline) {
      candidates.push({ routeId: routeProfile.id, metric: "requiredChunks", baseline: baseline ? baseline.requiredChunks : [], current: current ? current.requiredChunks : [], relativeIncrease: null, absoluteIncrease: null, relativeThreshold: null, absoluteThreshold: null });
      continue;
    }
    for (const metric of metrics) {
      if (metric === "requiredChunks") {
        const requiredChanged = JSON.stringify(current.requiredChunks) !== JSON.stringify(baseline.requiredChunks);
        const loadedChanged = JSON.stringify(current.loadedChunks) !== JSON.stringify(baseline.loadedChunks);
        if (requiredChanged || loadedChanged) {
          const baselineValue = requiredChanged ? baseline.requiredChunks : baseline.loadedChunks;
          const currentValue = requiredChanged ? current.requiredChunks : current.loadedChunks;
          candidates.push({ routeId: routeProfile.id, metric, baseline: baselineValue, current: currentValue, relativeIncrease: null, absoluteIncrease: null, relativeThreshold: null, absoluteThreshold: null });
        }
        continue;
      }
      const threshold = profile.regressionThresholds[metric] ?? { relative: null, absolute: null };
      const item = candidate(routeProfile.id, metric, baseline[metric], current[metric], threshold);
      if (item) candidates.push(item);
    }
  }
  return sortRouteCandidates(candidates, profile);
}

function diagnostic(code, field, message) { return { code, field: field ?? null, message }; }

export function createComparison(status = "not_requested", options = {}) {
  return {
    status,
    baselinePath: options.baselinePath ?? null,
    baselineSequence: options.baselineSequence ?? null,
    diagnostics: sortDiagnostics(options.diagnostics),
    routeCandidates: sortRouteCandidates(options.routeCandidates),
  };
}

function observationWithoutEnvelope(report) {
  const { schemaVersion: _schemaVersion, sourceSha: _sourceSha, comparison: _comparison, ...observation } = report;
  return observation;
}

export function createBaselineEnvelope(report) {
  return {
    schemaVersion: baselineSchemaVersion,
    updatePolicy: {
      authority: "product_owner",
      automaticWritesAllowed: false,
      method: "append_reviewed_accepted_main_observation",
      compareCommand: baselineCompareCommand,
    },
    observations: [{ ...observationWithoutEnvelope(report), sequence: 1, acceptedMainSha: report.sourceSha }],
  };
}

const BASELINE_TOP_KEYS = ["schemaVersion", "updatePolicy", "observations"];
const BASELINE_POLICY_KEYS = ["authority", "automaticWritesAllowed", "method", "compareCommand"];
const BASELINE_OBSERVATION_KEYS = ["sequence", "acceptedMainSha", "buildFingerprintSha256", "profile", "measurementProfileSha256", "harnessSha256", "environment", "policy", "bundle", "fixture", "routes"];
const BASELINE_ROUTE_KEYS = ["id", "path", "window", "readinessSelectors", "actions", "requiredChunks", "sampleCount", "loadedChunks", "transferBytes", "transferSpanMs", "parseMs", "executeMs", "chunks"];
const BASELINE_CHUNK_KEYS = ["logicalName", "emittedFile", "rawBytes", "gzipBytes", "policyStatus", "headroomBytes", "transferBytes", "transferDurationMs", "parseMs", "sampledCpuMs"];
const BASELINE_FIXTURE_KEYS = ["fixtureId", "fixtureSha256", "nonProduction", "materialFamily", "sessionStorageKey", "routes"];
const BASELINE_FIXTURE_ROUTE_KEYS = ["id", "requests", "allowedPreviewPosts", "persistentWrites", "unexpectedRequests"];
const BASELINE_REQUEST_KEYS = ["method", "path", "count"];
const BASELINE_BUNDLE_KEYS = ["observations", "summary"];
const BASELINE_BUNDLE_SUMMARY_KEYS = ["status", "warningCount", "errorCount", "largestRaw", "largestGzip"];
const BASELINE_PROFILE_KEYS = ["version", "window", "routes", "sampleCount", "timeoutMs", "settleMs", "browser", "network", "cpu", "gzip", "formulas", "categories", "events", "aggregation", "regressionOrder", "regressionThresholds"];
const BASELINE_PROFILE_ROUTE_KEYS = ["id", "path", "actions", "readinessSelectors", "requiredChunks"];
const BASELINE_PROFILE_BROWSER_KEYS = ["headless", "viewport", "deviceScaleFactor", "locale", "colorScheme", "reducedMotion", "cacheDisabled", "serviceWorkers"];
const BASELINE_PROFILE_NETWORK_KEYS = ["downloadBitsPerSecond", "uploadBitsPerSecond", "latencyMs"];
const BASELINE_PROFILE_CPU_KEYS = ["throttleRate", "profilerSampleIntervalUs"];
const BASELINE_PROFILE_GZIP_KEYS = ["level"];
const BASELINE_PROFILE_FORMULA_KEYS = ["transferBytes", "transferSpanMs", "parseMs", "executeMs", "sampledCpuMs"];
const BASELINE_PROFILE_AGGREGATION_KEYS = ["median", "bytes", "milliseconds"];
const BASELINE_ENVIRONMENT_KEYS = ["nodeVersion", "platform", "osRelease", "arch", "cpuModel", "chromiumVersion", "headless", "viewport", "deviceScaleFactor", "locale", "colorScheme", "reducedMotion", "cpuThrottleRate", "network", "profilerSampleIntervalUs", "sampleCount", "gzipLevel"];
const BASELINE_POLICY_KEYS_OBSERVATION = ["measurement", "gzip", "overrideActive", "activeOverrides", "entry", "lazy", "overrideNames"];
const BASELINE_POLICY_BUDGET_KEYS = ["warningBytes", "errorBytes", "warningPurpose", "errorPurpose"];
const BASELINE_POLICY_OVERRIDE_KEYS = ["entryWarning", "entryError", "lazyWarning", "lazyError"];
const BASELINE_BUNDLE_OBSERVATION_KEYS = ["kind", "logicalName", "emittedFile", "rawBytes", "gzipBytes", "warningBytes", "errorBytes", "headroomBytes", "status"];
const BASELINE_LARGEST_KEYS = ["kind", "logicalName", "emittedFile", "bytes"];
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const SHA1_PATTERN = /^[0-9a-f]{40}$/;

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasExactKeys(value, expected) {
  return isRecord(value) && JSON.stringify(Object.keys(value).sort(compareCodePoint)) === JSON.stringify([...expected].sort(compareCodePoint));
}

function hasFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function isNonnegativeInteger(value) {
  return Number.isSafeInteger(value) && value >= 0;
}

function isPositiveInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function isFiniteNonnegative(value) {
  return hasFiniteNumber(value) && value >= 0;
}

function isSortedUniqueStrings(value) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) return false;
  const sorted = [...value].sort(compareCodePoint);
  return new Set(value).size === value.length && JSON.stringify(value) === JSON.stringify(sorted);
}

function isStringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function validProfile(profile) {
  if (!hasExactKeys(profile, BASELINE_PROFILE_KEYS) || typeof profile.version !== "string" || profile.window !== "cold_route_plus_required_action" || profile.sampleCount !== 5 || !isNonnegativeInteger(profile.timeoutMs) || !isNonnegativeInteger(profile.settleMs) || !Array.isArray(profile.routes) || !hasExactKeys(profile.browser, BASELINE_PROFILE_BROWSER_KEYS) || !hasExactKeys(profile.browser.viewport, ["width", "height"]) || !hasExactKeys(profile.network, BASELINE_PROFILE_NETWORK_KEYS) || !hasExactKeys(profile.cpu, BASELINE_PROFILE_CPU_KEYS) || !hasExactKeys(profile.gzip, BASELINE_PROFILE_GZIP_KEYS) || !hasExactKeys(profile.formulas, BASELINE_PROFILE_FORMULA_KEYS) || !isStringArray(profile.categories) || !isStringArray(profile.events) || !hasExactKeys(profile.aggregation, BASELINE_PROFILE_AGGREGATION_KEYS) || !isStringArray(profile.regressionOrder) || !hasExactKeys(profile.regressionThresholds, ["transferBytes", "transferSpanMs", "parseMs", "executeMs"])) return false;
  if (profile.routes.length !== 3 || profile.routes.some((route) => !hasExactKeys(route, BASELINE_PROFILE_ROUTE_KEYS) || !isStringArray(route.actions) || !isStringArray(route.readinessSelectors) || !isSortedUniqueStrings(route.requiredChunks))) return false;
  if (!["process", "fit", "export"].every((id, index) => profile.routes[index]?.id === id && profile.routes[index]?.path === MEASUREMENT_PROFILE.routes[index]?.path)) return false;
  if (!["headless", "cacheDisabled"].every((key) => typeof profile.browser[key] === "boolean") || !isNonnegativeInteger(profile.browser.viewport.width) || !isNonnegativeInteger(profile.browser.viewport.height) || !isFiniteNonnegative(profile.browser.deviceScaleFactor) || typeof profile.browser.locale !== "string" || typeof profile.browser.colorScheme !== "string" || typeof profile.browser.reducedMotion !== "string" || typeof profile.browser.serviceWorkers !== "string") return false;
  if (!isPositiveInteger(profile.network.downloadBitsPerSecond) || !isPositiveInteger(profile.network.uploadBitsPerSecond) || !isNonnegativeInteger(profile.network.latencyMs) || !isPositiveInteger(profile.cpu.throttleRate) || !isPositiveInteger(profile.cpu.profilerSampleIntervalUs) || !isNonnegativeInteger(profile.gzip.level)) return false;
  if (!Object.values(profile.formulas).every((value) => typeof value === "string") || !Object.values(profile.aggregation).every((value) => typeof value === "string")) return false;
  if (!Object.values(profile.regressionThresholds).every((threshold) => hasExactKeys(threshold, ["relative", "absolute"]) && isFiniteNonnegative(threshold.relative) && isFiniteNonnegative(threshold.absolute))) return false;
  return true;
}

function validEnvironment(environment, profile = MEASUREMENT_PROFILE) {
  return hasExactKeys(environment, BASELINE_ENVIRONMENT_KEYS)
    && ["nodeVersion", "platform", "osRelease", "arch", "cpuModel", "chromiumVersion", "locale", "colorScheme", "reducedMotion"].every((key) => typeof environment[key] === "string")
    && typeof environment.headless === "boolean"
    && hasExactKeys(environment.viewport, ["width", "height"]) && isNonnegativeInteger(environment.viewport.width) && isNonnegativeInteger(environment.viewport.height)
    && isFiniteNonnegative(environment.deviceScaleFactor)
    && isPositiveInteger(environment.cpuThrottleRate)
    && hasExactKeys(environment.network, BASELINE_PROFILE_NETWORK_KEYS) && isPositiveInteger(environment.network.downloadBitsPerSecond) && isPositiveInteger(environment.network.uploadBitsPerSecond) && isNonnegativeInteger(environment.network.latencyMs)
    && isPositiveInteger(environment.profilerSampleIntervalUs) && environment.sampleCount === 5 && isNonnegativeInteger(environment.gzipLevel)
    && isRecord(profile) && isRecord(profile.browser) && isRecord(profile.cpu) && isRecord(profile.network) && isRecord(profile.gzip)
    && environment.headless === profile.browser.headless
    && JSON.stringify(environment.viewport) === JSON.stringify(profile.browser.viewport)
    && environment.deviceScaleFactor === profile.browser.deviceScaleFactor
    && environment.locale === profile.browser.locale
    && environment.colorScheme === profile.browser.colorScheme
    && environment.reducedMotion === profile.browser.reducedMotion
    && environment.cpuThrottleRate === profile.cpu.throttleRate
    && JSON.stringify(environment.network) === JSON.stringify(profile.network)
    && environment.profilerSampleIntervalUs === profile.cpu.profilerSampleIntervalUs
    && environment.sampleCount === profile.sampleCount
    && environment.gzipLevel === profile.gzip.level;
}

function validObservationPolicy(policy) {
  return hasExactKeys(policy, BASELINE_POLICY_KEYS_OBSERVATION)
    && policy.measurement === "raw_bytes"
    && policy.gzip === "observation_only_node_zlib_level_9"
    && policy.overrideActive === false
    && isStringArray(policy.activeOverrides) && policy.activeOverrides.length === 0
    && hasExactKeys(policy.entry, BASELINE_POLICY_BUDGET_KEYS) && hasExactKeys(policy.lazy, BASELINE_POLICY_BUDGET_KEYS)
    && hasExactKeys(policy.overrideNames, BASELINE_POLICY_OVERRIDE_KEYS)
    && [policy.entry, policy.lazy].every((budget) => isPositiveInteger(budget.warningBytes) && isPositiveInteger(budget.errorBytes) && budget.warningBytes < budget.errorBytes && typeof budget.warningPurpose === "string" && typeof budget.errorPurpose === "string")
    && Object.values(policy.overrideNames).every((value) => typeof value === "string" && value.length > 0);
}

function validBundleObservation(observation) {
  return hasExactKeys(observation, BASELINE_BUNDLE_OBSERVATION_KEYS)
    && (observation.kind === "entry" || observation.kind === "lazy")
    && typeof observation.logicalName === "string" && observation.logicalName.length > 0 && typeof observation.emittedFile === "string" && /^[^/\\]+\.js$/.test(observation.emittedFile)
    && isNonnegativeInteger(observation.rawBytes) && isNonnegativeInteger(observation.gzipBytes) && isPositiveInteger(observation.warningBytes) && isPositiveInteger(observation.errorBytes)
    && hasFiniteNumber(observation.headroomBytes) && observation.headroomBytes === observation.errorBytes - observation.rawBytes
    && (observation.status === "ok" || observation.status === "warning" || observation.status === "error")
    && observation.warningBytes < observation.errorBytes
    && observation.status === (observation.rawBytes < observation.warningBytes ? "ok" : observation.rawBytes <= observation.errorBytes ? "warning" : "error");
}

function validLargest(value) {
  return value === null || (hasExactKeys(value, BASELINE_LARGEST_KEYS) && (value.kind === "entry" || value.kind === "lazy") && typeof value.logicalName === "string" && typeof value.emittedFile === "string" && isNonnegativeInteger(value.bytes));
}

function sortBundleKey(value) {
  return `${value?.kind ?? ""}\u0000${value?.logicalName ?? ""}\u0000${value?.emittedFile ?? ""}`;
}

function sortChunkKey(value) {
  return `${value?.logicalName ?? ""}\u0000${value?.emittedFile ?? ""}`;
}

function validChunk(chunk) {
  return hasExactKeys(chunk, BASELINE_CHUNK_KEYS)
    && typeof chunk.logicalName === "string" && typeof chunk.emittedFile === "string"
    && isNonnegativeInteger(chunk.rawBytes) && isNonnegativeInteger(chunk.gzipBytes)
    && (chunk.policyStatus === "ok" || chunk.policyStatus === "warning" || chunk.policyStatus === "error")
    && hasFiniteNumber(chunk.headroomBytes)
    && isNonnegativeInteger(chunk.transferBytes) && isFiniteNonnegative(chunk.transferDurationMs)
    && isFiniteNonnegative(chunk.parseMs) && isFiniteNonnegative(chunk.sampledCpuMs);
}

function validRouteRow(route, index, bundle) {
  const expected = MEASUREMENT_PROFILE.routes[index];
  if (!expected || !hasExactKeys(route, BASELINE_ROUTE_KEYS) || route.id !== expected.id || route.path !== expected.path || route.window !== "cold_route_plus_required_action" || JSON.stringify(route.readinessSelectors) !== JSON.stringify(expected.readinessSelectors) || JSON.stringify(route.actions) !== JSON.stringify(expected.actions) || JSON.stringify(route.requiredChunks) !== JSON.stringify(expected.requiredChunks) || !isSortedUniqueStrings(route.loadedChunks) || route.sampleCount !== 5 || !isNonnegativeInteger(route.transferBytes) || !isFiniteNonnegative(route.transferSpanMs) || !isFiniteNonnegative(route.parseMs) || !isFiniteNonnegative(route.executeMs) || !Array.isArray(route.chunks)) return false;
  if (!expected.requiredChunks.every((required) => route.loadedChunks.includes(required))) return false;
  const chunkKeys = route.chunks.map(sortChunkKey);
  if (chunkKeys.some((key, chunkIndex) => chunkIndex > 0 && key === chunkKeys[chunkIndex - 1]) || JSON.stringify(chunkKeys) !== JSON.stringify([...chunkKeys].sort(compareCodePoint))) return false;
  if (!route.chunks.every(validChunk)) return false;
  const chunkNames = route.chunks.map((chunk) => chunk.logicalName);
  const bundleByFile = new Map((Array.isArray(bundle?.observations) ? bundle.observations : []).map((observation) => [observation.emittedFile, observation]));
  return new Set(chunkNames).size === chunkNames.length
    && JSON.stringify([...chunkNames].sort(compareCodePoint)) === JSON.stringify(route.loadedChunks)
    && route.transferBytes === route.chunks.reduce((sum, chunk) => sum + chunk.transferBytes, 0)
    && route.chunks.every((chunk) => {
      const observation = bundleByFile.get(chunk.emittedFile);
      return observation && observation.logicalName === chunk.logicalName && observation.rawBytes === chunk.rawBytes && observation.gzipBytes === chunk.gzipBytes && observation.gzipBytes === chunk.transferBytes && observation.status === chunk.policyStatus && observation.headroomBytes === chunk.headroomBytes;
    });
}

function validFixtureRoute(route, index) {
  const expectedId = MEASUREMENT_PROFILE.routes[index]?.id;
  if (!hasExactKeys(route, BASELINE_FIXTURE_ROUTE_KEYS) || route.id !== expectedId || !Array.isArray(route.requests) || route.requests.length === 0 || !isNonnegativeInteger(route.allowedPreviewPosts) || !isNonnegativeInteger(route.persistentWrites) || !isNonnegativeInteger(route.unexpectedRequests) || route.allowedPreviewPosts !== (route.id === "process" ? 1 : 0) || route.persistentWrites !== 0 || route.unexpectedRequests !== 0) return false;
  if (!route.requests.every((request) => hasExactKeys(request, BASELINE_REQUEST_KEYS) && (request.method === "GET" || request.method === "POST") && typeof request.path === "string" && request.path.startsWith("/api/v1/") && isPositiveInteger(request.count) && (request.method === "GET" || (route.id === "process" && request.path === "/api/v1/processing:preview")))) return false;
  const requestKeys = route.requests.map((request) => `${request.method}\u0000${request.path}`);
  const hasPreviewPost = route.requests.some((request) => request.method === "POST" && request.path === "/api/v1/processing:preview");
  return new Set(requestKeys).size === requestKeys.length && JSON.stringify(requestKeys) === JSON.stringify([...requestKeys].sort(compareCodePoint)) && (route.id === "process" ? hasPreviewPost : !hasPreviewPost);
}

function validFixture(fixture) {
  if (!hasExactKeys(fixture, BASELINE_FIXTURE_KEYS) || fixture.fixtureId !== "issue-189-synthetic-metal-v1" || typeof fixture.fixtureSha256 !== "string" || !SHA256_PATTERN.test(fixture.fixtureSha256) || fixture.nonProduction !== true || fixture.materialFamily !== "metal" || fixture.sessionStorageKey !== SESSION_STORAGE_KEY || !Array.isArray(fixture.routes) || fixture.routes.length !== 3) return false;
  return fixture.routes.every(validFixtureRoute);
}

function validBundle(bundle, policy) {
  if (!validObservationPolicy(policy) || !hasExactKeys(bundle, BASELINE_BUNDLE_KEYS) || !Array.isArray(bundle.observations) || bundle.observations.length === 0 || !hasExactKeys(bundle.summary, BASELINE_BUNDLE_SUMMARY_KEYS) || !bundle.observations.every(validBundleObservation) || !isNonnegativeInteger(bundle.summary.warningCount) || !isNonnegativeInteger(bundle.summary.errorCount) || !validLargest(bundle.summary.largestRaw) || !validLargest(bundle.summary.largestGzip)) return false;
  if (bundle.observations.filter((item) => item.kind === "entry").length !== 1) return false;
  if (bundle.observations.some((item) => {
    const budget = item.kind === "entry" ? policy.entry : policy.lazy;
    return item.warningBytes !== budget.warningBytes || item.errorBytes !== budget.errorBytes;
  })) return false;
  const keys = bundle.observations.map(sortBundleKey);
  if (new Set(keys).size !== keys.length || JSON.stringify(keys) !== JSON.stringify([...keys].sort(compareCodePoint))) return false;
  const warningCount = bundle.observations.filter((item) => item.status === "warning").length;
  const errorCount = bundle.observations.filter((item) => item.status === "error").length;
  const status = errorCount ? "error" : warningCount ? "warning" : "ok";
  if (bundle.summary.warningCount !== warningCount || bundle.summary.errorCount !== errorCount || bundle.summary.status !== status || errorCount !== 0) return false;
  const largestRaw = bundle.observations.reduce((largest, item) => !largest || item.rawBytes > largest.rawBytes ? item : largest, null);
  const largestGzip = bundle.observations.reduce((largest, item) => !largest || item.gzipBytes > largest.gzipBytes ? item : largest, null);
  const expectedLargest = (item, metric) => item ? { kind: item.kind, logicalName: item.logicalName, emittedFile: item.emittedFile, bytes: item[metric] } : null;
  return JSON.stringify(bundle.summary.largestRaw) === JSON.stringify(expectedLargest(largestRaw, "rawBytes")) && JSON.stringify(bundle.summary.largestGzip) === JSON.stringify(expectedLargest(largestGzip, "gzipBytes"));
}

export function validateBaseline(baseline) {
  const failures = [];
  if (!isRecord(baseline) || baseline.schemaVersion !== baselineSchemaVersion) failures.push(diagnostic("BASELINE_SCHEMA", "schemaVersion", "baseline schemaVersion is invalid"));
  if (!hasExactKeys(baseline, BASELINE_TOP_KEYS)) failures.push(diagnostic("BASELINE_SCHEMA", "baseline", "baseline envelope fields are invalid"));
  if (!hasExactKeys(baseline?.updatePolicy, BASELINE_POLICY_KEYS)
    || baseline.updatePolicy.authority !== "product_owner"
    || baseline.updatePolicy.automaticWritesAllowed !== false
    || baseline.updatePolicy.method !== "append_reviewed_accepted_main_observation"
    || baseline.updatePolicy.compareCommand !== baselineCompareCommand) {
    failures.push(diagnostic("BASELINE_SCHEMA", "updatePolicy", "baseline update policy is invalid"));
  }
  if (!Array.isArray(baseline?.observations)) failures.push(diagnostic("BASELINE_SCHEMA", "observations", "baseline observations must be an array"));
  if (failures.some((failure) => failure.code === "BASELINE_SCHEMA" && ["schemaVersion", "baseline", "updatePolicy", "observations"].includes(failure.field))) {
    if (!Array.isArray(baseline?.observations)) return sortDiagnostics(failures);
  }
  const observations = baseline.observations;
  if (observations.length === 0) failures.push(diagnostic("BASELINE_OBSERVATION", "observations", "baseline observations must not be empty"));
  const sequences = observations.map((item) => item?.sequence);
  if (sequences.some((value, index) => !Number.isInteger(value) || value !== index + 1)) failures.push(diagnostic("BASELINE_SEQUENCE", "observations.sequence", "baseline sequence must start at one and increase by one"));
  const accepted = observations.map((item) => item?.acceptedMainSha);
  if (accepted.some((value) => typeof value !== "string" || !SHA1_PATTERN.test(value))) failures.push(diagnostic("BASELINE_SHA", "observations.acceptedMainSha", "accepted main SHA values must be 40 lowercase hexadecimal characters"));
  if (new Set(accepted).size !== accepted.length) failures.push(diagnostic("BASELINE_SHA", "observations.acceptedMainSha", "accepted main SHA values must not repeat"));
  for (const [index, item] of observations.entries()) {
    const prefix = `observations[${index}]`;
    if (!hasExactKeys(item, BASELINE_OBSERVATION_KEYS)) failures.push(diagnostic("BASELINE_OBSERVATION", prefix, "baseline observation fields are invalid or incomplete"));
    if (item?.policy?.overrideActive) failures.push(diagnostic("BASELINE_OBSERVATION", `${prefix}.policy.overrideActive`, "baseline observations with active overrides are not accepted"));
    if (typeof item?.buildFingerprintSha256 !== "string" || !SHA256_PATTERN.test(item.buildFingerprintSha256 ?? "") || !validProfile(item?.profile) || typeof item?.measurementProfileSha256 !== "string" || !SHA256_PATTERN.test(item?.measurementProfileSha256 ?? "") || item.measurementProfileSha256 !== measurementProfileSha256(item.profile) || typeof item?.harnessSha256 !== "string" || !SHA256_PATTERN.test(item?.harnessSha256 ?? "") || !validEnvironment(item?.environment, item?.profile) || !validObservationPolicy(item?.policy) || !validBundle(item?.bundle, item?.policy) || !validFixture(item?.fixture) || !Array.isArray(item?.routes)) {
      failures.push(diagnostic("BASELINE_OBSERVATION", prefix, "baseline observation is missing full report fields"));
    }
    if (item?.fixture && (!hasExactKeys(item.fixture, BASELINE_FIXTURE_KEYS) || typeof item.fixture.fixtureSha256 !== "string" || !SHA256_PATTERN.test(item.fixture.fixtureSha256) || !Array.isArray(item.fixture.routes))) {
      failures.push(diagnostic("BASELINE_OBSERVATION", `${prefix}.fixture`, "baseline fixture is missing full fields"));
    }
    if (item?.bundle && (!hasExactKeys(item.bundle, BASELINE_BUNDLE_KEYS) || !Array.isArray(item.bundle.observations) || !hasExactKeys(item.bundle.summary, BASELINE_BUNDLE_SUMMARY_KEYS))) {
      failures.push(diagnostic("BASELINE_OBSERVATION", `${prefix}.bundle`, "baseline bundle is missing full fields"));
    }
    const routeRows = Array.isArray(item?.routes) ? item.routes : [];
    const routeIds = routeRows.map((route) => route?.id);
    if (JSON.stringify(routeIds) !== JSON.stringify(MEASUREMENT_PROFILE.routes.map((route) => route.id))) failures.push(diagnostic("BASELINE_SORT", `observations[${index}].routes`, "baseline routes are not in Process/Fit/Export order"));
    const bundleObservations = Array.isArray(item?.bundle?.observations) ? item.bundle.observations : [];
    const bundleSorted = [...bundleObservations].sort((left, right) => {
      if ((left?.kind ?? "") !== (right?.kind ?? "")) return left?.kind === "entry" ? -1 : 1;
      return compareCodePoint(String(left?.logicalName ?? ""), String(right?.logicalName ?? "")) || compareCodePoint(String(left?.emittedFile ?? ""), String(right?.emittedFile ?? ""));
    });
    if (JSON.stringify(bundleObservations.map((value) => `${value?.kind ?? ""}\u0000${value?.logicalName ?? ""}\u0000${value?.emittedFile ?? ""}`)) !== JSON.stringify(bundleSorted.map((value) => `${value?.kind ?? ""}\u0000${value?.logicalName ?? ""}\u0000${value?.emittedFile ?? ""}`))) failures.push(diagnostic("BASELINE_SORT", `observations[${index}].bundle.observations`, "baseline bundle observations are not sorted"));
    for (const [bundleIndex, observation] of bundleObservations.entries()) {
      if (!validBundleObservation(observation)) failures.push(diagnostic("BASELINE_OBSERVATION", `${prefix}.bundle.observations[${bundleIndex}]`, "baseline bundle observation is incomplete or inconsistent"));
    }
    for (const [routeIndex, route] of routeRows.entries()) {
      const chunkRows = Array.isArray(route?.chunks) ? route.chunks : [];
      const chunkNames = chunkRows.map((chunk) => `${chunk?.logicalName ?? ""}\u0000${chunk?.emittedFile ?? ""}`);
      if (JSON.stringify(chunkNames) !== JSON.stringify([...chunkNames].sort(compareCodePoint))) failures.push(diagnostic("BASELINE_SORT", `routes.${route?.id ?? "?"}.chunks`, "baseline chunks are not sorted"));
      if (!validRouteRow(route, routeIndex, item?.bundle)) failures.push(diagnostic("BASELINE_OBSERVATION", `${prefix}.routes.${route?.id ?? "?"}`, "baseline route is missing full fields or has inconsistent metrics"));
      for (const [chunkIndex, chunk] of chunkRows.entries()) {
        if (!validChunk(chunk)) failures.push(diagnostic("BASELINE_OBSERVATION", `${prefix}.routes.${route?.id ?? "?"}.chunks[${chunkIndex}]`, "baseline route chunk is missing full fields or has inconsistent metrics"));
      }
    }
    const fixtureRouteRows = Array.isArray(item?.fixture?.routes) ? item.fixture.routes : [];
    for (const [fixtureRouteIndex, route] of fixtureRouteRows.entries()) {
      if (!validFixtureRoute(route, fixtureRouteIndex)) failures.push(diagnostic("BASELINE_OBSERVATION", `${prefix}.fixture.routes.${route?.id ?? "?"}`, "baseline fixture route is missing full fields or has inconsistent request accounting"));
      const requests = Array.isArray(route?.requests) ? route.requests : [];
      const sortedRequests = [...requests].sort((left, right) => compareCodePoint(String(left?.method ?? ""), String(right?.method ?? "")) || compareCodePoint(String(left?.path ?? ""), String(right?.path ?? "")));
      if (JSON.stringify(requests) !== JSON.stringify(sortedRequests)) failures.push(diagnostic("BASELINE_SORT", `observations[${index}].fixture.routes.${route?.id ?? "?"}.requests`, "baseline fixture requests are not sorted"));
    }
  }
  return sortDiagnostics(failures);
}

export function compareReport(current, baseline) {
  const malformed = validateBaseline(baseline);
  if (malformed.length) return createComparison("invalid_baseline", { diagnostics: malformed });
  const previous = baseline.observations.at(-1);
  const diagnostics = [];
  const overrideActive = current.policy.overrideActive || previous.policy?.overrideActive;
  if (overrideActive) diagnostics.push(diagnostic("POLICY_OVERRIDE_ACTIVE", "policy.overrideActive", "policy overrides make the observation not comparable"));
  if (canonicalJson(current.environment) !== canonicalJson(previous.environment)) diagnostics.push(diagnostic("ENVIRONMENT_MISMATCH", "environment", "measurement environments differ"));
  if (current.measurementProfileSha256 !== previous.measurementProfileSha256 || canonicalJson(current.profile) !== canonicalJson(previous.profile)) diagnostics.push(diagnostic("PROFILE_MISMATCH", "measurementProfileSha256", "measurement profiles differ"));
  if (current.harnessSha256 !== previous.harnessSha256) diagnostics.push(diagnostic("HARNESS_MISMATCH", "harnessSha256", "measurement harness or fixture bytes differ"));
  if (current.fixture?.fixtureSha256 !== previous.fixture?.fixtureSha256) diagnostics.push(diagnostic("FIXTURE_MISMATCH", "fixture.fixtureSha256", "fixture bytes differ"));
  if (canonicalJson(current.policy) !== canonicalJson(previous.policy)) diagnostics.push(diagnostic("POLICY_MISMATCH", "policy", "bundle policies differ"));
  if (diagnostics.length) return createComparison("not_comparable", { baselineSequence: previous.sequence, diagnostics });
  const candidates = compareRoutes(current.routes, previous.routes);
  return createComparison(candidates.length ? "comparable_candidate_regression" : "comparable_no_regression", { baselineSequence: previous.sequence, routeCandidates: candidates });
}

/** Evaluate the prospective common-chunk trend without treating gzip as policy. */
export function evaluateTrend(observations) {
  const commonRaw = (item) => item?.bundle?.observations?.find((value) => value.logicalName === "common-processing-workbench")?.rawBytes ?? null;
  const commonStatus = (item) => item?.bundle?.observations?.find((value) => value.logicalName === "common-processing-workbench")?.status ?? null;
  const raw = observations.map(commonRaw);
  const statuses = observations.map(commonStatus);
  const immediateError = raw.at(-1) !== null && raw.at(-1) > 131_000;
  const twoConsecutiveStatus = statuses.length >= 2 && [statuses.at(-2), statuses.at(-1)].every((value) => value === "warning" || value === "error");
  let persistentGrowth = false;
  if (observations.length >= 3 && raw.slice(-3).every((value) => typeof value === "number")) {
    const [first, second, third] = raw.slice(-3);
    const firstDelta = second - first;
    const secondDelta = third - second;
    const statusWindow = statuses.slice(-3);
    persistentGrowth = statusWindow.length === 3 && statusWindow.every((status) => status === "ok") && first > 0 && second > 0 && firstDelta >= 1024 && secondDelta >= 1024 && firstDelta / first >= 0.01 && secondDelta / second >= 0.01;
  }
  return { immediateError, twoConsecutiveStatus, persistentGrowth, splitTrigger: immediateError || twoConsecutiveStatus || persistentGrowth };
}

export const trendDecision = evaluateTrend;

export function appendBaselineObservation(baseline, report) {
  const failures = validateBaseline(baseline);
  if (failures.length) throw new ModelingRouteMeasurementError("PROFILE", "cannot append to malformed baseline");
  if (report.policy.overrideActive) throw new ModelingRouteMeasurementError("PROFILE", "active policy overrides cannot be baselined");
  const previous = baseline.observations.at(-1);
  if (previous?.acceptedMainSha === report.sourceSha) throw new ModelingRouteMeasurementError("PROFILE", "accepted main SHA must not repeat");
  const observation = { ...observationWithoutEnvelope(report), sequence: baseline.observations.length + 1, acceptedMainSha: report.sourceSha };
  return { ...baseline, observations: [...baseline.observations, observation] };
}

function routeProfile(id) { return MEASUREMENT_PROFILE.routes.find((route) => route.id === id); }
function staticFileType(pathname) { return pathname.endsWith(".js") ? "text/javascript; charset=utf-8" : pathname.endsWith(".css") ? "text/css; charset=utf-8" : pathname.endsWith(".html") ? "text/html; charset=utf-8" : "application/octet-stream"; }

async function startFixtureServer({ distDir, fixture }) {
  const server = createServer(async (request, response) => {
    const parsed = new URL(request.url ?? "/", "http://127.0.0.1");
    const pathname = decodeURIComponent(parsed.pathname);
    if (pathname.startsWith("/api/v1/")) {
      const chunks = [];
      for await (const chunk of request) chunks.push(chunk);
      fixture.state.pending += 1;
      fixture.state.pendingRequests = fixture.state.pending;
      let result;
      try { result = await fixture.handle({ method: request.method ?? "GET", path: `${pathname}${parsed.search}`, body: Buffer.concat(chunks).toString("utf8") }); }
      finally { fixture.state.pending -= 1; fixture.state.pendingRequests = fixture.state.pending; }
      response.statusCode = result.status;
      response.setHeader("content-type", result.contentType ?? "application/json");
      response.setHeader("cache-control", "no-store");
      for (const [name, value] of Object.entries(result.headers ?? {})) response.setHeader(name, value);
      const body = Buffer.isBuffer(result.body) ? result.body : Buffer.from(String(result.body ?? ""));
      response.setHeader("content-length", body.byteLength);
      response.end(body);
      return;
    }
    let filePath = resolve(distDir, `.${pathname}`);
    if (!filePath.startsWith(resolve(distDir))) filePath = resolve(distDir, "index.html");
    try { const info = await stat(filePath); if (!info.isFile()) throw new Error("not a file"); }
    catch { filePath = resolve(distDir, "index.html"); }
    try {
      const raw = await readFile(filePath);
      response.statusCode = 200;
      response.setHeader("cache-control", "no-store");
      response.setHeader("content-type", staticFileType(filePath));
      if (filePath.endsWith(".js")) {
        const compressed = gzipSync(raw, { level: 9 });
        response.setHeader("content-encoding", "gzip");
        response.setHeader("content-length", compressed.byteLength);
        response.end(compressed);
      } else { response.setHeader("content-length", raw.byteLength); response.end(raw); }
    } catch { response.statusCode = 404; response.end("not found"); }
  });
  await new Promise((resolvePromise) => server.listen(0, "127.0.0.1", resolvePromise));
  const address = server.address();
  if (!address || typeof address === "string") throw new ModelingRouteMeasurementError("SERVER", "fixture server did not expose a TCP port");
  return { server, origin: `http://127.0.0.1:${address.port}` };
}

function resourceFile(url) {
  try {
    const match = new URL(String(url), "http://127.0.0.1").pathname.match(/^\/assets\/([^/]+\.js)$/);
    return match?.[1] ?? null;
  } catch {
    return null;
  }
}

async function readTracingStream(cdp, stream) {
  const parts = [];
  while (true) {
    const result = await cdp.send("IO.read", { handle: stream });
    if (result.data) parts.push(result.data);
    if (result.eof) break;
  }
  await cdp.send("IO.close", { handle: stream }).catch(() => undefined);
  try { return JSON.parse(parts.join("")); } catch { return { traceEvents: [] }; }
}

export function parseTraceMetrics(trace, cpuProfile = null) {
  const events = Array.isArray(trace) ? trace : trace?.traceEvents ?? [];
  const parseByFile = {};
  let parseMs = 0;
  for (const event of events) {
    if (!event || !["v8.parseOnBackground", "v8.compileModule"].includes(event.name)) continue;
    const data = event.args?.data ?? event.args ?? {};
    const file = resourceFile(data.url ?? data.scriptUrl ?? data.file ?? "");
    if (!file) continue;
    const value = Number(event.dur ?? 0) / 1000;
    parseMs += value;
    parseByFile[file] = (parseByFile[file] ?? 0) + value;
  }
  const cpuByFile = {};
  const cpuNodeCountByFile = {};
  const cpuFiles = new Set();
  const profile = cpuProfile?.profile ?? cpuProfile;
  if (Array.isArray(profile?.nodes)) {
    for (const node of profile.nodes) {
      const file = resourceFile(node?.callFrame?.url ?? "");
      if (!file) continue;
      cpuFiles.add(file);
      cpuNodeCountByFile[file] = (cpuNodeCountByFile[file] ?? 0) + 1;
    }
  }
  if (Array.isArray(profile?.nodes) && Array.isArray(profile.samples)) {
    const nodeById = new Map(profile.nodes.map((node) => [node.id, node]));
    for (const nodeId of profile.samples) {
      const node = nodeById.get(nodeId);
      const file = resourceFile(node?.callFrame?.url ?? "");
      if (file) cpuByFile[file] = (cpuByFile[file] ?? 0) + 0.1;
    }
  }
  return { parseMs, parseByFile, cpuByFile, cpuFiles, cpuNodeCountByFile };
}

function cpuProfileHasSamples(cpuProfile) {
  const profile = cpuProfile?.profile ?? cpuProfile;
  return Boolean(profile && Array.isArray(profile.nodes) && profile.nodes.length > 0 && Array.isArray(profile.samples) && profile.samples.length > 0);
}

function metricDelta(before, after, name) {
  const beforeMetric = before?.metrics?.find((item) => item.name === name);
  const afterMetric = after?.metrics?.find((item) => item.name === name);
  if (!beforeMetric || !afterMetric || !hasFiniteNumber(Number(beforeMetric.value)) || !hasFiniteNumber(Number(afterMetric.value))) {
    throw new ModelingRouteMeasurementError("TRACE", `Performance.${name} metric is required before and after the route`);
  }
  return Number(afterMetric.value) - Number(beforeMetric.value);
}

export function scriptDurationDelta(before, after) {
  return metricDelta(before, after, "ScriptDuration");
}

export function validateTraceAttribution({ route, bundle, trace, profile, traceMetrics }) {
  if (!(trace?.traceEvents?.length > 0)) throw new ModelingRouteMeasurementError("TRACE", `${route.id} produced no trace events`);
  if (!cpuProfileHasSamples(profile)) throw new ModelingRouteMeasurementError("TRACE", `${route.id} produced no CPU profile samples`);
  const common = bundle?.observations?.find((item) => item.logicalName === "common-processing-workbench");
  if (!common || !(traceMetrics?.parseByFile?.[common.emittedFile] > 0)) throw new ModelingRouteMeasurementError("TRACE", `${route.id} lacks required common-processing-workbench parse attribution`);
  for (const requiredLogicalName of route.requiredChunks ?? []) {
    const required = bundle.observations.find((item) => item.logicalName === requiredLogicalName);
    const hasNodeAttribution = Boolean(required && (
      traceMetrics?.cpuFiles?.has?.(required.emittedFile)
      || Object.prototype.hasOwnProperty.call(traceMetrics?.cpuNodeCountByFile ?? {}, required.emittedFile)
    ));
    if (!hasNodeAttribution) throw new ModelingRouteMeasurementError("TRACE", `${route.id} lacks required CPU node attribution for ${requiredLogicalName}`);
  }
  return true;
}

async function readinessContext(page) {
  const snapshot = await page.evaluate(() => {
    const surface = document.querySelector(".processing-workbench-page");
    return {
      alerts: [...document.querySelectorAll('[role="alert"]')].map((item) => item.textContent?.trim() ?? "").filter(Boolean),
      stateParts: surface ? [surface.className, surface.getAttribute("data-state"), surface.getAttribute("aria-busy")].filter(Boolean) : [],
      bodyText: document.body?.innerText ?? "",
    };
  }).catch(() => ({ alerts: [], stateParts: [], bodyText: "page unavailable" }));
  const state = [snapshot.stateParts.join(" "), snapshot.bodyText.replace(/\s+/g, " ").trim().slice(0, 240)].filter(Boolean).join(" | ") || "unknown";
  return `alerts: ${snapshot.alerts.length ? snapshot.alerts.join(" | ") : "none"}; state: ${state}`;
}

async function waitRouteVisible(page, route, selector, label = selector) {
  try {
    if (selector.startsWith("text=")) await page.getByText(selector.slice(5), { exact: false }).waitFor({ state: "visible", timeout: MEASUREMENT_PROFILE.timeoutMs });
    else await page.locator(selector).first().waitFor({ state: "visible", timeout: MEASUREMENT_PROFILE.timeoutMs });
  } catch (error) {
    const context = await readinessContext(page);
    throw new ModelingRouteMeasurementError("READINESS", `${route.id} ${label} did not become visible: ${error instanceof Error ? error.message : String(error)}; ${context}`);
  }
}

async function waitReady(page, route) {
  for (const selector of route.readinessSelectors) await waitRouteVisible(page, route, selector);
}

async function measureSample({ origin, route, fixture, bundle }) {
  fixture.setRoute(route.id);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: MEASUREMENT_PROFILE.browser.viewport, deviceScaleFactor: 1, locale: "en-US", colorScheme: "light", reducedMotion: "reduce", serviceWorkers: "block" });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  try {
    await cdp.send("Network.enable");
    await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
    await cdp.send("Network.emulateNetworkConditions", { offline: false, downloadThroughput: MEASUREMENT_PROFILE.network.downloadBitsPerSecond / 8, uploadThroughput: MEASUREMENT_PROFILE.network.uploadBitsPerSecond / 8, latency: MEASUREMENT_PROFILE.network.latencyMs });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: MEASUREMENT_PROFILE.cpu.throttleRate });
    await cdp.send("Performance.enable");
    const before = await cdp.send("Performance.getMetrics");
    await cdp.send("Profiler.enable");
    await cdp.send("Profiler.setSamplingInterval", { interval: MEASUREMENT_PROFILE.cpu.profilerSampleIntervalUs });
    await cdp.send("Profiler.start");
    let traceComplete;
    const tracePromise = new Promise((resolvePromise) => { traceComplete = resolvePromise; });
    cdp.on("Tracing.tracingComplete", (event) => traceComplete(event.stream));
    await cdp.send("Tracing.start", { categories: MEASUREMENT_PROFILE.categories.join(","), transferMode: "ReturnAsStream" });
    await context.addInitScript(({ key, value }) => { window.sessionStorage.setItem(key, JSON.stringify(value)); }, { key: SESSION_STORAGE_KEY, value: modelingSession(route.id) });
    await page.goto(`${origin}${route.path}`, { waitUntil: "domcontentloaded", timeout: MEASUREMENT_PROFILE.timeoutMs });
    if (route.id === "fit") {
      await waitRouteVisible(page, route, "button.fit-evidence-trigger", "Fit evidence trigger");
      await waitRouteVisible(page, route, ".fit-surface-state-saved-current", "saved Fit state");
      await waitRouteVisible(page, route, "svg.processing-curve polyline.curve-line", "Fit processing curve");
      const trigger = page.locator("button.fit-evidence-trigger").first();
      await trigger.click();
    }
    await waitReady(page, route);
    await page.evaluate(() => document.fonts?.ready ?? Promise.resolve());
    await page.waitForTimeout(MEASUREMENT_PROFILE.settleMs);
    for (const selector of route.readinessSelectors) await waitRouteVisible(page, route, selector);
    if (await page.locator('[role="alert"]').count()) {
      const alertText = await page.locator('[role="alert"]').allTextContents();
      throw new ModelingRouteMeasurementError("READINESS", `${route.id} exposed an alert after settle: ${alertText.join(" | ")}`);
    }
    if (fixture.state.pending !== 0) throw new ModelingRouteMeasurementError("FIXTURE", `${route.id} retained pending fixture requests`);
    if (route.id === "process" && fixture.state.previewPosts !== 1) throw new ModelingRouteMeasurementError("FIXTURE", "Process must issue exactly one preview POST per cold sample");
    if (route.id !== "process" && fixture.state.previewPosts !== 0) throw new ModelingRouteMeasurementError("FIXTURE", `${route.id} issued a preview POST`);
    const resources = await page.evaluate(() => performance.getEntriesByType("resource").map((entry) => ({ name: entry.name, startTime: entry.startTime, duration: entry.duration, encodedBodySize: entry.encodedBodySize })));
    const jsResources = resources.filter((resource) => resource.name.includes("/assets/") && resource.name.endsWith(".js"));
    const resourceRows = jsResources.map((resource) => ({ emittedFile: resourceFile(resource.name), transferBytes: resource.encodedBodySize, transferDurationMs: resource.duration, startTime: resource.startTime }));
    for (const resource of resourceRows) {
      const observation = lookupObservation(bundle, resource.emittedFile);
      if (!observation || observation.gzipBytes !== resource.transferBytes) throw new ModelingRouteMeasurementError("RESOURCE", `ResourceTiming gzip mismatch for ${resource.emittedFile ?? resource.name}`);
    }
    const loadedChunks = sortStrings(resourceRows.map((resource) => lookupObservation(bundle, resource.emittedFile)?.logicalName).filter(Boolean));
    for (const required of route.requiredChunks) if (!loadedChunks.includes(required)) throw new ModelingRouteMeasurementError("READINESS", `${route.id} did not load required chunk ${required}`);
    const transferBytes = resourceRows.reduce((sum, resource) => sum + resource.transferBytes, 0);
    const start = Math.min(...resourceRows.map((resource) => resource.startTime));
    const end = Math.max(...resourceRows.map((resource) => resource.startTime + resource.transferDurationMs));
    const after = await cdp.send("Performance.getMetrics");
    const profile = await cdp.send("Profiler.stop");
    await cdp.send("Performance.disable").catch(() => undefined);
    await cdp.send("Tracing.end");
    const stream = await tracePromise;
    const trace = stream ? await readTracingStream(cdp, stream) : { traceEvents: [] };
    const traceMetrics = parseTraceMetrics(trace, profile);
    validateTraceAttribution({ route, bundle, trace, profile, traceMetrics });
    const parseByFile = traceMetrics.parseByFile;
    const chunks = joinChunkMetrics({ bundle, resources: resourceRows.map((resource) => ({ ...resource, duration: resource.transferDurationMs })), parseByFile, cpuByFile: traceMetrics.cpuByFile });
    return { loadedChunks, transferBytes, transferSpanMs: end - start, parseMs: traceMetrics.parseMs, executeMs: scriptDurationDelta(before, after) * 1000, chunks };
  } catch (error) {
    if (error instanceof ModelingRouteMeasurementError) throw error;
    throw new ModelingRouteMeasurementError("READINESS", error instanceof Error ? `${error.message}${error.stack ? ` @ ${error.stack.split("\\n")[1] ?? ""}` : ""}` : String(error));
  } finally {
    await context.close().catch(() => undefined);
    await browser.close().catch(() => undefined);
  }
}

export async function measureRoutes({ distDir = resolve(repository, "apps", "web", "dist"), assetsDir = join(distDir, "assets"), sampleCount = 5 } = {}) {
  if (!existsSync(join(distDir, "index.html"))) throw new ModelingRouteMeasurementError("DIST", `production dist is unavailable: ${distDir}`);
  if (sampleCount !== 5) throw new ModelingRouteMeasurementError("PROFILE", "profile requires five samples");
  const bundle = await collectBundleBudget({ assetsDir, env: process.env });
  const fingerprint = await fingerprintBuild(assetsDir);
  const fixture = createModelingFixture();
  const serverInfo = await startFixtureServer({ distDir, fixture });
  const routes = [];
  let browserVersion = "unknown";
  try {
    const probe = await chromium.launch({ headless: true });
    browserVersion = probe.version();
    await probe.close();
    for (const route of MEASUREMENT_PROFILE.routes) {
      const samples = [];
      for (let sample = 0; sample < 5; sample += 1) samples.push(await measureSample({ origin: serverInfo.origin, route, fixture, bundle }));
      routes.push(aggregateRouteSamples(route, samples, bundle));
    }
  } finally { await new Promise((resolvePromise) => serverInfo.server.close(resolvePromise)); }
  if (fixture.state.pending !== 0 || fixture.state.persistentWrites !== 0 || fixture.state.unexpectedRequests !== 0) throw new ModelingRouteMeasurementError("FIXTURE", "fixture completed with pending, durable, or unexpected requests");
  const hashes = await integrityHashes();
  const summary = fixture.routeSummary();
  summary.fixtureSha256 = hashes.fixtureSha256;
  return {
    fingerprint,
    bundle,
    routes,
    fixture: summary,
    environment: environmentSnapshot(browserVersion),
  };
}

export function currentReport({ sourceSha, fingerprintSha256, profileHash, hashes, measured, comparison = createComparison() }) {
  return {
    schemaVersion: "cmp.web-modeling-route.v1",
    sourceSha,
    buildFingerprintSha256: fingerprintSha256,
    profile: MEASUREMENT_PROFILE,
    measurementProfileSha256: profileHash,
    harnessSha256: hashes.harnessSha256,
    environment: measured.environment,
    policy: policyFromBundle(measured.bundle),
    bundle: bundleSnapshot(measured.bundle),
    fixture: measured.fixture,
    routes: measured.routes,
    comparison,
  };
}

function gitSourceSha() {
  try { const value = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repository, encoding: "utf8" }).trim(); if (!/^[0-9a-f]{40}$/.test(value)) throw new Error("invalid SHA"); return value; } catch { throw new ModelingRouteMeasurementError("SOURCE_SHA", "git HEAD is not a 40-character lowercase SHA"); }
}

function invokedDirectly() { return process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url; }

function normalizeBaselinePath(value) {
  return relative(repository, resolve(repository, value)).replaceAll("\\", "/") || ".";
}

export async function run(argv = process.argv.slice(2)) {
  const compareIndex = argv.indexOf("--compare");
  const baselinePath = compareIndex >= 0 ? argv[compareIndex + 1] : null;
  if (compareIndex >= 0 && !baselinePath) throw new ModelingRouteMeasurementError("PROFILE", "--compare requires a baseline path");
  const sourceSha = gitSourceSha();
  const measured = await measureRoutes();
  const profileHash = measurementProfileSha256();
  const hashes = await integrityHashes();
  let report = currentReport({ sourceSha, fingerprintSha256: measured.fingerprint.sha256, profileHash, hashes, measured });
  if (baselinePath) {
    const normalizedBaselinePath = normalizeBaselinePath(baselinePath);
    let baseline;
    try { baseline = JSON.parse(await readFile(resolve(repository, normalizedBaselinePath), "utf8")); } catch { baseline = null; }
    report.comparison = { ...compareReport(report, baseline), baselinePath: normalizedBaselinePath };
    process.stdout.write(`${JSON.stringify(report)}\n`);
    if (report.comparison.status === "invalid_baseline") process.exitCode = 1;
    return report;
  }
  report.comparison = createComparison();
  process.stdout.write(`${JSON.stringify(report)}\n`);
  return report;
}

export async function main() {
  try { return await run(); }
  catch (error) {
    const failure = error instanceof ModelingRouteMeasurementError ? error : new ModelingRouteMeasurementError("SERVER", error instanceof Error ? error.message : String(error));
    process.stderr.write(`ModelingRouteMeasurementError[${failure.code}]: ${failure.message}\n`);
    process.exitCode = 1;
    return null;
  }
}

if (invokedDirectly()) await main();
