from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.artifacts.adapters.persistence.content import (
    SqlAlchemyArtifactRepository,
)
from cmp.modules.artifacts.adapters.persistence.maintenance import (
    SqlAlchemyArtifactMaintenanceRepository,
)
from cmp.modules.artifacts.adapters.persistence.uploads import (
    SqlAlchemyUploadRepository,
)
from cmp.modules.artifacts.adapters.storage.filesystem import (
    FilesystemMultipartObjectStore,
)
from cmp.modules.artifacts.application.content import (
    ArtifactRepository,
    ArtifactService,
    ArtifactTransferCodec,
    FinalizedArtifact,
    PrepareArtifact,
    ReconciliationResult,
)
from cmp.modules.artifacts.application.maintenance import (
    ArtifactMaintenanceCoordinator,
)
from cmp.modules.artifacts.application.uploads import (
    CompleteUpload,
    CreateUpload,
    CreateUploadResult,
    RecordUploadPart,
    UploadCapabilityCodec,
    UploadPolicy,
    UploadService,
)
from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactIntegrityError,
    ArtifactKind,
    ArtifactNotFound,
    IntegrityStatus,
    StoredObject,
    content_object_key,
)
from cmp.modules.artifacts.domain.uploads import ObjectStoreError
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.jobs.adapters.persistence.artifact_events import (
    SqlArtifactAvailableOutboxHook,
)
from cmp.modules.jobs.adapters.persistence.events import (
    SqlAlchemyInboxDeduplicator,
    SqlAlchemyOutboxRepository,
    SqlAlchemyOutboxWriter,
)
from cmp.modules.jobs.domain.events import (
    CloudEventDraft,
    EventConflict,
    EventLeaseLost,
    InboxOutcome,
    InboxReceipt,
)
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 7, 12, 17, 0, tzinfo=UTC)
ORG = UUID("8c000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("8c000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("8c000000-0000-4000-8000-000000000003")
ACTOR = UUID("8c000000-0000-4000-8000-000000000004")
OTHER_ACTOR = UUID("8c000000-0000-4000-8000-000000000005")
TRACE = "00-0000000000000000000000000000008c-000000000000008c-01"
UPLOAD_SECRET = b"t10-upload-capability-secret-at-least-32-bytes"
TRANSFER_SECRET = b"t10-transfer-capability-secret-at-least-32-bytes"


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    sessions: sessionmaker[Session]
    rls: SqlAlchemyRlsContext
    repository: SqlAlchemyArtifactRepository
    artifacts: ArtifactService
    uploads: UploadService
    store: FilesystemMultipartObjectStore


def _psycopg_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return url


def _alembic_config(database_url: URL) -> Config:
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    configuration.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return configuration


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t10_{uuid4().hex}"
    app_role = f"cmp_t10_app_{uuid4().hex}"
    cluster_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        connection.exec_driver_sql(
            f'CREATE ROLE "{app_role}" LOGIN NOSUPERUSER NOCREATEDB '
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: Engine | None = None
    with tempfile.TemporaryDirectory(prefix="cmp-t10-object-store-") as temporary:
        try:
            command.upgrade(_alembic_config(database_url), "head")
            with admin_engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO identity.principal "
                        "(id, principal_type, display_name, active, created_at, updated_at) "
                        "VALUES (:id, 'user', 'T10 Artifact User', true, :now, :now), "
                        "(:other_id, 'user', 'T10 Other User', true, :now, :now)"
                    ),
                    {
                        "id": ACTOR,
                        "other_id": OTHER_ACTOR,
                        "now": NOW - timedelta(days=1),
                    },
                )
                connection.exec_driver_sql(
                    "GRANT USAGE ON SCHEMA identity, revisioning, access_control, "
                    f'governance, artifact, events TO "{app_role}"'
                )
                connection.exec_driver_sql(
                    f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA artifact TO "{app_role}"'
                )
                connection.exec_driver_sql(
                    f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA events TO "{app_role}"'
                )
                connection.exec_driver_sql(
                    "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA "
                    f'access_control, revisioning, artifact TO "{app_role}"'
                )
            app_engine = sa.create_engine(
                database_url.set(username=app_role, password=None), pool_pre_ping=True
            )
            sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
            rls = SqlAlchemyRlsContext()
            with sessions() as session, session.begin():
                rls.assert_application_role(session)
            artifact_repository = SqlAlchemyArtifactRepository(
                session_factory=sessions,
                rls_context=rls,
                available_hooks=(SqlArtifactAvailableOutboxHook(),),
            )
            store = FilesystemMultipartObjectStore(Path(temporary))
            artifacts = ArtifactService(
                repository=artifact_repository,
                object_store=store,
                transfers=ArtifactTransferCodec(TRANSFER_SECRET, clock=lambda: NOW),
                clock=lambda: NOW,
            )
            uploads = UploadService(
                repository=SqlAlchemyUploadRepository(
                    session_factory=sessions,
                    rls_context=rls,
                ),
                object_store=store,
                capabilities=UploadCapabilityCodec(UPLOAD_SECRET, clock=lambda: NOW),
                raw_asset_finalizer=artifacts,
                policy=UploadPolicy(
                    max_object_bytes=2 * 1024 * 1024,
                    default_part_bytes=64 * 1024,
                    min_part_bytes=64 * 1024,
                    max_part_bytes=512 * 1024,
                    session_ttl=timedelta(hours=1),
                ),
                clock=lambda: NOW,
            )
            yield PostgresHarness(
                admin_engine,
                sessions,
                rls,
                artifact_repository,
                artifacts,
                uploads,
                store,
            )
        finally:
            if app_engine is not None:
                app_engine.dispose()
            command.downgrade(_alembic_config(database_url), "base")
            admin_engine.dispose()
            with cluster_engine.connect() as connection:
                connection.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": database_name},
                )
                connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
                connection.exec_driver_sql(f'DROP ROLE "{app_role}"')
            cluster_engine.dispose()


