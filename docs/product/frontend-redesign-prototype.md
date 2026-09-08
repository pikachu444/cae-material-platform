# Frontend foundation prototype

Status: RD-01 in progress. RD-00 governance and documentation are complete; this document records
the bounded prototype evidence. The later connected reader, write journeys, migration and cutover
remain open program rows.

The prototype is a task-first reader for stored Test Data and Solver Cards. Layout A puts the result
table first and keeps the selected detail beside it. Layout B uses the same Test Data/Card records,
query state, conditions and selection while giving the selected detail and scientific curve the full
width; **Results** returns to the list. Both layouts expose direct Test Data and Solver Cards paths.
An association is followed only when the selected object returns that concrete stored ID. Names are
displayed for recognition and the ID remains visible for exact selection.

Run the isolated prototype from the repository root:

```text
npm run dev:prototype
```

The review surface is `http://127.0.0.1:5174/`. `npm run dev` and the ordinary build use the live
gateway boundary and show an API-not-connected state; they do not load the synthetic fixture. Fixture
activation is limited to Vite's `prototype` mode. Scenario and layout controls are URL state, and a
display-title edit keeps the same ID and links in memory for the current page only.

The deterministic fixture contains 10,000 metadata rows. A selected tensile reference uses a
synthetic/non-production structural-steel reference context; the reader presents density, Young's
modulus and Poisson ratio as individually labeled values with units and applicability, separate from
the test conditions. Its bounded linear-elastic preview spans 0–0.1% engineering strain over a
1,000-position preview and a 1,000,000-point source, preserves original units and quantity semantics,
keeps a deliberate null gap, and renders explicit pointwise deviation metadata. The native OpenRadioss reference card is 504 bytes with SHA-256
`FE8873B1F6978D5BF30D4936EADBEE9FB3B3BF5CD086E4C827BDF2E6105829A1`. Unsupported or incomplete
mapping blocks download; approximated and ignored mapping requires acknowledgement for the selected
card ID. Card JSON is not used as a substitute for native file bytes.

The implementation and evidence are intentionally transient while RD-01 is reviewed. Component and
gateway tests run with `npm run test:prototype`; the full browser flow and 30 original A/B/state
screenshots plus negative states run with `npm run test:e2e --workspace @cmp/web-next`. The manifest
and images are written under `.artifacts/frontend-redesign-prototype/correction-1/` for this bounded
correction and record the source base, fixture hash, URL, layout, scenario, viewport and device-pixel
ratio. This synthetic prototype remains under visual review; visual disposition and the connected API
contract are required before the program advances to RD-02.
