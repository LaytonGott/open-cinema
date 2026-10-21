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
}

export function initHeader() {
  subscribe(render);
  render(getState());
}

export async function checkHealth() {
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
  }
}
