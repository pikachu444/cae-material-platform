# CMP Python Plugin SDK

This directory owns the framework-free T-18 authoring contract used inside an isolated plugin
runner. It exposes typed Job Spec views, scoped artifact I/O, bounded output writing,
deadline/cancellation signals, deterministic RNG, structured diagnostics, and the compatibility
test-kit primitives.

The standalone package version is `0.1.0` and implements SDK/runner contract `1.0`. Plugin code
implements `PluginExtension.describe`, `validate_job`, and `run`; it returns an
`ExtensionOutcome` while the runner itself constructs the immutable Result Manifest.

The SDK intentionally exposes no database session, core application service, object-store
credential, unrestricted HTTP client, or permanent filesystem API. The local subprocess adapter is
for reviewed synthetic/development packages only; production isolation is supplied by an OCI
runtime that enforces the execution plan outside Python.

The compatibility helpers live in `cmp_plugin_sdk.tck`. The repository TCK packages the
`plugins/reference/contract_echo` fixture and exercises all seven extension types without giving
any of them scientific semantics.

