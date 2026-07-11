"""Compose the T-15 job module from the shared PostgreSQL authorization boundary."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.jobs.adapters.contracts.jsonschema import (
    JsonSchemaJobContractValidator,
)
from cmp.modules.jobs.adapters.persistence.jobs import SqlAlchemyJobRepository
from cmp.modules.jobs.application.jobs import JobService


def build_job_service(identity: IdentityServices) -> JobService | None:
    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(
        identity.engine,
        class_=Session,
        expire_on_commit=False,
    )
    repository = SqlAlchemyJobRepository(
        session_factory=sessions,
        rls_context=identity.rls_context,
    )
    return JobService(
        repository=repository,
        validator=JsonSchemaJobContractValidator(),
    )
