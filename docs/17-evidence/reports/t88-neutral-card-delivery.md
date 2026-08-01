# T-88 In-workbench Neutral and solver-card delivery evidence

## Accepted outcome

The Metal workflow now finishes in a dedicated **Card** task inside the same Material Modeling
application shell:

- Card replaces the graph with an exact reviewed-result delivery workspace; it is not a drawer at the
  bottom of a long page;
- the selected Material and Material State use friendly revision labels while exact Processing Output,
  Material Model IR and Neutral Material revisions remain pinned internally;
- an existing canonical Neutral revision is restored instead of being silently duplicated;
- solver, version, material law, material ID and name are reviewed together;
- all six mapping meanings are visible, every field receives a state, approximation requires explicit
  acknowledgement and unsupported mapping blocks creation;
- after creation, evidence and mapping collapse so the native ASCII result and downloads have priority;
  the exact evidence remains reopenable in the same result context;
- Abaqus `.inp`, OpenRadioss `.rad` and mapping-report JSON downloads use immutable server bytes;
- the bulk action hands the exact selected sources to the existing checksum-package builder.

The cards remain `reference/non-production`. T-88 does not claim an Abaqus or OpenRadioss execution.

## Browser evidence

- [exact reviewed evidence and guided Card task](../images/historical-task-screenshots/t88-abaqus-card-delivery.png)
- [OpenRadioss LAW36 native ASCII preview](../images/historical-task-screenshots/t88-openradioss-card-delivery.png)

The Docker/PostgreSQL capture journey opens the top-level Card task, restores the existing exact DP780
Neutral Material, runs Abaqus preflight, acknowledges bounded transformation where required, creates
and downloads `.inp` plus mapping JSON, then repeats the process for OpenRadioss and verifies a `.rad`
download. It fails if the native preview is absent or the downloaded extension is wrong.

## Regression evidence

- component tests verify Card/Back-to-Fit task switching without losing the workbench;
- export tests verify the law label, six-state legend, approximation gate, result-first collapse and
  evidence reopening;
- the production build and bundle gate cover the integrated workspace;
- the merge gate runs the full frontend, Python/static/contract/document suite and isolated PostgreSQL
  integration suite.

T-88 accepts the cohesive Metal result-to-card interaction. Polymer relaxation/DMA graph parity is T-89;
Elastomer multi-mode graph parity is T-90.
