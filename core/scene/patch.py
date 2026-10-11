"""JSON Patch (RFC 6902) tối giản, không phụ thuộc thư viện ngoài.

Hỗ trợ đủ 6 phép: add, remove, replace, move, copy, test.
Áp dụng trên bản sao — tài liệu gốc không bao giờ bị sửa.
"""

from __future__ import annotations

import copy
from typing import Any


class PatchError(ValueError):
    pass


def _parse_pointer(ptr: str) -> list[str]:
    if ptr == "":
        return []
    if not ptr.startswith("/"):
        raise PatchError(f"JSON pointer phải bắt đầu bằng '/': {ptr!r}")
    return [p.replace("~1", "/").replace("~0", "~") for p in ptr[1:].split("/")]


def _index(container: list, token: str, allow_end: bool) -> int:
    if token == "-" and allow_end:
        return len(container)
    if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
        raise PatchError(f"chỉ số mảng không hợp lệ: {token!r}")
    i = int(token)
    limit = len(container) if allow_end else len(container) - 1
    if i > limit:
        raise PatchError(f"chỉ số {i} vượt quá mảng dài {len(container)}")
    return i


def _parent(doc: Any, tokens: list[str]) -> tuple[Any, str]:
    if not tokens:
        raise PatchError("không thao tác trực tiếp trên gốc tài liệu")
    cur = doc
    for t in tokens[:-1]:
        if isinstance(cur, dict):
            if t not in cur:
                raise PatchError(f"đường dẫn không tồn tại tại '{t}'")
            cur = cur[t]
        elif isinstance(cur, list):
            cur = cur[_index(cur, t, allow_end=False)]
        else:
            raise PatchError(f"không đi tiếp được qua giá trị nguyên thuỷ tại '{t}'")
    return cur, tokens[-1]


def _get(doc: Any, ptr: str) -> Any:
    cur = doc
    for t in _parse_pointer(ptr):
        if isinstance(cur, dict):
            if t not in cur:
                raise PatchError(f"đường dẫn không tồn tại: {ptr}")
            cur = cur[t]
        elif isinstance(cur, list):
            cur = cur[_index(cur, t, allow_end=False)]
        else:
            raise PatchError(f"đường dẫn không tồn tại: {ptr}")
    return cur


def _add(doc: Any, ptr: str, value: Any) -> Any:
    tokens = _parse_pointer(ptr)
    if not tokens:
        return copy.deepcopy(value)
    parent, last = _parent(doc, tokens)
    if isinstance(parent, dict):
        parent[last] = copy.deepcopy(value)
    elif isinstance(parent, list):
        parent.insert(_index(parent, last, allow_end=True), copy.deepcopy(value))
    else:
        raise PatchError(f"không thêm được vào {ptr}")
    return doc


def _remove(doc: Any, ptr: str) -> tuple[Any, Any]:
    parent, last = _parent(doc, _parse_pointer(ptr))
    if isinstance(parent, dict):
        if last not in parent:
            raise PatchError(f"không có khoá để xoá: {ptr}")
        return doc, parent.pop(last)
    if isinstance(parent, list):
        return doc, parent.pop(_index(parent, last, allow_end=False))
    raise PatchError(f"không xoá được {ptr}")


def apply_patch(doc: Any, patch: list[dict]) -> Any:
    if not isinstance(patch, list):
        raise PatchError("patch phải là danh sách thao tác")
    out = copy.deepcopy(doc)
    for n, op in enumerate(patch):
        if not isinstance(op, dict) or "op" not in op or "path" not in op:
            raise PatchError(f"thao tác #{n} thiếu 'op' hoặc 'path'")
        kind, path = op["op"], op["path"]
        try:
            if kind == "add":
                out = _add(out, path, op["value"])
            elif kind == "remove":
                out, _ = _remove(out, path)
            elif kind == "replace":
                _get(out, path)  # phải tồn tại
                out, _ = _remove(out, path) if path else (out, None)
                out = _add(out, path, op["value"])
            elif kind == "move":
                src = op["from"]
                if path.startswith(src + "/"):
                    raise PatchError("không move vào bên trong chính nó")
                out, val = _remove(out, src)
                out = _add(out, path, val)
            elif kind == "copy":
                out = _add(out, path, _get(out, op["from"]))
            elif kind == "test":
                if _get(out, path) != op["value"]:
                    raise PatchError(f"test thất bại tại {path}")
            else:
                raise PatchError(f"op không hỗ trợ: {kind!r}")
        except KeyError as e:
            raise PatchError(f"thao tác #{n} ({kind}) thiếu trường {e}") from None
        except PatchError as e:
            raise PatchError(f"thao tác #{n} ({kind} {path}): {e}") from None
    return out
