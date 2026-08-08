import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gzipSync } from "node:zlib";
import { test } from "node:test";

import { BundleBudgetError, collectBundleBudget, runBundleBudgetCli } from "./check_web_bundle.mjs";

async function assets(files) {
  const root = await mkdtemp(join(tmpdir(), "cmp-bundle-"));
  const assetsDir = join(root, "assets");
  await mkdir(assetsDir);
  for (const [name, content] of Object.entries(files)) await writeFile(join(assetsDir, name), content);
  return assetsDir;
}

test("collects deterministic raw and gzip observations in entry/logical order", async () => {
  const dir = await assets({ "lazy-z-12345678.js": "z".repeat(10), "index-abcdefgh.js": "i".repeat(20), "lazy-a-abcdefgh.js": "a".repeat(5) });
  const report = await collectBundleBudget({ assetsDir: dir, env: {} });
  assert.deepEqual(report.observations.map((item) => item.logicalName), ["index", "lazy-a", "lazy-z"]);
  assert.equal(report.observations[0].rawBytes, 20);
  assert.equal(report.observations[0].gzipBytes > 0, true);
  assert.equal(report.policy.entry.warningBytes, 285000);
  assert.equal(report.policy.lazy.errorBytes, 131000);
  assert.equal(report.passed, true);
});

test("marks warning at equality and errors only above the hard ceiling", async () => {
  const dir = await assets({ "index-abcdefgh.js": "x".repeat(10), "lazy-a-12345678.js": "a".repeat(10) });
  const warning = await collectBundleBudget({ assetsDir: dir, env: { CMP_WEB_ENTRY_WARNING_BYTES: "5", CMP_WEB_ENTRY_BUDGET_BYTES: "10", CMP_WEB_LAZY_CHUNK_WARNING_BYTES: "1", CMP_WEB_LAZY_CHUNK_BUDGET_BYTES: "2" } });
  assert.equal(warning.observations.find((item) => item.kind === "entry").status, "warning");
  assert.equal(warning.observations.find((item) => item.kind === "lazy").status, "error");
  assert.equal(warning.violations.length, 1);
  assert.equal(warning.passed, false);
});

test("applies warning/error/e+1 edges independently to entry and lazy budgets", async () => {
  const cases = [
    { kind: "entry", file: "index-abcdefgh.js", warningEnv: "CMP_WEB_ENTRY_WARNING_BYTES", errorEnv: "CMP_WEB_ENTRY_BUDGET_BYTES", warning: 5, error: 10, otherWarning: "100", otherError: "200", otherWarningEnv: "CMP_WEB_LAZY_CHUNK_WARNING_BYTES", otherErrorEnv: "CMP_WEB_LAZY_CHUNK_BUDGET_BYTES", otherFile: "lazy-a-12345678.js" },
    { kind: "lazy", file: "lazy-a-12345678.js", warningEnv: "CMP_WEB_LAZY_CHUNK_WARNING_BYTES", errorEnv: "CMP_WEB_LAZY_CHUNK_BUDGET_BYTES", warning: 5, error: 10, otherWarning: "100", otherError: "200", otherWarningEnv: "CMP_WEB_ENTRY_WARNING_BYTES", otherErrorEnv: "CMP_WEB_ENTRY_BUDGET_BYTES", otherFile: "index-abcdefgh.js" },
  ];
  for (const item of cases) {
    for (const [rawBytes, expectedStatus, expectedHeadroom, expectedViolations] of [[item.warning, "warning", item.error - item.warning, 0], [item.error, "warning", 0, 0], [item.error + 1, "error", -1, 1]]) {
      const files = { [item.file]: "x".repeat(rawBytes), [item.otherFile]: "y" };
      const env = { [item.warningEnv]: String(item.warning), [item.errorEnv]: String(item.error), [item.otherWarningEnv]: item.otherWarning, [item.otherErrorEnv]: item.otherError };
      const report = await collectBundleBudget({ assetsDir: await assets(files), env });
      const observation = report.observations.find((candidate) => candidate.kind === item.kind);
      assert.equal(observation.status, expectedStatus, `${item.kind} raw ${rawBytes}`);
      assert.equal(observation.headroomBytes, expectedHeadroom, `${item.kind} headroom ${rawBytes}`);
      assert.equal(report.violations.length, expectedViolations, `${item.kind} violations ${rawBytes}`);
    }
  }
});

