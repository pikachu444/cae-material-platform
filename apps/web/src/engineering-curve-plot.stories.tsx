import type { Meta, StoryObj } from "@storybook/react-vite";

import { EngineeringCurvePlot } from "./engineering-curve-plot";
import type { CommonCurveStage, CommonProcessingPreview } from "./features/modeling";

const baseStage: CommonCurveStage = { ordinal: 0, method_id: "mapping", method_version: "1.0.0", point_count: 3, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] }], diagnostics: ["Mapped source retained."], scalar_results: [] };
const activeStage: CommonCurveStage = { ordinal: 1, method_id: "curve.resample_linear", method_version: "1.0.0", point_count: 4, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.0007, 0.0014, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 1.5e8, 2.5e8, 3e8] }], diagnostics: ["Processed preview has a separate sampling grid."], scalar_results: [] };
const preview: CommonProcessingPreview = { execution_mode: "preview", promotable: false, source_document_sha256: "a".repeat(64), mapping_profile_sha256: "b".repeat(64), independent_quantity: "strain.engineering", stages: [baseStage, activeStage] };

const meta = { title: "Foundation/EngineeringCurvePlot", component: EngineeringCurvePlot, decorators: [(Story) => <div style={{ minWidth: 820, padding: 16 }}><Story /></div>] } satisfies Meta<typeof EngineeringCurvePlot>;
export default meta;
type Story = StoryObj<typeof meta>;

const args = { preview, activeStage, baseStage, width: 920, height: 460 };

export const Default: Story = { args };
export const SelectionEnabled: Story = { args: { ...args, onApplySelection: () => undefined } };
export const EmptyCompatibleSeries: Story = { args: { ...args, activeStage: { ...activeStage, series: [] } } };
