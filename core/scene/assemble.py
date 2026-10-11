"""Lắp cảnh 3D cho three.js (FR-10): phòng + asset từng object → scene.glb + scene.meta.json.

Mỗi instance là 1 node tên "<object_id>#<i>" (vd "chair_1#2"); viewer dùng tên này để
tra SKU/giá trong scene.meta.json. Khi sửa 1 object (W2), chỉ node của object đó đổi.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from core.io import write_bytes_atomic, write_json_atomic
from core.repository import Catalog
from core.room import build_room_mesh

from .._util import snap_rotation


def _instance_matrix(x_mm: float, z_mm: float, rotation_deg: float) -> np.ndarray:
    a = math.radians(snap_rotation(rotation_deg))
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    # quay quanh trục y: (0,0,1) → (sin a, 0, cos a), giống three.js rotation.y
    m[:3, :3] = [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    m[:3, 3] = [x_mm / 1000.0, 0.0, z_mm / 1000.0]
    return m


def assemble_scene(scene: dict, catalog: Catalog, assets_root: str | Path, out_glb: str | Path,
                   include_room: bool = True) -> dict:
    """Ghi out_glb và out_glb.meta.json. Trả về meta (dict)."""
    import trimesh

    from core.assets import tint_scene

    assets_root = Path(assets_root)
    out = trimesh.Scene()
    meta: dict = {"scene_id": scene["scene_id"], "version": scene.get("version"),
                  "room": scene["room"], "nodes": {}}

    if include_room:
        r = scene["room"]
        for name, mesh in build_room_mesh(r["width_mm"], r["depth_mm"], r["height_mm"]).items():
            color = [196, 178, 150, 255] if name == "floor" else [235, 232, 226, 255]
            # màu theo đỉnh (màu theo mặt khiến GLB export cần scipy)
            mesh.visual = trimesh.visual.ColorVisuals(mesh, vertex_colors=np.tile(color, (len(mesh.vertices), 1)))
            out.add_geometry(mesh, node_name=f"room/{name}", geom_name=f"room_{name}")

    cache: dict[str, trimesh.Scene] = {}
    registered: dict[str, str] = {}  # (asset key, geom key) → tên geometry trong cảnh ra
    for obj in scene["objects"]:
        if obj.get("custom"):
            continue
        v = catalog.variant(obj["variant_id"])
        p = catalog.product(v.sku)
        key = f"{v.asset_glb}|{v.tint_hex}"
        if key not in cache:
            src = assets_root / v.asset_glb if not Path(v.asset_glb).is_absolute() else Path(v.asset_glb)
            if not src.exists():
                raise FileNotFoundError(f"Thiếu asset {src} của biến thể {v.variant_id}")
            asset = trimesh.load(str(src), force="scene")
            if v.tint_hex:
                tint_scene(asset, v.tint_hex)
            cache[key] = asset
        asset = cache[key]
        for i, inst in enumerate(obj.get("instances", [])):
            node = f"{obj['id']}#{i}"
            x, z = inst["position_mm"]
            base = _instance_matrix(x, z, inst.get("rotation_deg", 0))
            out.graph.update(frame_to=node, frame_from=out.graph.base_frame, matrix=base)
            for gname in asset.graph.nodes_geometry:
                tf, geom_key = asset.graph[gname]
                # dùng chung 1 mesh cho mọi instance cùng asset (GLB nhỏ hơn, không copy)
                ref = registered.get(f"{key}|{geom_key}")
                if ref is None:
                    ref = f"{v.variant_id}/{geom_key}"
                    out.geometry[ref] = asset.geometry[geom_key]
                    registered[f"{key}|{geom_key}"] = ref
                out.graph.update(frame_to=f"{node}/{gname}", frame_from=node, matrix=tf, geometry=ref)
            meta["nodes"][node] = {
                "object_id": obj["id"], "variant_id": v.variant_id, "sku": p.sku, "name": p.name,
                "color": v.color_name, "price_vnd": v.price_vnd, "tinted": bool(v.tint_hex),
            }

    out_glb = Path(out_glb)
    write_bytes_atomic(out_glb, out.export(file_type="glb"))
    write_json_atomic(out_glb.with_suffix(".meta.json"), meta)
    return meta