test("records exact level-9 gzip bytes, headroom, and deterministic tie winners", async () => {
  const dir = await assets({ "lazy-z-12345678.js": "z".repeat(20), "index-abcdefgh.js": "i".repeat(20), "lazy-a-abcdefgh.js": "a".repeat(20) });
  const report = await collectBundleBudget({ assetsDir: dir, env: { CMP_WEB_ENTRY_WARNING_BYTES: "10", CMP_WEB_ENTRY_BUDGET_BYTES: "20", CMP_WEB_LAZY_CHUNK_WARNING_BYTES: "10", CMP_WEB_LAZY_CHUNK_BUDGET_BYTES: "20" } });
  for (const observation of report.observations) {
    const bytes = Buffer.from(observation.logicalName === "index" ? "i".repeat(20) : observation.logicalName === "lazy-a" ? "a".repeat(20) : "z".repeat(20));
    assert.equal(observation.gzipBytes, gzipSync(bytes, { level: 9 }).byteLength);
    assert.equal(observation.headroomBytes, observation.errorBytes - observation.rawBytes);
    assert.equal(observation.status, "warning");
  }
  assert.deepEqual(report.summary.largestRaw, { kind: "entry", logicalName: "index", emittedFile: "index-abcdefgh.js", bytes: 20 });
  assert.deepEqual(report.summary.largestGzip, { kind: "entry", logicalName: "index", emittedFile: "index-abcdefgh.js", bytes: report.observations[0].gzipBytes });
});

test("CLI is injectable and preserves JSON/error stream and exit contracts", async () => {
  const capture = () => ({ stdout: [], stderr: [], out: { write(value) { this.owner.stdout.push(String(value)); } }, err: { write(value) { this.owner.stderr.push(String(value)); } } });
  const okDir = await assets({ "index-abcdefgh.js": "x" });
  const ok = capture(); ok.out.owner = ok; ok.err.owner = ok;
  const okResult = await runBundleBudgetCli({ assetsDir: okDir, env: {}, stdout: ok.out, stderr: ok.err });
  assert.equal(okResult.exitCode, 0); assert.equal(okResult.report.passed, true); assert.equal(ok.stderr.length, 0); assert.equal(JSON.parse(ok.stdout.join(""))["passed"], true);
  const warning = capture(); warning.out.owner = warning; warning.err.owner = warning;
  const warningResult = await runBundleBudgetCli({ assetsDir: okDir, env: { CMP_WEB_ENTRY_WARNING_BYTES: "1", CMP_WEB_ENTRY_BUDGET_BYTES: "2" }, stdout: warning.out, stderr: warning.err });
  assert.equal(warningResult.exitCode, 0); assert.equal(warningResult.report.passed, true); assert.equal(warningResult.report.summary.status, "warning"); assert.equal(warning.stderr.length, 0);
  const errorDir = await assets({ "index-abcdefgh.js": "x".repeat(3) });
  const error = capture(); error.out.owner = error; error.err.owner = error;
  const errorResult = await runBundleBudgetCli({ assetsDir: errorDir, env: { CMP_WEB_ENTRY_WARNING_BYTES: "1", CMP_WEB_ENTRY_BUDGET_BYTES: "2" }, stdout: error.out, stderr: error.err });
  assert.equal(errorResult.exitCode, 1); assert.equal(errorResult.report.passed, false); assert.equal(error.stderr.length, 0); assert.deepEqual(JSON.parse(error.stdout.join("")).violations, [{ budgetBytes: 2, entry: true, name: "index-abcdefgh.js", passed: false, sizeBytes: 3 }]);
  const invalid = capture(); invalid.out.owner = invalid; invalid.err.owner = invalid;
  const invalidResult = await runBundleBudgetCli({ assetsDir: okDir, env: { CMP_WEB_ENTRY_WARNING_BYTES: "0" }, stdout: invalid.out, stderr: invalid.err });
  assert.equal(invalidResult.exitCode, 1); assert.equal(invalid.stdout.length, 0); assert.equal(invalidResult.error.code, "INVALID_POLICY"); assert.equal(invalid.stderr.join(""), "BundleBudgetError[INVALID_POLICY]: CMP_WEB_ENTRY_WARNING_BYTES must be a positive safe integer\n");
  const noAssets = capture(); noAssets.out.owner = noAssets; noAssets.err.owner = noAssets;
  const noAssetsResult = await runBundleBudgetCli({ assetsDir: join(tmpdir(), "cmp-no-assets-cli"), env: {}, stdout: noAssets.out, stderr: noAssets.err });
  assert.equal(noAssetsResult.exitCode, 1); assert.equal(noAssets.stdout.length, 0); assert.match(noAssets.stderr.join(""), /^BundleBudgetError\[NO_ASSETS\]: assets directory does not exist:/);
});

