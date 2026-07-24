import type {
  CanonicalTestDataDocumentResponse,
  CommonProcessingOutputResponse,
  MaterialResponse,
  MaterialStateResponse,
} from "./types";
import type { ModelingSessionSummary } from "./modeling-session-context";

/**
 * Export may hand the family adapter an output only when all client-visible exact pins agree.
 * The adapter then performs its existing server-side Material State/model checks.
 */
export function hasVerifiedExactExportChain({
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
}): boolean {
  if (!session?.material || !session.materialState || !session.testData || !session.mappingProfile || !session.processingOutput || !material || !materialState || !testData || !output) return false;
  const materialMatches = material.material_id === session.material.id
    && material.current_revision.id === session.material.revisionId;
  const stateMatches = materialState.material_state_id === session.materialState.id
    && materialState.current_revision.id === session.materialState.revisionId;
  const testDataMatches = testData.test_data_document_id === session.testData.id
    && testData.current_revision.id === session.testData.revisionId;
  const outputMatches = output.processing_output_id === session.processingOutput.id
    && output.current_revision.id === session.processingOutput.revisionId
    && output.source_document.aggregate_id === session.testData.id
    && output.source_document.revision_id === session.testData.revisionId;
  const mappingMatches = output.mapping_profile.aggregate_id === session.mappingProfile.id
    && output.mapping_profile.revision_id === session.mappingProfile.revisionId;
  return materialMatches && stateMatches && testDataMatches && outputMatches && mappingMatches;
}
