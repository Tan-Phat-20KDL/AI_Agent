#!/usr/bin/env bash
# Cài môi trường trên RunPod Pod (L40S, template "Runpod PyTorch"). Chạy lại nhiều lần không sao.
#
#   cd /workspace && git clone https://github.com/Tan-Phat-20KDL/AI_Agent.git furniture-ai
#   bash /workspace/furniture-ai/infra/runpod/bootstrap.sh
#
# Mọi thứ nằm trong /workspace (volume disk) để còn sau khi Stop pod.
# LƯU Ý Community Cloud: volume gắn với 1 máy; Terminate pod là mất → luôn đẩy code lên git
# và giữ infra/models.lock để dựng lại trên pod mới được.
set -euo pipefail

WS=${WS:-/workspace}
REPO_DIR=${REPO_DIR:-$WS/furniture-ai}
COMFY_DIR=${COMFY_DIR:-$WS/ComfyUI}
VENV=${VENV:-$WS/venv}
COMFY_REF=${COMFY_REF:-master}   # ghim commit cụ thể sau Phase 0 (NFR-10)
TRELLIS_NODE_REF=${TRELLIS_NODE_REF:-main}

log() { echo -e "\n[bootstrap] $*"; }

log "GPU:"; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv || true

if [ ! -d "$VENV" ]; then
  log "Tạo venv (dùng lại PyTorch có sẵn của template)"
  python3 -m venv --system-site-packages "$VENV"
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"
python -m pip install -q -U pip

if [ ! -d "$COMFY_DIR/.git" ]; then
  log "Clone ComfyUI"
  git clone https://github.com/comfyanonymous/ComfyUI "$COMFY_DIR"
fi
git -C "$COMFY_DIR" fetch -q --all --tags
git -C "$COMFY_DIR" checkout -q "$COMFY_REF"
log "Cài requirements ComfyUI"
pip install -q -r "$COMFY_DIR/requirements.txt"

log "Cài core furniture-ai + link custom node"
pip install -q -e "$REPO_DIR"
ln -sfn "$REPO_DIR/comfy_nodes" "$COMFY_DIR/custom_nodes/furniture_ai"

if [ ! -d "$COMFY_DIR/custom_nodes/ComfyUI-Trellis2/.git" ]; then
  log "Clone node TRELLIS.2 (visualbruno/ComfyUI-Trellis2, MIT)"
  git clone https://github.com/visualbruno/ComfyUI-Trellis2 "$COMFY_DIR/custom_nodes/ComfyUI-Trellis2"
fi
git -C "$COMFY_DIR/custom_nodes/ComfyUI-Trellis2" checkout -q "$TRELLIS_NODE_REF"
log "!! Cài phụ thuộc của ComfyUI-Trellis2 theo README của nó (wheel CuMesh cho Linux + đúng bản Torch)."
log "   README chỉ hướng dẫn Windows chi tiết → làm tay lần đầu, ghi lại lệnh vào file này."

python - <<'PY'
import torch, sys
print("[bootstrap] python", sys.version.split()[0], "| torch", torch.__version__,
      "| cuda", torch.version.cuda, "| GPU ok:", torch.cuda.is_available())
PY

log "Xong. Tải model: bash $REPO_DIR/infra/download_models.sh   |   Chạy: bash $REPO_DIR/infra/runpod/start.sh"
