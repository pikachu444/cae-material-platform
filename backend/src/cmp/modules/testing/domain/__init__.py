"""Explicit physical-specimen and reference Test Run domain values."""

from cmp.modules.testing.domain.import_mapping import (
    REFERENCE_IMPORT_MAPPING_SCHEMA_ID,
    REFERENCE_IMPORT_MAPPING_SCHEMA_VERSION,
    REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_ID,
    REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_VERSION,
    ImportDetectionStatus,
    MappingSuggestionConfidence,
    ReferenceImportMappingContent,
    SyntheticCsvDetectionReport,
)
from cmp.modules.testing.domain.reference_tensile import (
    REFERENCE_TENSILE_METHOD_CODE,
    REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
    REFERENCE_TENSILE_SCHEMA_VERSION,
    InvalidTestingData,
    SpecimenContent,
    TestingConflict,
    TestingError,
    TestingNotFound,
    TestMethodContent,
    TestRunContent,
)

__all__ = [
    "REFERENCE_IMPORT_MAPPING_SCHEMA_ID",
    "REFERENCE_IMPORT_MAPPING_SCHEMA_VERSION",
    "REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_ID",
    "REFERENCE_SYNTHETIC_CSV_HEADER_IMPORTER_VERSION",
    "REFERENCE_TENSILE_METHOD_CODE",
    "REFERENCE_TENSILE_METHOD_DISPLAY_NAME",
    "REFERENCE_TENSILE_SCHEMA_VERSION",
    "ImportDetectionStatus",
    "InvalidTestingData",
    "MappingSuggestionConfidence",
    "ReferenceImportMappingContent",
    "SpecimenContent",
    "SyntheticCsvDetectionReport",
    "TestMethodContent",
    "TestRunContent",
    "TestingConflict",
    "TestingError",
    "TestingNotFound",
]
