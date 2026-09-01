import { lazy, Suspense } from "react";

import { ModelingWorkspaceLayout } from "../../../../../design/modeling-workspace-layout";
import { EngineeringCurvePlotEmpty } from "../../../../../engineering-curve-plot";
import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import type { DmaTtsProcessWorkspaceProps } from "./dma-tts-process-workspace";

const DmaTtsProcessWorkspace = lazy(() =>
  import("./dma-tts-process-workspace").then((module) => ({
    default: module.DmaTtsProcessWorkspace,
  })),
);

interface DmaTtsProcessStageProps extends Omit<
  DmaTtsProcessWorkspaceProps,
  "testData" | "sourceDocument"
> {
  testData?: CanonicalTestDataDocumentResponse;
  sourceDocument?: Record<string, unknown>;
  onOpenData: () => void;
}

export function DmaTtsProcessStage({
  testData,
  sourceDocument,
  chart,
  ribbonOpen,
  onRibbonOpenChange,
  onOpenData,
  ...workspaceProps
}: DmaTtsProcessStageProps) {
  if (!testData || !sourceDocument) {
    return <ModelingWorkspaceLayout
      plot={<EngineeringCurvePlotEmpty
        width={chart.width}
        height={chart.height}
        blocked
        title="DMA Test Data is not ready"
        message="Return to Data and select the temperature-sweep test again."
        blockedActionLabel="Back to Data"
        onBackToData={onOpenData}
      />}
      ribbon={null}
      ribbonOpen={false}
      onRibbonOpenChange={onRibbonOpenChange}
    />;
  }

  return <Suspense fallback={<p className="loading-state">Loading DMA shift workspace…</p>}>
    <DmaTtsProcessWorkspace
      {...workspaceProps}
      chart={chart}
      ribbonOpen={ribbonOpen}
      onRibbonOpenChange={onRibbonOpenChange}
      testData={testData}
      sourceDocument={sourceDocument}
    />
  </Suspense>;
}
