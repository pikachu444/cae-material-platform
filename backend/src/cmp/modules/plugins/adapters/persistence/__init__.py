"""PostgreSQL persistence adapter for the T-17 plugin registry."""

from cmp.modules.plugins.adapters.persistence.registry import (
    SqlAlchemyPluginRegistryRepository,
)

__all__ = ["SqlAlchemyPluginRegistryRepository"]
