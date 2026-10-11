# SRS – AI Agent đặt sản phẩm nội thất vào phòng 3D + báo giá

Phiên bản 0.2 · 11/10/2026 · cấu trúc theo tinh thần ISO/IEC/IEEE 29148.
Thay đổi so với 0.1: demo chạy trên **RunPod L40S Community** (thay AWS); **bộ model rút gọn** cho P1;
nhập sản phẩm bằng **form** là bắt buộc, LLM tiếng Việt chuyển thành tuỳ chọn.

## 1. Giới thiệu

### 1.1 Mục đích
Đặc tả yêu cầu cho **core AI**: đưa sản phẩm nội thất có sẵn vào phòng của khách dưới dạng cảnh 3D
xem trong three.js, kèm báo giá tự động. Độc giả: kỹ sư triển khai, người kiểm thử, người duyệt phía công ty.

### 1.2 Phạm vi

| Ưu tiên | Phạm vi |
| --- | --- |
| **P1 – làm trước** | Sản phẩm có sẵn: ảnh 2D → 3D, hoặc file 3D có sẵn → chuẩn hoá. Đặt vào phòng dựng từ ảnh khách. Xem 3D trong three.js. Báo giá từ CSV. Sửa cục bộ không đổi phần còn lại |
| P2 – sau | Hàng đặt (custom): mô tả → ảnh 2D (Qwen-Image) → 3D; báo giá tay/template; LLM tiếng Việt |
| P3 – sau nữa | Dựng phòng từ video (splat), web app khách hàng, thanh toán |
| Ngoài phạm vi | VR, đăng nhập khách hàng, tích hợp ERP |

SRS là chuẩn cho cả công ty; bản triển khai đầu là **demo** chạy đúng luồng với cấu hình rẻ (mục 7).

### 1.3 Thuật ngữ

| Thuật ngữ | Nghĩa |
| --- | --- |
| SKU / biến thể | Mã sản phẩm có sẵn / một màu-vật liệu cụ thể của SKU (`variant_id`) |
| Asset 3D | GLB đã chuẩn hoá của 1 biến thể: Y-up, mét, gốc ở tâm đáy, bbox khớp CSV |
| Scene graph | JSON mô tả phòng + object (id, biến thể, số lượng, vị trí) — nguồn sự thật duy nhất |
| Scene version | Mỗi lần sửa tạo version mới `v<N>.json`, không ghi đè |
| JSON Patch | Thay đổi nhỏ trên scene graph theo RFC 6902 |
| EditScope | Danh sách object được phép sửa trong 1 lần sửa (+ cờ cho phép đổi số lượng/thêm/xoá) |
| Chế độ A | Dựng hộp phòng 3D từ 1 ảnh |
| I1 / W1 / W2 / W3 | Nạp asset SKU / tạo thiết kế / sửa / báo giá lại |

### 1.4 Tài liệu tham chiếu
[SPEC kỹ thuật](SPEC.md) (bằng chứng license, giá) · [runpod-setup.md](runpod-setup.md) · [aws-setup.md](aws-setup.md)

## 2. Mô tả tổng quan

### 2.1 Bối cảnh
Với sản phẩm có sẵn, bước tốn GPU nhất (2D → 3D) chạy **một lần cho mỗi biến thể** rồi lưu vào thư viện
asset; mỗi yêu cầu của khách chỉ còn dựng phòng, đặt đồ, tính giá.

1. **Offline – I1:** ảnh SKU → BiRefNet tách nền → TRELLIS.2 → giảm lưới → `FA · I1 Đăng ký asset 3D`
   (chuẩn hoá theo CSV, `asset_status=pending`) → người duyệt chuyển `approved`. SKU có file 3D sẵn: bỏ qua AI.
2. **Online – W1/W2/W3:** ảnh phòng → MoGe-2 + SAM 3 → kích thước hộp phòng → form chọn biến thể + số lượng
   → scene graph → đặt đồ tự động → `scene.glb` → three.js + báo giá.

### 2.2 Người dùng

