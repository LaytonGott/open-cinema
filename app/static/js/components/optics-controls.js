// Optics controls: re-apply aperture, focus point / rack focus and lens look, shown while the viewport shows a result.
import { getState, subscribe, shownVersionOf, setShownVersion } from "../state.js";
import { APERTURE_STOPS } from "./option-groups.js";
import { reapplyShown } from "../actions.js";

let slider = null;
let value = null;
let button = null;
let status = null;
let current = null;
let lastKey = null;
// The aperture asked for in a re-apply is not part of the public record, so the page keeps it itself, per shot id.
const pendingByShot = {};
const seenRunning = new Set();
let list = null;
let listKey = null;
let blur = null;
let focusGroup = null;
let lookSelect = null;

export const LOOKS = [
  { id: "clean", label: "Clean" },
  { id: "vintage", label: "Vintage" },
  { id: "anamorphic", label: "Anamorphic" },
];
const FOCUS_MODES = [
  { id: "auto", label: "Auto" },
  { id: "point", label: "Pick point" },
  { id: "rack", label: "Rack focus" },
];

// The pending focus choice of the shown version: mode, the points (frame fractions) and whether the layer is armed.
const focus = { mode: "auto", a: null, b: null, armed: false, step: "a" };

function modeOf(version) {
  if (version && version.rack) return "rack";
  if (version && version.focus) return "point";
  return "auto";
}

function lookOf(version) {
  return (version && version.look) || "clean";
}

function samePoint(p, q) {
  if (!p || !q) return !p && !q;
  return Number(p.x) === Number(q.x) && Number(p.y) === Number(q.y);
}

function pendingFocus() {
  return {
    focus: focus.mode === "auto" ? null : focus.a,
    rack: focus.mode === "rack" ? focus.b : null,
  };
}

function focusComplete() {
  if (focus.mode === "auto") return true;
  if (focus.mode === "point") return !!focus.a;
  return !!focus.a && !!focus.b;
}

function focusDiffers(version) {
  const p = pendingFocus();
  const vf = version ? version.focus || null : null;
  const vr = version ? version.rack || null : null;
  return !samePoint(p.focus, vf) || !samePoint(p.rack, vr);
}

function fLabel(n) {
  return "f/" + n;
}

// How much the background blurs at an f-number, in words: a wide aperture (small f-number) blurs the most.
function blurWord(fNumber) {
  if (fNumber <= 2) return "Background blur: strong";
  if (fNumber <= 4) return "Background blur: medium";
  if (fNumber <= 8) return "Background blur: slight";
  return "Background blur: almost none";
}

function showValue() {
  const text = fLabel(APERTURE_STOPS[Number(slider.value)]);
  value.textContent = text;
  slider.setAttribute("aria-valuetext", text);
  blur.textContent = blurWord(APERTURE_STOPS[Number(slider.value)]);
}

function updateButton() {
  const version = current ? shownVersionOf(current) : null;
  const apertureDiff = !version || APERTURE_STOPS[Number(slider.value)] !== Number(version.aperture);
  const fDiff = focusDiffers(version);
  const lDiff = !!lookSelect && lookSelect.value !== lookOf(version);
  const running = !current || !current.shot || current.shot.status === "optics";
  let text = "Apply aperture";
  if (fDiff) text = "Apply focus";
  else if (lDiff) text = "Apply look";
  button.textContent = text;
  button.setAttribute("aria-label", text);
  button.disabled = running || !focusComplete() || !(apertureDiff || fDiff || lDiff);
}

function showStatus(state, version) {
  const shot = state.shot;
  let text = "";
  // A shot record fetched before the re-apply started can still read "done" when its shot is shown again, so the
  // entry goes only once the shot has been seen running.
  if (shot && shot.status === "optics") seenRunning.add(shot.id);
  else if (shot && seenRunning.delete(shot.id)) delete pendingByShot[shot.id];
  if (shot && shot.status === "optics") {
    const target = shot.id in pendingByShot ? pendingByShot[shot.id] : APERTURE_STOPS[Number(slider.value)];
    text = "Applying f/" + target + " ...";
  } else if (focus.mode === "rack" && focus.a && !focus.b) {
    text = "Click a second point to rack focus to.";
  } else if (shot && shot.status === "done" && shot.reapply_error) {
    const err = shot.reapply_error;
    text = typeof err === "object" ? String(err.message) : String(err);
  } else if (version) {
    text = "Applied f/" + version.aperture;
  }
  status.textContent = text;
}

