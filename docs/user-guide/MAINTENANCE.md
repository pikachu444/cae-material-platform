# 사용자 가이드와 GUI 이미지 유지 규칙

사용자에게 보이는 route, navigation, form label, workflow step, plot, warning, mapping 또는
download 동작을 바꾸는 PR은 코드와 사용자 가이드 증거를 함께 갱신합니다.

## PR 필수 항목

1. 영향을 받는 `docs/user-guide/` 문서를 갱신합니다.
2. `screenshot-manifest.yaml`의 workflow/route/fixture/이미지 항목을 갱신합니다.
3. deterministic demo seed와 연결된 browser E2E를 실행합니다.
4. 1366×768과 1440×900에서 확인하고, 레이아웃이 확장되면 1920×1080도 캡처합니다.
5. token, confidential data, 개인 계정과 로컬 개인 경로가 이미지에 없는지 확인합니다.
6. 이미지가 해당 작업의 입력, 결과, 경고와 복구 흐름을 실제로 보여 주는지 확인합니다.

`make docs-capture`는 실행 중인 deterministic Compose demo에서 현재 대표 화면을 빈 sibling 임시
디렉터리에 생성합니다. 모든 파일, PNG 형식과 viewport 검증이 성공한 뒤에만
`docs/user-guide/images/current`를 교체합니다. `make docs-screenshots`는 Markdown 링크, 문서 분류,
navigation contract, current capture manifest, #167 reference manifest, 이미지 형식·크기·고아·중복을
검사합니다.

## 이미지 lifecycle

- `docs/user-guide/images/current/`에는 manifest에 등록한 현재 product route 캡처만 둡니다.
- #167의 승인 target은 `docs/17-evidence/images/issue-167-service-reference/`에 두고
  `docs/01-product/service-reference-manifest.yaml`로 등록합니다.
- retired 화면, 완료 Task 보고서, 중간 correction 캡처와 과거 캡처 스크립트는 working tree에서
  삭제합니다. 필요하면 Git 이력이나 병합 PR에서 복구합니다.
- Storybook과 임시 비교 캡처의 기본 출력은 Git에서 제외된 `.artifacts/`에 둡니다. 제품 가이드나
  승인 target으로 채택할 때만 해당 lifecycle manifest로 옮깁니다.
- 계산 결과나 mapping warning을 숨기려고 crop하지 않으며 실제 회사/고객 데이터를 사용하지 않습니다.
- 승인 target의 동일 바이트 중복은
  `docs/01-product/service-reference-duplicates.yaml`에 정확한 경로와 이유를 기록합니다.
- 모든 tracked Markdown은 `docs/documentation-manifest.yaml`에서 정확히 한 상태로 분류합니다.

## 로컬 강제와 Codex 훅

`.codex/hooks.json`은 commit 전 documentation-impact를 실행하고, push·PR·merge 전에는 문서,
diff, 링크, 이미지와 manifest 검사를 순서대로 실행합니다. 자동 hook은 LLM을 호출하지 않습니다.
자세한 계약은 [pre-publish 게이트](../14-testing/codex-pre-publish-review.md)를 참고하십시오.

```powershell
make docs-capture
make docs-screenshots
make docs-impact
make install-hooks
make verify-hooks
make pre-publish
```

모델 기반 독립 리뷰는 자동 검증에 포함되지 않으며 사용자의 사전 승인 후에만
`make pre-publish-review`로 실행합니다.
