"""Client tối giản cho server ComfyUI (chỉ dùng thư viện chuẩn).

Route theo tài liệu ComfyUI: POST /prompt, GET /history/<id>, GET /queue,
POST /interrupt, POST /upload/image.
Có timeout: hết giờ → gọi /interrupt và báo lỗi rõ ràng, không treo (NFR-02).
"""

from __future__ import annotations

import json
import mimetypes
import time
import urllib.request
import uuid
from pathlib import Path


class ComfyError(RuntimeError):
    pass


class JobTimeout(ComfyError):
    pass


class ComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", http_timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self.http_timeout = http_timeout
        self.client_id = uuid.uuid4().hex

    def _req(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        with urllib.request.urlopen(req, timeout=self.http_timeout) as r:
            raw = r.read()
        return json.loads(raw) if raw else None

    def submit(self, workflow_api: dict) -> str:
        """Gửi workflow dạng API JSON (ComfyUI: Workflow → Export (API)). Trả prompt_id."""
        body = json.dumps({"prompt": workflow_api, "client_id": self.client_id}).encode()
        res = self._req("POST", "/prompt", body, {"Content-Type": "application/json"})
        if not res or "prompt_id" not in res:
            raise ComfyError(f"ComfyUI không nhận workflow: {res}")
        if res.get("node_errors"):
            raise ComfyError(f"Lỗi node: {res['node_errors']}")
        return res["prompt_id"]

    def queue_size(self) -> int:
        q = self._req("GET", "/queue") or {}
        return len(q.get("queue_running", [])) + len(q.get("queue_pending", []))

    def interrupt(self) -> None:
        self._req("POST", "/interrupt", b"{}", {"Content-Type": "application/json"})

    def wait(self, prompt_id: str, timeout_s: float, poll_s: float = 1.0) -> dict:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            hist = self._req("GET", f"/history/{prompt_id}") or {}
            if prompt_id in hist:
                entry = hist[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyError(f"Workflow lỗi: {status.get('messages')}")
                return entry
            time.sleep(poll_s)
        self.interrupt()
        raise JobTimeout(f"Job {prompt_id} quá {timeout_s:.0f}s → đã gửi /interrupt")

    def run(self, workflow_api: dict, timeout_s: float) -> dict:
        return self.wait(self.submit(workflow_api), timeout_s)

    def upload_image(self, path: str | Path, overwrite: bool = True) -> str:
        """Tải ảnh (vd ảnh phòng) vào thư mục input của ComfyUI. Trả tên file để dùng trong workflow."""
        path = Path(path)
        boundary = uuid.uuid4().hex
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n".encode() + path.read_bytes() + b"\r\n",
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\n"
            f"{'true' if overwrite else 'false'}\r\n".encode(),
            f"--{boundary}--\r\n".encode(),
        ]
        res = self._req("POST", "/upload/image", b"".join(parts),
                        {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        return (res or {}).get("name", path.name)
