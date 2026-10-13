# Quy ước viết code

Mục tiêu: **ngắn, đọc một lần là hiểu, lỗi ở đâu sửa đúng chỗ đó**. Học theo cách các repo tham khảo
(TRELLIS.2, MoGe, ComfyUI) tách rõ thư viện lõi / lớp giao diện / script.

## 1. Tầng nào làm việc gì

```text
core/<miền>/      logic thuần: nhận dữ liệu → trả dữ liệu. Không đọc biến môi trường, không biết ComfyUI.
core/workflows.py ghép các miền thành use-case (W1, W2...). Không ghi file.
core/config.py    MỌI đường dẫn / biến môi trường — chỉ đọc cấu hình ở đây.
comfy_nodes/      lớp vỏ mỏng: đọc input node → gọi core → trả output. Không có if/else nghiệp vụ.
tools/, bench/    script chạy tay. infra/: cài đặt máy.
```

Lỗi nghiệp vụ (giá sai, đặt đồ sai) **luôn** sửa trong `core/`, kèm test. Nếu thấy mình viết logic trong
`comfy_nodes/` → chuyển xuống `core/workflows.py`.

## 2. Viết hàm

- Một hàm một việc, ≤ ~40 dòng; tên nói đúng việc (`place_missing`, `compute_quote`).
- Không sửa input: nhận scene → trả **scene mới** (`clone`/`apply_patch` đã làm sẵn).
- Đọc/ghi file chỉ ở mép: `core/io.py` (ghi atomic), `SceneStore`, `save_quote`.
- Type hint cho tham số và kết quả; `from __future__ import annotations` đầu file.
- Docstring 1–3 dòng: **vì sao**, không kể lại code. Comment chỉ khi có điều không hiển nhiên.

## 3. Lỗi

- Mỗi miền có exception riêng: `CsvValidationError`, `SceneError`, `ScopeViolation`, `PlacementError`,
  `PatchError`, `ComfyError`. Không `raise Exception(...)` chung chung.
- Thông điệp lỗi nói **ở đâu + cách sửa**: `products.csv:2 [depth_mm] phải là số nguyên` /
  `Không đủ chỗ đặt 'chair_1' ... Giảm số lượng hoặc đặt tay`.
- Không nuốt lỗi (`except: pass`). Bắt lỗi chỉ để thêm ngữ cảnh rồi `raise` tiếp.
- Hỏng giữa chừng không được để lại dữ liệu dở: tính hết rồi mới ghi (xem `plan_edit` → `commit_scene`).

## 4. Test

- Sửa bug: **viết test tái hiện lỗi trước** (test phải đỏ), sửa code, test xanh.
- Test đặt theo miền: `tests/test_<miền>.py`; dữ liệu mẫu lấy từ fixture `catalog`, `dining_scene`.
- Test không cần GPU, không cần mạng, chạy < 10 s: `python -m pytest -q`.
- Phần chỉ chạy trên GPU: viết script trong `bench/`, ghi số đo vào docs, không mock giả kết quả.

## 5. Git

- Nhánh: làm trên `develop` (hoặc `feature/<việc>` tách từ `develop`); `develop → staging → main` qua Pull Request.
- Commit nhỏ, một ý; tiêu đề dạng `loại: việc` — `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`.
  Ví dụ: `fix: W2 xếp lại ghế khi đổi sang mẫu to hơn`.
- Trước khi push: `python -m pytest -q` xanh. CI trên GitHub chạy lại tự động cho mọi push/PR.
- Không commit: `.venv/`, `runtime/`, model, ảnh khách, token/khóa (đã có `.gitignore`).

## 6. Phụ thuộc

- Core chỉ dùng `numpy`, `trimesh` (+ `pytest` khi dev). Thêm thư viện mới = ghi lý do trong PR.
- Model AI và custom node ghim commit + sha256 trong `infra/models.lock`.

## 7. Checklist Pull Request

- [ ] Test mới/đã sửa cho thay đổi này, `pytest` xanh
- [ ] Logic nằm trong `core/`, node chỉ gọi hàm
- [ ] Thông điệp lỗi chỉ ra chỗ sai + cách sửa
- [ ] Cập nhật `docs/SRS.md` nếu đổi yêu cầu/ngưỡng
