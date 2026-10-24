// Subject distance readout: asks the server for the estimate whenever lens or framing changes.
import { getEstimate } from "../api.js";
import { getState, subscribe } from "../state.js";

export function initDistance() {
  const el = document.querySelector('[data-testid="subject-distance"]');
  if (!el) return;
  const marker = document.querySelector('[data-testid="focus-marker"]');
  let counter = 0;
  let lastKey = null;

  function format(metres) {
    return "Subject about " + (metres >= 10 ? metres.toFixed(0) : metres.toFixed(1)) + " m";
  }

  async function update(state) {
    if (!state.options) return;
    const { lens_mm, framing } = state.form;
    const key = lens_mm + "|" + framing;
    if (key === lastKey) return;
    lastKey = key;
    const mine = ++counter;
    try {
      const body = await getEstimate(lens_mm, framing);
      if (mine !== counter) return;
      const metres = Number(body.subject_distance_m);
      if (!Number.isFinite(metres)) return;
      el.textContent = format(metres);
      el.setAttribute("data-metres", String(metres));
      if (marker) {
        const clamped = Math.min(20, Math.max(1, metres));
        marker.style.left = (100 * Math.log(clamped) / Math.log(20)) + "%";
      }
    } catch (e) {
      // ignored on purpose; the previous reading stays
    }
  }

  subscribe(update);
  update(getState());
}