| Vai trò | Làm gì | Giai đoạn |
| --- | --- | --- |
| Tư vấn / designer | Nhập ảnh phòng + chọn sản phẩm, sửa, xuất báo giá qua ComfyUI | Demo |
| Quản trị dữ liệu | Cập nhật CSV, chạy I1, duyệt asset | Demo |
| Kỹ sư | Triển khai, bật/tắt pod, theo dõi lỗi | Demo |
| Khách hàng | Tự thao tác trên web | P3 |

### 2.3 Ràng buộc
- **C-1** Chỉ model có license cho phép thương mại (SPEC mục 3). Cấm FLUX.1 dev/Kontext dev, Qwen-Image-2.1,
  Apple SHARP, SpatialLM, Depth Anything V2 Base/Large, RMBG-1.4.
- **C-2** Database giai đoạn đầu là **CSV** (mục 4), chỉ truy cập qua `core/repository`.
- **C-3** Demo: RunPod L40S 48 GB (Community), Linux. Production: AWS (aws-setup.md).
- **C-4** ComfyUI là giao diện vận hành của core trong demo.
- **C-5** Giá tiền không bao giờ do LLM tính.

### 2.4 Giả định & phụ thuộc

| ID | Giả định | Nếu sai |
| --- | --- | --- |
| A-1 | Mỗi biến thể có ≥ 1 ảnh rõ, nền đơn giản, góc 3/4, ≥ 1024 px | Mesh xấu → chụp lại hoặc dựng tay |
| A-2 | CSV có kích thước thật (mm) và giá của mọi SKU | Không scale đúng, không báo giá được |
| A-3 | Biến thể màu có ảnh riêng; nếu không, tô lại màu (gần đúng) | Màu lệch thực tế |
| A-4 | Ảnh phòng thấy sàn và ≥ 1 tường | Không dựng được hộp phòng |
| D-1 | RunPod còn L40S Community khi cần | Chờ, hoặc chuyển Secure Cloud |

## 3. Yêu cầu chức năng

Ngưỡng số là **đề xuất**, chốt lại sau Phase 0. Cột "Code" cho biết phần đã có trong repo.

| ID | Yêu cầu | Ưu tiên | Nghiệm thu | Code |
| --- | --- | --- | --- | --- |
| FR-01 | Nạp CSV, kiểm schema + tham chiếu chéo | Must | Lỗi báo đúng file/dòng/cột; không nạp nửa chừng | `core/repository` ✔ |
| FR-02 | I1: ảnh → GLB (tách nền → TRELLIS.2 → giảm lưới → scale theo CSV) | Must | Mở được trong three.js; bbox lệch ≤ 1%; ≤ 100k tam giác | chuẩn hoá ✔ · TRELLIS.2: Phase 0 |
| FR-03 | Nhập file 3D có sẵn (GLB/glTF/OBJ; FBX qua Blender) → chuẩn hoá | Must | Như FR-02 | `core/assets` ✔ |
| FR-04 | Chỉ asset `approved` dùng được cho khách | Must | Biến thể pending/rejected không ra trong tìm kiếm, scene bị từ chối | ✔ |
| FR-05 | Biến thể màu: GLB riêng nếu có ảnh; không thì tô `tint_hex` | Should | Nhãn "màu minh hoạ" | ✔ |
| FR-06 | Dựng hộp phòng từ 1 ảnh; nhập 1 kích thước thật để hiệu chỉnh | Must | Sai số kích thước sau hiệu chỉnh ≤ 5% trên bộ T2 | hình học ✔ · MoGe/SAM: Phase 0 |
| FR-07 | Xoá đồ cũ khỏi ảnh phòng (Qwen-Image-Edit) | Should | Designer chấp nhận ≥ 70% ảnh T2 | Phase 0 |
| FR-08a | Form chọn biến thể + số lượng + kiểu đặt (center / against_wall / around:<id>) | Must | Chỉ biến thể có trong CSV và đã duyệt | `FA_NewScene` ✔ |
| FR-08b | LLM đọc yêu cầu tiếng Việt → chọn SKU / sinh JSON Patch | Should (P2) | ≥ 90% đúng trên 50 câu T3; không chắc thì hỏi lại | — |
| FR-09 | Đặt đồ tự động: không chồng, không xuyên tường; ghế xếp quanh bàn quay mặt vào bàn | Must | 0 va chạm trên bộ test | `core/placement` ✔ |
| FR-10 | Xuất `scene.glb` + viewer three.js (PBR, bóng, giới hạn góc xoay, bấm xem SKU/giá) | Must | Mở được trên Chrome desktop | ✔ |
| FR-11 | Sửa cục bộ bằng JSON Patch + EditScope | Must | Object ngoài phạm vi giữ nguyên 100% case T4 | ✔ |
| FR-12 | Version + undo | Must | Quay lại version bất kỳ, lịch sử không mất | ✔ |
| FR-13 | Báo giá từ CSV, snapshot đơn giá, xuất JSON + CSV | Must | Khớp tính tay 100% bộ T5 | ✔ |
| FR-14 | Chụp PNG ≥ 1920 px từ viewer | Should | — | ✔ |
| FR-15 | Báo giá PDF | Should | — | — |
| FR-16 | Log mỗi job: thời gian từng bước, VRAM đỉnh, lỗi | Must | 100% job có log, kể cả job lỗi | `core/joblog` ✔ |
| FR-17 | Hàng đặt → cờ `custom`, báo giá tay | Could (P2) | Không tự tính giá | ✔ (cờ + loại khỏi báo giá) |
| FR-18 | Render đồ từ đúng camera ảnh gốc, ghép lên ảnh thật kèm bóng | Should | Designer chấp nhận ≥ 70% ảnh T2 | — |

