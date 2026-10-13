"""Đồ thay thế khi chưa có dữ liệu thật: khối bàn/ghế thô và ảnh vân gỗ mẫu.

Dùng cho demo và app khi người dùng chưa tải GLB (từ TRELLIS.2) hay ảnh vật liệu.
Chỉ cần numpy + trimesh; ghi PNG bằng thư viện chuẩn (không cần Pillow).
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np


def write_png(path: str | Path, rgb: np.ndarray) -> Path:
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].astype(np.uint8).tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    return path


def wood_texture(w: int = 1024, h: int = 171) -> np.ndarray:
    """Ảnh 1 thanh gỗ (ngang = chiều dài thanh): vân dọc + mạch tối ở mép."""
    rng = np.random.default_rng(3)
    x = np.linspace(0, 1, w)[None, :]
    y = np.linspace(0, 1, h)[:, None]
    grain = 0.5 + 0.25 * np.sin(2 * np.pi * (y * 9 + 0.15 * np.sin(2 * np.pi * x * 3))) + rng.normal(0, 0.04, (h, w))
    base = np.array([150, 105, 65]) + np.array([60, 45, 30]) * grain[..., None]
    edge = (y < 0.02) | (y > 0.98) | (x < 0.004)
    return np.clip(np.where(edge[..., None], base * 0.55, base), 0, 255)


def _box(extents, center, color):
    import trimesh

    m = trimesh.creation.box(extents=extents)
    m.apply_translation(center)
    m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=np.tile(color, (len(m.vertices), 1)))
    return m


def placeholder_mesh(kind: str, color=None):
    """Khối thô 'table' hoặc 'chair' (đơn vị tuỳ ý — normalize_asset sẽ scale đúng kích thước).

    Ghế: lưng ở phía sau (−z) → mặt trước nhìn về +z, đúng quy ước xếp ghế.
    """
    import trimesh

    if kind == "table":
        c = color or [40, 40, 40, 255]
        parts = [_box([1.6, 0.04, 0.9], [0, 0.73, 0], c)]
        parts += [_box([0.05, 0.71, 0.05], [x, 0.355, z], c) for x in (-0.75, 0.75) for z in (-0.4, 0.4)]
    elif kind == "chair":
        c = color or [120, 80, 50, 255]
        parts = [_box([0.45, 0.04, 0.45], [0, 0.45, 0.035], c), _box([0.45, 0.4, 0.04], [0, 0.66, -0.2], c)]
        parts += [_box([0.035, 0.43, 0.035], [x, 0.215, z], c) for x in (-0.2, 0.2) for z in (-0.2, 0.24)]
    else:
        raise ValueError(f"kind phải là 'table' hoặc 'chair', nhận {kind!r}")
    mesh = trimesh.util.concatenate(parts)
    mesh.unmerge_vertices()  # mỗi mặt đỉnh riêng → cạnh sắc, không bị làm mượt
    return mesh


def hex_to_rgba(hex_color: str) -> list[int]:
    """Mã màu sRGB (từ bảng chọn màu) → màu đỉnh glTF. glTF coi COLOR_0 là tuyến tính, nên phải đổi
    sRGB → linear; không đổi thì màu hiện ra nhạt hơn màu đã chọn."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        lin = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        out.append(round(lin * 255))
    return out + [255]
