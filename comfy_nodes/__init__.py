"""Custom node ComfyUI cho furniture-ai — lớp vỏ mỏng gọi core/ (xem CONTRIBUTING.md).

Phần 2D (ghép bàn ghế vào ảnh phòng, lát gỗ lên sàn) dùng node có sẵn của ComfyUI + Qwen-Image-Edit
+ SAM 3 — xem workflows/README.md. Hai node dưới đây lo phần 3D:

- FA · Chuẩn hoá 3D   : GLB từ TRELLIS.2 → đúng kích thước thật (mét), gốc ở tâm đáy
- FA · Dựng cảnh 3D   : phòng + 1 bàn + N ghế + vật liệu sàn/tường → scene.glb cho viewer three.js

Cài: symlink thư mục này vào ComfyUI/custom_nodes/furniture_ai (infra/runpod/bootstrap.sh làm sẵn).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.assets import normalize_asset  # noqa: E402
from core.config import root, runtime_dir  # noqa: E402
from core.scene3d import build_scene, table_chairs_spec  # noqa: E402

CATEGORY = "furniture-ai"
_DIM = {"min": 100, "max": 30000, "step": 10}


class FA_NormalizeAsset:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "src_glb": ("STRING", {"default": ""}),
            "name": ("STRING", {"default": "table"}),
            "width_mm": ("INT", {"default": 1600, **_DIM}),
            "depth_mm": ("INT", {"default": 900, **_DIM}),
            "height_mm": ("INT", {"default": 750, **_DIM}),
            "mode": (["fit", "uniform"],),
        }}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("glb_path", "report")
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, src_glb, name, width_mm, depth_mm, height_mm, mode):
        dst = runtime_dir() / "assets" / f"{name}.glb"
        rep = normalize_asset(src_glb, dst, (width_mm, depth_mm, height_mm), mode=mode)
        return (str(dst), json.dumps(rep.__dict__, ensure_ascii=False))


class FA_Scene3D:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "scene_id": ("STRING", {"default": "demo"}),
                "room_width_mm": ("INT", {"default": 4200, **_DIM}),
                "room_depth_mm": ("INT", {"default": 3600, **_DIM}),
                "room_height_mm": ("INT", {"default": 2800, **_DIM}),
                "table_glb": ("STRING", {"default": ""}),
                "table_w_d_h_mm": ("STRING", {"default": "1600,900,750"}),
                "chair_glb": ("STRING", {"default": ""}),
                "chair_w_d_h_mm": ("STRING", {"default": "450,520,820"}),
                "chair_qty": ("INT", {"default": 4, "min": 0, "max": 12}),
            },
            "optional": {
                "texture_path": ("STRING", {"default": ""}),
                "texture_on": (["floor", "wall_back", "wall_left", "wall_right"],),
                "tile_w_l_mm": ("STRING", {"default": "1200,200"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("glb_path",)
    FUNCTION = "run"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, scene_id, room_width_mm, room_depth_mm, room_height_mm, table_glb, table_w_d_h_mm,
            chair_glb, chair_w_d_h_mm, chair_qty, texture_path="", texture_on="floor", tile_w_l_mm="1200,200"):
        spec = table_chairs_spec(scene_id, (room_width_mm, room_depth_mm, room_height_mm), table_glb,
                          _ints(table_w_d_h_mm), chair_glb, _ints(chair_w_d_h_mm), chair_qty,
                          texture_path, texture_on, _ints(tile_w_l_mm))
        out = runtime_dir() / "out" / scene_id / "scene.glb"
        build_scene(spec, root(), out)
        return (str(out),)


def _ints(text: str) -> list[int]:
    return [int(x) for x in str(text).replace("x", ",").split(",") if x.strip()]


NODE_CLASS_MAPPINGS = {"FA_NormalizeAsset": FA_NormalizeAsset, "FA_Scene3D": FA_Scene3D}
NODE_DISPLAY_NAME_MAPPINGS = {"FA_NormalizeAsset": "FA · Chuẩn hoá 3D", "FA_Scene3D": "FA · Dựng cảnh 3D"}
