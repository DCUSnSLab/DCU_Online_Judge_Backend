# Changelog

이 프로젝트(DCU Online Judge Backend)의 주요 변경 사항을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [Semantic Versioning](https://semver.org/)을 따른다.

## [Unreleased]

## [3.0.0] - 2026-07-09
첫 정식 SemVer 릴리즈. 2022년 `OJ_2.3` 이후 누적된 변경을 정리한 상위 요약이다.
(이전 릴리즈는 `OJ_2.x` 등 비정형 태그로 관리되었음)

### Added
- SSO(OIDC) RP 연동 — `/api/auth/oidc/start`·`/api/auth/callback`, JWKS 검증, 사용자 매핑/생성
- LLM 게이트웨이 — API 키 발급/폐기, 라우트 관리, 게이트웨이 설정
- 관리자 대시보드 통계 API — 제출 추이·로그인 추이·제출 랭킹 + `UserLoginHistory` 모델 (GEN-579)
- 정성평가 큐 및 일괄 성적 재계산 관련 기능

### Changed
- 개설과목 목록 필터를 전체 레코드 기준(서버사이드)으로 처리 (GEN-1063)
- 수강생 목록 export를 페이지네이션 없이 전체 반환하도록 (GEN-581)
- LLM 키 목록에 `status` 필터 추가 — 활성/폐기 구분 (GEN-1143)

### Fixed
- 개설자 변경 시 `Problem.created_by` 미이전으로 새 개설자가 제출 내역을 못 보던 문제 (GEN-657)

### 마이그레이션
- `account.0003_userloginhistory` (로그인 통계용) 등 — 배포 시 `manage.py migrate` 필요
