# Administrator/User 및 기능 권한 사용법

서비스 화면에는 복잡한 내부 역할 대신 `Administrator`와 `User`만 표시됩니다. 실제 API와
PostgreSQL은 기존 세부 permission, organization/project 격리, classification 정책을 그대로
적용합니다. 따라서 화면을 단순화해도 데이터 경계가 느슨해지지 않습니다.

## 내 권한 확인

1. Docker demo를 실행하고 [Administration → Users & access](http://127.0.0.1:5173/administration/access)를 엽니다.
2. demo에서는 workspace가 자동으로 준비됩니다. 일반 배포에서는 관리자 계정으로 로그인합니다.
3. **My access**에서 제품 역할과 다음 다섯 기능의 상태를 확인합니다.

| 기능 권한 | 허용되는 제품 작업 |
| --- | --- |
| Schema configuration | Table, Attribute, Layout, Subset, Link Type 구성 |
| Catalog editing | Catalog, Test, Dataset 레코드 생성과 새 revision 작성 |
| Processing & calibration | Recipe, batch, 통계, fitting, Neutral IR 승격 |
| Model approval | review 결정과 release 발행 |
| Solver Card export | mapping preflight, native card, bulk package 생성 |

기존 상세 role binding과 resource/action/scope enforcement는 서버 내부에서 같은 제품 권한으로
안전하게 투영되지만 일반 화면에는 이 정책 용어를 표시하지 않습니다.

## User 권한 부여

이 작업은 Administrator만 할 수 있습니다.

1. **Assign product access**에서 사용자 또는 팀 이름을 입력합니다.
2. 제품 역할을 `User`로 선택합니다.
3. 허용할 기능만 체크합니다. 예를 들어 solver card만 내려받을 사용자는 **Solver Card
   export**만 선택할 수 있습니다.
4. **Create assignment**를 누릅니다. 운영 identity directory와 scope/classification 정책은 내부
   배포 설정에서 적용되며 이 일반 제품 form에는 노출되지 않습니다.

부여하지 않은 기능의 API는 403으로 거부됩니다. 화면에서 버튼을 숨기는 것만으로 권한을
구현하지 않으며, 서버의 permission 판정과 PostgreSQL RLS가 함께 적용됩니다.

## Administrator와 권한 회수

`Administrator`를 선택하면 다섯 기능과 access administration 권한이 함께 부여됩니다. 일부
기능만 가진 관리자는 만들지 않습니다. 권한을 변경하려면 기존 assignment의 **Revoke**를
누른 뒤 새 assignment를 생성합니다. 기존 행의 역할이나 체크 항목은 덮어쓰지 않습니다.

현재 demo group은 다음 값으로 미리 등록됩니다.

- issuer: `urn:cmp:demo-identity`
- group: `cmp-demo-material-team`
- role: `Administrator`

![통합 Administration의 제품 역할과 기능 권한 화면](../15-demo/images/t78-users-access.png)

화면 캡처는 Codex 내장 브라우저의 좁은 viewport 증거입니다. 데스크톱에서는 같은 카드와
assignment form이 여러 열로 배치됩니다.