**Quy tắc đổi số lượng (FR-09 + FR-11):** khi người dùng đổi số lượng của một món (vd 4 → 6 ghế), chỉ món đó
được xếp lại toàn bộ; mọi món khác giữ nguyên vị trí. Khi chỉ đổi màu/biến thể, vị trí giữ nguyên.

## 4. Yêu cầu dữ liệu (CSV làm database)

Thư mục `data/`: UTF-8 (chấp nhận BOM của Excel), dấu phẩy, dòng đầu là tên cột, tiền là số nguyên VND,
kích thước mm, nhiều giá trị trong một ô ngăn bằng `;`.

| File | Cột | Dùng cho |
| --- | --- | --- |
| `products.csv` | sku, name, category, style_tags, width_mm, depth_mm, height_mm, description | Tìm SKU, scale asset, đặt đồ |
| `variants.csv` | variant_id, sku, color_name, material_id, price_vnd, image_paths, asset_glb, asset_status, tint_hex | Giá bán, asset, duyệt, đổi màu |
| `materials.csv` | material_id, name, group, unit, unit_price_vnd, pbr_texture_dir | Mô tả vật liệu; hàng đặt (P2) |
| `pricing_rules.csv` | key, value, note (`vat_pct` bắt buộc; discount_pct, delivery_fee_vnd, install_pct) | Tham số báo giá |
| `labor_rates.csv` | process, unit, unit_price_vnd | Hàng đặt (P2) |
| `runtime/scenes/<id>/v<N>.json` | Scene graph từng version | FR-11, FR-12 |
| `runtime/quotes/<id>/v<N>.json/.csv` | Báo giá + snapshot đơn giá | FR-13 |

Công thức báo giá P1:

```
Tổng = [Σ price_k × qty_k × (1 − discount) + delivery + install] × (1 + vat)
install = install_pct × (tổng hàng sau chiết khấu)
```

Chuyển sang PostgreSQL khi có > 1 người sửa CSV cùng lúc hoặc web app cần ghi dữ liệu.

## 5. Giao diện

### 5.1 Node ComfyUI (`comfy_nodes/`)

