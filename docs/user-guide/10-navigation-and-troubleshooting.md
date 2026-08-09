# 메뉴와 Material 작업공간 사용법

상단 메뉴는 데이터를 서로 다른 제품으로 나누지 않습니다. 모든 업무는 같은 Material과
Material State의 exact revision 문맥을 공유합니다.

| 상단 메뉴 | 주 작업 |
| --- | --- |
| **Materials** | 검색·필터·비교, Browse Tree, 5-tab datasheet와 직접 solver card download |
| **Modeling** | 시험 데이터 선택, 처리 결과 확인, 모델 비교·선택, 카드 전달 준비 |
| **Activity** | 재개할 작업, 검토 요청, 최근 결과 |

**Administration**은 우측 workspace menu의 role-gated 항목입니다. Table/Attribute/Layout/Subset/
Link Type과 사용자 기능 권한을 관리합니다. `/database`, `/catalog/*`, `/datasets/*`의 기존 deep
link는 보존하지만 일반 사용자의 전역 메뉴에는 나타나지 않습니다.

## 권장 이동 순서

1. **Materials**에서 이름/grade를 검색하거나 **Browse Tree**의 Database → Profile → Table →
   Folder → Record를 탐색합니다.
2. Material 상세의 `Overview | Properties | Curves | CAE Cards | Evidence`를 검토합니다.
3. 카드가 있으면 Header 또는 CAE Cards에서 native preview/download를 실행합니다.
4. 카드가 없을 때 **Modeling → Data**에서 JSON/CSV/XLSX와 channel/unit을 고정합니다.
5. Process와 Fit의 같은 graph에서 처리·후보·residual·extrapolation을 검토하고 Export로 이동합니다.
6. 검토 요청은 **Activity**에서 상태와 요청 사유를 확인합니다. Reviewer는 행의 **Review**에서
   사유를 남기고 승인하거나 변경을 요청합니다. User와 Administrator는 자신의 요청이 결정되기
   전까지 **In progress**에서 확인하고, 실패한 작업은 정확한 입력으로 재시도합니다.
7. 상세 이력과 식별 정보는 Evidence에서, 재사용 처리 설정과 일괄 실행은 Advanced에서 확인합니다.

![통합 Materials 검색·결과·선택 문맥](images/current/materials-search-1440x900.png)

![Material의 5-tab 상세와 직접 card delivery](images/current/material-detail-1440x900.png)

![Activity 검토·재개·결과 작업 큐](images/current/activity-1440x900.png)

**Recent outcomes**는 승인·변경 요청 결과와 이 브라우저에서 열거나 내려받은 solver card 이력을
구분해 보여 줍니다. 긴 이력은 화면 크기와 관계없이 Activity 작업 영역 안에서만 스크롤되며 페이지
전체 레이아웃은 유지됩니다. 서버가 돌려준 요청 목록을 화면을 채우기 위해 늘리지 않습니다.

![Activity Recent outcomes 로컬 이력](images/current/activity-history-1440x900.png)

1366×768과 1920×1080에서도 같은 행 우선 구조를 유지합니다.

![1366px Activity 작업 큐](images/current/activity-1366x768.png)

![1920px Activity 작업 큐](images/current/activity-1920x1080.png)

2560×1440과 3840×2160에서도 queue와 Review action은 같은 exact revision 행 구조로 유지됩니다.
Activity는 공통 compact 기준을 사용합니다. task identity는 14px, tab·data·action은 13px,
metadata는 12px이며 action 높이는 최소 36px입니다. 3840px에서는 2656px 로컬 작업 영역 안에
2602px 다섯 열과 scrollbar를 나란히 두고 가운데 정렬해 상태와 행동 사이가 과도하게 벌어지지
않습니다. 1920px 고정 작업 섬, 해상도별 CSS, CSS `zoom`, 일괄 확대, 채우기용 행은 사용하지
않습니다.

이 보정은 새 고해상도 표시 단계를 정한 것이 아닙니다. 공통 표시 단계는 #221에서 비교·결정하고,
전체 화면 적용은 #184에서 검증합니다. Activity의 실제 Windows 4K 100%·150%·200% 물리적 판독성은
전체 제품 흐름 검증 뒤 마지막 #223에서 최종 판정합니다. 현재 증거 장비는 2560×1440 100%이며,
자동 3840×2160 캡처를 실제 4K 장비 판정으로 대신하지 않습니다.

![2560px Activity 작업 큐](images/current/activity-2560x1440.png)

![3840px Activity 작업 큐](images/current/activity-3840x2160.png)

3840px의 긴 이력에서도 오른쪽 로컬 scrollbar가 실제 콘텐츠 길이에 맞춰 나타납니다.

![1920px Activity Recent outcomes](images/current/activity-history-1920x1080.png)

![2560px Activity Recent outcomes](images/current/activity-history-2560x1440.png)

![3840px Activity Recent outcomes](images/current/activity-history-3840x2160.png)

## 운영 상태

**Activity**는 `Needs attention | In progress | Recent outcomes`의 짧은 작업 큐입니다. 같은
review 요청을 여러 번 만들지 않으며, 승인·변경 요청 결과는 해당 요청의 상태로 갱신됩니다. 일반
화면에는 업무 종류와 요청 사유가 보이고 정확한 식별자는 Evidence에 남습니다. 사용자가 새 자료
또는 solver card 검토를 요청하는 진입점은 각각 Material 상세와 Native Card Preview에 있습니다.
두 화면은 이미 열어 둔 정확한 revision을 사용하므로 사용자가 식별자나 hash를 직접 입력할 필요가
없습니다.

User와 Administrator의 기본 화면은 **In progress**이며 Reviewer 전용 결정 버튼이 없습니다.
Reviewer의 결정 저장이 실패하면 입력한 사유와 선택한 요청을 유지해 다시 시도할 수 있습니다.
다운로드 같은 작업이 실패한 경우에는 **Recovery needed**에서 **Open exact selection**으로 원래
선택을 다시 엽니다.

![User Activity 기본 화면](images/current/activity-user-1440x900.png)

![Administrator Activity 기본 화면](images/current/activity-administrator-1440x900.png)

![Activity 결정 실패 시 입력 보존](images/current/activity-decision-error-1440x900.png)

![Activity exact selection 복구](images/current/activity-recovery-1440x900.png)

기존 `/jobs-reviews` 링크는 같은 Activity 큐를 엽니다. 이 경로에서는 Aggregate type/ID, revision
ID, manifest hash를 직접 입력하거나 독립적으로 결정을 기록하지 않습니다. 요청은 Material 또는
Solver Card의 현재 화면에서 만들고, Reviewer의 기존 요청 결정은 Activity에서 처리합니다. 승인된
Record와 exact revision은 Materials 검색·다운로드에서 다시 찾을 수 있습니다. `/governance`
는 일반 검토 진입점이 아니며 Operations, Release, Governance Evidence의 고급 운영 화면을 유지합니다.

서비스 상태와 복구 절차는 일반 사용자 메뉴가 아니라 운영 담당자의
[운영 가이드](11-operations-and-recovery.md)에서 확인합니다.

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
