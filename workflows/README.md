# Workflow ComfyUI

Phạm vi: đầu vào **1–3 ảnh** — ảnh phòng, ảnh bàn, ảnh ghế (hoặc ảnh gạch/thanh gỗ) → ảnh 2D đã ghép + cảnh 3D.

| Workflow | Đầu vào | Đầu ra | Model | Trạng thái |
| --- | --- | --- | --- | --- |
| **A. Ghép bàn ghế (2D)** | ảnh phòng + ảnh bàn + ảnh ghế | ảnh phòng có 1 bàn + 4 ghế | Qwen-Image-Edit-2511 (FP8 + LoRA Lightning 4 bước) | Dựng trong UI ở Phase 0 |
| **B. Lát vật liệu (2D)** | ảnh phòng + ảnh gạch/gỗ | ảnh phòng có sàn/tường mới | SAM 3 (mask "floor"/"wall") + Qwen-Image-Edit-2511 + ghép theo mask | Dựng trong UI ở Phase 0 |
| **C. Cảnh 3D** | ảnh bàn, ảnh ghế, (ảnh gỗ), kích thước phòng | `scene.glb` + viewer three.js | BiRefNet → TRELLIS.2 → `FA · Chuẩn hoá 3D` → `FA · Dựng cảnh 3D` | Node FA xong; TRELLIS.2 dựng ở Phase 0 |

## A. Ghép bàn ghế vào ảnh phòng

1. 3 node *Load Image*: phòng, bàn, ghế.
2. Qwen-Image-Edit-2511 nhận cả 3 ảnh (model card: tốt nhất với 1–3 ảnh đầu vào). Câu lệnh ví dụ:
   *"Place this dining table in the center of the room and arrange 4 of these chairs around it, keep the room unchanged, realistic lighting and shadows."*
3. Lưu ảnh.

**Chưa kiểm chứng — phải thử với ảnh thật:** model giữ đúng mẫu bàn/ghế không, có ra đúng **4** ghế không,
phần phòng có bị đổi không. Model card chỉ nêu các tổ hợp người+sản phẩm, người+cảnh, không nói rõ sản phẩm+phòng.
Nếu phòng bị đổi: thêm bước B3 (ghép theo mask) để giữ nguyên pixel ngoài vùng đặt đồ.

## B. Lát gạch / thanh gỗ lên sàn hoặc tường

1. *Load Image*: phòng, ảnh vật liệu.
2. SAM 3 với prompt chữ `floor` (hoặc `wall`) → mask.
3. Qwen-Image-Edit-2511: ảnh phòng + ảnh vật liệu, câu lệnh *"Replace the floor with this wood plank flooring, keep everything else unchanged"*.
4. Ghép theo mask (node ghép ảnh có mask của ComfyUI) → **ngoài sàn giữ nguyên từng pixel**.

## C. Cảnh 3D

1. Ảnh bàn → BiRefNet tách nền → TRELLIS.2 → GLB → `FA · Chuẩn hoá 3D` (nhập kích thước thật mm).
2. Lặp lại cho ghế.
3. `FA · Dựng cảnh 3D`: kích thước phòng, 2 GLB, số ghế, (ảnh gỗ + kích thước 1 thanh, mặt cần lát).
4. Xem: `http://localhost:8080/viewer/?scene=runtime/out/<scene_id>/scene.glb` (qua SSH tunnel).

Kích thước phòng: nhập tay, hoặc ước lượng từ ảnh bằng MoGe-2 + `core.room.estimate_room` (đã có code, chưa nối node).

## Lưu workflow

Dựng xong trong UI → *Workflow → Export (API)* → lưu vào `workflows/api/<tên>.json` → chạy lại / đo bằng
`python bench/bench_workflow.py workflows/api/<tên>.json --runs 3`. Tên class node của Qwen/SAM 3/TRELLIS.2
chỉ biết chắc sau khi cài trên pod — không đoán trước.
