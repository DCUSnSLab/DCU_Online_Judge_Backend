"""dcu-sso 통합 — OIDC RP (Authorization Code + PKCE) 엔드포인트.

흐름 (Phase A):
  1. Browser  GET  /api/auth/oidc/start?next=...
        → state + code_verifier 생성, **signed cookie** 에 저장 (세션 무관)
        → SSO /oauth/authorize 로 302

  2. SSO 가 사용자 인증 후
     Browser  GET  /api/auth/callback?code=...&state=...
        → cookie 에서 state 복원·검증
        → SSO /oauth/token POST (code + code_verifier + client_secret)
        → id_token JWKS 검증
        → OJ User upsert (preferred_username 매칭, 없으면 신규 생성)
        → auth.login(request, user) (Django 세션)
        → SimpleJWT access/refresh 발급
        → Set-Cookie 로 잠시 access_token/refresh_token 노출 (frontend 가 localStorage 로 이전)
        → 302 frontend `next` 또는 `/`

기존 /api/login (UserLoginAPI) 는 그대로 살아있음 — feature flag 로 사용자 단위 전환.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from urllib.parse import urlencode, urlparse

import requests
from django.conf import settings
from django.contrib import auth
from django.core import signing
from django.http import HttpResponseRedirect
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken

from account.auth.sso_jwt import SSOAuthError, verify_id_token
from account.models import AdminType, User, UserProfile
from utils.api import APIView, CSRFExemptAPIView

logger = logging.getLogger(__name__)

# state/verifier 를 담을 signed cookie 이름 + TTL.
STATE_COOKIE_NAME = "sso_oidc_state"
STATE_COOKIE_TTL  = 600  # 10분 — SSO 로그인 페이지 체류 시간 여유분
STATE_SALT        = "account.oj_sso.state"


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def _gen_state() -> str:
    return secrets.token_urlsafe(32)


def _gen_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) — S256."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _safe_next(candidate: str | None) -> str:
    if not candidate:
        return "/"
    p = urlparse(candidate)
    # 외부 도메인으로의 open redirect 차단 — path 만 허용
    if p.netloc:
        return "/"
    return candidate or "/"


def _frontend_redirect(path: str) -> HttpResponseRedirect:
    """frontend dev/prod URL 로 302. base 미설정이면 path-only (same-origin)."""
    base = getattr(settings, "SSO_FRONTEND_BASE", "") or ""
    return HttpResponseRedirect((base + path) if base else path)


def _set_state_cookie(response, *, state: str, verifier: str, next_url: str) -> None:
    payload = signing.dumps(
        {"state": state, "verifier": verifier, "next": next_url},
        salt=STATE_SALT,
    )
    response.set_cookie(
        STATE_COOKIE_NAME, payload,
        max_age=STATE_COOKIE_TTL,
        httponly=True, secure=settings.SSO_COOKIE_SECURE,
        samesite="Lax",
        path="/api/",
    )


def _pop_state_cookie(request, response) -> dict | None:
    raw = request.COOKIES.get(STATE_COOKIE_NAME)
    if not raw:
        return None
    try:
        data = signing.loads(raw, salt=STATE_SALT, max_age=STATE_COOKIE_TTL)
    except signing.BadSignature:
        return None
    response.delete_cookie(STATE_COOKIE_NAME, path="/api/")
    return data


# ---------------------------------------------------------------------
# /api/auth/signup — SSO 회원가입 페이지로 단순 302
# ---------------------------------------------------------------------
class SSOSignupRedirectAPI(APIView):
    """frontend 의 '회원가입' 버튼 → SSO /signup 로 redirect.

    SSO 가 가입 + 이메일 인증을 자체적으로 처리. 끝나면 사용자가
    /api/auth/oidc/start 로 다시 와서 로그인.
    """

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        if not settings.SSO_LOGIN_ENABLED:
            return self.error("SSO is disabled")
        url = f"{settings.SSO_ISSUER.rstrip('/')}/signup"
        return HttpResponseRedirect(url)


# ---------------------------------------------------------------------
# /api/auth/oidc/start
# ---------------------------------------------------------------------
class OIDCStartAPI(APIView):
    """SSO authorize 로 브라우저 redirect.

    GET ?next=<path>
    """

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        if not settings.SSO_LOGIN_ENABLED:
            return self.error("SSO login is disabled")

        next_url = _safe_next(request.GET.get("next"))
        state = _gen_state()
        verifier, challenge = _gen_pkce_pair()

        params = {
            "response_type":  "code",
            "client_id":      settings.SSO_CLIENT_ID,
            "redirect_uri":   settings.SSO_REDIRECT_URI,
            "scope":          "openid profile email offline_access",
            "state":          state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        authorize_url = f"{settings.SSO_ISSUER.rstrip('/')}/oauth/authorize?{urlencode(params)}"
        response = HttpResponseRedirect(authorize_url)
        _set_state_cookie(response, state=state, verifier=verifier, next_url=next_url)
        return response


# ---------------------------------------------------------------------
# /api/auth/callback
# ---------------------------------------------------------------------
class OIDCCallbackAPI(CSRFExemptAPIView):
    """SSO 가 code 로 redirect — token 교환 + OJ User 매핑 + 세션/JWT 발급."""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        if not settings.SSO_LOGIN_ENABLED:
            return self.error("SSO login is disabled")

        code = request.GET.get("code")
        state = request.GET.get("state", "")
        error = request.GET.get("error")

        # state cookie 추출 (cookie 도 응답에서 삭제됨)
        scratch_resp = HttpResponseRedirect("")  # cookie 삭제용 placeholder
        cookie_data = _pop_state_cookie(request, scratch_resp)

        def _err(code: str) -> HttpResponseRedirect:
            r = _frontend_redirect(f"/auth/callback?error={code}")
            # state cookie 잔존 시 삭제
            if cookie_data is not None:
                r.delete_cookie(STATE_COOKIE_NAME, path="/api/")
            return r

        if error:
            return _err(error)
        if not code:
            return _err("missing_code")
        if cookie_data is None:
            return _err("invalid_state")

        expected_state = cookie_data.get("state")
        verifier       = cookie_data.get("verifier")
        next_url       = _safe_next(cookie_data.get("next"))

        if not expected_state or expected_state != state:
            return _err("invalid_state")
        if not verifier:
            return _err("missing_verifier")

        # ── 1) SSO /oauth/token 교환 ──
        try:
            r = requests.post(
                f"{settings.SSO_INTERNAL_BASE.rstrip('/')}/oauth/token",
                data={
                    "grant_type":    "authorization_code",
                    "client_id":     settings.SSO_CLIENT_ID,
                    "client_secret": settings.SSO_CLIENT_SECRET,
                    "code":          code,
                    "code_verifier": verifier,
                    "redirect_uri":  settings.SSO_REDIRECT_URI,
                },
                timeout=settings.SSO_HTTP_TIMEOUT,
            )
        except requests.RequestException as e:
            logger.error("sso.callback.token_post_failed err=%s", e)
            return _frontend_redirect("/auth/callback?error=token_exchange_failed")

        if r.status_code != 200:
            logger.error("sso.callback.token_post_status=%s body=%s", r.status_code, r.text[:200])
            return _frontend_redirect("/auth/callback?error=token_exchange_failed")

        data = r.json()
        id_token = data.get("id_token") or data.get("access_token")
        if not id_token:
            return _frontend_redirect("/auth/callback?error=token_missing")

        # ── 2) id_token JWKS 검증 ──
        try:
            ident = verify_id_token(id_token, expected_aud=settings.SSO_CLIENT_ID)
        except SSOAuthError as e:
            logger.error("sso.callback.verify_failed err=%s", e)
            return _frontend_redirect("/auth/callback?error=token_invalid")

        # ── 3) OJ User 매핑/upsert ──
        user = _resolve_or_create_user(ident)
        if user.is_disabled:
            return _frontend_redirect("/auth/callback?error=account_disabled")

        # ── 4) Django 세션 로그인 ──
        # OJ 의 utils.api.APIView 는 DRF APIView 가 아닌 Django View 직상속이라
        # DRF DEFAULT_AUTHENTICATION_CLASSES (SimpleJWT) 가 작동하지 않는다.
        # 즉 모든 API 는 Django session 으로만 인증됨. Phase B/C 에서 APIView 를
        # DRF 로 교체한 후 이 부분을 다시 제거할 예정.
        user.backend = "django.contrib.auth.backends.ModelBackend"
        auth.login(request, user)
        user.last_login = now()
        user.save(update_fields=["last_login"])

        # ── 5) SimpleJWT pair 발급 (frontend 가 localStorage 로 이전) ──
        refresh = RefreshToken.for_user(user)
        access_jwt  = str(refresh.access_token)
        refresh_jwt = str(refresh)

        # ── 6) frontend `/auth/callback` 으로 302 + cookie 로 잠깐 토큰 전달
        resp = _frontend_redirect(f"/auth/callback?next={next_url}")
        resp.delete_cookie(STATE_COOKIE_NAME, path="/api/")  # state cookie 정리
        # HttpOnly=False → frontend JS 가 읽어서 localStorage 로 옮긴 후 즉시 cookie 삭제
        resp.set_cookie("sso_access_token",  access_jwt,
                        max_age=120, httponly=False, secure=settings.SSO_COOKIE_SECURE,
                        samesite="Lax")
        resp.set_cookie("sso_refresh_token", refresh_jwt,
                        max_age=120, httponly=False, secure=settings.SSO_COOKIE_SECURE,
                        samesite="Lax")
        return resp


# ---------------------------------------------------------------------
# User 매핑/upsert
# ---------------------------------------------------------------------
def _resolve_or_create_user(ident) -> User:
    """SSO 사용자 → OJ User. 우선순위:
       1) sso_sub  (두 번째 로그인부터)
       2) legacy_oj_id claim → OJ.User.id 직접 매칭 (import 사용자 100% 정확)
       3) username claim (= SSO username) — 단, sso_sub 가 아직 비어있는 OJ User 만
       4) 신규 생성 (admin_type=REGULAR_USER, is_allowed=True)
    """
    # 1) sso_sub
    u = User.objects.filter(sso_sub=ident.sub).first()
    if u:
        return u

    # 2) legacy_oj_id (= OJ.User.id) — claim 에 있고 그 행이 아직 다른 sub 와 미연결일 때
    if ident.legacy_oj_id:
        u = User.objects.filter(id=ident.legacy_oj_id, sso_sub__isnull=True).first()
        if u:
            return _link_existing(u, ident, reason="legacy_oj_id")

    # 3) username 매칭 — SSO 의 username 그대로 (학번 아님)
    sso_username = ident.username or ident.preferred_username
    if sso_username:
        u = User.objects.filter(
            username__iexact=sso_username, sso_sub__isnull=True
        ).first()
        if u:
            return _link_existing(u, ident, reason="username")

    # 4) 신규 생성
    new_username = sso_username or f"sso-{ident.sub[:8]}"
    schoolssn = int(ident.dcucode_id) if (ident.dcucode_id and ident.dcucode_id.isdigit()) else 0
    u = User.objects.create(
        username=new_username,
        sso_sub=ident.sub,
        schoolssn=schoolssn,
        email=ident.email or None,
        realname=ident.name or "",
        admin_type=AdminType.REGULAR_USER,
        is_allowed=True,
    )
    UserProfile.objects.create(user=u)
    logger.info("sso.user.created username=%s sub=%s schoolssn=%s",
                new_username, ident.sub, schoolssn)
    return u


def _link_existing(u: User, ident, *, reason: str) -> User:
    """기존 OJ User 에 sso_sub 채움. 빈 필드만 채우고 기존 값은 덮어쓰지 않음."""
    u.sso_sub = ident.sub
    update_fields = ["sso_sub"]
    if ident.email and not u.email:
        u.email = ident.email
        update_fields.append("email")
    if ident.dcucode_id and ident.dcucode_id.isdigit() and not u.schoolssn:
        u.schoolssn = int(ident.dcucode_id)
        update_fields.append("schoolssn")
    u.save(update_fields=update_fields)
    logger.info("sso.user.linked oj_id=%s sub=%s via=%s", u.id, ident.sub, reason)
    return u
