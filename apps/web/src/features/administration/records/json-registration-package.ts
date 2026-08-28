import { ApiError } from "../../../shared/api/http";

const JSON_MEDIA_TYPE = "application/json";
const ZIP_MEDIA_TYPE = "application/zip";
const JSON_REGISTRATION_CONTRACT_ID =
  "https://cmp.example/contracts/catalog/json-record-registration.schema.json";
const JSON_PACKAGE_CONTRACT_ID = "cmp.catalog-record-registration-package";
const JSON_PACKAGE_CONTRACT_VERSION = "1.0.0";
export const MAX_SINGLE_JSON_BYTES = 25 * 1024 * 1024;
export const MAX_COMPONENT_BYTES = 250 * 1024 * 1024;
export const MAX_PACKAGE_BYTES = 64 * 1024 * 1024;

export function safeFilename(filename: string): string {
  const normalized = filename.normalize("NFC");
  if (
    !normalized
    || filename !== normalized
    || filename.length > 255
    || filename !== filename.trim()
    || filename.startsWith("/")
    || filename.endsWith("/")
    || filename.includes("\\")
    || filename.includes(":")
    || filename.includes("\0")
    || filename.split("/").some((part) => !part || part === "." || part === "..")
    || [...filename].some((character) => character < " " || character === "\u007f")
  ) {
    throw new ApiError(422, "Choose a source with a safe, non-empty NFC filename.");
  }
  return normalized;
}

export async function sha256Hex(value: Blob): Promise<string> {
  if (typeof crypto === "undefined" || !crypto.subtle) {
    throw new ApiError(503, "This browser cannot calculate the required SHA-256 upload digest.");
  }
  const digest = await crypto.subtle.digest("SHA-256", await value.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function utf8(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

function blobPart(value: Uint8Array): ArrayBuffer {
  const copy = new ArrayBuffer(value.byteLength);
  new Uint8Array(copy).set(value);
  return copy;
}

function compareBytes(left: Uint8Array, right: Uint8Array): number {
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return left.length - right.length;
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value.normalize("NFC"));
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new ApiError(422, "Package metadata must be finite.");
    return Object.is(value, -0) ? "0" : JSON.stringify(value);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) =>
      compareBytes(utf8(left.normalize("NFC")), utf8(right.normalize("NFC"))),
    );
    return `{${entries
      .map(([key, item]) => `${canonicalJson(key)}:${canonicalJson(item)}`)
      .join(",")}}`;
  }
  throw new ApiError(422, "Package metadata contains an unsupported value.");
}

function crc32(value: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of value) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function u16(value: number): Uint8Array {
  const bytes = new Uint8Array(2);
  new DataView(bytes.buffer).setUint16(0, value, true);
  return bytes;
}

function u32(value: number): Uint8Array {
  const bytes = new Uint8Array(4);
  new DataView(bytes.buffer).setUint32(0, value >>> 0, true);
  return bytes;
}

function concatBytes(parts: Uint8Array[]): Uint8Array {
  const result = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

function deterministicZip(entries: { name: string; value: Uint8Array }[]): Uint8Array {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;
  for (const entry of entries) {
    const name = utf8(entry.name);
    const crc = crc32(entry.value);
    const local = concatBytes([
      new Uint8Array([0x50, 0x4b, 0x03, 0x04]),
      u16(20), u16(0x800), u16(0), u16(0), u16(33),
      u32(crc), u32(entry.value.length), u32(entry.value.length),
      u16(name.length), u16(0), name, entry.value,
    ]);
    localParts.push(local);
    centralParts.push(concatBytes([
      new Uint8Array([0x50, 0x4b, 0x01, 0x02]),
      u16((3 << 8) | 20), u16(20), u16(0x800), u16(0), u16(0), u16(33),
      u32(crc), u32(entry.value.length), u32(entry.value.length),
      u16(name.length), u16(0), u16(0), u16(0), u16(0), u32(0o100644 << 16),
      u32(offset), name,
    ]));
    offset += local.length;
  }
  const centralOffset = offset;
  const central = concatBytes(centralParts);
  return concatBytes([
    concatBytes(localParts), central,
    new Uint8Array([0x50, 0x4b, 0x05, 0x06]),
    u16(0), u16(0), u16(entries.length), u16(entries.length),
    u32(central.length), u32(centralOffset), u16(0),
  ]);
}

function unicodeCaseFold(value: string): string {
  // JavaScript has no full Unicode casefold primitive.  The explicit sharp-s replacement
  // covers the non-round-tripping collision relevant to browser filenames; the backend
  // remains authoritative and repeats the complete collision check.
  return value.normalize("NFC").toLocaleLowerCase("en-US").replaceAll("ß", "ss");
}

export async function buildJsonRegistrationPackage(
  files: File[],
  classification: string,
): Promise<File> {
  if (!files.length || files.length > 100) {
    throw new ApiError(422, "Choose between one and 100 source files.");
  }
  const components = await Promise.all(files.map(async (file) => {
    const filename = safeFilename(file.name);
    if (file.size < 1 || file.size > MAX_COMPONENT_BYTES) {
      throw new ApiError(413, "A source must be between 1 byte and 250 MiB.");
    }
    const value = new Uint8Array(await file.arrayBuffer());
    return { filename, value, sha256: await sha256Hex(file), size_bytes: file.size };
  }));
  const folded = components.map((component) => unicodeCaseFold(component.filename));
  if (new Set(folded).size !== folded.length) {
    throw new ApiError(422, "Source filenames collide under Unicode case-folding.");
  }
  components.sort((left, right) => {
    const byName = compareBytes(utf8(left.filename), utf8(right.filename));
    return byName || compareBytes(utf8(left.sha256), utf8(right.sha256));
  });
  const paths = components.map(
    (component, index) => `records/${String(index + 1).padStart(3, "0")}-${component.sha256}.json`,
  );
  const manifest = utf8(`${canonicalJson({
    $schema: JSON_REGISTRATION_CONTRACT_ID,
    contract: JSON_PACKAGE_CONTRACT_ID,
    contract_version: JSON_PACKAGE_CONTRACT_VERSION,
    media_type: ZIP_MEDIA_TYPE,
    scope: { classification },
    components: components.map((component, index) => ({
      ordinal: index + 1,
      original_name: component.filename,
      path: paths[index],
      media_type: JSON_MEDIA_TYPE,
      size_bytes: component.size_bytes,
      sha256: component.sha256,
    })),
  })}\n`);
  const checksums = utf8([
    `${await sha256Hex(new Blob([blobPart(manifest)]))}  manifest.json`,
    ...components.map((component, index) => `${component.sha256}  ${paths[index]}`),
  ].join("\n") + "\n");
  const archive = deterministicZip([
    { name: "manifest.json", value: manifest },
    { name: "checksums.sha256", value: checksums },
    ...components.map((component, index) => ({ name: paths[index], value: component.value })),
  ]);
  if (archive.length > MAX_PACKAGE_BYTES) {
    throw new ApiError(413, "The deterministic JSON package must not exceed 64 MiB.");
  }
  return new File([blobPart(archive)], "json-record-registration.zip", { type: ZIP_MEDIA_TYPE });
}
