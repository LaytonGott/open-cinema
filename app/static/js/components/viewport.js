// Viewport: sets data-state on [data-testid=viewport] from the shared state.
import { getState, subscribe } from "../state.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

function stateOf(state) {
  const shot = state.shot;
  if (!shot) return state.submitting ? "working" : "empty";
  switch (shot.status) {
    case "done":
      return "result";
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
}

export function initViewport() {
  subscribe(render);
  render(getState());
}
