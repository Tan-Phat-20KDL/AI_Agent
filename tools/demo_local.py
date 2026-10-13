"""Chạy thử phần 3D trên laptop, KHÔNG cần GPU: 1 bàn + 4 ghế trong phòng, sàn lát gỗ.

Bàn/ghế ở đây là khối tạm đúng kích thước; trên GPU sẽ thay bằng GLB từ TRELLIS.2.
Ảnh gỗ là vân giả sinh bằng numpy; thay bằng ảnh thanh gỗ/gạch thật của bạn.

    python tools/demo_local.py
    python -m http.server 8080      # mở http://localhost:8080/viewer/?scene=runtime/out/demo/scene.glb
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from core.assets import normalize_asset  # noqa: E402
from core.scene3d import build_scene, table_chairs_spec  # noqa: E402

RUNTIME = ROOT / "runtime"
TABLE, CHAIR = (1600, 900, 750), (450, 520, 820)


def write_png(path: Path, rgb: np.ndarray) -> None:
    """Ghi PNG RGB 8-bit chỉ bằng thư viện chuẩn (không cần Pillow)."""
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].astype(np.uint8).tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def wood_texture(w: int = 1024, h: int = 171) -> np.ndarray:
    """1 thanh gỗ 1200 × 200 mm: vân dọc + mạch tối ở mép."""
    rng = np.random.default_rng(3)
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    grain = 0.5 + 0.25 * np.sin(2 * np.pi * (y * 9 + 0.15 * np.sin(2 * np.pi * x * 3))) + rng.normal(0, 0.04, (h, w))
    base = np.array([150, 105, 65]) + np.array([60, 45, 30]) * grain[..., None]
    edge = (y < 0.02) | (y > 0.98) | (x < 0.004)
    return np.clip(np.where(edge[..., None], base * 0.55, base), 0, 255)


def _box(extents, center, color):
    m = trimesh.creation.box(extents=extents)
    m.apply_translation(center)
    m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=np.tile(color, (len(m.vertices), 1)))
    return m


def placeholder(kind: str) -> trimesh.Trimesh:
    if kind == "table":
        c = [40, 40, 40, 255]
        parts = [_box([1.6, 0.04, 0.9], [0, 0.73, 0], c)]
        parts += [_box([0.05, 0.71, 0.05], [x, 0.355, z], c) for x in (-0.75, 0.75) for z in (-0.4, 0.4)]
    else:
        c = [120, 80, 50, 255]
        parts = [_box([0.45, 0.04, 0.45], [0, 0.45, 0.035], c), _box([0.45, 0.4, 0.04], [0, 0.66, -0.2], c)]
        parts += [_box([0.035, 0.43, 0.035], [x, 0.215, z], c) for x in (-0.2, 0.2) for z in (-0.2, 0.24)]
    return trimesh.util.concatenate(parts)


def main() -> None:
    print("1) Tạo bàn/ghế tạm + ảnh thanh gỗ mẫu")
    for name, dims in (("table", TABLE), ("chair", CHAIR)):
        raw = RUNTIME / "tmp" / f"{name}_raw.glb"
        raw.parent.mkdir(parents=True, exist_ok=True)
        placeholder(name).export(str(raw))
        normalize_asset(raw, RUNTIME / "assets" / f"{name}.glb", dims, mode="uniform")
    write_png(RUNTIME / "inputs" / "wood.png", wood_texture())

    print("2) Dựng cảnh: phòng 4.2 × 3.6 m, 1 bàn + 4 ghế, sàn lát gỗ 1200 × 200 mm")
    spec = table_chairs_spec("demo", (4200, 3600, 2800), "runtime/assets/table.glb", TABLE,
                             "runtime/assets/chair.glb", CHAIR, 4,
                             texture_path="runtime/inputs/wood.png", texture_on="floor", tile_mm=(1200, 200))
    meta = build_scene(spec, ROOT, RUNTIME / "out" / "demo" / "scene.glb")
    for node, info in meta["nodes"].items():
        print(f"   {node:8} vị trí {info['position_mm']} mm, quay {info['rotation_deg']}°")

    print("\nXem 3D:  python -m http.server 8080")
    print("         http://localhost:8080/viewer/?scene=runtime/out/demo/scene.glb")


if __name__ == "__main__":
    main()
