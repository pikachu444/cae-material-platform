from types import SimpleNamespace
from uuid import UUID

import pytest
from cmp.modules.catalog.domain.model import CatalogConflict, CatalogNotFound
from cmp.modules.datasets.adapters.integration.governed_test_data_source import (
    CatalogTestingGovernedTestDataSourceVerifier,
)
from cmp.modules.datasets.application.canonical_test_data import (
    ExactRevisionRef,
    GovernedTestDataSource,
)
from cmp.modules.datasets.domain.governed_tabular import GovernedImportConflict
from cmp.modules.identity_access.domain.authorization import DataClassification

MATERIAL = UUID("8b000000-0000-4000-8000-000000000001")
MATERIAL_REVISION = UUID("8b000000-0000-4000-8000-000000000002")
STATE = UUID("8b000000-0000-4000-8000-000000000003")
STATE_REVISION = UUID("8b000000-0000-4000-8000-000000000004")
RUN = UUID("8b000000-0000-4000-8000-000000000005")
RUN_REVISION = UUID("8b000000-0000-4000-8000-000000000006")
SPECIMEN = UUID("8b000000-0000-4000-8000-000000000007")
SPECIMEN_REVISION = UUID("8b000000-0000-4000-8000-000000000008")


def _source(**overrides: ExactRevisionRef) -> GovernedTestDataSource:
    return GovernedTestDataSource(
        material=overrides.get("material", ExactRevisionRef(MATERIAL, MATERIAL_REVISION)),
        material_state=overrides.get(
            "material_state", ExactRevisionRef(STATE, STATE_REVISION)
        ),
        test_run=overrides.get("test_run", ExactRevisionRef(RUN, RUN_REVISION)),
    )


class _Testing:
    def get_test_run_revision_for_processing(
        self, context: object, decision: object, aggregate_id: UUID, revision_id: UUID
    ) -> object:
        del context, decision
        if aggregate_id != RUN or revision_id != RUN_REVISION:
            raise GovernedImportConflict("exact Test Run revision is unavailable")
        return SimpleNamespace(
            record=SimpleNamespace(scope=SimpleNamespace(classification="internal")),
            content=SimpleNamespace(
                specimen_id=SPECIMEN,
                specimen_revision_id=SPECIMEN_REVISION,
            ),
        )

    def get_specimen_revision_for_processing(
        self, context: object, decision: object, aggregate_id: UUID, revision_id: UUID
    ) -> tuple[DataClassification, object]:
        del context, decision
        assert aggregate_id == SPECIMEN
        assert revision_id == SPECIMEN_REVISION
        return DataClassification.INTERNAL, SimpleNamespace(
            material_id=MATERIAL,
            material_revision_id=MATERIAL_REVISION,
            material_state_id=STATE,
            material_state_revision_id=STATE_REVISION,
        )


class _Catalog:
    def __init__(self, *, material_failure: Exception | None = None) -> None:
        self._material_failure = material_failure

    def get_material_state_revision_for_calibration(
        self, context: object, decision: object, aggregate_id: UUID, revision_id: UUID
    ) -> object:
        del context, decision
        if aggregate_id != STATE or revision_id != STATE_REVISION:
            raise GovernedImportConflict("exact Material State revision is unavailable")
        return SimpleNamespace(
            record=SimpleNamespace(
                scope=SimpleNamespace(
                    organization_id="org",
                    project_id="project",
                    classification="internal",
                )
            ),
            content=SimpleNamespace(
                material_id=MATERIAL,
                material_revision_id=MATERIAL_REVISION,
            ),
        )

    def get_material_revision_for_provenance(
        self, context: object, decision: object, aggregate_id: UUID, revision_id: UUID
    ) -> object:
        del context, decision
        if self._material_failure is not None:
            raise self._material_failure
        if aggregate_id != MATERIAL or revision_id != MATERIAL_REVISION:
            raise CatalogNotFound("exact Material revision is unavailable")
        return SimpleNamespace(
            record=SimpleNamespace(
                scope=SimpleNamespace(
                    organization_id="org",
                    project_id="project",
                    classification="internal",
                )
            )
        )


def _verifier(
    catalog: _Catalog | None = None,
) -> CatalogTestingGovernedTestDataSourceVerifier:
    return CatalogTestingGovernedTestDataSourceVerifier(
        catalog=catalog or _Catalog(),  # type: ignore[arg-type]
        testing=_Testing(),  # type: ignore[arg-type]
    )


def test_exact_test_run_specimen_state_material_chain_is_accepted() -> None:
    _verifier().verify(object(), object(), _source())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "source",
    [
        _source(
            material=ExactRevisionRef(
                UUID("8b000000-0000-4000-8000-000000000009"), MATERIAL_REVISION
            )
        ),
        _source(
            material_state=ExactRevisionRef(
                STATE, UUID("8b000000-0000-4000-8000-000000000009")
            )
        ),
        _source(
            test_run=ExactRevisionRef(
                RUN, UUID("8b000000-0000-4000-8000-000000000009")
            )
        ),
    ],
)
def test_any_declared_exact_source_mismatch_is_rejected(
    source: GovernedTestDataSource,
) -> None:
    with pytest.raises(GovernedImportConflict):
        _verifier().verify(object(), object(), source)  # type: ignore[arg-type]


def test_zero_revision_pins_are_rejected_before_cross_module_reads() -> None:
    with pytest.raises(GovernedImportConflict, match="non-zero"):
        ExactRevisionRef(MATERIAL, UUID(int=0))


@pytest.mark.parametrize(
    "failure",
    [
        CatalogNotFound("exact Material revision is unavailable"),
        CatalogConflict("Material revision is outside the authorized scope"),
    ],
)
def test_missing_or_restricted_exact_material_fails_closed(failure: Exception) -> None:
    with pytest.raises(GovernedImportConflict, match="could not be verified"):
        _verifier(_Catalog(material_failure=failure)).verify(
            object(), object(), _source()  # type: ignore[arg-type]
        )


def test_material_and_state_cross_classification_is_rejected() -> None:
    class CrossClassificationCatalog(_Catalog):
        def get_material_revision_for_provenance(
            self,
            context: object,
            decision: object,
            aggregate_id: UUID,
            revision_id: UUID,
        ) -> object:
            del context, decision, aggregate_id, revision_id
            return SimpleNamespace(
                record=SimpleNamespace(
                    scope=SimpleNamespace(
                        organization_id="org",
                        project_id="project",
                        classification="restricted",
                    )
                )
            )

    with pytest.raises(GovernedImportConflict, match="scope differs"):
        _verifier(CrossClassificationCatalog()).verify(
            object(), object(), _source()  # type: ignore[arg-type]
        )
