# AI_Agent — ghép bàn ghế / vật liệu vào ảnh phòng (2D + xem 3D)

Đầu vào **1–3 ảnh**: ảnh phòng + ảnh bàn + ảnh ghế (hoặc ảnh gạch/thanh gỗ).
Đầu ra: **ảnh 2D** căn phòng đã ghép 1 bàn + 4 ghế / đã lát vật liệu, và **cảnh 3D** xem bằng three.js.
ComfyUI là giao diện vận hành. Thử trước trên Colab T4 miễn phí ([notebook](notebooks/colab_phase0_t4.ipynb)), sau đó RunPod card 24 GB.

Tài liệu: [SRS](docs/SRS.md) · [SPEC (nghiên cứu model, license, giá)](docs/SPEC.md) ·
[Cài trên RunPod](docs/runpod-setup.md) · [Workflow](workflows/README.md) · [Quy ước code](CONTRIBUTING.md)

## Trạng thái

| Phần | Trạng thái |
| --- | --- |
| Ghép 2D (Qwen-Image-Edit-2511) và lát vật liệu 2D (SAM 3 + Qwen-Image-Edit) | Phase 0 — dựng workflow trên pod |
| Ảnh bàn/ghế → 3D (TRELLIS.2) | Phase 0 |
| Chuẩn hoá GLB đúng kích thước, đặt 4 ghế quanh bàn, lát vật liệu 3D, viewer | ✔ có test, chạy trên laptop |
| Ước lượng kích thước phòng từ point map MoGe-2 | ✔ phần hình học; nối model ở Phase 0 |
| Script cài/tự dừng pod, benchmark | Viết sẵn, chạy thử ở Phase 0 |

## Web (three.js) — chạy ngay trên laptop

```powershell
.\.venv\Scripts\python tools\serve.py
# mở http://localhost:8765/web/
```

Nhập kích thước phòng/bàn/ghế, tải ảnh gạch–thanh gỗ để lát sàn (đúng kích thước 1 viên), ảnh phòng thật dán lên tường
sau, ảnh sản phẩm để lấy màu, hoặc file `.glb` (từ TRELLIS.2) để thay khối mẫu. Bàn tự đặt giữa phòng, ghế xếp quanh;
kéo thả để di chuyển, phím R / nút ⟳ để xoay 90°. *Xuất cấu hình* ra JSON cùng dạng spec với `core/scene3d.py`.
Code: `web/js/` — `stage.js` (cảnh + phòng), `furniture.js` (bàn/ghế), `layout.js` (xếp đồ), `textures.js`, `main.js` (form).

## Chạy thử trên laptop (không cần GPU)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install numpy trimesh pytest
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python tools\demo_local.py
.\.venv\Scripts\python tools/serve.py
# mở http://localhost:8765/viewer/?scene=runtime/out/demo/scene.glb
```

## Cấu trúc

```text
core/            Python thuần (numpy, trimesh)
  assets/        chuẩn hoá GLB về kích thước thật
  placement/     đặt bàn giữa phòng, ghế quanh bàn, kiểm va chạm
  room/          hộp phòng, ước lượng từ point map MoGe-2
  scene3d.py     spec → scene.glb + meta (vật liệu sàn/tường)
  comfy_client.py, joblog.py, io.py, config.py
comfy_nodes/     node ComfyUI: Chuẩn hoá 3D, Dựng cảnh 3D
web/             web app three.js (giao diện chính)
viewer/          xem nhanh scene.glb do pipeline Python xuất ra
workflows/       hướng dẫn workflow A/B/C trong ComfyUI
infra/, bench/   cài đặt pod, benchmark Phase 0
notebooks/       Colab T4: test miễn phí trước khi thuê GPU
tools/           demo_local.py
```

## Nhánh git

| Nhánh | Dùng cho |
| --- | --- |
| `develop` | Code hằng ngày |
| `staging` | Bản chốt để demo — gộp từ `develop` qua Pull Request |
| `main` | Bản ổn định — gộp từ `staging` qua Pull Request |
| `archive/full-scope` | Bản phạm vi đầy đủ cũ (CSV, báo giá, version/sửa cục bộ) — cất để dùng lại |
