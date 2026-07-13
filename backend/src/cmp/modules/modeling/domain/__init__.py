"""Pure domain rules for solver-neutral Material Model IR records."""

from .reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    REFERENCE_MODEL_SCHEMA_VERSION,
    ReferenceLinearElasticContent,
    reference_linear_elastic_ir,
)

__all__ = [
    "REFERENCE_MODEL_FAMILY_ID",
    "REFERENCE_MODEL_SCHEMA_DIGEST",
    "REFERENCE_MODEL_SCHEMA_VERSION",
    "ReferenceLinearElasticContent",
    "reference_linear_elastic_ir",
]
