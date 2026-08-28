# ADR-0034: Product-facing session and workspace rebuild

## 먼저 읽기

- **무엇을 정했나요?** 기존 엔지니어링 기능은 유지하되, 제품 화면을 Material Database와 Material Modeling 작업 공간 중심으로 다시 구성합니다. 사용자는 한 출처의 제품 세션을 사용하고, 화면은 낮은 수준의 API를 직접 조합하는 대신 제품용 조회 모델을 통해 필요한 정보를 받습니다.
- **왜 중요한가요?** 일반 사용자가 API 주소, 토큰, 내부 모듈 페이지를 이해하지 않아도 재료를 찾고 모델링 작업을 이어 갈 수 있게 합니다. 임시 호환 화면이 남아 있다는 사실을 제품 경험 완성의 근거로 삼지 않습니다.
- **언제 읽나요?** 로그인과 세션, 기본 탐색 메뉴, Material Database·Material Modeling 작업 공간, 제품용 조회 API, 예전 경로의 호환 정책을 변경할 때 읽습니다.
- **용어를 쉽게 말하면:** same-origin session은 같은 웹 제품 안에서 안전하게 이어지는 로그인 상태입니다. 제품용 조회 모델은 화면이 바로 쓸 수 있게 묶은 데이터이고, compatibility route는 이전 주소를 잠시 유지하는 경로입니다. 제품 완성 근거는 내부 기능의 존재가 아니라 사용자가 정상 화면에서 끝까지 작업할 수 있다는 증거입니다.
- **상태 표기는?** Accepted는 이 제품 화면과 세션의 재구성 방향을 채택했다는 뜻입니다. 모든 엔지니어링 기능이 이미 만족스러운 제품 화면을 가졌거나 이전 작업이 끝났다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-19

## Context

The existing application proved many bounded domain and persistence contracts but exposed API
connection, bearer-token and infrastructure terminology to normal users. It also rendered Catalog
records and workflow links as flat panels and distributed modeling operations across module pages.
This did not satisfy the intended Granta/Material Data Center browsing experience or the cohesive
Material Modeler workflow.

## Decision

1. Keep PostgreSQL, immutable revisions, typed attributes/links, processing methods, Neutral IR and
   exporters as the engineering engine.
2. Replace the product-facing shell with Material Database and Material Modeling workspaces defined
   by `docs/product/desktop-engineering-ui-product-spec.md`.
3. The web application uses one same-origin product session. Demo deployments obtain and refresh a
   demo session without user configuration; normal deployments use a standard login. The product UI
   does not expose API URLs or bearer tokens. Existing bearer API support may remain for integrations
   and automated tests behind the product boundary.
4. Preserve `Administrator` and `User` as the visible roles. Existing granular enforcement remains
   an internal projection and an extension point for future resource/action/scope administration.
5. Add product read models for Contents Tree, Layout-driven datasheet/context and Modeling Session
   orchestration rather than making the browser compose a product from unrelated low-level APIs.
6. Existing flat routes may remain as temporary compatibility routes during cutover, but they are
   removed from primary navigation and cannot be used as product completion evidence.

## Consequences

- Product-facing frontend and some application query/orchestration APIs are replaced rather than
  cosmetically restyled.
- Core invariants and validated scientific/export code remain reusable.
- Demo and E2E tests must begin at the product home page and cannot inject a bearer token through a
  visible connection dialog.
- Capability status distinguishes engine implementation from accepted product experience.
