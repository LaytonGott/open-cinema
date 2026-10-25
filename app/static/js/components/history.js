// History strip: renders state.history (newest first) into [data-testid=history-list].
import { getState, subscribe } from "../state.js";
import { newShot, selectShot } from "../actions.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

function framingLabel(state, id) {
  const list = (state.options && state.options.framings) || [];
  const found = list.find((f) => f.id === id);
  return found ? found.label : id;
}

const items = new Map();
let lastSignature = null;

function buildItem(shot) {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.setAttribute("data-testid", "history-item");
  btn.dataset.shotId = shot.id;
  const spans = {};
  for (const name of ["title", "lens", "aperture", "framing", "dot", "status"]) {
    const span = document.createElement("span");
    span.className = name === "dot" ? "status-dot" : "history-" + name;
    spans[name] = span;
  }
  spans.dot.setAttribute("aria-hidden", "true");
  btn.append(spans.title, spans.lens, spans.aperture, spans.framing, spans.dot, spans.status);
  li.append(btn);
  return { li, btn, spans };
}

function setText(el, text) {
  if (el.textContent !== text) el.textContent = text;
}

function render(state) {
  const list = q("history-list");
  if (!list) return;
  const currentId = state.shot ? state.shot.id : null;
  const signature = JSON.stringify([
    state.history.map((s) => [s.id, s.status, s.params]),
    currentId,
    state.history.map((s) => framingLabel(state, (s.params || {}).framing)),
  ]);
  if (signature === lastSignature && items.size === list.children.length) return;
  lastSignature = signature;

  const seen = new Set();
  const ordered = [];
  for (const shot of state.history) {
    const p = shot.params || {};
    let item = items.get(shot.id);
    if (!item) {
      item = buildItem(shot);
      items.set(shot.id, item);
    }
    seen.add(shot.id);
    ordered.push(item.li);
    item.btn.dataset.status = shot.status;
    if (shot.id === currentId) item.btn.setAttribute("aria-current", "true");
    else item.btn.removeAttribute("aria-current");
    setText(item.spans.title, String(p.description || "").slice(0, 40));
    setText(item.spans.lens, p.lens_mm + "mm");
    setText(item.spans.aperture, "f/" + p.aperture);
    setText(item.spans.framing, framingLabel(state, p.framing));
    setText(item.spans.status, shot.status);
  }
  for (const [id, item] of items) {
    if (!seen.has(id)) {
      item.li.remove();
      items.delete(id);
    }
  }
  // Move an li only when it is not already where it belongs.
  let cursor = list.firstElementChild;
  for (const li of ordered) {
    if (li === cursor) cursor = cursor.nextElementSibling;
    else list.insertBefore(li, cursor);
  }
}

export function initHistory() {
  const list = q("history-list");
  if (list) {
    list.addEventListener("click", (event) => {
      const item = event.target.closest('[data-testid="history-item"]');
      if (item) selectShot(item.dataset.shotId);
    });
  }
  const fresh = q("history-new");
  if (fresh) fresh.addEventListener("click", newShot);
  subscribe(render);
  render(getState());
}
