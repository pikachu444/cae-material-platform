# Pre-publish 게이트와 독립 리뷰 실험

Status: automatic model review disabled; GitHub issue #119 reopened for redesign

## 현재 자동 게이트

로컬 `git push`와 Codex의 `gh pr create`, `gh pr ready`, `gh pr merge` 직전에는
`cmp-pre-publish` 하나가 다음 순서로 실행됩니다.

1. `origin/main...HEAD` documentation-impact 검사
2. clean worktree와 base/HEAD/diff/변경 경로 확인
3. `git diff --check`와 전체 user-guide/link/image/manifest 검사

앞 단계가 실패하면 뒤 단계는 실행하지 않습니다. 자동 경로는 `codex exec`나 다른 LLM reviewer를
시작하지 않습니다. `.githooks/pre-push`와 `.codex/hooks/pre_publish_gate.py` 모두
`independent_reviews=False`인 기본 모드를 사용합니다.

Storybook story, fixture와 `.storybook/` 전용 CSS는 제품 화면 source로 분류하지 않는다. 제품
route가 아직 소비하지 않는 shared design foundation은 제품 소유자가 범위를 명시적으로 승인한
경우에만 [documentation-impact 예외 폴더](documentation-impact-exceptions/)의 issue-number YAML로
current user-guide 영향 N/A를 기록할 수 있다. 확인서는 정확한 issue, `origin/main` merge-base, visual
file, unconsumed module과 보존 검증 대상 CSS만 선언한다. 검사기가 base/current CSS를 비교해 기존
declaration의 계산값 보존을 증명하고 새 selector를 직접 도출한 뒤 모든 제품 CSS/TS/TSX 소비자를
검색한다. wildcard, route/feature source, 실제 제품 consumer 또는 증명되지 않은 기존 화면 변화는
허용하지 않는다. 다음 route가 foundation을 소비하는 변경부터 일반 user-guide·current
PNG·screenshot manifest gate를 다시 적용한다.

이미 독립 감사와 제품 소유자의 `no-visible-change` 판정을 받은 app composition 분리는
`origin/main`에 먼저 병합된 issue-owned 확인서가 정확한 한 diff를 지문으로 고정한 경우에만
예외가 될 수 있다. 검사기는 실제 merge-base에서 visual patch와 전체 attested patch의 SHA-256을
다시 계산하고, visual path·base에 없던 composition target·characterization test·navigation
contract를 확인서와 대조한다. 확인서 자체는 지문에서 제외하되 visual diff와 같은 변경에서 새로
제출하거나 고칠 수 없다. base, path, test, contract, digest가 다르거나 CSS·route·style source가
하나라도 더 바뀌면 일반 current user-guide·5-viewport screenshot gate로 fail-closed 처리한다.

`git commit`은 staged documentation-impact만 검사합니다. commit과 publish를 한 shell 명령으로
묶으면 미래 commit을 검사할 수 없으므로 fail-closed 처리합니다. 일반 Bash 명령은 게이트 대상이
아닙니다.

`gh pr create`는 checked-out `HEAD`, 최신 remote `main`, 현재 origin repository만 허용합니다.
`--base main`을 명시해야 하며 `--head/-H`는 차단합니다. `gh pr ready/merge`는 대상 PR의
head/base SHA가 로컬 `HEAD`와 `origin/main`에 일치해야 합니다. Versioned pre-push hook은 Git이
전달한 remote와 ref가 현재 origin/branch/HEAD에 결박됐는지 검사 전후로 확인합니다.

## 자동 모델 리뷰를 중단한 이유

PR #120에서 도입한 자동 독립 리뷰는 실제 호출 중 예상보다 큰 token을 소비했습니다. 설치된 CLI가
실행 중 사용량을 강제로 중단하는 hard token cap을 제공하지 않는데도 사후 usage 검사를 상한처럼
설명한 것은 잘못이었습니다. timeout은 대기 시간만 제한하며 이미 소비된 token을 회수하거나
실시간으로 제한하지 않습니다.

또한 같은 diff가 publication action/profile별로 다시 검토됐고, reviewer가 bounded diff를 넘어
repository를 탐색했으며, raw shell command 문자열 해석이 복잡해졌습니다. 이 상태로 자동 호출을
유지하지 않습니다.

## 명시적 opt-in 독립 리뷰

독립 reviewer 구현과 schema/cache는 회귀 분석을 위해 남겨 두지만 자동 hook에서는 도달할 수
없습니다. 사용자가 비용과 범위를 확인하고 사전 승인한 경우에만 다음 명령을 실행합니다.

```powershell
make pre-publish-review
```

이는 다음 명령과 같습니다.

```powershell
uv run cmp-pre-publish --root . --trigger manual --independent-review
```

