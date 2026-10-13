#!/usr/bin/env bash
# Khởi động ComfyUI (chỉ nghe 127.0.0.1 — KHÔNG mở cổng HTTP qua proxy RunPod vì proxy là public,
# không có xác thực) + bộ tự dừng pod khi rảnh. Chạy mỗi lần Start pod.
#
# Từ máy cá nhân mở bằng SSH tunnel (SSH over exposed TCP, lấy IP/port ở tab Connect):
#   ssh -N -L 8188:127.0.0.1:8188 -L 8765:127.0.0.1:8765 root@<IP> -p <PORT> -i ~/.ssh/id_ed25519
#   → mở http://localhost:8188 (ComfyUI) và http://localhost:8765/viewer/ (viewer)
set -euo pipefail

WS=${WS:-/workspace}
REPO_DIR=${REPO_DIR:-$WS/furniture-ai}
COMFY_DIR=${COMFY_DIR:-$WS/ComfyUI}
VENV=${VENV:-$WS/venv}
LOG_DIR=${LOG_DIR:-$WS/logs}
mkdir -p "$LOG_DIR"
# shellcheck disable=SC1091
. "$VENV/bin/activate"
export FA_ROOT="$REPO_DIR"

if ! pgrep -f "ComfyUI/main.py" >/dev/null; then
  nohup python "$COMFY_DIR/main.py" --listen 127.0.0.1 --port 8188 >"$LOG_DIR/comfyui.log" 2>&1 &
  echo "ComfyUI đang khởi động → tail -f $LOG_DIR/comfyui.log"
fi
if ! pgrep -f "http.server 8765" >/dev/null; then
  (cd "$REPO_DIR" && nohup python -m http.server 8765 --bind 127.0.0.1 >"$LOG_DIR/viewer.log" 2>&1 &)
fi
if ! pgrep -f "idle_stop.sh" >/dev/null; then
  nohup bash "$REPO_DIR/infra/runpod/idle_stop.sh" >>"$LOG_DIR/idle_stop.log" 2>&1 &
  echo "Tự dừng pod sau ${IDLE_MIN:-30} phút GPU rảnh → log: $LOG_DIR/idle_stop.log"
fi
