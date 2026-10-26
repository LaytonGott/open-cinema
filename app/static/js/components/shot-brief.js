// Shot brief: the full description and the settings of the shown shot, under the viewport.
import { getState, subscribe } from "../state.js";

let lastKey = null;

function labelOf(list, id) {
  const found = (list || []).find((item) => item && item.id === id);
  return found && found.label ? found.label : String(id);
}

function render(state) {
  const box = document.querySelector("[data-testid=shot-brief]");
  if (!box) return;
  const shot = state.shot;
  if (!shot || !shot.params) {
    box.hidden = true;
    lastKey = null;
    return;
  }
  const p = shot.params;
  const options = state.options || {};
  const settings = [p.lens_mm + " mm", "f/" + p.aperture, labelOf(options.framings, p.framing), labelOf(options.cameras, p.camera)].join(" - ");
  const key = shot.id + "|" + p.description + "|" + settings;
  box.hidden = false;
  if (key === lastKey) return;
  lastKey = key;
  box.querySelector(".brief-text").textContent = p.description;
  box.querySelector(".brief-settings").textContent = settings;
}

export function initShotBrief() {
  subscribe(render);
  render(getState());
}
