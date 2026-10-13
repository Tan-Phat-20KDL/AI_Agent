"""Use-case chính cho UI: input người dùng (kích thước, file 3D, ảnh vật liệu) → cảnh 3D.

Thiếu GLB → dùng khối tạm đúng kích thước; thiếu ảnh vật liệu → vân gỗ mẫu.
Mọi file của 1 lần dựng nằm trong run_dir (runtime/<...>/<run_id>/).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from core.assets import normalize_asset
from core.assets.placeholder import hex_to_rgba, placeholder_mesh, wood_texture, write_png
from core.scene3d import build_scene, table_chairs_spec


@dataclass
class Item:
    dims_mm: tuple[int, int, int]          # rộng x, sâu z, cao y
    glb: str | None = None                 # file 3D người dùng tải lên (vd output TRELLIS.2)
    color: str = "#808080"                 # màu khối tạm khi không có glb


@dataclass
class Design:
    room_mm: tuple[int, int, int]
    table: Item
    chair: Item
    chair_qty: int = 4
    texture: str | None = None             # ảnh 1 viên gạch / 1 thanh gỗ
    tile_mm: tuple[int, int] = (1200, 200)
    surface: str = "floor"                 # floor | wall_back | wall_left | wall_right
    warnings: list[str] = field(default_factory=list)


def _asset(item: Item, kind: str, run_dir: Path, warnings: list[str]) -> Path:
    dst = run_dir / f"{kind}.glb"
    if item.glb:
        rep = normalize_asset(item.glb, dst, item.dims_mm, mode="fit")
        warnings += [f"{kind}: {w}" for w in rep.warnings]
        return dst
    raw = run_dir / f"{kind}_raw.glb"
    placeholder_mesh(kind, hex_to_rgba(item.color)).export(str(raw))
    normalize_asset(raw, dst, item.dims_mm, mode="fit")
    raw.unlink(missing_ok=True)
    return dst


def build_design(d: Design, root: str | Path, run_dir: str | Path) -> dict:
    """Ghi run_dir/scene.glb + scene.meta.json. Trả meta (+ 'scene' = đường dẫn tương đối từ root)."""
    root, run_dir = Path(root).resolve(), Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    rel = lambda p: p.resolve().relative_to(root).as_posix()  # noqa: E731

    table_glb = _asset(d.table, "table", run_dir, d.warnings)
    chair_glb = _asset(d.chair, "chair", run_dir, d.warnings) if d.chair_qty else None
    if d.texture:
        tex = run_dir / f"texture{Path(d.texture).suffix.lower() or '.png'}"
        shutil.copyfile(d.texture, tex)
    else:
        tex = write_png(run_dir / "texture.png", wood_texture())

    spec = table_chairs_spec(run_dir.name, d.room_mm, rel(table_glb), list(d.table.dims_mm),
                             rel(chair_glb) if chair_glb else "", list(d.chair.dims_mm), d.chair_qty,
                             texture_path=rel(tex), texture_on=d.surface, tile_mm=list(d.tile_mm))
    meta = build_scene(spec, root, run_dir / "scene.glb")
    meta["scene"] = rel(run_dir / "scene.glb")
    meta["warnings"] = d.warnings
    return meta
