// Bootstrap for the director app. Later beads extend init() by importing components.
import { initHeader, checkHealth } from "./components/header.js";
import { initOptionGroups } from "./components/option-groups.js";
import { initDescription } from "./components/description.js";
import { initAperture } from "./components/aperture.js";

import { initStatusPanel } from "./components/status-panel.js";

import { initOpticsControls } from "./components/optics-controls.js";
import { initViewport } from "./components/viewport.js";
import { initPlayer } from "./components/player.js";

import { initHistory } from "./components/history.js";
import { initSubmitError } from "./components/submit-error.js";
import { listShots } from "./api.js";
import { getState, setHistory } from "./state.js";
import { selectShot } from "./actions.js";
import { initHistoryRefresh } from "./history-refresh.js";

// Loads the server's shot list once; records already in state win, errors are left to the health banner.
async function loadHistory() {
  try {
    const body = await listShots();
    const loaded = (body && body.shots) || [];
    const known = new Set(getState().history.map((r) => r.id));
    setHistory([...getState().history, ...loaded.filter((r) => !known.has(r.id))]);
    const state = getState();
    if (state.shot === null && !state.submitting && state.history.length > 0) {
      selectShot(state.history[0].id);
    }
  } catch (e) {
    // ignored on purpose
  }
}

function init() {
  initHistory();
  loadHistory();
  initHistoryRefresh();
  initViewport();
  initPlayer();
  initOpticsControls();
  initStatusPanel();
  initHeader();
  initOptionGroups();
  initDescription();
  initAperture();
  initSubmitError();
  checkHealth();
}

document.addEventListener("DOMContentLoaded", init);
