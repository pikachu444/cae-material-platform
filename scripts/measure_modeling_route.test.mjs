import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { test } from "node:test";

import {
  MEASUREMENT_PROFILE,
  aggregateRouteSamples,
  canonicalJson,
  compareReport,
  compareRoutes,
  createBaselineEnvelope,
  createComparison,
  evaluateTrend,
  fingerprintBuild,
  integrityHashes,
  joinChunkMetrics,
  median,
  measurementProfileSha256,
  parseTraceMetrics,
  roundMilliseconds,
  sha256,
  scriptDurationDelta,
  validateTraceAttribution,
  validateBaseline,
} from "./measure_modeling_route.mjs";
import { collectBundleBudget } from "./check_web_bundle.mjs";
import { createModelingFixture, mappingProfile, ROUTES, testDataContent } from "./fixtures/modeling_route_fixture.mjs";

test("canonical profile hashes are stable and arrays retain order", () => {
  assert.equal(canonicalJson({ b: 1, a: { d: 2, c: 3 }, list: [2, 1] }), '{"a":{"c":3,"d":2},"b":1,"list":[2,1]}');
  assert.equal(sha256(Buffer.from(canonicalJson(MEASUREMENT_PROFILE))), sha256(Buffer.from(canonicalJson(MEASUREMENT_PROFILE))));
  assert.equal(MEASUREMENT_PROFILE.sampleCount, 5);
  assert.deepEqual(MEASUREMENT_PROFILE.regressionOrder, ["requiredChunks", "transferBytes", "transferSpanMs", "parseMs", "executeMs"]);
});

test("median and post-median millisecond rounding are deterministic", () => {
  assert.equal(median([9, 1, 5, 3, 7]), 5);
  assert.equal(roundMilliseconds(1.23456), 1.235);
  assert.throws(() => median([1, 2]), /odd/);
});

test("joins chunk rows and aggregates five cold samples", async () => {
  const assets = await mkdtemp(join(tmpdir(), "cmp-measure-"));
  await writeFile(join(assets, "index-abcdefgh.js"), "index");
  await writeFile(join(assets, "common-processing-workbench-12345678.js"), "common");
  const bundle = await collectBundleBudget({ assetsDir: assets, env: {} });
  const joined = joinChunkMetrics({ bundle, resources: [{ emittedFile: "index-abcdefgh.js", transferBytes: 10, transferDurationMs: 1 }, { emittedFile: "common-processing-workbench-12345678.js", transferBytes: 20, transferDurationMs: 2 }], parseByFile: { "index-abcdefgh.js": 0.5 }, cpuByFile: {} });
  assert.equal(joined.length, 2);
  const route = MEASUREMENT_PROFILE.routes[0];
  const samples = Array.from({ length: 5 }, (_, index) => ({ loadedChunks: ["index", "common-processing-workbench"], transferBytes: 30 + index, transferSpanMs: 3 + index / 10, parseMs: 1 + index / 10, executeMs: 2 + index / 10, chunks: joined }));
  const aggregate = aggregateRouteSamples(route, samples, bundle);
  assert.equal(aggregate.sampleCount, 5);
  assert.equal(aggregate.transferBytes, 32);
  assert.deepEqual(aggregate.loadedChunks, ["common-processing-workbench", "index"]);
});

test("fingerprint is filename-sorted and content-sensitive", async () => {
  const first = await mkdtemp(join(tmpdir(), "cmp-fingerprint-"));
  await writeFile(join(first, "z-12345678.js"), "z");
  await writeFile(join(first, "a-12345678.js"), "a");
  const one = await fingerprintBuild(first);
  const second = await mkdtemp(join(tmpdir(), "cmp-fingerprint-"));
  await writeFile(join(second, "a-12345678.js"), "a");
  await writeFile(join(second, "z-12345678.js"), "z");
  const two = await fingerprintBuild(second);
  assert.equal(one.sha256, two.sha256);
  await writeFile(join(second, "z-12345678.js"), "changed");
  assert.notEqual(one.sha256, (await fingerprintBuild(second)).sha256);
});

