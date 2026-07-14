from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.artifacts.adapters.persistence.uploads import (
    SqlAlchemyUploadRepository,
)
from cmp.modules.artifacts.adapters.storage.filesystem import (
    FilesystemMultipartObjectStore,
)
from cmp.modules.artifacts.application.uploads import (
    CancelUpload,
    CompleteUpload,
    CreateUpload,
    CreateUploadResult,
    RecordUploadPart,
    UploadCapabilityCodec,
    UploadPolicy,
    UploadService,
)
from cmp.modules.artifacts.domain.uploads import (
    DigestMismatch,
    UploadAccessDenied,
    UploadConflict,
    UploadNotFound,
    UploadState,
    UploadStateError,
)
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
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 7, 12, 13, 0, tzinfo=UTC)
ORG = UUID("89000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("89000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("89000000-0000-4000-8000-000000000003")
ACTOR = UUID("89000000-0000-4000-8000-000000000004")
OTHER_ACTOR = UUID("89000000-0000-4000-8000-000000000006")
TRACE = "00-00000000000000000000000000000089-0000000000000089-01"
SECRET = b"t09-postgresql-integration-secret-32-bytes-minimum"


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    service: UploadService
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
    database_name = f"cmp_t09_{uuid4().hex}"
    app_role = f"cmp_t09_app_{uuid4().hex}"
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
    with tempfile.TemporaryDirectory(prefix="cmp-t09-object-store-") as temporary:
        try:
            command.upgrade(_alembic_config(database_url), "head")
            with admin_engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO identity.principal "
                        "(id, principal_type, display_name, active, created_at, updated_at) "
                        "VALUES (:id, 'user', 'T09 Uploader', true, :now, :now), "
                        "(:other_id, 'user', 'T09 Other Uploader', true, :now, :now)"
                    ),
                    {
                        "id": ACTOR,
                        "other_id": OTHER_ACTOR,
                        "now": NOW - timedelta(days=1),
                    },
                )
                connection.exec_driver_sql(
                    "GRANT USAGE ON SCHEMA identity, revisioning, access_control, "
                    f'governance, artifact TO "{app_role}"'
                )
                connection.exec_driver_sql(
                    "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA artifact "
                    f'TO "{app_role}"'
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
            repository = SqlAlchemyUploadRepository(
                session_factory=sessions,
                rls_context=rls,
            )
            store = FilesystemMultipartObjectStore(Path(temporary))
            yield PostgresHarness(
                admin_engine,
                UploadService(
                    repository=repository,
                    object_store=store,
                    capabilities=UploadCapabilityCodec(SECRET, clock=lambda: NOW),
                    policy=UploadPolicy(
                        max_object_bytes=2 * 1024 * 1024,
                        default_part_bytes=64 * 1024,
                        min_part_bytes=64 * 1024,
                        max_part_bytes=512 * 1024,
                        session_ttl=timedelta(hours=1),
                    ),
                    clock=lambda: NOW,
                ),
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
        principal=Principal(actor_id, PrincipalType.USER, "T09 Uploader", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
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


async def _create(
    service: UploadService,
    context: SecurityContext,
    payload: bytes,
    idempotency_key: str,
    *,
    filename: str = "raw.bin",
    digest: str | None = None,
) -> CreateUploadResult:
    return await service.create(
        context,
        _decision(context, Permission.ARTIFACT_WRITE),
        CreateUpload(
            classification=DataClassification.INTERNAL,
            original_filename=filename,
            media_type="application/octet-stream",
            expected_size_bytes=len(payload),
            expected_sha256=digest or hashlib.sha256(payload).hexdigest(),
            idempotency_key=idempotency_key,
            part_size_bytes=64 * 1024,
            # Generic Artifact upload tests do not fabricate a dangling Testing revision.
            test_run_revision_id=None,
        ),
    )


async def _upload_all(
    service: UploadService,
    context: SecurityContext,
    created: CreateUploadResult,
    payload: bytes,
    *,
    reverse: bool = False,
) -> None:
    session = created.session
    numbers = list(range(1, session.expected_part_count + 1))
    if reverse:
        numbers.reverse()
    for part_number in numbers:
        start = (part_number - 1) * session.part_size_bytes
        end = min(start + session.part_size_bytes, len(payload))
        await service.record_part(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            RecordUploadPart(session.id, part_number, created.capability),
            _chunks(payload[start:end]),
        )


def test_stream_resume_complete_is_idempotent_and_raw_facts_are_immutable(
    postgres: PostgresHarness,
) -> None:
    payload = (b"streamed-raw-bytes-" * 9000)[:150_000]
    context = _context()

    async def run() -> tuple[CreateUploadResult, UUID, UUID]:
        created = await _create(postgres.service, context, payload, "t09-stream-1")
        replay = await _create(postgres.service, context, payload, "t09-stream-1")
        assert replay.replayed
        assert replay.session.id == created.session.id
        assert replay.capability == created.capability
        with pytest.raises(UploadConflict, match="already in use"):
            await _create(
                postgres.service,
                _context(actor_id=OTHER_ACTOR),
                payload,
                "t09-stream-1",
            )
        await _upload_all(postgres.service, context, created, payload, reverse=True)
        first_part = payload[: created.session.part_size_bytes]
        replayed_part = await postgres.service.record_part(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            RecordUploadPart(created.session.id, 1, created.capability),
            _chunks(first_part),
        )
        assert len(replayed_part.parts) == created.session.expected_part_count
        completed = await postgres.service.complete(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            CompleteUpload(created.session.id, created.capability),
        )
        replayed = await postgres.service.complete(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            CompleteUpload(created.session.id, created.capability),
        )
        assert replayed.raw_asset.id == completed.raw_asset.id
        assert replayed.ingestion_event.id == completed.ingestion_event.id
        assert not completed.duplicate_content
        assert postgres.store.read_for_testing(
            completed.raw_asset.staging_object_key
        ) == payload
        return created, completed.raw_asset.id, completed.ingestion_event.id

    created, raw_asset_id, event_id = asyncio.run(run())
    visible = postgres.service.get_raw_asset(
        context,
        _decision(context, Permission.ARTIFACT_READ),
        raw_asset_id,
    )
    assert visible.sha256 == hashlib.sha256(payload).hexdigest()

    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE artifact.raw_asset SET media_type = 'text/plain' "
                    "WHERE id = :id"
                ),
                {"id": raw_asset_id},
            )
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE artifact.ingestion_event SET duplicate_content = true "
                    "WHERE id = :id"
                ),
                {"id": event_id},
            )
    with pytest.raises(DBAPIError, match="terminal upload sessions are immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE artifact.upload_session "
                    "SET terminal_at = terminal_at + interval '1 second' "
                    "WHERE id = :id"
                ),
                {"id": created.session.id},
            )
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE artifact.upload_part SET sha256 = :digest "
                    "WHERE upload_session_id = :id AND part_number = 1"
                ),
                {"id": created.session.id, "digest": "f" * 64},
            )


