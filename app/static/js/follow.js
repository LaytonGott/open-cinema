// Follows one shot's progress: server-sent events, with polling as a fallback.
import * as api from "./api.js";
import { getState, setShot } from "./state.js";

const TERMINAL = ["done", "failed", "cancelled"];
const POLL_MS = 1000;
const MAX_RECONNECTS = 3;
const RECONNECT_MS = 500;
const SILENT_MS = 25000;
const LOST_RETRY_MS = 3000;
const RETRY_STREAM_MS = 30000;

let stopCurrent = null;

export function stopFollowing() {
  if (stopCurrent) stopCurrent();
  stopCurrent = null;
}

export function followShot(id) {
  if (stopCurrent) stopCurrent();

  let source = null;
  let timer = null;
  let reconnectTimer = null;
  let watchdog = null;
  let lostTimer = null;
  let retryTimer = null;
  let reconnects = 0;
  let stopped = false;

  function stop() {
    stopped = true;
    if (source) source.close();
    if (timer) clearTimeout(timer);
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (watchdog) clearTimeout(watchdog);
    if (lostTimer) clearTimeout(lostTimer);
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = null;
    watchdog = null;
    lostTimer = null;
    source = null;
    timer = null;
    reconnectTimer = null;
    if (stopCurrent === stop) stopCurrent = null;
  }

  function isCurrent() {
    const shot = getState().shot;
    return !!shot && shot.id === id;
  }

  function apply(record) {
    setShot(record);
    if (TERMINAL.includes(record.status)) stop();
  }

  function setStatusLabel(text) {
    const label = document.querySelector("[data-testid=status-label]");
    if (label) label.textContent = text;
  }

  function restartWatchdog() {
    if (watchdog) clearTimeout(watchdog);
    if (lostTimer) clearTimeout(lostTimer);
    lostTimer = null;
    watchdog = stopped ? null : setTimeout(checkSilent, SILENT_MS);
  }

  async function checkSilent() {
    watchdog = null;
    lostTimer = null;
    if (stopped) return;
    if (!isCurrent()) {
      stop();
      return;
    }
    try {
      const record = await api.getShot(id);
      if (stopped || !isCurrent()) return;
      apply(record);
      if (!stopped) restartWatchdog();
    } catch (err) {
      if (stopped || !isCurrent()) return;
      setStatusLabel("Connection lost, retrying");
      lostTimer = setTimeout(checkSilent, LOST_RETRY_MS);
    }
  }

  async function poll() {
    timer = null;
    if (stopped) return;
    if (!isCurrent()) {
      stop();
      return;
    }
    try {
      const record = await api.getShot(id);
      if (stopped) return;
      apply(record);
    } catch (err) {
      // keep trying until the shot is terminal or no longer current
    }
    if (!stopped && !source) timer = setTimeout(poll, POLL_MS);
  }

  function startPolling() {
    if (source) {
      source.close();
      source = null;
    }
    if (watchdog) clearTimeout(watchdog);
    watchdog = null;
    if (stopped) return;
    if (!retryTimer) retryTimer = setTimeout(retryStream, RETRY_STREAM_MS);
    if (timer) return;
    timer = setTimeout(poll, POLL_MS);
  }

  function retryStream() {
    retryTimer = null;
    if (stopped || source) return;
    reconnects = 0;
    openSource();
  }

  function streamWorks() {
    if (timer) clearTimeout(timer);
    if (retryTimer) clearTimeout(retryTimer);
    timer = null;
    retryTimer = null;
  }

  function openSource() {
    reconnectTimer = null;
    if (stopped) return;
    source = new EventSource("/api/shots/" + encodeURIComponent(id) + "/events");
    restartWatchdog();
    source.addEventListener("shot", (ev) => {
      if (stopped) return;
      reconnects = 0;
      streamWorks();
      restartWatchdog();
      try {
        apply(JSON.parse(ev.data));
      } catch (err) {
        // ignore a malformed event
      }
    });
    source.onerror = () => {
      if (stopped) return;
      if (source) source.close();
      source = null;
      if (reconnects < MAX_RECONNECTS) {
        reconnects += 1;
        reconnectTimer = setTimeout(openSource, RECONNECT_MS * reconnects);
      } else {
        startPolling();
      }
    };
  }

  stopCurrent = stop;
  openSource();
  return stop;
}