test("integrity hashes are byte-sensitive and profile hashing is canonical", async () => {
  const root = await mkdtemp(join(tmpdir(), "cmp-integrity-"));
  const script = join(root, "harness.mjs");
  const fixture = join(root, "fixture.mjs");
  await writeFile(script, "script-a"); await writeFile(fixture, "fixture-a");
  const first = await integrityHashes({ script, fixture });
  await writeFile(script, "script-b");
  const second = await integrityHashes({ script, fixture });
  assert.notEqual(first.harnessSha256, second.harnessSha256);
  await writeFile(fixture, "fixture-b");
  const third = await integrityHashes({ script, fixture });
  assert.notEqual(second.harnessSha256, third.harnessSha256);
  assert.notEqual(first.fixtureSha256, third.fixtureSha256);
  assert.equal(measurementProfileSha256(), sha256(Buffer.from(canonicalJson(MEASUREMENT_PROFILE))));
});

test("joining rejects an asset absent from the bundle and aggregation rejects changed chunk sets", async () => {
  const assets = await mkdtemp(join(tmpdir(), "cmp-join-"));
  await writeFile(join(assets, "index-abcdefgh.js"), "index");
  const bundle = await collectBundleBudget({ assetsDir: assets, env: {} });
  assert.throws(() => joinChunkMetrics({ bundle, resources: [{ emittedFile: "missing-12345678.js", transferBytes: 1, transferDurationMs: 1 }] }), (error) => error.code === "RESOURCE");
  const route = MEASUREMENT_PROFILE.routes[0];
  const sample = { loadedChunks: ["common-processing-workbench"], transferBytes: 1, transferSpanMs: 1, parseMs: 1, executeMs: 1, chunks: [{ logicalName: "common-processing-workbench", emittedFile: "common-processing-workbench-12345678.js", rawBytes: 1, gzipBytes: 1, policyStatus: "ok", headroomBytes: 1, transferBytes: 1, transferDurationMs: 1, parseMs: 1, sampledCpuMs: 1 }] };
  const samples = Array.from({ length: 5 }, () => structuredClone(sample));
  samples[4].loadedChunks = ["changed"];
  assert.throws(() => aggregateRouteSamples(route, samples, bundle), (error) => error.code === "TRACE");
  samples[4].loadedChunks = sample.loadedChunks;
  samples[4].chunks[0].emittedFile = "other-12345678.js";
  assert.throws(() => aggregateRouteSamples(route, samples, bundle), (error) => error.code === "TRACE");
});

