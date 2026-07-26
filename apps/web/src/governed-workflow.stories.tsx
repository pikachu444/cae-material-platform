import type { Meta, StoryObj } from "@storybook/react-vite";

import { ModelingStageShell } from "./modeling-stage-shell";
import type { ModelingSessionSummary } from "./modeling-session-context";
import { TargetPreviewResult } from "./modeling-target-preview-result";
import { MappingStatusList } from "./solver-card-delivery-ui";
import type { SolverCardEvidence } from "./solver-card-delivery";
import type { TargetPreviewResponse } from "./types";

const currentSession = {
  version: 3,
  updatedAt: "2026-07-27T00:00:00Z",
  materialFamily: "metal",
  objective: "Synthetic reference workflow",
  material: { id: "synthetic-material", revisionId: "synthetic-material-r2", label: "Reference alloy specimen", revisionNo: 2 },
  materialState: { id: "synthetic-state", revisionId: "synthetic-state-r1", label: "Reference condition", revisionNo: 1 },
  testData: { id: "synthetic-test", revisionId: "synthetic-test-r3", label: "Synthetic tensile input", revisionNo: 3 },
  mappingProfile: { id: "synthetic-mapping", revisionId: "synthetic-mapping-r1", label: "Reference mapping", revisionNo: 1 },
  processingOutput: { id: "synthetic-output", revisionId: "synthetic-output-r4", label: "Processed reference curve", revisionNo: 4 },
  selection: { id: "synthetic-selection", revisionId: "synthetic-selection-r1", label: "Explicit reference candidate", revisionNo: 1 },
  workspace: { activeStage: "fit", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
} satisfies ModelingSessionSummary;

const mappingItems = [
  { name: "density", ir_path: "/properties/density", target_representation: "*DENSITY", status: "exact", detail: "The immutable IR value is represented directly." },
  { name: "elastic_response", ir_path: "/elastic", target_representation: "*ELASTIC", status: "transformed", detail: "The exporter recorded the unit and representation transform." },
  { name: "hardening_response", ir_path: "/plastic", target_representation: "*PLASTIC", status: "approximated", detail: "Explicit acknowledgement is required before delivery." },
  { name: "unavailable_extension", ir_path: "/extension/reference", target_representation: null, status: "unsupported", detail: "This reference target cannot represent the requested extension." },
] satisfies SolverCardEvidence["mappingItems"];

const preview = {
  preview_identity: "reference/non-production-preview-001",
  filename: "reference_non_production.inp",
  native_text: "** reference/non-production preview\n*MATERIAL, NAME=REFERENCE\n*DENSITY\n7.80e-09\n",
  native_sha256: "a".repeat(64), mapping_report_sha256: "b".repeat(64), mapping: { items: mappingItems },
  source: { processing_output_id: "synthetic-output", processing_output_revision_id: "synthetic-output-r4", processing_output_sha256: "c".repeat(64), material_id: "synthetic-material", material_revision_id: "synthetic-material-r2", material_state_id: "synthetic-state", material_state_revision_id: "synthetic-state-r1", material_model_ir_revision_id: "synthetic-ir-r1", neutral_material_id: "synthetic-neutral", neutral_material_revision_id: "synthetic-neutral-r1" },
  target: { solver: "reference-target", version: "non-production", unit_system: "SI", solver_material_id: 101, material_name: "REFERENCE_NON_PRODUCTION" }, acknowledgement_identity: "reference/non-production-acknowledgement-001", non_production: true, delivery_status: "unavailable_pending_uxc_06c2",
} satisfies TargetPreviewResponse;

const meta = { title: "Governed/WorkflowComponents" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const ModelingStageSelectedWithReadiness: Story = { render: () => <ModelingStageShell session={currentSession} activeStage="fit" onStageChange={() => undefined} /> };
export const ModelingStageBlocked: Story = { render: () => <ModelingStageShell session={{ ...currentSession, material: undefined, materialState: undefined, testData: undefined, mappingProfile: undefined, processingOutput: undefined, selection: undefined }} activeStage="export" onStageChange={() => undefined} /> };
export const MappingExactTransformedApproximatedAndUnsupported: Story = { render: () => <MappingStatusList items={mappingItems} /> };
export const MappingEmpty: Story = { render: () => <MappingStatusList items={[]} /> };
export const TargetPreviewMixedMappingStates: Story = { render: () => <div style={{ maxWidth: 1100, padding: 24 }}><TargetPreviewResult preview={preview} /></div> };
