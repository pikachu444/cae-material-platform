import { createRoot } from "react-dom/client";
import "./shared/styles/global.css";

const mount = document.getElementById("root");
if (!mount) throw new Error("Application root is missing");

// Fixture activation has one boundary: Vite's explicit prototype mode. The
// ordinary build does not import the fixture generator or prototype transport.
if (import.meta.env.MODE === "prototype") {
  import("./prototype/PrototypeApp").then(({ PrototypeApp }) => {
    createRoot(mount).render(<PrototypeApp />);
  });
} else {
  import("./app/LiveApp").then(({ LiveApp }) => {
    createRoot(mount).render(<LiveApp />);
  });
}
