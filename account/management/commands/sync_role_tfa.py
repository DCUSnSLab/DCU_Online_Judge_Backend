"""ADMIN/SUPER_ADMIN/TA_ADMIN 사용자의 SSO require_tfa 일괄 동기화.

OJ 의 admin_type 이 위 셋 중 하나면 SSO 의 ServiceMembership.require_tfa=True.
그 외는 False (--include-downgrade 옵션 시).

사용법:
    python manage.py sync_role_tfa                # admin/교수 → require_tfa=True
    python manage.py sync_role_tfa --dry-run      # DB 변경 없음. 호출 대상만 출력
    python manage.py sync_role_tfa --include-downgrade
        # REGULAR_USER 인데 require_tfa=True 인 경우도 같이 False 로 되돌림
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from account.models import AdminType, User
from account.sso_client import set_require_tfa


ROLES_REQUIRE_TFA = (AdminType.ADMIN, AdminType.SUPER_ADMIN, AdminType.TA_ADMIN)


class Command(BaseCommand):
    help = "ADMIN/SUPER_ADMIN/TA_ADMIN 사용자에게 SSO require_tfa=True 일괄 적용."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="실제 API 호출 없이 대상만 출력")
        parser.add_argument("--include-downgrade", action="store_true",
                            help="REGULAR_USER 등 권한 하향된 사용자도 require_tfa=False 로 동기화")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        include_down = opts["include_downgrade"]

        # 1) 권한자 — require_tfa=True 대상
        admins = (
            User.objects
            .filter(admin_type__in=ROLES_REQUIRE_TFA)
            .exclude(Q(sso_sub__isnull=True) | Q(sso_sub=""))
            .order_by("admin_type", "username")
        )
        total_admin = admins.count()
        self.stdout.write(self.style.NOTICE(
            f"권한자 {total_admin}명 (ADMIN/SUPER_ADMIN/TA_ADMIN) — require_tfa=True 적용"
        ))

        ok = fail = 0
        for u in admins.iterator():
            label = f"{u.username:<20} {u.admin_type:<12} sso_sub={u.sso_sub}"
            if dry:
                self.stdout.write(f"  [DRY] {label}")
                continue
            if set_require_tfa(u.sso_sub, True):
                ok += 1
                self.stdout.write(f"  ✓ {label}")
            else:
                fail += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {label}"))

        # 2) 권한 하향자 — require_tfa=False (옵션)
        down_ok = down_fail = 0
        total_down = 0
        if include_down:
            regulars = (
                User.objects
                .exclude(admin_type__in=ROLES_REQUIRE_TFA)
                .exclude(Q(sso_sub__isnull=True) | Q(sso_sub=""))
                .order_by("username")
            )
            total_down = regulars.count()
            self.stdout.write(self.style.NOTICE(
                f"\n권한 하향자 {total_down}명 — require_tfa=False 적용"
            ))
            for u in regulars.iterator():
                label = f"{u.username:<20} {u.admin_type:<12} sso_sub={u.sso_sub}"
                if dry:
                    self.stdout.write(f"  [DRY] {label}")
                    continue
                if set_require_tfa(u.sso_sub, False):
                    down_ok += 1
                else:
                    down_fail += 1

        # 요약
        self.stdout.write(self.style.SUCCESS(
            f"\n완료 — 권한자 ok={ok} fail={fail} (전체 {total_admin})"
            + (f" / 하향자 ok={down_ok} fail={down_fail} (전체 {total_down})" if include_down else "")
            + (" [DRY-RUN]" if dry else "")
        ))
