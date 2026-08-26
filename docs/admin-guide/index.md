# CAE Material Platform 관리자 가이드

이 문서는 서비스 관리자가 Catalog 구조, 실제 Record, 형식 정의와 제품 접근 권한을 관리하는
현재 Administration 작업을 설명합니다.

## 1. 관리자 작업 영역

| 화면 | 주소 | 관리 대상 |
| --- | --- | --- |
| Database | `/administration/database` | Database, Configuration, Record type, Attribute, Layout, Subset, Link Type |
| Format definitions | `/administration/schema-bundles` | 형식 정의 파일 비교, 확인 후 적용, immutable 결과 검증과 다운로드 |
| Records | `/administration/records` | 선택한 Table에 저장되는 실제 Record 검색·생성·revision 작성·일괄 등록 |
| Access | `/administration/access` | User/Reviewer/Administrator 역할의 현재 접근 부여와 제거 |

`/administration`은 Database로 이동합니다. 기본 앱 바의 `Materials | Modeling | Activity`와 한 줄의
`Database | Format definitions | Records | Access` 작업 내비게이션은 모든 Administration 화면에서
유지됩니다. Docker demo는 Administrator인 **Demo user**를 준비합니다. Member directory 검색과
선택 흐름은 #327 범위이며 현재 화면은 이를 제공하지 않습니다.

## 2. Database 구조 관리

Database는 논리 Catalog 컨테이너입니다. **Configuration**은 contract의 Profile을 관리 화면에서 읽기
쉽게 표시한 선택적 Table 배치/설정이며 exact Database revision에 고정됩니다. Configuration 자체는
Record나 Attribute를 저장하지 않고, Record type은 Configuration 없이도 존재할 수 있습니다.
**Record type**은 contract의 Table이며 실제 Record 한 종류의 형식을 정의합니다. Layout은 그 Record를
datasheet에서 보여 줄 필드와 순서를 정의합니다.

1. **Administration → Database**에서 **Record type**을 선택합니다. Database를 고르지 않으면
   `No database selected`가 표시되고 Configuration은 나타나지 않습니다. Database를 고른 경우에만
   선택적 Configuration이 나타나며, 하나뿐이면 자동 선택됩니다. 내부 Profile/Table identity와 exact
   revision은 선택한 경우에만 주소에 함께 남습니다.
2. **Definition objects**에서 Attributes, Layouts, Subsets 또는 Link Types를 엽니다. 일반 정의는 목록의
   Revision과 선택한 정의의 lifecycle을 확인합니다. Layout 목록은 **Version**을 한 번만 표시합니다.
3. 새 객체는 **Create Database**, **Create Configuration**, **Create Record type**, **Create Attribute**처럼 현재
   객체 종류가 표시된 명령으로 시작합니다.
4. `number` Attribute에는 quantity semantics와 표준 단위를, `discrete`에는 허용값을,
   `record_reference`에는 대상 Table을 지정합니다.
5. **New layout**은 서버를 변경하지 않고 이름, 선택적 설명과 현재 Record type의 필드를 편집기에 엽니다.
   **Datasheet fields**에서 필드와 순서를 검토한 뒤 **Save**를 눌러야 exact Attribute revision과 함께
   새 Layout이 저장됩니다. 이 선택은 Attribute 자체를 비활성화하거나 삭제하지 않습니다.
6. 선택한 Layout의 **Preview**는 저장된 section과 field order를 실제 server Record에 적용합니다.
   **Preview with**에서 `이름 (Draft, revision N)`처럼 exact Record revision을 고르고 결과를 확인한 뒤
   **Back to layout** 또는 **Open in Records**로 같은 exact revision을 이어 갑니다.
7. **More**의 **Duplicate layout**은 값을 복사한 편집기를 열 뿐 서버를 변경하지 않으며, 별도 **Save**가
   새 identity를 만듭니다. **Delete layout**은 게시 이력이 없는 미사용 첫 draft에만 적용되고, 서버가
   사용 중인 항목을 거부하면 원본과 편집 상태를 보존합니다.
8. Database, Configuration, Record type, Attribute, Subset과 Link Type은 지원되는 validation과
   **Save new … revision**을 사용합니다. Layout publication은 현재 Administration 계약에서 승인된
   전환이 없어 이 화면에서 제공하지 않으며 validation API 자체는 유지됩니다.

지원 data type은 `number`, `integer`, `text`, `boolean`, `date`, `discrete`, `file`, `curve`,
`record_reference`입니다. 수치 Record 값은 원본 값·원본 단위 문자열·정규화 값·정규화 단위·quantity
semantics를 함께 저장합니다.

![Administration Database](../user-guide/images/current/administration-database-1440x900.png)

## 3. Format definitions 선택·검토·적용·검증

여러 형식 정의 파일을 한 번에 반영할 때는 **Administration → Format definitions**를 사용합니다.
정상 흐름은 `1 Choose files → 2 Review changes → 3 Apply changes → 4 Verify result`입니다.

1. canonical JSON 한 개, source-v2 manifest와 참조 JSON 파일들, checksummed source-set envelope JSON,
   또는 같은 구성을 담은 ZIP을 준비합니다. 입력은 1 byte 이상 64 MiB 이하이고 허용 media type과
   안전한 상대 경로를 사용해야 합니다.
2. **Format definition files**에서 파일을 고르고 File format, Definition set/version, Record type
   definitions, Unit definitions와 **Data classification**을 확인합니다.
