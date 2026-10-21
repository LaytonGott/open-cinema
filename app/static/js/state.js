// Shared client state: holds server values only; the client invents none.

const TERMINAL = ["done", "failed", "cancelled"];

let state = {
  options: null,
  form: {
    description: "",
    camera: "static",
    lens_mm: 50,
    aperture: 2.8,
    framing: "full-body",
  },
  comfy: { state: "checking", device: null, message: null },
  shot: null,
  history: [],
  submitting: false,
  error: null,
};

const listeners = new Set();

export function getState() {
  return state;
}

export function setState(patch) {
  state = { ...state, ...patch };
  for (const fn of [...listeners]) fn(state);
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// Stores a shot record; progress never decreases for the same non-terminal shot.
export function setShot(record) {
  const cur = state.shot;
  let next = record;
  if (
    record &&
    cur &&
    record.id === cur.id &&
    !TERMINAL.includes(record.status) &&
    typeof record.progress === "number" &&
    typeof cur.progress === "number" &&
    record.progress < cur.progress
  ) {
    next = { ...record, progress: cur.progress };
  }
  setState({ shot: next });
}
