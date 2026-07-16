"""Append deterministic synthetic Material revisions for an isolated T-47 scale gate."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from time import perf_counter
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid5

import psycopg

from cmp.modules.catalog.domain.model import (
    MaterialClass,
    MaterialContent,
    material_canonical,
)
from cmp.shared.domain.revisions import content_sha256

_DEMO_ORGANIZATION_ID = UUID("d0000000-0000-4000-8000-000000000001")
_DEMO_PROJECT_ID = UUID("d0000000-0000-4000-8000-000000000002")
_NAMESPACE = UUID("f4700000-0000-4000-8000-000000000001")
_MINIMUM_TARGET = 10_000


class PerformanceFixtureError(RuntimeError):
    """The scale fixture target or schema is unsafe."""


def _normalized_dsn(value: str, *, allow_non_loopback: bool) -> str:
    normalized = value.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.hostname is None:
        raise PerformanceFixtureError("fixture DSN must be a PostgreSQL URL")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and not allow_non_loopback:
        raise PerformanceFixtureError(
            "non-loopback fixture targets require --allow-non-loopback-isolated-environment"
        )
    database = unquote(parsed.path.lstrip("/"))
    if not database or database in {"postgres", "template0", "template1"}:
        raise PerformanceFixtureError("fixture DSN must name an isolated application database")
    return normalized


def _fixture_rows(
    *,
    organization_id: UUID,
    project_id: UUID,
    start: int,
    count: int,
    created_at: datetime,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    actor_id = uuid5(_NAMESPACE, "actor")
    identities: list[dict[str, object]] = []
    revisions: list[dict[str, object]] = []
    for ordinal in range(start, start + count):
        material_id = uuid5(_NAMESPACE, f"material:{ordinal}")
        revision_id = uuid5(_NAMESPACE, f"material:{ordinal}:revision:1")
        request_id = uuid5(_NAMESPACE, f"material:{ordinal}:request")
        content = MaterialContent(
            name=f"ZZ Performance Material {ordinal:05d}",
            material_code=f"PERF-{ordinal:05d}",
            material_family="synthetic-benchmark",
            description="Synthetic T-47 performance fixture; not material data.",
            material_class=MaterialClass.METAL,
        )
        common = {
            "organization_id": organization_id,
            "project_id": project_id,
            "classification": "internal",
        }
        identities.append(
            {
                **common,
                "id": material_id,
                "current_revision_id": revision_id,
                "created_at": created_at,
                "created_by": actor_id,
                "updated_at": created_at,
            }
        )
        revisions.append(
            {
                **common,
                "id": revision_id,
                "aggregate_id": material_id,
                "revision_no": 1,
                "based_on_revision_id": None,
                "schema_id": "urn:cmp:catalog:material:2.0.0",
                "schema_version": "2.0.0",
                "content_hash": content_sha256(material_canonical(content)),
                "created_at": created_at,
                "created_by": actor_id,
                "change_reason": "append isolated T-47 production-scale fixture",
                "request_id": request_id,
                "trace_id": f"t47-performance-fixture-{ordinal}",
                **material_canonical(content),
            }
        )
    return identities, revisions


_INSERT_IDENTITY = """
INSERT INTO catalog.material
  (id, organization_id, project_id, classification, current_revision_id,
   created_at, created_by, updated_at)
VALUES
  (%(id)s, %(organization_id)s, %(project_id)s, %(classification)s,
   %(current_revision_id)s, %(created_at)s, %(created_by)s, %(updated_at)s)
ON CONFLICT (organization_id, project_id, id) DO NOTHING
"""

_INSERT_REVISION = """
INSERT INTO catalog.material_revision
  (id, aggregate_id, organization_id, project_id, classification, revision_no,
   based_on_revision_id, schema_id, schema_version, content_hash, created_at,
   created_by, change_reason, request_id, trace_id, name, material_code,
   material_family, description, material_class)
VALUES
  (%(id)s, %(aggregate_id)s, %(organization_id)s, %(project_id)s,
   %(classification)s, %(revision_no)s, %(based_on_revision_id)s, %(schema_id)s,
   %(schema_version)s, %(content_hash)s, %(created_at)s, %(created_by)s,
   %(change_reason)s, %(request_id)s, %(trace_id)s, %(name)s, %(material_code)s,
   %(material_family)s, %(description)s, %(material_class)s)
