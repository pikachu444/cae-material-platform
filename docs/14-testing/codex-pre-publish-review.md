# Codex 독립 pre-publish 리뷰 게이트

Status: authoritative local publication gate for GitHub issue #119

## 목적과 경계

이 게이트는 로컬 `git push`와 Codex의 PR 생성·Ready 전환·병합 명령 전에 구현 세션과 분리된
읽기 전용 Codex 리뷰를 강제합니다. GitHub Actions, branch protection, OpenAI API key, 자동 수정,
자동 승인과 자동 병합은 범위가 아닙니다. 로컬 Codex 로그인 상태만 재사용합니다.

## 단일 실행 순서

`cmp-pre-publish` 하나가 다음 순서를 직렬로 실행합니다.

1. 기존 `origin/main...HEAD` documentation-impact 검사
2. clean worktree 확인과 base/HEAD/diff/변경 경로 계산
3. `git diff --check`와 전체 user-guide/link/image/manifest 검사
4. 독립 code review
5. UI 영향 변경일 때만 독립 visual review

앞 단계가 실패하면 뒤 단계는 실행하지 않습니다. 일반 Bash 명령은 게이트 대상이 아닙니다.
변경 경로는 documentation-impact와 reviewer가 같은 A/C/M/R/T/D name-status parser를 사용하며,
rename은 source와 destination을 모두 포함합니다.
`git commit`은 staged documentation-impact만 검사합니다. 무거운 pipeline은 `git push`,
`gh pr create`, `gh pr ready`, `gh pr merge`에만 적용합니다. commit과 publish를 한 shell 명령으로
묶으면 미래 commit을 검토할 수 없으므로 fail-closed 처리합니다.

`gh pr create`는 checked-out `HEAD`, 최신 remote `main`, 현재 origin repository만 허용합니다.
`--base main`을 반드시 명시해야 하고 `--head/-H`는 차단합니다. `gh pr ready/merge`는 `gh pr view`로 대상
PR의 head/base SHA를 읽고 로컬 `HEAD`와 `origin/main`에 일치할 때만 진행합니다. 독립 리뷰가 끝난
직후 대상 PR과 repository refs/diff/image 입력을 다시 수집해 처음 fingerprint 입력과 비교하므로,
다른 branch의 PASS나 리뷰 중 변경된 ref를 재사용할 수 없습니다. 환경 변수 assignment, `env`,
`command`, `sudo`, subshell/group wrapper로 실행한 publish 명령도 같은 gate로 분류합니다. 별도
`bash`/`cmd`/PowerShell 또는 `Start-Process` 안에 중첩한 publish 명령은 정확한 대상 결박이 불가능해
직접 실행하도록 차단합니다. 대상
혼동을 막기 위해 command-local 또는 ambient `GH_REPO`/`GH_HOST` override는 허용하지 않습니다.
PR URL selector와 `gh pr view`가 반환한 URL도 origin hostname/repository와 일치해야 합니다. Codex가
실행하는 `git push`는 reviewed root에서 `origin`과 checked-out branch를 명시한 형태만 허용하고,
`-C`, `-c`, `--config-env`, repository/config context global option, `GIT_*` assignment 또는
directory-changing wrapper는
다른 checkout의 PASS 재사용을 막기 위해 차단합니다. Versioned pre-push는 Git이 전달한 실제 remote
name/location이 configured `origin`인지 확인하고, stdin의 local/remote ref가 모두 checked-out branch이며
local SHA가 reviewed HEAD인지 리뷰 전후로 확인합니다.

## 독립 실행 계약

평상시 수동/pre-push 코드 리뷰는 `gpt-5.6-terra` + `medium`으로 변경 diff와 직접 연결된
contract/import/caller/test만 확인하며 timeout은 300초입니다. PR create/ready/merge 직전 최종 코드
리뷰는 `gpt-5.6-sol` + `high`, timeout 900초입니다. 실제 UI 소스 변경이 있을 때만 실행하는 시각
리뷰는 `gpt-5.6-sol` + `high`, timeout 900초입니다. 모델·reasoning·timeout은 fingerprint에 포함되어
동일 변경과 동일 profile의 완전한 PASS만 재사용합니다.

각 reviewer는 새 process에서 다음과 동등한 인자로 실행됩니다.

```text
codex exec --ephemeral --sandbox read-only \
  -c features.hooks=false \
  --model <profile-model> \
  -c 'model_reasoning_effort="<profile-effort>"' \
  --output-schema <schema> \
  --output-last-message <result> \
  --cd <git-root> -
```

prompt는 stdin으로 전달합니다. Visual reviewer에는 검토 대상 current PNG, 얻을 수 있는
`origin/main`의 before PNG와 관련 Granta/Material Modeler reference PNG를 `--image`로 전달합니다.
내부 process에는 `CMP_CODEX_REVIEW_ACTIVE=1`을 설정하고 project hooks를 꺼 재귀를 이중으로
차단합니다. reviewer 전후 `git status --porcelain`이 달라지면 PASS JSON이 있어도 실패합니다.

Prompt와 JSON Schema:

- [code review prompt](review-prompts/code-review.md)
- [visual review prompt](review-prompts/visual-review.md)
- `contracts/review/code-review.schema.json`
- `contracts/review/visual-review.schema.json`

