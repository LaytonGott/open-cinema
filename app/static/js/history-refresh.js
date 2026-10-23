// Keeps the history statuses of unfollowed, still-running shots fresh by polling the shot list.
import { listShots } from "./api.js";
import { getState, subscribe, upsertHistory } from "./state.js";

const POLL_MS = 1000;
const RUNNING = new Set(["queued", "generating", "optics"]);

let timer = null;

function followedId() {
  const shot = getState().shot;
  return shot ? shot.id : null;
}

// True while some history item is running and is not the followed shot.
function needsPolling() {
  const followed = followedId();
  return getState().history.some((r) => RUNNING.has(r.status) && r.id !== followed);
}

async function poll() {
  timer = null;
  if (!needsPolling()) return;
  try {
    const body = await listShots();
    for (const record of (body && body.shots) || []) {
      if (record.id !== followedId()) upsertHistory(record);
    }
  } catch (e) {
    // ignored on purpose; the next tick tries again
  }
  schedule();
}

function schedule() {
  if (timer === null && needsPolling()) timer = setTimeout(poll, POLL_MS);
}

export function initHistoryRefresh() {
  subscribe(schedule);
  schedule();
}
