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
    if (text) text.textContent = s === "down" ? state.comfy.message || "ComfyUI is not reachable." : "";
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
let failures = 0;
let softFailed = false;

function fail(message) {
  failures += 1;
  const shot = getState().shot;
  const running = shot && ["queued", "generating", "optics"].includes(shot.status);
  if (running && failures === 1) {
    softFailed = true;
    return;
  }
  setState({ comfy: { state: "down", device: null, message } });
}

export async function checkHealth() {
  if (inFlight) return;
  inFlight = true;
  softFailed = false;
  clearTimeout(timer);
  try {
    const h = await getHealth();
    const c = h.comfyui;
    if (c && c.reachable) {
      failures = 0;
      setState({ comfy: { state: "ok", device: c.device || null, message: null } });
    } else {
      fail((c && c.message) || null);
    }
  } catch (e) {
    fail(e && e.message ? e.message : null);
  } finally {
    inFlight = false;
    timer = setTimeout(checkHealth, softFailed || getState().comfy.state === "down" ? 5000 : 30000);
  }
}
