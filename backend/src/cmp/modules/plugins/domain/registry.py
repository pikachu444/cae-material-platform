"""Framework-free immutable plugin package registry invariants."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, cast
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

_PLUGIN_ID = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_CONTRACT_RANGE = re.compile(
    r"^>=([0-9]+)\.([0-9]+) <([0-9]+)\.([0-9]+)$"
)
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PluginRegistryError(Exception):
    """Base error for T-17 registry commands."""


class InvalidManifest(PluginRegistryError, ValueError):
    """Manifest, schema, or immutable artifact reference violates its contract."""


class PackageConflict(PluginRegistryError):
    """Plugin/version, digest, or idempotency identity maps to different content."""


class PackageNotFound(PluginRegistryError):
    """No package is visible in the selected tenant context."""


class PackageAccessDenied(PluginRegistryError):
    """Command classification exceeds the authorized project clearance."""


class InvalidPackageState(PluginRegistryError):
    """Verification, activation, or revocation is invalid for the current state."""


class ExtensionType(StrEnum):
    """Extension vocabulary from Manifest 1.0; core does not import implementations."""

    IMPORTER = "importer"
    PROCESSOR = "processor"
    STATISTICAL_ANALYZER = "statistical_analyzer"
    MATERIAL_MODEL = "material_model"
    CALIBRATOR = "calibrator"
    VALIDATOR = "validator"
    SOLVER_EXPORTER = "solver_exporter"


class SchemaRole(StrEnum):
    CONFIG = "config"
    INPUT = "input"
    OUTPUT = "output"
    EVIDENCE = "evidence"


class PackageState(StrEnum):
    CONTRACT_VALIDATED = "contract_validated"
    ELIGIBLE = "eligible"
    REJECTED = "rejected"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"


_STATE_TRANSITIONS: dict[PackageState, frozenset[PackageState]] = {
    PackageState.CONTRACT_VALIDATED: frozenset(
        {PackageState.ELIGIBLE, PackageState.REJECTED, PackageState.REVOKED}
    ),
    PackageState.ELIGIBLE: frozenset(
        {PackageState.REVOKED, PackageState.UNAVAILABLE}
    ),
    PackageState.UNAVAILABLE: frozenset({PackageState.REVOKED}),
    PackageState.REJECTED: frozenset(),
    PackageState.REVOKED: frozenset(),
}


def assert_package_transition(current: PackageState, target: PackageState) -> None:
    if target not in _STATE_TRANSITIONS[current]:
        raise InvalidPackageState(
            f"plugin package cannot transition from {current} to {target}"
        )


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be non-zero")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise InvalidManifest(f"{name} must be a string array")
    items = tuple(cast(list[str], value))
    if any(
        not item or item != item.strip() or len(item) > 100 or "\x00" in item
        for item in items
    ):
        raise InvalidManifest(f"{name} values must be trimmed and contain 1..100 characters")
    if tuple(sorted(set(items))) != items:
        raise InvalidManifest(f"{name} must be sorted and unique")
    return items


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_id: UUID
    sha256: str
    size_bytes: int
    media_type: str

    def __post_init__(self) -> None:
        _nonzero("artifact_id", self.artifact_id)
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("artifact sha256 must be lowercase hex")
        if not 0 <= self.size_bytes <= 9223372036854775807:
            raise ValueError("artifact size_bytes must fit a non-negative bigint")
        _trimmed("artifact media_type", self.media_type, 255)


@dataclass(frozen=True, slots=True)
class ExtensionDescriptor:
    ordinal: int
    extension_type: ExtensionType
    entrypoint: str
    capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.ordinal < 1:
            raise ValueError("extension ordinal must be positive")
        _trimmed("entrypoint", self.entrypoint, 500)
        if not self.capabilities:
            raise InvalidManifest("every extension requires at least one capability")
        if tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise InvalidManifest("extension capabilities must be sorted and unique")
        if any(_IDENTIFIER.fullmatch(item) is None for item in self.capabilities):
            raise InvalidManifest("capability must be a generic lowercase identifier")


def _supported_contract(contract_range: str, supported: tuple[int, int]) -> bool:
    match = _CONTRACT_RANGE.fullmatch(contract_range)
    if match is None:
        raise InvalidManifest("contract_api must use '>=major.minor <major.minor'")
    lower = (int(match.group(1)), int(match.group(2)))
    upper = (int(match.group(3)), int(match.group(4)))
    if lower >= upper:
        raise InvalidManifest("contract_api range must have an increasing upper bound")
    return lower <= supported < upper


@dataclass(frozen=True, slots=True)
class ImmutablePluginManifest:
    plugin_id: str
    display_name: str
    plugin_version: str
    package_digest: str
    contract_api: str
    extensions: tuple[ExtensionDescriptor, ...]
    network: str
    artifact_read_roles: tuple[str, ...]
    artifact_write_roles: tuple[str, ...]
    cpu: float
    memory_mb: int
    gpu: int
    timeout_s: int
    canonical_document: bytes
    manifest_digest: str

    @classmethod
    def from_validated_document(
        cls,
        document: object,
        *,
        supported_contract: tuple[int, int] = (1, 0),
    ) -> ImmutablePluginManifest:
        if not isinstance(document, dict):
            raise InvalidManifest("plugin manifest must be an object")
        value = cast(dict[str, Any], document)
        if value.get("manifest_version") != "1.0":
            raise InvalidManifest("manifest_version must be exactly 1.0")
        plugin_id = value.get("plugin_id")
        version = value.get("plugin_version")
        package_digest = value.get("package_digest")
        display_name = value.get("display_name")
        contract_api = value.get("contract_api")
        if (
            not isinstance(plugin_id, str)
            or len(plugin_id) > 255
            or _PLUGIN_ID.fullmatch(plugin_id) is None
        ):
            raise InvalidManifest("plugin_id is invalid")
        if (
            not isinstance(version, str)
            or len(version) > 64
            or _SEMVER.fullmatch(version) is None
        ):
            raise InvalidManifest("plugin_version must be an exact semantic version")
        if (
            not isinstance(package_digest, str)
            or not package_digest.startswith("sha256:")
            or _SHA256.fullmatch(package_digest.removeprefix("sha256:")) is None
        ):
            raise InvalidManifest("package_digest must be a lowercase SHA-256 digest")
        if not isinstance(display_name, str):
            raise InvalidManifest("display_name must be a string")
        _trimmed("display_name", display_name, 200)
        if (
            not isinstance(contract_api, str)
            or len(contract_api) > 100
            or not _supported_contract(contract_api, supported_contract)
        ):
            raise InvalidManifest("contract_api does not include supported runner contract 1.0")
        extension_values = value.get("extensions")
        if (
            not isinstance(extension_values, list)
            or not extension_values
            or len(extension_values) > 32767
        ):
            raise InvalidManifest("manifest requires at least one extension")
        extensions: list[ExtensionDescriptor] = []
        for ordinal, raw in enumerate(extension_values, start=1):
            if not isinstance(raw, dict):
                raise InvalidManifest("extension must be an object")
            extension_type = raw.get("type")
            entrypoint = raw.get("entrypoint")
            if not isinstance(extension_type, str) or not isinstance(entrypoint, str):
                raise InvalidManifest("extension type and entrypoint are required")
            capabilities = _strings(raw.get("capabilities"), "capabilities")
            extensions.append(
                ExtensionDescriptor(
                    ordinal,
                    ExtensionType(extension_type),
                    entrypoint,
                    capabilities,
                )
            )
        permissions = value.get("permissions")
        resources = value.get("resources")
        if not isinstance(permissions, dict) or not isinstance(resources, dict):
            raise InvalidManifest("permissions and resources must be objects")
        network = permissions.get("network")
        if network != "none":
            raise InvalidManifest("network permission must be deny-by-default 'none'")
        read_roles = _strings(
            permissions.get("artifact_read_roles"), "artifact_read_roles"
        )
        write_roles = _strings(
            permissions.get("artifact_write_roles"), "artifact_write_roles"
        )
        cpu = resources.get("cpu")
        memory_mb = resources.get("memory_mb")
        gpu = resources.get("gpu")
        timeout_s = resources.get("timeout_s")
        if not isinstance(cpu, (int, float)) or isinstance(cpu, bool):
            raise InvalidManifest("resources.cpu must be a finite positive number")
        cpu_decimal = Decimal(str(cpu))
        cpu_exponent = cpu_decimal.normalize().as_tuple().exponent
        if (
            not cpu_decimal.is_finite()
            or cpu_decimal <= 0
            or cpu_decimal > Decimal("9999999.999")
            or not isinstance(cpu_exponent, int)
            or cpu_exponent < -3
        ):
            raise InvalidManifest(
                "resources.cpu must fit a positive numeric(10,3) value"
            )
        if (
            not isinstance(memory_mb, int)
            or isinstance(memory_mb, bool)
            or not 64 <= memory_mb <= 2147483647
        ):
            raise InvalidManifest("resources.memory_mb must fit an integer and be at least 64")
        if (
            not isinstance(gpu, int)
            or isinstance(gpu, bool)
            or not 0 <= gpu <= 2147483647
        ):
            raise InvalidManifest("resources.gpu must fit a non-negative integer")
        if (
            not isinstance(timeout_s, int)
            or isinstance(timeout_s, bool)
            or not 1 <= timeout_s <= 2147483647
        ):
            raise InvalidManifest("resources.timeout_s must fit a positive integer")
        canonical = canonical_json_bytes(value)
        return cls(
            plugin_id,
            display_name,
            version,
            package_digest.removeprefix("sha256:"),
            contract_api,
            tuple(extensions),
            network,
            read_roles,
            write_roles,
            float(cpu_decimal),
            memory_mb,
            gpu,
            timeout_s,
            canonical,
            content_sha256(json.loads(canonical)),
        )

    def document(self) -> dict[str, Any]:
        value = json.loads(self.canonical_document)
        if not isinstance(value, dict):
            raise RuntimeError("canonical plugin manifest ceased to be an object")
        return value


@dataclass(frozen=True, slots=True)
class SchemaDocument:
    schema_id: str
    extension_ordinal: int
    role: SchemaRole
    canonical_document: bytes
    sha256: str

    @classmethod
    def from_validated_document(
        cls,
        *,
        schema_id: str,
        extension_ordinal: int,
        role: SchemaRole,
        document: object,
        expected_sha256: str,
    ) -> SchemaDocument:
        _trimmed("schema_id", schema_id, 500)
        if extension_ordinal < 1:
            raise InvalidManifest("schema extension_ordinal must be positive")
        if not isinstance(document, dict):
            raise InvalidManifest("registered schema must be a JSON object")
        if document.get("$id") != schema_id:
            raise InvalidManifest("registered schema_id must equal the document $id")
        canonical = canonical_json_bytes(document)
        digest = content_sha256(json.loads(canonical))
        if expected_sha256 != digest:
            raise InvalidManifest("registered schema digest does not match its document")
        return cls(schema_id, extension_ordinal, role, canonical, digest)

    def document(self) -> dict[str, Any]:
        value = json.loads(self.canonical_document)
        if not isinstance(value, dict):
            raise RuntimeError("canonical plugin schema ceased to be an object")
        return value


@dataclass(frozen=True, slots=True)
class ActivationRecord:
    id: UUID
    package_id: UUID
    activated_at: datetime
    activated_by: UUID
    reason: str
    request_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class PackageStateEventRecord:
    id: UUID
    package_id: UUID
    sequence_no: int
    from_state: PackageState | None
    to_state: PackageState
    occurred_at: datetime
    actor_id: UUID
    reason: str
    request_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class PackageRecord:
    id: UUID
    definition_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    manifest: ImmutablePluginManifest
    package_artifact: ArtifactReference
    signature_artifact: ArtifactReference
    sbom_artifact: ArtifactReference
    schemas: tuple[SchemaDocument, ...]
    state: PackageState
    state_events: tuple[PackageStateEventRecord, ...]
    submitted_at: datetime
    submitted_by: UUID
    submission_request_id: UUID
    submission_trace_id: str
    activation: ActivationRecord | None

    @property
    def activation_eligible(self) -> bool:
        return self.state is PackageState.ELIGIBLE

    @property
    def active(self) -> bool:
        return self.activation is not None and self.activation_eligible
