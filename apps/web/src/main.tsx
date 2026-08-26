import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app";
import { loadApiConfig } from "./api";
import { bootstrapDisplayDensity } from "./design/display-density";
import "./styles.css";
import "./design/tokens.css";
import "./design/typography.css";
import "./design/primitives.css";
import "./features/test-data/ui/governed-import-route.css";
import "./design/layout.css";
import "./features/materials/ui/materials.css";
import "./design/shell.css";
import "./features/activity/ui/activity.css";

// Apply the browser-local, product-wide preference before React creates the
// first shell frame. This prevents a Compact/Standard/Large flash on reload.
bootstrapDisplayDensity(loadApiConfig());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
