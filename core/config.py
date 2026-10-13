"""Mọi đường dẫn cấu hình qua biến môi trường — một chỗ duy nhất để sửa.

FA_ROOT     thư mục gốc dự án; đường dẫn tương đối (glb, texture) tính từ đây   mặc định: thư mục repo
FA_RUNTIME  output sinh ra khi chạy (scene.glb, log)                             mặc định: $FA_ROOT/runtime
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def root() -> Path:
    return Path(os.environ.get("FA_ROOT", REPO))


def runtime_dir() -> Path:
    return Path(os.environ.get("FA_RUNTIME", root() / "runtime"))