def _context(
    *,
    project_id: UUID = PROJECT_A,
    actor_id: UUID = ACTOR,
) -> SecurityContext:
    return SecurityContext(
        principal=Principal(actor_id, PrincipalType.USER, "Artifact User", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(actor_id),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    permission: Permission,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(Role.TEST_ENGINEER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


async def _chunks(value: bytes, size: int = 16 * 1024) -> AsyncIterator[bytes]:
    for offset in range(0, len(value), size):
        await asyncio.sleep(0)
        yield value[offset : offset + size]


async def _upload_raw(
    harness: PostgresHarness,
    context: SecurityContext,
    payload: bytes,
    idempotency_key: str,
) -> tuple[CreateUploadResult, UUID, UUID]:
    created = await harness.uploads.create(
        context,
        _decision(context, Permission.ARTIFACT_WRITE),
        CreateUpload(
            classification=DataClassification.INTERNAL,
            original_filename="raw.bin",
            media_type="application/octet-stream",
            expected_size_bytes=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            idempotency_key=idempotency_key,
            part_size_bytes=64 * 1024,
        ),
    )
    for part_number in range(1, created.session.expected_part_count + 1):
        start = (part_number - 1) * created.session.part_size_bytes
        end = min(start + created.session.part_size_bytes, len(payload))
        await harness.uploads.record_part(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            RecordUploadPart(created.session.id, part_number, created.capability),
            _chunks(payload[start:end]),
        )
    completed = await harness.uploads.complete(
        context,
        _decision(context, Permission.ARTIFACT_WRITE),
        CompleteUpload(created.session.id, created.capability),
    )
    assert completed.available_artifact_id is not None
    return created, completed.raw_asset.id, completed.available_artifact_id


async def _stage_derived(
    service: ArtifactService,
    store: FilesystemMultipartObjectStore,
    context: SecurityContext,
    payload: bytes,
    idempotency_key: str,
    *,
    schema_ref: str = "urn:cmp:schema:generic-binary:1",
    commit_hook: Callable[[Session, FinalizedArtifact], None] | None = None,
) -> FinalizedArtifact:
    staging_key = f"staging/{ORG}/{context.project_id}/{uuid4()}.derived"
    await store.write_for_testing(staging_key, payload)
    return await service.finalize_staged(
        context,
        _decision(context, Permission.ARTIFACT_WRITE),
        PrepareArtifact(
            classification=DataClassification.INTERNAL,
            artifact_kind=ArtifactKind.DERIVED,
            artifact_role="generic.output",
            schema_ref=schema_ref,
            media_type="application/octet-stream",
            expected_size_bytes=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            staging_object_key=staging_key,
            idempotency_key=idempotency_key,
        ),
        commit_hook=commit_hook,
    )


def test_raw_upload_promotes_idempotently_and_artifact_facts_are_immutable(
    postgres: PostgresHarness,
) -> None:
    payload = (b"raw-to-final-content-" * 6000)[:120_000]
    context = _context()

    async def run() -> tuple[CreateUploadResult, UUID, UUID]:
        created, raw_id, artifact_id = await _upload_raw(
            postgres, context, payload, "t10-raw-finalize"
        )
        replay = await postgres.uploads.complete(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            CompleteUpload(created.session.id, created.capability),
        )
        assert replay.available_artifact_id == artifact_id
        record = postgres.artifacts.get_artifact(
            context,
            _decision(context, Permission.ARTIFACT_READ),
            artifact_id,
        )
        assert record.artifact.source_raw_asset_id == raw_id
        assert record.artifact.artifact_kind is ArtifactKind.RAW
        assert record.integrity_status is IntegrityStatus.VERIFIED
        assert await postgres.store.inspect(created.session.staging_object_key) is None
        final = await postgres.store.inspect(record.artifact.storage_key)
        assert final is not None and final.sha256 == hashlib.sha256(payload).hexdigest()

        grant = await postgres.artifacts.issue_download(
            context,
            _decision(context, Permission.ARTIFACT_READ),
            artifact_id,
        )
        download = await postgres.artifacts.open_download(
            context,
            _decision(context, Permission.ARTIFACT_READ),
            artifact_id,
            grant.token,
        )
        received = bytearray()
        async for chunk in download.chunks:
            received.extend(chunk)
        assert bytes(received) == payload
        other_context = _context(actor_id=OTHER_ACTOR)
        with pytest.raises(ArtifactAccessDenied):
            await postgres.artifacts.open_download(
                other_context,
                _decision(other_context, Permission.ARTIFACT_READ),
                artifact_id,
                grant.token,
            )
        second_context = _context(actor_id=OTHER_ACTOR)
        _, duplicate_raw_id, duplicate_artifact_id = await _upload_raw(
            postgres,
            second_context,
            payload,
            "t10-raw-finalize-other-actor",
        )
        assert duplicate_raw_id == raw_id
        assert duplicate_artifact_id == artifact_id
        return created, raw_id, artifact_id

    created, _, artifact_id = asyncio.run(run())
    with postgres.admin_engine.connect() as connection:
        event = (
            connection.execute(
                sa.text(
                    "SELECT event_type, sequence_no, data FROM events.outbox_event "
                    "WHERE aggregate_id = :artifact_id"
                ),
                {"artifact_id": artifact_id},
            )
            .mappings()
            .one()
        )
        delivery_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM events.outbox_delivery WHERE event_id = ("
                "SELECT id FROM events.outbox_event WHERE aggregate_id = :artifact_id)"
            ),
            {"artifact_id": artifact_id},
        )
    assert event["event_type"] == "io.cmp.artifact.available.v1"
    assert event["sequence_no"] == 1
    assert event["data"]["artifact_id"] == str(artifact_id)
    assert "storage_key" not in event["data"]
    assert delivery_count == 1
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text("UPDATE artifact.artifact SET media_type = 'text/plain' WHERE id = :id"),
                {"id": artifact_id},
            )
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE artifact.integrity_observation SET status = 'missing' "
                    "WHERE artifact_id = :id"
                ),
                {"id": artifact_id},
            )
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE artifact.artifact_pending SET terminal_at = terminal_at "
                    "+ interval '1 second' WHERE id = (SELECT source_pending_id "
                    "FROM artifact.artifact WHERE id = :id)"
                ),
                {"id": artifact_id},
            )
    other_project_context = _context(project_id=PROJECT_B)
    with pytest.raises(ArtifactNotFound):
        postgres.artifacts.get_artifact(
            other_project_context,
            _decision(other_project_context, Permission.ARTIFACT_READ),
            artifact_id,
        )
    assert created.session.id.int != 0


