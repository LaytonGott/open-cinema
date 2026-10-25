// Keeps a follower video in step with a master video; returns a cleanup function.
const HARD_SEEK = 0.5;
const NUDGE = 0.15;

export function syncVideos(master, follower) {
  const cleanups = [];
  function on(target, name, handler) {
    target.addEventListener(name, handler);
    cleanups.push(() => target.removeEventListener(name, handler));
  }

  function mirrorPlayState() {
    if (master.paused) {
      if (!follower.paused) follower.pause();
    } else if (follower.paused) {
      const result = follower.play();
      if (result && result.catch) result.catch(() => {});
    }
  }

  function jump() {
    follower.currentTime = master.currentTime;
    mirrorPlayState();
  }

  function correct() {
    if (master.paused) return;
    if (follower.seeking) return;
    const drift = master.currentTime - follower.currentTime;
    if (Math.abs(drift) > HARD_SEEK) {
      follower.currentTime = master.currentTime;
      follower.playbackRate = master.playbackRate;
    } else if (Math.abs(drift) >= NUDGE) {
      follower.playbackRate = master.playbackRate * (drift > 0 ? 1.05 : 0.95);
    } else if (follower.playbackRate !== master.playbackRate) {
      follower.playbackRate = master.playbackRate;
    }
  }

  for (const name of ["seeking", "seeked", "pause", "play", "ratechange", "ended"]) {
    on(master, name, () => {
      if (name === "ratechange") follower.playbackRate = master.playbackRate;
      jump();
    });
  }
  // timeupdate also covers the loop restart: currentTime jumps back and the gap exceeds HARD_SEEK.
  on(master, "timeupdate", correct);

  let active = true;
  let frameHandle = null;
  if (typeof master.requestVideoFrameCallback === "function") {
    const tick = () => {
      if (!active) return;
      correct();
      frameHandle = master.requestVideoFrameCallback(tick);
    };
    frameHandle = master.requestVideoFrameCallback(tick);
  }
  cleanups.push(() => {
    active = false;
    if (frameHandle !== null && typeof master.cancelVideoFrameCallback === "function") {
      master.cancelVideoFrameCallback(frameHandle);
    }
  });

  return () => {
    for (const cleanup of cleanups) cleanup();
  };
}
