"""Reusable HTTP contract pieces for T-06 revision resources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cmp.shared.domain.revisions import RevisionRecord, RevisionRef

_ETAG = re.compile(r'^"revision:([1-9][0-9]*):sha256:([0-9a-f]{64})"$')


class InvalidRevisionETag(ValueError):
    """Raised for weak, wildcard, multiple, or malformed revision ETags."""


class RevisionPreconditionFailed(Exception):
    """HTTP-layer signal for a stale ``If-Match`` value."""

    def __init__(self, current: RevisionRef) -> None:
        self.current = current
        super().__init__(f"revision precondition failed; current revision is {current.revision_id}")


@dataclass(frozen=True, slots=True)
class RevisionETag:
    revision_no: int
    content_hash: str

    @classmethod
    def from_ref(cls, reference: RevisionRef) -> RevisionETag:
        return cls(reference.revision_no, reference.content_hash)

    @classmethod
    def parse(cls, value: str) -> RevisionETag:
        match = _ETAG.fullmatch(value.strip())
        if match is None:
            raise InvalidRevisionETag(
                'If-Match must contain one strong "revision:<n>:sha256:<hex>" ETag'
            )
        return cls(int(match.group(1)), match.group(2))

    def __post_init__(self) -> None:
        # RevisionRef owns the shared validation rules.
        RevisionRef(UUID(int=0), self.revision_no, self.content_hash)

    def __str__(self) -> str:
        return f'"revision:{self.revision_no}:sha256:{self.content_hash}"'


def require_matching_if_match(value: str | None, current: RevisionRef) -> UUID:
    """Validate ``If-Match`` and return the concrete current revision UUID for CAS."""

    if value is None:
        raise InvalidRevisionETag("If-Match is required for revision writes")
    supplied = RevisionETag.parse(value)
    if supplied != RevisionETag.from_ref(current):
        raise RevisionPreconditionFailed(current)
    return current.revision_id


class RevisionMetadataResponse(BaseModel):
    """Content-free common response metadata; typed resources add their own content schema."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    aggregate_id: UUID
    revision_no: int = Field(ge=1)
    based_on_revision_id: UUID | None
    schema_id: str = Field(min_length=1, max_length=255)
    schema_version: str = Field(min_length=1, max_length=64)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    created_by: UUID
    change_reason: str = Field(min_length=1, max_length=2000)
    organization_id: UUID
    project_id: UUID
    classification: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    lifecycle_state: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")

    @classmethod
    def from_record(
        cls, record: RevisionRecord, lifecycle_state: str
    ) -> RevisionMetadataResponse:
        return cls(
            id=record.revision_id,
            aggregate_id=record.aggregate_id,
            revision_no=record.revision_no,
            based_on_revision_id=record.based_on_revision_id,
            schema_id=record.schema_id,
            schema_version=record.schema_version,
            content_hash=record.content_hash,
            created_at=record.created_at,
            created_by=record.created_by,
            change_reason=record.change_reason,
            organization_id=record.scope.organization_id,
            project_id=record.scope.project_id,
            classification=record.scope.classification,
            lifecycle_state=lifecycle_state,
        )


def revision_openapi_components() -> dict[str, Any]:
    """Return runtime OpenAPI components mirrored by ``contracts/http/openapi.yaml``."""

    return {
        "schemas": {
            "RevisionMetadata": RevisionMetadataResponse.model_json_schema(
                ref_template="#/components/schemas/{model}"
            )
        },
        "headers": {
            "RevisionETag": {
                "description": "Strong ETag for one concrete immutable revision.",
                "required": True,
                "schema": {
                    "type": "string",
                    "pattern": r'^"revision:[1-9][0-9]*:sha256:[0-9a-f]{64}"$',
                },
            }
        },
        "parameters": {
            "IfMatchRevision": {
                "name": "If-Match",
                "in": "header",
                "required": True,
                "description": "Strong ETag of the expected current revision.",
                "schema": {
                    "type": "string",
                    "pattern": r'^"revision:[1-9][0-9]*:sha256:[0-9a-f]{64}"$',
                },
            }
        },
    }
