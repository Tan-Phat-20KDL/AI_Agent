# furniture-ai — Core AI đặt sản phẩm nội thất vào phòng 3D + báo giá

Core của hệ thống AI Agent: lấy **sản phẩm có sẵn** (ảnh 2D → 3D, hoặc file 3D có sẵn), đặt vào
**phòng dựng từ ảnh của khách**, xuất **cảnh 3D xem bằng three.js** kèm **báo giá tự động** từ CSV.
Sửa cục bộ (vd chỉ đổi ghế) không làm đổi phần còn lại của cảnh. ComfyUI là giao diện vận hành.

Tài liệu: [SRS](docs/SRS.md) · [SPEC kỹ thuật](docs/SPEC.md) · [Cài demo trên RunPod](docs/runpod-setup.md) ·
[AWS cho bản production](docs/aws-setup.md)

## Trạng thái

| Phần | Trạng thái | Chạy ở đâu |
| --- | --- | --- |
| CSV làm database + kiểm lỗi theo dòng/cột (FR-01, FR-04) | Xong, có test | Laptop |
| Scene graph + JSON Patch + chặn sửa vượt phạm vi + version/undo (FR-11, FR-12) | Xong, có test | Laptop |
| Đặt đồ tự động: giữa phòng, sát tường, ghế quanh bàn; không va chạm (FR-09) | Xong, có test | Laptop |
| Báo giá từ CSV, xuất JSON + CSV cho Excel (FR-13) | Xong, có test | Laptop |
| Chuẩn hoá asset GLB theo kích thước CSV, tô màu biến thể (FR-02/03/05) | Xong, có test | Laptop |
| Ước lượng hộp phòng từ point map MoGe-2 (FR-06) | Xong phần hình học, test bằng dữ liệu giả lập | Laptop |
| Xuất `scene.glb` + viewer three.js, chụp PNG (FR-10, FR-14) | Xong | Laptop |
| Custom node ComfyUI (W1, W2, W3, undo, đăng ký asset) | Xong, test không cần ComfyUI | Laptop / GPU |
| Workflow GPU: ảnh SKU → TRELLIS.2 (I1), ảnh phòng → MoGe-2 + SAM 3 | **Chưa** — dựng trong UI ở Phase 0 | GPU |
| Benchmark Phase 0, script cài đặt + tự dừng pod | Viết sẵn, **chưa chạy** trên GPU | GPU |

## Chạy thử trên laptop (không cần GPU)

Chỉ cần Python ≥ 3.10 và 3 thư viện nhẹ (numpy, trimesh, pytest).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q                 # 37 test
.\.venv\Scripts\python tools\demo_local.py          # W1 → W2 → báo giá, đồ 3D là khối tạm
.\.venv\Scripts\python -m http.server 8080
# mở http://localhost:8080/viewer/?scene=runtime/out/s_demo/v2/scene.glb
```

`demo_local.py` tạo bàn đen + 4 ghế nâu + sofa, rồi **chỉ đổi ghế sang xanh**: bàn, sofa, số ghế và
vị trí giữ nguyên; thử sửa lén cả bàn thì bị chặn. Đồ 3D trong demo là khối hộp đúng kích thước
CSV — trên GPU sẽ thay bằng mesh TRELLIS.2.

## Cấu trúc

```text
core/            Python thuần, không import ComfyUI
  repository/    đọc/ghi CSV (sau đổi PostgreSQL chỉ sửa ở đây)
  scene/         scene graph, JSON Patch, scope validator, store version, assemble scene.glb
  placement/     đặt đồ lên sàn, kiểm va chạm
  room/          hộp phòng từ point map MoGe-2
  assets/        chuẩn hoá GLB, tô màu
  quote/         báo giá
  comfy_client.py, joblog.py   gọi ComfyUI có timeout; log job + VRAM đỉnh
comfy_nodes/     custom node ComfyUI (lớp vỏ gọi core/)
workflows/api/   workflow ComfyUI dạng API JSON
viewer/          three.js viewer
data/            CSV mẫu (giá minh hoạ)
infra/           runpod/ (demo), aws/ (production), models.lock, download_models.sh
bench/           benchmark Phase 0 (chạy trên GPU)
tools/           demo_local.py
tests/           pytest
docs/            SRS, SPEC, hướng dẫn RunPod/AWS
```

## Đưa lên GitHub

Tạo repo **trống** trên GitHub (không tick README/.gitignore), rồi chạy trong thư mục này:

```powershell
git init -b main
git add .
git commit -m "Core furniture-ai: CSV, scene graph, đặt đồ, báo giá, viewer, infra RunPod"
git remote add origin https://github.com/<tài-khoản>/<tên-repo>.git
git push -u origin main
```

`.gitignore` đã loại `.venv/`, `runtime/`, `assets/`, model và ảnh phòng khách; `.gitattributes`
giữ xuống dòng LF cho file `.sh` để chạy được trên Linux.