function report(overrides = {}) {
  const policy = { measurement: "raw_bytes", gzip: "observation_only_node_zlib_level_9", overrideActive: false, activeOverrides: [], entry: { warningBytes: 285000, errorBytes: 300000, warningPurpose: "review growth before the hard entry ceiling", errorPurpose: "fail the production build" }, lazy: { warningBytes: 128000, errorBytes: 131000, warningPurpose: "start prospective Workbench trend review", errorPurpose: "fail the production build" }, overrideNames: { entryWarning: "CMP_WEB_ENTRY_WARNING_BYTES", entryError: "CMP_WEB_ENTRY_BUDGET_BYTES", lazyWarning: "CMP_WEB_LAZY_CHUNK_WARNING_BYTES", lazyError: "CMP_WEB_LAZY_CHUNK_BUDGET_BYTES" } };
  const logicalNames = ["index", ...new Set(MEASUREMENT_PROFILE.routes.flatMap((route) => route.requiredChunks))];
  const bundleObservations = logicalNames.map((logicalName) => {
    const kind = logicalName === "index" ? "entry" : "lazy";
    const warningBytes = policy[kind].warningBytes;
    const errorBytes = policy[kind].errorBytes;
    return { kind, logicalName, emittedFile: `${logicalName}-12345678.js`, rawBytes: 1, gzipBytes: 1, warningBytes, errorBytes, headroomBytes: errorBytes - 1, status: "ok" };
  }).sort((left, right) => (left.kind === "entry" ? -1 : right.kind === "entry" ? 1 : left.logicalName.localeCompare(right.logicalName)));
  const bundleObservation = (logicalName) => bundleObservations.find((observation) => observation.logicalName === logicalName);
  const route = (id) => {
    const expected = MEASUREMENT_PROFILE.routes.find((candidate) => candidate.id === id);
    const chunks = expected.requiredChunks.map((logicalName) => {
      const observation = bundleObservation(logicalName);
      return { logicalName, emittedFile: observation.emittedFile, rawBytes: observation.rawBytes, gzipBytes: observation.gzipBytes, policyStatus: observation.status, headroomBytes: observation.headroomBytes, transferBytes: 1, transferDurationMs: 1, parseMs: 1, sampledCpuMs: 1 };
    });
    return { ...expected, actions: [...expected.actions], readinessSelectors: [...expected.readinessSelectors], requiredChunks: [...expected.requiredChunks], window: "cold_route_plus_required_action", sampleCount: 5, loadedChunks: [...expected.requiredChunks], transferBytes: chunks.reduce((sum, chunk) => sum + chunk.transferBytes, 0), transferSpanMs: 100, parseMs: 10, executeMs: 20, chunks };
  };
  const fixtureRoutes = ROUTES.map((route) => ({ id: route.id, requests: route.id === "process" ? [{ method: "GET", path: "/api/v1/materials", count: 1 }, { method: "POST", path: "/api/v1/processing:preview", count: 1 }] : [{ method: "GET", path: "/api/v1/materials", count: 1 }], allowedPreviewPosts: route.id === "process" ? 1 : 0, persistentWrites: 0, unexpectedRequests: 0 }));
  const value = {
    schemaVersion: "cmp.web-modeling-route.v1", sourceSha: "a".repeat(40), buildFingerprintSha256: "b".repeat(64), profile: MEASUREMENT_PROFILE, measurementProfileSha256: "c".repeat(64), harnessSha256: "d".repeat(64), environment: { nodeVersion: "v1", platform: "test", osRelease: "test", arch: "x64", cpuModel: "test", chromiumVersion: "test", headless: true, viewport: MEASUREMENT_PROFILE.browser.viewport, deviceScaleFactor: 1, locale: "en-US", colorScheme: "light", reducedMotion: "reduce", cpuThrottleRate: 4, network: MEASUREMENT_PROFILE.network, profilerSampleIntervalUs: 100, sampleCount: 5, gzipLevel: 9 }, policy, bundle: { observations: bundleObservations, summary: { status: "ok", warningCount: 0, errorCount: 0, largestRaw: { kind: "entry", logicalName: "index", emittedFile: "index-12345678.js", bytes: 1 }, largestGzip: { kind: "entry", logicalName: "index", emittedFile: "index-12345678.js", bytes: 1 } } }, fixture: { fixtureId: "issue-189-synthetic-metal-v1", fixtureSha256: "e".repeat(64), nonProduction: true, materialFamily: "metal", sessionStorageKey: "cmp.modeling.recent-session.v4", routes: fixtureRoutes }, routes: [route("process"), route("fit"), route("export")], comparison: createComparison(), ...overrides,
  };
  if (!Object.hasOwn(overrides, "measurementProfileSha256")) value.measurementProfileSha256 = measurementProfileSha256();
  return value;
}

function reportWithMetric(metric, value) {
  const valueReport = report();
  const processRoute = valueReport.routes.find((route) => route.id === "process");
  if (metric === "transferBytes") {
    const rest = processRoute.chunks.slice(1).reduce((sum, chunk) => sum + chunk.transferBytes, 0);
    const commonTransfer = value - rest;
    processRoute.chunks[0].transferBytes = commonTransfer;
    processRoute.chunks[0].gzipBytes = commonTransfer;
    const commonObservation = valueReport.bundle.observations.find((observation) => observation.emittedFile === processRoute.chunks[0].emittedFile);
    commonObservation.gzipBytes = commonTransfer;
    for (const route of valueReport.routes) {
      for (const chunk of route.chunks) if (chunk.emittedFile === processRoute.chunks[0].emittedFile) { chunk.transferBytes = commonTransfer; chunk.gzipBytes = commonTransfer; }
      route.transferBytes = route.chunks.reduce((sum, chunk) => sum + chunk.transferBytes, 0);
    }
    valueReport.bundle.summary.largestGzip = { kind: commonObservation.kind, logicalName: commonObservation.logicalName, emittedFile: commonObservation.emittedFile, bytes: commonTransfer };
  }
  const route = valueReport.routes.find((candidate) => candidate.id === "process");
  route[metric] = value;
  return valueReport;
}

