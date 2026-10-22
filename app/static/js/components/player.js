// Player: before and after videos stacked inside the viewport while it shows a result.
import { getState, subscribe, shownVersionOf } from "../state.js";

function q(id) {
  return document.querySelector("[data-testid=" + id + "]");
}

function makeVideo(id) {
  const video = document.createElement("video");
  video.dataset.testid = id;
  video.muted = true;
  video.loop = true;
  video.playsInline = true;
  video.preload = "auto";
  video.setAttribute("muted", "");
  video.setAttribute("loop", "");
  video.setAttribute("playsinline", "");
  video.setAttribute("preload", "auto");
  video.style.objectFit = "contain";
  return video;
}

function setSrc(video, url) {
  if (url && video.getAttribute("src") !== url) video.setAttribute("src", url);
}

function build(viewport) {
  const player = document.createElement("div");
  player.dataset.testid = "player";
  player.append(makeVideo("before-video"), makeVideo("after-video"));
  viewport.prepend(player);
  return player;
}

function render(state) {
  const viewport = q("viewport");
  if (!viewport) return;
  let player = q("player");
  if (viewport.dataset.state !== "result") {
    if (player) player.hidden = true;
    return;
  }
  if (!player) player = build(viewport);
  player.hidden = false;
  const shot = state.shot;
  const version = shownVersionOf(state);
  setSrc(q("before-video"), shot && shot.before_url);
  setSrc(q("after-video"), version && version.url);
}

export function initPlayer() {
  subscribe(render);
  render(getState());
}
