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

`make docs-screenshots`는 문서 상태 분류, guide link, 전역 navigation contract, 현재/역사 이미지
분리, manifest와 PNG 크기·viewport drift를 검증한다. 화면 capture 자체는 deterministic demo
fixture와 연결된 browser E2E로 수행하고 PR 본문에 token/confidential-data 검토 결과를 기록한다.

## 이미지 변경 원칙

- 계산 결과나 mapping warning을 숨기기 위해 crop하지 않는다.
- 실제 회사/고객 데이터를 사용하지 않는다.
- 기능이 제거됐으면 과거 이미지를 최신 가이드에서 재사용하지 않는다.
- 역사적 E2E 문서의 이미지는 증거이므로 덮어쓰지 않는다. 새 검증일 directory와 문서를 만든다.
- 현재 화면에서 제외된 manifest 항목은 `docs/15-demo/screenshot-archive.yaml`에 보존한다.
- 문서 분류는 `docs/documentation-manifest.yaml`에 등록하고 누락된 Markdown을 만들지 않는다.

## 로컬 강제와 Codex 훅

`.codex/hooks.json`은 Codex의 `git commit`, `git push`, `gh pr create`, `gh pr merge` 직전과 작업
종료 시 `cmp-check-doc-impact`를 실행합니다. 저장소를 처음 열거나 hook 파일이 바뀌면 `/hooks`에서
프로젝트 hook의 정확한 내용을 검토하고 trust해야 합니다. 신뢰하지 않은 프로젝트 hook은 실행되지
않습니다.

```powershell
make docs-screenshots
make docs-impact
```

일반 Git pre-commit hook은 설치하지 않습니다. 따라서 Codex 밖에서 직접 실행한 Git 명령은 로컬
hook을 우회할 수 있으며, `scripts/ci.sh`의 `origin/main...HEAD` 검사가 같은 문서 영향 계약을 다시
확인합니다.
