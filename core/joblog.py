"""Log mỗi job dạng JSON lines (FR-16): thời gian từng bước, VRAM đỉnh, lỗi.

    log = JobLog("logs/jobs.jsonl", workflow="W1", scene_id="s_001")
    with log.step("trellis"):
        ...
    log.finish()

VRAM đỉnh đo bằng nvidia-smi chạy nền (không cần PyTorch); máy không có GPU → None.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class VramSampler:
    def __init__(self, interval_s: float = 0.5):
        self.interval = interval_s
        self.peak_mb: int | None = None
        self._stop = threading.Event()
        self._t: threading.Thread | None = None
        self.available = shutil.which("nvidia-smi") is not None

    def _read(self) -> int | None:
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout
            return max(int(x) for x in out.split()) if out.strip() else None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None

    def _loop(self):
        while not self._stop.is_set():
            v = self._read()
            if v is not None:
                self.peak_mb = v if self.peak_mb is None else max(self.peak_mb, v)
            self._stop.wait(self.interval)

    def __enter__(self):
        if self.available:
            self._t = threading.Thread(target=self._loop, daemon=True)
            self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join(timeout=2)


class JobLog:
    def __init__(self, path: str | Path, workflow: str, **fields):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.job_id = uuid.uuid4().hex[:12]
        self.base = {"job_id": self.job_id, "workflow": workflow, **fields}
        self.t0 = time.perf_counter()
        self.ok = True

    def _write(self, rec: dict):
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **self.base, **rec}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @contextmanager
    def step(self, name: str):
        t = time.perf_counter()
        with VramSampler() as vs:
            try:
                yield
            except BaseException as e:
                self.ok = False
                self._write({"step": name, "seconds": round(time.perf_counter() - t, 3),
                             "vram_peak_mb": vs.peak_mb, "error": f"{type(e).__name__}: {e}",
                             "trace": traceback.format_exc(limit=5)})
                raise
        self._write({"step": name, "seconds": round(time.perf_counter() - t, 3), "vram_peak_mb": vs.peak_mb})

    def finish(self, **fields):
        self._write({"step": "_total", "seconds": round(time.perf_counter() - self.t0, 3), "ok": self.ok, **fields})
