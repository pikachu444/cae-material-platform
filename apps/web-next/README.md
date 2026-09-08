# 새 조회 앱 실행과 개발

`apps/web-next`는 실제 API에 연결된 RD-02 조회 앱입니다. 소재·실험·저장 처리 결과·모델·솔버 카드를 조회하고
기존 파일을 내려받습니다. API 연결 실패를 합성 시안으로 숨기지 않습니다.
등록·처리 실행·평균화·모델/카드 생성의 새 화면과 기존 앱의 일괄 전환은 아직 남아 있습니다.

[실제 앱과 시안 접속 주소](../../README.md#접속-주소와-시안-원본),
[현재 구현 화면](../../README.md#현재-화면--새-조회-앱),
[현재 작업과 남은 범위](../../docs/planning/frontend-redesign-status.md)를 참고합니다.

## 실행

저장소 루트에서 실행합니다. 기존 API가 준비되어 있어야 합니다.

```powershell
npm ci --workspaces --include-workspace-root
$env:CMP_API_PROXY_TARGET = 'http://127.0.0.1:18000'
npm run dev --workspace @cmp/web-next
```

이 예시의 `18000`은 현재 RD-02 검토 환경입니다. 기본 Compose API라면 `8000`으로 바꿉니다.
같은 PC에서 <http://127.0.0.1:5174/materials>를 열고 **로컬 데모 연결**을 누릅니다.
원격 기기에서는 localhost 대신 root README의 외부 HTTPS 주소를 사용합니다.

| 명령 | 대상 |
| --- | --- |
| `npm run build --workspace @cmp/web-next` | TypeScript 검사와 실제 연결 앱 빌드, `dist` 출력 |
| `npm run test --workspace @cmp/web-next` | 새 앱 단위·component 검사 |
| `npm run typecheck --workspace @cmp/web-next` | TypeScript 검사만 실행 |
| `npm run check:web-next` | 별도 prototype 모드 검사; 실제 API 검증은 아님 |

Docker 터널로 빌드 결과를 공유할 때는 위 build 후 다음 서버를 실행합니다.

```powershell
$env:CMP_API_PROXY_TARGET = 'http://127.0.0.1:18000'
npm exec --workspace @cmp/web-next -- vite preview --host 0.0.0.0 --port 4174 --strictPort
```

`/api`도 이 preview의 proxy를 거칩니다. 화면을 수정했다면 공유 전에 다시 빌드합니다.
기존 앱은 `5173`, 새 개발 앱은 `5174`, 공유용 빌드는 `4174`, 독립 시안은 `8767`로 구분합니다.

## 코드 책임과 데이터 처리

| 위치 | 책임 |
| --- | --- |
| `app` | 경로·앱 구성·provider |
| `features/materials` | 소재·소재 상태 조회와 물성 표시 |
| `features/test-data` | 저장 실험·조건·곡선·실험 파일 |
| `features/processing-output` | 저장 처리 결과와 사용한 설정·입력 연결 |
| `features/models` | 저장 소재 모델과 연결 자료 조회 |
| `features/cards` | 저장 카드 목록·상세·물성·솔버 파일 다운로드 |
| `shared` | 실제 재사용하는 통신·UI primitive·공학 표시 component |

서버 객체는 TanStack Query, 검색·필터·페이지·선택·상세는 URL, 일시적인 열림과 초점은 지역 UI가 관리합니다.
미리보기·확대 상세·목록 복귀에서 검색조건과 선택을 이어갑니다. 조건과 물성값을 제목에 합치지 않습니다.

기존 backend가 요구하는 정확한 ID와 저장본 pin은 adapter가 검증합니다. 이름이나 첫 행으로 연결을 추측하지 않습니다.
다운로드는 서버의 파일 해시를 확인하고 저장된 bytes를 보존합니다. 교환용 모델 문서는 문서의 의미 해시를 검증하며,
HTTP 응답 bytes 해시와 혼동하지 않습니다. 이런 검증용 ID·해시를 사용자 상세 정보로 나열하지 않습니다.

처리 설정·Prony 계수·적용 범위·변환·근사·미지원은 읽을 수 있는 항목과 표로 표시합니다.
실제 솔버 파일 미리보기의 내용은 변경하지 않습니다. 소재만 리비전 관리한다는 목표 정책은
[데이터 정책](../../docs/product/data-management-policy.md)을 따르며, 기존 DB/API 이관은 후속 작업입니다.

카드 API는 권한이 허용하는 프로젝트 목록 전체를 반환합니다. 현재 reader는 이 응답을 대상으로
필터·정렬하고 12개씩 표시합니다. 건수는 필터 후의 목록 크기이며 서버 facet 또는 대규모 성능 보장이 아닙니다.
미지원 카드 계열은 이유를 표시하고, 접근이 거절된 관련 자료 때문에 허용된 원본 다운로드까지 대체하지 않습니다.

React Router·TanStack Query·Lucide를 현재 reader에서 사용합니다. Radix Dialog/Tooltip, React Hook Form,
Zod, TanStack Table은 설치된 기반이며 실제 업무가 요구하는 곳에 적용합니다. 처리 입력 화면을 reader에 미리 만들거나
공통 framework부터 늘리지 않습니다. 상태·API·CSS의 소유권은 [frontend architecture](../../docs/architecture/frontend-architecture.md)를 따릅니다.

## 외부 테스트: Cloudflare

현재 임시 주소의 발급 상태는 [root README의 접속 주소 표](../../README.md#접속-주소와-시안-원본)에 기록합니다.
2026-09-08 기존 Docker 이미지로 시안과 실제 앱의 별도 외부 주소를 발급했습니다.
현재 사용 중인 Docker 실행·재시작·주소 확인 명령은 [임시 주소 다시 열기](../../README.md#임시-주소-다시-열기)에 있습니다.
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
