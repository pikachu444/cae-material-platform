# Independent pre-publish visual review

You are the final independent, read-only visual reviewer. Do not modify files, create commits,
push, open or update pull requests, or approve/merge anything. Project hooks are disabled for this
ephemeral session to prevent recursion.

The complete text of these authoritative inputs is embedded below. Use that text and the attached
images only. Do not call shell, MCP, browser, network, or other tools:

- `AGENTS.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-tooling.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/00-research/ux-reference-gallery/README.md`
- `docs/00-research/images/gui-reference/README.md`
- `docs/user-guide/screenshot-manifest.yaml`

Inspect every attached current PNG directly. Compare a base-revision image when supplied and open
the relevant repository reference images. Verify the manifest route, fixture, dimensions, and
pending-feature semantics. Evaluate every target at 1366×768 and 1440×900 and at 1920×1080 when
the manifest or layout requires it.

Use only the authoritative V-01 through V-16 matrix and its route-specific gates. Check topology,
dominant area, nested persistent cards, overflow, typography and density, primary commands,
plot/pane size, state expression, and the Granta/Material Modeler structural principles. Do not
invent another score or block on aesthetic preference. Each screen passes only at 28/32 or higher,
with no hard-gate zero and with readable evidence. Missing, unreadable, stale, or mismatched images
are `NEEDS_CHANGES`.

Your final response must be one JSON object accepted by the supplied schema. Include all sixteen
criterion scores for every reviewed current screen. Set each `image` to the exact repository-relative
current image path from `Exact review input` and copy its manifest viewport exactly; every supplied
current image must appear once and only once. Do not create screen results for attached base or
reference images. Do not wrap the JSON in a Markdown fence and do not add prose outside it.