| Node | Input | Output | GPU |
| --- | --- | --- | --- |
| FA · W1 Tạo thiết kế (form) | scene_id, kích thước phòng, danh sách `<id> <variant> <SL> [placement]` | scene v1 | Không |
| FA · W2 Sửa cục bộ | scene_id, base_version, targets, patch JSON, allow_qty, allow_add_remove | scene vN+1 | Không |
| FA · Undo về version | scene_id, to_version | version mới | Không |
| FA · Xuất scene.glb | scene_id, version | đường dẫn GLB + meta | Không |
| FA · W3 Báo giá | scene_id, version | CSV báo giá, tổng VND | Không |
| FA · I1 Đăng ký asset 3D | variant_id, GLB nguồn (từ TRELLIS.2 hoặc file sẵn) | asset chuẩn hoá, pending | Không (GPU ở bước TRELLIS.2 trước đó) |

### 5.2 API
Script/web gọi server ComfyUI: `POST /prompt`, `GET /history/<id>`, `GET /queue`, `POST /interrupt`,
`POST /upload/image` (`core/comfy_client.py`). ComfyUI chỉ nghe `127.0.0.1`, truy cập qua SSH tunnel.

### 5.3 Định dạng file
GLB Y-up mét (node `<object_id>#<i>`, mesh dùng chung giữa các instance) + `scene.meta.json`; scene graph JSON
có `schema_version`; báo giá JSON + CSV có BOM; log job JSON lines.

## 6. Yêu cầu phi chức năng

| ID | Yêu cầu | Đo |
| --- | --- | --- |
| NFR-01 | VRAM đỉnh ≤ 80% tổng VRAM do `nvidia-smi` báo | `bench/bench_workflow.py` |
| NFR-02 | Mỗi workflow có timeout = 3 × p95 Phase 0; hết giờ → `/interrupt`, báo lỗi | `ComfyClient.wait` |
| NFR-03 | 1 job/GPU tại một thời điểm, còn lại xếp hàng | Gửi 5 job cùng lúc |
| NFR-04 | Ghi file atomic; kill giữa chừng không hỏng scene/CSV | `core/io.py` |
| NFR-05 | W2 với asset có sẵn ≤ 60 s; W1 (asset có sẵn) ≤ 5 phút (đề xuất) | Log FR-16 |
| NFR-06 | `scene.glb` ≤ 30 MB, mở ≤ 10 s ở 50 Mbps (đề xuất) | Chrome |
| NFR-07 | GPU chỉ chạy khi dùng; tự dừng sau 30 phút rảnh | `idle_stop.sh` |
| NFR-08 | Không mở cổng HTTP public; truy cập qua SSH tunnel | Pod không có HTTP port |
| NFR-09 | Ảnh phòng khách lưu tối đa 90 ngày (đề xuất), xoá khi khách yêu cầu | Script xoá theo scene_id |
| NFR-10 | Ghim version model + custom node | `infra/models.lock` |
| NFR-11 | Logic nghiệp vụ trong `core/`, có unit test; node chỉ là lớp vỏ | `pytest` |
| NFR-12 | Dựng lại pod mới từ script ≤ 1 giờ (không tính tải model) | Chạy thử trên pod mới |

## 7. Triển khai demo

1 pod **RunPod L40S 48 GB Community**, template Runpod PyTorch, volume disk 80 GB tại `/workspace`, bật khi cần.
Chi tiết, rủi ro và các bước: [runpod-setup.md](runpod-setup.md).

| Mức dùng | USD/tuần | USD/tháng |
| --- | --- | --- |
| 1 giờ/ngày | ≤ 9.72 | ≤ 41.70 |
| 3 giờ/ngày | ≤ 20.78 | ≤ 89.10 |

Bộ model rút gọn cho P1 (~35–45 GB, ước tính): TRELLIS.2, BiRefNet, MoGe-2, SAM 3, tuỳ chọn Qwen-Image-Edit FP8.
Không nạp Qwen-Image (chỉ cần cho hàng đặt) và LLM (thay bằng form).

## 8. Nghiệm thu & kiểm thử

Demo nghiệm thu khi mọi FR mức Must và NFR-01–04, 08 đạt trên bộ test do công ty cung cấp:

