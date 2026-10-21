// Bootstrap for the director app. Later beads extend init() by importing components.
import { initHeader, checkHealth } from "./components/header.js";
import { initOptionGroups } from "./components/option-groups.js";
import { initDescription } from "./components/description.js";

import { initStatusPanel } from "./components/status-panel.js";

function init() {
  initStatusPanel();
  initHeader();
  initOptionGroups();
  initDescription();
  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
