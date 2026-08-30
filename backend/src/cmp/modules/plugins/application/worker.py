"""Public application boundary for isolated plugin worker execution.

Worker composition consumes these application-level ports and approved runtime adapters.  The
adapter modules remain available for the generic T-18 implementation and compatibility imports,
but model-specific workers do not reach across the plugin module boundary into those private
layers.
"""

from cmp.modules.plugins.adapters.contracts.runner import JsonSchemaRunnerContractValidator
from cmp.modules.plugins.adapters.runner import SubprocessPluginRunner
from cmp.modules.plugins.adapters.worker.handler import (
    PLUGIN_JOB_TYPE,
    CommittedResultManifest,
    PluginAttemptHandler,
    PluginAttemptResult,
    PluginResultCommitter,
)

__all__ = [
    "PLUGIN_JOB_TYPE",
    "CommittedResultManifest",
    "JsonSchemaRunnerContractValidator",
    "PluginAttemptHandler",
    "PluginAttemptResult",
    "PluginResultCommitter",
    "SubprocessPluginRunner",
]