| Bộ | Nội dung | Dùng cho |
| --- | --- | --- |
| T1 | 20 SKU: 10 chỉ có ảnh, 5 có file 3D, 5 có biến thể màu | FR-01–05 |
| T2 | 20 ảnh phòng (khách/ăn/ngủ, sáng/tối), mỗi ảnh 1 kích thước đo tay | FR-06, 07, 09, 10, 18 |
| T3 | 50 yêu cầu tiếng Việt có đáp án | FR-08b |
| T4 | 10 kịch bản sửa cục bộ (vd chỉ đổi ghế) | FR-11, 12 |
| T5 | 10 scene có báo giá tính tay | FR-13 |
| T6 | 5 job cùng lúc; 1 job bị kill giữa chừng | NFR-01–04 |

Tầng kiểm thử: unit (`pytest`, laptop, hiện 37 test) → benchmark Phase 0 (GPU) → tích hợp qua `/prompt`
→ E2E demo quay video.

## 9. Tự phản biện

Rủi ro lớn nhất của P1: **chất lượng 3D từ ảnh sản phẩm thật chưa kiểm chứng** — chạy I1 trên T1 trước mọi việc khác.

| # | Điểm yếu | Hậu quả | Giảm thiểu |
| --- | --- | --- | --- |
| 1 | TRELLIS.2 chưa thử trên sản phẩm công ty (bề mặt bóng, kính, chân mảnh, vải) | Asset xấu → demo kém | I1 cho T1 trước; SKU fail → chụp lại / dựng tay SKU bán chạy |
| 2 | Kết quả là hộp phòng 3D, kém thật hơn ảnh gốc | Khách thấy phòng "giả" | FR-18: ghép đồ lên ảnh thật từ đúng camera |
| 3 | Tô màu biến thể là gần đúng | Khách đặt sai màu | Nhãn "màu minh hoạ"; chụp ảnh biến thể bán chạy |
| 4 | Community: pod có thể lên với 0 GPU; Terminate mất `/workspace` | Mất buổi demo / mất asset | Code trên git, model từ `models.lock`, sao lưu asset + CSV; chuyển Secure nếu lặp lại |
| 5 | `runpodctl` trong pod chưa xác minh | Không tự dừng → tốn tiền | Kiểm log lần đầu; số dư nạp nhỏ làm trần chi phí |
| 6 | CSV không có transaction | 2 người sửa cùng lúc mất dữ liệu | 1 người quản trị CSV; CSV trên git |
| 7 | Hộp phòng lấy từ phần sàn nhìn thấy | Phòng nhỏ hơn thật | Bắt buộc nhập 1 kích thước thật để hiệu chỉnh |
| 8 | Ngưỡng nghiệm thu đặt khi chưa có dữ liệu | Quá chặt/quá lỏng | Chốt sau Phase 0 |
| 9 | Ảnh phòng khách lưu ở máy chủ nước ngoài | Pháp lý dữ liệu cá nhân | Demo dùng ảnh nội bộ/được đồng ý; rà soát trước khi dùng ảnh khách |
| 10 | Tải model/node từ HF/GitHub | Chuỗi cung ứng, version trôi | Ghim commit + sha256 |
| 11 | Đặt đồ chỉ theo hình chữ nhật, góc 90° | Bố cục cứng, không có đồ xoay chéo | Đủ cho demo; chỉnh tay toạ độ khi cần |

## 10. Chuẩn bị code

Phần không cần GPU **đã xong** (mục 3, cột Code). Việc tiếp theo:

- [ ] Công ty chuẩn bị T1 (ảnh + kích thước + giá 20 SKU), T2 (20 ảnh phòng có số đo), người duyệt
- [ ] Tạo pod RunPod, chạy `bootstrap.sh`, điền `models.lock`, tải model
- [ ] Phase 0: benchmark từng model, dựng workflow I1 và phòng trong UI, Export (API) vào `workflows/api/`
- [ ] I1 cho 20 SKU → designer chấm → **quyết định đi tiếp với TRELLIS.2 hay đổi hướng**
- [ ] Nối output MoGe-2 + SAM 3 vào `core.room.estimate_room`, đưa kích thước phòng vào W1
- [ ] Cập nhật ngưỡng nghiệm thu theo số đo thật
