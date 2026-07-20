# Product experience specification

Status: `search-first contract; visual rules require approved reference comparison`

The authoritative visual contract is [`ux-visual-system.md`](ux-visual-system.md). A graph, form,
route, API connection, or screenshot alone is not proof of Granta/Material Modeler-level usability.
The reference topology, dominant-area ratio, density, surface grammar, and task continuity must pass
the measured comparison and product-owner review before production implementation.

## 1. Why this specification exists

The platform already has substantial persistence, revision, calculation and export foundations, but
the current web application exposes those foundations as disconnected technical screens. A working
API, a database row and a React form are not proof that a product capability is usable. This
specification defines the user-visible product that must sit on top of the existing engine.

The product has two primary workspaces:

1. **Material Database**, informed by the public browsing, datasheet, search, comparison and CAE
   usage concepts of Granta MI and Altair Material Data Center.
2. **Material Modeling**, informed by the public import, preparation, fitting, extrapolation and
   card-generation workflow of Altair Material Modeler.

Commercial branding, private schemas, proprietary algorithms and pixel-level screen copies are not
used. Functional similarity means that an experienced materials user recognizes the information
architecture and can complete the same public task sequence without learning platform internals.

## 2. Product boundary

### 2.1 What normal users see

The normal-user global navigation is limited to:

```text
Materials | Modeling | Activity
```

Normal users never configure or see an API base URL, bearer token, tenant identifier, RLS policy,
trace infrastructure or object-store key. A demo deployment creates or refreshes its user session
automatically. A non-demo deployment presents a normal login and keeps identity protocol details
behind the application boundary.

Technical support identifiers may appear only after an error, under an expandable diagnostic
section. They never replace a task-oriented error message and recovery action.

### 2.2 What administrators see

Administration exposes understandable product configuration:

- users and the `Administrator` / `User` roles;
- feature access for schema configuration, catalog editing, processing/modeling, approval and card
  export;
- database/profile, table, attribute, layout, subset and link-type configuration.

The internal authorization model may retain resource/action/scope rules for later fine-grained
policy, but the initial administrator UI does not require security vocabulary or policy expressions.

## 3. Material Database workspace

### 3.1 Search-first continuous workspace

```text
┌ Explorer / filters ──┬ Material results / Layout datasheet ──────────────────┐
│ Database / Profile   │ dense comparable rows or selected Record               │
│  Table / Folder      │ attributes, tables, curves and direct CAE action       │
│   Record             │ optional selected context opens only when width allows │
└──────────────────────┴────────────────────────────────────────────────────────┘
```

Search is the default entry, but the Contents Tree remains mounted in the same workspace while the
user opens records and follows links. It supports
Database/Profile, Table, nested Folder and Record nodes, lazy expansion, selection, breadcrumb,
deep links, saved Subsets and visible version state. A list of unrelated cards is not a tree.

### 3.2 Record experience

A record opens a Layout-driven datasheet. Material-facing tabs are:

```text
Overview | Properties | Curves | Test Data | Models | CAE Cards | Links
```

The material-facing tabs are `Overview | Properties | Curves | CAE Cards | Evidence`. Exact revision,
workflow, Layout choice, and additional administrative datasheets remain accessible in Evidence or
Advanced without making UUIDs the primary label. Linked and local values are visually distinct, and
following a link preserves the browse context.

### 3.3 Search, selection and comparison

The workspace provides quick search, advanced typed-attribute search, faceted filters, normalized
numeric ranges, unit-system selection, table/tile results, configurable columns, record selection,
comparison tables and curve overlay. Search results open the same datasheet used by tree browsing.

## 4. Material Modeling workspace

### 4.1 One cohesive graph-centered workbench

```text
┌ Curve / process tree ─┬ Current-step settings ribbon ─────────────────────────┐
│ specimens and curves  ├───────────────────────────────────────────────────────┤
│ ordered process       │ Raw / processed / fitted graph                       │
│                       │ overlay, residual, candidates and extrapolation       │
└───────────────────────┴───────────────────────────────────────────────────────┘
 Data → Process → Fit → Export
```

The plot stays visible while the user moves through the workflow. The selected step owns a shallow
settings ribbon above the plot; there is no permanent third inspector column. Raw, normalized,
processed, fitted and extrapolated curves have distinct legend and
line semantics. Changing an option updates a preview; only an explicit commit creates an immutable
result revision.

### 4.2 Required task flow

The workbench must let a user:

1. start from a Material/Test Data link or import JSON/CSV/XLSX;
2. confirm channel and unit mapping;
3. select curves, domains and missing-data policy;
4. add, reorder and configure processing methods;
5. compare raw and processed curves;
6. configure fitting model, parameters, bounds, weights and candidate selection;
7. compare fitted curves, residuals, diagnostics and extrapolation;
8. save the whole pipeline as a versioned Recipe and run it on multiple compatible datasets;
9. promote a reviewed result to Neutral Material JSON;
10. inspect mapping and download Abaqus/OpenRadioss native cards.

Metal, polymer and elastomer tracks share this shell and method registry. Family-specific methods
change the available steps and option schemas, not the navigation model.

## 5. Materials home and Activity

There is no separate Dashboard. `/` redirects to `/materials`. Activity contains recent modeling,
export, import, batch, and review work without placing infrastructure or exact identifiers in its
first viewport.

## 6. Demo dataset

The deterministic demo uses realistic synthetic hierarchy and never places the whole journey as
unrelated records under one table.

```text
Materials
├─ Metals
│  └─ Advanced High Strength Steels
│     └─ DP780
├─ Polymers
│  └─ Reference Viscoelastic Polymer
└─ Elastomers
   └─ Reference Rubber

Test Data
├─ Tensile
├─ Stress Relaxation
└─ Hyperelastic
```

Each Material datasheet links to exact Test Data, Processing/Recipe evidence, Neutral Material and
solver cards. The user must be able to discover the journey through the tree and search without
copying an identifier from documentation.

## 7. Completion gate

No capability is `implemented` at product level merely because DB/API/UI tests exist. Product
completion requires a clean deployment and an authenticated user session to prove this browser
journey without developer configuration:

```text
find material in tree/search
→ open datasheet and test curve
→ open Material Modeling
→ process and fit
→ compare candidates and extrapolation
→ save/reuse Recipe
→ create Neutral Material
→ inspect mapping
→ download Abaqus and OpenRadioss cards
→ return to linked Material datasheet
```

Evidence must include task-oriented Playwright assertions, current deterministic screenshots and a
user guide that starts from the product home page. API-only, seed-only and direct deep-link checks
are supporting engine evidence, not substitutes for this gate.
