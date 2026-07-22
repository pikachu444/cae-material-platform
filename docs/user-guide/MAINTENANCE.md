# 사용자 가이드와 GUI 이미지 유지 규칙

사용자에게 보이는 route, navigation, form label, workflow step, plot, warning, mapping 또는
download 동작을 바꾸는 PR은 코드만으로 완료되지 않는다.

## PR 필수 항목

1. 영향을 받는 `docs/user-guide/` 문서를 갱신한다.
2. 현재 화면은 `screenshot-manifest.yaml`의 workflow/route/fixture/이미지 항목을 갱신한다.
3. deterministic demo seed와 연결된 browser E2E를 실행한다.
4. 기본 1440x900 desktop viewport에서 capture한다. Codex in-app browser처럼 host가 viewport를
   고정하면 manifest에 실제 `width`/`height`를 기록하고 최소 800x700을 유지한다.
5. token, confidential data, 개인 계정과 로컬 개인 경로가 이미지에 없는지 검토한다.
6. 이미지가 단순 장식이 아니라 해당 작업의 입력·결과·warning을 보여 주는지 확인한다.

`make docs-capture`는 실행 중인 deterministic Compose demo에서 현재 대표 화면을 빈 sibling 임시
디렉터리에 생성합니다. 선언된 모든 파일·PNG 형식·viewport 검증이 성공한 뒤에만
`docs/user-guide/images/current`를 교체하므로, 이전 출력이 누락된 새 캡처를 대신할 수 없습니다.
`make docs-screenshots`는 모든 Markdown 내부 링크, 문서 상태 분류, 전역 navigation contract,
현재/역사 이미지 분리, current/archive/구조화 이미지 manifest, capture-script 출력, 이미지
형식·크기를 검증합니다. 고아 검사는 파일명 문자열이 아니라 해석된 repository-relative 전체 경로로
수행하며, SHA-256 중복은 manifest에 명시한 1 current ↔ 1 historical 경로 쌍만 허용합니다.

## 이미지 변경 원칙

- 계산 결과나 mapping warning을 숨기기 위해 crop하지 않는다.
- 실제 회사/고객 데이터를 사용하지 않는다.
- 기능이 제거됐으면 과거 이미지를 최신 가이드에서 재사용하지 않는다.
- 역사적 E2E 문서의 이미지는 증거이므로 덮어쓰지 않는다. 새 검증일 directory와 문서를 만든다.
- 현재 화면에서 제외된 manifest 항목은 `docs/17-evidence/screenshot-archive.yaml`에 보존한다.
- 과거 Task 보고서·이미지·캡처 스크립트는 `docs/17-evidence`에 두고 현재 가이드에서 직접
  사용하지 않는다.
- 문서 분류는 `docs/documentation-manifest.yaml`에 등록하고 누락된 Markdown을 만들지 않는다.

## 로컬 강제와 Codex 훅

`.codex/hooks.json`은 Codex의 `git commit` 전에 기존 documentation-impact를 실행하고, `git push`,
`gh pr create`, `gh pr ready`, `gh pr merge` 전에는 하나의 pipeline에서 documentation-impact,
독립 read-only code review, UI 영향 시 독립 visual review를 순서대로 실행합니다. 작업 종료 시 기존
worktree documentation-impact 차단도 유지합니다. 저장소를 처음 열거나 hook 파일이 바뀌면
`/hooks`에서 프로젝트 hook의 정확한 내용을 검토하고 trust해야 합니다. 자세한 cache·실패 계약은
[독립 pre-publish 리뷰 게이트](../14-testing/codex-pre-publish-review.md)를 참고하십시오.

```powershell
make docs-capture
make docs-screenshots
make docs-impact
make install-hooks
make verify-hooks
make pre-publish
```

일반 Git pre-commit hook은 설치하지 않습니다. 대신 versioned `.githooks/pre-push`를 한 번 설치하면
Codex 밖의 직접 `git push`도 같은 `cmp-pre-publish` 구현을 호출합니다. Installer는 기존 custom
hook path를 자동으로 덮어쓰지 않습니다. `scripts/ci.sh`의 `origin/main...HEAD` 문서 검사는 별도
방어선으로 유지합니다.
