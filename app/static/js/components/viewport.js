// Viewport: sets data-state on [data-testid=viewport] from the shared state.
import { getState, subscribe } from "../state.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

function stateOf(state) {
  const shot = state.shot;
  if (!shot) return state.submitting ? "working" : "empty";
  switch (shot.status) {
    case "done":
      return "result";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
    default:
      return "working";
  }
}

function render(state) {
  const viewport = q("viewport");
  if (!viewport) return;
  const value = stateOf(state);
  viewport.dataset.state = value;
  const hint = q("viewport-hint");
  if (hint) hint.hidden = value !== "empty";
  renderVideo(viewport, value, state.shot);
}

function currentUrl(shot) {
  const versions = (shot && shot.versions) || [];
  const found = versions.find((v) => v.n === shot.current_version);
  return found ? found.url : "";
}

function renderVideo(viewport, value, shot) {
  let video = q("result-video");
  const url = value === "result" ? currentUrl(shot) : "";
  if (!url) {
    if (video) video.hidden = true;
    return;
  }
  if (!video) {
    video = document.createElement("video");
    video.dataset.testid = "result-video";
    video.muted = true;
    video.loop = true;
    video.autoplay = true;
    video.playsInline = true;
    video.setAttribute("muted", "");
    video.setAttribute("loop", "");
    video.setAttribute("playsinline", "");
    video.setAttribute("autoplay", "");
    viewport.prepend(video);
  }
  video.hidden = false;
  if (video.getAttribute("src") !== url) video.setAttribute("src", url);
}

export function initViewport() {
  subscribe(render);
  render(getState());
}
