"""Mọi đường dẫn cấu hình qua biến môi trường — một chỗ duy nhất để sửa.

FA_ROOT     thư mục gốc dự án (chứa data/, assets/)     mặc định: thư mục repo
FA_DATA     thư mục CSV                                  mặc định: $FA_ROOT/data
FA_RUNTIME  scene/quote/log/output sinh ra khi chạy      mặc định: $FA_ROOT/runtime
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def root() -> Path:
    return Path(os.environ.get("FA_ROOT", REPO))


def data_dir() -> Path:
    return Path(os.environ.get("FA_DATA", root() / "data"))


def runtime_dir() -> Path:
    return Path(os.environ.get("FA_RUNTIME", root() / "runtime"))