test("baseline envelope round-trips and invalid sequence is rejected", () => {
  const current = report();
  const baseline = createBaselineEnvelope(current);
  assert.equal(baseline.schemaVersion, "cmp.web-modeling-route-baseline.v1");
  assert.deepEqual(validateBaseline(baseline), []);
  baseline.observations[0].sequence = 2;
  assert.equal(validateBaseline(baseline)[0].code, "BASELINE_SEQUENCE");
});

test("comparison distinguishes no-regression, strict two-threshold candidates, and mismatch", () => {
  const current = report();
  const baseline = createBaselineEnvelope(current);
  assert.equal(compareReport(current, baseline).status, "comparable_no_regression");
  const changed = report({ routes: current.routes.map((route) => route.id === "process" ? { ...route, transferBytes: 16000, transferSpanMs: 130, parseMs: 13, executeMs: 24 } : route) });
  assert.equal(compareReport(changed, baseline).status, "comparable_candidate_regression");
  const mismatch = report({ harnessSha256: "f".repeat(64) });
  assert.equal(compareReport(mismatch, baseline).status, "not_comparable");
  assert.equal(compareReport(mismatch, baseline).diagnostics[0].code, "HARNESS_MISMATCH");
  assert.equal(compareReport(current, null).status, "invalid_baseline");
});

test("numeric comparisons require both strict thresholds and chunk changes are OR candidates", () => {
  const base = report();
  const baseline = createBaselineEnvelope(base);
  const checks = [
    ["transferBytes", 100000, 105000, 105001],
    ["transferSpanMs", 100, 110, 120.001],
    ["parseMs", 10, 11, 12.001],
    ["executeMs", 100, 110, 110.001],
  ];
  for (const [metric, value, relativeEquality, overBoth] of checks) {
    const baselineReport = reportWithMetric(metric, value);
    const baselineEnvelope = createBaselineEnvelope(baselineReport);
    assert.equal(compareReport(reportWithMetric(metric, relativeEquality), baselineEnvelope).status, "comparable_no_regression");
    const absoluteEquality = metric === "transferBytes" ? value + 4096 : metric === "transferSpanMs" ? value + 20 : metric === "parseMs" ? value + 2 : value + 10;
    assert.equal(compareReport(reportWithMetric(metric, absoluteEquality), baselineEnvelope).status, "comparable_no_regression");
    assert.equal(compareReport(reportWithMetric(metric, overBoth), baselineEnvelope).status, "comparable_candidate_regression", metric);
    assert.equal(compareReport(reportWithMetric(metric, overBoth), baselineEnvelope).routeCandidates.find((candidate) => candidate.metric === metric).routeId, "process");
  }
  const requiredChanged = report({ routes: base.routes.map((route) => route.id === "process" ? { ...route, requiredChunks: ["new-required"] } : route) });
  assert.equal(compareReport(requiredChanged, baseline).routeCandidates[0].metric, "requiredChunks");
  const loadedChanged = report({ routes: base.routes.map((route) => route.id === "process" ? { ...route, loadedChunks: ["new-loaded"] } : route) });
  assert.equal(compareReport(loadedChanged, baseline).routeCandidates[0].metric, "requiredChunks");
});

test("not-comparable diagnostics are sorted and suppress route candidates", () => {
  const baseline = createBaselineEnvelope(report());
  const current = report({
    profile: { ...MEASUREMENT_PROFILE, version: "changed" },
    measurementProfileSha256: "f".repeat(64),
    harnessSha256: "e".repeat(64),
    environment: { ...report().environment, platform: "changed" },
    fixture: { ...report().fixture, fixtureSha256: "f".repeat(64) },
    policy: { ...report().policy, overrideActive: true, activeOverrides: ["CMP_WEB_ENTRY_WARNING_BYTES"] },
  });
  const comparison = compareReport(current, baseline);
  assert.equal(comparison.status, "not_comparable");
  assert.deepEqual(comparison.routeCandidates, []);
  assert.deepEqual(comparison.diagnostics.map((item) => item.code), ["ENVIRONMENT_MISMATCH", "FIXTURE_MISMATCH", "HARNESS_MISMATCH", "POLICY_MISMATCH", "POLICY_OVERRIDE_ACTIVE", "PROFILE_MISMATCH"]);
});

