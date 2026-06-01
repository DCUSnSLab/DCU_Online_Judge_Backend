"""SSO m2m client — RP 가 SSO 의 ServiceMembership 갱신.

- token endpoint 호출 (grant_type=client_credentials)
- token 캐시 (in-process, expires_in 만료 30초 전까지 재사용)
- PUT /internal/services/{client_id}/members/{sso_sub}

실패는 로깅만. RP 의 핵심 흐름은 막지 않음 (best-effort sync).
"""
from __future__ import annotations

import logging
import threading
import time

import requests
from django.conf import settings

log = logging.getLogger(__name__)

_lock = threading.Lock()
_token_cache: dict = {"access_token": None, "exp": 0.0}


def _get_m2m_token() -> str | None:
    """client_credentials 로 m2m access_token 발급/캐시 반환."""
    now = time.time()
    with _lock:
        if _token_cache["access_token"] and _token_cache["exp"] - 30 > now:
            return _token_cache["access_token"]
        try:
            r = requests.post(
                f"{settings.SSO_INTERNAL_BASE}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.SSO_CLIENT_ID,
                    "client_secret": settings.SSO_CLIENT_SECRET,
                    "scope": "internal:services",
                },
                timeout=settings.SSO_HTTP_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            _token_cache["access_token"] = data["access_token"]
            _token_cache["exp"] = now + int(data.get("expires_in", 600))
            return _token_cache["access_token"]
        except Exception as e:
            log.error("sso.m2m.token_failed err=%s", e)
            return None


def set_require_tfa(sso_sub: str | None, value: bool) -> bool:
    """SSO 의 ServiceMembership.require_tfa 갱신. 성공 시 True.

    - sso_sub 가 None/빈문자열이면 skip (SSO 와 매핑 안 된 사용자)
    - 호출자는 transaction.on_commit() 으로 묶는 것을 권장 (DB 커밋 후 외부 호출)
    """
    if not sso_sub:
        return False
    token = _get_m2m_token()
    if not token:
        return False
    url = (
        f"{settings.SSO_INTERNAL_BASE}"
        f"/internal/services/{settings.SSO_CLIENT_ID}/members/{sso_sub}"
    )
    try:
        r = requests.put(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"require_tfa": value, "status": "ACTIVE"},
            timeout=settings.SSO_HTTP_TIMEOUT,
        )
        if r.status_code in (200, 201):
            return True
        log.error(
            "sso.set_tfa.failed sub=%s value=%s status=%d body=%s",
            sso_sub, value, r.status_code, r.text[:200],
        )
        return False
    except Exception as e:
        log.error("sso.set_tfa.error sub=%s err=%s", sso_sub, e)
        return False
