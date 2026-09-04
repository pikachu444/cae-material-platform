import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

export const NIST_SRM_2491_DMA_FIXTURE_SHA256 =
  "e67ae6a2d4772b33b5a0ca9667449cc415a310b3399c7532304b7014083758d0";
export const NIST_SRM_2491_DMA_UPLOAD_SHA256 =
  "f9730a7047cffe9ed808faf861ade1464efad069fd28cc117d1bfe80a0e44068";
export const NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL = 4;
export const NIST_SRM_2491_REFERENCE_TEMPERATURE_K = 303.15;
export const NIST_SRM_2491_HOLDOUT_SWEEP_ORDINAL = 1;

export const NIST_SRM_2491_DMA_PROFILE_MAPPING = {
  data_schema: "dma_frequency_temperature_sweep",
  channels: [
    { source_quantity: "source_sweep_ordinal", normalized_quantity: "source_sweep_ordinal" },
    { source_quantity: "temperature", normalized_quantity: "temperature" },
    { source_quantity: "frequency", normalized_quantity: "frequency" },
    { source_quantity: "storage_modulus", normalized_quantity: "storage_modulus" },
    { source_quantity: "loss_modulus", normalized_quantity: "loss_modulus" },
  ],
} as const;

const TWO_PI = 6.283185307179586;
const SOURCE_HEADER =
  "temperature_c,angular_frequency_rad_per_s,storage_modulus_pa,storage_standard_uncertainty_pa,storage_model_pa,loss_modulus_pa,loss_standard_uncertainty_pa,loss_model_pa";
const UPLOAD_HEADER =
  "source_sweep_ordinal,temperature_degC,frequency_Hz,storage_modulus_Pa,loss_modulus_Pa";
const EXPECTED_TEMPERATURE_TOKENS = ["0.0", "10.0", "20.0", "30.0", "40.0", "50.0"];
const DEFAULT_FIXTURE_PATH = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../fixtures/public/nist-srm-2491-dma-table-9-v1.csv",
);

function fail(message: string): never {
  throw new Error(`Issue #392 NIST SRM 2491 fixture verification failed: ${message}`);
}

function fixtureBytes(sourceText?: string): Uint8Array {
  if (sourceText === undefined) return readFileSync(DEFAULT_FIXTURE_PATH);
  return Buffer.from(sourceText, "utf8");
}

/**
 * Derive the immutable governed multi-frequency upload without changing any
 * temperature, storage, or loss source tokens. The angular-frequency source
 * remains the numeric authority; only its cyclic-Hz projection is generated.
 */
export function deriveNistSrm2491CyclicHzUpload(sourceText?: string): string {
  const bytes = fixtureBytes(sourceText);
  let source: string;
  try {
    source = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    fail("source is not valid UTF-8");
  }
  if (source.includes("\r")) fail("source must use LF line endings");
  if (!source.endsWith("\n")) fail("source must end with one final LF");
  if (createHash("sha256").update(bytes).digest("hex") !== NIST_SRM_2491_DMA_FIXTURE_SHA256) {
    fail("source SHA-256 does not match the immutable public fixture");
  }

  const lines = source.split("\n");
  if (lines.at(-1) !== "") fail("source final line is not empty after the final LF");
  if (lines[0] !== SOURCE_HEADER) fail("source header changed");
  const rows = lines.slice(1, -1);
  if (rows.length !== 96) fail(`expected 96 source rows, got ${rows.length}`);

  const seenTemperatureTokens: string[] = [];
  const ordinalByTemperature = new Map<string, number>();
  const uploadRows = rows.map((line, rowIndex) => {
    const fields = line.split(",");
    if (fields.length !== 8) fail(`source row ${rowIndex + 1} does not have 8 comma-separated fields`);
    const [temperatureToken, angularToken, storageToken, , , lossToken] = fields;
    const temperature = Number(temperatureToken);
    const angular = Number(angularToken);
    if (!Number.isFinite(temperature) || !Number.isFinite(angular) || angular <= 0) {
      fail(`source row ${rowIndex + 1} has invalid temperature or angular frequency`);
    }
    if (!ordinalByTemperature.has(temperatureToken)) {
      ordinalByTemperature.set(temperatureToken, ordinalByTemperature.size + 1);
      seenTemperatureTokens.push(temperatureToken);
    }
    const ordinal = ordinalByTemperature.get(temperatureToken)!;
    const frequencyToken = (angular / TWO_PI).toPrecision(17);
    const reconstructedAngular = TWO_PI * Number(frequencyToken);
    if (Math.abs(reconstructedAngular - angular) > 1e-12 * Math.max(1, Math.abs(angular))) {
      fail(`row ${rowIndex + 1} does not preserve omega=2*pi*Hz within tolerance`);
    }
    return [ordinal, temperatureToken, frequencyToken, storageToken, lossToken].join(",");
  });
  if (seenTemperatureTokens.length !== 6 || seenTemperatureTokens.some((item, index) => item !== EXPECTED_TEMPERATURE_TOKENS[index])) {
    fail(`expected first-seen temperature groups ${EXPECTED_TEMPERATURE_TOKENS.join(",")}`);
  }
  if (ordinalByTemperature.size !== 6) fail("expected six first-seen sweep ordinals");

  const upload = `${UPLOAD_HEADER}\n${uploadRows.join("\n")}\n`;
  const uploadBytes = Buffer.from(upload, "utf8");
  if (uploadRows.length + 1 !== 97) fail(`expected 97 upload lines, got ${uploadRows.length + 1}`);
  if (uploadBytes.byteLength !== 4264) fail(`expected 4264 upload bytes, got ${uploadBytes.byteLength}`);
  if (createHash("sha256").update(uploadBytes).digest("hex") !== NIST_SRM_2491_DMA_UPLOAD_SHA256) {
    fail("derived upload SHA-256 does not match the immutable expected digest");
  }
  if (uploadRows[0].split(",")[2] !== "0.015915494309189534") fail("first cyclic frequency token changed");
  return upload;
}