export function chipText(v) {
  let text = fLabel(v.aperture);
  const look = lookOf(v);
  if (look !== "clean") text += " · " + LOOKS.find((l) => l.id === look).label;
  if (v.rack) text += " · rack";
  else if (v.focus) text += " · focus";
  return text;
}

function renderChips(state, version) {
  const versions = (state.shot && state.shot.versions) || [];
  const shown = version ? version.n : null;
  const key = versions.map((v) => [v.n, v.aperture, modeOf(v), lookOf(v)].join("@")).join(",") + "|" + shown;
  if (key === listKey) return;
  listKey = key;
  list.replaceChildren(
    ...versions.map((v) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.setAttribute("data-testid", "version-chip");
      chip.setAttribute("data-version", String(v.n));
      chip.setAttribute("data-aperture", String(v.aperture));
      chip.setAttribute("data-focus", modeOf(v));
      chip.setAttribute("data-look", lookOf(v));
      chip.setAttribute("aria-label", "Version " + v.n + ", " + chipText(v));
      chip.setAttribute("aria-pressed", v.n === shown ? "true" : "false");
      chip.textContent = chipText(v);
      chip.addEventListener("click", () => setShownVersion(v.n));
      return chip;
    }),
  );
}

// ---- focus layer (built by the player) and the focus-mode group

function layerEl() {
  return document.querySelector("[data-testid=focus-layer]");
}

function setPointFromLayer(fx, fy) {
  const clamp = (v) => Math.round(Math.min(1, Math.max(0, v)) * 1000) / 1000;
  const point = { x: clamp(fx), y: clamp(fy) };
  if (focus.mode === "point") {
    focus.a = point;
    focus.armed = false;
  } else if (focus.mode === "rack") {
    if (focus.step === "a") {
      focus.a = point;
      focus.b = null;
      focus.step = "b";
    } else {
      focus.b = point;
      focus.armed = false;
    }
  }
  refreshFocus();
}

