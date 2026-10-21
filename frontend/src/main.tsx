import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Dev-only handle for scripted UI checks (not included in production builds).
if (import.meta.env.DEV) {
  void import("./store").then((m) => {
    (window as unknown as { __sr: unknown }).__sr = m;
  });
}