허용 verdict는 `PASS`, `NEEDS_CHANGES`뿐입니다. `NEEDS_CHANGES`, timeout, 실행/인증 오류,
non-zero exit, 결과 파일 누락, invalid JSON, schema 위반과 시각 matrix의 28/32 또는 hard-gate
불일치는 모두 publish를 차단합니다. 상세 결과와 stdout/stderr는
`.cache/codex-review/<fingerprint>/`에 남으며 Git에는 포함되지 않습니다.
시각 결과의 screen 목록은 검토 대상으로 전달한 current 이미지의 repository-relative 경로와
manifest viewport에 정확히 1:1로 대응해야 하며, 누락·중복·임의 경로도 schema 오류와 같이 차단합니다.

## UI 영향과 시각 판정

다음 변경은 visual review를 실행합니다.

- test가 아닌 `apps/web/**/*.tsx`, `apps/web/**/*.css`
- test가 아닌 `apps/web/src/design/**/*.{ts,tsx,css}` 및
  `apps/web/src/components/**/*.{ts,tsx,css}`

문서, screenshot/manifest, UX reference만 변경한 경우에는 실제 UI 소스 변경이 아니므로 visual
review를 실행하지 않습니다. 이 파일들은 UI 소스 변경과 함께 변경될 때 deterministic 문서·이미지
검증 및 visual reviewer 입력으로 사용됩니다.

변경된 current PNG가 있으면 그 파일을 검토합니다. UI 영향은 있지만 변경 PNG가 없으면 current
manifest의 전체 캡처를 사용합니다. 이미지 누락·manifest 불일치는 앞선 deterministic 검사에서
차단합니다. Visual reviewer는 `visual-acceptance-matrix.md`의 V-01~V-16과 route별 hard gate만
사용하며 임의 점수나 미적 취향으로 차단할 수 없습니다.
obsolete current PNG를 삭제한 변경은 남아 있는 manifest 캡처를 current 입력으로 사용하고, 삭제된
PNG의 `origin/main` 사본을 before 비교 입력으로 보존합니다. Authoritative hard-gate 항목에 0점이
있으면 reviewer가 `hard_gate_pass`라고 응답해도 차단합니다.

## PASS cache

Fingerprint에는 다음이 포함됩니다.

- `origin/main` SHA, merge-base SHA, HEAD SHA와 binary diff SHA-256
- 변경 경로
- code/visual prompt와 schema SHA-256
- 관련 current/reference screenshot SHA-256과 삭제된 current screenshot 경로
- publication 대상의 hostname, repository, head/base SHA
- Codex CLI SHA-256, sandbox, hook, reasoning, timeout 설정

Code와 필요한 visual review까지 모두 PASS한 뒤에만 `pass.json`을 기록합니다. 부분 PASS와 실패는
재사용하지 않습니다. 같은 fingerprint의 result/schema/verdict를 다시 검증한 경우에만 cache hit로
허용합니다. diff, base, prompt, schema, image, CLI 또는 reviewer 설정이 바뀌면 새 리뷰가 필요합니다.
캐시를 삭제해도 결과 정확성은 바뀌지 않고 모델 호출만 다시 수행됩니다.

## 설치와 실행

Clone 후 저장소 루트에서 versioned pre-push hook을 한 번 설치하고 검증합니다.

```powershell
make install-hooks
make verify-hooks
```

Make가 없는 Windows 환경에서는 동일한 명령을 직접 실행합니다.

```powershell
uv run python scripts/install_git_hooks.py --root .
uv run python scripts/install_git_hooks.py --root . --check
```

Installer는 local `core.hooksPath`가 비어 있거나 이미 `.githooks`일 때만 설정합니다. 다른 hook
path를 덮어쓰지 않고 수동 통합을 요구합니다. 경로에 공백이 있어도 versioned shell hook은
`git rev-parse --show-toplevel` 결과를 인용하여 공통 `cmp-pre-publish`를 호출합니다.
Pre-push stdin도 공통 구현이 검사합니다. 한 번에 하나의 branch만 허용하며 local SHA가 검토한
현재 `HEAD`와 다르면 차단합니다. 다른 branch와 tag는 각각 checkout하고 별도 절차로 검토해야 합니다.

Codex에서는 `.codex/hooks.json` 변경 후 `/hooks`로 정확한 command를 검토하고 trust합니다.
수동 확인은 다음과 같습니다.

```powershell
make pre-publish
```

`codex`가 WindowsApps에 설치된 Windows 환경에서는 source CLI SHA-256과 정확히 일치하고
`codex-command-runner.exe`, `codex-windows-sandbox-setup.exe`가 같은 디렉터리에 있는 공식 local
runtime만 선택합니다. `codex.exe`만 단독 복사하면 read-only helper를 실행할 수 없으므로 허용하지
않습니다. 다른 설치 경로가 필요하면 기존 로그인 환경에서 `CMP_CODEX_EXECUTABLE`에 실행 파일의
전체 경로를 지정할 수 있습니다. 일치하는 runtime/helper나 인증이 없으면 우회 PASS 없이 차단합니다.

## 실패 해결

1. 출력된 상세 result/log 경로를 엽니다.
2. documentation 또는 deterministic 오류를 먼저 수정합니다.
3. reviewer finding의 path/line/evidence와 required action을 확인합니다.
4. 변경을 commit하고 `origin/main`을 최신으로 fetch한 뒤 다시 실행합니다.
5. 인증 실패는 같은 사용자 환경에서 `codex` 로그인 상태와 `codex exec --help`를 확인합니다.

Result 파일을 수동으로 PASS로 바꾸어도 fingerprint metadata, schema와 전체 PASS marker가 맞지 않으면
재사용되지 않습니다.
