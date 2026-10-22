// Player: before and after videos stacked inside the viewport while it shows a result.
import { getState, subscribe, shownVersionOf } from "../state.js";
import { syncVideos } from "../sync.js";
import { makeCompareSlider } from "../compare.js";

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

function fmt(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  return Math.floor(whole / 60) + ":" + String(whole % 60).padStart(2, "0");
}

function setSrc(video, url) {
  if (url && video.getAttribute("src") !== url) {
    video.setAttribute("src", url);
    updateReady();
  }
}

// Switching the shown version: keep the playback position and play state.
function setAfterSrc(after, before, url) {
  if (!url || after.getAttribute("src") === url) return;
  const hadSrc = after.hasAttribute("src");
  const time = before.currentTime;
  const wasPlaying = !before.paused;
  setSrc(after, url);
  if (!hadSrc) return;
  after.addEventListener("loadedmetadata", () => {
    after.currentTime = time;
    if (wasPlaying) {
      const result = after.play();
      if (result && result.catch) result.catch(() => {});
    }
  }, { once: true });
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
  const labelBefore = document.createElement("div");
  labelBefore.dataset.testid = "label-before";
  labelBefore.textContent = "Before";
  const labelAfter = document.createElement("div");
  labelAfter.dataset.testid = "label-after";
  const scrubber = document.createElement("input");
  scrubber.type = "range";
  scrubber.dataset.testid = "scrubber";
  scrubber.min = "0";
  scrubber.max = "1000";
  scrubber.step = "1";
  scrubber.value = "0";
  scrubber.setAttribute("aria-label", "Seek");
  const readout = document.createElement("span");
  readout.dataset.testid = "time-readout";
  readout.setAttribute("aria-live", "off");
  readout.textContent = "0:00 / 0:00";
  let dragging = false;
  scrubber.addEventListener("pointerdown", () => { dragging = true; });
  scrubber.addEventListener("pointerup", () => { dragging = false; });
  scrubber.addEventListener("change", () => { dragging = false; });
  const follow = () => {
    const duration = before.duration;
    if (dragging || !Number.isFinite(duration) || duration <= 0) return;
    scrubber.value = String(Math.round(before.currentTime / duration * 1000));
  };
  for (const name of ["timeupdate", "seeked", "loadedmetadata"]) {
    before.addEventListener(name, follow);
  }
  const updateReadout = () => {
    readout.textContent = fmt(before.currentTime) + " / " + fmt(before.duration);
  };
  for (const name of ["timeupdate", "seeked", "loadedmetadata", "durationchange", "emptied"]) {
    before.addEventListener(name, updateReadout);
  }
  scrubber.addEventListener("input", () => {
    const duration = before.duration;
    if (!Number.isFinite(duration) || duration <= 0) return;
    const time = Number(scrubber.value) / 1000 * duration;
    before.currentTime = time;
    after.currentTime = time;
  });
  syncVideos(before, after);
  player.append(before, after, makeCompareSlider(), labelBefore, labelAfter, toggle, scrubber, readout);
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
  setAfterSrc(q("after-video"), q("before-video"), version && version.url);
  q("label-after").textContent = version ? "After f/" + version.aperture : "After";
}

export function initPlayer() {
  subscribe(render);
  render(getState());
}
