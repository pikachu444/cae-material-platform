# Reference plugins

Contains synthetic, explicitly non-production TCK fixtures. `contract_echo` supplies seven
contract-only entrypoints and no scientific/domain behavior. This directory must never be imported
by the API process or generic worker; only an isolated runner may load a packaged entrypoint.

