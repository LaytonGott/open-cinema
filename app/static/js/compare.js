// Compare slider: keyboard- and pointer-operable before/after divider that publishes its position as --split on the player.
export function makeCompareSlider() {
  const slider = document.createElement("div");
  slider.dataset.testid = "compare-slider";
  slider.setAttribute("role", "slider");
  slider.tabIndex = 0;
  slider.setAttribute("aria-label", "Before and after");
  slider.setAttribute("aria-valuemin", "0");
  slider.setAttribute("aria-valuemax", "100");
  slider.setAttribute("aria-valuenow", "50");
  slider.setAttribute("aria-valuetext", "50% after");

  const handle = document.createElement("div");
  handle.dataset.testid = "compare-handle";
  handle.setAttribute("aria-hidden", "true");
  handle.style.left = "50%";
  const knob = document.createElement("span");
  knob.className = "compare-knob";
  const SVG_NS = "http://www.w3.org/2000/svg";
  for (const points of ["14 7 9 12 14 17", "10 7 15 12 10 17"]) {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const arrow = document.createElementNS(SVG_NS, "polyline");
    arrow.setAttribute("points", points);
    svg.append(arrow);
    knob.append(svg);
  }
  handle.append(knob);
  slider.append(handle);

  let current = 50;
  function setValue(n) {
    const value = Math.min(100, Math.max(0, Math.round(Number(n))));
    const shown = Number.isNaN(value) ? 50 : value;
    slider.setAttribute("aria-valuenow", String(shown));
    slider.setAttribute("aria-valuetext", shown + "% after");
    handle.style.left = shown + "%";
    current = shown;
    slider.syncSplit();
  }
  slider.setValue = setValue;
  slider.syncSplit = () => {
    if (!slider.parentElement) return;
    slider.parentElement.style.setProperty("--split", current + "%");
  };

  let dragging = false;
  function setFromPointer(event) {
    const rect = slider.getBoundingClientRect();
    if (rect.width > 0) setValue((event.clientX - rect.left) / rect.width * 100);
  }
  function endDrag(event) {
    if (!dragging) return;
    dragging = false;
    if (slider.hasPointerCapture && slider.hasPointerCapture(event.pointerId)) {
      slider.releasePointerCapture(event.pointerId);
    }
  }
  slider.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    slider.focus();
    setFromPointer(event);
    slider.setPointerCapture(event.pointerId);
    dragging = true;
  });
  slider.addEventListener("pointermove", (event) => {
    if (dragging) setFromPointer(event);
  });
  slider.addEventListener("pointerup", endDrag);
  slider.addEventListener("pointercancel", endDrag);
  slider.addEventListener("lostpointercapture", endDrag);

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
