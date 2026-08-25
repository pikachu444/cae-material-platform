# Issue #324 Windows offline installer evidence

검증일: 2026-08-26 (Asia/Seoul)

## 공급망과 산출물 inventory

저장소에는 binary를 추가하지 않았다. 연결된 Windows x64 환경에서 text-only manifest의 다섯 archive를
다운로드하고 SHA-256 일치 후에만 압축 해제·실행했다.

| Tool | Version | SHA-256 |
|---|---:|---|
| Python | 3.12.14 | `89f18f6932917163b74339ebcec2645c8e47ae7f1c5f2ac37f2b4f4cf3beb647` |
| uv | 0.12.5 | `4c4d49d8738847d9b71ba319e49a5688c93eac0fe6204b1df24e98528dddf39a` |
| Node | 24.19.0 | `57f71ab3652e797d84acddc79c81cc9ff1c6ddb2a1974cdb83f00fee9bff4c73` |
| npm | 11.17.0 | `b290bbb35b9e72c3ef84edbe041f28c4479c4d9ee79f555817b8caafe7ce4bba` |
| PostgreSQL | 16.15 | `25e6fcdfb8caec38691bf461125e7564508760666f7b8e5dc6a5f0818f58f81e` |

최종 Demo ZIP은 저장소 밖 임시 output에서 생성했다.

- 파일: `CAE-Material-Platform-0.38.0-demo-windows-x64.zip`
- bytes: `173891338`
- SHA-256: `22ac15b98c209c0908d1dc59cc4f9533a5557801517c5231d5d58addd462a71c`
- outer entries: `3` (`Install.cmd`, `bundle-manifest.json`, `payload.zip`)
- checksummed payload entries: `13588` (manifest inventory와 exact match)
- installed Python/PostgreSQL/Web entry: 각각 1개
- Node/npm/uv/pgAdmin runtime entry: `0`
- `Install.cmd`에 고정된 bundle manifest SHA-256:
  `66432feb24a212f16f791ec3c70f3a6b2cc2e217132918830252dd3ac04e5602`
- Python loader closure 전체를 포함한 payload archive SHA-256:
  `aebd50a17932a8d195ca4422e458524a79adec0c5682e1b58aa3100319758f72`

## Windows 실기 검증

Windows 11 x64 build 26200의 공백 포함 임시 `%LOCALAPPDATA%`에서 최종 ZIP을 해제하고 실제
`Install.cmd --listen-address 127.0.0.1`을 실행했다.

- `certutil`이 bundle manifest와 Python loader closure 전체를 담은 payload archive를 실행 전에
  검증했고, OS `tar.exe`가 검증된 archive를 임시 경로에 해제한 뒤 bundled Python을 실행했다.
- 일반 권한에서 user scope를 자동 선택했고 UAC를 요청하지 않았다.
- 전체 payload inventory 검증, portable program 설치, record와 Start/Stop/Status/Uninstall 진입점
  생성, data/state 분리가 성공했다.
- 비관리자 방화벽 경계는 로컬 설치를 유지하고 installer-owned rule name, TCP 5173,
  Private/Domain, LocalSubnet의 정확한 IT 명령을 화면과 installer log에 기록했다.
- canonical API 8000은 FE-07B의 격리 Compose가 점유 중이어서 시작은
  `category=port-conflict`/exit 2로 중단됐다. 해당 container나 port를 변경·중지하지 않았다.
- 같은 bundle 재실행은 program을 중복 복사하지 않았고 data sentinel과 기존 listen address를
  보존했다.
- 설치된 Python을 의도적으로 손상한 뒤 재실행했을 때 inventory mismatch를 발견하고 program만
  복구했으며 data sentinel을 보존했다.
- `Status.cmd`는 stopped state, local/LAN URL, Web-only exposure와 firewall 부재를 정확히 출력했다.
- `Uninstall.cmd`는 exit 0으로 program, 네 진입점과 install record를 제거했고 data sentinel을
  보존했으며 자기 자신도 비동기로 제거했다.
- 별도 tampered bundle에서 archive 내부 `python312.dll`을 바꿨을 때 `Install.cmd`가 Python 실행 전에
  `pre-execution checksum mismatch`/exit 2로 거부했다.
- 자동 회귀 검증은 Windows Server product type을 거부하고, 같은 이름의 외부 firewall rule을
  보존하는 program-specific 삭제 경계와 Demo↔Server profile 전환 거부/data 보존을 확인했다.

#323에서 같은 Windows PC의 별도 acceptance port를 사용해 PostgreSQL 16.15, migration,
application role/RLS, API/worker/Node-free Web, full Demo seed, DP780과 두 solver card exact digest,
stop/start read-back을 실제 검증했다. #324 installer는 이 runtime을 복제하지 않고 그대로 호출한다.

## 외부 잔여 gate

- 이 PC에는 Windows Sandbox가 없고 canonical 5173/8000/54329는 FE-07B가 소유한다. 따라서 FE를
  중지하지 않은 현재 실행에서는 깨끗한 PC의 한 번 설치→전체 기동→브라우저 DP780 흐름과 같은 LAN의
  다른 PC 접속을 다시 수행하지 않았다.
- 이미 상승된 관리자 세션이 아니므로 machine scope와 실제 firewall rule 생성·삭제는 자동 테스트의
  exact command/ownership 계약으로 검증했으며 실제 관리자 실행은 남아 있다.
- Server bundle 입력·secret/ACL/fail-closed 계약은 자동 검증했다. 실제 SPA OIDC Code+PKCE login은
  #215가 미구현이므로 Server 기동과 다른 PC 로그인은 계속 외부 차단 gate다.

이 세 항목은 Draft PR에서 숨기지 않으며 Ready/merge 전에 각각 가능한 환경과 선행 기능으로 다시
실행해야 한다.
