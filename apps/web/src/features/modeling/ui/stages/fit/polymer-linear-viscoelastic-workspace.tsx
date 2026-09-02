import { lazy, Suspense } from "react";

import type { ApiConfig } from "../../../../../shared/api";
import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import type { CommonProcessingOutputResponse } from "../../../model/common-processing-contracts";
import type { ModelingSessionRecordRef } from "../../../model/session-controller";
import type { LinearViscoelasticCatalogContext } from "../../../model/linear-viscoelastic-calibration-contracts";

const PolymerLinearViscoelasticFit = lazy(() => import("./polymer-linear-viscoelastic-fit").then((module) => ({
  default: module.PolymerLinearViscoelasticFit,
})));

interface PolymerLinearViscoelasticWorkspaceProps {
  config: ApiConfig;
  testData?: CanonicalTestDataDocumentResponse;
  testDataRef?: ModelingSessionRecordRef;
  sourceDisplayLabel?: string;
  materialDisplayLabel?: string;
  sourceDocument?: Record<string, unknown> | null;
  processingOutput?: CommonProcessingOutputResponse;
  catalogContext?: LinearViscoelasticCatalogContext;
  initialSelection?: ModelingSessionRecordRef;
  initialSelectedModel?: ModelingSessionRecordRef;
  staleTestData?: ModelingSessionRecordRef;
  staleTestDataDisplayLabel?: string;
  staleSelection?: ModelingSessionRecordRef;
  onSelectionSaved?: (selection: ModelingSessionRecordRef) => void;
  onSelectedModelSaved?: (model: ModelingSessionRecordRef) => void;
  onRestoreSavedInput?: () => void;
  onOpenData?: () => void;
  onOpenProcess?: () => void;
  onContinue?: () => void;
  ribbonOpen?: boolean;
  onRibbonOpenChange?: (open: boolean) => void;
}

export function PolymerLinearViscoelasticWorkspace({
  config,
  testData,
  testDataRef,
  sourceDisplayLabel,
  materialDisplayLabel,
  sourceDocument,
  processingOutput,
  catalogContext,
  initialSelection,
  initialSelectedModel,
  staleTestData,
  staleTestDataDisplayLabel,
  staleSelection,
  onSelectionSaved,
  onSelectedModelSaved,
  onRestoreSavedInput,
  onOpenData,
  onOpenProcess,
  onContinue,
  ribbonOpen,
  onRibbonOpenChange,
}: PolymerLinearViscoelasticWorkspaceProps) {
  return (
    <Suspense fallback={<p role="status" aria-label="Loading Polymer Fit workspace" aria-live="polite">Loading Polymer Fit workspace…</p>}>
      <PolymerLinearViscoelasticFit
        config={config}
        testData={testData}
        testDataRef={testDataRef}
        sourceDisplayLabel={sourceDisplayLabel}
        materialDisplayLabel={materialDisplayLabel}
        sourceDocument={sourceDocument}
        processingOutput={processingOutput}
        catalogContext={catalogContext}
        initialSelection={initialSelection}
        initialSelectedModel={initialSelectedModel}
        staleTestData={staleTestData}
        staleTestDataDisplayLabel={staleTestDataDisplayLabel}
        staleSelection={staleSelection}
        ribbonOpen={ribbonOpen}
        onRibbonOpenChange={onRibbonOpenChange}
        onSelectionSaved={onSelectionSaved}
        onSelectedModelSaved={onSelectedModelSaved}
        onRestoreSavedInput={onRestoreSavedInput}
        onOpenData={onOpenData}
        onOpenProcess={onOpenProcess}
        onContinue={onContinue}
      />
    </Suspense>
  );
}
