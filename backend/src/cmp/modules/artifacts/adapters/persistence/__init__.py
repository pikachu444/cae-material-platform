"""PostgreSQL persistence adapter for T-09 uploads and Raw Assets."""

from cmp.modules.artifacts.adapters.persistence.uploads import (
    SqlAlchemyUploadRepository,
)

__all__ = ["SqlAlchemyUploadRepository"]
