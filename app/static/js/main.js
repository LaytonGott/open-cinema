// Bootstrap for the director app. Later beads extend init() by importing components.
import { initHeader, checkHealth } from "./components/header.js";
import { initOptionGroups } from "./components/option-groups.js";
import { initDescription } from "./components/description.js";

function init() {
  initHeader();
  initOptionGroups();
  initDescription();
  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
