// User actions that talk to the API and update the shared state.
import * as api from "./api.js";
import { followShot, stopFollowing } from "./follow.js";
import { getState, setState, setShot } from "./state.js";
import { checkHealth } from "./components/header.js";

const RUNNING_STATUSES = ["queued", "generating", "optics"];

// Bumped by selectShot, newShot and submitShot; a selectShot whose token is stale is ignored.
let navigationToken = 0;

// Show an ApiError from a POST as the state error; anything else is shown too and never rethrown.
export function handlePostError(err) {
  if (err instanceof api.ApiError) {
    setState({ error: err.message });
    if (err.status === 503 && err.code === "comfy_unreachable") {
      setState({ comfy: { state: "down", device: null, message: err.message } });
    }
  } else if (err instanceof TypeError) {
    setState({ error: "Can't reach the app server" });
  } else {
    setState({ error: (err && err.message) || String(err) });
  }
}

export async function submitShot() {
  navigationToken++;
  const { description, camera, lens_mm, aperture, framing } = getState().form;
  setState({ submitting: true, error: null });
  try {
    const record = await api.createShot({ description, camera, lens_mm, aperture, framing });
    setShot(record);
    followShot(record.id);
  } catch (err) {
    handlePostError(err);
    checkHealth();
  } finally {
    setState({ submitting: false });
  }
}

export async function retryShot() {
  setState({ error: null });
  try {
    const shot = getState().shot;
    if (!shot) return;
    let record;
    if (shot.status === "failed" && shot.before_url) {
      record = await api.reapplyShot(shot.id, shot.params.aperture);
    } else {
      record = await api.createShot(shot.params);
    }
    setShot(record);
    followShot(record.id);
  } catch (err) {
    handlePostError(err);
  }
}

export async function reapplyShown(aperture) {
  setState({ error: null });
  try {
    const shot = getState().shot;
    if (!shot) return;
    const record = await api.reapplyShot(shot.id, aperture);
    setShot(record);
    followShot(record.id);
  } catch (err) {
    handlePostError(err);
  }
}

export function newShot() {
  navigationToken++;
  stopFollowing();
  setState({ shot: null, error: null });
  const field = document.querySelector("[data-testid=shot-description]");
  if (field) field.focus();
}

export async function selectShot(id) {
  stopFollowing();
  const token = ++navigationToken;
  try {
    const record = await api.getShot(id);
    if (token !== navigationToken) return;
    setShot(record);
    setState({ error: null });
    if (RUNNING_STATUSES.includes(record.status)) {
      followShot(id);
    }
  } catch (err) {
    handlePostError(err);
  }
}

export async function cancelCurrentShot() {
  setState({ error: null });
  try {
    const shot = getState().shot;
    if (!shot) return;
    const record = await api.cancelShot(shot.id);
    setShot(record);
  } catch (err) {
    handlePostError(err);
  }
}
