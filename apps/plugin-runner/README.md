# Plugin runner deployable

Implemented by `T-18` as the `cmp-plugin-runner` file-protocol entry point. The API and generic
worker never import plugin implementations; only a short-lived subprocess or an attested OCI
runtime loads the immutable package entrypoint.

The bundled subprocess adapter is for reviewed synthetic/development packages and is not a hard
production security boundary. Production composition must supply an OCI runtime that attests a
digest-pinned image, non-root user, read-only root/input mounts, ephemeral output, network none,
no-new-privileges, no host sockets, syscall filtering, and CPU/memory/PID quotas.

