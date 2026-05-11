"""
정성평가 사이드카(eval-dashboard FastAPI) 운영 옵션 관리.
- GET  /api/admin/eval/slots          : 현재 슬롯 상태 조회
- POST /api/admin/eval/slots {value}  : 슬롯 변경 (즉시 적용 + .env 동기화)

권한: Super Admin only.
사이드카 인증: EVAL_ADMIN_TOKEN 헤더(X-Admin-Token).
.env 동기화: 사이드카가 재시작되어도 값을 유지하기 위해 eval-dashboard/.env 의 MAX_CONCURRENT_EVAL_JOBS 라인 갱신.
"""
import os
import re
from pathlib import Path

import requests
from django.conf import settings

from account.decorators import super_admin_required
from utils.api import APIView


EVAL_BASE = "http://127.0.0.1:8001/api"
DEFAULT_EVAL_DIR = "/home/soobin/development/dcucode/DCU_Online_Judge_SideProjects/eval-dashboard/backend"


def _admin_token():
    # Django settings or env var. dev_settings.py 에 별도로 안 적었어도 환경변수로 받음.
    return getattr(settings, "EVAL_ADMIN_TOKEN", None) or os.environ.get("EVAL_ADMIN_TOKEN", "")


def _eval_env_path():
    p = getattr(settings, "EVAL_DASHBOARD_DIR", None) or os.environ.get("EVAL_DASHBOARD_DIR", DEFAULT_EVAL_DIR)
    return Path(p) / ".env"


def _sync_env_slots(value: int) -> bool:
    """eval-dashboard/.env 의 MAX_CONCURRENT_EVAL_JOBS 라인 갱신. 없으면 추가."""
    env_path = _eval_env_path()
    if not env_path.is_file():
        return False
    try:
        text = env_path.read_text(encoding="utf-8")
        line = f"MAX_CONCURRENT_EVAL_JOBS={value}"
        if re.search(r"^MAX_CONCURRENT_EVAL_JOBS=.*$", text, re.MULTILINE):
            new_text = re.sub(r"^MAX_CONCURRENT_EVAL_JOBS=.*$", line, text, flags=re.MULTILINE)
        else:
            sep = "" if text.endswith("\n") else "\n"
            new_text = text + sep + line + "\n"
        env_path.write_text(new_text, encoding="utf-8")
        return True
    except OSError:
        return False


class EvalSlotsAPI(APIView):
    @super_admin_required
    def get(self, request):
        token = _admin_token()
        if not token:
            return self.error("EVAL_ADMIN_TOKEN 설정이 필요합니다 (사이드카 .env + Django env 둘 다)")
        try:
            r = requests.get(f"{EVAL_BASE}/admin/slots",
                             headers={"X-Admin-Token": token}, timeout=10)
        except requests.RequestException as e:
            return self.error(f"사이드카 도달 실패: {e}")
        if r.status_code != 200:
            return self.error(f"사이드카 응답 오류: {r.status_code} {r.text[:200]}")
        return self.success(r.json())

    @super_admin_required
    def post(self, request):
        try:
            value = int((request.data or {}).get("value"))
        except (TypeError, ValueError):
            return self.error("value(정수) 필드가 필요합니다")
        if value < 1 or value > 64:
            return self.error("value 는 1~64 사이여야 합니다")

        token = _admin_token()
        if not token:
            return self.error("EVAL_ADMIN_TOKEN 설정이 필요합니다")

        try:
            r = requests.post(
                f"{EVAL_BASE}/admin/slots",
                json={"value": value},
                headers={"X-Admin-Token": token, "Content-Type": "application/json"},
                timeout=10,
            )
        except requests.RequestException as e:
            return self.error(f"사이드카 도달 실패: {e}")

        if r.status_code != 200:
            return self.error(f"사이드카 응답 오류: {r.status_code} {r.text[:200]}")

        synced = _sync_env_slots(value)
        result = r.json()
        result["env_synced"] = synced
        return self.success(result)
