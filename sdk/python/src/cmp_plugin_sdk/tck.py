"""Language-neutral compatibility findings shared by runner test harnesses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cmp_plugin_sdk.model import ExtensionDescriptor, ExtensionType


class TckSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class TckFinding:
    case: str
    severity: TckSeverity
    detail: str


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    findings: tuple[TckFinding, ...]

    @property
    def passed(self) -> bool:
        return not any(item.severity is TckSeverity.ERROR for item in self.findings)


ALL_EXTENSION_TYPES = frozenset(ExtensionType)


def check_declared_descriptor(
    descriptor: ExtensionDescriptor,
    *,
    expected_type: ExtensionType,
    declared_capabilities: tuple[str, ...],
) -> CompatibilityReport:
    findings: list[TckFinding] = []
    if descriptor.extension_type is not expected_type:
        findings.append(
            TckFinding(
                "manifest-schema-capability",
                TckSeverity.ERROR,
                "runtime extension type differs from the immutable manifest",
            )
        )
    if descriptor.capabilities != declared_capabilities:
        findings.append(
            TckFinding(
                "manifest-schema-capability",
                TckSeverity.ERROR,
                "runtime capabilities differ from the immutable manifest",
            )
        )
    if descriptor.sdk_api != "1.0":
        findings.append(
            TckFinding(
                "backward-compatibility",
                TckSeverity.ERROR,
                "extension does not implement SDK API 1.0",
            )
        )
    return CompatibilityReport(tuple(findings))


def check_extension_matrix(
    descriptors: tuple[ExtensionDescriptor, ...],
) -> CompatibilityReport:
    actual = {item.extension_type for item in descriptors}
    findings: list[TckFinding] = []
    missing = sorted(item.value for item in ALL_EXTENSION_TYPES - actual)
    duplicate_types = sorted(
        item.value
        for item in ALL_EXTENSION_TYPES
        if sum(value.extension_type is item for value in descriptors) != 1
    )
    if missing:
        findings.append(
            TckFinding(
                "seven-extension-matrix",
                TckSeverity.ERROR,
                "missing synthetic extension types: " + ", ".join(missing),
            )
        )
    if duplicate_types:
        findings.append(
            TckFinding(
                "seven-extension-matrix",
                TckSeverity.ERROR,
                "extension types must appear exactly once: "
                + ", ".join(duplicate_types),
            )
        )
    return CompatibilityReport(tuple(findings))
