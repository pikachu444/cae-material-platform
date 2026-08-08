import { gzipSync } from "node:zlib";
import { readdir, readFile, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repository = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const DEFAULT_ASSETS_DIR = join(repository, "apps", "web", "dist", "assets");

const OVERRIDE_NAMES = {
  entryWarning: "CMP_WEB_ENTRY_WARNING_BYTES",
  entryError: "CMP_WEB_ENTRY_BUDGET_BYTES",
  lazyWarning: "CMP_WEB_LAZY_CHUNK_WARNING_BYTES",
  lazyError: "CMP_WEB_LAZY_CHUNK_BUDGET_BYTES",
};

export const DEFAULT_BUNDLE_POLICY = Object.freeze({
  measurement: "raw_bytes",
  gzip: "observation_only_node_zlib_level_9",
  entry: Object.freeze({
    warningBytes: 285_000,
    errorBytes: 300_000,
    warningPurpose: "review growth before the hard entry ceiling",
    errorPurpose: "fail the production build",
  }),
  lazy: Object.freeze({
    warningBytes: 128_000,
    errorBytes: 131_000,
    warningPurpose: "start prospective Workbench trend review",
    errorPurpose: "fail the production build",
  }),
  overrideNames: Object.freeze({ ...OVERRIDE_NAMES }),
});

export class BundleBudgetError extends Error {
  /** @param {string} code @param {string} message */
  constructor(code, message) {
    super(message);
    this.name = "BundleBudgetError";
    this.code = code;
  }
}

function positiveSafeInteger(value, name) {
  if (typeof value === "number" && Number.isSafeInteger(value) && value > 0) return value;
  if (typeof value !== "string" || !/^[0-9]+$/.test(value.trim())) {
    throw new BundleBudgetError("INVALID_POLICY", `${name} must be a positive safe integer`);
  }
  const parsed = Number(value.trim());
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new BundleBudgetError("INVALID_POLICY", `${name} must be a positive safe integer`);
  }
  return parsed;
}

function readPolicy(env = process.env) {
  const values = {
    entryWarning: DEFAULT_BUNDLE_POLICY.entry.warningBytes,
    entryError: DEFAULT_BUNDLE_POLICY.entry.errorBytes,
    lazyWarning: DEFAULT_BUNDLE_POLICY.lazy.warningBytes,
    lazyError: DEFAULT_BUNDLE_POLICY.lazy.errorBytes,
  };
  const activeOverrides = [];
  for (const [key, envName] of Object.entries(OVERRIDE_NAMES)) {
    if (env && Object.prototype.hasOwnProperty.call(env, envName) && env[envName] !== undefined) {
      values[key] = positiveSafeInteger(env[envName], envName);
      activeOverrides.push(envName);
    }
  }
  if (values.entryWarning >= values.entryError || values.lazyWarning >= values.lazyError) {
    throw new BundleBudgetError("INVALID_POLICY", "warning threshold must be less than error threshold");
  }
  return { values, activeOverrides };
}

function statusFor(rawBytes, warningBytes, errorBytes) {
  if (rawBytes < warningBytes) return "ok";
  if (rawBytes <= errorBytes) return "warning";
  return "error";
}

