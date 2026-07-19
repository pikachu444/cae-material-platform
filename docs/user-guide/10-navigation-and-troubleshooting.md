# 메뉴와 Material 작업공간 사용법

상단 메뉴는 데이터를 서로 다른 제품으로 나누지 않습니다. 모든 업무는 같은 Material과
Material State의 exact revision 문맥을 공유합니다.

| 상단 메뉴 | 주 작업 |
| --- | --- |
| **Dashboard** | 재료 검색, 최근 Material과 세 재료 계열 작업 시작 |
| **Material Database** | Contents Tree, Datasheet, 검색·비교·링크와 Material record |
| **Material Modeling** | 시험 import, curve processing, Recipe, fitting, IR와 Solver Card |
| **Jobs & Reviews** | Batch/Job 상태, 검토·승인·배포와 다운로드 |
| **Administration** | Table/Attribute/Layout/Link Type과 사용자 기능 권한 |

## 권장 이동 순서

1. **Material Database**에서 Material을 검색하거나 생성합니다.
2. Material 상세의 **Overview**에서 State와 기본 물성을 확인합니다.
3. **Test data** 탭에서 시험 실행 문맥과 column/unit mapping을 고정합니다.
4. **Datasets & Processing**에서 개별 curve와 raw/normalized/processed 구분을 확인합니다.
5. **Models & Cards**에서 fitting 또는 수동 IR 입력, mapping report와 card를 확인합니다.
6. **Governance**에서 validation/provenance를 검토합니다.
7. 여러 파일이 필요하면 **Jobs & Reviews**의 다운로드 영역에서 Bundle을 만듭니다.

전역 **Tests**, **Datasets**, **Models**, **Governance** 메뉴에서 먼저 시작해도 됩니다. 각 화면은
현재 권한으로 보이는 Material 목록을 제시하고 선택한 Material의 같은 문맥 탭으로 이동합니다.
`/materials/{material_id}` 기존 주소는 **Overview**로 계속 동작합니다.

![전역 Models 허브에서 Material 선택](../15-demo/images/t46-global-navigation-model-hub.png)

![Material의 Models & Cards 문맥 탭](../15-demo/images/t46-material-context-tabs.png)

## Governance 운영 상태

전역 **Governance**의 **API observability**는 현재 API process의 요청 수, 5xx 수, active request와
route-template별 p95 상한을 보여줍니다. URL, query, request body, 시험 데이터, credential이나 tenant
식별자는 표시하지 않습니다. 이 화면은 빠른 진단용이며 여러 replica를 합치는 telemetry backend를
대신하지 않습니다. Docker demo에서는 local identity가 읽기 전용 auditor 역할을 포함합니다.

![Governance API observability](../15-demo/images/t47-api-observability.png)

## 자주 생기는 문제

### 오류에 `Support reference`가 표시됨

입력 수정 방법을 설명하는 오류 본문과 함께 `CMP-...` problem code와 trace ID가 표시됩니다.
본문에 따라 revision을 다시 선택하거나 입력을 수정한 뒤 재시도하십시오. 문제가 반복되면 token,
시험 원본 또는 회사 데이터를 복사하지 말고 **Support reference 전체 문자열만** 운영 담당자에게
전달하십시오. 이 값으로 API/worker trace를 찾을 수 있습니다.

### `Sign in to continue`가 표시됨

Docker Desktop과 demo 서비스가 실행 중인지 확인한 뒤 **Try again**을 누릅니다. 일반 배포라면
관리자가 제공한 로그인 화면에서 로그인합니다. 사용자에게 별도 연결 문자열 입력을 요구하지 않습니다.

### 메뉴에는 Material이 있지만 탭이 비어 있음

Material 아래에 State가 없거나, 해당 State에 필요한 Property Set/Test Run/Dataset이 없을 수
있습니다. **Overview**에서 State와 기본 물성을 먼저 만들고 앞 단계 탭부터 진행하십시오.

### Steel/Polymer/Elastomer 기능이 보이지 않음

이름으로 모델을 추론하지 않습니다. Material revision의 class가 각각 `metal`, `polymer`,
`elastomer`인지 확인하고, 기존 State가 이전 Material revision을 고정했다면 Overview의
명시적 rebase 동작으로 새 State revision을 추가하십시오.

### card 생성이 막힘

mapping report에서 `unsupported` 항목을 확인하십시오. `approximated`는 조용한 성공이 아니라
검토가 필요한 결과입니다. preflight 이후 source IR revision이 바뀌었다면 새 report를
만들어야 합니다.

### ZIP 다운로드가 안 됨

Bundle 목록을 새로 읽은 뒤 다시 시도하십시오. 다운로드 권한은 짧게 유효하며 Bundle과 원본
revision을 바꾸지 않습니다. required source가 권한 밖이거나 사라진 경우 새 Selection preflight가
실패합니다.
