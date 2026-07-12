"""Public T-18 Python SDK for isolated, contract-driven plugin implementations."""

from cmp_plugin_sdk.context import (
    CancellationRequested,
    DeadlineExceeded,
    OutputPolicyError,
    RunContext,
)
from cmp_plugin_sdk.model import (
    Diagnostic,
    DiagnosticSeverity,
    ExtensionDescriptor,
    ExtensionOutcome,
    ExtensionStatus,
    ExtensionType,
    PluginExtension,
    RunnerJobSpec,
    ValidationReport,
)

__version__ = "0.1.0"

__all__ = [
    "CancellationRequested",
    "DeadlineExceeded",
    "Diagnostic",
    "DiagnosticSeverity",
    "ExtensionDescriptor",
    "ExtensionOutcome",
    "ExtensionStatus",
    "ExtensionType",
    "OutputPolicyError",
    "PluginExtension",
    "RunContext",
    "RunnerJobSpec",
    "ValidationReport",
    "__version__",
]
