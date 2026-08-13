"""Narrow Catalog/Testing adapter for Canonical Test Data provenance verification."""

from __future__ import annotations

import hashlib

from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.catalog.domain.model import CatalogError
from cmp.modules.datasets.application.canonical_test_data import GovernedTestDataSource
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.datasets.domain.canonical_test_data import CanonicalTestDataDocument
from cmp.modules.datasets.domain.governed_tabular import (
    GovernedDatasetRepresentation,
    GovernedImportConflict,
    GovernedImportNotFound,
    ImportRunStatus,
    NormalizedTabularData,
    normalized_parquet_bytes,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.application.service import TestingService
from cmp.modules.testing.domain.reference_tensile import TestingError


class CatalogTestingGovernedTestDataSourceVerifier:
    """Proves Test Run -> Specimen -> State -> Material exact-revision lineage.

    This stays at application ports: the canonical-data aggregate never reads
    Catalog or Testing tables directly.
    """

    def __init__(
        self,
        *,
        catalog: CatalogService,
        testing: TestingService,
        governed_import: GovernedImportService | None = None,
    ) -> None:
        self._catalog = catalog
        self._testing = testing
        self._governed_import = governed_import

    def verify(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: GovernedTestDataSource,
        document: CanonicalTestDataDocument | None = None,
    ) -> None:
        try:
            run = self._testing.get_test_run_revision_for_processing(
                context, decision, source.test_run.aggregate_id, source.test_run.revision_id
            )
            classification, specimen = self._testing.get_specimen_revision_for_processing(
                context, decision, run.content.specimen_id, run.content.specimen_revision_id
            )
            state = self._catalog.get_material_state_revision_for_calibration(
                context,
                decision,
                source.material_state.aggregate_id,
                source.material_state.revision_id,
            )
            material = self._catalog.get_material_revision_for_provenance(
                context,
                decision,
                source.material.aggregate_id,
                source.material.revision_id,
            )
        except (CatalogError, TestingError) as error:
            raise GovernedImportConflict(
                "governed source exact lineage could not be verified"
            ) from error
        if classification.value != run.record.scope.classification:
            raise GovernedImportConflict("Test Run and Specimen classification differ")
        if (
            specimen.material_id != source.material.aggregate_id
            or specimen.material_revision_id != source.material.revision_id
            or specimen.material_state_id != source.material_state.aggregate_id
            or specimen.material_state_revision_id != source.material_state.revision_id
        ):
            raise GovernedImportConflict(
                "governed source does not match the exact Test Run specimen context"
            )
        if (
            state.record.scope.classification != classification.value
            or state.content.material_id != source.material.aggregate_id
            or state.content.material_revision_id != source.material.revision_id
        ):
            raise GovernedImportConflict(
                "governed source Material State does not pin the exact Material revision"
            )
        if material.record.scope != state.record.scope:
            raise GovernedImportConflict(
                "governed source Material revision scope differs from its Material State"
            )
        tabular = source.tabular_import
        if tabular is None:
            return
        if self._governed_import is None:
            raise GovernedImportConflict("governed tabular source verification is unavailable")
        try:
            import_run = self._governed_import.get_run_for_test_data_source(
                context,
                decision,
                tabular.import_run_id,
            )
        except GovernedImportNotFound as error:
            raise GovernedImportConflict(
                "governed tabular Import Run could not be verified"
            ) from error
        if (
            import_run.status is not ImportRunStatus.SUCCEEDED
            or import_run.scope != run.record.scope
            or import_run.test_run_id != source.test_run.aggregate_id
            or import_run.test_run_revision_id != source.test_run.revision_id
            or import_run.raw_asset_id != tabular.raw_asset_id
            or import_run.raw_artifact_id != tabular.raw_artifact_id
            or import_run.import_profile_id != tabular.import_profile.aggregate_id
            or import_run.import_profile_revision_id != tabular.import_profile.revision_id
            or import_run.normalized_dataset_id != tabular.normalized_dataset.aggregate_id
            or import_run.normalized_dataset_revision_id != tabular.normalized_dataset.revision_id
        ):
            raise GovernedImportConflict(
                "canonical Test Data does not pin the successful exact governed import"
            )
        if (
            document is None
            or import_run.raw_dataset_id is None
            or import_run.raw_dataset_revision_id is None
            or import_run.normalized_dataset_id is None
            or import_run.normalized_dataset_revision_id is None
        ):
            raise GovernedImportConflict(
                "canonical Test Data cannot verify the governed Dataset revisions"
            )
        try:
            raw = self._governed_import.get_dataset_revision_for_test_data_source(
                context,
                decision,
                import_run.raw_dataset_id,
                import_run.raw_dataset_revision_id,
            )
            normalized = self._governed_import.get_dataset_revision_for_test_data_source(
                context,
                decision,
                import_run.normalized_dataset_id,
                import_run.normalized_dataset_revision_id,
            )
        except GovernedImportNotFound as error:
            raise GovernedImportConflict(
                "governed tabular Dataset revisions could not be verified"
            ) from error
        expected_channels = tuple(
            (
                channel.normalized_quantity.value,
                channel.normalized_unit,
                channel.axis_role.value,
            )
            for channel in normalized.content.channels
        )
        actual_channels = tuple(
            (channel.key, channel.normalized_unit, channel.axis_role.value)
            for channel in document.channels
        )
        try:
            normalized_rows = tuple(
                tuple(float(value) for value in row)
                for row in zip(
                    *(channel.normalized_values for channel in document.channels),
                    strict=True,
                )
            )
            normalized_sha256 = hashlib.sha256(
                normalized_parquet_bytes(
                    NormalizedTabularData(
                        columns=tuple(
                            channel.normalized_quantity for channel in normalized.content.channels
                        ),
                        rows=normalized_rows,
                    )
                )
            ).hexdigest()
        except (TypeError, ValueError) as error:
            raise GovernedImportConflict(
                "canonical Test Data contains missing or invalid governed values"
            ) from error
        if (
            raw.content.representation is not GovernedDatasetRepresentation.RAW
            or normalized.content.representation is not GovernedDatasetRepresentation.NORMALIZED
            or raw.content.test_run_id != import_run.test_run_id
            or raw.content.test_run_revision_id != import_run.test_run_revision_id
            or normalized.content.test_run_id != import_run.test_run_id
            or normalized.content.test_run_revision_id != import_run.test_run_revision_id
            or raw.content.raw_asset_id != import_run.raw_asset_id
            or raw.content.raw_artifact_id != import_run.raw_artifact_id
            or normalized.content.raw_asset_id != import_run.raw_asset_id
            or normalized.content.raw_artifact_id != import_run.raw_artifact_id
            or raw.content.import_profile_id != import_run.import_profile_id
            or raw.content.import_profile_revision_id != import_run.import_profile_revision_id
            or normalized.content.import_profile_id != import_run.import_profile_id
            or normalized.content.import_profile_revision_id
            != import_run.import_profile_revision_id
            or raw.content.data_schema is not normalized.content.data_schema
            or raw.content.data_sha256 != document.source.sha256
            or normalized.content.source_dataset_revision_id != raw.record.revision_id
            or normalized.content.row_count != document.point_count
            or raw.content.row_count != document.point_count
            or raw.content.channels != normalized.content.channels
            or expected_channels != actual_channels
            or normalized.content.data_sha256 != normalized_sha256
        ):
            raise GovernedImportConflict(
                "canonical Test Data content differs from the pinned governed Dataset evidence"
            )
