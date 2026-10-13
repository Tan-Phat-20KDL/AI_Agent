import pytest

from core.placement import PlacementError, find_collisions, place_missing


def test_four_chairs_around_table(dining_spec):
    s = place_missing(dining_spec)
    table = s["objects"][0]["instances"][0]
    chairs = s["objects"][1]["instances"]
    assert len(chairs) == 4 and not find_collisions(s)
    south = [c for c in chairs if c["position_mm"][1] > table["position_mm"][1]]
    north = [c for c in chairs if c["position_mm"][1] < table["position_mm"][1]]
    assert len(south) == 2 and len(north) == 2            # 2 ghế mỗi cạnh dài
    assert {c["rotation_deg"] for c in south} == {180}    # quay mặt vào bàn
    assert {c["rotation_deg"] for c in north} == {0}


def test_input_not_mutated_and_existing_positions_kept(dining_spec):
    s1 = place_missing(dining_spec)
    assert dining_spec["objects"][0]["instances"] == []
    s1["objects"][1]["qty"] = 6
    s2 = place_missing(s1)
    assert s2["objects"][0]["instances"] == s1["objects"][0]["instances"]
    assert len(s2["objects"][1]["instances"]) == 6 and not find_collisions(s2)


def test_reset_rearranges_only_that_object(dining_spec):
    s1 = place_missing(dining_spec)
    s1["objects"][1]["dims_mm"] = [700, 700, 800]   # đổi sang ghế to hơn
    assert "chair" in find_collisions(s1)
    s2 = place_missing(s1, reset_ids={"chair"})
    assert not find_collisions(s2)
    assert s2["objects"][0] == s1["objects"][0]      # bàn không dời


def test_too_small_room_and_missing_dims(dining_spec):
    small = dict(dining_spec, room={"width_mm": 1500, "depth_mm": 1500, "height_mm": 2700})
    with pytest.raises(PlacementError, match="Không đủ chỗ"):
        place_missing(small)
    del dining_spec["objects"][0]["dims_mm"]
    with pytest.raises(PlacementError, match="dims_mm"):
        place_missing(dining_spec)
