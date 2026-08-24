import {
  downloadCanonicalTestDataDocument,
  type ApiConfig,
} from "../../../api";

export interface ExactTestDataChannel {
  key: string;
  name: string;
  quantitySemantics: string;
  axisRole: "independent" | "dependent" | "auxiliary";
  originalUnit: string;
  originalValues: Array<string | null>;
  missingReasons: Array<string | null>;
}

export interface ExactTestDataPoint {
  ordinal: number;
  independent: string | null;
  dependent: string | null;
  missingReason: string | null;
}

export interface ExactTestData {
  documentId: string;
  revisionId: string;
  documentKey: string;
  independent: ExactTestDataChannel;
  dependent: ExactTestDataChannel;
  points: ExactTestDataPoint[];
  artifact: Blob;
  filename: string;
}

function objectValue(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Exact Test Data has an invalid ${field} contract.`);
  }
  return value as Record<string, unknown>;
}

function textValue(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Exact Test Data is missing ${field}.`);
  }
  return value;
}

function nullableTextArray(value: unknown, field: string): Array<string | null> {
  if (!Array.isArray(value) || !value.every((item) => item === null || typeof item === "string")) {
    throw new Error(`Exact Test Data has invalid ${field}.`);
  }
  return value as Array<string | null>;
}

function channelValue(value: unknown): ExactTestDataChannel {
  const channel = objectValue(value, "channel");
  const axisRole = channel.axis_role;
  if (!(["independent", "dependent", "auxiliary"] as const).includes(
    axisRole as "independent" | "dependent" | "auxiliary",
  )) {
    throw new Error("Exact Test Data has an invalid channel axis role.");
  }
  const originalValues = nullableTextArray(
    channel.original_values,
    "channel original values",
  );
  const missingReasons = nullableTextArray(
    channel.missing_reasons,
    "channel missing reasons",
  );
  if (missingReasons.length !== originalValues.length) {
    throw new Error("Exact Test Data channel missingness does not match its values.");
  }
  return {
    key: textValue(channel.key, "channel key"),
    name: textValue(channel.name, "channel name"),
    quantitySemantics: textValue(
      channel.quantity_semantics,
      "channel quantity semantics",
    ),
    axisRole: axisRole as ExactTestDataChannel["axisRole"],
    originalUnit: textValue(
      channel.original_unit_string,
      "channel original unit",
    ),
    originalValues,
    missingReasons,
  };
}

export async function loadExactTestData(
  config: ApiConfig,
  documentId: string,
  revisionId: string,
): Promise<ExactTestData> {
  if (!documentId || !revisionId) {
    throw new Error("Exact Test Data identity and revision are required.");
  }
  const result = await downloadCanonicalTestDataDocument(
    config,
    documentId,
    revisionId,
  );
  let document: Record<string, unknown>;
  try {
    document = objectValue(
      JSON.parse(await result.data.blob.text()),
      "document",
    );
  } catch (cause) {
    if (cause instanceof SyntaxError) {
      throw new Error("Exact Test Data content is not valid JSON.");
    }
    throw cause;
  }
  if (document.document_type !== "cmp.test-data") {
    throw new Error("The bound revision is not canonical Test Data.");
  }
  if (!Array.isArray(document.channels)) {
    throw new Error("Exact Test Data is missing channels.");
  }
  const channels = document.channels.map(channelValue);
  const independent = channels.find((channel) => channel.axisRole === "independent");
  const dependent = channels.find(
    (channel) =>
      channel.axisRole === "dependent" &&
      channel.originalValues.length === independent?.originalValues.length,
  );
  if (!independent || !dependent || independent.originalValues.length < 2) {
    throw new Error(
      "Exact Test Data does not contain a renderable independent/dependent channel pair.",
    );
  }
  const points = independent.originalValues.map((value, index) => ({
    ordinal: index + 1,
    independent: value,
    dependent: dependent.originalValues[index],
    missingReason:
      independent.missingReasons[index] ?? dependent.missingReasons[index] ?? null,
  }));
  if (
    points.filter(
      (point) =>
        point.independent !== null &&
        point.dependent !== null &&
        Number.isFinite(Number(point.independent)) &&
        Number.isFinite(Number(point.dependent)),
    ).length < 2
  ) {
    throw new Error("Exact Test Data does not contain enough numeric points to plot.");
  }
  return {
    documentId,
    revisionId,
    documentKey: textValue(document.document_id, "document ID"),
    independent,
    dependent,
    points,
    artifact: result.data.blob,
    filename: result.data.filename,
  };
}
