#!/bin/bash
# Dành cho bản chạy trên AWS EC2 (production công ty) — xem docs/aws-setup.md bước 4.
# Cài: echo '*/5 * * * * root /opt/furniture-ai/idle_stop.sh' | sudo tee /etc/cron.d/idle_stop
# Instance phải đặt Shutdown behavior = Stop.
LIMIT_MIN=30
STAMP=/var/tmp/idle_since
UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1)
JOBS=$(curl -s --max-time 5 http://127.0.0.1:8188/queue | python3 -c "import sys,json;q=json.load(sys.stdin);print(len(q.get('queue_running',[]))+len(q.get('queue_pending',[])))" 2>/dev/null || echo 0)
if [ "${UTIL:-0}" -lt 5 ] && [ "$JOBS" -eq 0 ]; then
  [ -f "$STAMP" ] || date +%s > "$STAMP"
  if [ $(( $(date +%s) - $(cat "$STAMP") )) -ge $(( LIMIT_MIN * 60 )) ]; then
    rm -f "$STAMP"; /sbin/shutdown -h now
  fi
else
  rm -f "$STAMP"
fi
