# 관리자 가이드

이 가이드는 configurable Material Information System의 관리 기능을 설명한다. T-49에서
Table, typed Attribute, Layout과 Subset 관리가 실제 PostgreSQL/API/UI로 연결됐다. Folder,
Link Type, Explorer와 단순 feature grant는 각각 T-50/T-51/T-59에서 추가한다. 구현되지 않은
절차를 현재 사용 가능한 기능처럼 설명하지 않는다.

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

## Table과 Attribute 정의

1. Docker demo를 실행하고 [Catalog schema designer](http://127.0.0.1:5173/catalog/schema)를 연다.
2. **Connected token → Use local demo identity → Save connection**을 선택한다.
3. stable key, 표시명, classification과 설명을 입력해 Table revision 1을 만든다.
4. Table을 선택하고 stable Attribute key, 표시명과 data type을 입력한다.
5. `number`는 quantity semantics와 normalized UCUM-compatible unit을 함께 입력한다.
6. `discrete`는 중복 없는 허용값을, `record_reference`는 대상 Table을 선택한다.
7. 현재 Attribute revision들로 datasheet Layout을 만들고 필요하면 All records Subset을 만든다.

지원 data type은 `number`, `integer`, `text`, `boolean`, `date`, `discrete`, `file`, `curve`,
`record_reference`다. Attribute의 stable key와 data type은 기존 값을 바꾸지 않는다. 이름,
설명, validation 또는 Layout/Subset 정의를 고치면 API는 current ETag를 요구하고 새 revision을
추가한다. 수치 record value 저장소는 원본 값/단위 문자열과 정규화 값/단위/quantity semantics를
분리 보존하며 잘못된 조합을 DB에서도 거부한다. Record 입력과 Layout datasheet 소비는 T-50
범위이므로 현재 schema designer에서는 definition만 관리한다.

![T-49 Catalog schema designer](../15-demo/images/t49-configurable-catalog.png)

## 기존 관리 기능

- Material, Material State, Process, Lot/Batch와 fixed Property Set 생성
- organization/project/classification 경계의 기존 역할·permission 관리
- provenance, audit, review와 release evidence 조회

