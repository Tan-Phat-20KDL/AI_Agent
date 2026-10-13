"""Chạy thẳng class node ComfyUI (không cần cài ComfyUI) để chắc workflow W1/W2/W3 hoạt động."""

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("trimesh")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fa_env(tmp_path, monkeypatch, data_dir):
    import trimesh

    from core.assets import normalize_asset

    root = tmp_path / "fa"
    shutil.copytree(data_dir, root / "data")
    for rel, dims in (("assets/TB01/BLK.glb", (1600, 900, 750)), ("assets/CH01/BRN.glb", (450, 520, 820)),
                      ("assets/SF01/GRY.glb", (2100, 900, 850))):
        raw = tmp_path / "raw.glb"
        trimesh.creation.box(extents=[1, 1, 1]).export(str(raw))
        normalize_asset(raw, root / rel, dims)
    monkeypatch.setenv("FA_ROOT", str(root))
    monkeypatch.delenv("FA_DATA", raising=False)
    monkeypatch.delenv("FA_RUNTIME", raising=False)
    import comfy_nodes
    return root, comfy_nodes


def _run_api(nodes_mod, wf: dict) -> dict:
    """Mô phỏng ComfyUI chạy workflow API: giải tham chiếu ["id", output_index]."""
    results: dict[str, tuple] = {}
    for nid in sorted(wf, key=int):
        spec = wf[nid]
        inputs = {k: results[v[0]][v[1]] if isinstance(v, list) else v for k, v in spec["inputs"].items()}
        cls = nodes_mod.NODE_CLASS_MAPPINGS[spec["class_type"]]
        results[nid] = getattr(cls(), cls.FUNCTION)(**inputs)
    return results


def test_w1_then_w2(fa_env):
    root, nodes = fa_env
    w1 = json.loads((ROOT / "workflows/api/w1_form.json").read_text(encoding="utf-8"))
    r1 = _run_api(nodes, w1)
    assert r1["1"] == ("s_001", 1)
    assert Path(r1["2"][0]).exists()
    assert r1["3"][1] == 30_030_000

    w2 = json.loads((ROOT / "workflows/api/w2_edit_chair.json").read_text(encoding="utf-8"))
    r2 = _run_api(nodes, w2)
    assert r2["1"] == ("s_001", 2)
    v1 = json.loads((root / "runtime/scenes/s_001/v1.json").read_text(encoding="utf-8"))
    v2 = json.loads((root / "runtime/scenes/s_001/v2.json").read_text(encoding="utf-8"))
    assert v2["objects"][0] == v1["objects"][0] and v2["objects"][2] == v1["objects"][2]
    assert v2["objects"][1]["variant_id"] == "CH01-GRN"


def test_more_chairs_rearranges_only_chairs(fa_env):
    root, nodes = fa_env
    _run_api(nodes, json.loads((ROOT / "workflows/api/w1_form.json").read_text(encoding="utf-8")))
    sid, ver = nodes.FA_EditScene().run("s_001", 1, "chair_1",
                                        '[{"op": "replace", "path": "/objects/1/qty", "value": 6}]',
                                        True, False, "thêm 2 ghế")
    s = json.loads((root / f"runtime/scenes/s_001/v{ver}.json").read_text(encoding="utf-8"))
    v1 = json.loads((root / "runtime/scenes/s_001/v1.json").read_text(encoding="utf-8"))
    assert len(s["objects"][1]["instances"]) == 6
    assert s["objects"][0] == v1["objects"][0]   # bàn không đổi
    assert s["objects"][2] == v1["objects"][2]   # sofa không đổi


def test_color_change_keeps_chair_positions(fa_env):
    root, nodes = fa_env
    _run_api(nodes, json.loads((ROOT / "workflows/api/w1_form.json").read_text(encoding="utf-8")))
    _, ver = nodes.FA_EditScene().run("s_001", 1, "chair_1",
                                      '[{"op": "replace", "path": "/objects/1/variant_id", "value": "CH01-GRN"}]',
                                      False, False, "")
    s = json.loads((root / f"runtime/scenes/s_001/v{ver}.json").read_text(encoding="utf-8"))
    v1 = json.loads((root / "runtime/scenes/s_001/v1.json").read_text(encoding="utf-8"))
    assert s["objects"][1]["instances"] == v1["objects"][1]["instances"]


def test_bigger_variant_is_replaced_not_overlapping(fa_env):
    """Đổi ghế sang mẫu to hơn: ghế phải được xếp lại để không đè bàn; bàn và sofa giữ nguyên."""
    from core.placement import find_collisions
    from core.repository import load_catalog

    root, nodes = fa_env
    data = root / "data"
    with (data / "products.csv").open("a", encoding="utf-8") as fh:
        fh.write("CH02,Ghế bành Lounge,ghe_an,hien_dai,700,700,800,\n")
    with (data / "variants.csv").open("a", encoding="utf-8") as fh:
        fh.write("CH02-RED,CH02,Đỏ,,3900000,,assets/CH01/BRN.glb,approved,#AA3333\n")
    _run_api(nodes, json.loads((ROOT / "workflows/api/w1_form.json").read_text(encoding="utf-8")))
    _, ver = nodes.FA_EditScene().run("s_001", 1, "chair_1",
                                      '[{"op": "replace", "path": "/objects/1/variant_id", "value": "CH02-RED"}]',
                                      False, False, "")
    s = json.loads((root / f"runtime/scenes/s_001/v{ver}.json").read_text(encoding="utf-8"))
    v1 = json.loads((root / "runtime/scenes/s_001/v1.json").read_text(encoding="utf-8"))
    assert ver == 2                                   # đúng 1 version mới, không có version dở dang
    assert not find_collisions(s, load_catalog(data))
    assert s["objects"][0] == v1["objects"][0] and s["objects"][2] == v1["objects"][2]


def test_register_asset_sets_pending(fa_env, tmp_path):
    import trimesh

    root, nodes = fa_env
    raw = tmp_path / "trellis_out.glb"
    trimesh.creation.box(extents=[2, 1, 1.1]).export(str(raw))
    rel, report = nodes.FA_RegisterAsset().run("TB01-WAL", str(raw), "fit")
    assert (root / rel).exists()
    from core.repository import load_catalog

    v = load_catalog(root / "data").variant("TB01-WAL")
    assert (v.asset_glb, v.asset_status) == (rel, "pending")  # chờ người duyệt (FR-04)
    assert json.loads(report)["warnings"] == []
