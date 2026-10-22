// Optics controls: a re-apply aperture slider shown while the viewport shows a result.
import { getState, subscribe, shownVersionOf } from "../state.js";
import { APERTURE_STOPS } from "./option-groups.js";

let slider = null;
let value = null;
let button = null;
let current = null;
let lastKey = null;

function showValue() {
  const text = "f/" + APERTURE_STOPS[Number(slider.value)];
  value.textContent = text;
  slider.setAttribute("aria-valuetext", text);
}

function updateButton() {
  const version = current ? shownVersionOf(current) : null;
  const same = !!version && APERTURE_STOPS[Number(slider.value)] === Number(version.aperture);
  button.disabled = same || !current.shot || current.shot.status === "optics";
}

function onInput() {
  showValue();
  updateButton();
}

function render(state) {
  const box = document.querySelector("[data-testid=optics-controls]");
  const viewport = document.querySelector("[data-testid=viewport]");
  if (!box) return;
  const visible = !!viewport && viewport.dataset.state === "result";
  box.hidden = !visible;
  if (!visible) return;
  if (!slider) {
    slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = "7";
    slider.step = "1";
    slider.setAttribute("data-testid", "reapply-slider");
    slider.setAttribute("aria-label", "Aperture");
    value = document.createElement("output");
    value.setAttribute("data-testid", "reapply-value");
    slider.addEventListener("input", onInput);
    button = document.createElement("button");
    button.type = "button";
    button.setAttribute("data-testid", "reapply-button");
    button.textContent = "Apply aperture";
    box.append(slider, value, button);
  }
  current = state;
  const version = shownVersionOf(state);
  const key = (state.shot ? state.shot.id : "") + ":" + (version ? version.n : "");
  if (key === lastKey) {
    updateButton();
    return;
  }
  lastKey = key;
  const i = version ? APERTURE_STOPS.indexOf(Number(version.aperture)) : -1;
  slider.value = String(i < 0 ? 2 : i);
  showValue();
  updateButton();
}

export function initOpticsControls() {
  subscribe(render);
  render(getState());
}
