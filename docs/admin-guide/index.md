# 관리자 가이드

이 가이드는 configurable Material Information System의 관리 기능을 설명한다. 현재 `main`에는
고정 Material/State 관리와 내부 권한이 있으며 아래 기능은 T-49, T-51, T-59 구현과 함께 실제
화면·스크린샷으로 갱신한다. 구현되지 않은 절차를 현재 사용 가능한 기능처럼 설명하지 않는다.

## 관리 대상

1. Workspace와 Catalog Table
2. typed Attribute Definition과 quantity/unit/validation
3. record datasheet Layout
4. saved query Subset
5. Folder tree
6. Link Type의 source/target/cardinality
7. Administrator/User와 feature grant

관리자는 새 Attribute를 추가해도 DB migration이나 배포를 수행하지 않는다. published schema
revision을 수정하지 않고 새 revision을 만든다. 기존 record revision은 당시 schema revision과
값을 유지한다.

## 현재 사용할 수 있는 관리 기능

- Material, Material State, Process, Lot/Batch와 fixed Property Set 생성
- organization/project/classification 경계의 기존 역할·permission 관리
- provenance, audit, review와 release evidence 조회

T-49 이후에는 이 문서에 Table/Attribute/Layout 생성 따라하기와 실제 GUI capture를 추가한다.

