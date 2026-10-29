// Option radio groups: camera move, lens and framing, rendered from state.options.
import { getOptions } from "../api.js";
import { getState, setState, subscribe } from "../state.js";
import { CAMERA_ICONS, FRAMING_ICONS } from "./icons.js";

// Aperture stops (f-numbers) offered for a re-apply, in slider order.
export const APERTURE_STOPS = [1.4, 2, 2.8, 4, 5.6, 8, 11, 16];

const GROUPS = [
  { testid: "camera-group", key: "camera", list: "cameras", number: false, icons: CAMERA_ICONS },
  { testid: "lens-group", key: "lens_mm", list: "lenses", number: true },
  { testid: "framing-group", key: "framing", list: "framings", number: false, icons: FRAMING_ICONS },
];

// Last rendered lens figure text, and per group the element, options list and checked value.
let lastLens = null;
const cache = new Map();

function buildButton(g, opt, el) {
  const value = g.number ? opt : opt.id;
  const b = document.createElement("button");
  b.type = "button";
  b.setAttribute("role", "radio");
  b.dataset.value = String(value);
  b.className = "opt";
  if (g.icons) {
    const icon = document.createElement("span");
    icon.className = "opt-icon";
    icon.innerHTML = g.icons[opt.id] || "";
    b.appendChild(icon);
  }
  const label = document.createElement("span");
  label.className = "opt-label";
  label.textContent = g.number ? value + " mm" : opt.label;
  b.appendChild(label);
  if (!g.number && opt.lora) {
    // a real camera move (LTX-2 camera LoRA), said in text, not by colour alone
    const tag = document.createElement("span");
    tag.className = "opt-tag";
    tag.textContent = "LoRA";
    b.appendChild(tag);
  }
  const select = (v) => {
    const s = getState();
    setState({ form: { ...s.form, [g.key]: v } });
  };
  b.addEventListener("click", () => select(value));
  b.addEventListener("keydown", (ev) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
    if (!step) return;
    ev.preventDefault();
    const opts = (getState().options || {})[g.list] || [];
    const i = opts.findIndex((o) => String(g.number ? o : o.id) === String(value));
    if (i < 0) return;
    const nextOpt = opts[(i + step + opts.length) % opts.length];
    select(g.number ? nextOpt : nextOpt.id);
    const checkedNow = el.querySelector("[role=radio][aria-checked=true]");
    if (checkedNow) checkedNow.focus();
  });
  return b;
}

function render(state) {
  if (!state.options) return;
  const lensText = String(state.form.lens_mm);
  if (lensText !== lastLens) {
    const lensNum = document.querySelector("[data-testid=lens-figure] .lens-figure-num");
    if (lensNum) {
      lensNum.textContent = lensText;
      lastLens = lensText;
    }
  }
  for (const g of GROUPS) {
    const el = document.querySelector(`[data-testid=${g.testid}]`);
    if (!el) continue;
    const opts = state.options[g.list] || [];
    const listSig = JSON.stringify(opts);
    const formValue = String(state.form[g.key]);
    const prev = cache.get(g.testid);
    if (prev && prev.el === el && prev.listSig === listSig && prev.formValue === formValue && prev.lens === lensText) continue;
    if (!prev || prev.el !== el || prev.listSig !== listSig) {
      el.replaceChildren();
      for (const opt of opts) el.appendChild(buildButton(g, opt, el));
    }
    for (const b of el.children) {
      const checked = b.dataset.value === formValue;
      b.setAttribute("aria-checked", checked ? "true" : "false");
      b.tabIndex = checked ? 0 : -1;
    }
    cache.set(g.testid, { el, listSig, formValue, lens: lensText });
  }
}

export async function initOptionGroups() {
  subscribe(render);
  try {
    const options = await getOptions();
    const d = options.defaults || {};
    const form = { ...getState().form };
    for (const k of ["camera", "lens_mm", "aperture", "framing"]) {
      if (d[k] !== undefined) form[k] = d[k];
    }
    setState({ options, form });
  } catch (e) {
    setState({ error: e && e.message ? e.message : String(e) });
  }
}
