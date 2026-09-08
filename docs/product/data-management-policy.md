# Data management policy

Status: accepted D0-v3 target policy
Authority: accepted owner discussion recorded by [ADR-0036](../../adr/0036-material-only-revisions-and-data-links.md);
audit findings are evidence and do not replace this policy.

This policy is the canonical target for data identity, edit history and links during the frontend
redesign. It changes the persistence contract only through a later, real database/API migration. A
notice in a legacy document does not make a runtime field disappear.

## 1. The history boundary

Only edits to Material information have domain revision history. A Material information revision
contains the Material identity fields and the associated Material State, manufacturing and
heat-treatment information and direct property values that belong to that information, including
density, Young's modulus (`E`), Poisson's ratio (`nu`), yield information and applicability. The
revision is immutable after it is saved; the stable Material identity points to the current
information revision for convenient lookup.

State and PropertySet identities are ordinary stable objects. They do not acquire independent
domain histories merely because a Material information revision refers to them. A state label,
property-set label or other ordinary name can be corrected on the same stable object when the
application contract permits it.

Test conditions remain TestRun/TestData data. Specimen, TestRun, TestData, Dataset, Selection,
Mapping Profile, Process, Model, Solver Card and Link data use stable IDs and separate saved
objects. A rename updates the named object, preserves its links and does not stale scientific data.
The object is not silently rewritten into a new domain revision.

Changing the inputs or options currently eligible for a computation changes current eligibility and
the next allowed action. It does not mutate immutable saved bytes, a prior result, or a saved
object's scientific meaning. A saved result retains the actual inputs and settings used to produce
it as result data. These values are evidence for that result, not a new universal history system.

The following remain required:

- raw, input and output artifacts remain immutable and addressable by their exact stored bytes;
- original unit text, normalized unit, quantity semantics, scale/offset and channel meaning remain
  intact;
- actual typed input/output relations, processing and fit semantics, authorization, scientific
  validation and release meaning remain intact;
- unsupported, approximated, ignored and not-applicable mappings remain explicit, and unsupported
  mappings remain blocked;
- current pointers and eligibility may become stale after an upstream change, while saved data and
  its links remain readable.

The redesign removes the requirement for a universal Entity–Activity–Agent provenance graph, a
per-edit save reason, snapshot proliferation, and hidden nonmaterial revision writers. Provenance
is retained where a concrete result or artifact contract needs input usage, generation evidence or
responsibility; it is not a mandatory wrapper around every domain row. Software versions, schema
versions, source-file versions, hashes and opaque concurrency tokens are metadata for compatibility,
integrity and transport. They are not domain history.

## 2. Stable links and graph behavior

Links connect stable objects and preserve the typed relation and authorization scope. Relationship
traversal is not derivation: a graph reader can traverse both directions without claiming that one
endpoint was computed from the other. A link query never guesses a sibling card, matches by title,
or substitutes a `latest` object. Direct Test Data and direct Solver Cards paths can open
independently; a related card is shown only when the stored relation explicitly associates it.

The pilot journey is deliberately small and observable:

```text
ordinary-ID Test Data search/detail
  → explicitly associated stored Solver Card
  → native file download
```

Patching title metadata on the same ordinary Test Data row must preserve the row's stable ID and
the association, with zero nonmaterial domain revisions. The exact native file bytes remain
separate from the card's JSON representation.

## 3. Intake and exchange boundaries

The first governed tabular boundary accepts CSV, TSV and XLSX up to 16 MiB, 100,000 rows and 512
columns. CSV is UTF-8 with comma or semicolon delimiter; TSV uses a tab delimiter. Decimal syntax,
header presence and encoding are explicit inputs. XLSX uses one selected sheet or an explicit
`auto` single-sheet choice. Formula cells, macros, external references and unsafe ZIP content are
rejected. ZIP intake permits at most 128 members, 32 MiB total expanded content and a 100:1
expanded-to-packed ratio.

Canonical JSON is limited to 25 MiB, 512 channels and 1,000,000 points. A preview returns 500
points by default and at most 10,000; a full download returns the exact stored document. A
source-v2 Record JSON is a separate schema intake. It does not become an automatic Record →
compute bridge.

The raw path is ordered and resumable:

```text
create/resume → stream complete → server preview/detect → confirm mapping → import → read back
```

ProcessOutput is exchanged as direct JSON. Dataset CSV/Parquet are supported for bulk transfer;
there is no generic processed CSV/XLSX contract. A native solver file's bytes are not the card JSON.
Mapping reports use `exact`, `transformed`, `approximated`, `unsupported`, `ignored` and
`not_applicable`. `unsupported` blocks creation; approximation and ignore require explicit
acknowledgement.

## 4. Bounded scientific coverage

The redesign carries the existing reference boundaries forward without deciding a production
standard, material family, constitutive model, optimizer policy, solver card or validation
threshold. Metal has a bounded reference full flow. Single-temperature DMA and relaxation go
directly to Fit/Prony; fixed-frequency DMA temperature sweeps preserve the explicit TTS process.
The multi-DMA backend completed in #391 remains the source for the active #392 work and the next
#380 export work. Elastomer work remains restricted, and common Export outside the bounded metal
reference is not qualified by this policy.

## 5. Compatibility and migration

The v1 exact compatibility mapping is private. The unmodified v1 runtime is explicitly legacy until
the migration completes. Two old concrete revisions are imported as independent objects; they are
not reconstructed as a new head chain. Compatibility mapping must preserve bytes, units, typed
relations, authorization and scientific status while making the target identity model explicit.

Moving to this policy requires an actual database/API migration, read-back tests and rollback
evidence. Hiding a revision field in the UI, aliasing it to `latest`, or adding a second client-only
model is not migration. The migration preserves pre-cutover artifacts and backups and reconciles
new writes before old routes are retired.