def test_digest_mismatch_fails_terminally_and_discards_staged_object(
    postgres: PostgresHarness,
) -> None:
    payload = b"digest-mismatch" * 6000
    context = _context()

    async def run() -> CreateUploadResult:
        created = await _create(
            postgres.service,
            context,
            payload,
            "t09-digest-mismatch",
            digest="0" * 64,
        )
        await _upload_all(postgres.service, context, created, payload)
        with pytest.raises(DigestMismatch):
            await postgres.service.complete(
                context,
                _decision(context, Permission.ARTIFACT_WRITE),
                CompleteUpload(created.session.id, created.capability),
            )
        return created

    created = asyncio.run(run())
    failed = postgres.service.get_upload(
        context,
        _decision(context, Permission.ARTIFACT_READ),
        created.session.id,
    )
    assert failed.state is UploadState.FAILED
    assert failed.failure_code == "digest_mismatch"
    with pytest.raises(FileNotFoundError):
        postgres.store.read_for_testing(created.session.staging_object_key)


def test_duplicate_content_reuses_raw_asset_and_appends_ingestion_event(
    postgres: PostgresHarness,
) -> None:
    payload = b"duplicate-content" * 5000
    context = _context()

    async def run() -> tuple[UUID, UUID, str]:
        first = await _create(
            postgres.service,
            context,
            payload,
            "t09-dedup-first",
            filename="first.bin",
        )
        await _upload_all(postgres.service, context, first, payload)
        first_result = await postgres.service.complete(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            CompleteUpload(first.session.id, first.capability),
        )
        second = await _create(
            postgres.service,
            context,
            payload,
            "t09-dedup-second",
            filename="second.bin",
        )
        await _upload_all(postgres.service, context, second, payload)
        second_result = await postgres.service.complete(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            CompleteUpload(second.session.id, second.capability),
        )
        assert second_result.duplicate_content
        assert second_result.raw_asset.id == first_result.raw_asset.id
        assert second_result.ingestion_event.id != first_result.ingestion_event.id
        return (
            first_result.raw_asset.id,
            second_result.raw_asset.id,
            second.session.staging_object_key,
        )

    first_id, second_id, discarded_key = asyncio.run(run())
    assert first_id == second_id
    with pytest.raises(FileNotFoundError):
        postgres.store.read_for_testing(discarded_key)
    with postgres.admin_engine.connect() as connection:
        assert connection.execute(
            sa.text(
                "SELECT count(*) FROM artifact.raw_asset "
                "WHERE sha256 = :digest"
            ),
            {"digest": hashlib.sha256(payload).hexdigest()},
        ).scalar_one() == 1
        assert connection.execute(
            sa.text(
                "SELECT count(*) FROM artifact.ingestion_event "
                "WHERE raw_asset_id = :id"
            ),
            {"id": first_id},
        ).scalar_one() == 2


