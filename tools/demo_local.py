"""Chạy thử toàn luồng W1 → W2 → W3 trên laptop, KHÔNG cần GPU.

Asset 3D thật do TRELLIS.2 sinh trên GPU; ở đây tạo tạm hình khối đúng kích thước CSV
để kiểm tra scene graph, giữ context, đặt đồ, xuất GLB, báo giá và viewer.

    python tools/demo_local.py
    python -m http.server 8080      # rồi mở http://localhost:8080/viewer/?scene=runtime/out/s_demo/v2/scene.glb
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from core.assets import normalize_asset  # noqa: E402
from core.placement import place_missing  # noqa: E402
from core.quote import compute_quote, save_quote  # noqa: E402
from core.repository import load_catalog  # noqa: E402
from core.scene import EditScope, SceneStore, new_scene  # noqa: E402
from core.scene.assemble import assemble_scene  # noqa: E402

RUNTIME = ROOT / "runtime"


def _part(extents, center, color):
    m = trimesh.creation.box(extents=extents)
    m.apply_translation(center)
    m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=np.tile(color, (len(m.vertices), 1)))
    return m


def placeholder_mesh(category: str, color) -> trimesh.Trimesh:
    """Hình khối thô theo loại đồ (đơn vị tuỳ ý, normalize_asset sẽ scale đúng CSV)."""
    if category == "ban_an":
        parts = [_part([1.6, 0.04, 0.9], [0, 0.73, 0], color)]
        parts += [_part([0.05, 0.71, 0.05], [x, 0.355, z], color) for x in (-0.75, 0.75) for z in (-0.4, 0.4)]
    elif category == "ghe_an":
        parts = [_part([0.45, 0.04, 0.45], [0, 0.45, 0.035], color),
                 _part([0.45, 0.4, 0.04], [0, 0.66, -0.2], color)]  # lưng ghế ở phía sau (-z)
        parts += [_part([0.035, 0.43, 0.035], [x, 0.215, z], color) for x in (-0.2, 0.2) for z in (-0.2, 0.24)]
    elif category == "sofa":
        parts = [_part([2.1, 0.42, 0.9], [0, 0.21, 0], color),
                 _part([2.1, 0.43, 0.2], [0, 0.635, -0.35], color)]
    else:
        parts = [_part([1, 1, 1], [0, 0.5, 0], color)]
    return trimesh.util.concatenate(parts)


def make_placeholder_assets(catalog) -> None:
    colors = {"TB01-BLK": [40, 40, 40, 255], "CH01-BRN": [120, 80, 50, 255], "SF01-GRY": [150, 150, 155, 255]}
    tmp = RUNTIME / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for v in catalog.usable_variants():
        dst = ROOT / v.asset_glb
        if dst.exists():
            continue
        p = catalog.product(v.sku)
        raw = tmp / f"{v.variant_id}_raw.glb"
        placeholder_mesh(p.category, colors.get(v.variant_id, [200, 200, 200, 255])).export(str(raw))
        rep = normalize_asset(raw, dst, (p.width_mm, p.depth_mm, p.height_mm), mode="uniform")
        print(f"  asset tạm {v.asset_glb}: {rep.final_extents_m}")


def main() -> None:
    for sub in ("scenes", "quotes", "out"):
        shutil.rmtree(RUNTIME / sub, ignore_errors=True)
    cat = load_catalog(ROOT / "data")
    print("1) Tạo asset tạm cho biến thể đã duyệt")
    make_placeholder_assets(cat)

    store = SceneStore(RUNTIME / "scenes", cat)
    print("2) W1: bàn đen + 4 ghế nâu + sofa sát tường")
    s = new_scene("s_demo", 4200, 3600, 2800)
    s["objects"] = [
        {"id": "table_1", "variant_id": "TB01-BLK", "qty": 1, "placement": "center", "instances": []},
        {"id": "chair_1", "variant_id": "CH01-BRN", "qty": 4, "placement": "around:table_1", "instances": []},
        {"id": "sofa_1", "variant_id": "SF01-GRY", "qty": 1, "placement": "against_wall", "instances": []},
    ]
    v1 = store.create(place_missing(s, cat), note="W1")

    print("3) W2: chỉ đổi ghế sang xanh rêu — bàn, sofa, số ghế, vị trí giữ nguyên")
    v2 = store.commit("s_demo", 1, [{"op": "replace", "path": "/objects/1/variant_id", "value": "CH01-GRN"}],
                      EditScope.of("chair_1"), note="đổi màu ghế")
    assert v2["objects"][0] == v1["objects"][0] and v2["objects"][2] == v1["objects"][2]

    print("4) Thử sửa vượt phạm vi (đổi cả bàn) → phải bị chặn")
    try:
        store.commit("s_demo", 2, [{"op": "replace", "path": "/objects/0/qty", "value": 2}],
                     EditScope.of("chair_1"))
        raise SystemExit("LỖI: validator không chặn")
    except ValueError as e:
        print("   bị chặn đúng:", str(e).splitlines()[1].strip())

    for sc in (v1, v2):
        out = RUNTIME / "out" / "s_demo" / f"v{sc['version']}" / "scene.glb"
        assemble_scene(sc, cat, ROOT, out)
        q = compute_quote(sc, cat)
        save_quote(q, RUNTIME / "quotes")
        print(f"5) v{sc['version']}: {out.relative_to(ROOT)}  |  tổng báo giá {q.total_vnd:,} VND")

    print("\nXem 3D:  python -m http.server 8080")
    print("         http://localhost:8080/viewer/?scene=runtime/out/s_demo/v2/scene.glb")


if __name__ == "__main__":
    main()
