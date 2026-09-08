# Connected reader

`@cmp/web-next` contains the RD-02 connected reader for the project-scoped Materials, Test Data, Processing Outputs, Models and Solver Cards routes. The ordinary live app reads the configured API through feature-owned adapters; it does not fall back to fixture data when the API is unavailable.

The feature boundaries are intentional:

- `features/materials` owns Material and Material State reads.
- `features/test-data` owns exact document, curve and JSON artifact reads.
- `features/processing-output` owns saved output, stage and provenance reads.
- `features/models` owns Material State model and canonical IR reads.
- `features/cards` owns the complete Solver Card index, 12-row display paging, family/material filters and exact card artifact reads.
- The `/neutral-materials` reader composes the Models adapter and Cards index to validate one exact Neutral Material document and follow its stored Processing Output, Test Data and native-card relations.
- `shared/api/http-client.ts` owns bearer transport, explicit local-demo sign-in, authorization-scoped query keys, error mapping and SHA-256 verification for downloads. It does not create an identity implicitly and keeps an authorized token after a 403.

Every detail request carries the selected revision pin. Card detail also carries the family route and validates aggregate ID, revision ID, content hash and native artifact hash before showing the result. Artifact downloads require and verify the server-provided `X-Content-SHA256` or `X-CMP-Card-SHA256` header before the browser saves bytes. Relations are displayed from stored IDs and revision pins, never inferred from a name, first row or latest result. Preview, expanded detail and return are URL states, so query, filter, page, selected identity, scroll position and focus can be recovered without regenerating a saved result.

Neutral Material JSON uses `X-Content-SHA256` as the canonical document semantic digest. Its adapter validates that digest and the `X-Neutral-Material-ID`/revision headers against the typed document; it does not compare raw HTTP response bytes to the semantic hash. The Material explorer shows only the current server page and expands stored Material → Material State → specimen/Test Data relations. A denied optional relation remains local to that reader and does not replace an authorized source or native artifact with a fallback.

The Solver Card index returns the complete authorized project scope; the connected reader applies title/family/material filters to that complete response and displays a stable 12-row page. The displayed count is the post-filter local scope, not a server facet. Unknown card schemas remain visible as unsupported rows with an explicit reason. Known neutral hyperelastic, generalized-Maxwell and tabulated-plasticity variants retain their typed family labels.

The connected workspace uses the package versions already installed in this repository: React Router 8.3.1 for URL-backed reader state, TanStack Query 5.102.8 for abortable reads and authorization-scoped caches, and Lucide 1.41.0 for the task rail. The existing Radix Dialog/Tooltip, React Hook Form, Zod and TanStack Table packages remain available for their owned future workflows; the current 12-row reader tables do not force a table abstraction, and the read-only processing surface does not prebuild a write form. No package or version was added for this correction pass.

Processing write controls are deliberately outside this reader. A future processing workflow should hand off typed, revision-pinned values in this order: selected Test Data revision → mapping profile revision → settings/solver pins → execution request → comparison/validation → saved Processing Output revision. The reader only consumes saved output and exposes its exact source and settings pins; adding a write form here would allow an unvalidated partial request to look like a saved engineering result.

## Running

From the repository root:

| Command | Scope |
| --- | --- |
| `npm run dev --workspace @cmp/web-next` | Live reader on `127.0.0.1:5174` |
| `npm run typecheck --workspace @cmp/web-next` | TypeScript check |
| `npm run build --workspace @cmp/web-next` | TypeScript check and live Vite build |
| `npm run test --workspace @cmp/web-next` | Unit/component tests |
| `npm run check:web-next` | Existing prototype checks |

The Vite `/api` proxy defaults to `http://127.0.0.1:8000`. Set `CMP_API_PROXY_TARGET`, for example `CMP_API_PROXY_TARGET=http://127.0.0.1:18000`, when running against another local API. Use **로컬 데모 연결** to request a demo bearer explicitly; normal reads use the existing session/bearer and otherwise surface the API's authorization state.

The September 8 correction keeps one shared preview header across the five connected readers. The
toolbar stays visible while identity, properties and curves scroll below it. Experiment JSON and
solver-card downloads are also available directly from the preview. Engineering labels remain in
their feature/display adapters; the header owns no server state. The plot changes axis ticks and
labels only: it neither smooths nor resamples saved points.

