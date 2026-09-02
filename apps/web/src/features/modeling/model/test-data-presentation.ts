import type { CanonicalTestDataDocumentResponse } from "../../test-data/contracts";
import type { ModelingSessionRecordRef } from "./session-controller";

function specimenDisplayName(value: string): string {
  const normalized = value.trim();
  const numericSpecimen = normalized.match(/(?:specimen|sample|s)[-_ ]*(\d+)$/i)
    ?? normalized.match(/(\d+)$/);
  if (numericSpecimen) return `Specimen ${numericSpecimen[1].padStart(2, "0")}`;
  if (/^(?:specimen|sample)\b/i.test(normalized)) return normalized;
  return normalized ? `Specimen ${normalized}` : "Specimen";
}

export function curveRailIdentity(
  specimenId: string,
  revisionNo: number,
  sessionRevisionNo?: number,
): { specimen: string; revision: string } {
  const numericSpecimen = specimenId.match(/(?:specimen|sample|s)[-_ ]*(\d+)$/i)
    ?? specimenId.match(/(\d+)$/);
  return {
    specimen: numericSpecimen
      ? `Specimen ${numericSpecimen[1].padStart(2, "0")}`
      : specimenDisplayName(specimenId),
    revision: sessionRevisionNo === undefined
      ? `Revision r${revisionNo}`
      : `Session revision r${sessionRevisionNo}`,
  };
}

/** Fit keeps the exact pinned revision on one readable normal-surface line. */
export function fitRailIdentity(
  specimenId: string,
  libraryRevisionNo: number,
  exactRevisionNo?: number,
): string {
  return `${specimenDisplayName(specimenId)} · r${exactRevisionNo ?? libraryRevisionNo}`;
}

export function modelingCurveDisplayName(item: CanonicalTestDataDocumentResponse): string {
  const specimenMatch = item.specimen_id.match(/(?:specimen|sample|s)?[-_ ]*(\d+)$/i)
    ?? item.document_key.match(/(?:^|[-_ ])(\d+)$/);
  const method = item.method.trim().toLowerCase();
  const testType = method === "tensile" || method === "uniaxial tensile reference method"
    ? "Tensile test"
    : method.includes("planar")
      ? "Planar tension test"
      : method.includes("biaxial")
        ? "Biaxial tension test"
        : method.includes("uniaxial")
          ? "Uniaxial tension test"
          : method.includes("relaxation")
            ? "Relaxation test"
            : method.includes("dma")
              ? "DMA test"
              : "Test Data";
  return specimenMatch ? `${testType} ${specimenMatch[1].slice(-4).padStart(4, "0")}` : testType;
}

export function savedModelingInputDisplayLabel(
  reference: ModelingSessionRecordRef,
  current?: CanonicalTestDataDocumentResponse,
): string {
  const exactCurrentRevision = current?.test_data_document_id === reference.id
    && current.current_revision.id === reference.revisionId;
  if (exactCurrentRevision) {
    const pointCount = Math.max(0, ...current.channels.map((channel) => channel.point_count));
    return `${modelingCurveDisplayName(current)}${pointCount ? ` · ${pointCount} measured points` : ""}`;
  }

  const capturedLabel = reference.label.trim();
  return capturedLabel && capturedLabel !== current?.document_key
    ? capturedLabel
    : "Saved Test Data";
}
