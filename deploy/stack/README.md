# 공통 Stack CLI

`cmp-stack`은 [versioned topology](topology.yaml)의 같은 service·port·volume 계약으로 Compose 또는
Windows host process를 관리합니다. profile과 runtime은 항상 명시하며 자동 추측하지 않습니다.

```powershell
uv run cmp-stack --profile demo --runtime compose doctor
uv run cmp-stack --profile demo --runtime compose up
uv run cmp-stack --profile demo --runtime compose status
uv run cmp-stack --profile demo --runtime compose logs
uv run cmp-stack --profile demo --runtime compose down
```

`deploy/compose/docker-compose.demo.yml`은 topology의 생성 결과입니다. 직접 고치지 않고 다음
명령으로 drift를 확인하거나 변경된 topology를 반영합니다.

```powershell
uv run python scripts/render_stack_topology.py --check
uv run python scripts/render_stack_topology.py --write
```

두 runtime의 `up`과 `status`는 같은 local/LAN URL, 수신 주소, 외부 노출 port를 표시하며 Web만
LAN front door입니다. Compose는 topology의 `otel-collector`를 함께 관리합니다. Docker·WSL 없는
host runtime은 collector process를 몰래 대체하지 않으며 topology에 `external-opt-in`으로 명시합니다.
필요한 경우 운영자가 `OTEL_EXPORTER_OTLP_ENDPOINT`로 별도 collector를 연결하고 `status`에서 실제
설정 여부를 확인합니다.

## Windows host Demo

Host runtime은 Docker·WSL이나 Windows service 등록을 사용하지 않습니다. PostgreSQL 16 x64의
압축 해제된 `bin` 경로를 명시적으로 받고, 현재 Web production build를 Python front door로
제공하므로 실행 중 Node가 필요하지 않습니다.

```powershell
# 연결된 개발 환경에서 한 번 build합니다. offline bundle에는 #324가 이 결과를 포함합니다.
npm run build --workspace @cmp/web

uv run cmp-stack --profile demo --runtime host `
  --postgres-bin 'C:\Tools\PostgreSQL 16\bin' doctor

uv run cmp-stack --profile demo --runtime host `
  --postgres-bin 'C:\Tools\PostgreSQL 16\bin' up
```

기본 Web 주소는 <http://127.0.0.1:5173>입니다. 같은 Private/Domain 사설망에서 접속할 때만 PC의
명시적인 private IPv4를 사용합니다. `0.0.0.0`, public IP, hostname 추측은 거부됩니다.
시작 완료와 `status`의 `identity=synthetic-demo-only` 표시는 이 접속이 실제 사용자 인증을 대신하지
않는 synthetic Demo 전용임을 뜻합니다.

```powershell
uv run cmp-stack --profile demo --runtime host `
  --postgres-bin 'C:\Tools\PostgreSQL 16\bin' `
  --listen-address 192.168.10.12 up
```

Web TCP 5173만 LAN front door가 됩니다. API 8000과 PostgreSQL 54329는 loopback에만 bind합니다.
방화벽의 Private/Domain·`LocalSubnet` 규칙 생성은 #324 installer가 담당합니다. 현재 `status`는
로컬/LAN URL, 수신 주소와 필요한 방화벽 상태를 표시합니다.

```powershell
uv run cmp-stack --profile demo --runtime host status
uv run cmp-stack --profile demo --runtime host logs --lines 100
uv run cmp-stack --profile demo --runtime host down
```

`down`은 API·worker·Web과 private PostgreSQL process만 중지합니다. DB와 object data는 OS가 정한
data 위치에 그대로 남고 `-v`와 같은 삭제 동작은 없습니다. Windows 기본 위치는
`%LOCALAPPDATA%\CAE Material Platform\data`와 `state`이며 공백이 있는 경로도 argv 단위로 처리합니다.
실패한 `up`이나 Ctrl-C는 이번 실행에서 시작한 process를 중지하지만 기존 data는 삭제하지 않습니다.

## Server profile 경계

Server는 `--auth-config`와 `--secret-file`을 모두 요구하고 Demo identity·seed를 허용하지 않습니다.
OIDC issuer/audience/JWKS, rotating worker token file, governed S3 설정과 DB/application secret 중 하나라도
없으면 `doctor`와 `up`이 실패합니다. 설정값이나 secret은 state JSON과 로그에 기록하지 않습니다.

현재 SPA의 OIDC Authorization Code+PKCE login/callback은 [#215](https://github.com/pikachu444/cae-material-platform/issues/215)
소유의 미구현 기능입니다. 따라서 Server profile은 이 경계를 명확히 `doctor` 오류로 보고하고 시작하지
않습니다. Demo identity나 수동 bearer-token 입력으로 우회하지 않습니다. Server auth 설정에
`CMP_DEMO_*` 또는 격리가 입증되지 않은 `CMP_PLUGIN_*` 입력이 섞여도 별도 오류로 거부하며 상속된
환경의 같은 입력도 `doctor` 오류로 거부해 Server process로 전달하지 않습니다.
