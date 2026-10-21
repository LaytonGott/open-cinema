// Status panel: renders state.shot (server record) into [data-testid=status-panel].
import { getState, subscribe } from "../state.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

function render(state) {
  const panel = q("status-panel");
  if (!panel) return;
  const shot = state.shot;
  if (!shot) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  panel.dataset.status = shot.status;
  q("status-label").textContent = shot.message;
  const pct = Math.round(shot.progress * 100);
  const bar = q("progress-bar");
  bar.setAttribute("aria-valuenow", String(pct));
  const fill = bar.querySelector(".progress-fill");
  if (fill) fill.style.width = pct + "%";
  const stages = shot.stages || [];
  for (const id of ["generate", "optics"]) {
    const el = q("stage-" + id);
    const st = stages.find((s) => s.id === id);
    if (el && st) el.dataset.state = st.state;
  }
}

export function initStatusPanel() {
  subscribe(render);
  render(getState());
}
