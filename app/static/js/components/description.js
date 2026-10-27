// Scene description field and Generate button enable rules (no submit logic here).
import { getState, setState, subscribe } from "../state.js";
import { submitShot, importClip } from "../actions.js";

const BUSY = ["queued", "generating", "optics"];

function updateButton(state) {
  const btn = document.querySelector("[data-testid=generate-button]");
  if (!btn) return;
  const short = (state.form.description || "").trim().length < 3;
  const down = state.comfy.state === "down";
  const busy = !!(state.shot && BUSY.includes(state.shot.status));
  btn.disabled = short || down || state.submitting === true || busy;
  const own = document.querySelector("[data-testid=import-button]");
  if (own) own.disabled = down || state.submitting === true || busy;
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
  if (ta) {
    ta.addEventListener("keydown", (event) => {
      if (event.ctrlKey && event.key === "Enter" && btn && !btn.disabled) {
        event.preventDefault();
        submitShot();
      }
    });
  }
  const own = document.querySelector("[data-testid=import-button]");
  const input = document.querySelector("[data-testid=import-input]");
  if (own && input) {
    own.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      input.value = "";
      if (file) importClip(file);
    });
  }
  subscribe(updateButton);
  updateButton(getState());
}
