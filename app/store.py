"""On-disk shot store: one folder per shot under `data_dir/shots/<id>/`."""

import datetime
import json
import os
import secrets
import shutil
import sys
from pathlib import Path


def new_shot_id(existing=()):
    """Return a new shot id `YYYYMMDD-HHMMSS-xxxx` (UTC time, 4 random lowercase hex chars) not in `existing`."""
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        shot_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        if shot_id not in existing:
            return shot_id


class ShotStore:
    """Shots kept in memory in creation order and persisted as `shot.json` files."""

    def __init__(self, data_dir):
        """`data_dir` is the data directory (path); shots live in `data_dir/shots/`."""
        self.root = Path(data_dir) / "shots"
        self._records = {}
        self._seq = 0

    def shot_dir(self, shot_id):
        """Return the `Path` of the folder of shot `shot_id`."""
        return self.root / shot_id

    def _write(self, record):
        directory = self.shot_dir(record["id"])
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / "shot.json.tmp"
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(tmp, directory / "shot.json")

    def add(self, record):
        """Store a new record (dict with an `id`), filling `created_at` (UTC ISO string) and `seq` if missing; returns the record."""
        if "created_at" not in record:
            record["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")
        if "seq" not in record:
            self._seq += 1
            record["seq"] = self._seq
        else:
            self._seq = max(self._seq, record["seq"])
        self._write(record)
        self._records[record["id"]] = record
        return record

    def save(self, record):
        """Write an existing record (dict with an `id`) to its `shot.json`; returns None."""
        self._write(record)
        self._records[record["id"]] = record

    def get(self, shot_id):
        """Return the record dict of shot `shot_id`, or None if unknown."""
        return self._records.get(shot_id)

    def list(self):
        """Return all records as a list in creation order, oldest first."""
        return list(self._records.values())

    def remove(self, shot_id):
        """Forget shot `shot_id` and delete its folder; returns None."""
        self._records.pop(shot_id, None)
        shutil.rmtree(self.shot_dir(shot_id), ignore_errors=True)

    def load_all(self):
        """Load every `shots/*/shot.json`, skipping unreadable files with a stderr warning; returns None."""
        loaded = []
        for path in sorted(self.root.glob("*/shot.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                print(f"warning: skipping {path}: {exc}", file=sys.stderr)
                continue
            if not isinstance(record, dict):
                print(f"warning: skipping {path}: not a JSON object", file=sys.stderr)
                continue
            record.setdefault("id", path.parent.name)
            loaded.append(record)

        def key(r):
            seq = r.get("seq")
            return (str(r.get("created_at", "")), seq if isinstance(seq, int) else 0)

        loaded.sort(key=key)
        self._records = {r["id"]: r for r in loaded}
        seqs = [r["seq"] for r in loaded if isinstance(r.get("seq"), int)]
        self._seq = max(seqs, default=0)

    def recover_interrupted(self):
        """Mark loaded shots left queued, generating or optics as failed ("interrupted") and save them; returns the list of recovered shot ids."""
        message = "Open Cinema was stopped while this shot was running. Submit the shot again."
        recovered = []
        for record in self.list():
            status = record.get("status")
            if status not in ("queued", "generating", "optics"):
                continue
            stage = "optics" if status == "optics" else "generate"
            record["status"] = "failed"
            record["error"] = {"code": "interrupted", "message": message, "stage": stage}
            for entry in record.get("stages") or []:
                if isinstance(entry, dict) and entry.get("id") == stage:
                    entry["state"] = "failed"
                    entry["message"] = message
            self.save(record)
            recovered.append(record["id"])
        return recovered
