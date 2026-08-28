"""Application boundary for exact installed-format JSON Record registration (Issue #342).

The service intentionally composes the existing typed ``CatalogRecordService``.  JSON is
parsed and validated here, then converted to ``CatalogRecordValue`` instances before the
existing Record repository performs its normal current-revision, RLS, unit, and atomic
draft checks.  No generic JSON column is introduced as a business representation.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.catalog.application.configurable import AttributeSnapshot
from cmp.modules.catalog.application.records import (
    CatalogRecordService,
    CreateRecord,
    RecordSnapshot,
)
from cmp.modules.catalog.domain.configurable import AttributeDataType, ConfigurableCatalogConflict
from cmp.modules.catalog.domain.json_record_registration import (
    JSON_MEDIA_TYPE,
    JSON_PACKAGE_MEDIA_TYPE,
    MAX_PACKAGE_ARCHIVE_BYTES,
    JsonRegistrationDiagnostic,
    JsonRegistrationError,
    JsonRegistrationFile,
    JsonRegistrationFileResult,
    JsonRegistrationPreview,
    JsonRegistrationPreviewField,
    build_registration_package,
    curve_source_rows,
    exact_csv_filename,
    json_pointer,
    parse_strict_json,
    source_csv_bytes,
    validate_json_record,
    verify_registration_package,
)
from cmp.modules.catalog.domain.records import (
    CatalogRecordContent,
    CatalogRecordQuery,
    CatalogRecordValue,
    record_canonical,
)
from cmp.modules.datasets.application.canonical_test_data import NORMALIZED_PARQUET_SCHEMA
from cmp.modules.datasets.domain.curve_metadata import (
    CURVE_DEFINITION_PARQUET_KEY,
    CURVE_DEFINITION_SHA256_PARQUET_KEY,
    AxisRole,
    CurveChannel,
    CurveDefinition,
    OriginalUnit,
    UnitContract,
    ValueBasis,
    curve_definition_json_bytes,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.domain.revisions import content_sha256

JSON_REGISTRATION_TTL = timedelta(minutes=30)
JSON_CURVE_MEDIA_TYPE = "application/vnd.apache.parquet"
_APPROVED_JSON_LINK_KEYS = frozenset(
    {
        "technical_to_tensile",
        "technical_to_dma",
        "technical_to_fld",
        "tensile_to_elastoplasticity",
        "tensile_to_statistics",
    }
)
_EXACT_DOMAIN_BINDING_KINDS = frozenset(
    {
        "material",
        "material_state",
        "specimen",
        "test_run",
        "test_data",
        "processing_output",
        "material_model",
        "neutral_material",
        "solver_card",
        "neutral_solver_card",
        "release",
    }
)


def _curve_artifact_bytes(
    document: Mapping[str, Any], binding: JsonAttributeBinding
) -> bytes:
    """Encode one validated source curve as declared, immutable columnar bytes."""

    if binding.curve is None:
        raise ConfigurableCatalogConflict("curve binding metadata is missing")
    rows = curve_source_rows(document, pointer=binding.json_pointer, curve=binding.curve)
    curve = binding.curve
    x_unit = str(curve.get("x_unit") or "1")
    y_unit = str(curve.get("y_unit") or "1")
    x_semantics = str(curve.get("x_quantity") or "source.curve.x")
    y_semantics = str(curve.get("y_quantity") or "source.curve.y")
    definition = CurveDefinition(
        channels=(
            CurveChannel(
                key="x",
                label="Source x",
                quantity_semantics=x_semantics,
                axis_role=AxisRole.INDEPENDENT,
                unit_contract=UnitContract.EXPLICIT_LEGACY,
                dimension=None,
                original_units=(OriginalUnit(x_unit, "1"),),
                normalized_unit=x_unit,
                display_unit=x_unit,
                display_scale="1",
                display_offset="0",
                value_basis=ValueBasis.ORIGINAL,
            ),
            CurveChannel(
                key="y",
                label="Source y",
                quantity_semantics=y_semantics,
                axis_role=AxisRole.DEPENDENT,
                unit_contract=UnitContract.EXPLICIT_LEGACY,
                dimension=None,
                original_units=(OriginalUnit(y_unit, "1"),),
                normalized_unit=y_unit,
                display_unit=y_unit,
                display_scale="1",
                display_offset="0",
                value_basis=ValueBasis.ORIGINAL,
            ),
        )
    )
    metadata: dict[bytes, bytes] = {
        b"cmp.schema": NORMALIZED_PARQUET_SCHEMA.encode("utf-8"),
        CURVE_DEFINITION_PARQUET_KEY: curve_definition_json_bytes(definition),
        CURVE_DEFINITION_SHA256_PARQUET_KEY: definition.sha256.encode("ascii"),
    }
    table = pa.table(
        {
            "x": pa.array([row[0] for row in rows], type=pa.float64()),
            "y": pa.array([row[1] for row in rows], type=pa.float64()),
        }
    ).replace_schema_metadata(metadata)
    output = io.BytesIO()
    pq.write_table(table, output, compression="zstd", write_statistics=True)
    return output.getvalue()


class JsonRegistrationErrorCode(StrEnum):
    FORMAT_NOT_FOUND = "format_not_found"
    FORMAT_STALE = "stale_format"
    TOKEN_EXPIRED = "preview_expired"
    TOKEN_COMMITTED = "preview_committed"
    CALLER_MISMATCH = "preview_caller_mismatch"
    PACKAGE_MISMATCH = "preview_package_mismatch"
    REFERENCE_NOT_FOUND = "reference_not_found"
    REFERENCE_REVISION_REQUIRED = "reference_revision_required"
    SAME_BATCH_REFERENCE_UNSUPPORTED = "same_batch_reference_unsupported"
    REFERENCE_PIN_STALE = "reference_pin_stale"


@dataclass(frozen=True, slots=True)
class JsonAttributeBinding:
    """Exact schema-to-Attribute binding captured at format installation time."""

    json_pointer: str
    attribute: AttributeSnapshot
    source_unit: str | None = None
    quantity_semantics: str | None = None
    curve: Mapping[str, Any] | None = None
    section: str = ""
    # Exact source-schema x-key used for semantic projections.  This is internal binding
    # metadata and is intentionally omitted from response() and other API projections.
    source_key: str | None = None


@dataclass(frozen=True, slots=True)
class InstalledJsonRecordFormat:
    """Read-only projection of one installed exact format revision."""

    format_id: UUID
    format_revision_id: UUID
    format_key: str
    application_id: UUID
    application_revision_id: UUID
    schema_artifact_id: UUID
    schema_file: str
    schema_pointer: str
    schema_sha256: str
    table_id: UUID
    table_revision_id: UUID
    table_key: str
    table_source_file: str
    table_source_pointer: str
    table_source_sha256: str
    wrapper: str
    schema: Mapping[str, Any]
    attributes: tuple[JsonAttributeBinding, ...] = ()
    link_type_revision_ids: tuple[UUID, ...] = ()
    unit_profile_revision_ids: tuple[UUID, ...] = ()
    # Source-v2 reference-only arrays (for example Statistics -> Tensile) are not Catalog
    # Attributes.  Keep their exact table identity available to the atomic link projector.
    reference_table_ids: Mapping[str, UUID] = field(default_factory=dict)
    # The application manifest and the selected schema file can share one immutable source
    # Artifact, but their file/pointer/SHA coordinates remain distinct contract pins.
    application_source_artifact_id: UUID | None = None
    application_source_file: str | None = None
    application_source_pointer: str = "/"
    application_source_sha256: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("format_id", self.format_id),
            ("format_revision_id", self.format_revision_id),
            ("application_id", self.application_id),
            ("application_revision_id", self.application_revision_id),
            ("schema_artifact_id", self.schema_artifact_id),
            ("table_id", self.table_id),
            ("table_revision_id", self.table_revision_id),
        ):
            if value.int == 0:
                raise ValueError(f"{name} must be a non-zero UUID")
        for name, value in (
            ("schema_sha256", self.schema_sha256),
            ("table_source_sha256", self.table_source_sha256),
            ("application_source_sha256", self.application_source_sha256),
        ):
            if value is None:
                if name == "application_source_sha256":
                    continue
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
            if (
                len(value) != 64
                or value.lower() != value
                or any(c not in "0123456789abcdef" for c in value)
            ):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if not self.wrapper or not isinstance(self.schema, Mapping):
            raise ValueError("installed JSON format requires one schema wrapper")

    def response(self) -> dict[str, Any]:
        return {
            "format_id": str(self.format_id),
            "format_revision_id": str(self.format_revision_id),
            "format_key": self.format_key,
            "application_id": str(self.application_id),
            "application_revision_id": str(self.application_revision_id),
            "application_source": {
                "artifact_id": str(self.application_source_artifact_id or self.schema_artifact_id),
                "file": self.application_source_file or self.schema_file,
                "pointer": self.application_source_pointer,
                "sha256": self.application_source_sha256 or self.schema_sha256,
            },
            "schema": {
                "artifact_id": str(self.schema_artifact_id),
                "file": self.schema_file,
                "pointer": self.schema_pointer,
                "sha256": self.schema_sha256,
            },
            "table": {
                "id": str(self.table_id),
                "revision_id": str(self.table_revision_id),
                "key": self.table_key,
                "source_file": self.table_source_file,
                "source_pointer": self.table_source_pointer,
                "source_sha256": self.table_source_sha256,
            },
            "wrapper": self.wrapper,
            "attribute_bindings": [
                {
                    "pointer": item.json_pointer,
                    "attribute_id": str(item.attribute.id),
                    "attribute_revision_id": str(item.attribute.current.record.revision_id),
                    "attribute_key": item.attribute.current.content.key,
                    "data_type": item.attribute.current.content.data_type.value,
                    "source_unit": item.source_unit,
                    "quantity_semantics": item.quantity_semantics,
                    "curve": dict(item.curve) if item.curve is not None else None,
                    "section": item.section,
                }
                for item in self.attributes
            ],
            "link_type_revision_ids": [str(item) for item in self.link_type_revision_ids],
            "unit_profile_revision_ids": [str(item) for item in self.unit_profile_revision_ids],
        }


@dataclass(frozen=True, slots=True)
class JsonRegistrationToken:
    token: str
    format_revision_id: UUID
    caller_id: UUID
    package_sha256: str
    package_artifact_id: UUID | None
    classification: DataClassification
    files: tuple[JsonRegistrationFile, ...]
    documents: tuple[Mapping[str, Any], ...]
    results: tuple[JsonRegistrationFileResult, ...]
    created_at: datetime
    expires_at: datetime
    state: str = "open"
    batch_id: UUID | None = None
    committed_records: tuple[Any, ...] = ()
    # v1.0 callers use (file, component, kind, object_id, revision_id).  The
    # three-value form remains readable for direct in-process compatibility only;
    # the HTTP contract requires the file/component scope.
    domain_bindings: tuple[tuple[Any, ...], ...] = ()
    # Stored with the durable preview so an API worker can retry after losing its in-memory
    # token.  Keys retain both the JSON Pointer and identifier lookup forms.
    reference_pins: Mapping[tuple[str, str], Mapping[str, str]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JsonRegistrationSaveResult:
    batch_id: UUID
    replayed: bool
    records: tuple[Any, ...]
    package_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_id": str(self.batch_id),
            "replayed": self.replayed,
            "package_sha256": self.package_sha256,
            "lifecycle": "DRAFT",
            "records": [
                {
                    "record_id": str(item.id),
                    "record_revision_id": str(item.current.record.revision_id),
                    "revision_no": item.current.record.revision_no,
                    "external_key": item.current.content.external_key,
                }
                for item in self.records
            ],
            "publication": {"state": "DRAFT", "allowed": False},
        }


class JsonRegistrationReferenceResolver(Protocol):
    def __call__(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        table_id: UUID,
        external_key: str,
    ) -> Sequence[Any]: ...


class JsonRegistrationFormatResolver(Protocol):
    def __call__(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        format_revision_id: UUID,
    ) -> InstalledJsonRecordFormat | None: ...


class JsonRegistrationAsyncFormatResolver(Protocol):
    async def list_formats(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Sequence[InstalledJsonRecordFormat]: ...

    async def resolve_format(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        format_revision_id: UUID,
    ) -> InstalledJsonRecordFormat | None: ...


class JsonRegistrationDomainBindingResolver(Protocol):
    def __call__(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        binding: tuple[str, UUID, UUID],
    ) -> bool: ...


class JsonRegistrationPersistence(Protocol):
    def ensure_pending_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
    ) -> UUID: ...

    def persist_curve_artifact_in_transaction(
        self,
        *,
        session: Any,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        batch_id: UUID,
        component_ordinal: int,
        filename: str,
        json_pointer: str,
        artifact_id: UUID,
        artifact_sha256: str,
        artifact_size_bytes: int,
    ) -> None: ...

    def save_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
    ) -> None: ...

    def save_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
    ) -> None: ...

    def save_provenance(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
        records: Sequence[Any],
        resolved_links: Sequence[tuple[str, str, str, str, UUID, UUID]] = (),
    ) -> None: ...

    def commit_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
        batch_id: UUID,
    ) -> bool: ...

    def get_provenance(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
    ) -> Mapping[str, Any] | None: ...

    def persist_batch_in_transaction(
        self,
        *,
        session: Any,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
        records: Sequence[Any],
        resolved_links: Sequence[tuple[str, str, str, str, UUID, UUID]] = (),
    ) -> None: ...

    def load_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> Mapping[str, Any] | None: ...

    def load_committed_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> Mapping[str, Any] | None: ...


class JsonRecordRegistrationService:
    """Preview/save command with open→committed token semantics and exact replay."""

    def __init__(
        self,
        records: CatalogRecordService,
        *,
        formats: Mapping[UUID, InstalledJsonRecordFormat] | None = None,
        format_resolver: JsonRegistrationFormatResolver | None = None,
        async_format_resolver: JsonRegistrationAsyncFormatResolver | None = None,
        reference_resolver: JsonRegistrationReferenceResolver | None = None,
        domain_binding_resolver: JsonRegistrationDomainBindingResolver | None = None,
        artifact_service: Any | None = None,
        persistence: JsonRegistrationPersistence | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._records = records
        self._formats = dict(formats or {})
        self._format_resolver = format_resolver
        self._async_format_resolver = async_format_resolver
        self._reference_resolver = reference_resolver
        self._domain_binding_resolver = domain_binding_resolver
        self._artifacts = artifact_service
        self._persistence = persistence
        self._id = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._tokens: dict[str, JsonRegistrationToken] = {}
        self._provenance: dict[
            tuple[UUID, UUID],
            tuple[JsonRegistrationFile, Mapping[str, Any], InstalledJsonRecordFormat],
        ] = {}

    def register_format(self, value: InstalledJsonRecordFormat) -> None:
        self._formats[value.format_revision_id] = value

    def list_formats(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[InstalledJsonRecordFormat, ...]:
        self._require(context, decision, Permission.CATALOG_READ)
        return tuple(
            sorted(
                self._formats.values(),
                key=lambda item: (item.table_key, item.format_key, str(item.format_revision_id)),
            )
        )

    async def list_formats_async(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[InstalledJsonRecordFormat, ...]:
        self._require(context, decision, Permission.CATALOG_READ)
        if self._async_format_resolver is not None:
            values = await self._async_format_resolver.list_formats(context, decision)
            return tuple(
                sorted(
                    values,
                    key=lambda item: (
                        item.table_key,
                        item.format_key,
                        str(item.format_revision_id),
                    ),
                )
            )
        return self.list_formats(context, decision)

    def _format(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        format_revision_id: UUID,
        *,
        permission: Permission = Permission.CATALOG_WRITE,
    ) -> InstalledJsonRecordFormat:
        self._require(context, decision, permission)
        value = (
            self._format_resolver(context, decision, format_revision_id)
            if self._format_resolver is not None
            else self._formats.get(format_revision_id)
        )
        if value is None:
            raise ConfigurableCatalogConflict(JsonRegistrationErrorCode.FORMAT_NOT_FOUND.value)
        return value

    async def _format_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        format_revision_id: UUID,
        *,
        permission: Permission = Permission.CATALOG_WRITE,
    ) -> InstalledJsonRecordFormat:
        self._require(context, decision, permission)
        if self._async_format_resolver is not None:
            value = await self._async_format_resolver.resolve_format(
                context, decision, format_revision_id
            )
        else:
            value = self._format(
                context,
                decision,
                format_revision_id,
                permission=permission,
            )
        if value is None:
            raise ConfigurableCatalogConflict(JsonRegistrationErrorCode.FORMAT_NOT_FOUND.value)
        # Keep synchronous callers (including the durable CSV projection) exact and compatible
        # after an asynchronous production lookup; this is an immutable format cache, not a
        # mutable revision fallback.
        self._formats[value.format_revision_id] = value
        return value

    @staticmethod
    def _root_wrapper(document: Any) -> str | None:
        """Return a root wrapper only when the source has exactly one root member."""

        if not isinstance(document, Mapping) or len(document) != 1:
            return None
        value = next(iter(document))
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _format_diagnostic(
        file: JsonRegistrationFile,
        *,
        code: str,
        message: str,
        recovery: str,
    ) -> JsonRegistrationDiagnostic:
        return JsonRegistrationDiagnostic(
            file.filename,
            code,
            message,
            recovery,
            "/",
        )

    def _available_formats(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[InstalledJsonRecordFormat, ...]:
        del context, decision
        return tuple(
            sorted(
                self._formats.values(),
                key=lambda item: (
                    item.wrapper,
                    item.table_key,
                    item.format_key,
                    str(item.format_revision_id),
                ),
            )
        )

    def _resolve_preview_format(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        format_revision_id: UUID | None,
        files: Sequence[JsonRegistrationFile],
    ) -> tuple[
        InstalledJsonRecordFormat | None,
        dict[str, tuple[JsonRegistrationDiagnostic, ...]],
    ]:
        """Resolve one exact installed format from source roots, never from UI ordering."""

        if format_revision_id is not None:
            value = self._format(context, decision, format_revision_id)
            diagnostics: dict[str, tuple[JsonRegistrationDiagnostic, ...]] = {}
            for file in files:
                try:
                    document = parse_strict_json(file.content, filename=file.filename)
                except JsonRegistrationError:
                    # The strict parser diagnostic is emitted by the normal validation pass.
                    continue
                root = self._root_wrapper(document)
                if root != value.wrapper:
                    diagnostics[file.filename] = (
                        self._format_diagnostic(
                            file,
                            code="wrapper_mismatch",
                            message=(
                                f"The source root wrapper '{root or '/'}' does not match the "
                                f"installed format wrapper '{value.wrapper}'."
                            ),
                            recovery=(
                                "Choose a source file with the same installed wrapper, or "
                                "preview again with the matching exact format."
                            ),
                        ),
                    )
            return value, diagnostics

        formats = self._available_formats(context, decision)
        roots: dict[str, str] = {}
        for file in files:
            try:
                root = self._root_wrapper(parse_strict_json(file.content, filename=file.filename))
            except JsonRegistrationError:
                continue
            if root is not None:
                roots[file.filename] = root
        diagnostics: dict[str, tuple[JsonRegistrationDiagnostic, ...]] = {}
        distinct_roots = set(roots.values())
        if len(distinct_roots) > 1:
            for file in files:
                diagnostics[file.filename] = (
                    self._format_diagnostic(
                        file,
                        code="mixed_record_type",
                        message="All files in one batch must use the same root wrapper.",
                        recovery="Keep one installed record type in the batch and preview again.",
                    ),
                )
            return None, diagnostics
        if not distinct_roots:
            for file in files:
                diagnostics[file.filename] = (
                    self._format_diagnostic(
                        file,
                        code=JsonRegistrationErrorCode.FORMAT_NOT_FOUND.value,
                        message="The server could not detect an installed JSON Record wrapper.",
                        recovery=(
                            "Correct the JSON root or install the exact Record format, "
                            "then retry."
                        ),
                    ),
                )
            return None, diagnostics
        wrapper = next(iter(distinct_roots))
        candidates = tuple(item for item in formats if item.wrapper == wrapper)
        if not candidates:
            for file in files:
                diagnostics[file.filename] = (
                    self._format_diagnostic(
                        file,
                        code=JsonRegistrationErrorCode.FORMAT_NOT_FOUND.value,
                        message=f"No installed exact JSON format matches root wrapper '{wrapper}'.",
                        recovery="Install the exact format for this Record type, then retry.",
                    ),
                )
            return None, diagnostics
        if len(candidates) != 1:
            for file in files:
                diagnostics[file.filename] = (
                    self._format_diagnostic(
                        file,
                        code="format_ambiguous",
                        message=(
                            "More than one installed exact format matches root "
                            f"wrapper '{wrapper}'."
                        ),
                        recovery=(
                            "Ask an administrator to make one exact format revision "
                            "eligible, then retry."
                        ),
                    ),
                )
            return None, diagnostics
        return candidates[0], diagnostics

    @staticmethod
    def _require(
        context: SecurityContext, decision: AuthorizationDecision, permission: Permission
    ) -> None:
        if (
            decision.permission is not permission
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise ConfigurableCatalogConflict(
                "authorization decision does not match JSON registration context"
            )

    @staticmethod
    def _read_decision(decision: AuthorizationDecision) -> AuthorizationDecision:
        """Use the read half of a write request when resolving pinned references."""

        if decision.permission is Permission.CATALOG_READ:
            return decision
        if Permission.CATALOG_READ.value not in decision.database_permissions:
            raise ConfigurableCatalogConflict(
                "catalog.read permission is required to resolve exact references"
            )
        return replace(decision, permission=Permission.CATALOG_READ)

    def _validate_domain_bindings(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        bindings: Sequence[tuple[Any, ...]],
    ) -> tuple[tuple[Any, ...], ...]:
        """Validate caller-supplied exact domain pins before the atomic create."""

        if not bindings:
            return ()
        read_decision = self._read_decision(decision)
        resolver = self._domain_binding_resolver
        if resolver is None:
            resolver = getattr(self._records._repository, "validate_exact_domain_binding", None)
        if resolver is None:
            raise ConfigurableCatalogConflict("exact domain binding validation is unavailable")
        validated: list[tuple[Any, ...]] = []
        seen: set[tuple[Any, ...]] = set()
        for binding in bindings:
            if len(binding) == 3:
                file_name: str | None = None
                component: str | None = None
                kind, object_id, revision_id = binding
            elif len(binding) == 5:
                file_name, component, kind, object_id, revision_id = binding
                if (
                    not isinstance(file_name, str)
                    or not file_name
                    or not isinstance(component, str)
                    or not component
                ):
                    raise ConfigurableCatalogConflict(
                        "domain binding pin must identify one file and package component"
                    )
            else:
                raise ConfigurableCatalogConflict(
                    "domain binding pin must contain file, component, kind, object, and revision"
                )
            if not isinstance(kind, str) or kind not in _EXACT_DOMAIN_BINDING_KINDS:
                raise ConfigurableCatalogConflict("domain binding kind is not supported")
            if (
                not isinstance(object_id, UUID)
                or not isinstance(revision_id, UUID)
                or object_id.int == 0
                or revision_id.int == 0
            ):
                raise ConfigurableCatalogConflict(
                    "domain binding pin must identify an exact revision"
                )
            normalized = (
                (file_name, component, kind, object_id, revision_id)
                if file_name is not None and component is not None
                else (kind, object_id, revision_id)
            )
            resolver_binding = (kind, object_id, revision_id)
            if normalized in seen:
                raise ConfigurableCatalogConflict("duplicate exact domain binding pin")
            seen.add(normalized)
            if not resolver(
                context,
                read_decision,
                classification=classification,
                binding=resolver_binding,
            ):
                raise ConfigurableCatalogConflict(
                    "domain binding target must be an exact revision in the same scope"
                )
            validated.append(normalized)
        return tuple(validated)

    @staticmethod
    def _diagnostic(
        file: JsonRegistrationFile, error: JsonRegistrationError
    ) -> JsonRegistrationDiagnostic:
        return JsonRegistrationDiagnostic(
            file.filename,
            error.code,
            str(error),
            error.recovery,
            error.pointer,
            error.line,
            error.column,
            error.byte_offset,
        )

    def _reference_pins(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document: Mapping[str, Any],
        format_value: InstalledJsonRecordFormat,
        *,
        filename: str,
        pins: Mapping[tuple[str, str], Mapping[str, str]],
        batch_keys: set[str],
    ) -> tuple[dict[str, tuple[UUID, UUID]], tuple[JsonRegistrationDiagnostic, ...]]:
        if not any(
            binding.attribute.current.content.data_type is AttributeDataType.RECORD_REFERENCE
            for binding in format_value.attributes
        ):
            return {}, ()
        decision = self._read_decision(decision)
        resolved: dict[str, tuple[UUID, UUID]] = {}
        diagnostics: list[JsonRegistrationDiagnostic] = []
        for binding in format_value.attributes:
            if (
                binding.attribute.current.content.data_type
                is not AttributeDataType.RECORD_REFERENCE
            ):
                continue
            try:
                raw = json_pointer(document, binding.json_pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if raw is None:
                continue
            reference = binding.attribute.current.content
            if not isinstance(raw, str) or not raw.strip() or reference.reference_table_id is None:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        "reference_invalid",
                        "Record reference must be a non-empty identifier.",
                        "Correct the exact reference field and preview again.",
                        binding.json_pointer,
                    )
                )
                continue
            identifier = raw.strip()
            if identifier.casefold() in batch_keys:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        JsonRegistrationErrorCode.SAME_BATCH_REFERENCE_UNSUPPORTED.value,
                        "Same-batch human references are not supported by the v1 importer.",
                        "Save the referenced Record first, then pin its exact immutable revision.",
                        binding.json_pointer,
                    )
                )
                continue
            pin = pins.get((filename, binding.json_pointer)) or pins.get((filename, identifier))
            if pin is not None:
                try:
                    target_id = UUID(str(pin["record_id"]))
                    revision_id = UUID(str(pin["revision_id"]))
                except (KeyError, TypeError, ValueError) as error:
                    diagnostics.append(
                        JsonRegistrationDiagnostic(
                            filename,
                            "reference_pin_invalid",
                            "Reference pin must include record_id and revision_id.",
                            "Choose the exact immutable Record revision in the reference picker.",
                            binding.json_pointer,
                        )
                    )
                    del error
                    continue
                try:
                    target_revision = self._records.get_record_revision(
                        context,
                        decision,
                        target_id,
                        revision_id,
                    )
                    if (
                        target_revision.content.table_id != reference.reference_table_id
                        or target_revision.content.external_key != identifier
                        or str(pin.get("content_hash", ""))
                        != content_sha256(record_canonical(target_revision.content))
                    ):
                        raise ValueError("reference identity, table, or content hash changed")
                except Exception as error:
                    diagnostics.append(
                        JsonRegistrationDiagnostic(
                            filename,
                            JsonRegistrationErrorCode.REFERENCE_PIN_STALE.value,
                            "The pinned reference revision is missing or has changed.",
                            "Choose the same immutable Record revision again and preview again.",
                            binding.json_pointer,
                        )
                    )
                    del error
                    continue
                resolved[binding.json_pointer] = (target_id, revision_id)
                continue
            candidates = (
                self._reference_resolver(
                    context,
                    decision,
                    table_id=reference.reference_table_id,
                    external_key=identifier,
                )
                if self._reference_resolver is not None
                else self._current_reference(
                    context, decision, reference.reference_table_id, identifier
                )
            )
            if len(candidates) == 0:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        JsonRegistrationErrorCode.REFERENCE_NOT_FOUND.value,
                        "No eligible immutable Record revision matches this human identifier.",
                        (
                            "Select or create an eligible referenced Record, then supply "
                            "an exact revision pin."
                        ),
                        binding.json_pointer,
                    )
                )
            elif len(candidates) > 1:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        JsonRegistrationErrorCode.REFERENCE_REVISION_REQUIRED.value,
                        (
                            "More than one eligible immutable Record revision matches this "
                            "human identifier."
                        ),
                        "Choose the exact Record revision; latest/head is not a valid fallback.",
                        binding.json_pointer,
                    )
                )
            else:
                target = candidates[0]
                resolved[binding.json_pointer] = (target.id, target.current.record.revision_id)
        return resolved, tuple(diagnostics)

    def _reference_links(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        document: Mapping[str, Any],
        format_value: InstalledJsonRecordFormat,
        *,
        filename: str,
        pins: Mapping[tuple[str, str], Mapping[str, str]],
        batch_keys: set[str],
        resolved: Mapping[str, tuple[UUID, UUID]],
    ) -> tuple[
        tuple[tuple[str, str, str, UUID, UUID], ...],
        tuple[JsonRegistrationDiagnostic, ...],
    ]:
        """Resolve approved source-v2 references for the atomic Record Link projector.

        Reference-only arrays are intentionally absent from Catalog Attribute storage.  Walk the
        installed schema metadata as well as ordinary Record-reference Attributes so a Statistics
        row produces one exact Tensile link for every declared source ID.
        """

        def has_approved_reference(node: Any) -> bool:
            if isinstance(node, Mapping):
                reference = node.get("x-reference")
                if (
                    isinstance(reference, Mapping)
                    and reference.get("link_key") in _APPROVED_JSON_LINK_KEYS
                ):
                    return True
                return any(has_approved_reference(value) for value in node.values())
            if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
                return any(has_approved_reference(value) for value in node)
            return False

        if not has_approved_reference(format_value.schema):
            return (), ()
        decision = self._read_decision(decision)
        links: list[tuple[str, str, str, UUID, UUID]] = []
        diagnostics: list[JsonRegistrationDiagnostic] = []

        def escape(value: str) -> str:
            return value.replace("~", "~0").replace("/", "~1")

        def resolve_identifier(
            pointer: str,
            identifier: str,
            target_table_id: UUID,
        ) -> tuple[UUID, UUID] | None:
            normalized = identifier.strip()
            if not normalized:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        "reference_invalid",
                        "Record reference must be a non-empty identifier.",
                        "Correct the exact reference field and preview again.",
                        pointer,
                    )
                )
                return None
            if normalized.casefold() in batch_keys:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        JsonRegistrationErrorCode.SAME_BATCH_REFERENCE_UNSUPPORTED.value,
                        "Same-batch human references are not supported by the v1 importer.",
                        "Save the referenced Record first, then pin its exact immutable revision.",
                        pointer,
                    )
                )
                return None
            # Identifier-first lookup permits one pin per member of a reference-only
            # array; the pointer key remains the scalar/reference compatibility form.
            pin = pins.get((filename, normalized)) or pins.get((filename, pointer))
            if pin is not None:
                try:
                    target_id = UUID(str(pin["record_id"]))
                    revision_id = UUID(str(pin["revision_id"]))
                except (KeyError, TypeError, ValueError):
                    diagnostics.append(
                        JsonRegistrationDiagnostic(
                            filename,
                            "reference_pin_invalid",
                            "Reference pin must include record_id and revision_id.",
                            "Choose the exact immutable Record revision in the reference picker.",
                            pointer,
                        )
                    )
                    return None
                try:
                    target_revision = self._records.get_record_revision(
                        context,
                        decision,
                        target_id,
                        revision_id,
                    )
                    if (
                        target_revision.content.table_id != target_table_id
                        or target_revision.content.external_key != normalized
                        or str(pin.get("content_hash", ""))
                        != content_sha256(record_canonical(target_revision.content))
                    ):
                        raise ValueError("reference identity, table, or content hash changed")
                except Exception:
                    diagnostics.append(
                        JsonRegistrationDiagnostic(
                            filename,
                            JsonRegistrationErrorCode.REFERENCE_PIN_STALE.value,
                            "The pinned reference revision is missing or has changed.",
                            "Choose the same immutable Record revision again and preview again.",
                            pointer,
                        )
                    )
                    return None
                return target_id, revision_id
            candidates = (
                self._reference_resolver(
                    context,
                    decision,
                    table_id=target_table_id,
                    external_key=normalized,
                )
                if self._reference_resolver is not None
                else self._current_reference(context, decision, target_table_id, normalized)
            )
            if len(candidates) == 0:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        JsonRegistrationErrorCode.REFERENCE_NOT_FOUND.value,
                        "No eligible immutable Record revision matches this human identifier.",
                        (
                            "Select or create an eligible referenced Record, then supply "
                            "an exact revision pin."
                        ),
                        pointer,
                    )
                )
                return None
            if len(candidates) > 1:
                diagnostics.append(
                    JsonRegistrationDiagnostic(
                        filename,
                        JsonRegistrationErrorCode.REFERENCE_REVISION_REQUIRED.value,
                        (
                            "More than one eligible immutable Record revision matches "
                            "this human identifier."
                        ),
                        "Choose the exact Record revision; latest/head is not a valid fallback.",
                        pointer,
                    )
                )
                return None
            target = candidates[0]
            return target.id, target.current.record.revision_id

        def visit(node: Mapping[str, Any], pointer: str) -> None:
            reference = node.get("x-reference")
            if isinstance(reference, Mapping):
                link_key = reference.get("link_key")
                source_table_key = reference.get("source_table_key")
                target_table_key = reference.get("target_table_key")
                if (
                    isinstance(link_key, str)
                    and link_key in _APPROVED_JSON_LINK_KEYS
                    and isinstance(source_table_key, str)
                    and isinstance(target_table_key, str)
                ):
                    if format_value.table_key == target_table_key:
                        referenced_table_key = source_table_key
                    elif format_value.table_key == source_table_key:
                        referenced_table_key = target_table_key
                    else:
                        referenced_table_key = ""
                    referenced_table_id = format_value.reference_table_ids.get(referenced_table_key)
                    if referenced_table_id is None:
                        diagnostics.append(
                            JsonRegistrationDiagnostic(
                                filename,
                                "reference_binding_invalid",
                                f"Link '{link_key}' has no exact referenced Table binding.",
                                (
                                    "Use the installed source-v2 application bindings "
                                    "and preview again."
                                ),
                                pointer or "/",
                            )
                        )
                    else:
                        try:
                            raw = json_pointer(document, pointer)
                        except (KeyError, IndexError, TypeError, ValueError):
                            raw = None
                        if raw is not None:
                            raw_values = (
                                raw
                                if isinstance(raw, list)
                                else [raw]
                            )
                            if not raw_values:
                                diagnostics.append(
                                    JsonRegistrationDiagnostic(
                                        filename,
                                        "reference_invalid",
                                        "Reference array must contain at least one identifier.",
                                        "Correct the exact reference field and preview again.",
                                        pointer,
                                    )
                                )
                            for value in raw_values:
                                if not isinstance(value, str):
                                    diagnostics.append(
                                        JsonRegistrationDiagnostic(
                                            filename,
                                            "reference_invalid",
                                            "Record reference must be a string identifier.",
                                            "Correct the exact reference field and preview again.",
                                            pointer,
                                        )
                                    )
                                    continue
                                target = (
                                    resolved.get(pointer)
                                    if not isinstance(raw, list) and pointer in resolved
                                    else resolve_identifier(pointer, value, referenced_table_id)
                                )
                                if target is None:
                                    continue
                                links.append(
                                    (filename, pointer or "/", link_key, target[0], target[1])
                                )
            properties = node.get("properties")
            if isinstance(properties, Mapping):
                for name, child in properties.items():
                    if isinstance(name, str) and isinstance(child, Mapping):
                        visit(child, f"{pointer}/{escape(name)}")

        visit(format_value.schema, "")
        return tuple(links), tuple(diagnostics)

    def _current_reference(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        external_key: str,
    ) -> tuple[Any, ...]:
        repository = getattr(self._records, "_repository", None)
        # The legacy current/head resolver is intentionally ignored.  Exact JSON
        # registration may auto-resolve only through a resolver that explicitly
        # returns the complete immutable scoped history.  Production persistence includes
        # draft and reviewable revisions for authorized draft saves; Materials still filters
        # to its published projection.
        history_resolver = getattr(
            repository, "resolve_record_candidates_by_external_key", None
        )
        if history_resolver is None:
            # Keep direct in-process adapters that predate the broader candidate query usable;
            # production persistence provides the exact candidate method above.
            history_resolver = getattr(repository, "resolve_record_history_by_external_key", None)
        if history_resolver is not None:
            values = history_resolver(
                context=context,
                decision=decision,
                table_id=table_id,
                external_key=external_key,
            )
            return tuple(values or ())
        return ()

    def _is_published_exact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
    ) -> bool:
        """Check one exact Record revision against the durable published projection."""

        decision = self._read_decision(decision)
        revision = self._records.get_record_revision(
            context,
            decision,
            record_id,
            revision_id,
        )
        result = self._records.search_records(
            context=context,
            decision=decision,
            query=CatalogRecordQuery(
                table_id=revision.content.table_id,
                record_id=record_id,
                limit=1,
                published_only=True,
            ),
        )
        return any(
            item.id == record_id and item.current.record.revision_id == revision_id
            for item in result.items
        )

    @staticmethod
    def _schema_with_wrapper(format_value: InstalledJsonRecordFormat) -> dict[str, Any]:
        schema = dict(format_value.schema)
        schema["x-wrapper"] = format_value.wrapper
        # Strict wrapper is enforced by validate_json_record even when source-v2 omitted root
        # ``required``.  Keep the installed source bytes untouched.
        return schema

    @staticmethod
    def _preview_fields(
        document: Mapping[str, Any], format_value: InstalledJsonRecordFormat
    ) -> tuple[JsonRegistrationPreviewField, ...]:
        """Project the installed bindings into the small display model used by the UI."""

        def scalar_text(value: Any) -> str:
            if isinstance(value, str):
                return value
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )

        projected: list[JsonRegistrationPreviewField] = []
        for binding in format_value.attributes:
            try:
                value = json_pointer(document, binding.json_pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if value is None:
                continue
            definition = binding.attribute.current.content
            label = definition.name or definition.key
            section = binding.section or "Record"
            kind = definition.data_type.value
            if definition.data_type is AttributeDataType.CURVE:
                try:
                    points = len(
                        curve_source_rows(
                            document,
                            pointer=binding.json_pointer,
                            curve=binding.curve or {},
                        )
                    )
                except (KeyError, IndexError, TypeError, ValueError, JsonRegistrationError):
                    points = 0
                curve = binding.curve or {}
                x_unit = str(curve.get("x_unit") or "")
                y_unit = str(curve.get("y_unit") or "")
                channels = " · ".join(
                    part
                    for part in (
                        f"x {x_unit}" if x_unit else "x",
                        f"y {y_unit}" if y_unit else "y",
                    )
                )
                projected.append(
                    JsonRegistrationPreviewField(
                        section,
                        label,
                        binding.json_pointer,
                        kind,
                        summary=f"{points} points · {channels}",
                    )
                )
                continue
            unit: str | None = binding.source_unit
            display_value = value
            if isinstance(value, Mapping) and "value" in value:
                display_value = value.get("value")
                supplied_unit = value.get("unit") or value.get("original_unit_string")
                if isinstance(supplied_unit, str) and supplied_unit:
                    unit = supplied_unit
            projected.append(
                JsonRegistrationPreviewField(
                    section,
                    label,
                    binding.json_pointer,
                    kind,
                    value=scalar_text(display_value),
                    unit=unit,
                )
            )
        return tuple(projected)

    @staticmethod
    def _preview_record_name(
        document: Mapping[str, Any], format_value: InstalledJsonRecordFormat
    ) -> str | None:
        """Return the imported name from the installed name Attribute binding."""

        for binding in format_value.attributes:
            semantic_key = (
                binding.source_key
                if binding.source_key is not None
                else binding.attribute.current.content.key
            )
            if semantic_key not in {"record_name", "name"}:
                continue
            try:
                value = json_pointer(document, binding.json_pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def preview(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        format_revision_id: UUID | None = None,
        files: Sequence[JsonRegistrationFile],
        classification: DataClassification = DataClassification.INTERNAL,
        reference_pins: Mapping[tuple[str, str], Mapping[str, str]] | None = None,
        domain_bindings: Sequence[tuple[Any, ...]] = (),
        package_artifact_id: UUID | None = None,
        package_sha256: str | None = None,
    ) -> JsonRegistrationPreview:
        self._require(context, decision, Permission.CATALOG_WRITE)
        if not files:
            raise ValueError("JSON registration requires at least one file")
        format_value, resolution_diagnostics = self._resolve_preview_format(
            context,
            decision,
            format_revision_id=format_revision_id,
            files=files,
        )
        validated_domain_bindings = self._validate_domain_bindings(
            context, decision, classification, domain_bindings
        )
        package = build_registration_package(
            files,
            scope={
                "classification": classification.value,
                "organization_id": str(context.organization_id),
                "project_id": str(context.project_id),
            },
            format_pins=(
                {
                    "format_revision_id": str(format_value.format_revision_id),
                    "format": format_value.response(),
                }
                if format_value is not None
                else None
            ),
        )
        pins = reference_pins or {}
        results: list[JsonRegistrationFileResult] = []
        documents: list[Mapping[str, Any]] = []
        keys: set[str] = set()
        parsed: list[
            tuple[
                JsonRegistrationFile,
                Mapping[str, Any],
                tuple[JsonRegistrationDiagnostic, ...],
                list[JsonRegistrationDiagnostic],
                str | None,
            ]
        ] = []
        for file in files:
            warnings: tuple[JsonRegistrationDiagnostic, ...] = ()
            errors: list[JsonRegistrationDiagnostic] = list(
                resolution_diagnostics.get(file.filename, ())
            )
            try:
                document = parse_strict_json(file.content, filename=file.filename)
                if format_value is not None and not errors:
                    document, warnings, validation_errors = validate_json_record(
                        file.content,
                        self._schema_with_wrapper(format_value),
                        filename=file.filename,
                    )
                    errors.extend(validation_errors)
            except JsonRegistrationError as error:
                if not any(item.code == error.code for item in errors):
                    errors.append(self._diagnostic(file, error))
                document = {}
            external_key: str | None = None
            if format_value is not None and not errors and isinstance(document, Mapping):
                for binding in format_value.attributes:
                    if binding.attribute.current.content.business_key:
                        try:
                            candidate = json_pointer(document, binding.json_pointer)
                        except (KeyError, IndexError, TypeError, ValueError):
                            candidate = None
                        if isinstance(candidate, str):
                            external_key = candidate.strip()
                        break
                if external_key is not None:
                    folded = external_key.casefold()
                    if folded in keys:
                        errors.append(
                            JsonRegistrationDiagnostic(
                                file.filename,
                                "duplicate_identity_batch",
                                "The business key is duplicated within this registration batch.",
                                "Give every JSON file a distinct business key and preview again.",
                                "/",
                            )
                        )
                    keys.add(folded)
            parsed.append((file, document, warnings, errors, external_key))
        for file, document, warnings, errors, external_key in parsed:
            if format_value is not None and not errors and isinstance(document, Mapping):
                resolved, reference_errors = self._reference_pins(
                    context,
                    decision,
                    document,
                    format_value,
                    filename=file.filename,
                    pins=pins,
                    batch_keys=keys,
                )
                errors.extend(reference_errors)
                _, link_errors = self._reference_links(
                    context,
                    decision,
                    document,
                    format_value,
                    filename=file.filename,
                    pins=pins,
                    batch_keys=keys,
                    resolved=resolved,
                )
                errors.extend(link_errors)
            documents.append(document if isinstance(document, Mapping) else {})
            fields = (
                self._preview_fields(document, format_value)
                if format_value is not None and isinstance(document, Mapping)
                else ()
            )
            record_name = (
                self._preview_record_name(document, format_value)
                if format_value is not None and not errors and isinstance(document, Mapping)
                else None
            )
            results.append(
                JsonRegistrationFileResult(
                    file.filename,
                    file.sha256,
                    file.size_bytes,
                    not errors,
                    warnings,
                    tuple(errors),
                    external_key,
                    fields=fields,
                    record_name=record_name,
                )
            )
        now = self._clock()
        token = str(self._id())
        raw_source = (
            package_artifact_id is None
            and len(files) == 1
            and files[0].artifact_id is not None
        )
        authoritative_package_sha256 = (
            package_sha256
            if package_artifact_id is not None and package_sha256
            else files[0].artifact_sha256 or files[0].sha256
            if raw_source
            else package.sha256
        )
        preview = JsonRegistrationPreview(
            token,
            (now + JSON_REGISTRATION_TTL).isoformat().replace("+00:00", "Z"),
            authoritative_package_sha256,
            JSON_MEDIA_TYPE if raw_source else JSON_PACKAGE_MEDIA_TYPE,
            tuple(results),
            all(item.valid for item in results),
            str(format_value.format_revision_id) if format_value is not None else None,
            str(package_artifact_id) if package_artifact_id is not None else None,
            format_value.table_key if format_value is not None else None,
            format_value.response() if format_value is not None else None,
        )
        self._tokens[token] = JsonRegistrationToken(
            token,
            format_value.format_revision_id if format_value is not None else UUID(int=0),
            context.principal.id,
            authoritative_package_sha256,
            package_artifact_id,
            classification,
            tuple(files),
            tuple(documents),
            tuple(results),
            now,
            now + JSON_REGISTRATION_TTL,
            domain_bindings=validated_domain_bindings,
            reference_pins=dict(pins),
        )
        if self._persistence is not None and format_value is not None:
            self._persistence.save_preview(
                context=context,
                decision=decision,
                token=self._tokens[token],
                format_value=format_value,
            )
        return preview

    async def preview_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        format_revision_id: UUID | None = None,
        files: Sequence[JsonRegistrationFile],
        classification: DataClassification = DataClassification.INTERNAL,
        reference_pins: Mapping[tuple[str, str], Mapping[str, str]] | None = None,
        domain_bindings: Sequence[tuple[Any, ...]] = (),
        package_artifact_id: UUID | None = None,
        package_sha256: str | None = None,
    ) -> JsonRegistrationPreview:
        """Preview after resolving the installed format from durable source-v2 state."""

        if format_revision_id is not None:
            await self._format_async(context, decision, format_revision_id)
        elif self._async_format_resolver is not None:
            # The resolver is authoritative for installed exact formats.  Cache only the
            # returned immutable revisions so the synchronous preview path can share the
            # same root-wrapper candidate selection.
            values = await self._async_format_resolver.list_formats(context, decision)
            self._formats.update({item.format_revision_id: item for item in values})
        return self.preview(
            context,
            decision,
            format_revision_id=format_revision_id,
            files=files,
            classification=classification,
            reference_pins=reference_pins,
            domain_bindings=domain_bindings,
            package_artifact_id=package_artifact_id,
            package_sha256=package_sha256,
        )

    @staticmethod
    def _stored_diagnostic(value: Mapping[str, Any], filename: str) -> JsonRegistrationDiagnostic:
        return JsonRegistrationDiagnostic(
            filename=str(value.get("filename") or filename),
            code=str(value.get("code") or "preview_diagnostic"),
            message=str(value.get("message") or "Stored preview diagnostic"),
            recovery=str(value.get("recovery") or "Correct the source file and preview again."),
            pointer=(
                str(value["json_pointer"])
                if value.get("json_pointer") is not None
                else None
            ),
            line=(int(value["line"]) if value.get("line") is not None else None),
            column=(int(value["column"]) if value.get("column") is not None else None),
            byte_offset=(
                int(value["byte_offset"]) if value.get("byte_offset") is not None else None
            ),
            severity=str(value.get("severity") or "error"),
        )

    async def _restore_preview_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        token: str,
        row: Mapping[str, Any],
    ) -> JsonRegistrationToken:
        """Hydrate an open durable preview after an API worker restart."""

        try:
            format_revision_id = UUID(str(row["format_revision_id"]))
            package_sha256 = str(row["package_sha256"])
            classification = DataClassification(str(row["classification"]))
            created_at = row["created_at"]
            expires_at = row["expires_at"]
        except (KeyError, TypeError, ValueError) as error:
            raise ConfigurableCatalogConflict(
                "durable JSON registration preview is invalid"
            ) from error
        if not isinstance(created_at, datetime) or not isinstance(expires_at, datetime):
            raise ConfigurableCatalogConflict(
                "durable JSON registration preview timestamps are invalid"
            )
        if self._artifacts is None:
            raise ConfigurableCatalogConflict("immutable Artifact reader is unavailable")

        package_artifact_id: UUID | None = None
        raw_package_id = row.get("package_artifact_id")
        if raw_package_id is not None:
            try:
                package_artifact_id = UUID(str(raw_package_id))
            except (TypeError, ValueError) as error:
                raise ConfigurableCatalogConflict(
                    "durable JSON package Artifact identity is invalid"
                ) from error
        if package_artifact_id is not None:
            artifact_record, raw = await self._artifacts.read_verified_bytes(
                context,
                decision,
                package_artifact_id,
                maximum_bytes=MAX_PACKAGE_ARCHIVE_BYTES,
            )
            if (
                artifact_record.artifact.media_type != JSON_PACKAGE_MEDIA_TYPE
                or artifact_record.artifact.sha256 != package_sha256
                or hashlib.sha256(raw).hexdigest() != package_sha256
            ):
                raise ConfigurableCatalogConflict(
                    "durable JSON package Artifact integrity evidence is inconsistent"
                )
            files = verify_registration_package(
                raw,
                expected_classification=classification.value,
            )
        else:
            components = row.get("components")
            if not isinstance(components, list) or len(components) != 1:
                raise ConfigurableCatalogConflict("durable raw JSON preview has invalid components")
            component = components[0]
            if not isinstance(component, Mapping):
                raise ConfigurableCatalogConflict("durable JSON preview component is invalid")
            try:
                artifact_id = UUID(str(component["artifact_id"]))
                filename = str(component["filename"])
                expected_sha256 = str(component["sha256"])
                expected_size = int(component["size_bytes"])
            except (KeyError, TypeError, ValueError) as error:
                raise ConfigurableCatalogConflict(
                    "durable raw JSON component identity is invalid"
                ) from error
            artifact_record, raw = await self._artifacts.read_verified_bytes(
                context,
                decision,
                artifact_id,
                maximum_bytes=MAX_PACKAGE_ARCHIVE_BYTES,
            )
            if (
                artifact_record.artifact.media_type != JSON_MEDIA_TYPE
                or artifact_record.artifact.sha256 != expected_sha256
                or artifact_record.artifact.size_bytes != expected_size
                or hashlib.sha256(raw).hexdigest() != expected_sha256
                or len(raw) != expected_size
            ):
                raise ConfigurableCatalogConflict(
                    "durable raw JSON Artifact integrity evidence is inconsistent"
                )
            files = (
                JsonRegistrationFile(
                    filename,
                    raw,
                    JSON_MEDIA_TYPE,
                    str(artifact_id),
                    expected_sha256,
                ),
            )

        stored_components = row.get("components")
        if not isinstance(stored_components, list) or len(stored_components) != len(files):
            raise ConfigurableCatalogConflict(
                "durable preview component count differs from source package"
            )
        for stored, file in zip(stored_components, files, strict=True):
            if not isinstance(stored, Mapping):
                raise ConfigurableCatalogConflict("durable preview component is invalid")
            if (
                stored.get("filename") != file.filename
                or stored.get("sha256") != file.sha256
                or int(stored.get("size_bytes", -1)) != file.size_bytes
                or stored.get("package_path") != file.package_path
            ):
                raise ConfigurableCatalogConflict("durable preview component evidence changed")

        raw_results = row.get("results")
        if not isinstance(raw_results, list) or len(raw_results) != len(files):
            raise ConfigurableCatalogConflict(
                "durable preview result count differs from source package"
            )
        results: list[JsonRegistrationFileResult] = []
        documents: list[Mapping[str, Any]] = []
        for file, raw_result in zip(files, raw_results, strict=True):
            if not isinstance(raw_result, Mapping):
                raise ConfigurableCatalogConflict("durable preview result is invalid")
            try:
                document = parse_strict_json(file.content, filename=file.filename)
            except JsonRegistrationError as error:
                raise ConfigurableCatalogConflict(
                    "durable preview source is no longer strict JSON"
                ) from error
            if not isinstance(document, Mapping):
                raise ConfigurableCatalogConflict("durable preview source is not a JSON object")
            documents.append(document)
            warnings = tuple(
                self._stored_diagnostic(item, file.filename)
                for item in raw_result.get("warnings", ())
                if isinstance(item, Mapping)
            )
            errors = tuple(
                self._stored_diagnostic(item, file.filename)
                for item in raw_result.get("errors", ())
                if isinstance(item, Mapping)
            )
            fields = tuple(
                JsonRegistrationPreviewField(
                    str(item.get("section") or "Record"),
                    str(item.get("label") or "Field"),
                    str(item.get("pointer") or "/"),
                    str(item.get("kind") or "text"),
                    str(item["value"]) if item.get("value") is not None else None,
                    str(item["unit"]) if item.get("unit") is not None else None,
                    str(item["summary"]) if item.get("summary") is not None else None,
                )
                for item in raw_result.get("fields", ())
                if isinstance(item, Mapping)
            )
            results.append(
                JsonRegistrationFileResult(
                    file.filename,
                    file.sha256,
                    file.size_bytes,
                    bool(raw_result.get("valid")) and not errors,
                    warnings,
                    errors,
                    (
                        str(raw_result["external_key"])
                        if raw_result.get("external_key") is not None
                        else None
                    ),
                    (
                        str(raw_result["record_id"])
                        if raw_result.get("record_id") is not None
                        else None
                    ),
                    (
                        str(raw_result["record_revision_id"])
                        if raw_result.get("record_revision_id") is not None
                        else None
                    ),
                    (
                        str(raw_result["lifecycle"])
                        if raw_result.get("lifecycle") is not None
                        else None
                    ),
                    fields,
                    (
                        str(raw_result["record_name"])
                        if raw_result.get("record_name") is not None
                        else None
                    ),
                )
            )

        stored_bindings = row.get("domain_bindings") or ()
        domain_bindings: list[tuple[Any, ...]] = []
        for binding in stored_bindings:
            if not isinstance(binding, Mapping):
                raise ConfigurableCatalogConflict("durable domain binding pin is invalid")
            try:
                kind = str(binding["kind"])
                object_id = UUID(str(binding["object_id"]))
                revision_id = UUID(str(binding["revision_id"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ConfigurableCatalogConflict(
                    "durable domain binding pin is invalid"
                ) from error
            if binding.get("file") is not None or binding.get("component") is not None:
                if not isinstance(binding.get("file"), str) or not isinstance(
                    binding.get("component"), str
                ):
                    raise ConfigurableCatalogConflict("durable domain binding scope is invalid")
                domain_bindings.append(
                    (binding["file"], binding["component"], kind, object_id, revision_id)
                )
            else:
                domain_bindings.append((kind, object_id, revision_id))

        reference_pins: dict[tuple[str, str], Mapping[str, str]] = {}
        for pin in row.get("reference_pins") or ():
            if not isinstance(pin, Mapping):
                raise ConfigurableCatalogConflict("durable reference pin is invalid")
            try:
                file_name = str(pin["file"])
                selector = str(pin["selector"])
                reference_pins[(file_name, selector)] = {
                    key: str(value)
                    for key, value in pin.items()
                    if key not in {"file", "selector"}
                }
            except (KeyError, TypeError, ValueError) as error:
                raise ConfigurableCatalogConflict("durable reference pin is invalid") from error

        return JsonRegistrationToken(
            token,
            format_revision_id,
            context.principal.id,
            package_sha256,
            package_artifact_id,
            classification,
            tuple(files),
            tuple(documents),
            tuple(results),
            created_at,
            expires_at,
            batch_id=(
                UUID(str(row["batch_id"]))
                if row.get("batch_id") is not None
                else None
            ),
            domain_bindings=tuple(domain_bindings),
            reference_pins=reference_pins,
        )

    async def _restore_committed_result_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        token: str,
        package_sha256: str,
    ) -> JsonRegistrationSaveResult | None:
        loader = getattr(self._persistence, "load_committed_batch", None)
        if loader is None:
            return None
        row = loader(context=context, decision=decision, token=token)
        if row is None:
            return None
        if str(row.get("package_sha256")) != package_sha256:
            raise ConfigurableCatalogConflict(JsonRegistrationErrorCode.PACKAGE_MISMATCH.value)
        batch_id = row.get("batch_id")
        pairs = row.get("records")
        if not isinstance(batch_id, UUID) or not isinstance(pairs, Sequence):
            raise ConfigurableCatalogConflict("durable committed JSON batch is invalid")
        read_decision = self._read_decision(decision)
        records: list[RecordSnapshot] = []
        for pair in pairs:
            if not isinstance(pair, Sequence) or len(pair) != 2:
                raise ConfigurableCatalogConflict("durable committed JSON Record pin is invalid")
            try:
                record_id = UUID(str(pair[0]))
                revision_id = UUID(str(pair[1]))
            except (TypeError, ValueError) as error:
                raise ConfigurableCatalogConflict(
                    "durable committed JSON Record pin is invalid"
                ) from error
            revision = self._records.get_record_revision(
                context,
                read_decision,
                record_id,
                revision_id,
            )
            records.append(RecordSnapshot(record_id, revision.content.table_id, revision))
        return JsonRegistrationSaveResult(batch_id, True, tuple(records), package_sha256)

    def _value(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding: JsonAttributeBinding,
        value: Any,
        document: Mapping[str, Any],
        *,
        references: Mapping[str, tuple[UUID, UUID]],
        curve_artifacts: Mapping[tuple[str, str], tuple[UUID, str]],
        filename: str,
    ) -> CatalogRecordValue | None:
        attribute = binding.attribute
        definition = attribute.current.content
        if value is None:
            return None
        revision_id = attribute.current.record.revision_id
        if definition.data_type is AttributeDataType.RECORD_REFERENCE:
            target = references.get(binding.json_pointer)
            if target is None:
                raise ConfigurableCatalogConflict("reference revision pin is required before save")
            return CatalogRecordValue(
                attribute.id,
                revision_id,
                definition.data_type,
                target_record_id=target[0],
                target_record_revision_id=target[1],
            )
        if definition.data_type is AttributeDataType.CURVE:
            artifact = curve_artifacts.get((filename, binding.json_pointer))
            if artifact is None:
                raise ConfigurableCatalogConflict(
                    "curve save requires a verified derived Artifact"
                )
            return CatalogRecordValue(
                attribute.id,
                revision_id,
                definition.data_type,
                artifact_id=artifact[0],
                artifact_sha256=artifact[1],
            )
        if definition.data_type is AttributeDataType.NUMBER:
            # A numeric source value remains immutable pointer/unit evidence until the
            # installed exact Attribute supplies both sides of its unit contract.  Do not
            # infer quantity semantics from a source unit or schema label.
            if definition.normalized_unit is None or definition.quantity_semantics is None:
                return None
            declared_unit = binding.source_unit
            source_unit = declared_unit
            if isinstance(value, Mapping):
                supplied_unit = str(
                    value.get("unit") or value.get("original_unit_string") or source_unit or ""
                )
                if declared_unit is not None and supplied_unit != declared_unit:
                    raise ConfigurableCatalogConflict(
                        "numeric JSON unit differs from the exact installed binding"
                    )
                source_unit = supplied_unit
                value = value.get("value", value.get("original_value"))
            if not source_unit:
                raise ConfigurableCatalogConflict(
                    "declared original unit is required for numeric JSON values"
                )
            return self._records._registration_value(
                context,
                decision,
                attribute.id,
                definition,
                revision_id,
                {"value": value, "unit": source_unit},
            )
        if definition.data_type is AttributeDataType.INTEGER:
            if isinstance(value, bool):
                raise ValueError("integer JSON value cannot be boolean")
            return CatalogRecordValue(
                attribute.id, revision_id, definition.data_type, value=int(value)
            )
        if definition.data_type is AttributeDataType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError("boolean JSON value must be a JSON boolean")
            return CatalogRecordValue(attribute.id, revision_id, definition.data_type, value=value)
        if definition.data_type is AttributeDataType.DATE:
            return CatalogRecordValue(
                attribute.id,
                revision_id,
                definition.data_type,
                value=datetime.fromisoformat(str(value)).date()
                if "T" in str(value)
                else datetime.strptime(str(value), "%Y-%m-%d").date(),
            )
        if definition.data_type in {AttributeDataType.TEXT, AttributeDataType.DISCRETE}:
            if not isinstance(value, str):
                raise ValueError("text JSON value must be a string")
            return CatalogRecordValue(attribute.id, revision_id, definition.data_type, value=value)
        return CatalogRecordValue(attribute.id, revision_id, definition.data_type, value=str(value))

    def _content(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        format_value: InstalledJsonRecordFormat,
        document: Mapping[str, Any],
        result: JsonRegistrationFileResult,
        *,
        references: Mapping[str, tuple[UUID, UUID]],
        curve_artifacts: Mapping[tuple[str, str], tuple[UUID, str]],
    ) -> CatalogRecordContent:
        values: list[CatalogRecordValue] = []
        name = result.record_name or result.external_key or format_value.table_key
        for binding in format_value.attributes:
            try:
                value = json_pointer(document, binding.json_pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                value = None
            if value is None:
                continue
            candidate = self._value(
                context,
                decision,
                binding,
                value,
                document,
                references=references,
                curve_artifacts=curve_artifacts,
                filename=result.filename,
            )
            if candidate is not None:
                values.append(candidate)
            semantic_key = (
                binding.source_key
                if binding.source_key is not None
                else binding.attribute.current.content.key
            )
            if semantic_key in {"record_name", "name"} and isinstance(value, str):
                name = value.strip() or name
        content = CatalogRecordContent(
            format_value.table_id,
            format_value.table_revision_id,
            name,
            result.external_key,
            None,
            None,
            None,
            tuple(values),
        )
        return self._records._promote_business_key(context, decision, content)

    async def _prepare_curve_artifacts(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        *,
        batch_id: UUID,
    ) -> dict[tuple[str, str], tuple[UUID, str]]:
        """Materialize validated curve arrays through the immutable Artifact lifecycle."""

        persist_curve = getattr(
            self._persistence,
            "persist_curve_artifact_in_transaction",
            None,
        )
        if persist_curve is None:
            raise ConfigurableCatalogConflict(
                "curve Artifact provenance persistence is not configured"
            )
        ordered_files = tuple(
            sorted(
                pending.files,
                key=lambda item: (item.filename.encode("utf-8"), item.sha256),
            )
        )
        ordinals = {
            (file.filename, file.sha256): ordinal
            for ordinal, file in enumerate(ordered_files, start=1)
        }
        prepared: dict[tuple[str, str], tuple[UUID, str]] = {}
        for file, document in zip(pending.files, pending.documents, strict=True):
            for binding in format_value.attributes:
                if binding.attribute.current.content.data_type is not AttributeDataType.CURVE:
                    continue
                try:
                    value = json_pointer(document, binding.json_pointer)
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if value is None:
                    continue
                if self._artifacts is None or not hasattr(
                    self._artifacts, "finalize_derived_bytes"
                ):
                    raise ConfigurableCatalogConflict(
                        "curve Artifact finalization is not configured"
                    )
                curve_bytes = _curve_artifact_bytes(document, binding)
                command_digest = hashlib.sha256(
                    f"{batch_id}:{pending.package_sha256}:{file.filename}:"
                    f"{binding.json_pointer}".encode()
                ).hexdigest()

                def persist_curve_artifact(
                    session: Any,
                    finalized: Any,
                    *,
                    file: JsonRegistrationFile = file,
                    binding: JsonAttributeBinding = binding,
                ) -> None:
                    persist_curve(
                        session=session,
                        context=context,
                        decision=decision,
                        token=pending,
                        batch_id=batch_id,
                        component_ordinal=ordinals[(file.filename, file.sha256)],
                        filename=file.filename,
                        json_pointer=binding.json_pointer,
                        artifact_id=finalized.record.artifact.id,
                        artifact_sha256=finalized.record.artifact.sha256,
                        artifact_size_bytes=finalized.record.artifact.size_bytes,
                    )

                artifact = await self._artifacts.finalize_derived_bytes(
                    context,
                    decision,
                    classification=pending.classification,
                    artifact_role="catalog.json-record.curve",
                    schema_ref=NORMALIZED_PARQUET_SCHEMA,
                    media_type=JSON_CURVE_MEDIA_TYPE,
                    value=curve_bytes,
                    idempotency_key=f"json-record-curve-{command_digest}",
                    commit_hook=persist_curve_artifact,
                )
                prepared[(file.filename, binding.json_pointer)] = (
                    artifact.artifact.id,
                    artifact.artifact.sha256,
                )
        return prepared

    async def save_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        token: str,
        format_revision_id: UUID | None = None,
        package_sha256: str,
        change_reason: str,
        reference_pins: Mapping[tuple[str, str], Mapping[str, str]] | None = None,
        domain_bindings: Sequence[tuple[Any, ...]] | None = None,
    ) -> JsonRegistrationSaveResult:
        """Save a draft after durable pending association of any source curve Artifacts."""

        pending = self._tokens.get(token)
        if pending is None and self._persistence is not None:
            loader = getattr(self._persistence, "load_preview", None)
            if loader is not None:
                durable = loader(context=context, decision=decision, token=token)
                if durable is not None:
                    durable_format = durable.get("format_revision_id")
                    if (
                        format_revision_id is not None
                        and str(durable_format) != str(format_revision_id)
                    ):
                        raise ConfigurableCatalogConflict(
                            JsonRegistrationErrorCode.FORMAT_STALE.value
                        )
                    if str(durable.get("state")) == "committed":
                        replay = await self._restore_committed_result_async(
                            context,
                            decision,
                            token=token,
                            package_sha256=package_sha256,
                        )
                        if replay is None:
                            raise ConfigurableCatalogConflict(
                                "durable committed JSON batch is unavailable"
                            )
                        return replay
                    if str(durable.get("state")) != "open":
                        raise ConfigurableCatalogConflict("durable JSON preview token is not open")
                    pending = await self._restore_preview_async(
                        context,
                        decision,
                        token=token,
                        row=durable,
                    )
                    self._tokens[token] = pending
        if pending is not None and pending.state == "committed":
            return self.save(
                context,
                decision,
                token=token,
                format_revision_id=format_revision_id,
                package_sha256=package_sha256,
                change_reason=change_reason,
                reference_pins=reference_pins,
                domain_bindings=domain_bindings,
            )
        if pending is None:
            return self.save(
                context,
                decision,
                token=token,
                format_revision_id=format_revision_id,
                package_sha256=package_sha256,
                change_reason=change_reason,
                reference_pins=reference_pins,
                domain_bindings=domain_bindings,
            )
        format_value = await self._format_async(
            context,
            decision,
            pending.format_revision_id,
        )
        curve_bindings = []
        for file, document in zip(pending.files, pending.documents, strict=True):
            for binding in format_value.attributes:
                if binding.attribute.current.content.data_type is not AttributeDataType.CURVE:
                    continue
                try:
                    value = json_pointer(document, binding.json_pointer)
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if value is not None:
                    curve_bindings.append((file.filename, binding.json_pointer))
        batch_id: UUID | None = pending.batch_id
        if curve_bindings:
            ensure_pending_batch = getattr(self._persistence, "ensure_pending_batch", None)
            if ensure_pending_batch is None:
                raise ConfigurableCatalogConflict(
                    "curve Artifact batch persistence is not configured"
                )
            batch_id = ensure_pending_batch(
                context=context,
                decision=decision,
                token=pending,
                format_value=format_value,
                batch_id=batch_id or self._id(),
            )
            if pending.batch_id != batch_id:
                pending = replace(pending, batch_id=batch_id)
                self._tokens[token] = pending
        curve_artifacts = await self._prepare_curve_artifacts(
            context,
            decision,
            pending,
            format_value,
            batch_id=batch_id or self._id(),
        ) if curve_bindings else {}
        return self.save(
            context,
            decision,
            token=token,
            format_revision_id=format_revision_id,
            package_sha256=package_sha256,
            change_reason=change_reason,
            reference_pins=reference_pins,
            domain_bindings=domain_bindings,
            curve_artifacts=curve_artifacts,
        )

    def save(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        token: str,
        format_revision_id: UUID | None = None,
        package_sha256: str,
        change_reason: str,
        reference_pins: Mapping[tuple[str, str], Mapping[str, str]] | None = None,
        domain_bindings: Sequence[tuple[Any, ...]] | None = None,
        curve_artifacts: Mapping[tuple[str, str], tuple[UUID, str]] | None = None,
    ) -> JsonRegistrationSaveResult:
        self._require(context, decision, Permission.CATALOG_WRITE)
        pending = self._tokens.get(token)
        if pending is None:
            raise ConfigurableCatalogConflict("registration preview token is stale")
        now = self._clock()
        if pending.caller_id != context.principal.id:
            raise ConfigurableCatalogConflict(JsonRegistrationErrorCode.CALLER_MISMATCH.value)
        if (
            format_revision_id is not None
            and pending.format_revision_id != format_revision_id
        ):
            raise ConfigurableCatalogConflict(JsonRegistrationErrorCode.FORMAT_STALE.value)
        if pending.package_sha256 != package_sha256:
            raise ConfigurableCatalogConflict(JsonRegistrationErrorCode.PACKAGE_MISMATCH.value)
        if pending.state == "committed" and pending.batch_id is not None:
            return JsonRegistrationSaveResult(
                pending.batch_id,
                True,
                pending.committed_records,
                pending.package_sha256,
            )
        if now >= pending.expires_at:
            raise ConfigurableCatalogConflict(JsonRegistrationErrorCode.TOKEN_EXPIRED.value)
        if not all(item.valid for item in pending.results):
            raise ValueError("all JSON files must be valid before draft save")
        requested_domain_bindings = (
            pending.domain_bindings
            if domain_bindings is None
            else tuple(domain_bindings)
        )
        if domain_bindings is not None and tuple(domain_bindings) != pending.domain_bindings:
            raise ConfigurableCatalogConflict("domain binding pins do not match the preview")
        validated_domain_bindings = self._validate_domain_bindings(
            context, decision, pending.classification, requested_domain_bindings
        )
        format_value = self._format(context, decision, pending.format_revision_id)
        pins = pending.reference_pins if reference_pins is None else reference_pins
        if reference_pins is not None and dict(reference_pins) != dict(pending.reference_pins):
            raise ConfigurableCatalogConflict("reference pins do not match the preview")
        resolved_curve_artifacts = curve_artifacts or {}
        contents: list[CatalogRecordContent] = []
        resolved_links: list[tuple[str, str, str, str, UUID, UUID]] = []
        batch_keys = {
            item.external_key.casefold()
            for item in pending.results
            if item.external_key is not None
        }
        for file, document, result in zip(
            pending.files, pending.documents, pending.results, strict=True
        ):
            references, diagnostics = self._reference_pins(
                context,
                decision,
                document,
                format_value,
                filename=file.filename,
                pins=pins,
                batch_keys=batch_keys,
            )
            if diagnostics:
                diagnostic = diagnostics[0]
                location = diagnostic.pointer or "/"
                raise ConfigurableCatalogConflict(
                    f"{diagnostic.filename}{location}: {diagnostic.message}"
                )
            links, link_diagnostics = self._reference_links(
                context,
                decision,
                document,
                format_value,
                filename=file.filename,
                pins=pins,
                batch_keys=batch_keys,
                resolved=references,
            )
            if link_diagnostics:
                diagnostic = link_diagnostics[0]
                location = diagnostic.pointer or "/"
                raise ConfigurableCatalogConflict(
                    f"{diagnostic.filename}{location}: {diagnostic.message}"
                )
            resolved_links.extend(
                (file.filename, file.sha256, pointer, link_key, target_id, target_revision_id)
                for _, pointer, link_key, target_id, target_revision_id in links
            )
            content = self._content(
                context,
                decision,
                format_value,
                document,
                result,
                references=references,
                curve_artifacts=resolved_curve_artifacts,
            )
            self._records._validate_record(context, decision, content)
            contents.append(content)
        batch_id = pending.batch_id or self._id()

        def bindings_for_file(file: JsonRegistrationFile) -> tuple[tuple[str, UUID, UUID], ...]:
            selected: list[tuple[str, UUID, UUID]] = []
            for binding in validated_domain_bindings:
                if len(binding) == 3:
                    kind, object_id, revision_id = binding
                else:
                    file_name, component, kind, object_id, revision_id = binding
                    expected_component = file.package_path or file.filename
                    if file_name != file.filename or component != expected_component:
                        continue
                selected.append((kind, object_id, revision_id))
            return tuple(selected)

        commands = tuple(
            (
                self._id(),
                CreateRecord(
                    pending.classification,
                    content,
                    change_reason,
                    bindings_for_file(file),
                ),
            )
            for file, content in zip(pending.files, contents, strict=True)
        )
        repository = self._records._repository
        persist_in_transaction = getattr(self._persistence, "persist_batch_in_transaction", None)

        def after_create(transaction: Any, created: Sequence[Any]) -> None:
            if persist_in_transaction is None:
                return
            persist_in_transaction(
                session=transaction,
                context=context,
                decision=decision,
                token=pending,
                format_value=format_value,
                batch_id=batch_id,
                records=created,
                resolved_links=resolved_links,
            )

        create_kwargs: dict[str, Any] = {
            "context": context,
            "decision": decision,
            "records": commands,
            "registration_token": None,
        }
        if persist_in_transaction is not None:
            create_kwargs["after_create"] = after_create
        records = repository.create_records_atomically(**create_kwargs)
        for file, document, record in zip(pending.files, pending.documents, records, strict=True):
            self._provenance[(record.id, record.current.record.revision_id)] = (
                file,
                document,
                format_value,
            )
        if self._persistence is not None and persist_in_transaction is None:
            self._persistence.save_batch(
                context=context,
                decision=decision,
                token=pending,
                format_value=format_value,
                batch_id=batch_id,
            )
            self._persistence.save_provenance(
                context=context,
                decision=decision,
                token=pending,
                format_value=format_value,
                batch_id=batch_id,
                records=records,
            )
            if not self._persistence.commit_preview(
                context=context,
                decision=decision,
                token=token,
                batch_id=batch_id,
            ):
                raise ConfigurableCatalogConflict("JSON registration token could not be committed")
        self._tokens[token] = JsonRegistrationToken(
            pending.token,
            pending.format_revision_id,
            pending.caller_id,
            pending.package_sha256,
            pending.package_artifact_id,
            pending.classification,
            pending.files,
            pending.documents,
            pending.results,
            pending.created_at,
            pending.expires_at,
            "committed",
            batch_id,
            tuple(records),
            pending.domain_bindings,
            pending.reference_pins,
        )
        return JsonRegistrationSaveResult(batch_id, False, tuple(records), pending.package_sha256)

    def source_download(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        record_id: UUID,
        revision_id: UUID,
        published_only: bool = False,
    ) -> tuple[str, str, bytes]:
        self._require(context, decision, Permission.CATALOG_READ)
        if published_only and not self._is_published_exact(
            context, decision, record_id, revision_id
        ):
            raise ConfigurableCatalogConflict(
                "exact JSON source is available only for a published Record revision"
            )
        value = self._provenance.get((record_id, revision_id))
        if value is None:
            raise ConfigurableCatalogConflict("exact JSON source provenance is unavailable")
        file, _, _ = value
        return file.filename, JSON_MEDIA_TYPE, file.content

    async def _read_durable_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        record_id: UUID,
        revision_id: UUID,
    ) -> tuple[Mapping[str, Any], bytes]:
        lookup = getattr(self._persistence, "get_provenance", None)
        if lookup is None or self._artifacts is None:
            raise ConfigurableCatalogConflict("exact JSON source provenance is unavailable")
        provenance = lookup(
            context=context,
            decision=decision,
            record_id=record_id,
            revision_id=revision_id,
        )
        if provenance is None:
            raise ConfigurableCatalogConflict("exact JSON source provenance is unavailable")
        component_path = provenance.get("package_component_path")
        package_artifact_id = provenance.get("package_artifact_id")
        if component_path is not None:
            if not isinstance(component_path, str) or not component_path:
                raise ConfigurableCatalogConflict("package component path is invalid")
            try:
                package_id = (
                    package_artifact_id
                    if isinstance(package_artifact_id, UUID)
                    else UUID(str(package_artifact_id))
                )
            except (TypeError, ValueError) as error:
                raise ConfigurableCatalogConflict("package Artifact identity is invalid") from error
            package_artifact_record, package_raw = await self._artifacts.read_verified_bytes(
                context,
                decision,
                package_id,
                maximum_bytes=MAX_PACKAGE_ARCHIVE_BYTES,
            )
            package_artifact = package_artifact_record.artifact
            if (
                package_artifact.media_type != JSON_PACKAGE_MEDIA_TYPE
                or package_artifact.sha256 != provenance.get("package_sha256")
                or package_artifact.size_bytes != len(package_raw)
                or hashlib.sha256(package_raw).hexdigest() != provenance.get("package_sha256")
            ):
                raise ConfigurableCatalogConflict(
                    "package Artifact integrity evidence is inconsistent"
                )
            components = verify_registration_package(
                package_raw, expected_classification=str(provenance.get("classification"))
            )
            matches = [
                item
                for item in components
                if item.package_path == component_path
                and item.filename == provenance.get("original_filename")
                and item.sha256 == provenance.get("source_sha256")
                and item.size_bytes == provenance.get("source_length_bytes")
            ]
            if len(matches) != 1:
                raise ConfigurableCatalogConflict(
                    "package component path or digest does not match exact provenance"
                )
            return provenance, matches[0].content

        artifact_id = provenance.get("source_artifact_id")
        if not isinstance(artifact_id, UUID):
            try:
                artifact_id = UUID(str(artifact_id))
            except (TypeError, ValueError) as error:
                raise ConfigurableCatalogConflict("source Artifact identity is invalid") from error
        artifact_record, raw = await self._artifacts.read_verified_bytes(
            context,
            decision,
            artifact_id,
            maximum_bytes=MAX_PACKAGE_ARCHIVE_BYTES,
        )
        artifact = artifact_record.artifact
        if (
            artifact.media_type != JSON_MEDIA_TYPE
            or artifact.size_bytes != len(raw)
            or artifact.sha256 != provenance.get("source_sha256")
            or len(raw) != provenance.get("source_length_bytes")
            or hashlib.sha256(raw).hexdigest() != provenance.get("source_sha256")
        ):
            raise ConfigurableCatalogConflict("source Artifact integrity evidence is inconsistent")
        return provenance, raw

    async def source_download_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        record_id: UUID,
        revision_id: UUID,
        published_only: bool = False,
    ) -> tuple[str, str, bytes]:
        self._require(context, decision, Permission.CATALOG_READ)
        if published_only and not self._is_published_exact(
            context, decision, record_id, revision_id
        ):
            raise ConfigurableCatalogConflict(
                "exact JSON source is available only for a published Record revision"
            )
        value = self._provenance.get((record_id, revision_id))
        if value is not None:
            file, _, _ = value
            return file.filename, JSON_MEDIA_TYPE, file.content
        provenance, raw = await self._read_durable_source(
            context, decision, record_id=record_id, revision_id=revision_id
        )
        return str(provenance["original_filename"]), JSON_MEDIA_TYPE, raw

    async def source_availability_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        record_id: UUID,
        revision_id: UUID,
    ) -> dict[str, bool]:
        """Project exact source readiness for Materials without exposing legacy records."""

        self._require(context, decision, Permission.CATALOG_READ)
        try:
            published = self._is_published_exact(context, decision, record_id, revision_id)
        except ConfigurableCatalogConflict:
            published = False
        if not published:
            return {"available": False, "published": False, "ready": False}
        lookup = getattr(self._persistence, "get_provenance", None)
        if lookup is None or self._artifacts is None:
            return {"available": False, "published": True, "ready": False}
        ready = lookup(
            context=context,
            decision=self._read_decision(decision),
            record_id=record_id,
            revision_id=revision_id,
        ) is not None
        return {"available": ready, "published": True, "ready": ready}

    async def source_csv_download_async(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        record_id: UUID,
        revision_id: UUID,
        published_only: bool = False,
    ) -> tuple[str, str, bytes]:
        self._require(context, decision, Permission.CATALOG_READ)
        if published_only and not self._is_published_exact(
            context, decision, record_id, revision_id
        ):
            raise ConfigurableCatalogConflict(
                "exact CSV source is available only for a published Record revision"
            )
        value = self._provenance.get((record_id, revision_id))
        if value is not None:
            return self.source_csv_download(
                context, decision, record_id=record_id, revision_id=revision_id
            )
        provenance, raw = await self._read_durable_source(
            context, decision, record_id=record_id, revision_id=revision_id
        )
        format_revision_id = UUID(str(provenance["format_revision_id"]))
        format_value = await self._format_async(
            context,
            decision,
            format_revision_id,
            permission=Permission.CATALOG_READ,
        )
        document = parse_strict_json(raw, filename=str(provenance["original_filename"]))
        if not isinstance(document, Mapping):
            raise ConfigurableCatalogConflict("exact JSON source is not an object")
        revision_value = self._records.get_record_revision(
            context, decision, record_id, revision_id
        )
        key = revision_value.content.external_key or format_value.table_key
        normalized_values = {
            binding.json_pointer: (
                str(candidate.normalized_value),
                candidate.normalized_unit or "",
            )
            for binding in format_value.attributes
            for candidate in revision_value.content.values
            if candidate.attribute_definition_id == binding.attribute.id
            and candidate.normalized_value is not None
        }
        filename = exact_csv_filename(key, revision_value.record.revision_no)
        return (
            filename,
            "text/csv; charset=utf-8",
            source_csv_bytes(
                document,
                self._schema_with_wrapper(format_value),
                normalized_values=normalized_values,
            ),
        )

    def source_csv_download(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        record_id: UUID,
        revision_id: UUID,
        published_only: bool = False,
    ) -> tuple[str, str, bytes]:
        self._require(context, decision, Permission.CATALOG_READ)
        if published_only and not self._is_published_exact(
            context, decision, record_id, revision_id
        ):
            raise ConfigurableCatalogConflict(
                "exact CSV source is available only for a published Record revision"
            )
        value = self._provenance.get((record_id, revision_id))
        if value is None:
            raise ConfigurableCatalogConflict("exact JSON source provenance is unavailable")
        _, document, format_value = value
        revision_value = self._records.get_record_revision(
            context, decision, record_id, revision_id
        )
        key = revision_value.content.external_key or format_value.table_key
        normalized_values = {
            binding.json_pointer: (
                str(candidate.normalized_value),
                candidate.normalized_unit or "",
            )
            for binding in format_value.attributes
            for candidate in revision_value.content.values
            if candidate.attribute_definition_id == binding.attribute.id
            and candidate.normalized_value is not None
        }
        filename = exact_csv_filename(key, revision_value.record.revision_no)
        return (
            filename,
            "text/csv; charset=utf-8",
            source_csv_bytes(
                document,
                self._schema_with_wrapper(format_value),
                normalized_values=normalized_values,
            ),
        )


__all__ = [
    "JSON_REGISTRATION_TTL",
    "InstalledJsonRecordFormat",
    "JsonAttributeBinding",
    "JsonRecordRegistrationService",
    "JsonRegistrationErrorCode",
    "JsonRegistrationPersistence",
    "JsonRegistrationSaveResult",
]
