// Optics controls: a re-apply aperture slider shown while the viewport shows a result.
import { getState, subscribe, shownVersionOf, setShownVersion } from "../state.js";
import { APERTURE_STOPS } from "./option-groups.js";
import { reapplyShown } from "../actions.js";

let slider = null;
let value = null;
let button = null;
let status = null;
let current = null;
let lastKey = null;
let pendingAperture = null;
let list = null;
let listKey = null;

// The aperture asked for in a re-apply is not part of the public record, so the page keeps it itself: in memory, and in
// sessionStorage so a reload while the re-apply runs still shows the target.
function rememberRequested(shotId, aperture) {
  pendingAperture = aperture;
  try { sessionStorage.setItem("requestedAperture:" + shotId, String(aperture)); } catch (err) { /* storage may be blocked */ }
}

function requestedFor(shotId) {
  if (pendingAperture !== null) return pendingAperture;
  try {
    const stored = sessionStorage.getItem("requestedAperture:" + shotId);
    return stored === null ? null : Number(stored);
  } catch (err) {
    return null;
  }
}

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

function showStatus(state, version) {
  const shot = state.shot;
  let text = "";
  if (shot && shot.status === "optics") {
    const requested = requestedFor(shot.id);
    const target = requested !== null ? requested : APERTURE_STOPS[Number(slider.value)];
    text = "Applying f/" + target + " ...";
  } else if (shot && shot.status === "done" && shot.reapply_error) {
    const err = shot.reapply_error;
    text = typeof err === "object" ? String(err.message) : String(err);
  } else if (version) {
    text = "Applied f/" + version.aperture;
  }
  status.textContent = text;
}

function renderChips(state, version) {
  const versions = (state.shot && state.shot.versions) || [];
  const shown = version ? version.n : null;
  const key = versions.map((v) => v.n + "@" + v.aperture).join(",") + "|" + shown;
  if (key === listKey) return;
  listKey = key;
  list.replaceChildren(
    ...versions.map((v) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.setAttribute("data-testid", "version-chip");
      chip.setAttribute("data-version", String(v.n));
      chip.setAttribute("data-aperture", String(v.aperture));
      chip.setAttribute("aria-label", "Version " + v.n + ", f/" + v.aperture);
      chip.setAttribute("aria-pressed", v.n === shown ? "true" : "false");
      chip.textContent = "f/" + v.aperture;
      chip.addEventListener("click", () => setShownVersion(v.n));
      return chip;
    }),
  );
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
    button.setAttribute("aria-label", "Apply aperture");
    button.textContent = "Apply aperture";
    button.addEventListener("click", () => {
      const aperture = APERTURE_STOPS[Number(slider.value)];
      rememberRequested(current.shot.id, aperture);
      reapplyShown(aperture);
    });
    status = document.createElement("span");
    status.setAttribute("data-testid", "reapply-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    list = document.createElement("div");
    list.setAttribute("data-testid", "version-list");
    box.append(slider, value, button, status, list);
  }
  current = state;
  const version = shownVersionOf(state);
  renderChips(state, version);
  showStatus(state, version);
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