def test_outbox_sequence_crash_reclaim_poison_and_inbox_dedup(
    postgres: PostgresHarness,
) -> None:
    context = _context(project_id=PROJECT_B)
    aggregate_id = uuid4()
    writer = SqlAlchemyOutboxWriter()

    def draft(sequence: int) -> CloudEventDraft:
        return CloudEventDraft(
            organization_id=ORG,
            project_id=PROJECT_B,
            classification=DataClassification.INTERNAL,
            aggregate_type="test.aggregate",
            aggregate_id=aggregate_id,
            event_type="io.cmp.test.sequence.v1",
            source="urn:cmp:test:outbox",
            subject=f"test/{aggregate_id}",
            data_schema="urn:cmp:schema:event:test-sequence:1.0.0",
            data={"value": sequence},
            occurred_at=NOW + timedelta(seconds=sequence),
            recorded_by=ACTOR,
            request_id=context.request_id,
            trace_id=context.trace_id,
            deduplication_key=f"test.sequence:{aggregate_id}:{sequence}",
        )

    with postgres.sessions() as session, session.begin():
        postgres.rls.bind_authorization(
            session,
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
        )
        first = writer.append(
            session,
            draft(1),
            recorded_at=NOW + timedelta(seconds=1),
        )
        replay = writer.append(
            session,
            draft(1),
            recorded_at=NOW + timedelta(seconds=1),
        )
        second = writer.append(
            session,
            draft(2),
            recorded_at=NOW + timedelta(seconds=2),
        )
    assert not first.replayed and replay.replayed
    assert first.event.id == replay.event.id
    assert (first.event.sequence_no, second.event.sequence_no) == (1, 2)
    with postgres.sessions() as session, session.begin():
        postgres.rls.bind_authorization(
            session,
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
        )
        with pytest.raises(EventConflict):
            writer.append(
                session,
                replace(draft(1), data={"value": "substituted"}),
                recorded_at=NOW + timedelta(seconds=1),
            )

    other_project_context = _context(project_id=PROJECT_A)
    with postgres.sessions() as session, session.begin():
        postgres.rls.bind_authorization(
            session,
            other_project_context,
            _decision(other_project_context, Permission.JOB_EXECUTE),
        )
        hidden = session.scalar(
            sa.text("SELECT id FROM events.outbox_event WHERE id = :event_id"),
            {"event_id": first.event.id},
        )
    assert hidden is None

    repository = SqlAlchemyOutboxRepository(
        session_factory=postgres.sessions,
        rls_context=postgres.rls,
    )
    execute = _decision(context, Permission.JOB_EXECUTE)
    claimed = repository.claim(
        context=context,
        decision=execute,
        limit=10,
        lease_duration=timedelta(seconds=30),
        now=NOW + timedelta(seconds=3),
    )
    assert [item.event.id for item in claimed] == [first.event.id]
    assert (
        repository.claim(
            context=context,
            decision=execute,
            limit=10,
            lease_duration=timedelta(seconds=30),
            now=NOW + timedelta(seconds=20),
        )
        == ()
    )

    reclaimed = repository.claim(
        context=context,
        decision=execute,
        limit=10,
        lease_duration=timedelta(seconds=30),
        now=NOW + timedelta(seconds=34),
    )
    assert len(reclaimed) == 1
    assert reclaimed[0].event.id == first.event.id
    assert reclaimed[0].lease_token != claimed[0].lease_token
    assert reclaimed[0].attempt_count == 2
    with pytest.raises(EventLeaseLost):
        repository.published(
            context=context,
            decision=execute,
            event_id=first.event.id,
            lease_token=claimed[0].lease_token,
            published_at=NOW + timedelta(seconds=35),
        )
    repository.published(
        context=context,
        decision=execute,
        event_id=first.event.id,
        lease_token=reclaimed[0].lease_token,
        published_at=NOW + timedelta(seconds=35),
    )

    second_claim = repository.claim(
        context=context,
        decision=execute,
        limit=10,
        lease_duration=timedelta(seconds=30),
        now=NOW + timedelta(seconds=36),
    )
    assert [item.event.id for item in second_claim] == [second.event.id]
    assert repository.failed(
        context=context,
        decision=execute,
        event_id=second.event.id,
        lease_token=second_claim[0].lease_token,
        failure_code="poison_fixture",
        retry_at=NOW + timedelta(seconds=40),
        failed_at=NOW + timedelta(seconds=37),
        maximum_attempts=1,
    )
    with postgres.sessions() as session, session.begin():
        postgres.rls.bind_authorization(
            session,
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
        )
        writer.append(
            session,
            draft(3),
            recorded_at=NOW + timedelta(seconds=38),
        )
    assert (
        repository.claim(
            context=context,
            decision=execute,
            limit=10,
            lease_duration=timedelta(seconds=30),
            now=NOW + timedelta(seconds=50),
        )
        == ()
    )

    receipt = InboxReceipt(
        consumer_name="io.cmp.test.consumer",
        event_id=first.event.id,
        event_type=first.event.draft.event_type,
        data_sha256=first.event.draft.data_sha256,
        outcome=InboxOutcome.COMPLETED,
        side_effect_key=f"effect:{first.event.id}",
        received_at=NOW + timedelta(seconds=35),
        processed_at=NOW + timedelta(seconds=36),
    )
    inserted: list[bool] = []
    for _ in range(2):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, execute)
            inserted.append(
                SqlAlchemyInboxDeduplicator.record(
                    session,
                    context=context,
                    classification=DataClassification.INTERNAL.value,
                    receipt=receipt,
                )
            )
    assert inserted == [True, False]
    with postgres.admin_engine.connect() as connection:
        inbox_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM events.consumer_inbox "
                "WHERE consumer_name = :consumer AND event_id = :event_id"
            ),
            {"consumer": receipt.consumer_name, "event_id": receipt.event_id},
        )
    assert inbox_count == 1