test("baseline validation rejects empty history, bad SHA/sequence, overrides, missing fields, sort drift, and envelope extras", () => {
  const baseline = createBaselineEnvelope(report());
  assert.equal(validateBaseline({ ...baseline, observations: [] })[0].code, "BASELINE_OBSERVATION");
  const nullObservationDiagnostics = validateBaseline({ ...baseline, observations: [null] });
  assert.ok(nullObservationDiagnostics.length > 0);
  assert.ok(nullObservationDiagnostics.every((item) => item.code.startsWith("BASELINE_")));
  assert.equal(validateBaseline({ ...baseline, observations: [{ ...baseline.observations[0], sequence: 1.5 }] })[0].code, "BASELINE_SEQUENCE");
  assert.equal(validateBaseline({ ...baseline, observations: [{ ...baseline.observations[0], acceptedMainSha: "bad" }] })[0].code, "BASELINE_SHA");
  const duplicate = structuredClone(baseline); duplicate.observations.push({ ...structuredClone(duplicate.observations[0]), sequence: 2 });
  assert.ok(validateBaseline(duplicate).some((item) => item.code === "BASELINE_SHA"));
  const override = structuredClone(baseline); override.observations[0].policy.overrideActive = true;
  assert.ok(validateBaseline(override).some((item) => item.code === "BASELINE_OBSERVATION"));
  const missing = structuredClone(baseline); delete missing.observations[0].fixture.fixtureSha256; delete missing.observations[0].routes[0].chunks;
  assert.ok(validateBaseline(missing).some((item) => item.code === "BASELINE_OBSERVATION"));
  const routeOrder = structuredClone(baseline); routeOrder.observations[0].routes.reverse();
  assert.ok(validateBaseline(routeOrder).some((item) => item.code === "BASELINE_SORT"));
  const bundleOrder = structuredClone(baseline); bundleOrder.observations[0].bundle.observations.push({ ...bundleOrder.observations[0].bundle.observations[0], logicalName: "zzz" }); bundleOrder.observations[0].bundle.observations.reverse();
  assert.ok(validateBaseline(bundleOrder).some((item) => item.code === "BASELINE_SORT"));
  const requestOrder = structuredClone(baseline); requestOrder.observations[0].fixture.routes[0].requests = [{ method: "POST", path: "/z", count: 1 }, { method: "GET", path: "/a", count: 1 }];
  assert.ok(validateBaseline(requestOrder).some((item) => item.code === "BASELINE_SORT"));
  const sourceExtra = structuredClone(baseline); sourceExtra.observations[0].sourceSha = "a".repeat(40);
  assert.ok(validateBaseline(sourceExtra).some((item) => item.code === "BASELINE_OBSERVATION"));
  const badPolicy = structuredClone(baseline); badPolicy.updatePolicy.compareCommand = "wrong";
  assert.equal(validateBaseline(badPolicy)[0].code, "BASELINE_SCHEMA");
});