test("rejects missing, malformed, duplicate, and invalid policy inputs", async () => {
  await assert.rejects(() => collectBundleBudget({ assetsDir: join(tmpdir(), "cmp-no-such-assets"), env: {} }), (error) => error instanceof BundleBudgetError && error.code === "NO_ASSETS");
  const noIndex = await assets({ "lazy-a-12345678.js": "x" });
  await assert.rejects(() => collectBundleBudget({ assetsDir: noIndex, env: {} }), (error) => error.code === "ENTRY_COUNT");
  const noJavaScript = await assets({ "index-abcdefgh.css": "x" });
  await assert.rejects(() => collectBundleBudget({ assetsDir: noJavaScript, env: {} }), (error) => error.code === "NO_ASSETS");
  const malformed = await assets({ "index-abcdefgh.js": "x", "bad.js": "y" });
  await assert.rejects(() => collectBundleBudget({ assetsDir: malformed, env: {} }), (error) => error.code === "LOGICAL_NAME");
  const duplicate = await assets({ "foo-abcdefgh.js": "x", "foo-12345678.js": "y", "index-87654321.js": "z" });
  await assert.rejects(() => collectBundleBudget({ assetsDir: duplicate, env: {} }), (error) => error.code === "LOGICAL_NAME");
  await assert.rejects(() => collectBundleBudget({ assetsDir: noIndex, env: { CMP_WEB_ENTRY_WARNING_BYTES: "0" } }), (error) => error.code === "INVALID_POLICY");
  for (const value of ["1.5", "-1", "9007199254740992", "unsafe"]) {
    await assert.rejects(() => collectBundleBudget({ assetsDir: noIndex, env: { CMP_WEB_ENTRY_WARNING_BYTES: value } }), (error) => error.code === "INVALID_POLICY");
  }
  await assert.rejects(() => collectBundleBudget({ assetsDir: noIndex, env: { CMP_WEB_ENTRY_WARNING_BYTES: "10", CMP_WEB_ENTRY_BUDGET_BYTES: "10" } }), (error) => error.code === "INVALID_POLICY");
});

test("preserves override names/order and compatibility fields", async () => {
  const dir = await assets({ "index-abcdefgh.js": "x", "lazy-a-12345678.js": "y" });
  const report = await collectBundleBudget({ assetsDir: dir, env: { CMP_WEB_ENTRY_WARNING_BYTES: "2", CMP_WEB_LAZY_CHUNK_WARNING_BYTES: "2", CMP_WEB_LAZY_CHUNK_BUDGET_BYTES: "4" } });
  assert.equal(report.policy.overrideActive, true);
  assert.deepEqual(report.policy.activeOverrides, ["CMP_WEB_ENTRY_WARNING_BYTES", "CMP_WEB_LAZY_CHUNK_WARNING_BYTES", "CMP_WEB_LAZY_CHUNK_BUDGET_BYTES"]);
  assert.equal(report.entryBudgetBytes, 300000);
  assert.equal(report.lazyChunkBudgetBytes, 4);
  assert.equal(report.largestChunkBytes, 1);
  assert.deepEqual(report.violations, []);
});

test("sorts filenames before validation so duplicate diagnostics do not depend on creation order", async () => {
  const first = await assets({ "foo-zzzzzzzz.js": "z", "foo-aaaaaaaa.js": "a", "index-abcdefgh.js": "i" });
  const second = await assets({ "index-abcdefgh.js": "i", "foo-aaaaaaaa.js": "a", "foo-zzzzzzzz.js": "z" });
  const errorMessage = async (assetsDir) => {
    await assert.rejects(() => collectBundleBudget({ assetsDir, env: {} }), (error) => {
      assert.equal(error.code, "LOGICAL_NAME");
      return true;
    }).catch((error) => { throw error; });
  };
  const readError = async (assetsDir) => {
    try { await collectBundleBudget({ assetsDir, env: {} }); } catch (error) { return `${error.code}: ${error.message}`; }
    throw new Error("expected duplicate logical-name failure");
  };
  await errorMessage(first);
  await errorMessage(second);
  assert.equal(await readError(first), await readError(second));
  assert.equal(await readError(first), "LOGICAL_NAME: duplicate logical name foo: foo-aaaaaaaa.js, foo-zzzzzzzz.js");
});
