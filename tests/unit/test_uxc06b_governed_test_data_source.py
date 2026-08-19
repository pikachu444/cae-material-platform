import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from cmp.modules.catalog.domain.model import CatalogConflict, CatalogNotFound
from cmp.modules.datasets.adapters.integration.governed_test_data_source import (
    CatalogTestingGovernedTestDataSourceVerifier,
)
from cmp.modules.datasets.application.canonical_test_data import (
    ExactRevisionRef,
    GovernedTabularTestDataSource,
    GovernedTestDataSource,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    ChannelAxisRole,
)
from cmp.modules.datasets.domain.canonical_test_data import TestDataChannel as CanonicalChannel
from cmp.modules.datasets.domain.canonical_test_data import TestDataSource as CanonicalSource
from cmp.modules.datasets.domain.canonical_test_data import (
    TestExecutionMetadata as ExecutionMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestMaterialMetadata as MaterialMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestSpecimenMetadata as SpecimenMetadata,
)
from cmp.modules.datasets.domain.governed_tabular import (
    AxisRole,
    GovernedChannelMapping,
    GovernedDatasetRepresentation,
    GovernedImportConflict,
    ImportRunStatus,
    NormalizedTabularData,
    QuantityKind,
    TabularDataSchema,
    normalized_parquet_bytes,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext

MATERIAL = UUID("8b000000-0000-4000-8000-000000000001")
MATERIAL_REVISION = UUID("8b000000-0000-4000-8000-000000000002")
STATE = UUID("8b000000-0000-4000-8000-000000000003")
STATE_REVISION = UUID("8b000000-0000-4000-8000-000000000004")
RUN = UUID("8b000000-0000-4000-8000-000000000005")
RUN_REVISION = UUID("8b000000-0000-4000-8000-000000000006")
SPECIMEN = UUID("8b000000-0000-4000-8000-000000000007")
SPECIMEN_REVISION = UUID("8b000000-0000-4000-8000-000000000008")
RAW_ASSET = UUID("8b000000-0000-4000-8000-000000000011")
RAW_ARTIFACT = UUID("8b000000-0000-4000-8000-000000000012")
IMPORT_RUN = UUID("8b000000-0000-4000-8000-000000000013")
PROFILE = UUID("8b000000-0000-4000-8000-000000000014")
PROFILE_REVISION = UUID("8b000000-0000-4000-8000-000000000015")
RAW_DATASET = UUID("8b000000-0000-4000-8000-000000000016")
RAW_DATASET_REVISION = UUID("8b000000-0000-4000-8000-000000000017")
NORMALIZED_DATASET = UUID("8b000000-0000-4000-8000-000000000018")
NORMALIZED_DATASET_REVISION = UUID("8b000000-0000-4000-8000-000000000019")
ORGANIZATION = UUID("8b000000-0000-4000-8000-000000000020")
PROJECT = UUID("8b000000-0000-4000-8000-000000000021")
ACTOR = UUID("8b000000-0000-4000-8000-000000000022")
REQUEST = UUID("8b000000-0000-4000-8000-000000000023")
NOW = datetime(2026, 8, 19, 9, 0, tzinfo=UTC)
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Test data verifier", True),
    organization_id=ORGANIZATION,
    project_id=PROJECT,
    issuer="urn:cmp:test",
    subject=str(ACTOR),
    token_id="uxc06b-test-token",
    groups=(),
    scopes=(Permission.DATASET_WRITE.value,),
    request_id=REQUEST,
    trace_id="00-8b000000000040008000000000000023-0000000000000023-01",
    authenticated_at=NOW,
)
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORGANIZATION,
    project_id=PROJECT,
    permission=Permission.DATASET_WRITE,
    roles=(Role.DATA_STEWARD,),
    database_permissions=(Permission.DATASET_WRITE.value,),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=REQUEST,
    trace_id=CONTEXT.trace_id,
    decided_at=NOW,
)


