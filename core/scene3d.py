"""Dựng cảnh 3D cho three.js: hộp phòng + bàn/ghế (GLB) + vật liệu lát sàn/tường.

spec = {
  "scene_id": "demo",
  "room": {"width_mm": 4200, "depth_mm": 3600, "height_mm": 2800},
  "surfaces": {                                   # tuỳ chọn: ảnh gạch/thanh gỗ lát lên mặt nào
    "floor": {"texture": "inputs/wood.png", "tile_mm": [1200, 200]},
  },
  "objects": [
    {"id": "table", "glb": "assets/table.glb", "dims_mm": [1600, 900, 750], "qty": 1, "placement": "center"},
    {"id": "chair", "glb": "assets/chair.glb", "dims_mm": [450, 520, 820], "qty": 4, "placement": "around:table"},
  ],
}

Ghi <out>.glb + <out>.meta.json. Node tên "<id>#<i>" (vd "chair#2"); mặt phòng tên "room_floor",
"room_wall_back"... Texture không nhúng vào GLB: viewer đọc từ meta và lặp theo tile_mm,
nên kích thước viên gạch/thanh gỗ hiển thị đúng tỉ lệ thật.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from core._util import snap_rotation
from core.io import export_glb, write_bytes_atomic, write_json_atomic
from core.placement import find_collisions, place_missing
from core.room import build_room_mesh

SURFACES = ("floor", "wall_back", "wall_left", "wall_right")


class SceneSpecError(ValueError):
    pass


def validate_spec(spec: dict) -> None:
    errs = []
    room = spec.get("room") or {}
    for k in ("width_mm", "depth_mm", "height_mm"):
        if not isinstance(room.get(k), int) or room[k] <= 0:
            errs.append(f"room.{k} phải là số nguyên > 0 (mm)")
    for name, surf in (spec.get("surfaces") or {}).items():
        if name not in SURFACES:
            errs.append(f"surfaces.{name}: chỉ hỗ trợ {SURFACES}")
        tile = surf.get("tile_mm")
        if not surf.get("texture") or not (isinstance(tile, list) and len(tile) == 2 and min(tile) > 0):
            errs.append(f"surfaces.{name}: cần texture và tile_mm [rộng, dài] > 0")
    ids = set()
    for o in spec.get("objects", []):
        oid = o.get("id")
        if not oid or oid in ids:
            errs.append(f"object id trống hoặc trùng: {oid!r}")
        ids.add(oid)
        if not o.get("glb"):
            errs.append(f"{oid}: thiếu glb")
        dm = o.get("dims_mm")
        if not (isinstance(dm, list) and len(dm) == 3 and min(dm) > 0):
            errs.append(f"{oid}: dims_mm phải là [rộng, sâu, cao] > 0")
        if not isinstance(o.get("qty", 1), int) or o.get("qty", 1) < 1:
            errs.append(f"{oid}: qty phải là số nguyên ≥ 1")
    if errs:
        raise SceneSpecError("Spec không hợp lệ:\n" + "\n".join(f"  - {e}" for e in errs))


def table_chairs_spec(scene_id, room_dims, table_glb, table_dims, chair_glb, chair_dims, chair_qty,
               texture_path="", texture_on="floor", tile_mm=(1200, 200)) -> dict:
    """Spec cho bài toán 1 bàn + N ghế (+ vật liệu lát lên 1 mặt) — dùng chung cho node ComfyUI và script."""
    objects = []
    if table_glb:
        objects.append({"id": "table", "glb": table_glb, "dims_mm": list(table_dims), "qty": 1,
                        "placement": "center", "instances": []})
    if chair_glb and chair_qty:
        objects.append({"id": "chair", "glb": chair_glb, "dims_mm": list(chair_dims), "qty": chair_qty,
                        "placement": "around:table" if table_glb else "center", "instances": []})
    w, d, h = room_dims
    spec = {"scene_id": scene_id, "room": {"width_mm": w, "depth_mm": d, "height_mm": h}, "objects": objects}
    if texture_path:
        spec["surfaces"] = {texture_on: {"texture": texture_path, "tile_mm": list(tile_mm)}}
    return spec


def _instance_matrix(x_mm: float, z_mm: float, rotation_deg: float) -> np.ndarray:
    a = math.radians(snap_rotation(rotation_deg))
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    m[:3, :3] = [[c, 0, s], [0, 1, 0], [-s, 0, c]]  # quay quanh y, giống three.js rotation.y
    m[:3, 3] = [x_mm / 1000.0, 0.0, z_mm / 1000.0]
    return m


def build_scene(spec: dict, root: str | Path, out_glb: str | Path) -> dict:
    """Đặt đồ (nếu chưa có vị trí) → ghi GLB + meta. Trả về meta (gồm vị trí đã đặt)."""
    import trimesh

    validate_spec(spec)
    root = Path(root)
    placed = place_missing(spec)
    if bad := find_collisions(placed):
        raise SceneSpecError(f"Đồ bị chồng/lòi khỏi phòng: {sorted(bad)}")

    out = trimesh.Scene()
    r = placed["room"]
    for name, mesh in build_room_mesh(r["width_mm"], r["depth_mm"], r["height_mm"]).items():
        color = [196, 178, 150, 255] if name == "floor" else [235, 232, 226, 255]
        # màu theo đỉnh: màu theo mặt khiến GLB export cần scipy
        mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=np.tile(color, (len(mesh.vertices), 1)))
        out.add_geometry(mesh, node_name=f"room_{name}", geom_name=f"room_{name}")

    nodes: dict[str, dict] = {}
    for obj in placed["objects"]:
        src = Path(obj["glb"]) if Path(obj["glb"]).is_absolute() else root / obj["glb"]
        if not src.exists():
            raise FileNotFoundError(f"Thiếu file 3D {src} của '{obj['id']}'")
        asset = trimesh.load(str(src), force="scene")
        geoms = {}
        for gname in asset.graph.nodes_geometry:
            tf, gkey = asset.graph[gname]
            ref = f"{obj['id']}/{gkey}"
            out.geometry[ref] = asset.geometry[gkey]  # 1 mesh dùng chung cho mọi instance
            geoms[gname] = (tf, ref)
        for i, inst in enumerate(obj["instances"]):
            node = f"{obj['id']}#{i}"
            x, z = inst["position_mm"]
            out.graph.update(frame_to=node, frame_from=out.graph.base_frame,
                             matrix=_instance_matrix(x, z, inst.get("rotation_deg", 0)))
            for gname, (tf, ref) in geoms.items():
                out.graph.update(frame_to=f"{node}/{gname}", frame_from=node, matrix=tf, geometry=ref)
            nodes[node] = {"object_id": obj["id"], "position_mm": [x, z], "rotation_deg": inst.get("rotation_deg", 0)}

    out_glb = Path(out_glb)
    write_bytes_atomic(out_glb, export_glb(out))
    meta = {"scene_id": placed.get("scene_id", out_glb.stem), "room": r,
            "surfaces": placed.get("surfaces", {}), "nodes": nodes, "objects": placed["objects"]}
    write_json_atomic(out_glb.with_suffix(".meta.json"), meta)
    return meta
