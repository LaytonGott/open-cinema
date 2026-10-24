// Director aperture slider: writes form.aperture and mirrors it into the slider, its value text and aria-valuetext.
import { APERTURE_STOPS } from "./option-groups.js";
import { getState, setState, subscribe } from "../state.js";

export function initAperture() {
  const slider = document.querySelector('[data-testid="aperture-slider"]');
  const value = document.querySelector('[data-testid="aperture-value"]');
  if (!slider) return;

  function render(state) {
    const index = APERTURE_STOPS.indexOf(Number(state.form.aperture));
    if (index < 0) return;
    const text = "f/" + APERTURE_STOPS[index];
    slider.value = String(index);
    slider.setAttribute("aria-valuetext", text);
    if (value) value.textContent = text;
  }

  slider.addEventListener("input", () => {
    const aperture = APERTURE_STOPS[Number(slider.value)];
    setState({ form: { ...getState().form, aperture } });
  });
  subscribe(render);
  render(getState());
}
