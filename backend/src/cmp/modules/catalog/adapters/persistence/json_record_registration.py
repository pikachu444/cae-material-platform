"""RLS-bound durable state for exact JSON registration tokens and provenance."""

from __future__ import annotations

import hashlib
import posixpath
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from cmp.modules.artifacts.adapters.persistence.content import artifact_table
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.catalog.adapters.persistence.configurable import (
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.adapters.persistence.links import (
    _RECORD_LINKS,
    link_type,
    link_type_revision,
    record_link,
    record_link_revision,
)
from cmp.modules.catalog.adapters.persistence.schema_bundle_applications import (
    schema_definition_bundle,
    schema_definition_bundle_application,
    schema_definition_bundle_binding,
    schema_definition_bundle_version,
)
from cmp.modules.catalog.application.configurable import AttributeSnapshot
from cmp.modules.catalog.application.json_record_registration import (
    InstalledJsonRecordFormat,
    JsonAttributeBinding,
    JsonRegistrationToken,
)
from cmp.modules.catalog.application.links import RECORD_LINK_AGGREGATE_TYPE
from cmp.modules.catalog.domain.configurable import ConfigurableCatalogConflict
from cmp.modules.catalog.domain.json_record_registration import (
    JSON_MEDIA_TYPE,
    JSON_PACKAGE_MEDIA_TYPE,
    MAX_PACKAGE_ARCHIVE_BYTES,
    flatten_schema_fields,
    json_pointer,
    parse_strict_json,
)
from cmp.modules.catalog.domain.links import RecordLinkContent, record_link_canonical
from cmp.modules.catalog.domain.schema_sources import (
    SOURCE_SET_CONTRACT_ID,
    SOURCE_SET_MEDIA_TYPE,
    SOURCE_ZIP_MEDIA_TYPE,
    _read_source_set_envelope,
    _read_source_zip,
    normalize_schema_definition_source,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.adapters.persistence.revisions import SqlAlchemyRevisionTransaction
from cmp.shared.domain.revisions import RevisionCreated, RevisionDraft, TenantScope, content_sha256

metadata = sa.MetaData()
_uuid = postgresql.UUID(as_uuid=True)


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")

json_record_registration_preview = sa.Table(
    "json_record_registration_preview",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("principal_id", _uuid, nullable=False),
    sa.Column("token_digest", sa.CHAR(64), nullable=False),
    sa.Column("format_id", _uuid, nullable=False),
    sa.Column("format_revision_id", _uuid, nullable=False),
    sa.Column("application_id", _uuid, nullable=False),
    sa.Column("application_revision_id", _uuid, nullable=False),
    sa.Column("schema_artifact_id", _uuid, nullable=False),
    sa.Column("schema_sha256", sa.CHAR(64), nullable=False),
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("package_artifact_id", _uuid, nullable=True),
    sa.Column("package_sha256", sa.CHAR(64), nullable=False),
    sa.Column("package_media_type", sa.String(64), nullable=False),
    sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("reference_pins", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("domain_bindings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("state", sa.String(16), nullable=False),
    sa.Column("batch_id", _uuid, nullable=True),
    schema="catalog",
)

json_record_registration_batch = sa.Table(
    "json_record_registration_batch",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("preview_id", _uuid, nullable=False),
    sa.Column("token_digest", sa.CHAR(64), nullable=False),
    sa.Column("format_id", _uuid, nullable=False),
    sa.Column("format_revision_id", _uuid, nullable=False),
    sa.Column("package_artifact_id", _uuid, nullable=True),
    sa.Column("package_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_state", sa.String(32), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("last_error", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    sa.Column("request_id", _uuid, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)

json_record_registration_batch_state_event = sa.Table(
    "json_record_registration_batch_state_event",
    metadata,
    sa.Column("id", _uuid, nullable=False),
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("batch_id", _uuid, nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("error", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", _uuid, nullable=False),
    sa.Column("request_id", _uuid, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)

json_record_registration_curve_artifact = sa.Table(
    "json_record_registration_curve_artifact",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("batch_id", _uuid, nullable=False),
    sa.Column("component_ordinal", sa.Integer(), nullable=False),
    sa.Column("original_filename", sa.String(255), nullable=False),
    sa.Column("json_pointer", sa.String(2000), nullable=False),
    sa.Column("artifact_id", _uuid, nullable=False),
    sa.Column("artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)

record_json_source_provenance = sa.Table(
    "record_json_source_provenance",
    metadata,
    sa.Column("organization_id", _uuid, nullable=False),
    sa.Column("project_id", _uuid, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("batch_id", _uuid, nullable=False),
    sa.Column("record_id", _uuid, nullable=False),
    sa.Column("record_revision_id", _uuid, nullable=False),
    sa.Column("component_ordinal", sa.Integer(), nullable=False),
    sa.Column("original_filename", sa.String(255), nullable=False),
    sa.Column("media_type", sa.String(64), nullable=False),
    sa.Column("source_artifact_id", _uuid, nullable=True),
    sa.Column("source_length_bytes", sa.BigInteger(), nullable=False),
    sa.Column("source_sha256", sa.CHAR(64), nullable=False),
    sa.Column("package_artifact_id", _uuid, nullable=True),
    sa.Column("package_component_path", sa.String(1000), nullable=True),
    sa.Column("package_sha256", sa.CHAR(64), nullable=False),
    sa.Column("format_id", _uuid, nullable=False),
    sa.Column("format_revision_id", _uuid, nullable=False),
    sa.Column("application_id", _uuid, nullable=False),
    sa.Column("application_revision_id", _uuid, nullable=False),
    sa.Column("schema_artifact_id", _uuid, nullable=False),
    sa.Column("schema_file", sa.String(1000), nullable=False),
    sa.Column("schema_pointer", sa.String(2000), nullable=False),
    sa.Column("schema_sha256", sa.CHAR(64), nullable=False),
    sa.Column("table_id", _uuid, nullable=False),
    sa.Column("table_revision_id", _uuid, nullable=False),
    sa.Column("table_source_file", sa.String(1000), nullable=False),
    sa.Column("table_source_pointer", sa.String(2000), nullable=False),
    sa.Column("table_source_sha256", sa.CHAR(64), nullable=False),
    sa.Column("pointer_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("unit_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    schema="catalog",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


class SqlAlchemyJsonRegistrationRepository:
    """Persist the command envelope without promoting source JSON to business state."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[Callable[[Session, RevisionCreated], None]] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)

    @staticmethod
    def token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _state_event(
        *,
        context: SecurityContext,
        token: JsonRegistrationToken,
        batch_id: UUID,
        state: str,
        attempt_count: int,
        error: str | None,
    ) -> dict[str, Any]:
        if state not in {"artifacts_pending", "ready", "reconciliation_failed"}:
            raise ValueError("invalid JSON registration batch source state")
        return {
            "id": uuid4(),
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": token.classification.value,
            "batch_id": batch_id,
            "state": state,
            "attempt_count": attempt_count,
            "error": error,
            "created_at": datetime.now(UTC),
            "created_by": context.principal.id,
            "request_id": context.request_id,
            "trace_id": context.trace_id,
        }

    def ensure_pending_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
    ) -> UUID:
        """Create or reuse the durable pending batch before derived Artifacts finalize."""

        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            preview = (
                session.execute(
                    sa.select(json_record_registration_preview)
                    .where(
                        json_record_registration_preview.c.organization_id
                        == context.organization_id,
                        json_record_registration_preview.c.project_id == context.project_id,
                        json_record_registration_preview.c.principal_id == context.principal.id,
                        json_record_registration_preview.c.token_digest
                        == self.token_digest(token.token),
                        json_record_registration_preview.c.state == "open",
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if preview is None:
                raise ValueError("JSON registration preview token is stale or already committed")

            stored_batch_id = preview.get("batch_id")
            if stored_batch_id is not None:
                selected_batch_id = UUID(str(stored_batch_id))
            else:
                existing = (
                    session.execute(
                        sa.select(json_record_registration_batch)
                        .where(
                            json_record_registration_batch.c.organization_id
                            == context.organization_id,
                            json_record_registration_batch.c.project_id == context.project_id,
                            json_record_registration_batch.c.token_digest
                            == self.token_digest(token.token),
                        )
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None:
                    selected_batch_id = UUID(str(existing["id"]))
                else:
                    selected_batch_id = batch_id
                    session.execute(
                        sa.insert(json_record_registration_batch).values(
                            id=selected_batch_id,
                            organization_id=context.organization_id,
                            project_id=context.project_id,
                            classification=token.classification.value,
                            preview_id=UUID(token.token),
                            token_digest=self.token_digest(token.token),
                            format_id=format_value.format_id,
                            format_revision_id=format_value.format_revision_id,
                            package_artifact_id=token.package_artifact_id,
                            package_sha256=token.package_sha256,
                            source_state="artifacts_pending",
                            attempt_count=0,
                            last_error=None,
                            created_at=datetime.now(UTC),
                            created_by=context.principal.id,
                            request_id=context.request_id,
                            trace_id=context.trace_id,
                        )
                    )
                    session.execute(
                        sa.insert(json_record_registration_batch_state_event).values(
                            self._state_event(
                                context=context,
                                token=token,
                                batch_id=selected_batch_id,
                                state="artifacts_pending",
                                attempt_count=0,
                                error=None,
                            )
                        )
                    )

            batch = (
                session.execute(
                    sa.select(json_record_registration_batch)
                    .where(
                        json_record_registration_batch.c.organization_id
                        == context.organization_id,
                        json_record_registration_batch.c.project_id == context.project_id,
                        json_record_registration_batch.c.id == selected_batch_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one_or_none()
            )
            if batch is None:
                raise ValueError("JSON registration pending batch is unavailable")
            if (
                batch["classification"] != token.classification.value
                or batch["format_id"] != format_value.format_id
                or batch["format_revision_id"] != format_value.format_revision_id
                or str(batch["package_sha256"]) != token.package_sha256
                or str(batch["source_state"]) != "artifacts_pending"
            ):
                raise ValueError("JSON registration pending batch identity changed")
            if preview.get("batch_id") is None:
                session.execute(
                    sa.update(json_record_registration_preview)
                    .where(
                        json_record_registration_preview.c.organization_id
                        == context.organization_id,
                        json_record_registration_preview.c.project_id == context.project_id,
                        json_record_registration_preview.c.id == preview["id"],
                        json_record_registration_preview.c.state == "open",
                        json_record_registration_preview.c.batch_id.is_(None),
                    )
                    .values(batch_id=selected_batch_id)
                )
            return selected_batch_id

    def persist_curve_artifact_in_transaction(
        self,
        *,
        session: Session,
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
    ) -> None:
        """Bind a finalized curve Artifact to its pending JSON batch in the same transaction."""

        self._rls.bind_authorization(session, context, decision)
        batch = (
            session.execute(
                sa.select(json_record_registration_batch)
                .where(
                    json_record_registration_batch.c.organization_id
                    == context.organization_id,
                    json_record_registration_batch.c.project_id == context.project_id,
                    json_record_registration_batch.c.id == batch_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if batch is None or str(batch["source_state"]) != "artifacts_pending":
            raise ValueError("curve Artifact requires an artifacts_pending JSON batch")
        if batch["classification"] != token.classification.value:
            raise ValueError("curve Artifact classification differs from JSON batch")
        artifact = (
            session.execute(
                sa.select(artifact_table)
                .where(
                    artifact_table.c.organization_id == context.organization_id,
                    artifact_table.c.project_id == context.project_id,
                    artifact_table.c.classification == token.classification.value,
                    artifact_table.c.id == artifact_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if artifact is None:
            raise ValueError("finalized curve Artifact is not visible in this scope")
        if (
            str(artifact["sha256"]) != artifact_sha256
            or int(artifact["size_bytes"]) != artifact_size_bytes
        ):
            raise ValueError("finalized curve Artifact differs from its immutable identity")
        existing = (
            session.execute(
                sa.select(json_record_registration_curve_artifact)
                .where(
                    json_record_registration_curve_artifact.c.organization_id
                    == context.organization_id,
                    json_record_registration_curve_artifact.c.project_id == context.project_id,
                    json_record_registration_curve_artifact.c.batch_id == batch_id,
                    json_record_registration_curve_artifact.c.original_filename == filename,
                    json_record_registration_curve_artifact.c.json_pointer == json_pointer,
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if (
                existing["artifact_id"] != artifact_id
                or str(existing["artifact_sha256"]) != artifact_sha256
                or int(existing["artifact_size_bytes"]) != artifact_size_bytes
            ):
                raise ValueError("curve Artifact association changed during retry")
            return
        session.execute(
            sa.insert(json_record_registration_curve_artifact).values(
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=token.classification.value,
                batch_id=batch_id,
                component_ordinal=component_ordinal,
                original_filename=filename,
                json_pointer=json_pointer,
                artifact_id=artifact_id,
                artifact_sha256=artifact_sha256,
                artifact_size_bytes=artifact_size_bytes,
                created_at=datetime.now(UTC),
            )
        )

    def save_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
    ) -> None:
        components = [
            {
                "filename": item.filename,
                "artifact_id": item.artifact_id,
                "package_path": item.package_path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
            }
            for item in token.files
        ]
        results = [item.as_dict() for item in token.results]
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            session.execute(
                sa.insert(json_record_registration_preview).values(
                    id=UUID(token.token),
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=token.classification.value,
                    principal_id=context.principal.id,
                    token_digest=self.token_digest(token.token),
                    format_id=format_value.format_id,
                    format_revision_id=format_value.format_revision_id,
                    application_id=format_value.application_id,
                    application_revision_id=format_value.application_revision_id,
                    schema_artifact_id=format_value.schema_artifact_id,
                    schema_sha256=format_value.schema_sha256,
                    table_id=format_value.table_id,
                    table_revision_id=format_value.table_revision_id,
                    package_artifact_id=token.package_artifact_id,
                    package_sha256=token.package_sha256,
                    package_media_type=(
                        JSON_PACKAGE_MEDIA_TYPE
                        if token.package_artifact_id is not None
                        else JSON_MEDIA_TYPE
                    ),
                    components=components,
                    results=results,
                    reference_pins=[
                        {
                            "file": key[0],
                            "selector": key[1],
                            **dict(value),
                        }
                        for key, value in token.reference_pins.items()
                    ],
                    domain_bindings=[
                        (
                            {
                                "file": binding[0],
                                "component": binding[1],
                                "kind": binding[2],
                                "object_id": str(binding[3]),
                                "revision_id": str(binding[4]),
                            }
                            if len(binding) == 5
                            else {
                                "kind": binding[0],
                                "object_id": str(binding[1]),
                                "revision_id": str(binding[2]),
                            }
                        )
                        for binding in token.domain_bindings
                    ],
                    created_at=token.created_at,
                    expires_at=token.expires_at,
                    state=token.state,
                    batch_id=token.batch_id,
                )
            )

    def load_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> Mapping[str, Any] | None:
        """Read one durable preview envelope for an API-worker retry."""

        with self._sessions() as session:
            self._rls.bind_authorization(session, context, decision)
            row = (
                session.execute(
                    sa.select(json_record_registration_preview).where(
                        json_record_registration_preview.c.organization_id
                        == context.organization_id,
                        json_record_registration_preview.c.project_id == context.project_id,
                        json_record_registration_preview.c.principal_id == context.principal.id,
                        json_record_registration_preview.c.token_digest == self.token_digest(token),
                    )
                )
                .mappings()
                .one_or_none()
            )
            return dict(row) if row is not None else None

    def load_committed_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
    ) -> Mapping[str, Any] | None:
        """Read durable Record identities for a post-commit acknowledgement retry."""

        with self._sessions() as session:
            self._rls.bind_authorization(session, context, decision)
            batch = (
                session.execute(
                    sa.select(json_record_registration_batch).where(
                        json_record_registration_batch.c.organization_id
                        == context.organization_id,
                        json_record_registration_batch.c.project_id == context.project_id,
                        json_record_registration_batch.c.token_digest == self.token_digest(token),
                    )
                )
                .mappings()
                .one_or_none()
            )
            if batch is None:
                return None
            rows = (
                session.execute(
                    sa.select(
                        record_json_source_provenance.c.record_id,
                        record_json_source_provenance.c.record_revision_id,
                    )
                    .where(
                        record_json_source_provenance.c.organization_id
                        == context.organization_id,
                        record_json_source_provenance.c.project_id == context.project_id,
                        record_json_source_provenance.c.batch_id == batch["id"],
                    )
                    .order_by(record_json_source_provenance.c.component_ordinal.asc())
                )
                .mappings()
                .all()
            )
            return {
                "batch_id": batch["id"],
                "package_sha256": str(batch["package_sha256"]),
                "format_revision_id": batch["format_revision_id"],
                "records": tuple(
                    (row["record_id"], row["record_revision_id"]) for row in rows
                ),
            }

    def commit_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: str,
        batch_id: UUID,
    ) -> bool:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            result = cast(
                CursorResult[Any],
                session.execute(
                    sa.update(json_record_registration_preview)
                    .where(
                        json_record_registration_preview.c.organization_id
                        == context.organization_id,
                        json_record_registration_preview.c.project_id == context.project_id,
                        json_record_registration_preview.c.principal_id == context.principal.id,
                        json_record_registration_preview.c.token_digest == self.token_digest(token),
                        json_record_registration_preview.c.state == "open",
                        json_record_registration_preview.c.expires_at > datetime.now(UTC),
                    )
                    .values(state="committed", batch_id=batch_id)
                ),
            )
            return result.rowcount == 1

    def save_batch(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
    ) -> None:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            session.execute(
                sa.insert(json_record_registration_batch).values(
                    id=batch_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=token.classification.value,
                    preview_id=UUID(token.token),
                    token_digest=self.token_digest(token.token),
                    format_id=format_value.format_id,
                    format_revision_id=format_value.format_revision_id,
                    package_artifact_id=token.package_artifact_id,
                    package_sha256=token.package_sha256,
                    source_state="ready",
                    attempt_count=0,
                    last_error=None,
                    created_at=datetime.now(UTC),
                    created_by=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.insert(json_record_registration_batch_state_event),
                [
                    self._state_event(
                        context=context,
                        token=token,
                        batch_id=batch_id,
                        state="artifacts_pending",
                        attempt_count=0,
                        error=None,
                    ),
                    self._state_event(
                        context=context,
                        token=token,
                        batch_id=batch_id,
                        state="ready",
                        attempt_count=0,
                        error=None,
                    ),
                ],
            )

    def append_batch_state_event(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        batch_id: UUID,
        state: str,
        error: str | None = None,
    ) -> None:
        """Append a reconciliation state fact without mutating the batch identity."""

        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            batch = session.execute(
                sa.select(json_record_registration_batch)
                .where(
                    json_record_registration_batch.c.organization_id == context.organization_id,
                    json_record_registration_batch.c.project_id == context.project_id,
                    json_record_registration_batch.c.id == batch_id,
                )
                .with_for_update()
            ).mappings().one_or_none()
            if batch is None:
                raise ValueError("JSON registration batch is not visible in this scope")
            previous = session.execute(
                sa.select(sa.func.max(json_record_registration_batch_state_event.c.attempt_count))
                .where(
                    json_record_registration_batch_state_event.c.organization_id
                    == context.organization_id,
                    json_record_registration_batch_state_event.c.project_id == context.project_id,
                    json_record_registration_batch_state_event.c.batch_id == batch_id,
                )
            ).scalar_one_or_none()
            attempt_count = int(previous or 0) + (1 if state == "reconciliation_failed" else 0)
            token = JsonRegistrationToken(
                token="state-event",
                format_revision_id=batch["format_revision_id"],
                caller_id=context.principal.id,
                package_sha256=str(batch["package_sha256"]),
                package_artifact_id=batch["package_artifact_id"],
                classification=DataClassification(str(batch["classification"])),
                files=(),
                documents=(),
                results=(),
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC),
            )
            session.execute(
                sa.insert(json_record_registration_batch_state_event).values(
                    self._state_event(
                        context=context,
                        token=token,
                        batch_id=batch_id,
                        state=state,
                        attempt_count=attempt_count,
                        error=error,
                    )
                )
            )

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
    ) -> None:
        rows = []
        for ordinal, (file, record) in enumerate(zip(token.files, records, strict=True), start=1):
            rows.append(
                {
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                    "classification": token.classification.value,
                    "batch_id": batch_id,
                    "record_id": record.id,
                    "record_revision_id": record.current.record.revision_id,
                    "component_ordinal": ordinal,
                    "original_filename": file.filename,
                    "media_type": file.media_type,
                    "source_artifact_id": UUID(file.artifact_id) if file.artifact_id else None,
                    "source_length_bytes": file.size_bytes,
                    "source_sha256": file.sha256,
                    "package_artifact_id": token.package_artifact_id,
                    "package_component_path": file.package_path,
                    "package_sha256": token.package_sha256,
                    "format_id": format_value.format_id,
                    "format_revision_id": format_value.format_revision_id,
                    "application_id": format_value.application_id,
                    "application_revision_id": format_value.application_revision_id,
                    "schema_artifact_id": format_value.schema_artifact_id,
                    "schema_file": format_value.schema_file,
                    "schema_pointer": format_value.schema_pointer,
                    "schema_sha256": format_value.schema_sha256,
                    "table_id": format_value.table_id,
                    "table_revision_id": format_value.table_revision_id,
                    "table_source_file": format_value.table_source_file,
                    "table_source_pointer": format_value.table_source_pointer,
                    "table_source_sha256": format_value.table_source_sha256,
                    "pointer_evidence": {},
                    "unit_evidence": {},
                    "created_at": datetime.now(UTC),
                }
            )
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            session.execute(sa.insert(record_json_source_provenance), rows)
            self._persist_links_in_transaction(
                session=session,
                context=context,
                token=token,
                format_value=format_value,
                batch_id=batch_id,
                records=records,
                resolved_links=resolved_links,
            )

    def get_provenance(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
    ) -> dict[str, Any] | None:
        """Read one exact source pin through the same scoped RLS session."""

        with self._sessions() as session:
            self._rls.bind_authorization(session, context, decision)
            latest_state = (
                sa.select(json_record_registration_batch_state_event.c.state)
                .where(
                    json_record_registration_batch_state_event.c.organization_id
                    == context.organization_id,
                    json_record_registration_batch_state_event.c.project_id == context.project_id,
                    json_record_registration_batch_state_event.c.batch_id
                    == json_record_registration_batch.c.id,
                )
                .order_by(
                    json_record_registration_batch_state_event.c.created_at.desc(),
                    json_record_registration_batch_state_event.c.id.desc(),
                )
                .limit(1)
                .scalar_subquery()
            )
            row = (
                session.execute(
                    sa.select(record_json_source_provenance)
                    .select_from(
                        record_json_source_provenance.join(
                            json_record_registration_batch,
                            sa.and_(
                                json_record_registration_batch.c.organization_id
                                == record_json_source_provenance.c.organization_id,
                                json_record_registration_batch.c.project_id
                                == record_json_source_provenance.c.project_id,
                                json_record_registration_batch.c.id
                                == record_json_source_provenance.c.batch_id,
                            ),
                        )
                    )
                    .where(
                        record_json_source_provenance.c.organization_id
                        == context.organization_id,
                        record_json_source_provenance.c.project_id == context.project_id,
                        record_json_source_provenance.c.record_id == record_id,
                        record_json_source_provenance.c.record_revision_id == revision_id,
                        sa.or_(latest_state.is_(None), latest_state == "ready"),
                    )
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            return dict(row) if row is not None else None

    def _persist_links_in_transaction(
        self,
        *,
        session: Session,
        context: SecurityContext,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
        records: Sequence[Any],
        resolved_links: Sequence[tuple[str, str, str, str, UUID, UUID]],
    ) -> None:
        """Persist the exact approved links resolved by the registration command.

        Link identities and revisions are created through the shared typed revision
        transaction while the caller's Record transaction is still open.  This keeps
        Record, source provenance, and links atomic and prevents a partial graph from
        being published when one component fails.
        """

        if not resolved_links:
            return
        link_revision_ids = tuple(
            value for value in format_value.link_type_revision_ids if isinstance(value, UUID)
        )
        if not link_revision_ids:
            raise ValueError("JSON registration resolved a link without installed link types")
        link_rows = (
            session.execute(
                sa.select(
                    link_type.c.id.label("link_type_id"),
                    link_type_revision.c.id.label("link_type_revision_id"),
                    link_type_revision.c.link_key,
                    link_type_revision.c.source_table_id,
                    link_type_revision.c.target_table_id,
                )
                .select_from(
                    link_type.join(
                        link_type_revision,
                        sa.and_(
                            link_type_revision.c.aggregate_id == link_type.c.id,
                            link_type_revision.c.organization_id
                            == link_type.c.organization_id,
                            link_type_revision.c.project_id == link_type.c.project_id,
                            link_type_revision.c.classification
                            == link_type.c.classification,
                        ),
                    )
                )
                .where(
                    link_type.c.organization_id == context.organization_id,
                    link_type.c.project_id == context.project_id,
                    link_type_revision.c.id.in_(link_revision_ids),
                )
            )
            .mappings()
            .all()
        )
        link_by_key = {str(row["link_key"]): dict(row) for row in link_rows}
        record_by_file = {
            (file.filename, file.sha256): record
            for file, record in zip(token.files, records, strict=True)
        }
        transaction = SqlAlchemyRevisionTransaction(session, _RECORD_LINKS, self._hooks)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            token.classification.value,
        )
        seen: set[tuple[UUID, UUID, UUID, UUID, UUID]] = set()
        for (
            filename,
            file_sha256,
            pointer,
            link_key,
            target_id,
            target_revision_id,
        ) in resolved_links:
            link = link_by_key.get(link_key)
            if link is None:
                raise ValueError(f"installed link type '{link_key}' is not available")
            record = record_by_file.get((filename, file_sha256))
            if record is None:
                raise ValueError(
                    f"resolved JSON link source '{filename}' does not match a registered file"
                )
            source_table_id = link["source_table_id"]
            target_table_id = link["target_table_id"]
            record_revision_id = record.current.record.revision_id
            if format_value.table_id == source_table_id:
                source_record_id = record.id
                source_record_revision_id = record_revision_id
                link_target_id = target_id
                link_target_revision_id = target_revision_id
            elif format_value.table_id == target_table_id:
                source_record_id = target_id
                source_record_revision_id = target_revision_id
                link_target_id = record.id
                link_target_revision_id = record_revision_id
            else:
                raise ValueError(
                    f"link type '{link_key}' does not connect table '{format_value.table_key}'"
                )
            identity = (
                link["link_type_id"],
                source_record_id,
                link_target_id,
                source_record_revision_id,
                link_target_revision_id,
            )
            if identity in seen:
                continue
            seen.add(identity)
            existing = session.execute(
                sa.select(record_link.c.id)
                .select_from(
                    record_link.join(
                        record_link_revision,
                        sa.and_(
                            record_link_revision.c.id
                            == record_link.c.current_revision_id,
                            record_link_revision.c.aggregate_id == record_link.c.id,
                            record_link_revision.c.organization_id
                            == record_link.c.organization_id,
                            record_link_revision.c.project_id == record_link.c.project_id,
                            record_link_revision.c.classification
                            == record_link.c.classification,
                        ),
                    )
                )
                .where(
                    record_link.c.organization_id == context.organization_id,
                    record_link.c.project_id == context.project_id,
                    record_link.c.link_type_id == link["link_type_id"],
                    record_link_revision.c.source_record_id == source_record_id,
                    record_link_revision.c.source_record_revision_id
                    == source_record_revision_id,
                    record_link_revision.c.target_record_id == link_target_id,
                    record_link_revision.c.target_record_revision_id
                    == link_target_revision_id,
                    record_link_revision.c.active.is_(True),
                )
                .limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                continue
            content = RecordLinkContent(
                link_type_id=link["link_type_id"],
                link_type_revision_id=link["link_type_revision_id"],
                source_record_id=source_record_id,
                source_record_revision_id=source_record_revision_id,
                target_record_id=link_target_id,
                target_record_revision_id=link_target_revision_id,
                active=True,
                note=f"JSON registration {filename} at {pointer}",
            )
            draft = RevisionDraft(
                revision_id=uuid4(),
                aggregate_type=RECORD_LINK_AGGREGATE_TYPE,
                aggregate_id=uuid4(),
                scope=scope,
                schema_id="urn:cmp:catalog:record-link:1.0.0",
                schema_version="1.0.0",
                content=content,
                content_hash=content_sha256(record_link_canonical(content)),
                created_at=datetime.now(UTC),
                created_by=context.principal.id,
                change_reason=f"JSON registration batch {batch_id}",
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
            revision = transaction.create(draft)
            transaction.stage(RevisionCreated(revision, "draft"))

    def _validate_curve_associations_in_transaction(
        self,
        *,
        session: Session,
        context: SecurityContext,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
        file_documents: Mapping[tuple[str, str], Mapping[str, Any]],
        ordered_files: Sequence[Any],
    ) -> None:
        expected: dict[tuple[str, str], int] = {}
        for ordinal, file in enumerate(ordered_files, start=1):
            document = file_documents[(file.filename, file.sha256)]
            for binding in format_value.attributes:
                if binding.attribute.current.content.data_type.value != "curve":
                    continue
                try:
                    value = json_pointer(document, binding.json_pointer)
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if value is not None:
                    expected[(file.filename, binding.json_pointer)] = ordinal
        rows = (
            session.execute(
                sa.select(json_record_registration_curve_artifact)
                .where(
                    json_record_registration_curve_artifact.c.organization_id
                    == context.organization_id,
                    json_record_registration_curve_artifact.c.project_id == context.project_id,
                    json_record_registration_curve_artifact.c.batch_id == batch_id,
                )
            )
            .mappings()
            .all()
        )
        actual = {(str(row["original_filename"]), str(row["json_pointer"])): row for row in rows}
        if set(actual) != set(expected):
            raise ValueError("pending JSON curve Artifact associations are incomplete")
        for key, ordinal in expected.items():
            row = actual[key]
            if int(row["component_ordinal"]) != ordinal:
                raise ValueError("pending JSON curve Artifact component order changed")
            artifact = (
                session.execute(
                    sa.select(artifact_table.c.sha256, artifact_table.c.size_bytes)
                    .where(
                        artifact_table.c.organization_id == context.organization_id,
                        artifact_table.c.project_id == context.project_id,
                        artifact_table.c.classification == token.classification.value,
                        artifact_table.c.id == row["artifact_id"],
                    )
                )
                .mappings()
                .one_or_none()
            )
            if artifact is None or (
                str(artifact["sha256"]) != str(row["artifact_sha256"])
                or int(artifact["size_bytes"]) != int(row["artifact_size_bytes"])
            ):
                raise ValueError("pending JSON curve Artifact identity is inconsistent")

    def persist_batch_in_transaction(
        self,
        *,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
        token: JsonRegistrationToken,
        format_value: InstalledJsonRecordFormat,
        batch_id: UUID,
        records: Sequence[Any],
        resolved_links: Sequence[tuple[str, str, str, str, UUID, UUID]] = (),
    ) -> None:
        """Insert batch/provenance and consume the token in the Record transaction.

        ``SqlAlchemyCatalogRecordRepository.create_records_atomically`` invokes this hook
        before its outer transaction commits.  A failed evidence insert therefore rolls back
        the typed Record rows as well as the token transition.
        """

        preview = (
            session.execute(
                sa.select(json_record_registration_preview)
                .where(
                    json_record_registration_preview.c.organization_id == context.organization_id,
                    json_record_registration_preview.c.project_id == context.project_id,
                    json_record_registration_preview.c.principal_id == context.principal.id,
                    json_record_registration_preview.c.token_digest
                    == self.token_digest(token.token),
                    json_record_registration_preview.c.state == "open",
                    json_record_registration_preview.c.expires_at > datetime.now(UTC),
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if preview is None:
            raise ValueError("JSON registration preview token is stale or already committed")
        if len(records) != len(token.files):
            raise ValueError("JSON registration provenance count differs from Record count")
        if preview["batch_id"] is not None and preview["batch_id"] != batch_id:
            raise ValueError("JSON registration batch identity differs from the preview")

        existing_batch = (
            session.execute(
                sa.select(json_record_registration_batch)
                .where(
                    json_record_registration_batch.c.organization_id
                    == context.organization_id,
                    json_record_registration_batch.c.project_id == context.project_id,
                    json_record_registration_batch.c.id == batch_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if existing_batch is not None:
            if (
                existing_batch["classification"] != token.classification.value
                or existing_batch["format_id"] != format_value.format_id
                or existing_batch["format_revision_id"] != format_value.format_revision_id
                or str(existing_batch["package_sha256"]) != token.package_sha256
                or str(existing_batch["source_state"]) != "artifacts_pending"
            ):
                raise ValueError("pending JSON registration batch identity changed")

        file_documents = {
            (file.filename, file.sha256): document
            for file, document in zip(token.files, token.documents, strict=True)
        }
        ordered_files = tuple(
            sorted(
                token.files,
                key=lambda item: (
                    item.filename.encode("utf-8"),
                    item.sha256,
                ),
            )
        )
        if existing_batch is not None:
            self._validate_curve_associations_in_transaction(
                session=session,
                context=context,
                token=token,
                format_value=format_value,
                batch_id=batch_id,
                file_documents=file_documents,
                ordered_files=ordered_files,
            )
        record_by_file = {
            (file.filename, file.sha256): record
            for file, record in zip(token.files, records, strict=True)
        }
        rows: list[dict[str, Any]] = []
        for ordinal, file in enumerate(ordered_files, start=1):
            if not file.artifact_id and not (
                token.package_artifact_id is not None and file.package_path
            ):
                raise ValueError(
                    "JSON source provenance requires a verified source Artifact or package path"
                )
            document = file_documents[(file.filename, file.sha256)]
            record = record_by_file[(file.filename, file.sha256)]
            pointer_evidence: dict[str, Any] = {}
            unit_evidence: dict[str, Any] = {}
            for binding in format_value.attributes:
                try:
                    source_value = json_pointer(document, binding.json_pointer)
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                pointer_evidence[binding.json_pointer] = {
                    "label": binding.attribute.current.content.name,
                    "value": source_value,
                    "section": binding.section,
                }
                unit_evidence[binding.json_pointer] = {
                    "original_unit": binding.source_unit,
                    "quantity_semantics": binding.quantity_semantics,
                    "normalized_unit": binding.attribute.current.content.normalized_unit,
                }
            rows.append(
                {
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                    "classification": token.classification.value,
                    "batch_id": batch_id,
                    "record_id": record.id,
                    "record_revision_id": record.current.record.revision_id,
                    "component_ordinal": ordinal,
                    "original_filename": file.filename,
                    "media_type": file.media_type,
                    "source_artifact_id": UUID(file.artifact_id) if file.artifact_id else None,
                    "source_length_bytes": file.size_bytes,
                    "source_sha256": file.sha256,
                    "package_artifact_id": token.package_artifact_id,
                    "package_component_path": file.package_path,
                    "package_sha256": token.package_sha256,
                    "format_id": format_value.format_id,
                    "format_revision_id": format_value.format_revision_id,
                    "application_id": format_value.application_id,
                    "application_revision_id": format_value.application_revision_id,
                    "schema_artifact_id": format_value.schema_artifact_id,
                    "schema_file": format_value.schema_file,
                    "schema_pointer": format_value.schema_pointer,
                    "schema_sha256": format_value.schema_sha256,
                    "table_id": format_value.table_id,
                    "table_revision_id": format_value.table_revision_id,
                    "table_source_file": format_value.table_source_file,
                    "table_source_pointer": format_value.table_source_pointer,
                    "table_source_sha256": format_value.table_source_sha256,
                    "pointer_evidence": pointer_evidence,
                    "unit_evidence": unit_evidence,
                    "created_at": datetime.now(UTC),
                }
            )
        if existing_batch is None:
            session.execute(
                sa.insert(json_record_registration_batch).values(
                    id=batch_id,
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=token.classification.value,
                    preview_id=UUID(token.token),
                    token_digest=self.token_digest(token.token),
                    format_id=format_value.format_id,
                    format_revision_id=format_value.format_revision_id,
                    package_artifact_id=token.package_artifact_id,
                    package_sha256=token.package_sha256,
                    source_state="ready",
                    attempt_count=0,
                    last_error=None,
                    created_at=datetime.now(UTC),
                    created_by=context.principal.id,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
            session.execute(
                sa.insert(json_record_registration_batch_state_event).values(
                    self._state_event(
                        context=context,
                        token=token,
                        batch_id=batch_id,
                        state="artifacts_pending",
                        attempt_count=0,
                        error=None,
                    )
                )
            )
        session.execute(sa.insert(record_json_source_provenance), rows)
        self._persist_links_in_transaction(
            session=session,
            context=context,
            token=token,
            format_value=format_value,
            batch_id=batch_id,
            records=records,
            resolved_links=resolved_links,
        )
        session.execute(
            sa.insert(json_record_registration_batch_state_event).values(
                self._state_event(
                    context=context,
                    token=token,
                    batch_id=batch_id,
                    state="ready",
                    attempt_count=0,
                    error=None,
                )
            )
        )
        updated = cast(
            CursorResult[Any],
            session.execute(
                sa.update(json_record_registration_preview)
                .where(
                    json_record_registration_preview.c.organization_id == context.organization_id,
                    json_record_registration_preview.c.project_id == context.project_id,
                    json_record_registration_preview.c.id == preview["id"],
                    json_record_registration_preview.c.state == "open",
                )
                .values(state="committed", batch_id=batch_id)
            ),
        )
        if updated.rowcount != 1:
            raise ValueError("JSON registration preview token could not be committed")


class SqlAlchemyInstalledJsonRecordFormatResolver:
    """Discover JSON formats from the exact current Schema Bundle applications.

    The application table deliberately does not expose a mutable ``latest`` revision.  A
    format is therefore materialised only from ``schema_definition_bundle.current_application_id``
    and the immutable application bindings behind that identity.  Source-v2 applications are
    re-read from their immutable source-set Artifact so the format keeps the original source file
    path, digest, and pointer alongside the exact Catalog Table/Attribute revisions.
    """

    _APPROVED_LINK_KEYS = frozenset(
        {
            "technical_to_tensile",
            "technical_to_dma",
            "technical_to_fld",
            "tensile_to_elastoplasticity",
            "tensile_to_statistics",
        }
    )

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: RlsContext,
        artifacts: ArtifactService,
        schemas: SqlAlchemyConfigurableCatalogRepository,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._artifacts = artifacts
        self._schemas = schemas

    def _current_applications(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[tuple[dict[str, Any], tuple[dict[str, Any], ...]], ...]:
        application = schema_definition_bundle_application
        bundle = schema_definition_bundle
        version = schema_definition_bundle_version
        statement = (
            sa.select(application, bundle.c.bundle_key, version.c.bundle_version)
            .select_from(
                application.join(
                    bundle,
                    sa.and_(
                        bundle.c.id == application.c.bundle_id,
                        bundle.c.organization_id == application.c.organization_id,
                        bundle.c.project_id == application.c.project_id,
                    ),
                ).join(
                    version,
                    sa.and_(
                        version.c.id == application.c.bundle_version_id,
                        version.c.bundle_id == bundle.c.id,
                        version.c.organization_id == application.c.organization_id,
                        version.c.project_id == application.c.project_id,
                    ),
                )
            )
            .where(
                application.c.organization_id == context.organization_id,
                application.c.project_id == context.project_id,
                bundle.c.current_application_id == application.c.id,
            )
            .order_by(bundle.c.bundle_key.asc(), application.c.id.asc())
        )
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            rows = session.execute(statement).mappings().all()
            result: list[tuple[dict[str, Any], tuple[dict[str, Any], ...]]] = []
            for row in rows:
                bindings = session.execute(
                    sa.select(schema_definition_bundle_binding)
                    .where(
                        schema_definition_bundle_binding.c.organization_id
                        == context.organization_id,
                        schema_definition_bundle_binding.c.project_id == context.project_id,
                        schema_definition_bundle_binding.c.application_id == row["id"],
                    )
                    .order_by(
                        schema_definition_bundle_binding.c.sequence.asc(),
                        schema_definition_bundle_binding.c.external_key.asc(),
                    )
                ).mappings()
                result.append((dict(row), tuple(dict(item) for item in bindings)))
            return tuple(result)

    @staticmethod
    def _source_files(raw: bytes, media_type: str) -> dict[str, bytes] | None:
        normalized = media_type.split(";", maxsplit=1)[0].strip().lower()
        try:
            document = parse_strict_json(raw, filename="schema-source.json")
        except Exception:
            document = None
        if normalized == SOURCE_SET_MEDIA_TYPE or (
            isinstance(document, dict) and document.get("$schema") == SOURCE_SET_CONTRACT_ID
        ):
            files, diagnostics = _read_source_set_envelope(raw)
            if files is None:
                detail = "; ".join(item.message for item in diagnostics[:3])
                raise ConfigurableCatalogConflict(
                    f"installed source-set Artifact is invalid{': ' + detail if detail else ''}"
                )
            return files
        if normalized in {"application/zip", SOURCE_ZIP_MEDIA_TYPE}:
            files, diagnostics = _read_source_zip(raw)
            if files is None:
                detail = "; ".join(item.message for item in diagnostics[:3])
                raise ConfigurableCatalogConflict(
                    f"installed source ZIP Artifact is invalid{': ' + detail if detail else ''}"
                )
            return files
        return None

    @staticmethod
    def _manifest(files: Mapping[str, bytes]) -> tuple[str, dict[str, Any]]:
        candidates: list[tuple[str, dict[str, Any]]] = []
        for path, raw in sorted(files.items()):
            try:
                value = parse_strict_json(raw, filename=path)
            except Exception:
                continue
            if (
                isinstance(value, dict)
                and value.get("document_type") == "cmp.catalog-schema-bundle"
            ):
                candidates.append((path, value))
        if len(candidates) != 1:
            raise ConfigurableCatalogConflict(
                "installed source-v2 Artifact must contain exactly one schema bundle manifest"
            )
        return candidates[0]

    @staticmethod
    def _schema_entry(
        canonical: Mapping[str, Any], table_key: str
    ) -> Mapping[str, Any]:
        entries = canonical.get("record_schemas")
        if not isinstance(entries, list):
            raise ConfigurableCatalogConflict(
                "installed source-v2 application has no record schemas"
            )
        matches = [
            item
            for item in entries
            if isinstance(item, Mapping) and item.get("key") == table_key
        ]
        if len(matches) != 1 or not isinstance(matches[0].get("schema"), Mapping):
            raise ConfigurableCatalogConflict(
                f"installed source-v2 application has no unique schema for table '{table_key}'"
            )
        return matches[0]

    def _attribute_bindings(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        table_key: str,
        schema: Mapping[str, Any],
        bindings: Sequence[Mapping[str, Any]],
        source_file: str | None = None,
    ) -> tuple[JsonAttributeBinding, ...]:
        attribute_rows = {
            str(item["external_key"]): item
            for item in bindings
            if item.get("target_type") == "attribute"
            and item.get("parent_external_key") == table_key
        }
        source_attribute_rows = {
            str(item["source_pointer"]): item
            for item in bindings
            if item.get("target_type") == "attribute"
            and item.get("parent_external_key") == table_key
            and isinstance(item.get("source_pointer"), str)
        }
        fields = tuple(
            field
            for field in flatten_schema_fields(schema)
            if not (
                isinstance(field.schema.get("x-reference"), Mapping)
                and field.schema["x-reference"].get("reference_only") is True
            )
        )
        values: list[JsonAttributeBinding] = []
        for field in fields:
            key = field.schema.get("x-key")
            row = attribute_rows.get(key) if isinstance(key, str) else None
            if row is None and source_file is not None:
                source_pointer = "/files/" + _escape_pointer(source_file)
                source_pointer += "".join(
                    "/properties/" + segment
                    for segment in field.pointer.strip("/").split("/")
                    if segment
                )
                row = source_attribute_rows.get(source_pointer)
            if row is None:
                declared_type = field.schema.get("type")
                declared_types = (
                    {declared_type}
                    if isinstance(declared_type, str)
                    else {item for item in declared_type if isinstance(item, str)}
                    if isinstance(declared_type, list)
                    else set()
                )
                is_open_source_object = (
                    "object" in declared_types
                    and field.schema.get("additionalProperties") is True
                    and not isinstance(field.schema.get("properties"), Mapping)
                )
                if field.curve is None and (
                    "array" in declared_types or is_open_source_object
                ):
                    # Source arrays are retained in the immutable JSON evidence.  The
                    # source-v2 adapter intentionally does not project them as Catalog
                    # Attributes.  The same applies to explicitly open source objects;
                    # their contents remain immutable source evidence rather than a
                    # fabricated generic Attribute.
                    continue
                raise ConfigurableCatalogConflict(
                    f"installed table '{table_key}' is missing an exact binding for "
                    f"'{key or field.pointer}'"
                )
            binding_key = str(row["external_key"])
            attribute_id = row.get("aggregate_id")
            revision_id = row.get("revision_id")
            if not isinstance(attribute_id, UUID) or not isinstance(revision_id, UUID):
                raise ConfigurableCatalogConflict(
                    f"installed Attribute '{key}' has no immutable revision pin"
                )
            snapshot = self._schemas.get_attribute(
                context=context,
                decision=decision,
                attribute_id=attribute_id,
            )
            if snapshot.table_id != table_id:
                raise ConfigurableCatalogConflict(
                    f"installed Attribute '{binding_key}' is bound to the wrong Catalog Table"
                )
            if snapshot.current.record.revision_id != revision_id:
                exact = self._schemas.get_attribute_revision(
                    context=context,
                    decision=decision,
                    attribute_id=attribute_id,
                    revision_id=revision_id,
                )
                snapshot = AttributeSnapshot(snapshot.id, snapshot.table_id, exact)
            if snapshot.current.content.key != binding_key:
                raise ConfigurableCatalogConflict(
                    f"installed Attribute binding key drifted for '{binding_key}'"
                )
            values.append(
                JsonAttributeBinding(
                    json_pointer=field.pointer,
                    attribute=snapshot,
                    source_unit=field.source_unit,
                    quantity_semantics=field.quantity_semantics,
                    curve=field.curve,
                    section=field.section,
                    source_key=key if isinstance(key, str) else None,
                )
            )
        return tuple(values)

    @staticmethod
    def _registration_schema(
        source_schema: Mapping[str, Any],
        canonical_schema: Mapping[str, Any],
        *,
        source_file: str,
        wrapper: str,
    ) -> dict[str, Any]:
        """Retain source property names while carrying normalized link metadata.

        Source-v2 normalization unwraps the record and renames leaves to stable Catalog
        keys.  Registration still validates the user's original wrapper/property spelling,
        so use the immutable source schema as the shape and overlay only the canonical
        reference/curve annotations needed by the typed importer.
        """

        result = deepcopy(dict(source_schema))
        prefix = "/files/" + _escape_pointer(source_file)

        def visit(node: Any) -> None:
            if not isinstance(node, Mapping):
                if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
                    for child in node:
                        visit(child)
                return
            origin = node.get("x-source-origin")
            if isinstance(origin, Mapping) and origin.get("file") == source_file:
                pointer = origin.get("pointer")
                if isinstance(pointer, str) and pointer.startswith(prefix):
                    relative = pointer[len(prefix) :] or ""
                    try:
                        target = json_pointer(result, relative)
                    except (KeyError, IndexError, TypeError, ValueError):
                        target = None
                    if isinstance(target, dict):
                        if isinstance(node.get("x-reference"), Mapping):
                            target["x-reference"] = deepcopy(node["x-reference"])
                        else:
                            # A source reference without an approved Link Type is
                            # retained as a typed text field, never as a product link.
                            target.pop("x-reference", None)
                        if isinstance(node.get("x-curve"), Mapping):
                            target["x-curve"] = deepcopy(node["x-curve"])
            for child in node.values():
                visit(child)

        visit(canonical_schema)
        result["x-wrapper"] = wrapper
        return result

    async def _formats_for_application(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        application_row: Mapping[str, Any],
        bindings: Sequence[Mapping[str, Any]],
    ) -> tuple[InstalledJsonRecordFormat, ...]:
        artifact_id = application_row.get("source_artifact_id")
        application_id = application_row.get("id")
        if not isinstance(artifact_id, UUID) or not isinstance(application_id, UUID):
            raise ConfigurableCatalogConflict(
                "installed application has no immutable source identity"
            )
        artifact_record, raw = await self._artifacts.read_verified_bytes(
            context,
            decision,
            artifact_id,
            maximum_bytes=MAX_PACKAGE_ARCHIVE_BYTES,
        )
        files = self._source_files(raw, artifact_record.artifact.media_type)
        if files is None:
            return ()
        manifest_file, _manifest = self._manifest(files)
        manifest_sha256 = hashlib.sha256(files[manifest_file]).hexdigest()
        normalized = normalize_schema_definition_source(
            raw,
            media_type=artifact_record.artifact.media_type,
            organization_id=context.organization_id,
            project_id=context.project_id,
            source_classification=artifact_record.artifact.classification,
        )
        if normalized.canonical_bytes is None or normalized.source_format != "source-v2":
            raise ConfigurableCatalogConflict(
                "installed source-set Artifact did not produce a valid source-v2 application"
            )
        canonical = parse_strict_json(normalized.canonical_bytes, filename="schema-source-v2.json")
        if not isinstance(canonical, Mapping):
            raise ConfigurableCatalogConflict("installed source-v2 application is not an object")

        table_rows = {
            str(item["external_key"]): item
            for item in bindings
            if item.get("target_type") == "table"
        }
        link_rows = {
            str(item["external_key"]): item
            for item in bindings
            if item.get("target_type") == "link_type"
            and item.get("external_key") in self._APPROVED_LINK_KEYS
        }
        table_ids = {
            str(item["external_key"]): item["aggregate_id"]
            for item in bindings
            if item.get("target_type") == "table"
            and isinstance(item.get("aggregate_id"), UUID)
        }
        formats: list[InstalledJsonRecordFormat] = []
        for table_key, row in sorted(table_rows.items()):
            table_id = row.get("aggregate_id")
            table_revision_id = row.get("revision_id")
            source_file = row.get("source_file")
            source_file_sha256 = row.get("source_file_sha256")
            source_pointer = row.get("source_pointer")
            if (
                not isinstance(table_id, UUID)
                or not isinstance(table_revision_id, UUID)
                or not isinstance(source_file, str)
                or not isinstance(source_file_sha256, str)
                or not isinstance(source_pointer, str)
            ):
                raise ConfigurableCatalogConflict(
                    f"installed table '{table_key}' lacks exact source coordinates"
                )
            source_raw = files.get(posixpath.normpath(source_file))
            if source_raw is None or hashlib.sha256(source_raw).hexdigest() != source_file_sha256:
                raise ConfigurableCatalogConflict(
                    f"installed source file digest differs for table '{table_key}'"
                )
            table_revision = self._schemas.get_table_revision(
                context=context,
                decision=decision,
                table_id=table_id,
                revision_id=table_revision_id,
            )
            if table_revision.content.key != table_key:
                raise ConfigurableCatalogConflict(
                    f"installed Catalog Table binding key drifted for '{table_key}'"
                )
            entry = self._schema_entry(canonical, table_key)
            canonical_schema = entry["schema"]
            assert isinstance(canonical_schema, Mapping)
            source_schema = parse_strict_json(source_raw, filename=source_file)
            if not isinstance(source_schema, Mapping):
                raise ConfigurableCatalogConflict(
                    f"installed source file '{source_file}' is not a JSON schema object"
                )
            source_properties = source_schema.get("properties")
            wrapper: str | None = None
            if isinstance(source_properties, Mapping):
                wrapper = next(
                    (key for key in source_properties if isinstance(key, str)),
                    None,
                )
            if not isinstance(wrapper, str):
                raise ConfigurableCatalogConflict(
                    f"installed schema for table '{table_key}' has no wrapper"
                )
            schema = self._registration_schema(
                source_schema,
                canonical_schema,
                source_file=source_file,
                wrapper=wrapper,
            )
            schema_sha256 = source_file_sha256
            if len(schema_sha256) != 64:
                raise ConfigurableCatalogConflict(
                    f"installed schema digest is invalid for table '{table_key}'"
                )
            format_id = uuid5(
                NAMESPACE_URL,
                f"cmp-json-format:{application_id}:{table_id}",
            )
            format_revision_id = uuid5(
                NAMESPACE_URL,
                "cmp-json-format-revision:"
                f"{application_id}:{table_id}:{table_revision_id}:{source_file}:"
                f"{source_pointer}:{source_file_sha256}:{schema_sha256}",
            )
            formats.append(
                InstalledJsonRecordFormat(
                    format_id=format_id,
                    format_revision_id=format_revision_id,
                    format_key=f"{application_row['bundle_key']}:{table_key}",
                    application_id=application_id,
                    # Schema Bundle applications are immutable identities rather than a
                    # mutable revision stream; retain that exact identity in both contract pins.
                    application_revision_id=application_id,
                    schema_artifact_id=artifact_id,
                    schema_file=source_file,
                    schema_pointer=source_pointer,
                    schema_sha256=schema_sha256,
                    table_id=table_id,
                    table_revision_id=table_revision_id,
                    table_key=table_key,
                    table_source_file=source_file,
                    table_source_pointer=source_pointer,
                    table_source_sha256=source_file_sha256,
                    wrapper=wrapper,
                    schema=schema,
                    attributes=self._attribute_bindings(
                        context=context,
                        decision=decision,
                        table_id=table_id,
                        table_key=table_key,
                        schema=schema,
                        bindings=bindings,
                        source_file=source_file,
                    ),
                    link_type_revision_ids=tuple(
                        link_rows[key]["revision_id"]
                        for key in sorted(link_rows)
                        if isinstance(link_rows[key].get("revision_id"), UUID)
                    ),
                    unit_profile_revision_ids=(),
                    reference_table_ids=table_ids,
                    application_source_artifact_id=artifact_id,
                    application_source_file=manifest_file,
                    application_source_pointer="/",
                    application_source_sha256=manifest_sha256,
                )
            )
        return tuple(formats)

    async def list_formats(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[InstalledJsonRecordFormat, ...]:
        values: list[InstalledJsonRecordFormat] = []
        for application_row, bindings in self._current_applications(
            context=context,
            decision=decision,
        ):
            values.extend(
                await self._formats_for_application(
                    context=context,
                    decision=decision,
                    application_row=application_row,
                    bindings=bindings,
                )
            )
        return tuple(
            sorted(
                values,
                key=lambda item: (item.table_key, item.format_key, str(item.format_revision_id)),
            )
        )

    async def resolve_format(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        format_revision_id: UUID,
    ) -> InstalledJsonRecordFormat | None:
        for value in await self.list_formats(context, decision):
            if value.format_revision_id == format_revision_id:
                return value
        return None


__all__ = [
    "SqlAlchemyInstalledJsonRecordFormatResolver",
    "SqlAlchemyJsonRegistrationRepository",
    "json_record_registration_batch",
    "json_record_registration_batch_state_event",
    "json_record_registration_curve_artifact",
    "json_record_registration_preview",
    "record_json_source_provenance",
]
