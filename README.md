# CAE Material Platform

재료를 찾고, 시험 데이터를 검토해 모델을 맞추고, 사용할 수 있는 솔버 카드를 받는 작업을 한
곳에서 이어 가는 엔지니어링 플랫폼입니다. 일반 화면에서는 재료명, 물성, 곡선, 작업 상태처럼
업무에 필요한 정보만 보입니다. 상세 식별값과 계산 근거는 필요할 때 Evidence와 Advanced에서
확인합니다.

> 저장소의 예제 데이터와 수치 모델은 `reference/non-production` 범위입니다. 실제 승인 재료값,
> 생산용 재료 모델 또는 특정 솔버의 사용 승인을 대신하지 않습니다.

![현재 Materials 검색 화면](docs/user-guide/images/current/materials-search-1440x900.png)

![현재 Modeling Fit 화면](docs/user-guide/images/current/modeling-fit-1440x900.png)

## 이 플랫폼에서 하는 일

- **재료 찾기와 비교**: Database → Profile → Table → Folder → Record 구조를 따라가거나 검색으로
  재료를 찾고, 물성·곡선·관련 카드를 비교합니다.
- **시험 데이터로 모델 만들기**: 시험 데이터를 불러와 필요한 처리를 확인하고, 후보 모델을 그래프에서
  비교한 뒤 선택한 결과를 카드 생성 단계로 전달합니다.
- **검토와 배포**: 요청된 재료 데이터와 솔버 카드를 역할에 맞게 검토하고, 승인 또는 변경 요청의
  결과를 Activity에서 확인합니다. 배포와 증거 확인은 필요한 경우 운영용 Governance 화면에서 계속합니다.

## 역할별로 할 수 있는 일

| 역할 | 주 업무 |
| --- | --- |
| **일반 사용자** | 재료 검색·조회·비교, 승인된 카드 다운로드, 시험 데이터 업로드 요청, 통계와 모델 맞춤, 카드 생성 요청 |
| **Reviewer** | 일반 사용자 업무와 함께 제출된 재료 데이터·솔버 카드의 변경 요청과 승인 작업을 Activity 큐에서 처리합니다. |
| **Administrator** | 데이터베이스 구조와 속성 관리, 자료 편집, review request와 정확한 Activity 복구, 권한 관리를 수행합니다. 승인 결정은 Reviewer가 담당하며 Database → 목록 → 속성 편집의 3단 관리 화면을 사용합니다. |

## 핵심 사용 흐름

### 기존 Material에서 solver card 받기

`재료 검색 → 결과 비교 → 재료 상세 → 솔버 카드 → 미리보기/다운로드`

1. `/materials`에서 이름 또는 grade로 검색하거나 Browse Tree를 엽니다.
2. 결과와 상세에서 물성, 곡선, 관련 재료를 확인합니다.
3. **CAE Cards**에서 사용할 카드를 미리 본 뒤 내려받습니다.
4. 카드가 아직 없으면 선택한 재료 문맥을 유지한 채 Modeling으로 이동합니다.

### 시험 데이터에서 새 card 만들기

`모델링 Data → Process → Fit → Export → 재료 라이브러리 저장`

1. JSON 또는 CSV/TSV/XLSX 시험 데이터를 등록합니다.
2. Process에서 처리 결과와 곡선을 확인합니다.
3. Fit에서 후보 응답을 그래프 위에서 비교하고 사용할 결과를 명시적으로 선택합니다.
4. Export에서 카드 미리보기와 전달 준비 상태를 확인합니다.

## 지금 가능한 일과 다음 화면

### 현재 화면

현재 `/materials`는 재료 검색, Browse Tree, 상세, 곡선과 CAE card 미리보기·다운로드를 제공합니다.
`/modeling`은 Data, Process, Fit, Export의 시험 데이터 처리와 그래프 중심 모델 맞춤 흐름을
제공합니다. Activity는 역할별 검토 대기, 재개할 작업, 최근 결과를 한 큐에서 보여 주며,
Administration은 Database → 목록 → 속성 편집의 3단 작업 화면을 제공합니다. 이전 `/jobs-reviews`
링크도 같은 Activity 큐로 열립니다.

### 승인된 구현 목표

2026-07-26에 승인된 다음 화면 구조를 실제 제품에 순차 적용합니다. 이는 **현재 화면**의 주장이나
대체 캡처가 아니라, 구현 시 지켜야 할 디자인·사용성 기준입니다.

- Materials는 탐색 트리, 넓은 결과표, 선택한 재료 상세가 한 작업 공간에서 이어집니다.
- Modeling은 조절 가능한 작은 곡선 목록과 얕은 제어 영역을 두고, 그래프를 가장 크게 유지합니다.
- Activity는 User/Administrator의 요청·복구와 Reviewer 승인 작업을 역할별로 보여 줍니다.
- Administration은 객체 탐색기, 목록, 속성 편집기를 연결합니다.

