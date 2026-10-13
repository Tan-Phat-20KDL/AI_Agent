"""Custom node ComfyUI cho furniture-ai — chỉ là lớp vỏ gọi core/ (SRS NFR-11).

Cài: tạo symlink thư mục này vào ComfyUI/custom_nodes/furniture_ai
(script infra/runpod/bootstrap.sh làm sẵn). Thư mục gốc dự án lấy từ biến môi trường
FA_ROOT (mặc định: thư mục cha của file này).

Kiểu dữ liệu truyền giữa node là STRING (đường dẫn / JSON) để workflow dễ đọc và
export ra API JSON gọi từ script/web sau này.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.config import data_dir as _data_dir  # noqa: E402
from core.config import root as _root  # noqa: E402
from core.config import runtime_dir as _runtime  # noqa: E402
from core.placement import place_missing  # noqa: E402
from core.quote import compute_quote, save_quote  # noqa: E402
from core.repository import load_catalog, set_variant_asset  # noqa: E402
from core.scene import EditScope, SceneStore, new_scene  # noqa: E402
from core.scene.assemble import assemble_scene  # noqa: E402
from core.workflows import plan_edit  # noqa: E402

CATEGORY = "furniture-ai"


def _store():
    cat = load_catalog(_data_dir())
    return cat, SceneStore(_runtime() / "scenes", cat)


def _parse_items(text: str) -> list[dict]:
    """Form nhập sản phẩm, mỗi dòng: <object_id> <variant_id> <số lượng> [placement]
    vd:  table_1 TB01-BLK 1 center
         chair_1 CH01-BRN 4 around:table_1
    """
    objs = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 3:
            raise ValueError(f"Dòng {n}: cần '<object_id> <variant_id> <số lượng> [placement]'")
        oid, vid, qty = parts[0], parts[1], int(parts[2])
        objs.append({"id": oid, "variant_id": vid, "qty": qty,
                     "placement": parts[3] if len(parts) > 3 else "center", "instances": []})
    return objs


class FA_NewScene:
    """W1: tạo scene v1 từ form (không cần LLM), tự đặt đồ."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_id": ("STRING", {"default": "s_001"}),
            "room_width_mm": ("INT", {"default": 4200, "min": 1000, "max": 30000}),
            "room_depth_mm": ("INT", {"default": 3600, "min": 1000, "max": 30000}),
            "room_height_mm": ("INT", {"default": 2800, "min": 2000, "max": 6000}),
            "items": ("STRING", {"multiline": True,
                                 "default": "table_1 TB01-BLK 1 center\nchair_1 CH01-BRN 4 around:table_1"}),
        }}

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("scene_id", "version")
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, scene_id, room_width_mm, room_depth_mm, room_height_mm, items):
        cat, store = _store()
        s = new_scene(scene_id, room_width_mm, room_depth_mm, room_height_mm)
        s["objects"] = _parse_items(items)
        s = store.create(place_missing(s, cat), note="W1 tạo mới")
        return (scene_id, s["version"])


class FA_EditScene:
    """W2: sửa cục bộ bằng JSON Patch; chỉ object trong 'targets' được đổi."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "scene_id": ("STRING", {"default": "s_001"}),
            "base_version": ("INT", {"default": 1, "min": 1}),
            "targets": ("STRING", {"default": "chair_1"}),
            "patch_json": ("STRING", {"multiline": True, "default":
                '[{"op": "replace", "path": "/objects/1/variant_id", "value": "CH01-GRN"}]'}),
            "allow_qty": ("BOOLEAN", {"default": False}),
            "allow_add_remove": ("BOOLEAN", {"default": False}),
            "note": ("STRING", {"default": ""}),
        }}

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("scene_id", "version")
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, scene_id, base_version, targets, patch_json, allow_qty, allow_add_remove, note):
        cat, store = _store()
        scope = EditScope.of(*[t.strip() for t in targets.split(",") if t.strip()],
                             allow_qty=allow_qty, allow_add=allow_add_remove, allow_remove=allow_add_remove)
        s = store.commit_scene(scene_id, base_version,
                               plan_edit(store.load(scene_id, base_version), json.loads(patch_json), scope, cat),
                               scope, note=note or "W2 sửa")
        return (scene_id, s["version"])


class FA_RevertScene:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"scene_id": ("STRING", {"default": "s_001"}),
                             "to_version": ("INT", {"default": 1, "min": 1})}}

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("scene_id", "version")
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, scene_id, to_version):
        _, store = _store()
        s = store.revert(scene_id, to_version)
        return (scene_id, s["version"])


class FA_AssembleScene:
    """Xuất scene.glb + meta cho three.js viewer."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"scene_id": ("STRING", {"default": "s_001"}),
                             "version": ("INT", {"default": 1, "min": 1})}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("glb_path",)
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, scene_id, version):
        cat, store = _store()
        s = store.load(scene_id, version)
        out = _runtime() / "out" / scene_id / f"v{version}" / "scene.glb"
        assemble_scene(s, cat, _root(), out)
        return (str(out),)


class FA_Quote:
    """W3: báo giá từ CSV, lưu JSON + CSV."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"scene_id": ("STRING", {"default": "s_001"}),
                             "version": ("INT", {"default": 1, "min": 1})}}

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("quote_csv_path", "total_vnd")
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, scene_id, version):
        cat, store = _store()
        q = compute_quote(store.load(scene_id, version), cat)
        _, csv_path = save_quote(q, _runtime() / "quotes")
        return (str(csv_path), q.total_vnd)


class FA_RegisterAsset:
    """I1 bước cuối: chuẩn hoá GLB (từ TRELLIS.2 hoặc file 3D có sẵn) và ghi vào variants.csv."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "variant_id": ("STRING", {"default": "TB01-WAL"}),
            "src_glb": ("STRING", {"default": ""}),
            "mode": (["fit", "uniform"],),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("asset_glb", "report")
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, variant_id, src_glb, mode):
        from core.assets import normalize_asset

        cat = load_catalog(_data_dir())
        v = cat.variant(variant_id)
        p = cat.product(v.sku)
        rel = f"assets/{p.sku}/{variant_id}.glb"
        rep = normalize_asset(src_glb, _root() / rel, (p.width_mm, p.depth_mm, p.height_mm), mode=mode)
        # luôn về 'pending' — người duyệt mới chuyển sang 'approved' (FR-04)
        set_variant_asset(_data_dir(), variant_id, asset_glb=rel, asset_status="pending")
        return (rel, json.dumps(rep.__dict__, ensure_ascii=False))


NODE_CLASS_MAPPINGS = {
    "FA_NewScene": FA_NewScene,
    "FA_EditScene": FA_EditScene,
    "FA_RevertScene": FA_RevertScene,
    "FA_AssembleScene": FA_AssembleScene,
    "FA_Quote": FA_Quote,
    "FA_RegisterAsset": FA_RegisterAsset,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FA_NewScene": "FA · W1 Tạo thiết kế (form)",
    "FA_EditScene": "FA · W2 Sửa cục bộ (JSON Patch)",
    "FA_RevertScene": "FA · Undo về version",
    "FA_AssembleScene": "FA · Xuất scene.glb",
    "FA_Quote": "FA · W3 Báo giá",
    "FA_RegisterAsset": "FA · I1 Đăng ký asset 3D",
}
