"""Server tĩnh cho viewer — thay `python -m http.server`.

Trên Windows, http.server lấy MIME type từ Registry; nhiều máy khai `.js` là text/plain → trình duyệt
từ chối chạy ES module (lỗi "Expected a JavaScript-or-Wasm module script"). Ở đây ép MIME đúng.

    python tools/serve.py            # http://localhost:8765/viewer/?scene=runtime/out/demo/scene.glb
    python tools/serve.py 9000 --bind 127.0.0.1
"""

from __future__ import annotations

import argparse
import functools
import http.server
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIME = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".wasm": "application/wasm",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, **MIME}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # sửa code xong F5 là thấy, không dính cache
        super().end_headers()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", type=int, default=8765)
    ap.add_argument("--bind", default="127.0.0.1")
    a = ap.parse_args()
    handler = functools.partial(Handler, directory=str(ROOT))
    with http.server.ThreadingHTTPServer((a.bind, a.port), handler) as httpd:
        print(f"Viewer: http://localhost:{a.port}/viewer/?scene=runtime/out/demo/scene.glb   (Ctrl+C để dừng)")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
