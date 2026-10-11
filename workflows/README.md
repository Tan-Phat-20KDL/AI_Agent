# Workflow ComfyUI

| File | Việc | GPU | Trạng thái |
| --- | --- | --- | --- |
| `api/w1_form.json` | W1: tạo scene từ form → đặt đồ → `scene.glb` → báo giá | Không | Chạy được (node FA) |
| `api/w2_edit_chair.json` | W2: chỉ đổi ghế sang xanh, giữ bàn/sofa | Không | Chạy được (node FA) |
| `i1_ingest_sku` | I1: ảnh SKU → BiRefNet → TRELLIS.2 → Simplify → `FA · I1 Đăng ký asset 3D` | Có | **Dựng trong UI ở Phase 0** |
| `room_a` | Ảnh phòng → MoGe-2 + SAM 3 → `core.room.estimate_room` → kích thước phòng cho W1 | Có | **Dựng trong UI ở Phase 0** |

Gửi workflow API từ script: `core.comfy_client.ComfyClient().run(json, timeout_s=...)`, hoặc đo hiệu năng:
`python bench/bench_workflow.py workflows/api/w1_form.json --runs 3`.

Vì sao I1 và room_a chưa có file: tên class node của ComfyUI-Trellis2 / wrapper SAM 3 / MoGe-2
chỉ biết chắc sau khi cài trên máy GPU. Dựng trong UI → *Workflow → Export (API)* → lưu vào `api/`
→ ghi commit node vào `infra/models.lock`.
