// Follows one shot's progress: server-sent events, with polling as a fallback.
import * as api from "./api.js";
import { getState, setShot } from "./state.js";

const TERMINAL = ["done", "failed", "cancelled"];
const POLL_MS = 1000;
const MAX_RECONNECTS = 3;
const RECONNECT_MS = 500;

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
  let reconnects = 0;
  let stopped = false;

  function stop() {
    stopped = true;
    if (source) source.close();
    if (timer) clearTimeout(timer);
    if (reconnectTimer) clearTimeout(reconnectTimer);
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

  async function poll() {
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
    if (!stopped) timer = setTimeout(poll, POLL_MS);
  }

  function startPolling() {
    if (source) {
      source.close();
      source = null;
    }
    if (stopped || timer) return;
    timer = setTimeout(poll, POLL_MS);
  }

  function openSource() {
    reconnectTimer = null;
    if (stopped) return;
    source = new EventSource("/api/shots/" + encodeURIComponent(id) + "/events");
    source.addEventListener("shot", (ev) => {
      if (stopped) return;
      reconnects = 0;
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
