// Bootstrap for the director app. Later beads extend init() by importing components.
import { initHeader, checkHealth } from "./components/header.js";

function init() {
  initHeader();
  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