opt-in code review는 `gpt-5.6-terra` + `medium`, UI source 변경의 visual review는
`gpt-5.6-sol` + `high` profile을 사용합니다. reviewer는 새 `codex exec --ephemeral`,
read-only sandbox, `features.hooks=false`로 실행됩니다. 오류, timeout, 인증 실패, invalid JSON,
schema 위반과 `NEEDS_CHANGES`는 opt-in 명령을 실패시킵니다.

구현에 기록된 `max_tokens`와 실행 후 usage 검사는 live token hard cap이 아닙니다. 이를 비용
보장으로 표현하거나 취급해서는 안 됩니다. 자동 재시도는 허용하지 않습니다.

## Opt-in visual review와 cache

`--independent-review`를 명시했고 test가 아닌 `apps/web/**/*.tsx` 또는 `apps/web/**/*.css` 등 실제
UI source가 변경된 경우에만 visual reviewer가 실행됩니다. 문서나 screenshot만 바뀐 경우에는
실행하지 않습니다. current manifest의 대상 PNG와 가능한 base/reference PNG를 사용하고,
authoritative visual matrix의 hard gate와 85/100 기준만 적용합니다.

PASS cache fingerprint에는 base/HEAD/diff, prompt/schema, reviewer profile, current/reference image,
publication target이 포함됩니다. 실패 결과는 재사용하지 않습니다. 이 cache는 opt-in reviewer에만
적용되며 자동 결정적 검사는 비용이 작으므로 매번 실행합니다.

## 설치와 확인

Clone 후 versioned deterministic pre-push hook을 설치하고 검증합니다.

```powershell
make install-hooks
make verify-hooks
make pre-publish
```

Make가 없는 Windows 환경에서는 다음을 사용합니다.

```powershell
uv run python scripts/install_git_hooks.py --root .
uv run python scripts/install_git_hooks.py --root . --check
uv run cmp-pre-publish --root . --trigger manual
```

`make pre-publish`와 기본 CLI에는 `--independent-review`가 없으며 모델을 호출하지 않습니다.
Codex에서는 `.codex/hooks.json` 변경 후 `/hooks`에서 정확한 command를 검토하고 trust합니다.

## 남은 #119 재설계 조건

자동 LLM review를 다시 활성화하려면 다음을 모두 별도 PR에서 충족해야 합니다.

1. raw shell command 정규식 가로채기 대신 대상 branch/PR을 구조적으로 결박하는 전용 publish
   command를 제공한다.
2. exact diff당 code review를 한 번만 실행하고 create/ready/merge가 같은 결과를 재사용하도록
   stage별 cache를 분리한다.
3. visual review는 실제 UI source가 바뀐 route와 viewport에만 제한하고 code review cache와
   독립적으로 관리한다.
4. reviewer가 repository 탐색 도구를 사용할 수 없도록 완전한 bounded input을 제공하고 입력
   byte 수를 호출 전에 제한한다.
5. CLI가 live token hard cap을 제공하지 않으면 token cap을 보장한다고 표현하지 않는다. timeout,
   retry 0회, 한 번의 호출 범위와 실제 usage를 별도로 공개한다.
6. 모델 호출을 대체한 회귀 테스트를 먼저 통과시키고, 실제 smoke test는 사용자의 명시적 승인
   후 정확히 한 번만 수행한다.
7. 실패·timeout·인증 오류가 자동 재시도나 다른 profile 재호출로 이어지지 않게 한다.
8. automatic hook 재활성화는 실제 smoke 결과와 예상 비용을 PR에 공개하고 별도 승인을 받은 뒤
   진행한다.

## 실패 해결

1. documentation 또는 deterministic 오류를 먼저 수정합니다.
2. branch, remote main과 PR head/base가 바뀌었으면 fetch 후 다시 실행합니다.
3. current screenshot, Markdown link와 manifest 불일치를 수정합니다.
4. non-user-visible foundation이라면 issue-owned 확인서의 base SHA와 정확한 path를 확인합니다.
   product consumer와 computed appearance 보존은 확인서의 자기신고가 아니라 검사기의 base/current
   CSS 비교와 전체 CSS/TS/TSX 검색으로 증명되어야 합니다.
   composition attestation이라면 확인서가 `origin/main`에 선행하고 실제 range patch digest와
   target/test/navigation-contract 집합이 모두 일치하는지 확인합니다. frontend guard baseline의
   `sourceSha`는 fingerprint에서만 고정 sentinel로 정규화하되 실제 값은 merge-base와 정확히
   일치해야 하며, baseline의 나머지 모든 바이트는 그대로 fingerprint에 결박합니다.
5. opt-in reviewer를 실행했다면 `.cache/codex-review/<fingerprint>/`의 result/log에서
   path/line/evidence를 확인합니다.