def test_cancel_and_cross_project_or_tampered_capability_fail_closed(
    postgres: PostgresHarness,
) -> None:
    payload = b"cancelled-upload" * 5000
    owner = _context()
    other = _context(project_id=PROJECT_B)

    async def run() -> None:
        created = await _create(
            postgres.service, owner, payload, "t09-cancel-cross-project"
        )
        with pytest.raises(UploadNotFound):
            await postgres.service.record_part(
                other,
                _decision(other, Permission.ARTIFACT_WRITE),
                RecordUploadPart(created.session.id, 1, created.capability),
                _chunks(payload[: created.session.part_size_bytes]),
            )
        tampered_capability = created.capability[:-1] + (
            "B" if created.capability.endswith("A") else "A"
        )
        with pytest.raises(UploadAccessDenied):
            await postgres.service.record_part(
                owner,
                _decision(owner, Permission.ARTIFACT_WRITE),
                RecordUploadPart(
                    created.session.id,
                    1,
                    tampered_capability,
                ),
                _chunks(payload[: created.session.part_size_bytes]),
            )
        await postgres.service.record_part(
            owner,
            _decision(owner, Permission.ARTIFACT_WRITE),
            RecordUploadPart(created.session.id, 1, created.capability),
            _chunks(payload[: created.session.part_size_bytes]),
        )
        cancelled = await postgres.service.cancel(
            owner,
            _decision(owner, Permission.ARTIFACT_WRITE),
            CancelUpload(created.session.id, created.capability),
        )
        assert cancelled.state is UploadState.CANCELLED
        with pytest.raises(UploadStateError):
            await postgres.service.record_part(
                owner,
                _decision(owner, Permission.ARTIFACT_WRITE),
                RecordUploadPart(created.session.id, 2, created.capability),
                _chunks(payload[created.session.part_size_bytes :]),
            )

    asyncio.run(run())


def test_environment_maximum_fixture_streams_in_bounded_chunks(
    postgres: PostgresHarness,
) -> None:
    payload = (bytes(range(256)) * 8192)[: 2 * 1024 * 1024]
    context = _context()

    async def run() -> None:
        created = await _create(
            postgres.service,
            context,
            payload,
            "t09-environment-maximum",
            filename="environment-maximum.bin",
        )
        assert created.session.expected_size_bytes == 2 * 1024 * 1024
        assert created.session.expected_part_count == 32
        await _upload_all(postgres.service, context, created, payload)
        completed = await postgres.service.complete(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            CompleteUpload(created.session.id, created.capability),
        )
        assert completed.raw_asset.size_bytes == len(payload)
        assert postgres.store.read_for_testing(
            completed.raw_asset.staging_object_key
        ) == payload

    asyncio.run(run())
