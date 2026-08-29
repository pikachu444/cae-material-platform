import type {
  MaterialResponse,
  MaterialStateResponse,
} from "../../materials/contracts";
import type { CanonicalTestDataDocumentResponse } from "../../test-data/contracts";
import type { CommonProcessingOutputResponse } from "./common-processing-contracts";
import type { ModelingSessionSummary } from "./session-controller";

export interface ExportPrerequisite {
  label: string;
  status: "current" | "missing" | "stale" | "not-supported";
  detail: string;
}

/**
 * A UI checklist only. `current` browser pins are deliberately not elevated to
 * server provenance. Delivery remains blocked until the API exposes the two
 * governed pins on the Processing Output (or an equivalent server verifier).
 */
export function exportPrerequisites({
  session,
  material,
  materialState,
  testData,
  output,
}: {
  session: ModelingSessionSummary | null | undefined;
  material: MaterialResponse | undefined;
  materialState: MaterialStateResponse | undefined;
  testData: CanonicalTestDataDocumentResponse | undefined;
  output: CommonProcessingOutputResponse | undefined;
}): ExportPrerequisite[] {
  const pin = (
    present: boolean,
    current: boolean,
    label: string,
    detail: string,
    staleDetail: string,
  ): ExportPrerequisite => ({
    label,
    status: !present ? "missing" : current ? "current" : "stale",
    detail: present && !current ? staleDetail : detail,
  });
  const materialCurrent = Boolean(session?.material && material
    && material.material_id === session.material.id
    && material.current_revision.id === session.material.revisionId);
  const stateCurrent = Boolean(session?.materialState && materialState
    && materialState.material_state_id === session.materialState.id
    && materialState.current_revision.id === session.materialState.revisionId);
  const sessionTestData = session?.testData;
  const testDataLoaded = Boolean(sessionTestData && testData
    && testData.test_data_document_id === sessionTestData.id
    && testData.current_revision.id === sessionTestData.revisionId);
  const testDataCurrent = Boolean(testDataLoaded && output
    && output.source_document.aggregate_id === sessionTestData?.id
    && output.source_document.revision_id === sessionTestData?.revisionId);
  const outputCurrent = Boolean(session?.processingOutput && output
    && output.processing_output_id === session.processingOutput.id
    && output.current_revision.id === session.processingOutput.revisionId);
  const mappingCurrent = Boolean(session?.mappingProfile && output
    && output.mapping_profile.aggregate_id === session.mappingProfile.id
    && output.mapping_profile.revision_id === session.mappingProfile.revisionId);

  const selectionCurrent = Boolean(session?.selection && output
    && session.selection.id === output.processing_output_id
    && session.selection.revisionId === output.current_revision.id);
  const proof = output?.export_provenance;
  const sessionPinCurrent = (key: "materialModelIr" | "neutralModel"): boolean => Boolean(
    session?.[key]
    && session.invalidation?.dispositions[key] !== "stale"
    && session.invalidation?.dispositions[key] !== "regenerate",
  );
  const proofCurrent = Boolean(proof && materialCurrent && stateCurrent && testDataCurrent
    && proof.material.aggregate_id === session?.material?.id
    && proof.material.revision_id === session?.material?.revisionId
    && proof.material_state.aggregate_id === session?.materialState?.id
    && proof.material_state.revision_id === session?.materialState?.revisionId);

  return [
    pin(Boolean(session?.material && material), materialCurrent, "Material", "Current session Material revision", "Loaded Material differs from the session revision"),
    pin(Boolean(session?.materialState && materialState), stateCurrent, "Material State", "Current session Material State revision", "Loaded Material State differs from the session revision"),
    pin(Boolean(session?.testData && testData && output), testDataCurrent, "Test Data", "Processing Output pins the current exact Test Data revision", "Loaded/session Test Data or the Processing Output source pin differs"),
    pin(Boolean(session?.mappingProfile && output), mappingCurrent, "Mapping Profile", "Exact Processing Output mapping revision", "Processing Output pins a different Mapping Profile revision"),
    pin(Boolean(session?.processingOutput && output), outputCurrent, "Processing Output", "Current selected Processing Output revision", "Loaded Processing Output differs from the session revision"),
    pin(Boolean(session?.selection && output), selectionCurrent, "Engineer selection", "Saved engineer decision pins the current Processing Output", "Engineer decision pins a different Processing Output revision"),
    {
      label: "Server provenance proof",
      status: !proof ? "missing" : proofCurrent ? "current" : "stale",
      detail: !proof
        ? "Historical output has no governed source proof and is never inferred."
        : proofCurrent
          ? "Server-verified Test Run, Material State, and Material revisions match."
          : "Server proof mismatches the selected exact source context.",
    },
    {
      label: "Material Model IR",
      status: session?.materialModelIr ? sessionPinCurrent("materialModelIr") ? "current" : "stale" : "missing",
      detail: session?.materialModelIr
        ? "Exact session IR revision is pinned; the server verifies its embedded Neutral relation."
        : "Choose and save an exact Material Model IR revision before target preview.",
    },
    {
      label: "Neutral representation",
      status: session?.neutralModel ? sessionPinCurrent("neutralModel") ? "current" : "stale" : "missing",
      detail: session?.neutralModel
        ? "Exact session Neutral revision is pinned; no first or latest Neutral revision is used."
        : "Promote or load an exact Neutral representation before target preview.",
    },
    {
      label: "Ephemeral target preview producer",
      status: "current",
      detail: "Server-only target preview validates the exact governed output, embedded IR, and Neutral relation. Delivery is unavailable pending UXC-06C2.",
    },
  ];
}
