# Demo trên RunPod L40S (Community Cloud)

Demo/dev chạy trên **1 pod RunPod L40S 48 GB, gói Community, bật khi cần**, khoảng 1–3 giờ/ngày.
Bản production cho cả công ty vẫn theo [aws-setup.md](aws-setup.md). Giá tra ngày 09/10/2026 từ
[runpod.io/pricing](https://www.runpod.io/pricing) và [docs lưu trữ](https://docs.runpod.io/pods/storage/types) —
kiểm lại trong console trước khi nạp tiền.

## Chi phí

| Khoản | Đơn giá | 1 h/ngày: tuần / tháng (USD) | 3 h/ngày: tuần / tháng (USD) |
| --- | --- | --- | --- |
| GPU L40S Community | 0.79 USD/h (số trên trang giá, kiểm lại console) | 5.53 / 23.70 | 16.59 / 71.10 |
| Volume disk 80 GB (`/workspace`) | 0.10 USD/GB-tháng khi chạy, **0.20 khi dừng** | ≤ 3.72 / ≤ 16.00 | ≤ 3.72 / ≤ 16.00 |
| Container disk 20 GB | 0.10 USD/GB-tháng (docs không ghi giá khi dừng) | ≤ 0.47 / ≤ 2.00 | ≤ 0.47 / ≤ 2.00 |
| **Tổng** | | **≤ 9.72 / ≤ 41.70** | **≤ 20.78 / ≤ 89.10** |

Đính chính so với bảng trước trong SPEC: con số "34–82 USD/tháng" giả định có network volume
0.07 USD/GB, nhưng **network volume chỉ dùng được với Secure Cloud** ([docs](https://docs.runpod.io/pods/storage/create-network-volumes)).
Với Community, ổ `/workspace` là volume disk gắn với máy đó, giá 0.20 USD/GB-tháng khi dừng.

80 GB đủ cho bộ model rút gọn (~35–45 GB: TRELLIS.2, BiRefNet, MoGe-2, SAM 3, tuỳ chọn
Qwen-Image-Edit FP8) + ComfyUI + venv. Số này là ước tính, đo lại ở Phase 0.

## Rủi ro riêng của Community — đọc trước khi chọn

1. **Pod có thể lên với 0 GPU khi Start lại**: dừng pod là trả GPU, người khác có thể thuê mất máy đó
   ([docs](https://docs.runpod.io/references/troubleshooting/zero-gpus)). Dữ liệu vẫn nằm trên máy cũ.
   Cách xử lý: Start với 0 GPU chỉ để lấy dữ liệu ra, hoặc chờ, hoặc Terminate rồi dựng pod mới.
2. **Terminate là mất `/workspace`.** Vì vậy: code luôn đẩy lên GitHub; model tải lại được từ
   `infra/models.lock`; asset 3D đã duyệt và CSV phải sao lưu ra ngoài (git hoặc nơi lưu riêng).
3. **Không mở cổng HTTP qua proxy RunPod**: URL `https://<pod>-<port>.proxy.runpod.net` là public,
   không có xác thực ([docs](https://docs.runpod.io/pods/configuration/expose-ports)). Dùng SSH tunnel như dưới.

Nếu (1) xảy ra thường xuyên: chuyển sang **Secure Cloud + network volume 80 GB** — L40S 1.09 USD/h
+ 5.60 USD/tháng lưu trữ ≈ 38–104 USD/tháng cho 1–3 h/ngày, không còn rủi ro 0 GPU. Script trong
repo dùng chung `/workspace` nên không phải sửa gì.

## Các bước

1. **Tài khoản + tiền**: đăng ký RunPod, nạp số dư nhỏ (vd 25 USD). RunPod trừ dần từ số dư nên số dư
   cũng là trần chi phí; số dư về 0 thì lưu trữ vẫn bị tính và volume có thể bị xoá — giữ số dư dương.
2. **SSH key**: trên Windows chạy `ssh-keygen -t ed25519`, dán nội dung file `.pub` vào
   *Settings → SSH Public Keys* ([docs](https://docs.runpod.io/pods/configuration/use-ssh)).
3. **Tạo pod**: Pods → Deploy → **Community Cloud** → GPU **L40S** → template **Runpod PyTorch**
   (có sẵn SSH qua TCP) → Container disk 20 GB, **Volume disk 80 GB** mount `/workspace`.
   Không thêm *HTTP ports*. Giữ TCP port 22.
4. **Kết nối**: tab *Connect* → copy lệnh *SSH over exposed TCP* (dạng `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519`).
5. **Cài lần đầu** (trong pod):
   ```bash
   cd /workspace && git clone https://github.com/Tan-Phat-20KDL/AI_Agent.git furniture-ai
   cd furniture-ai && git checkout develop   # demo cho khách: git checkout staging
   bash infra/runpod/bootstrap.sh
   # điền URL + sha256 vào infra/models.lock rồi:
   bash furniture-ai/infra/download_models.sh
   ```
   Repo là private: khi `git clone` hỏi *Username* thì nhập tên GitHub, *Password* thì dán một
   **fine-grained token** tạo tại https://github.com/settings/personal-access-tokens/new
   (Repository access: chỉ `AI_Agent`; Permissions → Contents: **Read-only**; đặt hạn dùng ngắn).
   Không dùng mật khẩu GitHub thật, không commit token vào repo.
   Phụ thuộc của ComfyUI-Trellis2 (wheel CuMesh cho Linux) cài tay theo README của node đó lần đầu,
   rồi ghi lệnh lại vào `bootstrap.sh`.
6. **Mỗi lần làm việc**:
   ```bash
   bash /workspace/furniture-ai/infra/runpod/start.sh      # trong pod
   ```
   ```powershell
   # trên Windows, giữ cửa sổ mở
   ssh -N -L 8188:127.0.0.1:8188 -L 8080:127.0.0.1:8080 root@<IP> -p <PORT> -i $HOME\.ssh\id_ed25519
   ```
   Mở `http://localhost:8188` (ComfyUI) và `http://localhost:8080/viewer/?scene=runtime/out/<scene>/v<N>/scene.glb`.
   Port forwarding `-L` là tính năng chuẩn của OpenSSH; docs RunPod không nói rõ — thử ở lần đầu.
7. **Tắt**: Stop pod trên console (không Terminate). `idle_stop.sh` tự gọi `runpodctl pod stop $RUNPOD_POD_ID`
   sau 30 phút GPU rảnh — **chưa xác minh** `runpodctl` có sẵn và đã xác thực bên trong pod; kiểm tra
   `/workspace/logs/idle_stop.log` ở lần đầu. Nếu không chạy được, phải Stop tay.

## Checklist Phase 0 trên pod

- [ ] `nvidia-smi` thấy L40S 48 GB; `bootstrap.sh` in `GPU ok: True`
- [ ] `python -m pytest -q` qua trên pod
- [ ] Workflow `api/w1_form.json` chạy qua ComfyUI API (`bench/bench_workflow.py --runs 3`)
- [ ] Dựng workflow I1 (ảnh SKU → TRELLIS.2 → FA · I1 Đăng ký asset 3D) cho 20 SKU test, đo VRAM/thời gian
- [ ] Dựng workflow phòng (MoGe-2 + SAM 3 → `core.room.estimate_room`) cho 20 ảnh test
- [ ] Thử `idle_stop.sh` dừng được pod thật
- [ ] Ghi số đo vào SRS, thay các giả định