def test_artifact_outbox_and_custom_commit_hook_roll_back_together_when_hook_fails(
    postgres: PostgresHarness,
) -> None:
    def fail_after_outbox(session: Session, result: FinalizedArtifact) -> None:
        del session, result
        raise RuntimeError("synthetic post-outbox transaction failure")

    repository = SqlAlchemyArtifactRepository(
        session_factory=postgres.sessions,
        rls_context=postgres.rls,
        available_hooks=(SqlArtifactAvailableOutboxHook(),),
    )
    service = ArtifactService(
        repository=repository,
        object_store=postgres.store,
        transfers=ArtifactTransferCodec(TRANSFER_SECRET, clock=lambda: NOW),
        clock=lambda: NOW,
    )
    idempotency_key = f"t16-rollback-{uuid4()}"
    with pytest.raises(RuntimeError, match="post-outbox"):
        asyncio.run(
            _stage_derived(
                service,
                postgres.store,
                _context(),
                b"atomic-artifact-and-outbox",
                idempotency_key,
                commit_hook=fail_after_outbox,
            )
        )

    with postgres.admin_engine.connect() as connection:
        pending = (
            connection.execute(
                sa.text(
                    "SELECT reserved_artifact_id, state FROM artifact.artifact_pending "
                    "WHERE idempotency_key = :idempotency_key"
                ),
                {"idempotency_key": idempotency_key},
            )
            .mappings()
            .one()
        )
        artifact_count = connection.scalar(
            sa.text("SELECT count(*) FROM artifact.artifact WHERE id = :artifact_id"),
            {"artifact_id": pending["reserved_artifact_id"]},
        )
        event_count = connection.scalar(
            sa.text("SELECT count(*) FROM events.outbox_event WHERE aggregate_id = :artifact_id"),
            {"artifact_id": pending["reserved_artifact_id"]},
        )
    assert pending["state"] == "promoting"
    assert artifact_count == 0
    assert event_count == 0


