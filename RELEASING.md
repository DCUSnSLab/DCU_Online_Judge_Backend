# 릴리즈 / 버전 관리 가이드

## 버전 체계
- **Semantic Versioning**: `vMAJOR.MINOR.PATCH`
  - **MAJOR**: 호환성이 깨지는 변경 (API·DB 스키마 등)
  - **MINOR**: 하위호환 기능 추가
  - **PATCH**: 하위호환 버그·소규모 수정
- **repo별 독립 버전**: 백엔드/프론트가 각자 태그·CHANGELOG를 관리한다.
- 태그 이름은 `vX.Y.Z` 로 통일한다. (과거 `OJ_2.x` 혼용은 v3.0.0부터 정리)

## 브랜치 흐름
- 기능/수정: `GEN-####_...` 브랜치 → PR → `develop`
- 릴리즈: `develop` → `master` PR 머지 시점이 하나의 릴리즈다.
- `master` 는 항상 "배포된 상태"를 가리키고, 모든 정식 태그는 `master` 에 찍는다.

## 릴리즈 절차 (develop → master)
1. `develop` 에서 이번 릴리즈 범위를 확정한다.
2. 새 버전 번호를 정한다 (기능 누적 → MINOR, 버그만 → PATCH, 호환성 깨짐 → MAJOR).
3. `CHANGELOG.md` 의 `[Unreleased]` 항목을 `[X.Y.Z] - YYYY-MM-DD` 로 확정한다.
4. 버전 마커 갱신: 루트 `VERSION` 파일.
5. `develop → master` PR 을 생성·머지한다.
6. `master` 에서 태그:
   ```bash
   git checkout master && git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
7. GitHub Release 발행 (해당 CHANGELOG 섹션을 릴리즈 노트로):
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <릴리즈노트.md>
   ```

## 마이그레이션 주의
- DB 마이그레이션이 포함된 릴리즈는 CHANGELOG에 명시하고, 배포 시 `manage.py migrate` 를 반드시 수행한다.

## CHANGELOG 작성 규칙
- 형식: [Keep a Changelog](https://keepachangelog.com/)
- 섹션: `Added` / `Changed` / `Fixed` / `Removed`
- 각 항목 끝에 관련 태스크 `(GEN-####)` 를 표기한다.
- 평소에는 `[Unreleased]` 아래에 항목을 쌓고, 릴리즈 시점에 버전 섹션으로 확정한다.
