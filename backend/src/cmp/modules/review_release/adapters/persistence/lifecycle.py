"""Initial lifecycle event/projection hook for newly created revisions.

T-06 records only the initial state.  Review transitions, separation of duties, and release
policy remain T-29/T-30 responsibilities.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from cmp.shared.domain.revisions import RevisionCreated

_metadata = sa.MetaData()

LIFECYCLE_EVENT = sa.Table(
    "lifecycle_event",
    _metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("organization_id", sa.Uuid()),
    sa.Column("project_id", sa.Uuid()),
    sa.Column("classification", sa.String()),
    sa.Column("aggregate_type", sa.String()),
    sa.Column("aggregate_id", sa.Uuid()),
    sa.Column("revision_id", sa.Uuid()),
    sa.Column("sequence_no", sa.BigInteger()),
    sa.Column("from_state", sa.String()),
    sa.Column("to_state", sa.String()),
    sa.Column("occurred_at", sa.DateTime(timezone=True)),
    sa.Column("actor_id", sa.Uuid()),
    sa.Column("reason", sa.String()),
    sa.Column("request_id", sa.Uuid()),
    sa.Column("trace_id", sa.String()),
    schema="governance",
)

LIFECYCLE_PROJECTION = sa.Table(
    "lifecycle_projection",
    _metadata,
    sa.Column("organization_id", sa.Uuid()),
    sa.Column("project_id", sa.Uuid()),
    sa.Column("classification", sa.String()),
    sa.Column("aggregate_type", sa.String()),
    sa.Column("aggregate_id", sa.Uuid()),
    sa.Column("revision_id", sa.Uuid()),
    sa.Column("lifecycle_state", sa.String()),
    sa.Column("sequence_no", sa.BigInteger()),
    sa.Column("last_event_id", sa.Uuid()),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    schema="governance",
)


class SqlInitialLifecycleHook:
    """Append the initial event and projection inside the revision transaction."""

    def __init__(self, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        event_id = self._id_factory()
        common = {
            "organization_id": revision.scope.organization_id,
            "project_id": revision.scope.project_id,
            "classification": revision.scope.classification,
            "aggregate_type": revision.aggregate_type,
            "aggregate_id": revision.aggregate_id,
            "revision_id": revision.revision_id,
        }
        session.execute(
            sa.insert(LIFECYCLE_EVENT).values(
                **common,
                id=event_id,
                sequence_no=1,
                from_state=None,
                to_state=event.lifecycle_state,
                occurred_at=revision.created_at,
                actor_id=revision.created_by,
                reason="revision-created",
                request_id=revision.request_id,
                trace_id=revision.trace_id,
            )
        )
        session.execute(
            sa.insert(LIFECYCLE_PROJECTION).values(
                **common,
                lifecycle_state=event.lifecycle_state,
                sequence_no=1,
                last_event_id=event_id,
                updated_at=revision.created_at,
            )
        )
