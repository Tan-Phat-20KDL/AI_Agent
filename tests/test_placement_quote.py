import json

import pytest

from core.placement import PlacementError, instance_rects, place_missing
from core.quote import compute_quote, save_quote


def _no_collisions(scene, catalog, gap=50):
    rects = [r for _, _, r in instance_rects(scene, catalog)]
    W, D = scene["room"]["width_mm"], scene["room"]["depth_mm"]
    for i, a in enumerate(rects):
        assert a.inside(W, D), a
        for b in rects[i + 1:]:
            assert not a.overlaps(b, gap - 1), (a, b)


def test_chairs_around_table(catalog, dining_scene):
    s = place_missing(dining_scene, catalog)
    table = s["objects"][0]["instances"][0]
    chairs = s["objects"][1]["instances"]
    assert len(chairs) == 4
    _no_collisions(s, catalog)
    # 2 ghế mỗi cạnh dài, quay mặt vào bàn
    south = [c for c in chairs if c["position_mm"][1] > table["position_mm"][1]]
    north = [c for c in chairs if c["position_mm"][1] < table["position_mm"][1]]
    assert len(south) == 2 and len(north) == 2
    assert {c["rotation_deg"] for c in south} == {180}
    assert {c["rotation_deg"] for c in north} == {0}


def test_existing_positions_never_move(catalog, dining_scene):
    s1 = place_missing(dining_scene, catalog)
    s1["objects"][1]["qty"] = 6
    s2 = place_missing(s1, catalog)
    assert s2["objects"][0]["instances"] == s1["objects"][0]["instances"]
    assert s2["objects"][1]["instances"][:4] == s1["objects"][1]["instances"]
    assert len(s2["objects"][1]["instances"]) == 6
    _no_collisions(s2, catalog)


def test_against_wall_and_too_small_room(catalog, dining_scene):
    dining_scene["objects"].append(
        {"id": "sofa_1", "variant_id": "SF01-GRY", "qty": 1, "placement": "against_wall", "instances": []})
    s = place_missing(dining_scene, catalog)
    sofa = s["objects"][2]["instances"][0]
    (x, z), rot = sofa["position_mm"], sofa["rotation_deg"]
    W, D, half = 4200, 3600, 900 // 2  # sofa sâu 900 mm, cách tường 20 mm
    # sát 1 bức tường và quay mặt vào phòng
    assert (z, rot) == (20 + half, 0) or (x, rot) == (20 + half, 90) or \
           (x, rot) == (W - 20 - half, 270) or (z, rot) == (D - 20 - half, 180)
    _no_collisions(s, catalog)

    dining_scene["room"] = {"width_mm": 1500, "depth_mm": 1500, "height_mm": 2700}
    with pytest.raises(PlacementError):
        place_missing(dining_scene, catalog)


def test_quote_matches_hand_calculation(tmp_path, catalog, dining_scene):
    s = place_missing(dining_scene, catalog)
    s["version"] = 1
    q = compute_quote(s, catalog)
    # tính tay: 6.900.000 + 4 × 1.850.000 = 14.300.000; +500.000 vận chuyển = 14.800.000; VAT 10% = 1.480.000
    assert q.subtotal_vnd == 14_300_000
    assert q.vat_vnd == 1_480_000
    assert q.total_vnd == 16_280_000
    j, c = save_quote(q, tmp_path / "quotes")
    assert json.loads(j.read_text(encoding="utf-8"))["total_vnd"] == 16_280_000
    assert c.read_bytes().startswith(b"\xef\xbb\xbf")  # BOM cho Excel


def test_custom_item_goes_to_manual(catalog, dining_scene):
    dining_scene["objects"].append({"id": "cabinet_x", "custom": True, "qty": 1, "dims_mm": [800, 400, 900],
                                    "placement": "against_wall", "instances": []})
    q = compute_quote(dining_scene, catalog)
    assert q.manual_items == ["cabinet_x"]
