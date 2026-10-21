// Option radio groups: camera move, lens and framing, rendered from state.options.
import { getOptions } from "../api.js";
import { getState, setState, subscribe } from "../state.js";

const GROUPS = [
  { testid: "camera-group", key: "camera", list: "cameras", number: false },
  { testid: "lens-group", key: "lens_mm", list: "lenses", number: true },
  { testid: "framing-group", key: "framing", list: "framings", number: false },
];

function render(state) {
  if (!state.options) return;
  for (const g of GROUPS) {
    const el = document.querySelector(`[data-testid=${g.testid}]`);
    if (!el) continue;
    el.replaceChildren();
    for (const opt of state.options[g.list] || []) {
      const value = g.number ? opt : opt.id;
      const checked = String(state.form[g.key]) === String(value);
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.dataset.value = String(value);
      b.setAttribute("aria-checked", checked ? "true" : "false");
      b.tabIndex = checked ? 0 : -1;
      b.textContent = g.number ? value + " mm" : opt.label;
      const select = (v) => {
        const s = getState();
        setState({ form: { ...s.form, [g.key]: v } });
      };
      b.addEventListener("click", () => select(value));
      b.addEventListener("keydown", (ev) => {
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
        if (!step) return;
        ev.preventDefault();
        const opts = state.options[g.list] || [];
        const i = opts.indexOf(opt);
        const nextOpt = opts[(i + step + opts.length) % opts.length];
        select(g.number ? nextOpt : nextOpt.id);
        const checkedNow = el.querySelector("[role=radio][aria-checked=true]");
        if (checkedNow) checkedNow.focus();
      });
      el.appendChild(b);
    }
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
