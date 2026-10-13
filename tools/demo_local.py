"""Chạy thử phần 3D trên laptop, KHÔNG cần GPU: 1 bàn + 4 ghế trong phòng, sàn lát gỗ.

Bàn/ghế ở đây là khối tạm đúng kích thước; trên GPU sẽ thay bằng GLB từ TRELLIS.2.

    python tools/demo_local.py
    python tools/serve.py      # mở http://localhost:8765/viewer/?scene=runtime/out/demo/scene.glb
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252

from core.assets import normalize_asset  # noqa: E402
from core.assets.placeholder import placeholder_mesh, wood_texture, write_png  # noqa: E402
from core.scene3d import build_scene, table_chairs_spec  # noqa: E402

RUNTIME = ROOT / "runtime"
TABLE, CHAIR = (1600, 900, 750), (450, 520, 820)


def main() -> None:
    print("1) Tạo bàn/ghế tạm + ảnh thanh gỗ mẫu")
    for name, dims in (("table", TABLE), ("chair", CHAIR)):
        raw = RUNTIME / "tmp" / f"{name}_raw.glb"
        raw.parent.mkdir(parents=True, exist_ok=True)
        placeholder_mesh(name).export(str(raw))
        normalize_asset(raw, RUNTIME / "assets" / f"{name}.glb", dims, mode="uniform")
    write_png(RUNTIME / "inputs" / "wood.png", wood_texture())

    print("2) Dựng cảnh: phòng 4.2 × 3.6 m, 1 bàn + 4 ghế, sàn lát gỗ 1200 × 200 mm")
    spec = table_chairs_spec("demo", (4200, 3600, 2800), "runtime/assets/table.glb", TABLE,
                             "runtime/assets/chair.glb", CHAIR, 4,
                             texture_path="runtime/inputs/wood.png", texture_on="floor", tile_mm=(1200, 200))
    meta = build_scene(spec, ROOT, RUNTIME / "out" / "demo" / "scene.glb")
    for node, info in meta["nodes"].items():
        print(f"   {node:8} vị trí {info['position_mm']} mm, quay {info['rotation_deg']}°")

    print("\nXem 3D:  python tools/serve.py")
    print("         http://localhost:8765/viewer/?scene=runtime/out/demo/scene.glb")


if __name__ == "__main__":
    main()