function compareCodePoint(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function observationCompare(left, right) {
  if (left.kind !== right.kind) return left.kind === "entry" ? -1 : 1;
  const byLogical = compareCodePoint(left.logicalName, right.logicalName);
  return byLogical || compareCodePoint(left.emittedFile, right.emittedFile);
}

function largestObservation(observations, value) {
  let largest = null;
  for (const observation of observations) {
    if (!largest || observation[value] > largest[value]) largest = observation;
  }
  if (!largest) return null;
  return {
    kind: largest.kind,
    logicalName: largest.logicalName,
    emittedFile: largest.emittedFile,
    bytes: largest[value],
  };
}

/**
 * Collect the production JavaScript byte budget.
 *
 * The function deliberately performs no process I/O beyond reading the supplied assets directory;
 * callers can pass a temporary directory and an explicit environment for deterministic tests.
 * @param {{assetsDir?: string, env?: Record<string, string|undefined>}} [options]
 */
export async function collectBundleBudget({ assetsDir = DEFAULT_ASSETS_DIR, env = process.env } = {}) {
  const { values, activeOverrides } = readPolicy(env);
  const directory = resolve(String(assetsDir));
  let names;
  try {
    names = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error && typeof error === "object" && error.code === "ENOENT") {
      throw new BundleBudgetError("NO_ASSETS", `assets directory does not exist: ${directory}`);
    }
    throw new BundleBudgetError("ASSET_IO", `cannot read assets directory: ${directory}`);
  }
  const jsEntries = names
    .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
    .sort((left, right) => compareCodePoint(left.name, right.name));
  if (jsEntries.length === 0) {
    throw new BundleBudgetError("NO_ASSETS", `no production JavaScript assets found below ${directory}`);
  }

  const parsed = [];
  const logicalNames = new Map();
  for (const entry of jsEntries) {
    const match = /^(.+)-([A-Za-z0-9_-]{8})\.js$/.exec(entry.name);
    if (!match) {
      throw new BundleBudgetError("LOGICAL_NAME", `JavaScript asset has no logical name: ${entry.name}`);
    }
    const logicalName = match[1];
    if (logicalNames.has(logicalName)) {
      throw new BundleBudgetError(
        "LOGICAL_NAME",
        `duplicate logical name ${logicalName}: ${logicalNames.get(logicalName)}, ${entry.name}`,
      );
    }
    logicalNames.set(logicalName, entry.name);
    parsed.push({ emittedFile: entry.name, logicalName });
  }
  const entryFiles = parsed.filter((item) => item.logicalName === "index");
  if (entryFiles.length !== 1) {
    throw new BundleBudgetError("ENTRY_COUNT", `expected exactly one index asset, found ${entryFiles.length}`);
  }

  const observations = [];
  for (const item of parsed) {
    const filePath = join(directory, item.emittedFile);
    let bytes;
    let metadata;
    try {
      [bytes, metadata] = await Promise.all([readFile(filePath), stat(filePath)]);
    } catch {
      throw new BundleBudgetError("ASSET_IO", `cannot read JavaScript asset: ${item.emittedFile}`);
    }
    if (metadata.size !== bytes.byteLength) {
      throw new BundleBudgetError("ASSET_IO", `JavaScript asset changed while reading: ${item.emittedFile}`);
    }
    const kind = item.logicalName === "index" ? "entry" : "lazy";
    const thresholds = kind === "entry"
      ? { warningBytes: values.entryWarning, errorBytes: values.entryError }
      : { warningBytes: values.lazyWarning, errorBytes: values.lazyError };
    const rawBytes = metadata.size;
    let gzipBytes;
    try {
      gzipBytes = gzipSync(bytes, { level: 9 }).byteLength;
    } catch {
      throw new BundleBudgetError("ASSET_IO", `cannot gzip JavaScript asset: ${item.emittedFile}`);
    }
    observations.push({
      kind,
      logicalName: item.logicalName,
      emittedFile: item.emittedFile,
      rawBytes,
      gzipBytes,
      warningBytes: thresholds.warningBytes,
      errorBytes: thresholds.errorBytes,
      headroomBytes: thresholds.errorBytes - rawBytes,
      status: statusFor(rawBytes, thresholds.warningBytes, thresholds.errorBytes),
    });
  }
  observations.sort(observationCompare);
  const warningCount = observations.filter((item) => item.status === "warning").length;
  const errorCount = observations.filter((item) => item.status === "error").length;
  const largestRaw = largestObservation(observations, "rawBytes");
  const largestGzip = largestObservation(observations, "gzipBytes");
  const violations = observations
    .filter((item) => item.status === "error")
    .map((item) => ({
      budgetBytes: item.errorBytes,
      entry: item.kind === "entry",
      name: item.emittedFile,
      passed: false,
      sizeBytes: item.rawBytes,
    }));
  const policy = {
    measurement: "raw_bytes",
    gzip: "observation_only_node_zlib_level_9",
    overrideActive: activeOverrides.length > 0,
    activeOverrides,
    entry: {
      warningBytes: values.entryWarning,
      errorBytes: values.entryError,
      warningPurpose: DEFAULT_BUNDLE_POLICY.entry.warningPurpose,
      errorPurpose: DEFAULT_BUNDLE_POLICY.entry.errorPurpose,
    },
    lazy: {
      warningBytes: values.lazyWarning,
      errorBytes: values.lazyError,
      warningPurpose: DEFAULT_BUNDLE_POLICY.lazy.warningPurpose,
      errorPurpose: DEFAULT_BUNDLE_POLICY.lazy.errorPurpose,
    },
    overrideNames: { ...OVERRIDE_NAMES },
  };
  return {
    schemaVersion: "cmp.web-bundle-budget.v1",
    policy,
    observations,
    summary: {
      status: errorCount ? "error" : warningCount ? "warning" : "ok",
      warningCount,
      errorCount,
      largestRaw,
      largestGzip,
    },
    entryBudgetBytes: values.entryError,
    lazyChunkBudgetBytes: values.lazyError,
    largestChunkBytes: largestRaw?.bytes ?? 0,
    violations,
    passed: errorCount === 0,
  };
}

function invokedDirectly() {
  if (!process.argv[1]) return false;
  try {
    return pathToFileURL(resolve(process.argv[1])).href === import.meta.url;
  } catch {
    return false;
  }
}

/**
 * Run the bundle-budget command against an injectable asset directory and I/O
 * streams.  Keeping the command boundary separate from `main` lets the
 * deterministic tests exercise all success, warning, error, and fatal paths
 * without relying on a pre-existing production build.
 * @param {{assetsDir?: string, env?: Record<string, string|undefined>, stdout?: {write: Function}, stderr?: {write: Function}}} [options]
 */
export async function runBundleBudgetCli({
  assetsDir = DEFAULT_ASSETS_DIR,
  env = process.env,
  stdout = process.stdout,
  stderr = process.stderr,
} = {}) {
  try {
    const report = await collectBundleBudget({ assetsDir, env });
    stdout.write(`${JSON.stringify(report)}\n`);
    return { report, passed: report.passed, exitCode: report.passed ? 0 : 1 };
  } catch (error) {
    const failure = error instanceof BundleBudgetError
      ? error
      : new BundleBudgetError("ASSET_IO", error instanceof Error ? error.message : String(error));
    stderr.write(`BundleBudgetError[${failure.code}]: ${failure.message}\n`);
    return { report: null, passed: false, error: failure, exitCode: 1 };
  }
}

export async function main() {
  const result = await runBundleBudgetCli();
  process.exitCode = result.exitCode;
  return result.report;
}

if (invokedDirectly()) await main();
