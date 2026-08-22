import type { Preview } from "@storybook/react-vite";

import "../src/styles.css";
import "../src/design/tokens.css";
import "../src/design/typography.css";
import "../src/design/primitives.css";
import "../src/design/layout.css";
import "../src/features/modeling/ui/modeling-core-workbench.css";
import "../src/design/shell.css";
import "./preview.css";

const preview: Preview = {
  parameters: {
    layout: "fullscreen",
    a11y: {
      context: "body",
    },
  },
};

export default preview;
