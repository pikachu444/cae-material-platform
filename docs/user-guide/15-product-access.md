# 제품 역할 및 접근 상태

제품 목표 역할은 `User`, `Reviewer`, `Administrator`입니다. 현재 화면은 `Administrator`와 `User`
만 제공하며, `Reviewer`는 향후 접근 migration에서 추가됩니다. User는 재료를 찾고 보고 내려받고,
업로드 검토·처리·fitting·card 검토를 요청합니다. Reviewer는 User 작업에 더해 material/card를 검토하고
변경 요청·승인·다운로드 publish를 수행합니다. Administrator는 모든 접근·편집·구성·검토·승인을 수행합니다.

## 내 권한 확인

1. Docker demo를 실행하고 [Administration → Users & access](http://127.0.0.1:5173/administration/access)를 엽니다.
2. demo에서는 workspace가 자동으로 준비됩니다. 일반 배포에서는 관리자 계정으로 로그인합니다.
3. **My access**에서 현재 제품 역할과 다음 기능의 상태를 확인합니다.

| 기능 권한 | 허용되는 제품 작업 |
| --- | --- |
| Schema configuration | Table, Attribute, Layout, Subset, Link Type 구성 |
| Catalog editing | Catalog, Test, Dataset 레코드 생성과 새 revision 작성 |
| Processing & calibration | Recipe, batch, 통계, fitting, Neutral IR 승격 |
| Model approval | review 결정과 release 발행 |
| Solver Card export | mapping preflight, native card, bulk package 생성 |

제품에서 부여된 역할과 기능에 따라 사용할 수 있는 화면과 동작이 달라집니다. 사용할 수 없는
기능은 표시되지 않거나, 검토 요청 또는 관리자 문의 방법을 안내합니다.

## 현재 User 권한 부여

이 작업은 Administrator만 할 수 있습니다.

1. **Assign product access**에서 사용자 또는 팀 이름을 입력합니다.
2. 제품 역할을 `User`로 선택합니다.
3. 허용할 기능만 체크합니다. 예를 들어 solver card만 내려받을 사용자는 **Solver Card
   export**만 선택할 수 있습니다.
4. **Create assignment**를 누릅니다. 사용자는 새로 부여된 역할에서 허용된 기능만 볼 수 있습니다.

Reviewer를 현재 화면에서 선택할 수 있다고 가정하지 마십시오. 기능을 쓸 수 없으면 화면은 다음
행동(검토 요청 또는 관리자 문의)을 안내해야 하며, 기존 작업 문맥은 유지합니다. 허용되지 않은
동작은 화면에서 사용할 수 없으며 실행할 수도 없습니다.

## Administrator와 권한 회수

`Administrator`를 선택하면 다섯 기능과 access administration 권한이 함께 부여됩니다. 일부
기능만 가진 관리자는 만들지 않습니다. 권한을 변경하려면 기존 assignment의 **Revoke**를
누른 뒤 새 assignment를 생성합니다. 기존 행의 역할이나 체크 항목은 덮어쓰지 않습니다.

현재 demo group은 다음 값으로 미리 등록됩니다.

- issuer: `urn:cmp:demo-identity`
- group: `cmp-demo-material-team`
- role: `Administrator`


화면 캡처는 Codex 내장 브라우저의 좁은 viewport 증거입니다. 데스크톱에서는 같은 카드와
assignment form이 여러 열로 배치됩니다.
