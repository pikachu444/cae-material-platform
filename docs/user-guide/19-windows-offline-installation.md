# Windows 11 x64 오프라인 설치와 운영

이 절차는 Windows 11 x64 PC용입니다. Windows Server OS와 Arm64는 지원 범위가 아닙니다. 설치된
제품은 Docker, WSL, Hyper-V, Windows service와 Node를 사용하지 않습니다.

## 가장 짧은 Demo 설치

1. 준비된 `CAE-Material-Platform-<version>-demo-windows-x64.zip`을 대상 PC에 복사합니다.
2. ZIP을 로컬 폴더에 완전히 해제합니다. ZIP 내부에서 직접 실행하지 않습니다.
3. `Install.cmd`를 실행합니다. 일반 실행은 `%LOCALAPPDATA%` 아래 user scope를 사용합니다. 이미
   관리자로 실행 중일 때만 `%ProgramFiles%`의 machine scope를 사용하며 UAC를 요청하지 않습니다.
4. bundle manifest와 모든 payload SHA-256이 맞아야 설치가 시작됩니다. 완료 후 열린 브라우저에서
   `DP780`을 검색하고 CAE Cards의 Abaqus 또는 OpenRadioss card를 내려받습니다.

설치 control 폴더에는 다음 진입점이 생깁니다.

```text
Start.cmd       제품 기동과 브라우저 열기
Stop.cmd        process 중지, DB와 object data 보존
Status.cmd      local/LAN URL, 수신 주소, process와 firewall 상태
Uninstall.cmd   installer 소유 프로그램·진입점·방화벽 규칙 제거, data 보존
```

같은 bundle의 `Install.cmd`를 다시 실행해도 설치 scope, 기존 수신 주소, private PostgreSQL cluster,
object data와 Server 설정을 보존합니다. 중복 cluster나 process를 만들지 않습니다.
Demo와 Server는 보존 data의 의미가 다르므로 기존 설치 위에서 profile을 바꾸는 것은 거부됩니다.
전환하려면 먼저 제거한 뒤 보존 data 폴더를 별도로 옮기고 다른 profile을 새로 설치합니다.

## LAN 접속과 Windows Defender Firewall

기본 설치는 loopback 주소를 사용합니다. 같은 Private/Domain 사설망의 다른 PC에서 접속하려면 대상
PC의 명시적인 private IPv4를 한 번 지정합니다.

```cmd
Install.cmd --listen-address 192.168.10.12
```

설치기는 이름·설명·group·설치된 Python 경로까지 일치하는 `CAE-Material-Platform-Web` 규칙 하나만
소유합니다. 관리자 실행이면 TCP 5173 inbound를 Private/Domain profile과 `LocalSubnet`으로 제한해
멱등하게 설정합니다. API 8000, PostgreSQL 54329,
OTLP 4318, metrics 8889는 열지 않습니다. 일반 실행 또는 조직 정책 차단 시 로컬 설치·기동은
유지하고 화면과 `state\logs\installer.log`에 IT가 관리자 권한으로 실행할 정확한 명령을 남깁니다.

```cmd
netsh advfirewall firewall add rule name="CAE-Material-Platform-Web" description="CAE Material Platform Web (installer-owned)" group="CAE Material Platform Offline Installer" dir=in action=allow protocol=TCP localport=5173 profile=private,domain remoteip=localsubnet program="<설치 program>\python\python.exe"
```

`Status.cmd`에서 `present=true`와 `remote_access=Private/Domain LocalSubnet`을 확인한 뒤 다른 PC의
브라우저에서 표시된 LAN URL을 엽니다. 제거는 이름과 설치 프로그램 경로가 모두 일치하는 규칙만
삭제합니다. 같은 이름의 사용자·조직 규칙은 보존합니다. 일반 권한으로 제거해 규칙을 삭제할 수
없으면 IT용 exact-path 삭제 명령을 출력하며 다른 방화벽 규칙은 바꾸지 않습니다.

## 연결된 환경에서 bundle 생성

builder는 Python 3.12.14, uv 0.12.5, Node 24.19.0, npm 11.17.0과 PostgreSQL 16.15 Windows x64의
URL·architecture·SHA-256을 `deploy/windows/toolchain-manifest.json`에서 읽습니다. 저장소 버전 파일과
다르거나 다운로드가 누락·변조되면 압축 해제 또는 실행 전에 중단합니다.

```powershell
uv run python scripts/build_windows_offline_bundle.py `
  --profile demo `
  --output-dir C:\cmp-bundles
```

Node/npm은 격리한 임시 source에서 Web production asset을 만들 때만 사용합니다. uv는 locked Python
dependency와 application wheel을 portable Python에 설치할 때만 사용합니다. 생성된 ZIP에는 이 세
build tool을 넣지 않습니다. ZIP, archive, 생성 secret과 실제 인증 설정은 Git에 추가하지 않습니다.

## Server bundle

Server 입력 JSON에는 실제 OIDC issuer/audience/JWKS와 governed S3 bucket/KMS 설정을 넣습니다.
password, client secret, `CMP_DEMO_*`, `CMP_PLUGIN_*`는 builder가 거부합니다. DB/application secret과
worker token은 대상 PC에서 안전한 난수로 처음 한 번 생성하고 ACL을 제한하며 재설치 때 보존합니다.

```powershell
uv run python scripts/build_windows_offline_bundle.py `
  --profile server `
  --server-auth-config C:\secure\cmp-server-auth.json `
  --output-dir C:\cmp-bundles
```

인증 입력이 빠지거나 잘못되면 Server는 Demo identity·synthetic seed·수동 bearer token으로 fallback하지
않습니다. 현재 SPA OIDC Authorization Code+PKCE login/callback은 #215의 미구현 선행 계약이므로
Server 기동은 그 기능이 병합되기 전까지 정확한 오류로 중단됩니다.

## 실패 진단과 복구

- `offline bundle manifest checksum mismatch` 또는 `file is missing/checksum mismatch`: ZIP을 다시
  전달받고 완전히 해제합니다. `Install.cmd`는 전체 payload를 담은 고정 checksum archive를 Windows
  `certutil`로 먼저 확인하므로 Python loader DLL을 포함한 손상된 바이너리는 실행되지 않습니다.
- `port is unavailable`: `Status.cmd`와 표시된 5173/8000/54329 소유 process를 IT에 전달합니다.
  설치기는 알 수 없는 process를 종료하지 않습니다.
- `execution policy or antivirus may have blocked`: `.cmd`도 조직 정책에 차단됐는지, 격리 기록과
  `installer.log`의 정확한 파일·오류 번호를 IT에 전달합니다. 보안 제품을 자동으로 끄지 않습니다.
- `firewall ... local-only`: 로컬 브라우저 사용은 유지됩니다. 위의 rule name, TCP 5173,
  Private/Domain, LocalSubnet 명령을 IT에 전달합니다.
- Server auth 오류: 입력 JSON과 외부 IdP/S3 설정을 수정한 새 Server bundle을 사용합니다. Demo로
  전환하지 않습니다.

실패한 설치를 다시 실행해도 `data` 아래 DB와 object store는 지우지 않습니다. `Uninstall.cmd`도
동일하게 data를 보존하므로 완전 삭제가 필요한 경우에는 보존 자료를 확인한 뒤 별도 승인된 수동
절차를 사용합니다.
