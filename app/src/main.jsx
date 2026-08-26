import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./base.css";
import "./views.css";
import "./sources.css";
import "./analysis.css";
import "./dimensions.css";
import "./reports.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