3. **Preview changes (no write)**를 누릅니다. 이 단계는 immutable source Artifact를 올리고 현재
   Catalog와 비교할 뿐 정의를 적용하지 않습니다.
4. `Change | Definition type | Name | Current state` 표와 위의 Create/Update/No change/Conflict/Error 요약을
   검토합니다. 행을 선택하면 적용 결과가 한 번 표시되며 reason code, source 위치, ID와 checksum은
   **Technical details** 또는 **Checksum and provenance**에서 확인합니다.
5. conflict, error 또는 migration-required가 없을 때 **Apply N changes**를 눌러 최종 확인을 엽니다.
   Definition set, version과 변경 수를 다시 확인하고 **Apply confirmed changes**를 실행합니다.
6. 서버는 적용 직전 현재 Catalog를 다시 비교하고 전체 revision·publication·provenance를 한 transaction으로
   기록합니다. 완료 후 **Verified immutable result**를 read-back하고 **Download applied definition files**로
   검증된 결과만 내려받습니다.

![Format definitions 변경 검토](../user-guide/images/current/administration-format-definitions-1440x900.png)

새로고침은 원본 파일 내용이나 token을 저장하지 않습니다. 주소의 exact `application_id`가 있으면 그
immutable application을 다시 읽습니다. 적용 전 복구는 source Artifact로 변경 비교를 다시 계산합니다.
stale plan은 기존 apply를 반복하지 않고 새 비교를 계산해야 합니다. 내부 자동화는 plan에 Artifact ID와
SHA-256을, apply에 같은 값과 서버가 반환한 `plan_fingerprint`, `delete_missing=false`, 새
`Idempotency-Key`를 사용합니다. 정의 세트에 없는 기존 객체나 Record는 삭제하지 않습니다.

## 4. 실제 Record 관리

Database가 구조를 정의한다면 **Records**는 선택한 Table 아래의 실제 데이터 항목을 검색·생성·수정합니다.
Records에서 필드를 추가하지 않습니다.

1. 현재 관리할 **Record type**을 선택하고 이름 또는 대표 field로 검색합니다. **Filters**에서 Folder,
   facets와 saved views를 사용합니다.
2. 결과 툴바의 **Display layout**을 선택하고 Name, 대표 field(예: Material code), Revision, Status 열에서
   한 행을 선택해 exact Record revision을 엽니다.
3. **Create record**는 새 실제 Record 입력 화면을 열고 **Save new record**가 revision 1을 저장합니다.
4. 기존 Record는 편집 제목 아래의 `Draft · Revision N`처럼 한 번 표시된 lifecycle과 exact revision을
   확인한 뒤 **Save new revision**으로 수정합니다. 기존 revision은 덮어쓰지 않습니다.
5. 브라우저 reload 뒤에도 URL에 고정된 Table/Folder/Record identity와
   exact revision을 다시 읽습니다. 존재하지 않는 좌표를 current, 첫 항목이나 다른 session 값으로
   대체하지 않습니다.
6. 여러 건은 **Import records**를 열어 **Read file columns → Validate records → Import validated records**
   순서로 진행합니다. 모든 행이 유효할 때만 한 번에 등록됩니다.

![검색 결과가 중심인 Records](../user-guide/images/current/administration-records-1440x900.png)

Folder parent와 Record Link 양 끝은 exact revision으로 고정됩니다. Link Type은 source/target Table,
양방향 표시 이름과 cardinality를 정의합니다. 링크를 종료할 때는 과거를 삭제하지 않고 비활성 revision을
추가합니다.

## 5. Access 부여와 회수

Access 표는 **Member | Role | Permissions | Action**을 같은 행에서 보여 줍니다. Permissions는
서버가 선택 역할에서 계산한 고정 작업 묶음이며 관리자가 직접 입력하지 않습니다.

1. **Grant access**를 열고 Member type에서 Team 또는 User ID를 선택합니다.
2. Team은 Identity provider와 Team name을, 사용자는 User ID를 입력합니다.
3. Role을 선택하고 **Permissions**를 확인합니다. Maximum classification, organization 범위와 Reason을
   결정한 뒤 **Grant access**를 실행합니다.
4. 현재 접근은 해당 행의 **Remove access**로 제거합니다. 확인 사유와 immutable 부여·제거 이력은
   서버에 보존되며 정상 표면은 active assignment에 집중합니다.

역할의 server-derived Permissions는 다음과 같습니다.

| 역할 | Permissions |
| --- | --- |
| User | Processing & calibration, Solver Card export |
| Reviewer | Processing & calibration, Model approval, Solver Card export |
| Administrator | Schema configuration, Catalog editing, Processing & calibration, Solver Card export |

Model approval은 Reviewer 역할에만 포함됩니다. 제품 화면은 역할별 기능을 임의로 조합하지 않으며,
export-controlled 접근은 별도 운영 승인이 필요합니다. User와 Reviewer는 Access 관리와 Format definitions
apply를 사용할 수 없습니다.

![Access assignments](../user-guide/images/current/administration-access-1920x1080.png)

## 6. 운영 점검

- Database/Configuration/Record type과 선택 정의의 exact revision을 확인합니다.
- Layout 필드 선택이 Attribute 삭제가 아니라 현재 datasheet 구성 변경인지 확인합니다.
- Format definitions의 no-write 비교와 확인 후 적용을 구분합니다.
- Record 생성·revision 저장 뒤 reload로 같은 exact 좌표를 read-back합니다.
- Access의 Member, Role, Permissions와 Remove access 이력을 확인합니다.
- 기존 데이터를 지우거나 role table을 직접 수정하지 않습니다.
