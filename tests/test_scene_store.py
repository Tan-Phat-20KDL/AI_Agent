"""Kịch bản giữ context trong yêu cầu gốc: bàn đen + 4 ghế nâu → chỉ đổi ghế."""

import hashlib
import json

import pytest

from core.placement import place_missing
from core.scene import EditScope, SceneError, SceneStore, ScopeViolation, StaleVersionError


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


@pytest.fixture
def store(tmp_path, catalog, dining_scene):
    s = SceneStore(tmp_path / "scenes", catalog)
    s.create(place_missing(dining_scene, catalog), note="W1")
    return s


def test_change_only_chairs_keeps_table(store):
    v1 = store.load("s_demo")
    table_hash = _h(v1["objects"][0])
    v2 = store.commit("s_demo", 1, [
        {"op": "replace", "path": "/objects/1/variant_id", "value": "CH01-GRN"},
    ], EditScope.of("chair_1"), note="đổi ghế sang xanh")
    assert v2["version"] == 2 and v2["parent_version"] == 1
    assert _h(v2["objects"][0]) == table_hash          # bàn giữ nguyên tuyệt đối
    assert v2["objects"][1]["qty"] == 4                # số ghế không đổi
    assert v2["objects"][1]["instances"] == v1["objects"][1]["instances"]  # vị trí ghế giữ nguyên


def test_patch_touching_table_is_rejected(store):
    with pytest.raises(ScopeViolation) as e:
        store.commit("s_demo", 1, [
            {"op": "replace", "path": "/objects/1/variant_id", "value": "CH01-GRN"},
            {"op": "replace", "path": "/objects/0/variant_id", "value": "TB01-WAL"},
        ], EditScope.of("chair_1"))
    assert "table_1" in str(e.value)
    assert store.versions("s_demo") == [1]  # không ghi gì


def test_qty_change_needs_permission(store):
    patch = [{"op": "replace", "path": "/objects/1/qty", "value": 6}]
    with pytest.raises(ScopeViolation):
        store.commit("s_demo", 1, patch, EditScope.of("chair_1"))
    v2 = store.commit("s_demo", 1, patch, EditScope.of("chair_1", allow_qty=True))
    assert v2["objects"][1]["qty"] == 6


def test_reorder_trick_is_caught(store):
    """Patch xoá bàn rồi thêm lại bàn khác ở cùng id vẫn bị chặn (kiểm tra theo kết quả)."""
    v1 = store.load("s_demo")
    fake = dict(v1["objects"][0], variant_id="TB01-WAL")
    with pytest.raises(ScopeViolation):
        store.commit("s_demo", 1, [{"op": "remove", "path": "/objects/0"},
                                   {"op": "add", "path": "/objects/0", "value": fake}],
                     EditScope.of("chair_1"))


def test_unapproved_variant_rejected(store):
    with pytest.raises(SceneError):
        store.commit("s_demo", 1, [{"op": "replace", "path": "/objects/0/variant_id", "value": "TB01-WAL"}],
                     EditScope.of("table_1"))


def test_stale_version_and_revert(store):
    store.commit("s_demo", 1, [{"op": "replace", "path": "/objects/1/variant_id", "value": "CH01-GRN"}],
                 EditScope.of("chair_1"))
    with pytest.raises(StaleVersionError):
        store.commit("s_demo", 1, [], EditScope.of())
    v3 = store.revert("s_demo", 1)
    assert v3["version"] == 3 and v3["objects"][1]["variant_id"] == "CH01-BRN"
    assert store.versions("s_demo") == [1, 2, 3]  # lịch sử không mất
