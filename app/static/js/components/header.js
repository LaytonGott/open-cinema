// Header ComfyUI status: renders state.comfy into [data-testid=comfy-status].
import { getHealth } from "../api.js";
import { getState, setState, subscribe } from "../state.js";

function render(state) {
  const el = document.querySelector("[data-testid=comfy-status]");
  if (!el) return;
  const { state: s, device } = state.comfy;
  el.dataset.state = s;
  if (s === "ok") el.textContent = "ComfyUI: connected" + (device ? " " + device : "");
  else if (s === "down") el.textContent = "ComfyUI: offline";
  else el.textContent = "ComfyUI: checking";
  const banner = document.querySelector("[data-testid=comfy-banner]");
  if (banner) {
    banner.hidden = s !== "down";
    const text = document.querySelector("[data-testid=comfy-banner-text]");
    if (text) text.textContent = s === "down" ? state.comfy.message || "" : "";
  }
}

export function initHeader() {
  const retry = document.querySelector("[data-testid=comfy-retry]");
  if (retry) retry.addEventListener("click", () => checkHealth());
  window.addEventListener("focus", () => checkHealth());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") checkHealth();
  });
  subscribe(render);
  render(getState());
}

let timer = null;
let inFlight = false;

export async function checkHealth() {
  if (inFlight) return;
  inFlight = true;
  clearTimeout(timer);
  try {
    const h = await getHealth();
    const c = h.comfyui;
    if (c && c.reachable) {
      setState({ comfy: { state: "ok", device: c.device || null, message: null } });
    } else {
      setState({ comfy: { state: "down", device: null, message: (c && c.message) || null } });
    }
  } catch (e) {
    setState({ comfy: { state: "down", device: null, message: e && e.message ? e.message : null } });
  } finally {
    inFlight = false;
    timer = setTimeout(checkHealth, getState().comfy.state === "down" ? 5000 : 30000);
  }
}
