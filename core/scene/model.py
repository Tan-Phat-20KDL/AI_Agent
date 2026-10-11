"""Scene graph: nguồn sự thật duy nhất của một thiết kế (SPEC mục 4, SRS 1.3).

Hệ toạ độ (giống three.js / glTF): gốc ở góc phòng trên sàn, đơn vị mm trong JSON
(đổi sang mét khi xuất GLB), x theo chiều rộng, z theo chiều sâu, y hướng lên.
rotation_deg quay quanh trục y; 0° = mặt trước sản phẩm nhìn về +z,
90° = nhìn về +x (cùng quy ước Object3D.rotation.y của three.js).

Ví dụ:
{
  "schema_version": 1, "scene_id": "s_001", "version": 1,
  "room": {"width_mm": 4200, "depth_mm": 3600, "height_mm": 2800},
  "objects": [
    {"id": "table_1", "variant_id": "TB01-BLK", "qty": 1, "placement": "center",
     "instances": [{"position_mm": [2100, 1800], "rotation_deg": 0}]},
    {"id": "chair_1", "variant_id": "CH01-BRN", "qty": 4, "placement": "around:table_1",
     "instances": []}
  ]
}
"""

from __future__ import annotations

import copy
import re
from typing import Any

from core.repository import Catalog

SCHEMA_VERSION = 1
_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
PLACEMENTS = ("center", "against_wall", "free")


class SceneError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("Scene không hợp lệ:\n" + "\n".join(f"  - {e}" for e in errors))


def new_scene(scene_id: str, width_mm: int, depth_mm: int, height_mm: int = 2700,
              room_extra: dict | None = None) -> dict:
    room = {"width_mm": int(width_mm), "depth_mm": int(depth_mm), "height_mm": int(height_mm)}
    if room_extra:
        room.update(room_extra)
    return {"schema_version": SCHEMA_VERSION, "scene_id": scene_id, "version": 0, "room": room, "objects": []}


def object_by_id(scene: dict, object_id: str) -> dict:
    for o in scene.get("objects", []):
        if o.get("id") == object_id:
            return o
    raise KeyError(f"Scene không có object '{object_id}'")


def _valid_placement(p: Any, ids: set[str]) -> str | None:
    if not isinstance(p, str):
        return "placement phải là chuỗi"
    if p in PLACEMENTS:
        return None
    if p.startswith("around:"):
        target = p.split(":", 1)[1]
        return None if target in ids else f"placement trỏ tới object không tồn tại '{target}'"
    return f"placement không hợp lệ '{p}' (cho phép {PLACEMENTS} hoặc around:<id>)"


def validate_scene(scene: dict, catalog: Catalog | None = None) -> list[str]:
    """Trả về danh sách lỗi (rỗng = hợp lệ). Có catalog thì kiểm tra cả SKU/asset."""
    errs: list[str] = []
    if scene.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version phải là {SCHEMA_VERSION}")
    if not isinstance(scene.get("scene_id"), str) or not _ID.match(scene.get("scene_id", "")):
        errs.append("scene_id thiếu hoặc sai định dạng [A-Za-z0-9_-]")
    room = scene.get("room")
    if not isinstance(room, dict):
        errs.append("thiếu room")
    else:
        for k in ("width_mm", "depth_mm", "height_mm"):
            v = room.get(k)
            if not isinstance(v, int) or v <= 0:
                errs.append(f"room.{k} phải là số nguyên > 0")
    objects = scene.get("objects")
    if not isinstance(objects, list):
        errs.append("objects phải là danh sách")
        return errs
    ids = [o.get("id") for o in objects if isinstance(o, dict)]
    id_set = {i for i in ids if isinstance(i, str)}
    seen: set[str] = set()
    for idx, o in enumerate(objects):
        where = f"objects[{idx}]"
        if not isinstance(o, dict):
            errs.append(f"{where} phải là object")
            continue
        oid = o.get("id")
        if not isinstance(oid, str) or not _ID.match(oid):
            errs.append(f"{where}.id sai định dạng")
        elif oid in seen:
            errs.append(f"trùng id object '{oid}'")
        else:
            seen.add(oid)
            where = f"object '{oid}'"
        qty = o.get("qty")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
            errs.append(f"{where}.qty phải là số nguyên ≥ 1")
        perr = _valid_placement(o.get("placement", "center"), id_set - {oid})
        if perr:
            errs.append(f"{where}: {perr}")
        inst = o.get("instances", [])
        if not isinstance(inst, list):
            errs.append(f"{where}.instances phải là danh sách")
        else:
            if isinstance(qty, int) and len(inst) > qty:
                errs.append(f"{where} có {len(inst)} vị trí nhưng qty={qty}")
            for j, it in enumerate(inst):
                pos = it.get("position_mm") if isinstance(it, dict) else None
                if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(x, (int, float)) for x in pos)):
                    errs.append(f"{where}.instances[{j}].position_mm phải là [x, z]")
                rot = it.get("rotation_deg", 0) if isinstance(it, dict) else None
                if not isinstance(rot, (int, float)):
                    errs.append(f"{where}.instances[{j}].rotation_deg phải là số")
        if o.get("custom"):
            continue  # hàng đặt: không bắt buộc có trong catalog, báo giá tay (FR-17)
        vid = o.get("variant_id")
        if not isinstance(vid, str) or not vid:
            errs.append(f"{where}.variant_id bắt buộc (hoặc đặt custom=true)")
        elif catalog is not None:
            v = catalog.variants.get(vid)
            if v is None:
                errs.append(f"{where}: biến thể '{vid}' không có trong CSV")
            elif not v.is_usable:
                errs.append(f"{where}: biến thể '{vid}' chưa được duyệt (asset_status={v.asset_status})")
    return errs


def ensure_valid(scene: dict, catalog: Catalog | None = None) -> dict:
    errs = validate_scene(scene, catalog)
    if errs:
        raise SceneError(errs)
    return scene


def clone(scene: dict) -> dict:
    return copy.deepcopy(scene)
