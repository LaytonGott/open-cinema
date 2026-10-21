// Status panel: renders state.shot (server record) into [data-testid=status-panel].
import { getState, subscribe } from "../state.js";
import { cancelCurrentShot } from "../actions.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

export function formatElapsed(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const s = total % 60;
  return Math.floor(total / 60) + ":" + (s < 10 ? "0" : "") + s;
}

let timer = null;
let baseRecord = null;
let baseAt = 0;

function stopTimer() {
  if (timer !== null) clearInterval(timer);
  timer = null;
  baseRecord = null;
}

function tick() {
  const el = q("elapsed");
  if (!el || !baseRecord) return;
  el.textContent = formatElapsed(baseRecord.elapsed_s + (Date.now() - baseAt) / 1000);
}

function syncTimer(shot, running) {
  if (!running) {
    stopTimer();
    return;
  }
  if (shot !== baseRecord) {
    baseRecord = shot;
    baseAt = Date.now();
  }
  if (timer === null) timer = setInterval(tick, 1000);
}

function render(state) {
  const panel = q("status-panel");
  if (!panel) return;
  const shot = state.shot;
  if (!shot) {
    panel.hidden = true;
    stopTimer();
    return;
  }
  panel.hidden = shot.status === "done";
  const elapsed = q("elapsed");
  if (elapsed) elapsed.textContent = formatElapsed(shot.elapsed_s);
  syncTimer(shot, !panel.hidden && ["queued", "generating", "optics"].includes(shot.status));
  const dot = q("record-dot");
  if (dot) dot.hidden = !["queued", "generating", "optics"].includes(shot.status);
  const cancel = q("cancel-button");
  if (cancel) cancel.hidden = !["queued", "generating", "optics"].includes(shot.status);
  panel.dataset.status = shot.status;
  q("status-label").textContent = shot.status === "cancelled" ? "Cancelled." : shot.message;
  const errorEl = q("error-message");
  if (errorEl) {
    const failed = shot.status === "failed" && shot.error;
    errorEl.hidden = !failed;
    errorEl.textContent = failed ? shot.error.message : "";
  }
  const retry = q("retry-button");
  if (retry) {
    const retryable = shot.status === "failed" || shot.status === "cancelled";
    retry.hidden = !retryable;
    retry.textContent = shot.status === "failed" && shot.before_url ? "Retry optics" : "Try again";
  }
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
  const cancel = q("cancel-button");
  if (cancel) cancel.addEventListener("click", cancelCurrentShot);
  subscribe(render);
  render(getState());
}