test("baseline validation rejects malformed nested values and comparison reports invalid_baseline", () => {
  const mutations = [
    ["build fingerprint", (observation) => { observation.buildFingerprintSha256 = "bad"; }],
    ["profile hash", (observation) => { observation.measurementProfileSha256 = "0".repeat(64); }],
    ["environment viewport", (observation) => { observation.environment.viewport.width += 1; }],
    ["policy shape", (observation) => { observation.policy = { overrideActive: false }; }],
    ["bundle threshold", (observation) => { observation.bundle.observations[0].warningBytes += 1; }],
    ["bundle raw bytes", (observation) => { observation.bundle.observations[0].rawBytes = "x"; }],
    ["route transfer", (observation) => { observation.routes[0].transferBytes = "not-a-number"; }],
    ["route transfer total", (observation) => { observation.routes[0].transferBytes += 1; }],
    ["route readiness", (observation) => { observation.routes[0].readinessSelectors[0] = "changed"; }],
    ["route loaded order", (observation) => { observation.routes[0].loadedChunks.reverse(); }],
    ["chunk raw bytes", (observation) => { observation.routes[0].chunks[0].rawBytes += 1; }],
    ["chunk transfer", (observation) => { observation.routes[0].chunks[0].transferBytes += 1; }],
    ["chunk parse", (observation) => { observation.routes[0].chunks[0].parseMs = null; }],
    ["fixture routes", (observation) => { observation.fixture.routes = []; }],
    ["fixture route id", (observation) => { observation.fixture.routes[0].id = "wrong"; }],
    ["fixture write count", (observation) => { observation.fixture.routes[0].persistentWrites = 99; }],
    ["fixture request method", (observation) => { observation.fixture.routes[0].requests[0].method = 1; }],
  ];
  for (const [label, mutate] of mutations) {
    const baseline = createBaselineEnvelope(report());
    mutate(baseline.observations[0]);
    const diagnostics = validateBaseline(baseline);
    assert.ok(diagnostics.length > 0, label);
    assert.ok(diagnostics.every((item) => item.code.startsWith("BASELINE_")), label);
    assert.equal(compareReport(report(), baseline).status, "invalid_baseline", label);
  }
});

test("trend truth table uses raw common bytes only", () => {
  const observation = (raw, status = "ok", gzipBytes = raw) => ({ bundle: { observations: [{ logicalName: "common-processing-workbench", rawBytes: raw, gzipBytes, status }] } });
  assert.equal(evaluateTrend([observation(131001)]).immediateError, true);
  assert.equal(evaluateTrend([observation(131000, "warning"), observation(131000, "warning")]).twoConsecutiveStatus, true);
  assert.equal(evaluateTrend([observation(100000), observation(101024), observation(102048)]).persistentGrowth, true);
  assert.equal(evaluateTrend([observation(120000), observation(121024), observation(122048)]).persistentGrowth, false);
  assert.equal(evaluateTrend([observation(100000, "ok"), observation(101024, "warning"), observation(102048, "ok")]).persistentGrowth, false);
  assert.equal(evaluateTrend([observation(100000), observation(101024)]).persistentGrowth, false);
  assert.equal(evaluateTrend([observation(100000), observation(100000), observation(100000)]).persistentGrowth, false);
  assert.equal(evaluateTrend([observation(100000), observation(101024), observation(100000)]).persistentGrowth, false);
  assert.equal(evaluateTrend([observation(100000), observation(101023), observation(102046)]).persistentGrowth, false);
  assert.equal(evaluateTrend([observation(100000, "ok", 1), observation(100000, "ok", 999999)]).splitTrigger, false);
});

test("synthetic fixture accepts one exact Process preview and rejects all other mutations", async () => {
  const fixture = createModelingFixture();
  fixture.setRoute("process");
  const payload = JSON.stringify({ document: testDataContent, mapping_profile: mappingProfile.content, steps: fixture.processSteps.map((step) => ({ method_id: step.method_id, method_version: step.method_version, options: { ...step.options } })) });
  assert.equal((await fixture.handle({ method: "POST", path: "/api/v1/processing:preview", body: payload })).status, 200);
  assert.equal((await fixture.handle({ method: "POST", path: "/api/v1/processing:preview", body: payload })).status, 404);
  fixture.setRoute("fit");
  assert.equal((await fixture.handle({ method: "POST", path: "/api/v1/processing:preview", body: payload })).status, 404);
  fixture.setRoute("process");
  const changedOptions = JSON.parse(payload); changedOptions.steps[0].options = [];
  assert.equal((await fixture.handle({ method: "POST", path: "/api/v1/processing:preview", body: JSON.stringify(changedOptions) })).status, 404);
  assert.equal((await fixture.handle({ method: "POST", path: "/api/v1/processing:commit", body: "{}" })).status, 404);
  assert.equal((await fixture.handle({ method: "DELETE", path: "/api/v1/anything" })).status, 404);
  const summary = fixture.routeSummary();
  assert.equal(summary.routes.reduce((sum, route) => sum + route.persistentWrites, 0), 0);
  assert.ok(summary.routes.reduce((sum, route) => sum + route.unexpectedRequests, 0) >= 3);
  for (const route of summary.routes) {
    const keys = route.requests.map((item) => `${item.method}\u0000${item.path}`);
    assert.deepEqual(keys, [...keys].sort());
  }
});

