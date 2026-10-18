"""Run one LTX benchmark through the Comfy SDK and record time, VRAM and RAM.

Expects local ComfyUI on :8188 with comfy-api-proxy on :8189 in front of it.

    COMFY_BASE_URL=http://127.0.0.1:8189 python bench/run_bench.py ltxv-0.9.8-13b --seed 42 --label ltxv098-cold \
        --comfy-log D:/OpenCinema/logs/comfyui.log
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import threading
import time
from pathlib import Path

import psutil
import pynvml
from comfy_sdk import Comfy

from workflows import WORKFLOWS

GB = 1024 ** 3
HERE = Path(__file__).resolve().parent


def comfy_pid(port: int = 8188) -> int:
    for c in psutil.net_connections(kind="tcp"):
        if c.status == psutil.CONN_LISTEN and c.laddr.port == port and c.pid:
            return c.pid
    raise RuntimeError(f"no process listening on :{port}")


class Monitor(threading.Thread):
    """Samples GPU memory, ComfyUI process memory and system memory every `dt` seconds."""

    def __init__(self, pid: int, dt: float = 0.5):
        super().__init__(daemon=True)
        self.proc, self.dt, self.samples, self._halt = psutil.Process(pid), dt, [], threading.Event()
        pynvml.nvmlInit()
        self.gpu = pynvml.nvmlDeviceGetHandleByIndex(0)

    def sample(self) -> dict:
        mi = self.proc.memory_info()
        vm, sw = psutil.virtual_memory(), psutil.swap_memory()
        return {
            "t": time.time(),
            "gpu_used": pynvml.nvmlDeviceGetMemoryInfo(self.gpu).used,
            "proc_wset": mi.rss,              # working set (resident)
            "proc_private": mi.private,       # private commit
            "proc_peak_wset": mi.peak_wset,
            "sys_used": vm.total - vm.available,
            "sys_avail": vm.available,
            "pagefile_used": sw.used,
        }

    def run(self):
        while not self._halt.is_set():
            self.samples.append(self.sample())
            time.sleep(self.dt)

    def stop(self):
        self._halt.set()
        self.join()


def log_tail(path: str | None, start: int) -> str:
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        f.seek(start)
        return f.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", choices=sorted(WORKFLOWS))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--label", required=True)
    ap.add_argument("--encoder-device", default="cpu", help="LTX-2 only: cpu (offloaded) or default")
    ap.add_argument("--comfy-log", default=None)
    args = ap.parse_args()

    build = WORKFLOWS[args.workflow]
    kwargs = {"encoder_device": args.encoder_device} if args.workflow.startswith("ltx2") else {}
    graph = build(args.seed, f"bench/{args.label}", **kwargs)

    mon = Monitor(comfy_pid())
    base = []
    for _ in range(5):
        base.append(mon.sample())
        time.sleep(0.5)
    baseline = {k: statistics.median(s[k] for s in base) for k in base[0] if k != "t"}
    log_start = os.path.getsize(args.comfy_log) if args.comfy_log and os.path.exists(args.comfy_log) else 0

    client = Comfy()
    wf = client.workflows.from_json(graph)
    mon.start()
    t0 = time.time()
    job = client.run(wf)
    wall = time.time() - t0
    mon.stop()

    out_dir = HERE / "out"
    out_dir.mkdir(exist_ok=True)
    saved = []
    for o in job.get_outputs("29" if args.workflow.startswith("ltx2") else "14"):
        p = out_dir / f"{args.label}{Path(o.name).suffix or '.mp4'}"
        o.to_file(p)
        saved.append(str(p))

    s = mon.samples
    peak = lambda k: max(x[k] for x in s)
    log = log_tail(args.comfy_log, log_start)
    result = {
        "label": args.label,
        "workflow": args.workflow,
        "seed": args.seed,
        "encoder_device": kwargs.get("encoder_device"),
        "status": job.status,
        "wall_s": round(wall, 1),
        "comfy_reported_s": [float(x) for x in re.findall(r"Prompt executed in ([\d.]+) seconds", log)],
        "gpu_total_gb": round(pynvml.nvmlDeviceGetMemoryInfo(mon.gpu).total / GB, 2),
        "gpu_baseline_gb": round(baseline["gpu_used"] / GB, 2),
        "gpu_peak_gb": round(peak("gpu_used") / GB, 2),
        "gpu_peak_over_baseline_gb": round((peak("gpu_used") - baseline["gpu_used"]) / GB, 2),
        "proc_peak_wset_gb": round(max(peak("proc_wset"), s[-1]["proc_peak_wset"] if s else 0) / GB, 2),
        "proc_peak_private_gb": round(peak("proc_private") / GB, 2),
        "sys_ram_total_gb": round(psutil.virtual_memory().total / GB, 2),
        "sys_used_baseline_gb": round(baseline["sys_used"] / GB, 2),
        "sys_used_peak_gb": round(peak("sys_used") / GB, 2),
        "sys_avail_min_gb": round(min(x["sys_avail"] for x in s) / GB, 2),
        "pagefile_baseline_gb": round(baseline["pagefile_used"] / GB, 2),
        "pagefile_peak_gb": round(peak("pagefile_used") / GB, 2),
        "log_load_lines": [l.strip() for l in log.splitlines() if re.search(r"loaded (completely|partially)|Requested to load|lowvram|offload|out of memory|OOM", l, re.I)][:40],
        "log_speed_lines": re.findall(r"\d+/\d+ \[[^\]]*(?:s/it|it/s)\]", log)[-12:],
        "outputs": saved,
        "samples": len(s),
    }
    res_dir = HERE / "results"
    res_dir.mkdir(exist_ok=True)
    (res_dir / f"{args.label}.json").write_text(json.dumps(result, indent=2))
    with open(res_dir / f"{args.label}.samples.jsonl", "w") as f:
        for x in s:
            f.write(json.dumps(x) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("log_load_lines",)}, indent=2))


if __name__ == "__main__":
    main()
