// Bootstrap for the director app. Later beads extend init() by importing components.
import { initHeader, checkHealth } from "./components/header.js";
import { initOptionGroups } from "./components/option-groups.js";

function init() {
  initHeader();
  initOptionGroups();
  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
