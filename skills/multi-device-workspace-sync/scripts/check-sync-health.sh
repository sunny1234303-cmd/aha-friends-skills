#!/usr/bin/env bash
# 상시 가동 기기에서 실행: Syncthing 동기화 상태와 Tailscale 원격 접근 상태를 한 번에 점검.
# 이 스크립트는 범용 템플릿이다 — SYNCTHING_GUI, TAILSCALE_HOSTNAME, LOCAL_SERVICE_PORT를
# 자신의 환경에 맞게 아래에서 바꿔 쓴다.

set -euo pipefail

SYNCTHING_GUI="${SYNCTHING_GUI:-http://127.0.0.1:8384}"
LOCAL_SERVICE_PORT="${LOCAL_SERVICE_PORT:-}"  # 예: 5678 — 비워두면 이 항목은 건너뜀

echo "== Syncthing =="
if curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$SYNCTHING_GUI" | grep -q "200\|401"; then
  echo "OK  — Syncthing GUI 응답함 ($SYNCTHING_GUI)"
else
  echo "WARN — Syncthing이 안 켜져 있거나 응답 없음. 'open -a Syncthing'으로 실행 확인."
fi

echo "== Tailscale =="
if command -v tailscale >/dev/null 2>&1; then
  tailscale status --peers=false 2>/dev/null || echo "WARN — tailscale 데몬 상태 확인 불가"
else
  echo "INFO — tailscale CLI 없음 (앱만 설치된 경우 정상일 수 있음)"
fi

if [ -n "$LOCAL_SERVICE_PORT" ]; then
  echo "== 로컬 서비스 (port $LOCAL_SERVICE_PORT) =="
  if curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:$LOCAL_SERVICE_PORT" | grep -q "^[23]"; then
    echo "OK  — 로컬 서비스 응답함"
  else
    echo "WARN — 로컬 서비스 응답 없음"
  fi
fi
