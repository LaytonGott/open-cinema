// Compare slider: keyboard-operable before/after divider (no dragging or clipping here).
export function makeCompareSlider() {
  const slider = document.createElement("div");
  slider.dataset.testid = "compare-slider";
  slider.setAttribute("role", "slider");
  slider.tabIndex = 0;
  slider.setAttribute("aria-label", "Before and after");
  slider.setAttribute("aria-valuemin", "0");
  slider.setAttribute("aria-valuemax", "100");
  slider.setAttribute("aria-valuenow", "50");

  function setValue(n) {
    const value = Math.min(100, Math.max(0, Math.round(Number(n))));
    slider.setAttribute("aria-valuenow", String(Number.isNaN(value) ? 50 : value));
  }
  slider.setValue = setValue;

  slider.addEventListener("keydown", (event) => {
    const current = Number(slider.getAttribute("aria-valuenow"));
    const step = event.shiftKey ? 10 : 1;
    switch (event.key) {
      case "ArrowRight":
      case "ArrowUp":
        setValue(current + step);
        break;
      case "ArrowLeft":
      case "ArrowDown":
        setValue(current - step);
        break;
      case "Home":
        setValue(0);
        break;
      case "End":
        setValue(100);
        break;
      default:
        return;
    }
    event.preventDefault();
  });
  return slider;
}
