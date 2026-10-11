import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.repository import load_catalog  # noqa: E402


@pytest.fixture
def data_dir(tmp_path) -> Path:
    """Bản sao thư mục data/ mẫu để test được ghi thoải mái."""
    d = tmp_path / "data"
    shutil.copytree(ROOT / "data", d)
    return d


@pytest.fixture
def catalog(data_dir):
    return load_catalog(data_dir)


@pytest.fixture
def dining_scene() -> dict:
    """Ví dụ trong yêu cầu: bàn đen + 4 ghế nâu."""
    return {
        "schema_version": 1,
        "scene_id": "s_demo",
        "version": 0,
        "room": {"width_mm": 4200, "depth_mm": 3600, "height_mm": 2800},
        "objects": [
            {"id": "table_1", "variant_id": "TB01-BLK", "qty": 1, "placement": "center", "instances": []},
            {"id": "chair_1", "variant_id": "CH01-BRN", "qty": 4, "placement": "around:table_1", "instances": []},
        ],
    }
