import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TABLE_DIMS = [1600, 900, 750]
CHAIR_DIMS = [450, 520, 820]


@pytest.fixture
def dining_spec() -> dict:
    """Bài toán chuẩn: 1 bàn + 4 ghế trong phòng 4.2 × 3.6 m."""
    return {
        "scene_id": "demo",
        "room": {"width_mm": 4200, "depth_mm": 3600, "height_mm": 2800},
        "objects": [
            {"id": "table", "glb": "assets/table.glb", "dims_mm": TABLE_DIMS, "qty": 1,
             "placement": "center", "instances": []},
            {"id": "chair", "glb": "assets/chair.glb", "dims_mm": CHAIR_DIMS, "qty": 4,
             "placement": "around:table", "instances": []},
        ],
    }


@pytest.fixture
def assets_root(tmp_path) -> Path:
    """Thư mục có table.glb, chair.glb (khối hộp đã chuẩn hoá đúng kích thước)."""
    trimesh = pytest.importorskip("trimesh")
    from core.assets import normalize_asset

    for name, dims in (("table", TABLE_DIMS), ("chair", CHAIR_DIMS)):
        raw = tmp_path / f"{name}_raw.glb"
        trimesh.creation.box(extents=[1, 1, 1]).export(str(raw))
        normalize_asset(raw, tmp_path / "assets" / f"{name}.glb", tuple(dims))
    return tmp_path
