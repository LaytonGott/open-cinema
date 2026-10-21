// History strip: renders state.history (newest first) into [data-testid=history-list].
import { getState, subscribe } from "../state.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

function framingLabel(state, id) {
  const list = (state.options && state.options.framings) || [];
  const found = list.find((f) => f.id === id);
  return found ? found.label : id;
}

function render(state) {
  const list = q("history-list");
  if (!list) return;
  const currentId = state.shot ? state.shot.id : null;
  list.replaceChildren();
  for (const shot of state.history) {
    const p = shot.params || {};
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("data-testid", "history-item");
    btn.dataset.shotId = shot.id;
    btn.dataset.status = shot.status;
    if (shot.id === currentId) btn.setAttribute("aria-current", "true");

    const title = document.createElement("span");
    title.className = "history-title";
    title.textContent = String(p.description || "").slice(0, 40);
    const lens = document.createElement("span");
    lens.className = "history-lens";
    lens.textContent = p.lens_mm + "mm";
    const aperture = document.createElement("span");
    aperture.className = "history-aperture";
    aperture.textContent = "f/" + p.aperture;
    const framing = document.createElement("span");
    framing.className = "history-framing";
    framing.textContent = framingLabel(state, p.framing);
    const dot = document.createElement("span");
    dot.className = "status-dot";
    dot.setAttribute("aria-hidden", "true");
    const status = document.createElement("span");
    status.className = "history-status";
    status.textContent = shot.status;

    btn.append(title, lens, aperture, framing, dot, status);
    li.append(btn);
    list.append(li);
  }
}

export function initHistory() {
  subscribe(render);
  render(getState());
}
