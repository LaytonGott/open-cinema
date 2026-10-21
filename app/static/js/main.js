// Bootstrap for the director app. Later beads extend init() by importing components.
import { initHeader, checkHealth } from "./components/header.js";
import { initOptionGroups } from "./components/option-groups.js";
import { initDescription } from "./components/description.js";

import { initStatusPanel } from "./components/status-panel.js";

import { initViewport } from "./components/viewport.js";

function init() {
  initViewport();
  initStatusPanel();
  initHeader();
  initOptionGroups();
  initDescription();
  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
