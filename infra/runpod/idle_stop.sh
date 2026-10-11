#!/usr/bin/env bash
# Tự Stop pod khi GPU rảnh và hàng đợi ComfyUI trống liên tục IDLE_MIN phút (NFR-07).
# Lệnh dừng theo docs RunPod: `runpodctl pod stop $RUNPOD_POD_ID`.
# CHƯA XÁC MINH: runpodctl có sẵn + đã xác thực bên trong pod hay không → script kiểm tra trước,
# nếu thiếu thì chỉ ghi cảnh báo (không làm gì nguy hiểm). Phase 0 phải thử thật 1 lần.
set -uo pipefail

IDLE_MIN=${IDLE_MIN:-30}
CHECK_S=${CHECK_S:-300}
GPU_BUSY_PCT=${GPU_BUSY_PCT:-5}
idle_since=""

stop_pod() {
  if command -v runpodctl >/dev/null 2>&1 && [ -n "${RUNPOD_POD_ID:-}" ]; then
    echo "$(date -Is) rảnh ${IDLE_MIN} phút → runpodctl pod stop $RUNPOD_POD_ID"
    runpodctl pod stop "$RUNPOD_POD_ID" && exit 0
    echo "$(date -Is) runpodctl lỗi — cần Stop tay trên console"
  else
    echo "$(date -Is) CẢNH BÁO: không có runpodctl hoặc RUNPOD_POD_ID → không tự dừng được, hãy Stop tay"
  fi
}

while true; do
  util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | sort -n | tail -1)
  jobs=$(curl -s --max-time 5 http://127.0.0.1:8188/queue | python3 -c \
    "import sys,json;q=json.load(sys.stdin);print(len(q.get('queue_running',[]))+len(q.get('queue_pending',[])))" \
    2>/dev/null || echo 0)
  if [ "${util:-0}" -lt "$GPU_BUSY_PCT" ] && [ "${jobs:-0}" -eq 0 ]; then
    [ -z "$idle_since" ] && idle_since=$(date +%s)
    if [ $(( $(date +%s) - idle_since )) -ge $(( IDLE_MIN * 60 )) ]; then
      stop_pod
      idle_since=$(date +%s)  # không spam nếu dừng thất bại
    fi
  else
    idle_since=""
  fi
  sleep "$CHECK_S"
done
