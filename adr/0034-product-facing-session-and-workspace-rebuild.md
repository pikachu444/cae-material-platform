# ADR-0034: Product-facing session and workspace rebuild

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
   by `docs/01-product/product-experience-spec.md`.
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
