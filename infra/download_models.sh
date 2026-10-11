#!/usr/bin/env bash
# Tải model theo infra/models.lock vào $COMFY_DIR/models, kiểm sha256 nếu có. Chạy lại không tải trùng.
# Model gated trên HuggingFace: export HF_TOKEN=... trước khi chạy.
set -euo pipefail
REPO_DIR=${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
COMFY_DIR=${COMFY_DIR:-/workspace/ComfyUI}
LOCK="$REPO_DIR/infra/models.lock"

n=0
while IFS=$'\t' read -r name url dest sha license; do
  [[ -z "${name// }" || "$name" == \#* ]] && continue
  out="$COMFY_DIR/models/$dest"
  mkdir -p "$(dirname "$out")"
  if [ -s "$out" ]; then
    echo "[skip] $name đã có"
  else
    echo "[get ] $name ($license) → models/$dest"
    auth=()
    [ -n "${HF_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $HF_TOKEN")
    curl -fL --retry 3 "${auth[@]}" -o "$out.part" "$url"
    mv "$out.part" "$out"
  fi
  if [ -n "${sha// }" ]; then
    echo "$sha  $out" | sha256sum -c - >/dev/null && echo "[ ok ] sha256 $name" || { echo "[FAIL] sha256 $name"; exit 1; }
  fi
  n=$((n + 1))
done < "$LOCK"
echo "Xong $n model. Dung lượng: $(du -sh "$COMFY_DIR/models" | cut -f1)"
