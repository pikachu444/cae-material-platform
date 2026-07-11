"""Compose T-17 from the shared PostgreSQL authorization boundary."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.plugins.adapters.contracts.jsonschema import (
    JsonSchemaPluginContractValidator,
)
from cmp.modules.plugins.adapters.persistence.registry import (
    SqlAlchemyPluginRegistryRepository,
)
from cmp.modules.plugins.application.registry import PluginRegistryService


def build_plugin_registry_service(
    identity: IdentityServices,
) -> PluginRegistryService | None:
    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(
        identity.engine,
        class_=Session,
        expire_on_commit=False,
    )
    repository = SqlAlchemyPluginRegistryRepository(
        session_factory=sessions,
        rls_context=identity.rls_context,
    )
    return PluginRegistryService(
        repository=repository,
        validator=JsonSchemaPluginContractValidator(),
    )
