# Worker deployable

The worker entry point is `cmp.apps.worker:main`. T-18 provides a `plugin.run` handler bridge that
maps validated Result Manifests onto the durable T-15 Attempt contract. Deployment composition
must inject a trusted project-scoped service context, T-10 package/input materializer, result
committer, and selected runner adapter.

When those dependencies are absent, the CLI intentionally registers no handler and remains in
safe idle smoke-test mode. It never fabricates a service principal, object-store credential, or
mutable artifact reference.

