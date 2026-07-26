import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { EngineeringColumnResizeHandle } from "./engineering-column-resize-handle";
import { ResizableSplitPane } from "./resizable-split-pane";

const meta = { title: "Foundation/ResizableSplitPane", component: ResizableSplitPane, parameters: { layout: "fullscreen" } } satisfies Meta<typeof ResizableSplitPane>;
export default meta;
type Story = StoryObj<typeof meta>;

const navigator = <nav aria-label="Material navigator" className="story-pane"><strong>Browse</strong><button type="button">Synthetic material family</button></nav>;
const main = <section className="story-pane"><strong>Results</strong><p>Selected records appear without changing workspace topology.</p></section>;
const context = <aside className="story-pane"><strong>Selection</strong><p>Context stays optional and resizable.</p></aside>;

export const Default: Story = { args: { id: "storybook-materials-default", navigator, main, context, navigatorLabel: "material navigator", contextLabel: "selection" } };

export const NarrowContextCollapsed: Story = {
  args: { id: "storybook-materials-compact", navigator, main, context },
  parameters: { viewport: { defaultViewport: "mobile1" } },
};

function ColumnResizeDemo() {
  const [width, setWidth] = useState(220);
  return <div className="story-column-resize-demo"><span style={{ width }}>{width}px material column</span><EngineeringColumnResizeHandle label="Material" width={width} min={160} max={360} onChange={setWidth} /></div>;
}

export const KeyboardResizeHandle: Story = {
  args: { id: "storybook-column-resize", navigator, main, context },
  render: () => <ColumnResizeDemo />,
};
