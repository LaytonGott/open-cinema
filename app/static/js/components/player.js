// Player: before and after videos stacked inside the viewport while it shows a result.
import { getState, subscribe, shownVersionOf } from "../state.js";
import { syncVideos } from "../sync.js";

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

function updateReady() {
  const toggle = q("play-toggle");
  const before = q("before-video");
  const after = q("after-video");
  if (!toggle || !before || !after) return;
  toggle.disabled = !(before.readyState >= 2 && after.readyState >= 2);
}

function updatePlaying() {
  const toggle = q("play-toggle");
  const before = q("before-video");
  if (!toggle || !before) return;
  const playing = !before.paused;
  toggle.setAttribute("aria-pressed", playing ? "true" : "false");
  toggle.setAttribute("aria-label", playing ? "Pause" : "Play");
  toggle.textContent = playing ? "⏸ Pause" : "▶ Play";
}

function setSrc(video, url) {
  if (url && video.getAttribute("src") !== url) {
    video.setAttribute("src", url);
    updateReady();
  }
}

function onToggle() {
  const toggle = q("play-toggle");
  if (!toggle || toggle.disabled) return;
  const videos = [q("before-video"), q("after-video")];
  const start = videos[0].paused;
  for (const video of videos) {
    if (start) {
      const result = video.play();
      if (result && result.catch) result.catch(() => {});
    } else {
      video.pause();
    }
  }
}

function build(viewport) {
  const player = document.createElement("div");
  player.dataset.testid = "player";
  const before = makeVideo("before-video");
  const after = makeVideo("after-video");
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.dataset.testid = "play-toggle";
  toggle.setAttribute("aria-pressed", "false");
  toggle.setAttribute("aria-label", "Play");
  toggle.textContent = "▶ Play";
  toggle.disabled = true;
  toggle.addEventListener("click", onToggle);
  for (const video of [before, after]) {
    for (const name of ["loadeddata", "canplay", "emptied"]) {
      video.addEventListener(name, updateReady);
    }
    for (const name of ["play", "pause"]) {
      video.addEventListener(name, updatePlaying);
    }
  }
  syncVideos(before, after);
  player.append(before, after, toggle);
  viewport.prepend(player);
  updateReady();
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
