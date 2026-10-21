// Scene description field and Generate button enable rules (no submit logic here).
import { getState, setState, subscribe } from "../state.js";
import { submitShot } from "../actions.js";

const BUSY = ["queued", "generating", "optics"];

function updateButton(state) {
  const btn = document.querySelector("[data-testid=generate-button]");
  if (!btn) return;
  const short = (state.form.description || "").trim().length < 3;
  const down = state.comfy.state === "down";
  const busy = !!(state.shot && BUSY.includes(state.shot.status));
  btn.disabled = short || down || state.submitting === true || busy;
}

export function initDescription() {
  const ta = document.querySelector("[data-testid=shot-description]");
  if (ta) {
    ta.addEventListener("input", () => {
      const s = getState();
      setState({ form: { ...s.form, description: ta.value } });
    });
  }
  const btn = document.querySelector("[data-testid=generate-button]");
  if (btn) btn.addEventListener("click", () => submitShot());
  subscribe(updateButton);
  updateButton(getState());
}
