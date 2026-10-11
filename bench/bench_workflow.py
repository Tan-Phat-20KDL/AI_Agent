"""Benchmark Phase 0 — chạy trên máy GPU (RunPod/AWS), không chạy trên laptop.

Chạy 1 workflow ComfyUI (dạng API JSON) N lần, đo thời gian và VRAM đỉnh (nvidia-smi),
ghi JSON lines + in p50/p95/max. Số đo này thay MỌI con số giả định trong SPEC/SRS
(thời gian GPU mỗi job, timeout = 3 × p95, VRAM ≤ 80%).

    python bench/bench_workflow.py workflows/api/i1_trellis.json --runs 5 --timeout 900

Lần chạy đầu thường gồm cả thời gian nạp model (cold) — được tách riêng trong kết quả.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.comfy_client import ComfyClient  # noqa: E402
from core.joblog import VramSampler  # noqa: E402


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))
    return xs[k]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow", type=Path)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--url", default="http://127.0.0.1:8188")
    ap.add_argument("--out", type=Path, default=ROOT / "runtime" / "bench.jsonl")
    ap.add_argument("--gpu-mb", type=int, default=0, help="tổng VRAM (MB); 0 = đọc từ nvidia-smi")
    a = ap.parse_args()
    if not a.gpu_mb:
        import subprocess

        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout.split()
        a.gpu_mb = int(out[0]) if out else 1

    wf = json.loads(a.workflow.read_text(encoding="utf-8"))
    cli = ComfyClient(a.url)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(a.runs):
        t = time.perf_counter()
        with VramSampler(0.25) as vs:
            cli.run(wf, timeout_s=a.timeout)
        rec = {"workflow": a.workflow.name, "run": i, "cold": i == 0,
               "seconds": round(time.perf_counter() - t, 2), "vram_peak_mb": vs.peak_mb}
        rows.append(rec)
        with a.out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(rec)

    warm = [r["seconds"] for r in rows if not r["cold"]] or [rows[0]["seconds"]]
    peak = max((r["vram_peak_mb"] or 0) for r in rows)
    print(f"\ncold: {rows[0]['seconds']}s | warm p50 {statistics.median(warm):.1f}s "
          f"p95 {pct(warm, 95):.1f}s max {max(warm):.1f}s | VRAM đỉnh {peak} MB "
          f"({peak / a.gpu_mb:.0%} GPU) → timeout đề xuất {3 * pct(warm, 95):.0f}s")
    if peak > 0.8 * a.gpu_mb:
        print("CẢNH BÁO: VRAM đỉnh > 80% (vi phạm NFR-01) — hạ độ phân giải TRELLIS.2 hoặc tách model")


if __name__ == "__main__":
    main()
