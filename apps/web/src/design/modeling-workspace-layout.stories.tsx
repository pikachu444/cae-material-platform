import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { ModelingWorkspaceLayout } from "./modeling-workspace-layout";

const meta = { title: "Foundation/ModelingWorkspaceLayout", component: ModelingWorkspaceLayout, parameters: { layout: "fullscreen" } } satisfies Meta<typeof ModelingWorkspaceLayout>;
export default meta;
type Story = StoryObj<typeof meta>;

function ModelingStory({ navigator = true, initiallyOpen = true }: { navigator?: boolean; initiallyOpen?: boolean }) {
  const [ribbonOpen, setRibbonOpen] = useState(initiallyOpen);
  return <ModelingWorkspaceLayout
    navigator={navigator ? <aside className="story-pane"><strong>Curves</strong><button type="button">Observed response</button><button type="button">Processed response</button></aside> : undefined}
    ribbon={<div className="story-ribbon"><span>Fit settings</span><button type="button">Update candidates</button></div>}
    plot={<section className="story-plot-placeholder" aria-label="Persistent plot placeholder">Persistent graph area</section>}
    dock={navigator ? undefined : <section className="story-pane">Delivery evidence stays below the plot.</section>}
    ribbonOpen={ribbonOpen}
    onRibbonOpenChange={setRibbonOpen}
  />;
}

const storyArgs = {
  ribbon: <span>Fit settings</span>,
  plot: <span>Persistent graph area</span>,
  ribbonOpen: true,
  onRibbonOpenChange: () => undefined,
};

export const Default: Story = { args: storyArgs, render: () => <ModelingStory /> };
export const RibbonCollapsed: Story = { args: storyArgs, render: () => <ModelingStory initiallyOpen={false} /> };
export const ExportReclaimsNavigator: Story = { args: storyArgs, render: () => <ModelingStory navigator={false} /> };
