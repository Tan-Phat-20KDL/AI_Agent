# SPEC kỹ thuật – Multi-model AI pipeline thiết kế nội thất 2D/3D + báo giá

Tra cứu 09/10/2026. Bản này là chuẩn cho cả công ty; quyết định triển khai demo nằm trong [SRS](SRS.md).
Mọi license/VRAM/giá dưới đây lấy từ trang nguồn đã mở (link kèm). Số **chưa đo** được ghi rõ là ước tính.

**Đã chốt (11/10/2026):** database = CSV; ưu tiên sản phẩm có sẵn; demo trên RunPod L40S Community;
bộ model rút gọn cho P1 (không Qwen-Image, không LLM).

## 1. Tham chiếu

| Tham chiếu | Xác minh được | Không xác minh được |
| --- | --- | --- |
| [DBHomes](https://dbhomes.com.vn/) / DBLab | Có nền tảng AI nội bộ DBLab biến mô tả thành phối cảnh, khách yêu cầu chỉnh tiếp ([CafeF 08/07/2025](https://cafef.vn/ung-dung-ai-vao-thiet-ke-noi-that-toi-uu-thoi-gian-phuc-vu-khach-hang-18825070716555534.chn), bài PR) | Model, kiến trúc, có báo giá tự động không |
| [Little Workshop – WebVR Showroom](https://littleworkshop.fr/projects/showroom/) | WebGL/three.js, vật liệu PBR, đổi vật liệu real-time; model + texture dựng tay | Có dùng lightmap bake không |

Hệ quả: showroom kiểu Little Workshop dựa trên mesh dựng tay. AI image-to-3D đủ để xem/xoay/đặt vào phòng,
nhưng chưa bằng mesh dựng tay — sản phẩm bán chạy nên có GLB dựng tay.

## 2. Pipeline

Scene graph JSON là nguồn sự thật duy nhất; LLM/form chỉ sửa scene graph; 4 nhánh đọc từ nó:
đồ 2D→3D (offline, 1 lần/biến thể), phòng chế độ A (1 ảnh) hoặc B (video), lắp `scene.glb`, báo giá.
Kết quả chính là **cảnh 3D trong three.js**; ảnh 2D chỉ là ảnh chụp từ cảnh 3D.

## 3. Model con

| # | Vai trò | Model | License | Kích thước / VRAM công bố | Nguồn |
| --- | --- | --- | --- | --- | --- |
| M1 | Hiểu yêu cầu tiếng Việt → JSON Patch (P2) | Qwen3-VL-8B-Instruct | Apache-2.0 | ~9B (BF16) | [HF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) |
| M2 | Depth mét + normal + FOV từ ảnh phòng | MoGe-2 vitl-normal | MIT | 331M; 60 ms/ảnh A100/3090 FP16 | [GitHub](https://github.com/microsoft/MoGe) |
| M3 | Mask sàn/tường/đồ bằng prompt chữ | SAM 3 (dự phòng SAM 2.1) | SAM License (không cấm thương mại; cấm quân sự/ITAR) · SAM 2: Apache-2.0 | 848M; CUDA ≥ 12.6, PyTorch ≥ 2.7 | [SAM 3](https://github.com/facebookresearch/sam3) · [SAM 2](https://github.com/facebookresearch/sam2) |
| M4 | Ảnh 2D sản phẩm từ mô tả (hàng đặt, P2) | Qwen-Image-2512 (+ LoRA) | Apache-2.0 | 20B; ComfyUI có FP8 | [HF](https://huggingface.co/Qwen/Qwen-Image-2512) |
| M5 | Tách nền ảnh sản phẩm | BiRefNet | MIT | 3.5 GB VRAM FP16 | [GitHub](https://github.com/ZhengPeng7/BiRefNet) |
| M6 | 1 ảnh → GLB có PBR | TRELLIS.2-4B | MIT | ≥ 24 GB; H100 ~3 s @512³, ~17 s @1024³; chỉ test Linux | [GitHub](https://github.com/microsoft/TRELLIS.2) · [node ComfyUI](https://github.com/visualbruno/ComfyUI-Trellis2) (MIT) |
| M6b | Dự phòng 3D | Hunyuan3D-2.1 | Tencent Community: loại trừ EU/UK/Hàn Quốc; > 1 triệu MAU phải xin | 10 GB shape, 21 GB texture | [LICENSE](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE) |
| M7 | Xoá đồ cũ khỏi ảnh phòng; làm ảnh giống thật (tuỳ chọn) | Qwen-Image-Edit-2511 | Apache-2.0 | 20B; ComfyUI native FP8 | [HF](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) · [ComfyUI](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit) |
| M8 | Hộp phòng mét từ point map | Code (`core/room`) | — | CPU | — |
| M9 | Chế độ B: pose + depth từ video | VGGT-1B-Commercial | Chỉ checkpoint Commercial dùng thương mại, phải nộp đơn | 1B | [GitHub](https://github.com/facebookresearch/vggt) |
| M10 | Chế độ B: train splat phòng | gsplat | Apache-2.0 | tới 4× ít VRAM hơn 3DGS gốc | [GitHub](https://github.com/nerfstudio-project/gsplat) |
| V | Render splat chung cảnh mesh three.js | Spark | MIT | trình duyệt | [GitHub](https://github.com/sparkjsdev/spark) |
| — | BOM + báo giá | Code (`core/quote`) | — | CPU | — |

**Đã loại vì license:** FLUX.1 dev / Kontext dev ([non-commercial](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev)),
Qwen-Image-2.1 ([Qwen Research License](https://github.com/QwenLM/Qwen-Image-2.1)),
Apple SHARP ([weights chỉ nghiên cứu](https://github.com/apple/ml-sharp/blob/main/LICENSE_MODEL)),
SpatialLM 1.1 ([CC-BY-NC-4.0](https://github.com/manycore-research/SpatialLM)),
Depth Anything V2 Base/Large ([CC-BY-NC-4.0](https://github.com/DepthAnything/Depth-Anything-V2)),
RMBG-1.4 (non-commercial theo [IC-Light](https://github.com/lllyasviel/IC-Light)).

**Bộ rút gọn cho demo P1:** M2, M3, M5, M6, (M7 tuỳ chọn) — không nạp M1, M4.

## 4. Giữ context (đã hiện thực trong `core/scene`)

1. Scene graph JSON là nguồn sự thật; mỗi object có `id` cố định.
2. Mỗi lần sửa là một JSON Patch (RFC 6902) + `EditScope` (object nào được sửa, có được đổi số lượng/thêm/xoá).
3. Validator so **kết quả** before/after theo id: object ngoài phạm vi đổi bất kỳ trường nào → từ chối.
4. Mỗi lần sửa ghi version mới, không ghi đè; undo = version mới chép nội dung cũ.
5. Cảnh 3D: mỗi đồ là node `<id>#<i>`; chỉ node của object được sửa thay đổi. Asset cache theo biến thể.
6. Đổi số lượng → chỉ món đó được xếp lại; đổi màu → vị trí giữ nguyên.

## 5. Cảnh 3D

| Chế độ | Input | Cách dựng | Xoay | License |
| --- | --- | --- | --- | --- |
| A – 1 ảnh (mặc định) | ảnh phòng | MoGe-2 + SAM 3 → hộp phòng mét; Qwen-Image-Edit xoá đồ cũ, chiếu ảnh làm texture | Quanh góc chụp; viewer giới hạn góc | MIT / SAM / Apache |
| B – video (P3) | video quanh phòng | VGGT → COLMAP → gsplat → Spark | Toàn phòng | Apache / MIT; VGGT phải xin |

Giới hạn: TRELLIS.2 xuất một bộ texture cho cả vật thể (không đổi vật liệu từng phần nếu chưa tách part);
chế độ B giữ nguyên đồ cũ trong splat.

## 6. Hạ tầng chuẩn cho công ty (production)

Tách worker để không model nào phải nạp/xả liên tục (tổng trọng số đủ bộ ~75 GB > 48 GB VRAM):

| Worker | Model | VRAM ước tính | GPU |
| --- | --- | --- | --- |
| G1 image | Qwen-Image FP8 (~20 GB) + text encoder FP8 (~8 GB); Qwen-Image-Edit luân phiên | ~28–30 GB | L40S 48 GB, RAM ≥ 64 GB |
| G2 3D | TRELLIS.2 (≥ 24 GB) + MoGe-2 + SAM 3 + BiRefNet | ~30 GB+ | L40S 48 GB, RAM ≥ 64 GB |
| G3 LLM | Qwen3-VL-8B (~18 GB BF16) | ~18 GB + KV | L4 24 GB |
| CPU | API, DB, báo giá | — | t4g.medium |

Giá tra 09/10/2026 (USD/giờ, Linux): AWS g6e.2xlarge 2.242 · g6e.xlarge 1.861 · g6.xlarge 0.805 ·
t4g.medium 0.034 ([Vantage](https://instances.vantage.sh/aws/ec2/g6e.2xlarge)) ·
RunPod Pod L40S 1.09 (Secure) · Serverless 48 GB 1.75 · Serverless 24 GB 0.69 ([RunPod](https://www.runpod.io/pricing)).

Chi phí ẩn AWS: NAT Gateway 0.045 USD/h + 0.045 USD/GB, Public IPv4 0.005 USD/h kể cả không dùng
([VPC](https://aws.amazon.com/vpc/pricing/)); EBS gp3 0.08 USD/GB-tháng kể cả khi tắt máy
([EBS](https://aws.amazon.com/ebs/pricing/)); data transfer ra Internet miễn phí 100 GB/tháng.

Thời gian GPU mỗi job **chưa đo** — mọi con số chi phí theo job/tháng ở bản online trước đây là giả định,
phải thay bằng số đo Phase 0 (`bench/bench_workflow.py`).

## 7. Tự phản biện SPEC

1. AI vẽ hình dáng tự do rồi báo giá theo template → ảnh và giá có thể không khớp. **Đã xử lý bằng P1:**
   chỉ dùng sản phẩm có sẵn, giá lấy từ biến thể; AI chỉ dựng 3D của sản phẩm có thật.
2. Phòng 3D từ 1 ảnh chỉ là hộp phòng → thêm FR-18 ghép lên ảnh thật.
3. Tỉ lệ mét của MoGe-2 chưa biết sai số → bắt buộc nhập 1 kích thước thật.
4. ComfyUI yếu ở trạng thái/version/queue → logic nằm trong `core/`, node chỉ là lớp vỏ.
5. Nhiều model, nhiều CUDA env (TRELLIS.2 CUDA 12.4/PyTorch 2.6 vs SAM 3 CUDA ≥ 12.6/PyTorch ≥ 2.7) → ghim version, thử env chung PyTorch 2.8.
6. Texture TRELLIS.2 có sẵn bóng đổ từ ảnh → bị chiếu sáng 2 lần trong three.js; cần ảnh sản phẩm ánh sáng đều.
7. License có thể đóng ở bản sau (Qwen-Image-2.1 đã chuyển Research License) → ghim bản Apache/MIT hiện tại.
