import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Fonts are bundled from npm so Bengali/Hindi render offline with correct conjuncts.
import "@fontsource/noto-sans/400.css";
import "@fontsource/noto-sans/700.css";
import "@fontsource/noto-sans-bengali/400.css";
import "@fontsource/noto-sans-bengali/700.css";
import "@fontsource/noto-sans-devanagari/400.css";
import "@fontsource/noto-sans-devanagari/700.css";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
