"""Chuẩn hoá asset 3D của SKU (FR-02, FR-03, FR-05).

Sau chuẩn hoá: glTF Y-up, đơn vị mét, gốc toạ độ ở tâm đáy (x, z giữa; y thấp nhất = 0),
bounding box khớp kích thước nhập vào. Áp dụng cho cả GLB do TRELLIS.2 sinh ra
lẫn file 3D có sẵn của công ty (định dạng trimesh đọc được: glb/gltf/obj/ply/stl...).
FBX: đổi sang GLB bằng Blender trước (trimesh không đọc FBX).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class AssetReport:
    src: str
    dst: str
    original_extents_m: tuple[float, float, float]
    final_extents_m: tuple[float, float, float]
    scale: tuple[float, float, float]
    mode: str
    triangles: int
    warnings: list[str] = field(default_factory=list)

    def within(self, dims_mm: tuple[int, int, int], tol: float = 0.01) -> bool:
        """Kiểm tra FR-02: bbox lệch ≤ tol so với kích thước nhập. dims_mm = (rộng x, sâu z, cao y)."""
        w, d, h = (x / 1000.0 for x in dims_mm)
        fx, fy, fz = self.final_extents_m
        return all(abs(a - b) <= tol * b for a, b in ((fx, w), (fy, h), (fz, d)))


def _load_scene(path: str | Path):
    import trimesh

    return trimesh.load(str(path), force="scene")


def normalize_asset(src: str | Path, dst: str | Path, dims_mm: tuple[int, int, int],
                    mode: str = "fit", max_triangles: int = 100_000) -> AssetReport:
    """dims_mm = (width_mm, depth_mm, height_mm) của sản phẩm thật.

    mode="fit"     : scale riêng từng trục → bbox khớp chính xác kích thước nhập (mặc định)
    mode="uniform" : scale đều theo chiều cao → giữ tỉ lệ hình, bbox có thể lệch
    """
    import trimesh

    if mode not in ("fit", "uniform"):
        raise ValueError("mode phải là 'fit' hoặc 'uniform'")
    scene = _load_scene(src)
    if scene.is_empty:
        raise ValueError(f"{src}: file không có hình học")
    lo, hi = scene.bounds
    ext = hi - lo
    if np.any(ext <= 0):
        raise ValueError(f"{src}: bounding box suy biến {ext}")

    target = np.array([dims_mm[0], dims_mm[2], dims_mm[1]], dtype=np.float64) / 1000.0  # x, y, z
    warnings: list[str] = []
    per_axis = target / ext
    if mode == "fit":
        s = per_axis
        spread = per_axis.max() / per_axis.min()
        if spread > 1.10:
            warnings.append(
                f"tỉ lệ hình lệch kích thước nhập vào {spread:.2f}× giữa các trục — kiểm tra hướng model hoặc ảnh đầu vào")
    else:
        s = np.full(3, per_axis[1])

    center = np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    m = np.eye(4)
    m[:3, :3] = np.diag(s)
    m[:3, 3] = -center * s
    scene.apply_transform(m)

    tris = int(sum(len(g.faces) for g in scene.geometry.values() if hasattr(g, "faces")))
    if tris > max_triangles:
        warnings.append(f"{tris} tam giác > {max_triangles} — giảm lưới (node Simplify Trimesh) trước khi dùng web")

    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    from core.io import write_bytes_atomic

    data = scene.export(file_type="glb")

    write_bytes_atomic(dst, data)
    lo2, hi2 = scene.bounds
    return AssetReport(
        src=str(src), dst=str(dst),
        original_extents_m=tuple(float(x) for x in ext),
        final_extents_m=tuple(float(x) for x in (hi2 - lo2)),
        scale=tuple(float(x) for x in s), mode=mode, triangles=tris, warnings=warnings,
    )


def _hex_rgba(hex_color: str) -> list[int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"mã màu sai: {hex_color}")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [255]


def tint_scene(scene, hex_color: str) -> int:
    """Đổi màu gần đúng (FR-05): đặt baseColorFactor của vật liệu PBR = màu tint.

    Theo glTF, baseColorFactor nhân với texture → giữ vân gỗ/vải, đổi tông màu.
    Kết quả chỉ là "màu minh hoạ". Trả về số vật liệu đã đổi.
    """
    import trimesh

    rgba = _hex_rgba(hex_color)
    n = 0
    for g in scene.geometry.values():
        vis = getattr(g, "visual", None)
        if isinstance(vis, trimesh.visual.texture.TextureVisuals):
            mat = vis.material
            if isinstance(mat, trimesh.visual.material.SimpleMaterial):
                mat = mat.to_pbr()
                vis.material = mat
            mat.baseColorFactor = np.array(rgba, dtype=np.uint8)
            n += 1
        elif isinstance(vis, trimesh.visual.color.ColorVisuals):
            g.visual = trimesh.visual.ColorVisuals(g, vertex_colors=np.tile(rgba, (len(g.vertices), 1)))
            n += 1
    return n
