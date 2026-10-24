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

function showError(visible) {
  const alert = q("player-error");
  if (alert) alert.hidden = !visible;
}

function wireVideo(video) {
  video.addEventListener("error", () => showError(true));
  video.addEventListener("loadeddata", () => showError(false));
  for (const name of ["loadeddata", "canplay", "emptied"]) {
    video.addEventListener(name, updateReady);
  }
  for (const name of ["play", "pause"]) {
    video.addEventListener(name, updatePlaying);
  }
}

// A fresh after video that looks like the old one; the caller inserts it.
function cloneAfterVideo(old, url) {
  const video = makeVideo("after-video");
  wireVideo(video);
  video.style.cssText = old.style.cssText;
  video.className = old.className;
  video.style.clipPath = old.style.clipPath;
  video.setAttribute("src", url);
  return video;
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

let unsync = null;
let pending = null;

// Switching the shown version: load a clone beside the old video and swap once it can show a frame.
function setAfterSrc(after, before, url) {
  if (!url || after.getAttribute("src") === url) return;
  if (!after.hasAttribute("src")) {
    setSrc(after, url);
    return;
  }
  if (pending) pending.remove();
  const next = cloneAfterVideo(after, url);
  pending = next;
  next.removeAttribute("data-testid");
  next.addEventListener("loadedmetadata", () => {
    next.currentTime = before.currentTime;
  }, { once: true });
  next.addEventListener("loadeddata", () => {
    if (pending !== next) return;
    pending = null;
    // the master may have been sought or played on while the clone loaded: take its time and state as they are now
    if (Math.abs(next.currentTime - before.currentTime) > 0.05) next.currentTime = before.currentTime;
    const wasPlaying = !before.paused;
    next.dataset.testid = "after-video";
    after.replaceWith(next);
    if (unsync) unsync();
    unsync = syncVideos(before, next);
    if (wasPlaying) {
      const result = next.play();
      if (result && result.catch) result.catch(() => {});
    }
    updateReady();
  }, { once: true });
  after.after(next);
}

let lastShotId = null;

function loadSrc(video, url) {
  video.pause();
  video.removeAttribute("src");
  if (url) video.setAttribute("src", url);
  video.load();
}

// A different shot: drop any pending clone and load both videos directly, without the clone swap.
function resetMedia(before, after, shot, version) {
  if (pending) {
    pending.remove();
    pending = null;
  }
  showError(false);
  loadSrc(before, shot && shot.before_url);
  loadSrc(after, version && version.url);
  if (unsync) unsync();
  unsync = syncVideos(before, after);
  q("scrubber").value = "0";
  q("time-readout").textContent = "0:00 / 0:00";
  updatePlaying();
  updateReady();
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
  player.tabIndex = 0;
  player.setAttribute("aria-label", "Video player");
  player.addEventListener("keydown", (event) => {
    if (event.target !== player) return;
    if (event.key !== " " && event.code !== "Space") return;
    event.preventDefault();
    onToggle();
  });
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
  wireVideo(before);
  wireVideo(after);
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
    const current = q("after-video");
    if (current) current.currentTime = time;
  });
  unsync = syncVideos(before, after);
  const error = document.createElement("div");
  error.dataset.testid = "player-error";
  error.setAttribute("role", "alert");
  error.hidden = true;
  error.textContent = "The video could not be loaded.";
  player.append(before, after, makeCompareSlider(), labelBefore, labelAfter, error);
  viewport.prepend(player);
  const controls = document.createElement("div");
  controls.dataset.testid = "player-controls";
  controls.append(toggle, scrubber, readout);
  viewport.after(controls);
  updateReady();
  return player;
}

// No shot: release the media and remove the player so build() makes a fresh one later.
function teardown() {
  if (unsync) {
    unsync();
    unsync = null;
  }
  if (pending) {
    pending.remove();
    pending = null;
  }
  for (const id of ["before-video", "after-video"]) {
    const video = q(id);
    if (!video) continue;
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
  const player = q("player");
  if (player) player.remove();
  const controls = q("player-controls");
  if (controls) controls.remove();
  lastShotId = null;
}

function render(state) {
  const viewport = q("viewport");
  if (!viewport) return;
  let player = q("player");
  if (!state.shot) {
    teardown();
    return;
  }
  if (viewport.dataset.state !== "result") {
    if (player) player.hidden = true;
    if (q("player-controls")) q("player-controls").hidden = true;
    return;
  }
  if (!player) player = build(viewport);
  player.hidden = false;
  q("player-controls").hidden = false;
  const shot = state.shot;
  const version = shownVersionOf(state);
  const before = q("before-video");
  const shotId = shot ? shot.id : null;
  if (shotId !== lastShotId) {
    lastShotId = shotId;
    resetMedia(before, q("after-video"), shot, version);
  } else {
    setSrc(before, shot && shot.before_url);
    setAfterSrc(q("after-video"), before, version && version.url);
  }
  q("label-after").textContent = version ? "After f/" + version.aperture : "After";
}

export function initPlayer() {
  subscribe(render);
  render(getState());
}
