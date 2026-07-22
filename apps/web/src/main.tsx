import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app";
import "./styles.css";
import "./design/tokens.css";
import "./design/typography.css";
import "./design/primitives.css";
import "./design/layout.css";
import "./design/shell.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
