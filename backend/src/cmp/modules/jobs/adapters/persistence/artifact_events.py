"""Map a T-10 Artifact commit to one atomic transport-neutral outbox event."""

from __future__ import annotations

from sqlalchemy.orm import Session

from cmp.modules.artifacts.application.content import FinalizedArtifact
from cmp.modules.jobs.adapters.contracts.events_jsonschema import (
    JsonSchemaEventContractValidator,
)
from cmp.modules.jobs.adapters.persistence.events import SqlAlchemyOutboxWriter
from cmp.modules.jobs.domain.events import CloudEventDraft


class SqlArtifactAvailableOutboxHook:
    def __init__(self, *, writer: SqlAlchemyOutboxWriter | None = None) -> None:
        self._writer = writer or SqlAlchemyOutboxWriter()
        self._validator = JsonSchemaEventContractValidator()

    def __call__(self, session: Session, result: FinalizedArtifact) -> None:
        if result.replayed:
            return
        pending = result.pending
        artifact = result.record.artifact
        appended = self._writer.append(
            session,
            CloudEventDraft(
                organization_id=artifact.organization_id,
                project_id=artifact.project_id,
                classification=artifact.classification,
                aggregate_type="artifact.artifact",
                aggregate_id=artifact.id,
                event_type="io.cmp.artifact.available.v1",
                source="urn:cmp:module:artifacts",
                subject=f"artifacts/{artifact.id}",
                data_schema="urn:cmp:schema:event:artifact-available:1.0.0",
                data={
                    "artifact_id": str(artifact.id),
                    "pending_artifact_id": str(pending.id),
                    "artifact_kind": artifact.artifact_kind.value,
                    "artifact_role": artifact.artifact_role,
                    "schema_ref": artifact.schema_ref,
                    "media_type": artifact.media_type,
                    "size_bytes": artifact.size_bytes,
                    "sha256": artifact.sha256,
                    "source_raw_asset_id": (
                        str(artifact.source_raw_asset_id)
                        if artifact.source_raw_asset_id is not None
                        else None
                    ),
                    "created_at": artifact.created_at.isoformat().replace("+00:00", "Z"),
                },
                occurred_at=artifact.created_at,
                recorded_by=artifact.created_by,
                request_id=pending.request_id,
                trace_id=pending.trace_id,
                deduplication_key=f"artifact.available:{artifact.id}",
            ),
            recorded_at=artifact.created_at,
        )
        self._validator.validate(appended.event)


__all__ = ["SqlArtifactAvailableOutboxHook"]
