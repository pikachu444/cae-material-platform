# T-03 OIDC Principal 및 Request Security Context 구현 기록

## 1. 추적성

- Task: `T-03`
- Requirements: `NFR-SEC-001`, `NFR-SEC-002`, `NFR-SEC-003`, `NFR-SEC-006`,
  `NFR-AUD-001`, `FR-API-001`
- ADR: `ADR-001`, `ADR-002`
- 표준: RFC 6750 bearer token, RFC 8725 JWT BCP, RFC 9068 JWT access-token profile

## 2. 관련 결정과 권장 가정

1. API는 access token만 받고 ID token을 API credential로 사용하지 않는다.
2. 신뢰 설정은 운영자가 지정한 단일 issuer/audience/JWKS URL과 비대칭 알고리즘 allowlist다.
   Token claim/header가 key endpoint나 issuer discovery를 선택하지 못한다.
3. `(issuer, subject)`를 외부 identity의 불변 key로 사용하고 내부 principal은 opaque UUIDv4로
   분리한다. Display name과 active flag는 mutable projection이다.
4. 검증된 token이 하나의 organization/project 선택 context를 제공한다고 가정한다. 이
   context는 authorization 결과가 아니며 membership/RBAC/ABAC와 RLS 적용은 T-04 범위다.
5. JIT provisioning은 운영 선택이며 기본값은 false다. 활성화 시 같은 외부 identity의 동시
   최초 요청은 PostgreSQL transaction advisory lock으로 직렬화한다.
6. `identity.principal`은 deployment-level actor projection이다. Organization마다 principal을
   복제하지 않고 T-04의 tenant-scoped role binding이 principal과 organization/project를 잇는다.

여러 issuer federation, account linking 관리 API, project 선택/token exchange 방식, group-role
mapping matrix는 실제 IdP/조직 정책이 필요하므로 확정하지 않았다.

## 3. 구현 경계와 계층

| 계층 | 구현 |
| --- | --- |
| Domain | user/service Principal, 검증된 token, authentication request, SecurityContext |
| Application | access-token verifier/principal repository port, fail-closed context service |
| OIDC adapter | strict PyJWT verifier, configured JWKS resolver, synthetic development test IdP |
| Persistence | explicit principal/external identity table mapping과 JIT resolution |
| API adapter | RFC 6750 bearer 처리, `/api/v1/me`, sanitized problem response |
| Composition | environment settings, SQLAlchemy session factory, OIDC adapter wiring |

Domain/application은 FastAPI, SQLAlchemy, PyJWT를 import하지 않는다. Identity module은 Material,
시험, fitting, solver 또는 plugin domain을 참조하지 않는다.

## 4. Token 검증

다음 조건을 모두 통과한 claim만 `VerifiedAccessToken`으로 변환한다.

- compact JWT 구조와 최대 길이
- `typ=at+jwt|application/at+jwt`
- 명시적인 비대칭 `alg` allowlist와 `kid`
- configured JWKS signature, exact issuer, audience
- `exp`, `iat`, `jti`, `sub`, configurable client-id claim
- non-zero organization/project UUID
- bounded, trimmed group과 scope
- service grant인 경우 `sub == client_id`

검증 실패 사유는 내부 code로 구분하지만 HTTP response는 token/claim/key 정보를 포함하지 않는
공통 401 problem으로 축약한다. JWKS나 principal store가 사용할 수 없으면 임의 허용하지 않고
503으로 fail closed한다.

## 5. PostgreSQL migration

`20260711_002_T03_identity_principal.py`는 다음 구조를 만든다.

### `identity.principal`

- `id UUID` primary key, adapter가 UUIDv4 생성
- `principal_type VARCHAR(16)` with `user|service` check
- `display_name VARCHAR(255)`, `active BOOLEAN`
- `created_at`, `updated_at` timezone timestamp와 순서 check
- `(principal_type, active)` index
- ID/type/created timestamp 변경 및 row delete 차단 trigger

### `identity.external_identity`

- `id UUID` primary key와 `principal_id` restricted foreign key
- `issuer VARCHAR(2048)`, `subject VARCHAR(255)`
- unique `(issuer, subject)`와 `principal_id` index
- `created_at`, monotonic `last_seen_at`
- issuer/subject/principal/created timestamp 변경 및 row delete 차단 trigger

Core attribute는 모두 explicit typed column이며 EAV 또는 JSON/JSONB payload가 없다. Identity
table은 tenant-owned resource가 아니므로 T-03에서 RLS를 붙이지 않는다. T-04가 tenant-owned
role binding과 모든 resource의 deny-by-default RLS를 추가한다.

## 6. API와 운영 설정

`GET /api/v1/me`는 bearer access token을 검증한 뒤 다음 request context를 반환한다.

- stable principal UUID, type, display name
- selected organization/project UUID
- normalized group/scope
- request UUID와 W3C traceparent

OIDC가 설정되지 않았으면 503, token이 없거나 잘못됐으면 401, inactive 또는 미등록
principal이면 403이다. Error body는 `application/problem+json`, response는 `Cache-Control:
no-store`와 `X-Request-ID`를 포함한다. Health endpoint는 계속 공개다.

필수 설정은 `CMP_DATABASE_URL`, `CMP_OIDC_ISSUER`, `CMP_OIDC_AUDIENCE`,
`CMP_OIDC_JWKS_URL`이다. 알고리즘, clock skew, JIT provisioning, loopback 개발 허용, client/org/
project/group/display/service-grant claim mapping을 별도 환경 변수로 조정할 수 있다. 일부 필수
OIDC 설정만 주어진 상태는 startup error로 거부한다.

## 7. 검증과 범위 제외

- Unit: user/service claim mapping, configurable claims, issuer/audience/expiry/type/algorithm,
  missing tenant, inactive principal, partial configuration
- API integration: synthetic RSA test IdP user/service token, `/me`, missing bearer, ID-token
  confusion, missing project, unconfigured fail-closed, sanitized correlation response
- Migration: offline explicit table/constraint/index/trigger와 JSON/EAV column 부재
- PostgreSQL integration: upgrade/downgrade, JIT on/off, UUIDv4 identity, concurrent first login,
  principal-type confusion, immutable external key와 timestamp guard
- Regression: 기존 health/worker/generated client/T-06 revision PostgreSQL suite

T-03은 password/MFA/authorization server, role binding, RBAC/ABAC, tenant RLS, audit hash chain,
Material, 시험 importer, fitting, solver exporter를 구현하지 않는다.
