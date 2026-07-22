# T-71 Explorer-integrated search and saved Subset evidence

Date: `2026-07-19`

The live Docker service searches the configurable Catalog without leaving the Explorer. Searching
`DP780` returned eight exact current Record revisions: Material, State, Test JSON, Processing Output,
Material Model IR, Neutral Material JSON and the Abaqus/OpenRadioss native cards. Selecting the
Material result opened the same revision in the center Workflow graph with forward/reverse links and
its governed Material deep link.

The clean seed also created the immutable `DP780 workflow records` Subset
`97a1e311-412a-49dc-86a4-4a29b3dd124e`. The protected verifier confirmed that its filter definition
retains `text=DP780`, then independently verified the eight-node graph and the complete 13-component
Material-to-card package.

![Catalog search and exact Workflow graph on one surface](../images/t71-explorer-search-workflow.jpg)

During the reseed regression, the seed previously chose the first tabulated-plasticity model after a
processed IR had been added. It now selects the direct Dataset-derived model by the exact Dataset
revision and rejects a processed projection for that compatibility path. Repeated seeding completed
without overwriting any model, card or source revision.

Verification completed with the protected Docker/PostgreSQL demo verifier, 774 passing Python tests
(76 PostgreSQL tests are environment-gated in the default runner), 62 passing frontend tests, the
production web build and bundle budget, static typing, architecture checks and the user-guide gate.
