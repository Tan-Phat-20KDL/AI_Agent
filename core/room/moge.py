"""Đo kích thước phòng từ 1 ảnh bằng MoGe-2 (MIT) — chỉ chạy được trên máy có GPU + torch + moge.

    pip install git+https://github.com/microsoft/MoGe.git
Cách gọi theo README MoGe: MoGeModel.from_pretrained("Ruicheng/moge-2-vitl-normal"), model.infer(tensor (3,H,W) 0..1).
Laptop không có torch/moge → MeasureUnavailable (UI hiện thông báo, không crash).
"""

from __future__ import annotations

from pathlib import Path

from .geometry import RoomEstimate, estimate_room, floor_mask_from_normals

_MODEL = None
MODEL_ID = "Ruicheng/moge-2-vitl-normal"


class MeasureUnavailable(RuntimeError):
    pass


def _load():
    global _MODEL
    if _MODEL is None:
        try:
            import torch
            from moge.model.v2 import MoGeModel
        except ImportError as e:
            raise MeasureUnavailable(f"Thiếu {e.name} — đo phòng cần GPU + MoGe-2 (chạy trên Colab/RunPod)") from None
        if not torch.cuda.is_available():
            raise MeasureUnavailable("Không có GPU CUDA — đo phòng bằng MoGe-2 cần GPU")
        _MODEL = MoGeModel.from_pretrained(MODEL_ID).to("cuda").eval()
    return _MODEL


def measure_room(image_path: str | Path, known_height_mm: int | None = None, max_side: int = 1600) -> RoomEstimate:
    """Ảnh phòng → kích thước (mm). known_height_mm (chiều cao trần đo tay) để hiệu chỉnh tỉ lệ."""
    import cv2
    import torch

    model = _load()
    img = cv2.cvtColor(cv2.imread(str(image_path)), cv2.COLOR_BGR2RGB)
    s = max_side / max(img.shape[:2])
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    x = torch.tensor(img / 255, dtype=torch.float32, device="cuda").permute(2, 0, 1)
    with torch.no_grad():
        out = model.infer(x)
    pts = out["points"].cpu().numpy()
    floor = floor_mask_from_normals(out["normal"].cpu().numpy(), out["mask"].cpu().numpy().astype(bool))
    est = estimate_room(pts, floor)
    if known_height_mm:
        est = estimate_room(pts, floor, calibration=(est.height_mm, known_height_mm))
    return est
