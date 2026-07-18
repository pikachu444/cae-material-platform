# 관리자 가이드

이 가이드는 configurable Material Information System의 관리 기능을 설명한다. T-49/T-50에서
Table, typed Attribute, Layout, Subset, Folder와 typed Record 관리가 실제 PostgreSQL/API/UI로
연결됐고, T-51에서 Catalog/Workflow Explorer와 arbitrary Link Type이 추가됐다. 단순 feature
grant는 T-59에서 추가한다. 구현되지 않은 절차를 현재 사용 가능한 기능처럼 설명하지 않는다.

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
분리 보존하며 잘못된 조합을 DB에서도 거부한다. 실제 Record 입력은
[Catalog records](http://127.0.0.1:5173/catalog/records)에서 Layout 순서로 수행한다.

![T-49 Catalog schema designer](../15-demo/images/t49-configurable-catalog.png)

## Folder, Record와 saved Subset 운영

1. **Catalog records**에서 관리할 Table을 선택한다.
2. Folder 이름과 선택적 parent를 지정한다. 모든 parent는 exact Folder revision을 고정하고
   application과 PostgreSQL trigger가 cycle 및 다른 Table 연결을 차단한다.
3. Layout을 선택해 Record 입력 순서를 결정한다. Layout은 값을 복제하지 않고 Attribute revision
   표시 순서만 제공한다.
4. 검색 조건을 Subset으로 저장한다. Subset 수정은 기존 filter를 덮어쓰지 않고 새 revision을
   추가해야 한다.
5. Record 수정은 current ETag를 사용하며 기존 Record revision과 typed value row는 immutable이다.

## Link Type과 Record Link 운영

1. [Catalog Explorer](http://127.0.0.1:5173/catalog/explorer) 하단의 **Administrator · define
   Link Type**을 연다.
2. stable key/name, source/target Table, 방향별 표시명, outgoing/incoming cardinality를 정한다.
   Link Type revision은 두 Table의 정확한 current revision을 고정한다.
3. Record를 선택한 뒤 오른쪽 **Typed link editor**에서 적용 가능한 Link Type과 target Record를
   선택한다. 서버는 target의 exact current revision을 저장하며 `latest` 별칭은 받지 않는다.
4. endpoint Table 불일치, tenant/project/classification 불일치, 중복 active link와 cardinality
   위반은 application과 PostgreSQL trigger가 모두 거부한다.
5. 링크 관계를 종료할 때 **Deactivate**를 사용한다. 기존 revision은 감사와 재현을 위해 남는다.

Workflow Explorer는 forward/reverse label을 구분해 표시하며 링크 양 끝으로 이동할 수 있다.
Table이나 Record가 새 revision을 만들어도 기존 Link가 가리키는 revision은 바뀌지 않는다.

## 기존 관리 기능

- Material, Material State, Process, Lot/Batch와 fixed Property Set 생성
- organization/project/classification 경계의 기존 역할·permission 관리
- provenance, audit, review와 release evidence 조회

