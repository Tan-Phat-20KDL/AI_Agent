"""Lưu scene theo version: scenes/<scene_id>/v<N>.json, không bao giờ ghi đè (FR-12).

- commit(): áp JSON Patch lên version mới nhất → kiểm tra phạm vi + hợp lệ → ghi v<N+1>.
- revert(): "undo" = tạo version mới có nội dung của version cũ (lịch sử giữ nguyên).
- Khoá lạc quan: phải nói rõ đang sửa từ version nào; nếu đã có version mới hơn → từ chối.
"""

from __future__ import annotations

import re
from pathlib import Path

from core.io import read_json, write_json_atomic
from core.repository import Catalog

from .model import SceneError, clone, validate_scene
from .patch import apply_patch
from .scope import EditScope, check_scope

_V = re.compile(r"^v(\d+)\.json$")


class StaleVersionError(RuntimeError):
    pass


class ScopeViolation(SceneError):
    pass


class SceneStore:
    def __init__(self, root: str | Path, catalog: Catalog | None = None):
        self.root = Path(root)
        self.catalog = catalog

    def _dir(self, scene_id: str) -> Path:
        return self.root / scene_id

    def path(self, scene_id: str, version: int) -> Path:
        return self._dir(scene_id) / f"v{version}.json"

    def versions(self, scene_id: str) -> list[int]:
        d = self._dir(scene_id)
        if not d.exists():
            return []
        return sorted(int(m.group(1)) for p in d.iterdir() if (m := _V.match(p.name)))

    def latest_version(self, scene_id: str) -> int:
        vs = self.versions(scene_id)
        if not vs:
            raise KeyError(f"Chưa có scene '{scene_id}'")
        return vs[-1]

    def load(self, scene_id: str, version: int | None = None) -> dict:
        version = self.latest_version(scene_id) if version is None else version
        p = self.path(scene_id, version)
        if not p.exists():
            raise KeyError(f"Scene '{scene_id}' không có version {version}")
        return read_json(p)

    def _write(self, scene: dict) -> dict:
        p = self.path(scene["scene_id"], scene["version"])
        if p.exists():
            raise StaleVersionError(f"{p.name} đã tồn tại — không ghi đè")
        write_json_atomic(p, scene)
        return scene

    def _validate(self, scene: dict) -> None:
        errs = validate_scene(scene, self.catalog)
        if errs:
            raise SceneError(errs)

    def create(self, scene: dict, note: str = "") -> dict:
        if self.versions(scene["scene_id"]):
            raise StaleVersionError(f"Scene '{scene['scene_id']}' đã tồn tại")
        s = clone(scene)
        s["version"] = 1
        s["parent_version"] = None
        if note:
            s["note"] = note
        self._validate(s)
        return self._write(s)

    def commit(self, scene_id: str, base_version: int, patch: list[dict], scope: EditScope,
               note: str = "") -> dict:
        latest = self.latest_version(scene_id)
        if base_version != latest:
            raise StaleVersionError(
                f"Đang sửa từ v{base_version} nhưng mới nhất là v{latest} — tải lại rồi sửa")
        before = self.load(scene_id, latest)
        after = apply_patch(before, patch)
        violations = check_scope(before, after, scope)
        if violations:
            raise ScopeViolation(violations)
        return self._commit_scene(before, after, note)

    def commit_scene(self, scene_id: str, base_version: int, new_scene: dict, scope: EditScope,
                     note: str = "") -> dict:
        """Như commit() nhưng nhận scene đã sửa sẵn (dùng cho bộ đặt đồ tự động)."""
        latest = self.latest_version(scene_id)
        if base_version != latest:
            raise StaleVersionError(f"Đang sửa từ v{base_version} nhưng mới nhất là v{latest}")
        before = self.load(scene_id, latest)
        violations = check_scope(before, new_scene, scope)
        if violations:
            raise ScopeViolation(violations)
        return self._commit_scene(before, new_scene, note)

    def _commit_scene(self, before: dict, after: dict, note: str) -> dict:
        s = clone(after)
        s["version"] = before["version"] + 1
        s["parent_version"] = before["version"]
        if note:
            s["note"] = note
        else:
            s.pop("note", None)
        self._validate(s)
        return self._write(s)

    def revert(self, scene_id: str, to_version: int) -> dict:
        latest = self.latest_version(scene_id)
        old = self.load(scene_id, to_version)
        s = clone(old)
        s["version"] = latest + 1
        s["parent_version"] = latest
        s["note"] = f"undo về v{to_version}"
        self._validate(s)
        return self._write(s)
