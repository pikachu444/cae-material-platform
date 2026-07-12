"""T-18 local subprocess and OCI-ready isolated runner adapters."""

from cmp.modules.plugins.adapters.runner.oci import (
    OciExecutionPlan,
    OciOutputPolicy,
    OciPluginRunner,
    OciRuntime,
    OciRuntimeCapabilities,
)
from cmp.modules.plugins.adapters.runner.subprocess import SubprocessPluginRunner

__all__ = [
    "OciExecutionPlan",
    "OciOutputPolicy",
    "OciPluginRunner",
    "OciRuntime",
    "OciRuntimeCapabilities",
    "SubprocessPluginRunner",
]