## 외부 테스트: Cloudflare

현재 임시 주소의 발급 상태는 [root README의 접속 주소 표](../../README.md#접속-주소와-시안-원본)에 기록합니다.
2026-09-08 기존 Docker 이미지로 시안과 실제 앱의 별도 외부 주소를 발급했습니다.
현재 사용 중인 Docker 실행·재시작·주소 확인 명령은 위 root README에 있습니다.
Docker 방식은 HTTP Host Header를 `localhost:4174`로 전달하므로 새 주소마다 Vite 설정을 바꿀 필요가 없습니다.
아래는 Docker 없이 네이티브 cloudflared를 쓰는 대안입니다. 이 방식은 새 호스트를 환경변수에 넣어 preview를 재시작합니다.

확인 기준: 2026-09-08. 현재 새 frontend는 `5174`, 이 문서의 외부 확인용 빌드 화면은 `4174`를 사용합니다.
현재 RD-02 API는 `18000`에서 실행 중입니다. 기본 Compose를 새로 실행한 환경이면 API 포트가 `8000`일 수 있으므로 실제 포트에 맞춥니다.
명령은 현재 작업 폴더인 `C:\SourceCodes\cae-material-platform-rd02`에서 실행합니다. 다른 checkout에서는 그 저장소 루트로 바꿉니다.

### 임시 주소로 격리 데모 확인

Quick Tunnel은 계정이나 소유 도메인 없이 임시 HTTPS 주소를 발급합니다. PC와 API, preview 서버, 터널이 계속 실행 중이어야 합니다.
공유기를 설정하거나 인바운드 포트를 열 필요는 없습니다. 주소는 고정 주소가 아니며 재시작하면 바뀔 수 있습니다.
[Cloudflare 공식 안내](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)

**이 앱의 데모 로그인은 비밀번호 없이 관리자 토큰을 발급합니다.** 화면에 수정 버튼이 없더라도 `/api`가 함께 전달됩니다.
따라서 이 절차는 공개되어도 되는 격리된 합성 데모에서만 사용합니다. 임시 URL은 접근 통제 수단이 아닙니다.
지금 작업 중인 DB나 비공개 자료를 그대로 열려면 아래의 Access 방식으로 먼저 접속자를 제한합니다.

1. [공식 Windows 다운로드](https://developers.cloudflare.com/tunnel/downloads/)에서 환경에 맞는 MSI를 설치합니다.
   새 PowerShell을 열고 `cloudflared --version`으로 설치를 확인합니다. 설치가 PATH를 등록하지 않았다면 설치된 `cloudflared.exe`의 전체 경로를 사용합니다.

2. **터미널 A**에서 새 frontend를 빌드합니다. 기존 API는 실행 상태로 둡니다.

   ```powershell
   Set-Location C:\SourceCodes\cae-material-platform-rd02
   npm.cmd run build --workspace @cmp/web-next
   ```

3. **터미널 B**에서 터널을 실행하고 출력된 `https://….trycloudflare.com` 주소를 복사합니다.

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:4174
   ```

   다음 단계에서 preview가 켜지기 전에는 이 주소가 502를 반환할 수 있습니다. 터미널 B는 열어 둡니다.

4. **터미널 A**에서 복사한 주소를 입력하고 빌드 화면을 실행합니다.

   ```powershell
   $cmpPreviewUrl = (Read-Host '터미널 B에 나온 https:// 임시 주소') -as [uri]
   $env:__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS = $cmpPreviewUrl.DnsSafeHost
   $env:CMP_API_PROXY_TARGET = 'http://127.0.0.1:18000'
   npm.cmd exec --workspace @cmp/web-next -- vite preview --host 127.0.0.1 --port 4174 --strictPort
   ```

   발급받은 호스트 하나만 허용합니다. `allowedHosts: true`나 `.trycloudflare.com` 전체 허용은 설정하지 않습니다.
   이 환경변수는 이 PowerShell에서 시작한 프로세스에만 적용되며 저장소 설정을 변경하지 않습니다.
   Vite preview는 이 저장소의 `/api` proxy와 허용 호스트 설정을 이어받습니다.
   [Vite 호스트 설정](https://vite.dev/config/server-options#server-allowedhosts), [preview 설정](https://vite.dev/config/preview-options)

5. 휴대전화의 Wi-Fi를 끄거나 다른 외부 네트워크에서 임시 주소의 `/materials`를 엽니다.
   **로컬 데모 연결**을 누른 뒤 소재 선택 → 미리보기 → 확대 → 목록 복귀, 실험 조회와 카드 다운로드를 확인합니다.
   외부 기기의 `127.0.0.1`은 그 기기 자신이므로 브라우저에는 반드시 발급된 HTTPS 주소를 입력합니다.

6. 확인을 마치면 **터미널 B에서 Ctrl+C**로 외부 접속부터 끊고, 터미널 A의 preview도 Ctrl+C로 종료합니다.
   기존 로컬 개발 서버와 API는 별개입니다. 수정한 화면을 다시 공유할 때는 빌드를 다시 실행합니다.

`vite preview`는 빌드 확인용 서버이며 상시 운영 서버가 아닙니다. 이 절차는 배포·자동 시작 설정을 만들지 않습니다.

### 지정한 사람만 접속시키기

현재 작업 데이터로 반복 테스트하려면 **Cloudflare Tunnel + Access**를 사용합니다.
Cloudflare 계정과 이 계정에서 사용할 수 있는 도메인을 준비한 뒤 다음 순서로 설정합니다.

1. Access에 테스트 호스트의 Self-hosted 애플리케이션을 만들고 본인·테스터 이메일만 허용하는 정책을 설정합니다.
2. Tunnel에서 해당 호스트를 `http://127.0.0.1:4174`로 연결하고 **Protect with Access**를 설정합니다.
3. 위 preview 명령의 허용 호스트를 그 고정 호스트로 바꿔 실행합니다. connector 실행 명령은 Cloudflare 대시보드가 제공하는 해당 터널 명령을 사용합니다.
4. 로그아웃한 외부 브라우저에서 앱과 `/api` 모두 인증 전에 차단되는지 확인한 후 공유합니다.

Access 로그인과 앱 내부 권한은 별개입니다. 데모 로그인은 여전히 관리자 권한이므로, 실제 사용자 권한 테스트에는 별도 계정을 사용해야 합니다.
터널 토큰은 README나 Git에 기록하지 않습니다.
[Cloudflare Access 공식 절차](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)

### 접속이 안 될 때

| 증상 | 확인할 곳 |
| --- | --- |
| 임시 주소에서 502 | API가 아니라 `4174` preview가 실행 중인지, 터널의 대상 포트가 맞는지 확인합니다. |
| `Blocked request. This host is not allowed` | 새로 발급된 정확한 호스트를 환경변수에 넣고 preview를 재시작합니다. 터널을 다시 켰다면 주소도 다시 확인합니다. |
| 화면만 보이고 데이터가 안 나옴 | 로컬 `http://127.0.0.1:18000/api/v1/health`와 preview의 `/api/v1/health`를 확인합니다. API 포트가 `8000`이면 proxy 환경변수도 맞춥니다. |
| 세션 만료·연결 안 됨 | 현재 데모 토큰은 15분 유효합니다. 해당 브라우저 탭에서 로컬 데모 연결을 다시 누릅니다. |
| 예전 화면이 보임 | `apps/web-next`를 다시 빌드했는지, `4174`가 이 checkout에서 실행되는지 확인합니다. |
| Quick Tunnel 생성 실패 | `%USERPROFILE%\.cloudflared\config.yaml`이 있으면 기존 설정과 충돌할 수 있습니다. 기존 설정을 삭제하지 말고 보존한 상태에서 공식 안내에 따라 분리합니다. |

Quick Tunnel은 동시 처리 중인 요청 200개 제한이 있고 SSE를 지원하지 않습니다. 현재 조회·다운로드는 일반 HTTP 요청입니다.
추후 SSE로 처리 진행률을 전달한다면 Quick Tunnel로 그 동작까지 검증할 수 없습니다.
2026-09-08 외부 HTTPS 주소로 시안 HTML·JavaScript와 실제 앱 화면·`/api/v1/health`의 200 응답을 확인했습니다.
로컬에서는 지정하지 않은 호스트가 403을 반환하는 것도 확인했습니다.
