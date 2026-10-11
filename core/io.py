"""Ghi file an toàn: ghi ra file tạm rồi đổi tên (NFR-04).

Nếu tiến trình bị kill giữa chừng, file cũ vẫn còn nguyên.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_bytes_atomic(path: str | os.PathLike, data: bytes) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


def write_text_atomic(path: str | os.PathLike, text: str, encoding: str = "utf-8") -> Path:
    return write_bytes_atomic(path, text.encode(encoding))


def write_json_atomic(path: str | os.PathLike, obj: Any) -> Path:
    return write_text_atomic(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n")


def read_json(path: str | os.PathLike) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