승인 근거와 반응형 비교 이미지는 [UX 설계 인덱스](docs/design-index.md)에서, 공개 제품 참고자료와
이미지 출처는 [영구 참고자료 카탈로그](docs/00-research/product-reference-source-catalog.json)에서
확인할 수 있습니다. 외부 제품의 화면·브랜드·내부 구조를 복사하지 않습니다.

## 5분 로컬 실행

필수 도구는 Git과 Docker Desktop(Compose 포함)입니다. 저장소 루트에서 실행합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
```

`postgres`와 `api`가 healthy이고 `migrate`, `reference-plugins`, `seed`가 0으로 종료되면
<http://127.0.0.1:5173>을 엽니다. Demo session은 자동으로 준비되며 별도 API 주소나 토큰 입력은
필요하지 않습니다. 상태는 <http://127.0.0.1:8000/api/v1/health>에서 확인합니다.

현재 기준선에서는 기존 demo volume의 화면 확인은 가능하지만, **새 volume에서 전체 seed를 끝까지
재현하는 실패**가 [#157](https://github.com/pikachu444/cae-material-platform/issues/157)에 남아 있습니다.
위 명령이 `seed` 단계에서 멈추면 화면 기능이 없다고 단정하지 말고 해당 issue의 재현·수정 절차를
따르십시오.

처음에는 `DP780`을 검색해 재료 상세와 CAE Card를 살펴본 뒤, 필요한 경우 **Modeling → Data**에서
시험 데이터를 등록해 보십시오.

종료는 다음 명령을 사용합니다. `-v`는 synthetic demo volume을 삭제하므로 필요한 경우에만
사용하십시오.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml down
```

Windows/WSL 설치와 문제 해결은 [Compose 실행 가이드](deploy/compose/README.md)를 참고하십시오.

### 외부에서 로컬 데모 접속

Cloudflare Quick Tunnel을 사용하면 공유기 포트 포워딩 없이 현재 PC의 로컬 데모를 잠시 외부에
공개할 수 있습니다. 먼저 위의 Compose를 실행해 <http://127.0.0.1:5173>이 열리는지 확인한 뒤,
최초 한 번 다음 컨테이너를 만듭니다.

```powershell
docker run -d --name cmp-cloudflared --restart unless-stopped `
  cloudflare/cloudflared:latest tunnel --no-autoupdate `
  --http-host-header localhost:5173 `
  --url http://host.docker.internal:5173
```

이미 컨테이너가 있으면 `docker start cmp-cloudflared`만 실행합니다. 현재 할당된 외부 주소는 다음
명령의 마지막 결과에서 확인합니다.

```powershell
docker logs cmp-cloudflared 2>&1 |
  Select-String -AllMatches 'https://[a-z0-9-]+\.trycloudflare\.com' |
  ForEach-Object { $_.Matches.Value } |
  Select-Object -Last 1
```

2026-08-14 현재 확인한 주소는
<https://tomato-empire-coleman-pricing.trycloudflare.com>입니다. Quick Tunnel 주소는 컨테이너를
다시 만들거나 재시작하면 바뀔 수 있으므로, 접속되지 않으면 위 명령으로 현재 주소를 다시 확인합니다.
PC, Docker Desktop, `cmp-local-demo-web`, `cmp-cloudflared`가 모두 실행 중이어야 외부에서 접속할 수
있습니다.

Quick Tunnel에는 별도의 Cloudflare 접근 제한을 설정하지 않았으므로 주소를 아는 누구나 데모 화면에
접근할 수 있습니다. 합성 데모 데이터에만 사용하고 기밀 시험 데이터나 production credential은
입력하지 마십시오. 외부 공개를 끝낼 때는 `docker stop cmp-cloudflared`를 실행합니다.

## 개발과 검증

Python 3.12, `uv`, Node.js/npm을 사용합니다.

```powershell
uv sync --all-groups
npm ci
uv run pytest tests/contracts
npm run build --workspace @cmp/web
npm run test:web
uv run cmp-check-user-guide --root .
```

전체 명령은 [개발 가이드](DEVELOPMENT.md), 사용자 화면 확인 방법은
[사용자 가이드](docs/user-guide/index.md)를 따릅니다. 개발 변경 전에는 [AGENTS.md](AGENTS.md)와
정확한 GitHub issue를 읽으십시오. 완료된 작업 이력은 Git과 병합된 issue/PR에서 확인합니다.

## 문서

- [사용자 가이드](docs/user-guide/index.md)
- [관리자 가이드](docs/admin-guide/index.md)
- [제품 방향과 UX 기준](docs/01-product/product-vision.md)
- [UX 설계 인덱스](docs/design-index.md)
- [공식 제품 참고자료와 이미지 출처](docs/00-research/product-reference-source-catalog.json)
- [요구사항](docs/02-requirements/requirements.md)
- [현재 구현 상태](IMPLEMENTATION_STATUS.md)
- [backlog](docs/13-delivery/backlog.md)

이 저장소는 private 개발 저장소입니다. 실제 기밀 시험 데이터, production credential 또는
승인되지 않은 solver 자료를 commit하지 마십시오.
