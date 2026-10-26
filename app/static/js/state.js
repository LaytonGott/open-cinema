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
  shownVersion: null,
  history: [],
  submitting: false,
  error: null,
  estimateM: null,
};

const listeners = new Set();

export function formatDistance(metres) {
  return metres < 10 ? metres.toFixed(1) : metres.toFixed(0);
}

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

// Stores a shot record; progress never decreases within one run. A run is still going while the
// previous status is non-terminal, so a re-apply (done) or retry (failed/cancelled) starts fresh.
export function setShot(record) {
  const cur = state.shot;
  let next = record;
  if (
    record &&
    cur &&
    record.id === cur.id &&
    !TERMINAL.includes(cur.status) &&
    typeof record.progress === "number" &&
    typeof cur.progress === "number" &&
    record.progress < cur.progress
  ) {
    next = { ...record, progress: cur.progress };
  }
  const fresh =
    !!record && (!cur || record.id !== cur.id || record.current_version !== cur.current_version);
  const patch = { shot: next };
  if (!record) patch.shownVersion = null;
  else if (fresh) patch.shownVersion = record.current_version ?? null;
  setState(patch);
  if (next) upsertHistory(next);
}

// Chooses which version of the shot the viewport shows (a version number, or null for the current one).
export function setShownVersion(n) {
  setState({ shownVersion: n ?? null });
}

// Returns the version object {n, aperture, url} that state.shownVersion names, else the current version, else null.
export function shownVersionOf(s) {
  const shot = s && s.shot;
  const versions = (shot && shot.versions) || [];
  const pick = (n) => versions.find((v) => v.n === n);
  return (s.shownVersion != null && pick(s.shownVersion)) || pick(shot && shot.current_version) || null;
}

// Puts a shot record into history, newest first: new ids go to the front, known ids are replaced in place.
export function upsertHistory(record) {
  const i = state.history.findIndex((r) => r.id === record.id);
  const history =
    i < 0
      ? [record, ...state.history]
      : state.history.map((r, j) => (j === i ? record : r));
  setState({ history });
}

// Replaces history with the server's list (newest first).
export function setHistory(records) {
  setState({ history: [...records] });
}
