// Viewport: sets data-state on [data-testid=viewport] from the shared state.
import { getState, subscribe, shownVersionOf } from "../state.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

function stateOf(state) {
  const shot = state.shot;
  if (!shot) return state.submitting ? "working" : "empty";
  switch (shot.status) {
    case "done":
      return "result";
    case "optics":
      return shot.versions && shot.versions.length > 0 ? "result" : "working";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
    default:
      return "working";
  }
}

function render(state) {
  const viewport = q("viewport");
  if (!viewport) return;
  const value = stateOf(state);
  viewport.dataset.state = value;
  const hint = q("viewport-hint");
  if (hint) hint.hidden = value !== "empty";
  renderHud(state);
}

function renderHud(state) {
  const hud = q("hud");
  if (!hud) return;
  const p = state.shot ? state.shot.params : state.form;
  if (!p) return;
  const list = (state.options && state.options.framings) || [];
  const found = list.find((f) => f.id === p.framing);
  const framing = found ? found.label : p.framing;
  const version = state.shot ? shownVersionOf(state) : null;
  const aperture = version && version.aperture != null ? version.aperture : p.aperture;
  let text = p.lens_mm + " mm  f/" + aperture + "  " + String(framing || "").toUpperCase();
  const d = state.shot && state.shot.derived ? state.shot.derived.subject_distance_m : null;
  if (typeof d === "number" && isFinite(d)) {
    text += "  about " + (d < 10 ? d.toFixed(1) : String(Math.round(d))) + " m";
  }
  hud.textContent = text;
}

export function initViewport() {
  subscribe(render);
  render(getState());
}
