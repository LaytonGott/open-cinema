// User actions that talk to the API and update the shared state.
import * as api from "./api.js";
import { getState, setState, setShot } from "./state.js";

export async function submitShot() {
  const { description, camera, lens_mm, aperture, framing } = getState().form;
  setState({ submitting: true, error: null });
  try {
    const record = await api.createShot({ description, camera, lens_mm, aperture, framing });
    setShot(record);
  } catch (err) {
    if (err instanceof api.ApiError) {
      setState({ error: err.message });
    } else {
      throw err;
    }
  } finally {
    setState({ submitting: false });
  }
}
