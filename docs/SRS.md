# SRS – Ghép bàn ghế / vật liệu vào ảnh phòng (2D + xem 3D)

Phiên bản 0.3 · 13/10/2026. **Thu hẹp phạm vi** so với 0.2: bỏ CSV, báo giá, quản lý version/sửa cục bộ,
LLM. Bản đầy đủ cũ nằm ở nhánh git `archive/full-scope`.

## 1. Phạm vi

**Đầu vào: 1–3 ảnh.**

| Việc | Ảnh vào | Ra |
| --- | --- | --- |
| A. Ghép đồ | ảnh phòng + ảnh 1 bàn + ảnh 1 ghế | ảnh phòng có 1 bàn + 4 ghế (2D) + cảnh 3D xoay được |
| B. Lát vật liệu | ảnh phòng + ảnh gạch/thanh gỗ | ảnh phòng có sàn hoặc tường lát vật liệu đó (2D) + cảnh 3D |

**Ngoài phạm vi (giai đoạn này):** báo giá, nhiều loại đồ, sửa nhiều lượt có lịch sử, nhập yêu cầu bằng tiếng Việt,
web app khách hàng, dựng phòng từ video.

## 2. Ràng buộc

- C-1 Chỉ model cho phép thương mại: Qwen-Image-Edit-2511 (Apache-2.0), SAM 3 (SAM License), TRELLIS.2 (MIT),
  BiRefNet (MIT), MoGe-2 (MIT). Nguồn và license: [SPEC.md](SPEC.md).
- C-2 Phần cứng theo bậc, rẻ trước: **0a Colab T4 miễn phí** (notebook `notebooks/colab_phase0_t4.ipynb`) →
  **0b RunPod card 24 GB** cho Qwen-Image-Edit + TRELLIS bản 1 (≥ 16 GB) → chỉ lên A6000 48 GB nếu cần TRELLIS.2 (≥ 24 GB, sát giới hạn 24 GB).

## 3. Yêu cầu chức năng

| ID | Yêu cầu | Ưu tiên | Nghiệm thu (đề xuất, chốt sau Phase 0) | Trạng thái |
| --- | --- | --- | --- | --- |
| FR-1 | A-2D: ghép 1 bàn + 4 ghế từ 2 ảnh sản phẩm vào ảnh phòng | Must | Đúng 4 ghế, giữ đúng mẫu bàn/ghế, phòng không bị đổi — designer chấm đạt ≥ 70% bộ test | Phase 0 |
| FR-2 | B-2D: lát vật liệu lên sàn hoặc tường | Must | Chỉ vùng sàn/tường thay đổi (ghép theo mask), vân vật liệu giống ảnh vào | Phase 0 |
| FR-3 | Ảnh bàn/ghế → GLB đúng kích thước thật | Must | bbox lệch ≤ 1% so với kích thước nhập | Chuẩn hoá ✔ · TRELLIS.2: Phase 0 |
| FR-4 | Dựng cảnh 3D: phòng + 1 bàn + N ghế quanh bàn, không chồng/không xuyên tường | Must | 0 va chạm | ✔ `core/placement`, `core/scene3d` |
| FR-5 | Lát ảnh vật liệu lên sàn/tường trong 3D, đúng kích thước 1 viên/thanh | Must | 1 lần lặp texture = `tile_mm` | ✔ viewer |
| FR-6 | Viewer three.js: xoay, bấm chọn đồ, chụp PNG ≥ 1920 px | Must | Mở được trên Chrome | ✔ |
| FR-7 | Kích thước phòng: nhập tay hoặc ước lượng từ ảnh (MoGe-2 + SAM 3) | Should | Sai số ≤ 5% sau hiệu chỉnh 1 kích thước | Hình học ✔ · nối model: Phase 0 |

## 4. Phi chức năng

| ID | Yêu cầu |
| --- | --- |
| NFR-1 | VRAM đỉnh ≤ 80% (`bench/bench_workflow.py`) |
| NFR-2 | Mỗi workflow có timeout; hết giờ → `/interrupt` (`core/comfy_client.py`) |
| NFR-3 | ComfyUI chỉ nghe 127.0.0.1, truy cập qua SSH tunnel |
| NFR-4 | Pod tự dừng sau 30 phút GPU rảnh (`infra/runpod/idle_stop.sh`, cần kiểm chứng runpodctl) |
| NFR-5 | Code theo [CONTRIBUTING.md](../CONTRIBUTING.md); CI chạy test mỗi push |

## 5. Phase 0 (việc tiếp theo, trên pod)

0. **Colab T4 (miễn phí):** chạy notebook — test code, MoGe-2 đo phòng từ ảnh thật, dựng cảnh 3D. Ghi VRAM đỉnh.
1. **RunPod 24 GB:** cài ComfyUI + Qwen-Image-Edit-2511 FP8 + SAM 3 + BiRefNet + TRELLIS (bản 1; bản 2 nếu đủ VRAM).
2. Thử FR-1 và FR-2 với **ảnh thật của bạn** (5–10 bộ). Đây là rủi ro lớn nhất: chưa biết model ghép đúng 4 ghế
   và giữ đúng mẫu không. Không đạt → cân nhắc ghép từ cảnh 3D (render 3D rồi làm thật bằng Qwen-Image-Edit).
3. Thử FR-3 (TRELLIS.2) với ảnh bàn/ghế thật.
4. Đo VRAM, thời gian, ghi vào tài liệu.

## 6. Tự phản biện

| Điểm yếu | Giảm thiểu |
| --- | --- |
| Ghép 2D bằng model sinh ảnh có thể đổi mẫu ghế, sai số lượng, đổi phòng | Thử thật trước; ghép theo mask; phương án dự phòng là render từ cảnh 3D |
| Ảnh 2D và cảnh 3D tạo độc lập nên vị trí đồ có thể không khớp nhau | Chấp nhận cho demo; nếu cần khớp: ảnh 2D render từ chính cảnh 3D |
| Cảnh 3D là hộp phòng, kém thật hơn ảnh gốc | Giới hạn góc xoay; ảnh 2D vẫn là kết quả chính để xem |
| `runpodctl` trong pod chưa kiểm chứng | Xem log lần đầu, Stop tay nếu không chạy |
