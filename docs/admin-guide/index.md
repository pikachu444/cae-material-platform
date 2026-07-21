# CAE Material Platform 관리자 가이드

이 문서는 개발 설정이 아니라 서비스 관리자가 Material Information System의 구조와 사용자
권한을 구성하는 방법을 설명합니다. 관리자는 Table과 항목을 추가하고, 레코드 사이의 링크
규칙을 정하고, 사용자에게 필요한 제품 기능만 부여합니다.

## 1. 관리자 작업 영역

| 화면 | 주소 | 관리 대상 |
| --- | --- | --- |
| Administration overview | `/administration` | 관리자 작업 선택과 제품 권한 원칙 |
| Database design | `/administration/database` | Table, Attribute, Layout, Subset, Link Type |
| Users & access | `/administration/access` | Administrator/User와 기능 권한 |
| Material Database | `/database` | Folder, Record, exact-revision link 탐색 |

Docker demo는 **Demo workspace** Administrator session을 자동으로 준비합니다. 사용자는 API 주소나
token을 입력하지 않습니다. 운영 환경의 회사 identity directory 연결은 배포 설정이며 일반
Administration 화면에 issuer, subject 또는 token을 노출하지 않습니다.

Administration은 일반 사용자 메뉴에 상시 노출되지 않습니다. 우측 workspace menu에서 열며,
왼쪽 220 px 관리 목록과 하나의 주 작업면을 사용합니다. Overview의 관리 작업은 card grid가 아닌
divider 목록이고, Database design은 20 px 제목, 340 px Table 열과 나머지 Attribute/Layout 열을
사용합니다. Attribute도 rounded card가 아닌 52 px divider 행으로 표시합니다.

## 2. Table과 Attribute 구성

1. **Administration → Database design**에서 stable key, 표시 이름, 설명과 classification을 입력해
   Table revision 1을 만듭니다.
2. Table을 선택하고 Attribute stable key, 표시 이름, 설명과 data type을 정의합니다.
3. `number`에는 quantity semantics와 정규화 단위를 함께 지정합니다.
4. `discrete`에는 허용값을, `record_reference`에는 대상 Table을 지정합니다.
5. Attribute를 Layout에 원하는 순서로 배치하고, 자주 쓰는 검색 조건은 Subset으로
   저장합니다.

지원 data type은 `number`, `integer`, `text`, `boolean`, `date`, `discrete`, `file`, `curve`,
`record_reference`입니다. Attribute 추가에는 DB migration이 필요하지 않지만, 정의 자체는
revision으로 보존됩니다. 수치값은 원본 값·원본 단위 문자열·정규화 값·정규화 단위·quantity
semantics를 함께 저장합니다.

## 3. Folder와 Record 운영

**Catalog records** 또는 **Catalog Explorer**에서 Table을 선택한 뒤 Folder와 Record를
생성합니다. Folder parent는 exact revision으로 고정되며 cycle이나 다른 Table 연결은 서버와
PostgreSQL이 모두 거부합니다. Record를 수정할 때는 현재 ETag가 필요하고, 성공하면 기존 행을
덮어쓰지 않고 새 Record revision이 생깁니다.

Layout은 입력 순서만 정의하며 값을 복제하지 않습니다. Subset을 수정할 때도 기존 검색 조건을
바꾸지 않고 새 revision을 추가합니다.

## 4. Link Type과 관련 데이터 이동

**Administration → Database design → Link Types**에서 다음을 지정합니다.

- stable key와 이름
- source/target Table
- 정방향·역방향 표시 이름
- outgoing/incoming cardinality

Record link의 양 끝은 항상 exact Record revision입니다. `latest` 별칭, 다른 scope의 endpoint,
허용하지 않은 Table 조합과 cardinality 위반은 거부됩니다. 링크를 종료할 때는 삭제하지 않고
Deactivate를 사용합니다. 사용자는 Related records 패널과 Workflow Explorer에서 링크를 따라
시험, Dataset, Processing Run, Neutral IR, Solver Card로 이동할 수 있습니다.

## 5. Administrator/User 권한

[Users & access](http://127.0.0.1:5173/administration/access)는 내부 역할 이름 대신 다음 두 역할만 표시합니다.

- `Administrator`: 사용자 관리와 다섯 제품 기능을 모두 사용
- `User`: 지정된 기능만 사용

User에게 부여할 수 있는 기능은 다음과 같습니다.

1. Schema configuration
2. Catalog editing
3. Processing & calibration
4. Model approval
5. Solver Card export

제품 화면에서는 사용자 또는 팀 이름만 선택합니다. identity-provider issuer, principal UUID,
project/organization scope와 classification enforcement는 배포 identity directory 및 내부 정책
확장점에서 처리합니다. export-controlled 접근은 별도 운영 승인을 거치며 단순 기능 체크로 자동
부여하지 않습니다.

권한 변경은 기존 assignment를 수정하는 방식이 아닙니다. 기존 assignment를 **Revoke**하고 새
assignment를 추가합니다. 부여·회수 이력은 남으며 일반 User가 assignment 목록이나 생성 API를
호출하면 403으로 거부됩니다.

## 6. 내부 확장성과 기존 역할 호환성

T-59 이전의 상세 role binding은 제거하지 않습니다. 서버가 기존 role들의 permission 합계를
Administrator/User와 기능 권한으로 투영하므로 기존 enforcement가 계속 동작합니다. 이 내부
호환 정보는 일반 제품 화면에 표시하지 않습니다. 향후 resource/action/scope 단위 권한을 추가해도
Catalog schema나 사용자 작업 흐름을 다시 만들지 않습니다.

![통합 Administration 개요](../15-demo/images/ux-redesign-v2/administration-overview-1440x900.png)

![평면 행으로 정리한 Table, Attribute, Layout, Subset 및 Link Type 관리](../15-demo/images/ux-redesign-v2/administration-database-1440x900.png)

![새 Attribute revision이 Layout 기반 Record Datasheet에 투영된 결과](../15-demo/images/ux-redesign-v2/administration-layout-datasheet-1440x900.png)

![제품 역할 및 기능 권한](../15-demo/images/t78-users-access.png)

## 7. 운영 점검

- 사용자가 예상한 organization/project를 선택했는지 확인합니다.
- 운영 identity directory에서 사용자/팀 이름 mapping을 확인합니다.
- 필요한 최소 classification과 기능만 부여합니다.
- 권한 변경 뒤 새 session에서 `/administration/access`의 실제 effective access를 확인합니다.
- schema, catalog, processing, approval, export 각각 허용/거부 API를 점검합니다.
- 기존 데이터를 지우거나 role table을 직접 수정하지 않습니다.