function wireLayer(layer) {
  if (layer.dataset.wired === "1") return;
  layer.dataset.wired = "1";
  layer.addEventListener("click", (event) => {
    if (!focus.armed) return;
    const box = layer.getBoundingClientRect();
    setPointFromLayer((event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height);
  });
  layer.addEventListener("keydown", (event) => {
    if (!focus.armed) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    setPointFromLayer(0.5, 0.5);
  });
}

function renderLayer() {
  const layer = layerEl();
  if (!layer) return;
  wireLayer(layer);
  layer.classList.toggle("armed", focus.armed);
  layer.tabIndex = focus.armed ? 0 : -1;
  layer.setAttribute("aria-label", focus.armed && focus.mode === "rack" && focus.step === "b"
    ? "Choose the point to rack focus to" : "Choose the focus point");
  const points = [["a", focus.mode === "auto" ? null : focus.a], ["b", focus.mode === "rack" ? focus.b : null]];
  for (const [id, point] of points) {
    let marker = layer.querySelector(`[data-testid=focus-marker][data-point=${id}]`);
    if (!marker) {
      marker = document.createElement("span");
      marker.dataset.testid = "focus-marker";
      marker.dataset.point = id;
      marker.setAttribute("aria-hidden", "true");
      marker.textContent = id === "a" ? "A" : "B";
      layer.append(marker);
    }
    marker.hidden = !point;
    if (point) {
      marker.style.left = point.x * 100 + "%";
      marker.style.top = point.y * 100 + "%";
    }
  }
  let line = layer.querySelector(".focus-line");
  if (!line) {
    line = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    line.setAttribute("class", "focus-line");
    line.setAttribute("aria-hidden", "true");
    line.setAttribute("viewBox", "0 0 100 100");
    line.setAttribute("preserveAspectRatio", "none");
    line.innerHTML = '<line x1="0" y1="0" x2="0" y2="0" vector-effect="non-scaling-stroke"></line>';
    layer.prepend(line);
  }
  const both = focus.mode === "rack" && focus.a && focus.b;
  line.style.display = both ? "" : "none";
  if (both) {
    const l = line.querySelector("line");
    l.setAttribute("x1", focus.a.x * 100);
    l.setAttribute("y1", focus.a.y * 100);
    l.setAttribute("x2", focus.b.x * 100);
    l.setAttribute("y2", focus.b.y * 100);
  }
}

function renderFocusGroup() {
  for (const radio of focusGroup.querySelectorAll("[role=radio]")) {
    const on = radio.dataset.value === focus.mode;
    radio.setAttribute("aria-checked", on ? "true" : "false");
    radio.tabIndex = on ? 0 : -1;
  }
}

function refreshFocus() {
  renderFocusGroup();
  renderLayer();
  if (current) showStatus(current, shownVersionOf(current));
  updateButton();
}

function chooseMode(mode) {
  focus.mode = mode;
  focus.armed = mode !== "auto";
  focus.step = "a";
  focus.a = null;
  focus.b = null;
  refreshFocus();
}

function buildFocusGroup() {
  const group = document.createElement("div");
  group.setAttribute("data-testid", "focus-mode");
  group.setAttribute("role", "radiogroup");
  group.setAttribute("aria-label", "Focus");
  for (const m of FOCUS_MODES) {
    const radio = document.createElement("button");
    radio.type = "button";
    radio.setAttribute("role", "radio");
    radio.dataset.value = m.id;
    radio.textContent = m.label;
    radio.addEventListener("click", () => chooseMode(m.id));
    group.append(radio);
  }
  group.addEventListener("keydown", (event) => {
    const keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!(event.key in keys)) return;
    event.preventDefault();
    const ids = FOCUS_MODES.map((m) => m.id);
    const next = ids[(ids.indexOf(focus.mode) + keys[event.key] + ids.length) % ids.length];
    chooseMode(next);
    group.querySelector(`[data-value=${next}]`).focus();
  });
  return group;
}

function buildLookSelect() {
  const select = document.createElement("select");
  select.setAttribute("data-testid", "reapply-look");
  select.setAttribute("aria-label", "Look");
  for (const l of LOOKS) {
    const option = document.createElement("option");
    option.value = l.id;
    option.textContent = l.label;
    select.append(option);
  }
  select.addEventListener("change", updateButton);
  return select;
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
  if (!visible) {
    focus.armed = false;
    renderLayer();
    return;
  }
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
    blur = document.createElement("span");
    blur.setAttribute("data-testid", "reapply-blur");
    slider.addEventListener("input", onInput);
    focusGroup = buildFocusGroup();
    lookSelect = buildLookSelect();
    button = document.createElement("button");
    button.type = "button";
    button.setAttribute("data-testid", "reapply-button");
    button.setAttribute("aria-label", "Apply aperture");
    button.textContent = "Apply aperture";
    button.addEventListener("click", () => {
      const aperture = APERTURE_STOPS[Number(slider.value)];
      pendingByShot[current.shot.id] = aperture;
      reapplyShown(aperture, { ...pendingFocus(), look: lookSelect.value });
    });
    status = document.createElement("span");
    status.setAttribute("data-testid", "reapply-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    list = document.createElement("div");
    list.setAttribute("data-testid", "version-list");
    box.append(slider, value, blur, focusGroup, lookSelect, button, status, list);
  }
  current = state;
  const version = shownVersionOf(state);
  renderChips(state, version);
  const key = (state.shot ? state.shot.id : "") + ":" + (version ? version.n : "");
  if (key !== lastKey) {
    lastKey = key;
    const i = version ? APERTURE_STOPS.indexOf(Number(version.aperture)) : -1;
    slider.value = String(i < 0 ? 2 : i);
    focus.mode = modeOf(version);
    focus.a = version ? version.focus || null : null;
    focus.b = version ? version.rack || null : null;
    focus.armed = false;
    focus.step = "a";
    lookSelect.value = lookOf(version);
    showValue();
  }
  renderFocusGroup();
  renderLayer();
  showStatus(state, version);
  updateButton();
}

export function initOpticsControls() {
  subscribe(render);
  render(getState());
}