test("trace/profile helpers expose attribution and reject missing data; ScriptDuration is required", () => {
  const trace = { traceEvents: [
    { name: "v8.parseOnBackground", dur: 2000, args: { data: { url: "http://127.0.0.1/assets/common-12345678.js" } } },
    { name: "v8.compileModule", dur: 1000, args: { data: { url: "http://127.0.0.1/assets/panel-12345678.js" } } },
  ] };
  const profile = { nodes: [{ id: 1, callFrame: { url: "http://127.0.0.1/assets/common-12345678.js" } }, { id: 2, callFrame: { url: "http://127.0.0.1/assets/panel-12345678.js" } }], samples: [1, 2, 1] };
  const metrics = parseTraceMetrics(trace, profile);
  assert.equal(metrics.parseMs, 3); assert.equal(metrics.parseByFile["common-12345678.js"], 2); assert.equal(metrics.cpuByFile["panel-12345678.js"], 0.1);
  assert.deepEqual(parseTraceMetrics({ traceEvents: [] }, { nodes: [], samples: [] }), { parseMs: 0, parseByFile: {}, cpuByFile: {}, cpuFiles: new Set(), cpuNodeCountByFile: {} });
  const bundle = { observations: [{ logicalName: "common-processing-workbench", emittedFile: "common-12345678.js" }, { logicalName: "modeling-process-panel", emittedFile: "panel-12345678.js" }] };
  assert.equal(validateTraceAttribution({ route: ROUTES[0], bundle, trace, profile, traceMetrics: metrics }), true);
  const nodePresentNoSample = parseTraceMetrics(trace, { nodes: profile.nodes, samples: [1] });
  assert.equal(validateTraceAttribution({ route: ROUTES[0], bundle, trace, profile: { nodes: profile.nodes, samples: [1] }, traceMetrics: nodePresentNoSample }), true);
  assert.equal(joinChunkMetrics({ bundle, resources: [{ emittedFile: "common-12345678.js", transferBytes: 1, transferDurationMs: 1 }, { emittedFile: "panel-12345678.js", transferBytes: 1, transferDurationMs: 1 }], parseByFile: metrics.parseByFile, cpuByFile: nodePresentNoSample.cpuByFile }).find((chunk) => chunk.emittedFile === "panel-12345678.js").sampledCpuMs, 0);
  const nodeAbsent = parseTraceMetrics(trace, { nodes: [profile.nodes[0]], samples: [1] });
  assert.throws(() => validateTraceAttribution({ route: ROUTES[0], bundle, trace, profile: { nodes: [profile.nodes[0]], samples: [1] }, traceMetrics: nodeAbsent }), (error) => error.code === "TRACE");
  assert.throws(() => validateTraceAttribution({ route: ROUTES[0], bundle, trace: { traceEvents: [] }, profile, traceMetrics: metrics }), (error) => error.code === "TRACE");
  assert.throws(() => validateTraceAttribution({ route: ROUTES[0], bundle, trace, profile: { nodes: [], samples: [] }, traceMetrics: metrics }), (error) => error.code === "TRACE");
  assert.throws(() => validateTraceAttribution({ route: ROUTES[0], bundle, trace, profile, traceMetrics: { parseByFile: {}, cpuByFile: {} } }), (error) => error.code === "TRACE");
  assert.equal(scriptDurationDelta({ metrics: [{ name: "ScriptDuration", value: 1 }] }, { metrics: [{ name: "ScriptDuration", value: 1.25 }] }), 0.25);
  assert.throws(() => scriptDurationDelta({ metrics: [] }, { metrics: [] }), (error) => error.code === "TRACE");
});
