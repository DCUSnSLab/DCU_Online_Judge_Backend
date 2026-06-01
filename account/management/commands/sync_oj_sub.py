"""dcu-sso `service_memberships` (client=oj) 를 조회해 OJ User.sso_sub 일괄 매핑.

흐름:
1. SSO 의 /oauth/token (client_credentials) 으로 m2m 토큰 발급
2. /internal/services/oj/members 페이지 순회
3. 응답의 user_id (= SSO sub) 를 OJ User 에 매핑:
   - 우선 username 매칭 (SSO 의 preferred_username 이 OJ 의 username 과 일치하는 경우)
   - 또는 (옵션) 별도 매핑 테이블 — 지금은 username 동일성만
4. OJ User.sso_sub 채움 (idempotent)

   사용법:
       python manage.py sync_oj_sub                # 전체
       python manage.py sync_oj_sub --dry-run      # DB 미변경
       python manage.py sync_oj_sub --limit 100    # 테스트
"""

from __future__ import annotations

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from account.models import User


class Command(BaseCommand):
    help = "dcu-sso 의 service_memberships(oj) 를 OJ User.sso_sub 로 일괄 매핑"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--page-size", type=int, default=200)

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        limit = opts["limit"]
        page_size = opts["page_size"]

        token = self._m2m_token()
        self.stdout.write(self.style.NOTICE(f"  m2m token OK (len={len(token)})"))

        # 페이지네이션 순회
        page = 1
        matched = 0
        skipped = 0
        not_found = 0
        already = 0
        processed = 0

        while True:
            data = self._list_members(token, page=page, page_size=page_size)
            items = data.get("items") or []
            if not items:
                break
            for it in items:
                processed += 1
                sub = it["user_id"]

                meta = it.get("meta") or {}
                # username 우선 매핑 — SSO 의 service_memberships 에 별도 보관 X.
                # 대안: SSO /internal/users/<sub> 가 없으므로 GET 으로 idtoken 받아도 됨.
                # 가장 단순: SSO admin 명령으로 받은 preferred_username (= OJ 의 username)
                # 가 응답에 안 들어옴 → 별도 lookup 필요.
                # 여기선 meta 에 oj_admin_type 이 있는 행만 사용 (import_oj_users 가
                # 모든 OJ 행에 채워두었으므로 안전).
                if "oj_admin_type" not in meta:
                    skipped += 1
                    continue

                user_qs = User.objects.filter(sso_sub=sub)
                if user_qs.exists():
                    already += 1
                    continue

                # SSO 의 preferred_username = OJ 의 username 동일성으로 매핑
                u = self._lookup_user_by_username_via_sso(token, sub)
                if u is None:
                    not_found += 1
                else:
                    if not dry:
                        u.sso_sub = sub
                        u.save(update_fields=["sso_sub"])
                    matched += 1

                if limit and processed >= limit:
                    break

            self.stdout.write(
                f"  page={page} total={data.get('total')} processed={processed} "
                f"matched={matched} already={already} skipped={skipped} not_found={not_found}"
            )
            if limit and processed >= limit:
                break
            if processed >= (data.get("total") or 0):
                break
            page += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n완료: matched={matched}  already={already}  skipped={skipped}  not_found={not_found}"
            + ("  (DRY-RUN)" if dry else "")
        ))

    # ----------------------------------------------------------------
    def _m2m_token(self) -> str:
        url = f"{settings.SSO_INTERNAL_BASE.rstrip('/')}/oauth/token"
        try:
            r = requests.post(url, data={
                "grant_type": "client_credentials",
                "client_id":     settings.SSO_CLIENT_ID,
                "client_secret": settings.SSO_CLIENT_SECRET,
                "scope":         "internal:services",
            }, timeout=settings.SSO_HTTP_TIMEOUT)
            r.raise_for_status()
            return r.json()["access_token"]
        except requests.RequestException as e:
            raise CommandError(f"m2m 토큰 발급 실패: {e}") from e

    def _list_members(self, token: str, *, page: int, page_size: int) -> dict:
        url = (f"{settings.SSO_INTERNAL_BASE.rstrip('/')}"
               f"/internal/services/{settings.SSO_CLIENT_ID}/members"
               f"?page={page}&page_size={page_size}")
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                         timeout=settings.SSO_HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def _lookup_user_by_username_via_sso(self, token: str, sub: str) -> User | None:
        """SSO 가 외부 노출하지 않으므로 username 으로 OJ DB 에서 직접 찾는 대신,
        SSO 의 service_memberships meta 에 우리가 import 시 저장한 oj_admin_type 의
        존재 자체로 매핑 안전성 확인. 실제 username 은 SSO 의 sub 으로는 알 수 없으므로
        SSO 의 별도 admin API 가 추가될 때까지는 본 명령은 import_oj_users 가 채워둔
        legacy_oj_id 와의 1대1 관계를 신뢰한다.

        대신 OJ 측에서는 username 매칭이 가능 — SSO 의 preferred_username 이 OJ username
        과 같으므로, SSO 의 /userinfo 를 m2m 로는 호출 못 함 (Bearer access_token 필요).
        따라서 이 명령은 sub 만으로 매핑할 수 없고, SSO 가 별도 admin lookup API 를 노출하기 전까지는
        callback 시점의 JIT 매핑에 의존한다.
        """
        # Phase A: callback JIT 매핑을 우선 신뢰. bulk sync 는 SSO 가 admin lookup API
        # 노출한 후에 활성화. 여기선 None 반환으로 not_found 만 카운트.
        return None
