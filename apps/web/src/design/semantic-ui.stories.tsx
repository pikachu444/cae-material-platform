import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  EngineeringPane,
  EngineeringPlotRegion,
  EngineeringSection,
  SemanticStatus,
  SemanticText,
  WorkbenchMessage,
} from "./semantic-ui";

const meta = {
  title: "Foundation/SemanticUI",
  parameters: { layout: "fullscreen" },
} satisfies Meta;

export default meta;
type Story = StoryObj<typeof meta>;

function SyntheticCurve() {
  return (
    <div className="story-semantic-plot-sample">
      <svg viewBox="0 0 640 260" role="img" aria-label="Synthetic non-production stress and strain curve">
        <path className="story-semantic-axis" d="M48 20V224H620" />
        <path className="story-semantic-curve" d="M48 224 C150 214 188 178 252 153 S365 92 430 83 S535 70 620 42" />
        <text x="48" y="248">Synthetic strain</text>
        <text x="56" y="36">Synthetic stress</text>
      </svg>
    </div>
  );
}

function ParameterEvidence() {
  return (
    <>
      <SemanticText semanticRole="sectionHeading" as="h3">Candidate evidence</SemanticText>
      <dl className="story-semantic-values">
        <div><dt>Candidate</dt><dd>B</dd></div>
        <div><dt>Residual</dt><dd>0.018 synthetic</dd></div>
        <div><dt>Revision</dt><dd>demo-r2</dd></div>
      </dl>
      <SemanticText semanticRole="metadata">Synthetic non-production values</SemanticText>
    </>
  );
}

export const ContractExamples: Story = {
  render: () => (
    <main className="story-semantic-foundation ux-page">
      <EngineeringPane label="Semantic UI contract example">
        <header className="story-semantic-header">
          <SemanticText semanticRole="workspaceTitle">Semantic UI foundation</SemanticText>
          <SemanticText semanticRole="metadata">Developer example · synthetic non-production data</SemanticText>
        </header>

        <EngineeringSection label="Typography roles">
          <SemanticText semanticRole="sectionHeading">Typography roles</SemanticText>
          <div className="story-semantic-role-grid">
            <SemanticText semanticRole="label">Selected model</SemanticText>
            <SemanticText semanticRole="value">Synthetic candidate B</SemanticText>
            <SemanticText semanticRole="metadata">Revision demo-r2 · method example-v1</SemanticText>
            <SemanticText semanticRole="importantResult">Residual 0.018 synthetic</SemanticText>
          </div>
        </EngineeringSection>

        <EngineeringSection label="Actual statuses">
          <SemanticText semanticRole="sectionHeading">Actual statuses</SemanticText>
          <div className="story-semantic-statuses">
            <SemanticStatus status="success" label="Saved model ready" detail="Revision demo-r2" />
            <SemanticStatus status="warning" label="Review required" detail="Synthetic validation" />
            <SemanticStatus status="danger" label="Export unavailable" detail="No saved model" />
          </div>
          <SemanticText semanticRole="metadata">Counts, revisions, methods, and material families remain neutral metadata.</SemanticText>
        </EngineeringSection>

        <EngineeringSection label="Workbench messages">
          <SemanticText semanticRole="sectionHeading">Workbench messages</SemanticText>
          <div className="story-semantic-message-grid">
            <WorkbenchMessage kind="loading" title="Loading test data">The selected revision remains pinned.</WorkbenchMessage>
            <WorkbenchMessage kind="empty" title="No candidate results">Adjust a current filter without changing the saved model.</WorkbenchMessage>
            <WorkbenchMessage kind="blocked" title="Export blocked">Save an explicit model before export.</WorkbenchMessage>
            <WorkbenchMessage kind="error" title="Preview failed">The last valid preview and exact inputs remain available.</WorkbenchMessage>
            <WorkbenchMessage kind="recovery" title="Preview can be retried" action={{ label: "Retry preview", onClick: () => undefined }}>Retry with the preserved revision and inputs.</WorkbenchMessage>
            <WorkbenchMessage kind="engineeringCondition" title="Engineering condition">The synthetic values use the displayed coordinate system.</WorkbenchMessage>
          </div>
        </EngineeringSection>

        <EngineeringSection label="Plot regions">
          <SemanticText semanticRole="sectionHeading">Plot-only region</SemanticText>
          <EngineeringPlotRegion label="Synthetic processed response" plot={<SyntheticCurve />} />
          <SemanticText semanticRole="sectionHeading">Plot with contract-backed companion</SemanticText>
          <EngineeringPlotRegion
            label="Synthetic fit comparison"
            plot={<SyntheticCurve />}
            companion={<ParameterEvidence />}
            companionLabel="Synthetic candidate evidence"
          />
        </EngineeringSection>
      </EngineeringPane>
    </main>
  ),
};
