// Submit error: shows state.error verbatim in [data-testid=submit-error], hidden when empty.
import { getState, subscribe } from "../state.js";

function render(state) {
  const el = document.querySelector("[data-testid=submit-error]");
  if (!el) return;
  const message = state.error || "";
  el.hidden = !message;
  el.textContent = message;
}

export function initSubmitError() {
  subscribe(render);
  render(getState());
}
