import json

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")

from core.assets import normalize_asset  # noqa: E402
from core.room import estimate_room, fit_plane_ransac  # noqa: E402
from core.scene3d import SceneSpecError, build_scene, table_chairs_spec  # noqa: E402


def test_build_scene_nodes_positions_and_texture(dining_spec, assets_root):
    dining_spec["surfaces"] = {"floor": {"texture": "inputs/wood.png", "tile_mm": [1200, 200]}}
    out = assets_root / "out" / "scene.glb"
    meta = build_scene(dining_spec, assets_root, out)
    assert set(meta["nodes"]) == {"table#0", "chair#0", "chair#1", "chair#2", "chair#3"}
    assert meta["surfaces"]["floor"]["tile_mm"] == [1200, 200]
    saved = json.loads(out.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert saved["nodes"] == meta["nodes"]

    loaded = trimesh.load(str(out), force="scene")
    assert {"room_floor", "table#0", "chair#3"} <= set(loaded.graph.nodes)
    tf, _ = loaded.graph.get("table#0")
    x, z = meta["nodes"]["table#0"]["position_mm"]
    assert np.allclose(tf[[0, 2], 3], [x / 1000, z / 1000], atol=1e-6)   # mm → m đúng chỗ


def test_bad_spec_reports_every_problem(dining_spec):
    dining_spec["room"]["width_mm"] = 0
    dining_spec["objects"][1]["qty"] = 0
    dining_spec["surfaces"] = {"ceiling": {"texture": "x.png", "tile_mm": [1, 1]}}
    with pytest.raises(SceneSpecError) as e:
        build_scene(dining_spec, ".", "unused.glb")
    msg = str(e.value)
    assert "room.width_mm" in msg and "chair: qty" in msg and "surfaces.ceiling" in msg


def test_missing_glb_file_is_clear(dining_spec, tmp_path):
    with pytest.raises(FileNotFoundError, match="table"):
        build_scene(dining_spec, tmp_path, tmp_path / "scene.glb")


def test_table_chairs_spec_helper():
    s = table_chairs_spec("x", (4000, 3000, 2700), "t.glb", [1600, 900, 750], "c.glb", [450, 520, 820], 4,
                          texture_path="wood.png", texture_on="wall_back", tile_mm=[600, 600])
    assert [o["id"] for o in s["objects"]] == ["table", "chair"]
    assert s["objects"][1]["placement"] == "around:table"
    assert s["surfaces"] == {"wall_back": {"texture": "wood.png", "tile_mm": [600, 600]}}


# ---------------------------------------------------------------- asset + phòng


def _box(path, extents):
    trimesh.creation.box(extents=extents).export(str(path))


def test_normalize_asset_matches_dims(tmp_path):
    _box(tmp_path / "raw.glb", [1.0, 0.5, 0.6])   # đầu ra AI: tỉ lệ đúng, đơn vị tuỳ ý
    rep = normalize_asset(tmp_path / "raw.glb", tmp_path / "out.glb", (1600, 900, 750))
    assert rep.within((1600, 900, 750)) and not rep.warnings
    lo, hi = trimesh.load(str(tmp_path / "out.glb"), force="scene").bounds
    assert abs(lo[1]) < 1e-6 and abs(lo[0] + hi[0]) < 1e-6 and abs(lo[2] + hi[2]) < 1e-6


def test_normalize_warns_on_bad_proportions(tmp_path):
    _box(tmp_path / "raw.glb", [1.0, 1.0, 1.0])
    assert normalize_asset(tmp_path / "raw.glb", tmp_path / "out.glb", (1600, 900, 750)).warnings


def test_ransac_plane_with_outliers():
    rng = np.random.default_rng(1)
    xy = rng.uniform(-2, 2, size=(800, 2))
    plane = np.c_[xy[:, 0], np.full(800, 1.4), xy[:, 1]] + rng.normal(0, 0.003, (800, 3))
    n, d, mask = fit_plane_ransac(np.vstack([plane, rng.uniform(-2, 2, size=(200, 3))]))
    assert abs(abs(n[1]) - 1) < 1e-2 and abs(abs(d) - 1.4) < 1e-2 and mask[:800].mean() > 0.95


def test_estimate_room_from_synthetic_point_map():
    """Phòng 4×3×2.7 m, camera cao 1.4 m chúc xuống 15° — giả lập output MoGe-2 (toạ độ OpenCV)."""
    rng = np.random.default_rng(0)
    W, D, H = 4.0, 3.0, 2.7
    floor = np.c_[rng.uniform(0, W, 3000), np.zeros(3000), rng.uniform(0, D, 3000)]
    back = np.c_[rng.uniform(0, W, 1500), rng.uniform(0, H, 1500), np.full(1500, D)]
    p = (np.vstack([floor, back]) - [W / 2, 1.4, -0.5]) * [1, -1, 1]
    t = np.radians(15)
    p = p @ np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]]).T
    mask = np.r_[np.ones(3000, bool), np.zeros(1500, bool)]
    est = estimate_room(p, mask)
    assert abs(est.camera_height_mm - 1400) < 30
    assert abs(est.width_mm - 4000) / 4000 < 0.06 and abs(est.depth_mm - 3000) / 3000 < 0.06
    fixed = estimate_room(p * 0.8, mask, calibration=(estimate_room(p * 0.8, mask).camera_height_mm, 1400))
    assert abs(fixed.camera_height_mm - 1400) <= 2


def test_floor_mask_from_normals():
    from core.room import floor_mask_from_normals

    n = np.zeros((2, 3, 3))
    n[0] = [0, -1, 0]                 # ngửa lên (OpenCV: lên = -y) → sàn
    n[1] = [0, 0, -1]                 # tường nhìn về camera → không phải sàn
    n[0, 2] = [0, 0.96, 0.28]         # trần (úp xuống) → không phải sàn
    valid = np.ones((2, 3), bool)
    valid[0, 1] = False
    assert floor_mask_from_normals(n, valid).tolist() == [[True, False, False], [False, False, False]]
