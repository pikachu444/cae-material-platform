import type { ApiConfig } from "../../../../../shared/api";
import type { MaterialResponse, MaterialStateResponse, PropertySetResponse } from "../../../../materials/contracts";
import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import type { CommonProcessingOutputResponse } from "../../../model/common-processing-contracts";
import type { LinearViscoelasticCatalogContext } from "../../../model/linear-viscoelastic-calibration-contracts";
import { savedModelingInputDisplayLabel } from "../../../model/test-data-presentation";
import type {
  ModelingSessionEvent,
  ModelingSessionRecordRef,
  ModelingSessionSummary,
} from "../../../model/session-controller";
import { PolymerLinearViscoelasticWorkspace } from "./polymer-linear-viscoelastic-workspace";

interface PolymerFitSource {
  testData?: CanonicalTestDataDocumentResponse;
  ref?: ModelingSessionRecordRef;
  displayLabel?: string;
  document?: Record<string, unknown> | null;
  processingOutput?: CommonProcessingOutputResponse;
}

interface PolymerFitCatalog {
  material?: MaterialResponse;
  materialState?: MaterialStateResponse;
  propertySet?: PropertySetResponse;
}

interface PolymerLinearViscoelasticStageProps {
  config: ApiConfig;
  source: PolymerFitSource;
  catalog: PolymerFitCatalog;
  session?: ModelingSessionSummary | null;
  documents: CanonicalTestDataDocumentResponse[];
  materialDisplayLabel?: string;
  ribbonOpen: boolean;
  onRibbonOpenChange: (open: boolean) => void;
  onSessionEvent?: (event: ModelingSessionEvent) => void;
  onRestoreSavedInput: () => void;
  onOpenData: () => void;
  onOpenProcess: () => void;
  onContinue: () => void;
}

function resolveCatalogContext(
  catalog: PolymerFitCatalog,
  session?: ModelingSessionSummary | null,
): LinearViscoelasticCatalogContext | undefined {
  const { material, materialState, propertySet } = catalog;
  if (!material || !materialState || !propertySet
    || session?.material?.id !== material.material_id
    || session.material.revisionId !== material.current_revision.id
    || session?.materialState?.id !== materialState.material_state_id
    || session.materialState.revisionId !== materialState.current_revision.id
    || propertySet.material_state_id !== materialState.material_state_id
    || propertySet.current_revision.content.material_state_revision_id !== materialState.current_revision.id) {
    return undefined;
  }
  return {
    material: { id: material.material_id, revisionId: material.current_revision.id },
    materialState: { id: materialState.material_state_id, revisionId: materialState.current_revision.id },
    propertySet: { id: propertySet.property_set_id, revisionId: propertySet.current_revision.id },
  };
}

export function PolymerLinearViscoelasticStage({
  config,
  source,
  catalog,
  session,
  documents,
  materialDisplayLabel,
  ribbonOpen,
  onRibbonOpenChange,
  onSessionEvent,
  onRestoreSavedInput,
  onOpenData,
  onOpenProcess,
  onContinue,
}: PolymerLinearViscoelasticStageProps) {
  const staleTestDataDocument = session?.stalePointers?.testData
    ? documents.find((item) => item.test_data_document_id === session.stalePointers?.testData?.id)
    : undefined;
  return <PolymerLinearViscoelasticWorkspace
    config={config}
    testData={source.testData}
    testDataRef={source.ref}
    sourceDisplayLabel={source.displayLabel}
    materialDisplayLabel={materialDisplayLabel}
    sourceDocument={source.document}
    processingOutput={source.processingOutput}
    catalogContext={resolveCatalogContext(catalog, session)}
    initialSelection={session?.selection}
    initialSelectedModel={session?.materialModelIr}
    staleTestData={session?.stalePointers?.testData}
    staleTestDataDisplayLabel={session?.stalePointers?.testData
      ? savedModelingInputDisplayLabel(session.stalePointers.testData, staleTestDataDocument)
      : undefined}
    staleSelection={session?.stalePointers?.selection}
    ribbonOpen={ribbonOpen}
    onRibbonOpenChange={onRibbonOpenChange}
    onSelectionSaved={(selection) => onSessionEvent?.({ type: "SELECT_CANDIDATE", selection })}
    onSelectedModelSaved={(model) => onSessionEvent?.({ type: "SET_CURRENT", key: "materialModelIr", value: model })}
    onRestoreSavedInput={onRestoreSavedInput}
    onOpenData={onOpenData}
    onOpenProcess={onOpenProcess}
    onContinue={onContinue}
  />;
}
