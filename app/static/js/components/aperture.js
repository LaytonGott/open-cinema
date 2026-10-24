// Director aperture slider: writes form.aperture and mirrors it into the slider, its value text and aria-valuetext.
import { APERTURE_STOPS } from "./option-groups.js";
import { getState, setState, subscribe } from "../state.js";

export function initAperture() {
  const slider = document.querySelector('[data-testid="aperture-slider"]');
  const value = document.querySelector('[data-testid="aperture-value"]');
  const iris = document.querySelector('[data-testid="aperture-iris"]');
  const scale = document.querySelector('[data-testid="aperture-scale"]');
  if (!slider) return;

  function render(state) {
    const index = APERTURE_STOPS.indexOf(Number(state.form.aperture));
    if (index < 0) return;
    const text = "f/" + APERTURE_STOPS[index];
    slider.value = String(index);
    slider.setAttribute("aria-valuetext", text);
    if (value) value.textContent = text;
    if (iris) {
      const size = 1 - (index / (APERTURE_STOPS.length - 1)) * 0.85;
      iris.style.setProperty("--iris", String(Math.round(size * 1000) / 1000));
    }
    if (scale) {
      Array.from(scale.children).forEach((span, i) => span.classList.toggle("on", i === index));
    }
  }

  slider.addEventListener("input", () => {
    const aperture = APERTURE_STOPS[Number(slider.value)];
    setState({ form: { ...getState().form, aperture } });
  });
  subscribe(render);
  render(getState());
}
