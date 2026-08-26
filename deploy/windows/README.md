# Windows 11 x64 offline bundle

연결된 Windows x64 빌드 PC에서 Demo bundle을 생성합니다. 다운로드한 도구는 text-only
`toolchain-manifest.json`의 SHA-256을 통과하기 전에는 압축 해제하거나 실행하지 않습니다.

```powershell
uv run python scripts/build_windows_offline_bundle.py --profile demo --output-dir C:\cmp-bundles
```

Server bundle은 실제 OIDC issuer/audience/JWKS와 governed S3 설정을 담은 JSON을 요구합니다.
`CMP_DEMO_*`, `CMP_PLUGIN_*` 및 실제 secret은 허용하지 않습니다. worker token과 DB/application
secret은 대상 PC의 설치기가 생성합니다.

```powershell
uv run python scripts/build_windows_offline_bundle.py --profile server `
  --server-auth-config C:\secure\cmp-server-auth.json --output-dir C:\cmp-bundles
```

생성된 ZIP을 대상 Windows 11 x64 PC에서 해제하고 `Install.cmd`를 실행합니다. 일반 실행은 user
scope, 이미 상승된 관리자 실행은 machine scope를 자동 선택하며 UAC를 요청하지 않습니다. Node,
npm, uv는 bundle build에만 사용되고 설치 제품 runtime에는 포함되지 않습니다.
`Install.cmd`는 고정 checksum의 전체 payload archive를 OS `certutil`로 검증한 뒤에만 bundled
Python을 실행합니다. Windows Server와 기존 data를 보존한 Demo↔Server profile 전환은 거부합니다.

상세한 설치·방화벽·재설치·제거·문제 해결은
[Windows 오프라인 설치 가이드](../../docs/user-guide/19-windows-offline-installation.md)를 따릅니다.