def test_durable_reconciliation_reclaims_crash_and_cleans_only_staging(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    decision = _decision(context, Permission.ARTIFACT_WRITE)
    finalized = asyncio.run(
        _stage_derived(
            postgres.artifacts,
            postgres.store,
            context,
            b"durable-reconciliation-target",
            f"t16-maintenance-{uuid4()}",
        )
    )
    staging_key = finalized.pending.staging_object_key
    asyncio.run(postgres.store.write_for_testing(staging_key, b"leftover-staging"))
    repository = SqlAlchemyArtifactMaintenanceRepository(
        session_factory=postgres.sessions,
        rls_context=postgres.rls,
    )
    repository.ensure_schedule(
        context=context,
        decision=decision,
        classification=DataClassification.INTERNAL,
        interval=timedelta(minutes=1),
        retention=timedelta(hours=1),
        now=NOW,
    )

    async def reconcile() -> ReconciliationResult:
        return await postgres.artifacts.reconcile(context, decision, limit=100)

    coordinator = ArtifactMaintenanceCoordinator(
        repository=repository,
        reconciler=reconcile,
        object_store=postgres.store,
        clock=lambda: NOW + timedelta(hours=2),
    )
    result = asyncio.run(coordinator.run_once(context, decision))

    assert result.status == "succeeded"
    assert result.staging_cleaned >= 1
    assert asyncio.run(postgres.store.inspect(staging_key)) is None
    assert asyncio.run(postgres.store.inspect(finalized.record.artifact.storage_key)) is not None
    with postgres.admin_engine.connect() as connection:
        cleanup_count = connection.scalar(
            sa.text(
                "SELECT count(*) FROM artifact.staging_cleanup "
                "WHERE pending_artifact_id = :pending_id"
            ),
            {"pending_id": finalized.pending.id},
        )
    assert cleanup_count == 1

    other_context = _context(project_id=PROJECT_B)
    other_decision = _decision(other_context, Permission.ARTIFACT_WRITE)
    repository.ensure_schedule(
        context=other_context,
        decision=other_decision,
        classification=DataClassification.INTERNAL,
        interval=timedelta(minutes=1),
        retention=timedelta(hours=1),
        now=NOW,
    )
    first = repository.claim(
        context=other_context,
        decision=other_decision,
        lease_duration=timedelta(minutes=5),
        now=NOW,
    )
    assert first is not None
    assert (
        repository.claim(
            context=other_context,
            decision=other_decision,
            lease_duration=timedelta(minutes=5),
            now=NOW + timedelta(minutes=1),
        )
        is None
    )
    replacement = repository.claim(
        context=other_context,
        decision=other_decision,
        lease_duration=timedelta(minutes=5),
        now=NOW + timedelta(minutes=6),
    )
    assert replacement is not None and replacement.run_id != first.run_id
    with postgres.admin_engine.connect() as connection:
        state = connection.scalar(
            sa.text("SELECT state FROM artifact.reconciliation_run WHERE id = :run_id"),
            {"run_id": first.run_id},
        )
    assert state == "timed_out"


class _FailOnceStore:
    def __init__(self, delegate: FilesystemMultipartObjectStore) -> None:
        self.delegate = delegate
        self.failed = False

    async def promote(self, **kwargs: Any) -> StoredObject:
        if not self.failed:
            self.failed = True
            raise ObjectStoreError("synthetic transient copy failure")
        return await self.delegate.promote(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)


class _FailCommitOnceRepository:
    def __init__(self, delegate: SqlAlchemyArtifactRepository) -> None:
        self.delegate = delegate
        self.failed = False

    def commit_available(self, **kwargs: Any) -> FinalizedArtifact:
        if not self.failed:
            self.failed = True
            raise RuntimeError("synthetic DB response loss")
        return self.delegate.commit_available(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)


def test_copy_failure_retries_and_object_success_db_gap_is_reconciled(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    retry_store = _FailOnceStore(postgres.store)
    retry_service = ArtifactService(
        repository=postgres.repository,
        object_store=cast(Any, retry_store),
        transfers=ArtifactTransferCodec(TRANSFER_SECRET, clock=lambda: NOW),
        clock=lambda: NOW,
    )
    payload = b"retryable-copy" * 3000
    staging_key = f"staging/{ORG}/{PROJECT_A}/{uuid4()}.derived"
    command_value = PrepareArtifact(
        classification=DataClassification.INTERNAL,
        artifact_kind=ArtifactKind.DERIVED,
        artifact_role="generic.output",
        schema_ref="urn:cmp:schema:generic-binary:1",
        media_type="application/octet-stream",
        expected_size_bytes=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        staging_object_key=staging_key,
        idempotency_key="t10-retry-copy",
    )

    async def retry_copy() -> FinalizedArtifact:
        await postgres.store.write_for_testing(staging_key, payload)
        with pytest.raises(ObjectStoreError):
            await retry_service.finalize_staged(
                context,
                _decision(context, Permission.ARTIFACT_WRITE),
                command_value,
            )
        result = await retry_service.finalize_staged(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            command_value,
        )
        assert result.pending.attempt_count == 2
        return result

    retried = asyncio.run(retry_copy())
    assert retried.record.integrity_status is IntegrityStatus.VERIFIED

    gap_payload = b"object-success-db-gap" * 2500
    gap_staging = f"staging/{ORG}/{PROJECT_A}/{uuid4()}.derived"
    failing_repository = _FailCommitOnceRepository(postgres.repository)
    gap_service = ArtifactService(
        repository=cast(ArtifactRepository, failing_repository),
        object_store=postgres.store,
        transfers=ArtifactTransferCodec(TRANSFER_SECRET, clock=lambda: NOW),
        clock=lambda: NOW,
    )

    async def recover_gap() -> None:
        await postgres.store.write_for_testing(gap_staging, gap_payload)
        with pytest.raises(RuntimeError, match="DB response loss"):
            await gap_service.finalize_staged(
                context,
                _decision(context, Permission.ARTIFACT_WRITE),
                PrepareArtifact(
                    classification=DataClassification.INTERNAL,
                    artifact_kind=ArtifactKind.DERIVED,
                    artifact_role="generic.output",
                    schema_ref="urn:cmp:schema:generic-binary:1",
                    media_type="application/octet-stream",
                    expected_size_bytes=len(gap_payload),
                    expected_sha256=hashlib.sha256(gap_payload).hexdigest(),
                    staging_object_key=gap_staging,
                    idempotency_key="t10-db-gap",
                ),
            )
        final_key = content_object_key(
            ORG,
            PROJECT_A,
            DataClassification.INTERNAL,
            hashlib.sha256(gap_payload).hexdigest(),
        )
        assert await postgres.store.inspect(final_key) is not None
        reconciled = await postgres.artifacts.reconcile(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
        )
        assert reconciled.pending_recovered >= 1

    asyncio.run(recover_gap())


def test_reconciler_detects_missing_corrupt_orphan_and_missing_staging(
    postgres: PostgresHarness,
) -> None:
    context = _context()

    async def run() -> tuple[UUID, UUID]:
        missing = await _stage_derived(
            postgres.artifacts,
            postgres.store,
            context,
            b"missing-final" * 2000,
            "t10-missing-final",
        )
        corrupt = await _stage_derived(
            postgres.artifacts,
            postgres.store,
            context,
            b"corrupt-final" * 2000,
            "t10-corrupt-final",
        )
        postgres.store.remove_for_testing(missing.record.artifact.storage_key)
        postgres.store.corrupt_for_testing(corrupt.record.artifact.storage_key, b"damaged")

        orphan_bytes = b"orphan-final-object"
        orphan_digest = hashlib.sha256(orphan_bytes).hexdigest()
        orphan_key = content_object_key(ORG, PROJECT_A, DataClassification.INTERNAL, orphan_digest)
        await postgres.store.write_for_testing(orphan_key, orphan_bytes)

        absent_staging = f"staging/{ORG}/{PROJECT_A}/{uuid4()}.derived"
        with pytest.raises(ObjectStoreError):
            await postgres.artifacts.finalize_staged(
                context,
                _decision(context, Permission.ARTIFACT_WRITE),
                PrepareArtifact(
                    classification=DataClassification.INTERNAL,
                    artifact_kind=ArtifactKind.DERIVED,
                    artifact_role="generic.output",
                    schema_ref="urn:cmp:schema:generic-binary:1",
                    media_type="application/octet-stream",
                    expected_size_bytes=1,
                    expected_sha256=hashlib.sha256(b"x").hexdigest(),
                    staging_object_key=absent_staging,
                    idempotency_key="t10-missing-staging",
                ),
            )

        result = await postgres.artifacts.reconcile(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
        )
        assert result.missing >= 1
        assert result.corrupt >= 1
        assert result.orphan_objects >= 1
        assert result.issues_recorded >= 2
        missing_record = postgres.artifacts.get_artifact(
            context,
            _decision(context, Permission.ARTIFACT_READ),
            missing.record.artifact.id,
        )
        corrupt_record = postgres.artifacts.get_artifact(
            context,
            _decision(context, Permission.ARTIFACT_READ),
            corrupt.record.artifact.id,
        )
        assert missing_record.integrity_status is IntegrityStatus.MISSING
        assert corrupt_record.integrity_status is IntegrityStatus.CORRUPT
        with pytest.raises(ArtifactIntegrityError):
            await postgres.artifacts.issue_download(
                context,
                _decision(context, Permission.ARTIFACT_READ),
                missing.record.artifact.id,
            )
        return missing.record.artifact.id, corrupt.record.artifact.id

    missing_id, corrupt_id = asyncio.run(run())
    with postgres.admin_engine.connect() as connection:
        status_rows = connection.execute(
            sa.text(
                "SELECT artifact_id, status FROM artifact.integrity_projection "
                "WHERE artifact_id IN (:missing_id, :corrupt_id)"
            ),
            {"missing_id": missing_id, "corrupt_id": corrupt_id},
        )
        statuses: dict[UUID, str] = {cast(UUID, row[0]): str(row[1]) for row in status_rows}
        assert statuses[missing_id] == "missing"
        assert statuses[corrupt_id] == "corrupt"
        issue_types = set(
            connection.execute(
                sa.text("SELECT issue_type FROM artifact.reconciliation_issue")
            ).scalars()
        )
        assert "orphan_object" in issue_types
        assert "pending_missing_staging" in issue_types
