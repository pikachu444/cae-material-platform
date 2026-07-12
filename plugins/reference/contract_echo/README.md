# Contract Echo TCK fixture

This package is a synthetic, non-production T-18 fixture. Its seven entrypoints all perform the
same generic byte echo/RNG behavior so the compatibility matrix can exercise every extension type
without implementing a test importer, scientific model, fitting algorithm, or solver exporter.

The TCK builds an immutable ZIP from this directory, computes its package and dependency-lock
digests, and patches those values only into the external Job Spec. Core API and worker modules must
never import this package; only the isolated runner process loads an entrypoint.
