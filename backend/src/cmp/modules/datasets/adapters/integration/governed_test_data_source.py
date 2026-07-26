"""Narrow Catalog/Testing adapter for Canonical Test Data provenance verification."""

from __future__ import annotations

from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.catalog.domain.model import CatalogError
from cmp.modules.datasets.application.canonical_test_data import GovernedTestDataSource
from cmp.modules.datasets.domain.governed_tabular import GovernedImportConflict
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.application.service import TestingService
from cmp.modules.testing.domain.reference_tensile import TestingError


class CatalogTestingGovernedTestDataSourceVerifier:
    """Proves Test Run -> Specimen -> State -> Material exact-revision lineage.

    This stays at application ports: the canonical-data aggregate never reads
    Catalog or Testing tables directly.
    """

    def __init__(self, *, catalog: CatalogService, testing: TestingService) -> None:
        self._catalog = catalog
        self._testing = testing

    def verify(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: GovernedTestDataSource,
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
