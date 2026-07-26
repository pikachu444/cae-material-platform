import { useEffect } from "react";
import type { Meta, StoryObj } from "@storybook/react-vite";

import { ApplicationShell, publishWorkspaceCommandState, publishWorkspaceStatus } from "./application-shell";

const meta = {
  title: "Foundation/ApplicationShell",
  component: ApplicationShell,
  parameters: { layout: "fullscreen" },
} satisfies Meta<typeof ApplicationShell>;

export default meta;
type Story = StoryObj<typeof meta>;

function StoryWorkspace({
  selection = "Curve comparison",
  revision = "Draft",
  jobs = "No active job",
  warnings = "0 warnings",
  command,
  degraded = false,
}: {
  selection?: string;
  revision?: string;
  jobs?: string;
  warnings?: string;
  command?: string;
  degraded?: boolean;
}) {
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (command) publishWorkspaceCommandState(command);
      publishWorkspaceStatus({
        selection,
        revision,
        jobs,
        warnings,
        connection: degraded ? "degraded" : "online",
      });
    });
    return () => window.clearTimeout(timer);
  }, [command, degraded, jobs, revision, selection, warnings]);
  return <section className="story-workspace-surface" aria-label="Modeling workspace context"><p>Persistent engineering context</p></section>;
}

const navigate = () => undefined;

export const Default: Story = {
  args: { path: "/materials", navigate, children: <StoryWorkspace selection="No material selected" revision="Current records" /> },
};

export const ModelingCommandAndStatusContext: Story = {
  args: { path: "/modeling", navigate, children: <StoryWorkspace command="modeling:fit" /> },
};

export const WarningAndDegradedConnection: Story = {
  args: { path: "/modeling", navigate, children: <StoryWorkspace command="modeling:fit" jobs="Preview needs review" warnings="1 warning" degraded /> },
};
