import json

import pytest

pytest.importorskip("trimesh")

from core.design import Design, Item, build_design  # noqa: E402
from core.placement import PlacementError  # noqa: E402


def _design(**kw):
    base = dict(room_mm=(4200, 3600, 2800), table=Item((1600, 900, 750), color="#202020"),
                chair=Item((450, 520, 820), color="#7a5232"), chair_qty=4)
    base.update(kw)
    return Design(**base)


def test_build_without_uploads_uses_placeholders(tmp_path):
    meta = build_design(_design(), tmp_path, tmp_path / "runtime" / "r1")
    assert meta["scene"] == "runtime/r1/scene.glb"
    assert len(meta["nodes"]) == 5 and meta["warnings"] == []
    assert meta["surfaces"]["floor"]["texture"] == "runtime/r1/texture.png"
    saved = json.loads((tmp_path / "runtime/r1/scene.meta.json").read_text(encoding="utf-8"))
    assert saved["nodes"] == meta["nodes"]


def test_uploaded_texture_and_wall_surface(tmp_path):
    from core.assets.placeholder import wood_texture, write_png

    up = write_png(tmp_path / "upload.png", wood_texture(64, 16))
    meta = build_design(_design(texture=str(up), tile_mm=(600, 600), surface="wall_back"), tmp_path, tmp_path / "r2")
    assert meta["surfaces"] == {"wall_back": {"texture": "r2/texture.png", "tile_mm": [600, 600]}}


def test_uploaded_glb_wrong_proportion_warns(tmp_path):
    import trimesh

    glb = tmp_path / "chair_ai.glb"
    trimesh.creation.box(extents=[1, 1, 1]).export(str(glb))
    meta = build_design(_design(chair=Item((450, 520, 820), glb=str(glb))), tmp_path, tmp_path / "r3")
    assert any(w.startswith("chair:") for w in meta["warnings"])


def test_room_too_small(tmp_path):
    with pytest.raises(PlacementError):
        build_design(_design(room_mm=(1500, 1500, 2700)), tmp_path, tmp_path / "r4")
