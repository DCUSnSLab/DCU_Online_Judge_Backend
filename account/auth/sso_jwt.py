"""dcu-sso 발급 JWT 검증 헬퍼 (Phase A — OIDC RP).

callback 시 1회 호출. 이후 OJ 의 모든 요청은 자체 SimpleJWT 가 처리.

- JWKS 는 Django cache 에 `sso_jwks` 키로 SSO_JWKS_CACHE_TTL 초 캐시.
- `kid` 미일치 시 즉시 재조회.
- iss / aud / exp 검증, signature 는 JWKS 의 `kid` 매칭 키로.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = "sso_jwks_v1"


class SSOAuthError(Exception):
    """SSO JWT 검증 실패."""


def _b64url_uint(s: str) -> int:
    pad = "=" * (-len(s) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(s + pad), "big")


def _jwk_to_rsa_pubkey(jwk: dict):
    """JWK (kty=RSA) → cryptography RSAPublicKey.

    PyJWT 의 `jwt.algorithms.RSAAlgorithm.from_jwk` 는 컨테이너 환경의 PyJWT
    버전에 따라 import 가 실패할 수 있어 직접 변환.
    """
    if jwk.get("kty") != "RSA":
        raise SSOAuthError(f"unsupported jwk kty: {jwk.get('kty')}")
    n = _b64url_uint(jwk["n"])
    e = _b64url_uint(jwk["e"])
    return RSAPublicNumbers(e, n).public_key()


@dataclass(frozen=True)
class SSOIdentity:
    sub: str
    preferred_username: str
    username: str               # SSO users.username (사용자 정의 ID) — OJ User.username 으로 매핑
    dcucode_id: str             # 학번/교직원번호 (없으면 빈 문자열)
    legacy_oj_id: int | None    # DCUCODE OJ user.id (import 사용자만 채워짐)
    email: str
    email_verified: bool
    name: str
    services: list
    raw: dict


# ---------------------------------------------------------------------
# JWKS fetch + 캐시
# ---------------------------------------------------------------------
def _jwks_url() -> str:
    return f"{settings.SSO_INTERNAL_BASE.rstrip('/')}/jwks.json"


def _fetch_jwks(force: bool = False) -> dict:
    if not force:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached
    try:
        resp = requests.get(_jwks_url(), timeout=settings.SSO_HTTP_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise SSOAuthError(f"JWKS fetch failed: {e}") from e
    jwks = resp.json()
    cache.set(CACHE_KEY, jwks, timeout=settings.SSO_JWKS_CACHE_TTL)
    return jwks


def _public_key_for(kid: str):
    jwks = _fetch_jwks(force=False)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return _jwk_to_rsa_pubkey(key)
    # kid 미일치 — 강제 재조회 후 1회 더
    jwks = _fetch_jwks(force=True)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return _jwk_to_rsa_pubkey(key)
    raise SSOAuthError(f"signing key not found: kid={kid}")


# ---------------------------------------------------------------------
# 토큰 검증
# ---------------------------------------------------------------------
def verify_id_token(token: str, *, expected_aud: str | None = None) -> SSOIdentity:
    """SSO 발급 JWT (id_token 또는 access_token) 검증.

    - signature: JWKS 의 `kid` 매칭 키
    - iss: settings.SSO_ISSUER 와 일치
    - aud: expected_aud (보통 client_id = "oj"). None 이면 검증 skip
    - exp / iat: 자동 검증
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise SSOAuthError(f"malformed token: {e}") from e

    kid = header.get("kid")
    if not kid:
        raise SSOAuthError("token header missing kid")

    pub = _public_key_for(kid)

    try:
        payload = jwt.decode(
            token,
            pub,
            algorithms=["RS256"],
            issuer=settings.SSO_ISSUER,
            audience=expected_aud,
            options={"verify_aud": expected_aud is not None},
        )
    except jwt.PyJWTError as e:
        raise SSOAuthError(f"token verify failed: {e}") from e

    return SSOIdentity(
        sub=payload["sub"],
        preferred_username=payload.get("preferred_username", ""),
        username=payload.get("username", ""),
        dcucode_id=payload.get("dcucode_id") or "",
        legacy_oj_id=payload.get("legacy_oj_id"),
        email=payload.get("email", ""),
        email_verified=bool(payload.get("email_verified", False)),
        name=payload.get("name", ""),
        services=payload.get("services") or [],
        raw=payload,
    )
