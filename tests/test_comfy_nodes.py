"""Gọi thẳng class node ComfyUI (không cần cài ComfyUI)."""

import json

import pytest

pytest.importorskip("trimesh")


@pytest.fixture
def nodes(monkeypatch, assets_root):
    monkeypatch.setenv("FA_ROOT", str(assets_root))
    monkeypatch.delenv("FA_RUNTIME", raising=False)
    import comfy_nodes
    return comfy_nodes


def test_scene3d_node(nodes, assets_root):
    (glb,) = nodes.FA_Scene3D().run("demo", 4200, 3600, 2800, "assets/table.glb", "1600,900,750",
                                    "assets/chair.glb", "450x520x820", 4,
                                    texture_path="inputs/wood.png", texture_on="floor", tile_w_l_mm="1200,200")
    meta = json.loads((assets_root / "runtime/out/demo/scene.meta.json").read_text(encoding="utf-8"))
    assert glb.endswith("scene.glb") and len(meta["nodes"]) == 5
    assert meta["surfaces"]["floor"]["texture"] == "inputs/wood.png"


def test_normalize_node(nodes, assets_root, tmp_path):
    import trimesh

    raw = tmp_path / "trellis_out.glb"
    # cùng tỉ lệ 1600 × 750 × 900 (x, y, z) nhưng đơn vị tuỳ ý, như output của TRELLIS.2
    trimesh.creation.box(extents=[3.2, 1.5, 1.8]).export(str(raw))
    path, report = nodes.FA_NormalizeAsset().run(str(raw), "table2", 1600, 900, 750, "fit")
    assert path.endswith("table2.glb") and json.loads(report)["warnings"] == []
