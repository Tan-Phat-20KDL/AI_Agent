import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")

from core.assets import normalize_asset  # noqa: E402
from core.placement import place_missing  # noqa: E402
from core.room import estimate_room, fit_plane_ransac  # noqa: E402
from core.scene.assemble import assemble_scene  # noqa: E402


def test_ransac_recovers_plane_with_outliers():
    rng = np.random.default_rng(1)
    xy = rng.uniform(-2, 2, size=(800, 2))
    plane = np.c_[xy[:, 0], np.full(800, 1.4), xy[:, 1]] + rng.normal(0, 0.003, (800, 3))
    junk = rng.uniform(-2, 2, size=(200, 3))
    n, d, mask = fit_plane_ransac(np.vstack([plane, junk]))
    assert abs(abs(n[1]) - 1) < 1e-2
    assert abs(abs(d) - 1.4) < 1e-2
    assert mask[:800].mean() > 0.95


def _synthetic_room(W=4.0, D=3.0, H=2.7, cam_h=1.4, tilt_deg=15):
    """Phòng W×D×H, camera cao cam_h ở giữa mép trước, nhìn chúc xuống tilt_deg (toạ độ OpenCV)."""
    rng = np.random.default_rng(0)
    floor = np.c_[rng.uniform(0, W, 3000), np.zeros(3000), rng.uniform(0, D, 3000)]
    back = np.c_[rng.uniform(0, W, 1500), rng.uniform(0, H, 1500), np.full(1500, D)]
    pts_room = np.vstack([floor, back])
    cam = np.array([W / 2, cam_h, -0.5])
    p = pts_room - cam
    # room (x phải, y lên, z tới) → camera OpenCV (x phải, y xuống, z tới), rồi chúc xuống
    p = p * np.array([1, -1, 1])
    t = np.radians(tilt_deg)
    rx = np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]])
    p = p @ rx.T
    mask = np.r_[np.ones(3000, bool), np.zeros(1500, bool)]
    return p, mask


def test_estimate_room_dimensions():
    pts, floor_mask = _synthetic_room()
    est = estimate_room(pts, floor_mask)
    assert abs(est.camera_height_mm - 1400) < 30
    assert abs(est.width_mm - 4000) / 4000 < 0.06
    assert abs(est.depth_mm - 3000) / 3000 < 0.06
    assert abs(est.height_mm - 2700) / 2700 < 0.06


def test_calibration_scales_everything():
    pts, floor_mask = _synthetic_room()
    est = estimate_room(pts * 0.8, floor_mask)  # mô hình đo nhỏ hơn thật 20%
    fixed = estimate_room(pts * 0.8, floor_mask, calibration=(est.camera_height_mm, 1400))
    assert abs(fixed.camera_height_mm - 1400) <= 2
    assert abs(fixed.width_mm - 4000) / 4000 < 0.06


def _box_glb(path, extents):
    trimesh.creation.box(extents=extents).export(str(path))


def test_normalize_asset_matches_csv_dims(tmp_path):
    src = tmp_path / "raw.glb"
    _box_glb(src, [1.0, 0.5, 0.6])  # đầu ra AI: tỉ lệ đúng, đơn vị tuỳ ý
    rep = normalize_asset(src, tmp_path / "out.glb", (1600, 900, 750))
    assert rep.within((1600, 900, 750))
    lo, hi = trimesh.load(str(tmp_path / "out.glb"), force="scene").bounds
    assert abs(lo[1]) < 1e-6                         # đáy chạm sàn
    assert abs(lo[0] + hi[0]) < 1e-6 and abs(lo[2] + hi[2]) < 1e-6  # tâm x, z ở gốc


def test_normalize_warns_on_bad_proportions(tmp_path):
    src = tmp_path / "raw.glb"
    _box_glb(src, [1.0, 1.0, 1.0])
    rep = normalize_asset(src, tmp_path / "out.glb", (1600, 900, 750))
    assert rep.warnings


def test_assemble_scene_nodes(tmp_path, catalog, dining_scene):
    assets = tmp_path / "assets"
    for rel, dims in (("TB01/BLK.glb", (1600, 900, 750)), ("CH01/BRN.glb", (450, 520, 820))):
        raw = tmp_path / "raw.glb"
        _box_glb(raw, [1, 1, 1])
        normalize_asset(raw, assets / rel, dims)
    s = place_missing(dining_scene, catalog)
    s["objects"][1]["variant_id"] = "CH01-GRN"  # biến thể tô màu, dùng chung GLB
    meta = assemble_scene(s, catalog, tmp_path, tmp_path / "out" / "scene.glb")
    assert set(meta["nodes"]) == {"table_1#0", "chair_1#0", "chair_1#1", "chair_1#2", "chair_1#3"}
    assert meta["nodes"]["chair_1#0"]["tinted"] is True
    loaded = trimesh.load(str(tmp_path / "out" / "scene.glb"), force="scene")
    names = set(loaded.graph.nodes)
    assert {"table_1#0", "chair_1#3"} <= names
    # bàn đặt đúng vị trí (mm → m)
    tf, _ = loaded.graph.get("table_1#0")
    x, z = s["objects"][0]["instances"][0]["position_mm"]
    assert np.allclose(tf[[0, 2], 3], [x / 1000, z / 1000], atol=1e-6)