def _source(**overrides: ExactRevisionRef) -> GovernedTestDataSource:
    return GovernedTestDataSource(
        material=overrides.get("material", ExactRevisionRef(MATERIAL, MATERIAL_REVISION)),
        material_state=overrides.get("material_state", ExactRevisionRef(STATE, STATE_REVISION)),
        test_run=overrides.get("test_run", ExactRevisionRef(RUN, RUN_REVISION)),
    )


_FLD_CHANNELS = (
    GovernedChannelMapping(0, "minor", QuantityKind.MINOR_STRAIN, "1", AxisRole.INDEPENDENT),
    GovernedChannelMapping(1, "major", QuantityKind.MAJOR_STRAIN, "1", AxisRole.DEPENDENT),
)
_FLD_ROWS = ((-0.1, 0.3), (0.1, 0.4))
_RAW_SHA256 = hashlib.sha256(b"minor,major\n-0.1,0.3\n0.1,0.4\n").hexdigest()
_NORMALIZED_SHA256 = hashlib.sha256(
    normalized_parquet_bytes(
        NormalizedTabularData(
            columns=(QuantityKind.MINOR_STRAIN, QuantityKind.MAJOR_STRAIN),
            rows=_FLD_ROWS,
        )
    )
).hexdigest()


def _tabular_source() -> GovernedTestDataSource:
    return GovernedTestDataSource(
        material=ExactRevisionRef(MATERIAL, MATERIAL_REVISION),
        material_state=ExactRevisionRef(STATE, STATE_REVISION),
        test_run=ExactRevisionRef(RUN, RUN_REVISION),
        tabular_import=GovernedTabularTestDataSource(
            RAW_ASSET,
            RAW_ARTIFACT,
            IMPORT_RUN,
            ExactRevisionRef(PROFILE, PROFILE_REVISION),
            ExactRevisionRef(NORMALIZED_DATASET, NORMALIZED_DATASET_REVISION),
        ),
    )


def _document(*, tampered: bool = False) -> CanonicalTestDataDocument:
    major_values = (Decimal("0.3"), Decimal("0.41") if tampered else Decimal("0.4"))
    return CanonicalTestDataDocument(
        document_id="UXC06B-FLD-01",
        material=MaterialMetadata("CMP Test", "Synthetic", None),
        test=ExecutionMetadata(
            date(2026, 8, 19),
            "Test operator",
            "CMP Test Laboratory",
            "bounded synthetic forming-limit test",
        ),
        specimen=SpecimenMetadata("UXC06B-SPECIMEN", "bounded synthetic fixture"),
        conditions=(),
        channels=(
            CanonicalChannel(
                key="minor_strain",
                name="Minor strain",
                quantity_semantics="mechanics.minor_strain",
                axis_role=ChannelAxisRole.INDEPENDENT,
                original_unit_string="1",
                normalized_unit="1",
                normalization_scale=Decimal("1"),
                normalization_offset=Decimal("0"),
                original_values=(Decimal("-0.1"), Decimal("0.1")),
                normalized_values=(Decimal("-0.1"), Decimal("0.1")),
                missing_reasons=(None, None),
            ),
            CanonicalChannel(
                key="major_strain",
                name="Major strain",
                quantity_semantics="mechanics.major_strain",
                axis_role=ChannelAxisRole.DEPENDENT,
                original_unit_string="1",
                normalized_unit="1",
                normalization_scale=Decimal("1"),
                normalization_offset=Decimal("0"),
                original_values=major_values,
                normalized_values=major_values,
                missing_reasons=(None, None),
            ),
        ),
        source=CanonicalSource("uxc06b-fld.csv", "text/csv", _RAW_SHA256),
    )


