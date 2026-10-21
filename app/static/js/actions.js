// User actions that talk to the API and update the shared state.
import * as api from "./api.js";
import { followShot } from "./follow.js";
import { getState, setState, setShot } from "./state.js";

// Show an ApiError from a POST as the state error; anything else is rethrown.
export function handlePostError(err) {
  if (err instanceof api.ApiError) {
    setState({ error: err.message });
  } else {
    throw err;
  }
}

export async function submitShot() {
  const { description, camera, lens_mm, aperture, framing } = getState().form;
  setState({ submitting: true, error: null });
  try {
    const record = await api.createShot({ description, camera, lens_mm, aperture, framing });
    setShot(record);
    followShot(record.id);
  } catch (err) {
    handlePostError(err);
  } finally {
    setState({ submitting: false });
  }
}

export async function retryShot() {
  const shot = getState().shot;
  try {
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

export async function cancelCurrentShot() {
  try {
    const record = await api.cancelShot(getState().shot.id);
    setShot(record);
  } catch (err) {
    if (err instanceof api.ApiError) {
      setState({ error: err.message });
    } else {
      throw err;
    }
  }
}