ON CONFLICT (organization_id, project_id, id) DO NOTHING
"""


def seed_material_scale(
    dsn: str,
    *,
    organization_id: UUID,
    project_id: UUID,
    target_count: int,
    batch_size: int = 1000,
    allow_non_loopback: bool = False,
) -> dict[str, object]:
    if target_count < _MINIMUM_TARGET:
        raise PerformanceFixtureError("production-scale fixture requires at least 10,000 Materials")
    if not 100 <= batch_size <= 5000:
        raise PerformanceFixtureError("fixture batch size must be between 100 and 5000")
    normalized = _normalized_dsn(dsn, allow_non_loopback=allow_non_loopback)
    started = perf_counter()
    inserted = 0
    with psycopg.connect(normalized) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema='exporting' AND table_name='bulk_export_job'
                    AND column_name='lease_token'
                )
                """
            )
            if cursor.fetchone() != (True,):
                raise PerformanceFixtureError("fixture database is older than migration 058")
            cursor.execute(
                """
                SELECT count(*) FROM catalog.material
                WHERE organization_id=%s AND project_id=%s
                """,
                (organization_id, project_id),
            )
            initial_row = cursor.fetchone()
            if initial_row is None:
                raise PerformanceFixtureError("fixture Material count query returned no row")
            initial_count = int(initial_row[0])
            next_ordinal = 1
            current_count = initial_count
            while current_count < target_count:
                current_batch = min(batch_size, target_count - current_count)
                identities, revisions = _fixture_rows(
                    organization_id=organization_id,
                    project_id=project_id,
                    start=next_ordinal,
                    count=current_batch,
                    created_at=datetime.now(UTC),
                )
                cursor.execute("SET CONSTRAINTS ALL DEFERRED")
                cursor.executemany(_INSERT_IDENTITY, identities)
                cursor.executemany(_INSERT_REVISION, revisions)
                next_ordinal += current_batch
                cursor.execute(
                    """
                    SELECT count(*) FROM catalog.material
                    WHERE organization_id=%s AND project_id=%s
                    """,
                    (organization_id, project_id),
                )
                observed_row = cursor.fetchone()
                if observed_row is None:
                    raise PerformanceFixtureError("fixture Material count query returned no row")
                observed_count = int(observed_row[0])
                inserted += observed_count - current_count
                current_count = observed_count
            cursor.execute(
                """
                SELECT count(*) FROM catalog.material identity
                JOIN catalog.material_revision revision
                  ON revision.organization_id=identity.organization_id
                 AND revision.project_id=identity.project_id
                 AND revision.aggregate_id=identity.id
                 AND revision.id=identity.current_revision_id
                WHERE identity.organization_id=%s AND identity.project_id=%s
                """,
                (organization_id, project_id),
            )
            final_row = cursor.fetchone()
            if final_row is None:
                raise PerformanceFixtureError("fixture exact-revision query returned no row")
            final_count = int(final_row[0])
    if final_count < target_count:
        raise PerformanceFixtureError(
            "fixture did not reach its required exact-revision cardinality"
        )
    return {
        "duration_seconds": round(perf_counter() - started, 6),
        "final_exact_revision_count": final_count,
        "initial_identity_count": initial_count,
        "inserted_identity_revision_pairs": inserted,
        "organization_id": str(organization_id),
        "project_id": str(project_id),
        "synthetic_only": True,
        "target_count": target_count,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-dsn", required=True)
    parser.add_argument("--organization-id", type=UUID, default=_DEMO_ORGANIZATION_ID)
    parser.add_argument("--project-id", type=UUID, default=_DEMO_PROJECT_ID)
    parser.add_argument("--target-count", type=int, default=_MINIMUM_TARGET)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--allow-non-loopback-isolated-environment", action="store_true")
    parser.add_argument("--acknowledge-immutable-synthetic-write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if not args.acknowledge_immutable_synthetic_write:
        raise PerformanceFixtureError(
            "fixture appends immutable synthetic revisions; pass the explicit acknowledgement"
        )
    report = seed_material_scale(
        args.postgres_dsn,
        organization_id=args.organization_id,
        project_id=args.project_id,
        target_count=args.target_count,
        batch_size=args.batch_size,
        allow_non_loopback=args.allow_non_loopback_isolated_environment,
    )
    print(json.dumps(report, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