class _GovernedImports:
    def get_run_for_test_data_source(self, *args: object) -> object:
        del args
        return SimpleNamespace(
            status=ImportRunStatus.SUCCEEDED,
            scope=SimpleNamespace(classification="internal"),
            test_run_id=RUN,
            test_run_revision_id=RUN_REVISION,
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=RAW_ARTIFACT,
            import_profile_id=PROFILE,
            import_profile_revision_id=PROFILE_REVISION,
            raw_dataset_id=RAW_DATASET,
            raw_dataset_revision_id=RAW_DATASET_REVISION,
            normalized_dataset_id=NORMALIZED_DATASET,
            normalized_dataset_revision_id=NORMALIZED_DATASET_REVISION,
        )

    def get_dataset_revision_for_test_data_source(
        self,
        _context: SecurityContext,
        _decision: AuthorizationDecision,
        dataset_id: UUID,
        revision_id: UUID,
    ) -> object:
        common = {
            "test_run_id": RUN,
            "test_run_revision_id": RUN_REVISION,
            "raw_asset_id": RAW_ASSET,
            "raw_artifact_id": RAW_ARTIFACT,
            "import_profile_id": PROFILE,
            "import_profile_revision_id": PROFILE_REVISION,
            "row_count": 2,
            "channels": _FLD_CHANNELS,
            "data_schema": TabularDataSchema.FORMING_LIMIT,
        }
        if (dataset_id, revision_id) == (RAW_DATASET, RAW_DATASET_REVISION):
            return SimpleNamespace(
                record=SimpleNamespace(revision_id=RAW_DATASET_REVISION),
                content=SimpleNamespace(
                    **common,
                    representation=GovernedDatasetRepresentation.RAW,
                    data_sha256=_RAW_SHA256,
                ),
            )
        assert (dataset_id, revision_id) == (
            NORMALIZED_DATASET,
            NORMALIZED_DATASET_REVISION,
        )
        return SimpleNamespace(
            record=SimpleNamespace(revision_id=NORMALIZED_DATASET_REVISION),
            content=SimpleNamespace(
                **common,
                representation=GovernedDatasetRepresentation.NORMALIZED,
                source_dataset_revision_id=RAW_DATASET_REVISION,
                data_sha256=_NORMALIZED_SHA256,
            ),
        )


class _Testing:
    def get_test_run_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_id: UUID,
        revision_id: UUID,
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
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_id: UUID,
        revision_id: UUID,
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
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_id: UUID,
        revision_id: UUID,
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
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        aggregate_id: UUID,
        revision_id: UUID,
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
    _verifier().verify(CONTEXT, DECISION, _source())


def test_exact_governed_tabular_run_datasets_and_canonical_values_are_verified() -> None:
    verifier = CatalogTestingGovernedTestDataSourceVerifier(
        catalog=_Catalog(),  # type: ignore[arg-type]
        testing=_Testing(),  # type: ignore[arg-type]
        governed_import=_GovernedImports(),  # type: ignore[arg-type]
    )

    verifier.verify(CONTEXT, DECISION, _tabular_source(), _document())
    with pytest.raises(GovernedImportConflict, match="differs from the pinned"):
        verifier.verify(CONTEXT, DECISION, _tabular_source(), _document(tampered=True))


@pytest.mark.parametrize(
    "source",
    [
        _source(
            material=ExactRevisionRef(
                UUID("8b000000-0000-4000-8000-000000000009"), MATERIAL_REVISION
            )
        ),
        _source(
            material_state=ExactRevisionRef(STATE, UUID("8b000000-0000-4000-8000-000000000009"))
        ),
        _source(test_run=ExactRevisionRef(RUN, UUID("8b000000-0000-4000-8000-000000000009"))),
    ],
)
def test_any_declared_exact_source_mismatch_is_rejected(
    source: GovernedTestDataSource,
) -> None:
    with pytest.raises(GovernedImportConflict):
        _verifier().verify(CONTEXT, DECISION, source)


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
            CONTEXT,
            DECISION,
            _source(),
        )


def test_material_and_state_cross_classification_is_rejected() -> None:
    class CrossClassificationCatalog(_Catalog):
        def get_material_revision_for_provenance(
            self,
            context: SecurityContext,
            decision: AuthorizationDecision,
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
            CONTEXT,
            DECISION,
            _source(),
        )
