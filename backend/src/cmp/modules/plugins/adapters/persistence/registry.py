"""Atomic PostgreSQL implementation of the immutable T-17 plugin registry."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from itertools import pairwise
from typing import Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.plugins.application.registry import (
    ActivatePackage,
    PackageRegistrationResult,
    RegisterPackage,
)
from cmp.modules.plugins.domain.registry import (
    ActivationRecord,
    ArtifactReference,
    ImmutablePluginManifest,
    InvalidPackageState,
    PackageConflict,
    PackageNotFound,
    PackageRecord,
    PackageState,
    PackageStateEventRecord,
    SchemaDocument,
    SchemaRole,
    assert_package_transition,
)

metadata = sa.MetaData()
uuid_type = postgresql.UUID(as_uuid=True)

definition_table = sa.Table(
    "definition",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("plugin_id", sa.String(255), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    schema="plugin",
)

package_table = sa.Table(
    "package",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("definition_id", uuid_type, nullable=False),
    sa.Column("plugin_version", sa.String(64), nullable=False),
    sa.Column("display_name", sa.String(200), nullable=False),
    sa.Column("package_digest", sa.CHAR(64), nullable=False),
    sa.Column("manifest", postgresql.JSONB(), nullable=False),
    sa.Column("manifest_digest", sa.CHAR(64), nullable=False),
    sa.Column("contract_api", sa.String(100), nullable=False),
    sa.Column("network_policy", sa.String(32), nullable=False),
    sa.Column("requested_cpu", sa.Numeric(10, 3), nullable=False),
    sa.Column("requested_memory_mb", sa.Integer(), nullable=False),
    sa.Column("requested_gpu", sa.Integer(), nullable=False),
    sa.Column("requested_timeout_s", sa.Integer(), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    sa.Column("package_artifact_id", uuid_type, nullable=False),
    sa.Column("package_artifact_digest", sa.CHAR(64), nullable=False),
    sa.Column("package_artifact_size", sa.BigInteger(), nullable=False),
    sa.Column("package_artifact_media_type", sa.String(255), nullable=False),
    sa.Column("signature_artifact_id", uuid_type, nullable=False),
    sa.Column("signature_artifact_digest", sa.CHAR(64), nullable=False),
    sa.Column("signature_artifact_size", sa.BigInteger(), nullable=False),
    sa.Column("signature_artifact_media_type", sa.String(255), nullable=False),
    sa.Column("sbom_artifact_id", uuid_type, nullable=False),
    sa.Column("sbom_artifact_digest", sa.CHAR(64), nullable=False),
    sa.Column("sbom_artifact_size", sa.BigInteger(), nullable=False),
    sa.Column("sbom_artifact_media_type", sa.String(255), nullable=False),
    sa.Column("idempotency_key", sa.String(255), nullable=False),
    sa.Column("submission_digest", sa.CHAR(64), nullable=False),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("submitted_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="plugin",
)

extension_table = sa.Table(
    "extension",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("package_id", uuid_type, nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("extension_type", sa.String(64), nullable=False),
    sa.Column("entrypoint", sa.String(500), nullable=False),
    schema="plugin",
)

capability_table = sa.Table(
    "capability",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("package_id", uuid_type, nullable=False),
    sa.Column("extension_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("capability", sa.String(100), nullable=False),
    schema="plugin",
)

schema_table = sa.Table(
    "schema",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("package_id", uuid_type, nullable=False),
    sa.Column("extension_ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("schema_role", sa.String(32), nullable=False),
    sa.Column("schema_id", sa.String(500), nullable=False),
    sa.Column("document", postgresql.JSONB(), nullable=False),
    sa.Column("document_digest", sa.CHAR(64), nullable=False),
    schema="plugin",
)

artifact_role_table = sa.Table(
    "artifact_role",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("package_id", uuid_type, nullable=False),
    sa.Column("direction", sa.String(16), nullable=False),
    sa.Column("role_name", sa.String(100), nullable=False),
    schema="plugin",
)

state_event_table = sa.Table(
    "package_state_event",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("package_id", uuid_type, nullable=False),
    sa.Column("sequence_no", sa.BigInteger(), nullable=False),
    sa.Column("from_state", sa.String(32), nullable=True),
    sa.Column("to_state", sa.String(32), nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("actor_id", uuid_type, nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="plugin",
)

state_projection_table = sa.Table(
    "package_state_projection",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("package_id", uuid_type, nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("sequence_no", sa.BigInteger(), nullable=False),
    sa.Column("last_event_id", uuid_type, nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="plugin",
)

activation_table = sa.Table(
    "activation",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("package_id", uuid_type, nullable=False),
    sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("activated_by", uuid_type, nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="plugin",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _artifact(row: RowMapping, prefix: str) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=cast(UUID, row[f"{prefix}_artifact_id"]),
        sha256=str(row[f"{prefix}_artifact_digest"]),
        size_bytes=int(row[f"{prefix}_artifact_size"]),
        media_type=str(row[f"{prefix}_artifact_media_type"]),
    )


def _event(row: RowMapping) -> PackageStateEventRecord:
    source = row["from_state"]
    return PackageStateEventRecord(
        id=cast(UUID, row["id"]),
        package_id=cast(UUID, row["package_id"]),
        sequence_no=int(row["sequence_no"]),
        from_state=PackageState(str(source)) if source is not None else None,
        to_state=PackageState(str(row["to_state"])),
        occurred_at=row["occurred_at"],
        actor_id=cast(UUID, row["actor_id"]),
        reason=str(row["reason"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


class SqlAlchemyPluginRegistryRepository:
    """Store immutable package facts and serialize state/activation commands."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    def _bind(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @staticmethod
    def _package_row(
        session: Session,
        package_id: UUID,
        *,
        lock_projection: bool = False,
    ) -> RowMapping:
        joined = package_table.join(
            definition_table,
            sa.and_(
                definition_table.c.organization_id == package_table.c.organization_id,
                definition_table.c.project_id == package_table.c.project_id,
                definition_table.c.id == package_table.c.definition_id,
            ),
        ).join(
            state_projection_table,
            sa.and_(
                state_projection_table.c.organization_id
                == package_table.c.organization_id,
                state_projection_table.c.project_id == package_table.c.project_id,
                state_projection_table.c.package_id == package_table.c.id,
            ),
        )
        statement = (
            sa.select(
                package_table,
                definition_table.c.plugin_id.label("stable_plugin_id"),
                state_projection_table.c.state.label("current_state"),
                state_projection_table.c.sequence_no.label("current_sequence"),
            )
            .select_from(joined)
            .where(package_table.c.id == package_id)
        )
        if lock_projection:
            statement = statement.with_for_update(of=state_projection_table)
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise PackageNotFound(str(package_id))
        return row

    @staticmethod
    def _schemas(session: Session, package_id: UUID) -> tuple[SchemaDocument, ...]:
        rows = session.execute(
            sa.select(schema_table)
            .where(schema_table.c.package_id == package_id)
            .order_by(schema_table.c.extension_ordinal, schema_table.c.schema_id)
        ).mappings()
        return tuple(
            SchemaDocument.from_validated_document(
                schema_id=str(row["schema_id"]),
                extension_ordinal=int(row["extension_ordinal"]),
                role=SchemaRole(str(row["schema_role"])),
                document=row["document"],
                expected_sha256=str(row["document_digest"]),
            )
            for row in rows
        )

    @staticmethod
    def _events(
        session: Session, package_id: UUID
    ) -> tuple[PackageStateEventRecord, ...]:
        return tuple(
            _event(row)
            for row in session.execute(
                sa.select(state_event_table)
                .where(state_event_table.c.package_id == package_id)
                .order_by(state_event_table.c.sequence_no)
            ).mappings()
        )

    @staticmethod
    def _activation(session: Session, package_id: UUID) -> ActivationRecord | None:
        row = session.execute(
            sa.select(activation_table).where(
                activation_table.c.package_id == package_id
            )
        ).mappings().one_or_none()
        if row is None:
            return None
        return ActivationRecord(
            id=cast(UUID, row["id"]),
            package_id=cast(UUID, row["package_id"]),
            activated_at=row["activated_at"],
            activated_by=cast(UUID, row["activated_by"]),
            reason=str(row["reason"]),
            request_id=cast(UUID, row["request_id"]),
            trace_id=str(row["trace_id"]),
        )

    @classmethod
    def _record(cls, session: Session, row: RowMapping) -> PackageRecord:
        manifest = ImmutablePluginManifest.from_validated_document(row["manifest"])
        if (
            manifest.manifest_digest != row["manifest_digest"]
            or manifest.plugin_id != row["stable_plugin_id"]
            or manifest.plugin_version != row["plugin_version"]
            or manifest.display_name != row["display_name"]
            or manifest.package_digest != row["package_digest"]
            or manifest.contract_api != row["contract_api"]
            or manifest.network != row["network_policy"]
            or Decimal(str(manifest.cpu)) != row["requested_cpu"]
            or manifest.memory_mb != row["requested_memory_mb"]
            or manifest.gpu != row["requested_gpu"]
            or manifest.timeout_s != row["requested_timeout_s"]
            or row["non_production"] is not True
        ):
            raise RuntimeError("persisted plugin manifest projection mismatch")

        extension_rows = tuple(
            session.execute(
                sa.select(extension_table)
                .where(extension_table.c.package_id == row["id"])
                .order_by(extension_table.c.ordinal)
            ).mappings()
        )
        capabilities: dict[int, tuple[str, ...]] = {}
        for extension in extension_rows:
            ordinal = int(extension["ordinal"])
            capabilities[ordinal] = tuple(
                str(item)
                for item in session.execute(
                    sa.select(capability_table.c.capability)
                    .where(
                        capability_table.c.package_id == row["id"],
                        capability_table.c.extension_ordinal == ordinal,
                    )
                    .order_by(capability_table.c.capability)
                ).scalars()
            )
        if len(extension_rows) != len(manifest.extensions) or any(
            int(actual["ordinal"]) != expected.ordinal
            or str(actual["extension_type"]) != expected.extension_type.value
            or str(actual["entrypoint"]) != expected.entrypoint
            or capabilities[int(actual["ordinal"])] != expected.capabilities
            for actual, expected in zip(extension_rows, manifest.extensions, strict=True)
        ):
            raise RuntimeError("persisted plugin extension projection mismatch")

        roles = tuple(
            session.execute(
                sa.select(artifact_role_table.c.direction, artifact_role_table.c.role_name)
                .where(artifact_role_table.c.package_id == row["id"])
                .order_by(artifact_role_table.c.direction, artifact_role_table.c.role_name)
            )
        )
        read_roles = tuple(str(item.role_name) for item in roles if item.direction == "read")
        write_roles = tuple(
            str(item.role_name) for item in roles if item.direction == "write"
        )
        if (
            read_roles != manifest.artifact_read_roles
            or write_roles != manifest.artifact_write_roles
        ):
            raise RuntimeError("persisted plugin artifact role projection mismatch")

        schemas = cls._schemas(session, cast(UUID, row["id"]))
        if {item.extension_ordinal for item in schemas} != {
            item.ordinal for item in manifest.extensions
        }:
            raise RuntimeError("persisted plugin schema coverage mismatch")
        events = cls._events(session, cast(UUID, row["id"]))
        if not events or events[0].sequence_no != 1 or events[0].from_state is not None:
            raise RuntimeError("persisted plugin package has no valid initial state event")
        for previous, current in pairwise(events):
            if (
                current.sequence_no != previous.sequence_no + 1
                or current.from_state is not previous.to_state
            ):
                raise RuntimeError("persisted plugin package state history is discontinuous")
            assert_package_transition(previous.to_state, current.to_state)
        state = PackageState(str(row["current_state"]))
        if events[-1].to_state is not state or events[-1].sequence_no != int(
            row["current_sequence"]
        ):
            raise RuntimeError("persisted plugin state projection is stale")
        return PackageRecord(
            id=cast(UUID, row["id"]),
            definition_id=cast(UUID, row["definition_id"]),
            organization_id=cast(UUID, row["organization_id"]),
            project_id=cast(UUID, row["project_id"]),
            classification=DataClassification(str(row["classification"])),
            manifest=manifest,
            package_artifact=_artifact(row, "package"),
            signature_artifact=_artifact(row, "signature"),
            sbom_artifact=_artifact(row, "sbom"),
            schemas=schemas,
            state=state,
            state_events=events,
            submitted_at=row["submitted_at"],
            submitted_by=cast(UUID, row["submitted_by"]),
            submission_request_id=cast(UUID, row["request_id"]),
            submission_trace_id=str(row["trace_id"]),
            activation=cls._activation(session, cast(UUID, row["id"])),
        )

    def register(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RegisterPackage,
        definition_id: UUID,
        package_id: UUID,
        event_id: UUID,
        schema_ids: tuple[UUID, ...],
        manifest: ImmutablePluginManifest,
        schemas: tuple[SchemaDocument, ...],
        submission_digest: str,
        now: datetime,
    ) -> PackageRegistrationResult:
        if len(schema_ids) != len(schemas):
            raise RuntimeError("schema identity allocation does not match schema documents")
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            inserted_definition = session.execute(
                postgresql.insert(definition_table)
                .values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    id=definition_id,
                    classification=command.classification.value,
                    plugin_id=manifest.plugin_id,
                    created_at=now,
                    created_by=context.principal.id,
                )
                .on_conflict_do_nothing()
                .returning(definition_table.c.id)
            ).scalar_one_or_none()
            if inserted_definition is None:
                existing_definition = session.execute(
                    sa.select(definition_table).where(
                        definition_table.c.plugin_id == manifest.plugin_id
                    )
                ).mappings().one_or_none()
                if existing_definition is None:
                    raise PackageConflict("plugin definition identity is already in use")
                if existing_definition["classification"] != command.classification.value:
                    raise PackageConflict(
                        "plugin definition classification is immutable"
                    )
                stable_definition_id = cast(UUID, existing_definition["id"])
            else:
                stable_definition_id = cast(UUID, inserted_definition)

            package_values = {
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "id": package_id,
                "classification": command.classification.value,
                "definition_id": stable_definition_id,
                "plugin_version": manifest.plugin_version,
                "display_name": manifest.display_name,
                "package_digest": manifest.package_digest,
                "manifest": manifest.document(),
                "manifest_digest": manifest.manifest_digest,
                "contract_api": manifest.contract_api,
                "network_policy": manifest.network,
                "requested_cpu": Decimal(str(manifest.cpu)),
                "requested_memory_mb": manifest.memory_mb,
                "requested_gpu": manifest.gpu,
                "requested_timeout_s": manifest.timeout_s,
                "non_production": True,
                "package_artifact_id": command.package_artifact.artifact_id,
                "package_artifact_digest": command.package_artifact.sha256,
                "package_artifact_size": command.package_artifact.size_bytes,
                "package_artifact_media_type": command.package_artifact.media_type,
                "signature_artifact_id": command.signature_artifact.artifact_id,
                "signature_artifact_digest": command.signature_artifact.sha256,
                "signature_artifact_size": command.signature_artifact.size_bytes,
                "signature_artifact_media_type": command.signature_artifact.media_type,
                "sbom_artifact_id": command.sbom_artifact.artifact_id,
                "sbom_artifact_digest": command.sbom_artifact.sha256,
                "sbom_artifact_size": command.sbom_artifact.size_bytes,
                "sbom_artifact_media_type": command.sbom_artifact.media_type,
                "idempotency_key": command.idempotency_key,
                "submission_digest": submission_digest,
                "submitted_at": now,
                "submitted_by": context.principal.id,
                "request_id": context.request_id,
                "trace_id": context.trace_id,
            }
            inserted_package = session.execute(
                postgresql.insert(package_table)
                .values(**package_values)
                .on_conflict_do_nothing()
                .returning(package_table.c.id)
            ).scalar_one_or_none()
            if inserted_package is None:
                candidates: list[RowMapping] = []
                for condition in (
                    package_table.c.idempotency_key == command.idempotency_key,
                    sa.and_(
                        package_table.c.definition_id == stable_definition_id,
                        package_table.c.plugin_version == manifest.plugin_version,
                    ),
                    package_table.c.package_digest == manifest.package_digest,
                    package_table.c.id == package_id,
                ):
                    existing = session.execute(
                        sa.select(package_table).where(condition)
                    ).mappings().one_or_none()
                    if existing is not None:
                        candidates.append(existing)
                for existing in candidates:
                    if existing["submission_digest"] == submission_digest:
                        existing_id = cast(UUID, existing["id"])
                        return PackageRegistrationResult(
                            self._record(
                                session, self._package_row(session, existing_id)
                            ),
                            True,
                        )
                if any(
                    existing["definition_id"] == stable_definition_id
                    and existing["plugin_version"] == manifest.plugin_version
                    for existing in candidates
                ):
                    raise PackageConflict(
                        "plugin ID and version already map to a different digest"
                    )
                raise PackageConflict(
                    "package digest, idempotency key, or generated identity is already in use"
                )

            common_values = {
                "organization_id": context.organization_id,
                "project_id": context.project_id,
                "classification": command.classification.value,
                "package_id": package_id,
            }
            for extension in manifest.extensions:
                session.execute(
                    sa.insert(extension_table).values(
                        **common_values,
                        ordinal=extension.ordinal,
                        extension_type=extension.extension_type.value,
                        entrypoint=extension.entrypoint,
                    )
                )
                for capability in extension.capabilities:
                    session.execute(
                        sa.insert(capability_table).values(
                            **common_values,
                            extension_ordinal=extension.ordinal,
                            capability=capability,
                        )
                    )
            for schema_id, registered_schema in zip(
                schema_ids, schemas, strict=True
            ):
                session.execute(
                    sa.insert(schema_table).values(
                        **common_values,
                        id=schema_id,
                        extension_ordinal=registered_schema.extension_ordinal,
                        schema_role=registered_schema.role.value,
                        schema_id=registered_schema.schema_id,
                        document=registered_schema.document(),
                        document_digest=registered_schema.sha256,
                    )
                )
            for direction, roles in (
                ("read", manifest.artifact_read_roles),
                ("write", manifest.artifact_write_roles),
            ):
                for role in roles:
                    session.execute(
                        sa.insert(artifact_role_table).values(
                            **common_values,
                            direction=direction,
                            role_name=role,
                        )
                    )
            session.execute(
                sa.insert(state_event_table).values(
                    **common_values,
                    id=event_id,
                    sequence_no=1,
                    from_state=None,
                    to_state=PackageState.CONTRACT_VALIDATED.value,
                    occurred_at=now,
                    actor_id=context.principal.id,
                    reason="manifest and schemas contract validated",
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.insert(state_projection_table).values(
                    **common_values,
                    state=PackageState.CONTRACT_VALIDATED.value,
                    sequence_no=1,
                    last_event_id=event_id,
                    updated_at=now,
                )
            )
            return PackageRegistrationResult(
                self._record(session, self._package_row(session, package_id)), False
            )

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        package_id: UUID,
    ) -> PackageRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            return self._record(session, self._package_row(session, package_id))

    def get_active(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plugin_id: str,
        plugin_version: str,
        package_digest: str,
    ) -> PackageRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            active = (
                package_table.join(
                    definition_table,
                    sa.and_(
                        definition_table.c.organization_id
                        == package_table.c.organization_id,
                        definition_table.c.project_id == package_table.c.project_id,
                        definition_table.c.id == package_table.c.definition_id,
                    ),
                )
                .join(
                    state_projection_table,
                    sa.and_(
                        state_projection_table.c.organization_id
                        == package_table.c.organization_id,
                        state_projection_table.c.project_id == package_table.c.project_id,
                        state_projection_table.c.package_id == package_table.c.id,
                    ),
                )
                .join(
                    activation_table,
                    sa.and_(
                        activation_table.c.organization_id
                        == package_table.c.organization_id,
                        activation_table.c.project_id == package_table.c.project_id,
                        activation_table.c.package_id == package_table.c.id,
                    ),
                )
            )
            package_id = session.execute(
                sa.select(package_table.c.id)
                .select_from(active)
                .where(
                    definition_table.c.plugin_id == plugin_id,
                    package_table.c.plugin_version == plugin_version,
                    package_table.c.package_digest == package_digest,
                    state_projection_table.c.state == PackageState.ELIGIBLE.value,
                )
            ).scalar_one_or_none()
            if package_id is None:
                raise PackageNotFound("active plugin package is not visible")
            return self._record(
                session, self._package_row(session, cast(UUID, package_id))
            )

    def transition(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        package_id: UUID,
        target: PackageState,
        event_id: UUID,
        reason: str,
        now: datetime,
    ) -> PackageRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            package = self._package_row(session, package_id, lock_projection=True)
            current = PackageState(str(package["current_state"]))
            if current is target:
                return self._record(session, package)
            assert_package_transition(current, target)
            next_sequence = int(package["current_sequence"]) + 1
            common_values = {
                "organization_id": package["organization_id"],
                "project_id": package["project_id"],
                "classification": package["classification"],
                "package_id": package_id,
            }
            session.execute(
                sa.insert(state_event_table).values(
                    **common_values,
                    id=event_id,
                    sequence_no=next_sequence,
                    from_state=current.value,
                    to_state=target.value,
                    occurred_at=now,
                    actor_id=context.principal.id,
                    reason=reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            updated = session.execute(
                sa.update(state_projection_table)
                .where(
                    state_projection_table.c.organization_id
                    == package["organization_id"],
                    state_projection_table.c.project_id == package["project_id"],
                    state_projection_table.c.package_id == package_id,
                    state_projection_table.c.state == current.value,
                    state_projection_table.c.sequence_no
                    == package["current_sequence"],
                )
                .values(
                    state=target.value,
                    sequence_no=next_sequence,
                    last_event_id=event_id,
                    updated_at=now,
                )
            )
            if getattr(updated, "rowcount", None) != 1:
                raise PackageConflict("plugin package state changed concurrently")
            return self._record(
                session, self._package_row(session, package_id)
            )

    def activate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ActivatePackage,
        activation_id: UUID,
        now: datetime,
    ) -> PackageRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            package = self._package_row(
                session, command.package_id, lock_projection=True
            )
            if PackageState(str(package["current_state"])) is not PackageState.ELIGIBLE:
                raise InvalidPackageState(
                    "only an eligible plugin package can be activated"
                )
            existing = self._activation(session, command.package_id)
            if existing is not None:
                return self._record(session, package)
            inserted = session.execute(
                postgresql.insert(activation_table)
                .values(
                    organization_id=package["organization_id"],
                    project_id=package["project_id"],
                    id=activation_id,
                    classification=package["classification"],
                    package_id=command.package_id,
                    activated_at=now,
                    activated_by=context.principal.id,
                    reason=command.reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
                .on_conflict_do_nothing()
                .returning(activation_table.c.id)
            ).scalar_one_or_none()
            if inserted is None and self._activation(session, command.package_id) is None:
                raise PackageConflict("plugin activation identity is already in use")
            return self._record(
                session, self._package_row(session, command.package_id)
            )
