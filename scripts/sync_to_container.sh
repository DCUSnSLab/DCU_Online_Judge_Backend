#!/usr/bin/env bash
# 호스트 backend repo → 실행 중인 oj-backend 컨테이너로 변경 파일 복사.
#
# 사용:
#   bash scripts/sync_to_container.sh                  # 인증 관련 디렉토리 일괄 복사
#   bash scripts/sync_to_container.sh path1 path2 ...   # 지정 파일/디렉토리만
#   RESTART=1 bash scripts/sync_to_container.sh         # 복사 후 재시작
#
# 컨테이너 자동 탐지: ancestor=harbor.cu.ac.kr/dcucode_dev/dcu_code_be 또는 name=oj-backend
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CTNR="$(docker ps -q --filter "name=oj-backend" | head -1)"
if [ -z "$CTNR" ]; then
  CTNR="$(docker ps -q --filter "ancestor=harbor.cu.ac.kr/dcucode_dev/dcu_code_be:latest" | head -1)"
fi
if [ -z "$CTNR" ]; then
  echo "[err] oj-backend 컨테이너를 찾을 수 없습니다." >&2
  exit 1
fi

# 기본 sync 대상 — SSO 이식과 관련된 디렉토리/파일
if [ $# -eq 0 ]; then
  TARGETS=(
    "account"
    "oj/settings.py"
    "oj/urls.py"
  )
else
  TARGETS=("$@")
fi

echo "→ container: $CTNR"
for t in "${TARGETS[@]}"; do
  src="$REPO_ROOT/$t"
  if [ ! -e "$src" ]; then
    echo "  skip (없음): $t"; continue
  fi
  dst="/app/$t"
  if [ -d "$src" ]; then
    parent="/app/$(dirname "$t")"
    docker exec "$CTNR" mkdir -p "$parent" 2>/dev/null || true
    docker cp "$src" "$CTNR:$parent/"
    echo "  cp -r $t → $parent/"
  else
    parent="/app/$(dirname "$t")"
    docker exec "$CTNR" mkdir -p "$parent" 2>/dev/null || true
    docker cp "$src" "$CTNR:$dst"
    echo "  cp    $t → $dst"
  fi
done

if [ "${RESTART:-0}" = "1" ]; then
  echo "→ restart $CTNR"
  docker restart "$CTNR" >/dev/null
fi

echo "✓ sync 완료"
