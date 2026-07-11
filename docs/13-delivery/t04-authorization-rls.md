# T-04 RBAC·ABAC 및 PostgreSQL RLS 구현 기록

## 1. 추적성

- Task: `T-04`
- Requirements: `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-006`
- ADR: `ADR-001`, `ADR-002`
- 선행 구현: T-03 principal/request context, T-06 tenant/classification columns

## 2. 권장 가정과 미결정 사항

1. 문서의 13개 role과 대표 권한을 보수적인 MVP action matrix로 구체화한다. Domain/Product의
   최종 승인이 오기 전까지 `ASSUMPTION`이다.
2. Platform/org/project admin은 business data read, review, release 권한을 자동으로 얻지 않는다.
3. Organization-wide binding은 `project_id=NULL`, project binding은 exact UUID로 표현한다.
4. 표준 clearance는 `internal < confidential < restricted`다. `export_controlled`는 별도 explicit
   flag로만 허용하며 nationality/compartment 판단은 구현하지 않는다.
5. 첫 배포는 single-enterprise 가정이므로 deployment-level platform role도 organization context
   안에서 조회한다. Platform-admin grant는 application API가 아니라 운영자 provisioning 전용이다.
6. Artifact download-token endpoint는 T-15 전까지 없으므로 T-04는 재사용 authorization guard와
   row/filter leakage 회귀를 제공하고 실제 transfer-token 검증은 T-15에서 연결한다.

## 3. Service-layer policy

`Permission`은 module/action을 명시한다. Role matrix는 deny-by-default이며 알 수 없는 action을
문자열 fallback으로 허용하지 않는다. `AuthorizationService`는 다음 순서로 decision을 만든다.

1. T-03 `SecurityContext`의 principal, issuer/groups, organization/project로 active binding을 찾는다.
2. principal 또는 exact-issuer group subject, org/project scope, valid/expiry/revoke를 다시 검증한다.
3. 요청 action을 부여하는 binding만 남긴다. 없으면 403이다.
4. 남은 binding 안에서만 role, 표준 max clearance, export flag를 합성한다.
5. 요청 action, 필요한 read, governance hook에 한정된 DB permission closure를 만든다.

따라서 data write role의 낮은 clearance와 무관한 consumer binding의 높은 clearance를 결합해
권한을 높일 수 없다.

## 4. Role binding persistence

`identity.role_binding`은 generic EAV가 아닌 explicit relation이다.

- opaque binding UUID, organization UUID, nullable project UUID
- fixed record classification `restricted`
- exactly one subject: principal FK 또는 `(group_issuer, group_name)`
- constrained role, `internal|confidential|restricted` max clearance, export flag
- valid-from/expiry, creator/time/grant reason
- nullable revoke actor/time/reason tuple
- tenant/subject lookup와 duplicate-grant indexes

Grant content는 immutable이고 delete를 금지한다. Update는 최초 revoke tuple을 원자적으로 쓰는
경우만 허용한다. Revoke된 row는 다시 바꿀 수 없다. Platform admin은 principal + org-wide row만
가능하고 application administration service로 신규 부여할 수 없다.

Org admin grant/revoke는 먼저 `identity.manage`를 service에서 검사하고 같은 decision을 DB
transaction에 bind한다. RLS는 selected organization/project, `created_by`/`revoked_by` actor까지
다시 검사한다.

## 5. PostgreSQL session과 RLS

Migration `20260711_003_T04_authorization_rls.py`는 `access_control` schema에 다음 fail-closed
function을 둔다.

- current principal/issuer/groups/permissions/clearance/export setting
- organization/project exact match
- classification rank와 `can_access_row(...)`
- runtime DB role이 relation owner/superuser/`BYPASSRLS`인지 확인하는 startup assertion

Adapter는 모든 setting을 `set_config(name, value, true)`로 설정해 현재 transaction 이후 pool에
남지 않게 한다. 같은 transaction에서 principal/org/project/request를 바꾸려 하면 application
level에서 거부한다. Authentication만 bind하면 permissions와 clearance가 비어 있으므로 role
binding own-read 외 resource row는 보이지 않는다.

Governance lifecycle table과 future tenant table은 command별 SELECT/INSERT/UPDATE/DELETE policy를
분리하고 `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`를 적용한다. Policy나 context가
없으면 row는 0건이며 write는 거부된다.

PostgreSQL 문서에 따라 FK/unique integrity check는 RLS를 우회한다. 이를 완화하기 위해 FK와
unique key에 organization/project/classification을 포함하고, hidden target과 존재하지 않는
target이 같은 SQLSTATE/constraint 표면을 내는지 회귀 테스트한다.

## 6. API 경계

`RequestAuthorizationDependency`는 T-03 authentication dependency 다음에 실행한다. Route마다
하나의 explicit `Permission`을 지정하고 성공 decision을 `request.state.authorization_decision`에
둔다. Repository transaction은 그 decision 없이 열지 않는다.

- binding 없음/권한 없음: sanitized 403 `CMP-AUTHZ-0001`
- policy store/RLS context 없음: sanitized 503 `CMP-AUTHZ-0002`
- token, binding detail, 다른 tenant 존재는 response에 포함하지 않음

`GET /api/v1/me`는 계속 identity/context만 반환한다. Role administration public endpoint는 아직
추가하지 않았고, 필요 시 별도 OpenAPI/JSON Schema 계약으로 만든다.

## 7. 검증

- Unit: 13 role matrix, conservative admin boundaries, principal/group/scope, expiry/revoke,
  classification/export, cross-binding non-composition, grant/revoke application service
- Migration: explicit table/check/FK/index/trigger/policy/function, no business table/JSON EAV,
  clean PostgreSQL upgrade/downgrade
- PostgreSQL: real non-owner `LOGIN NOSUPERUSER NOBYPASSRLS` role, own binding resolution,
  org/project/classification list/count/facet, missing/wrong permission, cross-project/high-class
  write rejection, one-way revoke, transaction rebind rejection
- Leakage: tenant composite FK hidden-vs-random target has identical `23503`/constraint result;
  tenant-scoped opaque UUID can repeat without cross-tenant unique collision
- Regression: T-03 principal/JWKS API and T-06 immutable revision/CAS/governance suites

## 8. 범위 제외

- 실제 Material, 시험, dataset, artifact-transfer 또는 solver resource endpoint
- nationality/export-control compartment engine
- lifecycle owner/team/SoD decision(T-29), audit hash chain(T-05)
- DB login secret, cluster role 생성, backup/migration role provisioning
- role-management public API와 UI
