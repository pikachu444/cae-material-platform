from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.application.scientific_profile import (
    SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
    CreateScientificProfile,
    RevisionSnapshot,
    ScientificProfileRepository,
    ScientificProfileService,
)
from cmp.modules.modeling.domain.scientific_profile import (
    OgdenScientificParameters,
    ScientificApprovalStatus,
    ScientificProfileConflict,
    ScientificProfileContent,
    ScientificProfileFamily,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope, content_sha256

NOW = datetime(2026, 8, 19, 9, 0, tzinfo=UTC)
ORG, PROJECT, ACTOR, PROFILE, HISTORICAL_REVISION = (
    UUID(int=value) for value in range(1, 6)
)
TRACE = "00-00000000000000000000000000000053-0000000000000053-01"
CONTEXT = SecurityContext(
    Principal(ACTOR, PrincipalType.USER, "Modeler", True),
    ORG,
    PROJECT,
    "https://test.invalid",
    str(ACTOR),
    str(uuid4()),
    (),
    ("openid",),
    uuid4(),
    TRACE,
    NOW,
)


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        ACTOR,
        ORG,
        PROJECT,
        permission,
        (Role.MATERIAL_MODELER,),
        database_permissions_for(permission),
        DataClassification.INTERNAL,
        False,
        CONTEXT.request_id,
        TRACE,
        NOW,
    )


def _content(status: ScientificApprovalStatus) -> ScientificProfileContent:
    return ScientificProfileContent(
        "Reference one-term Ogden",
        ScientificProfileFamily.ELASTOMER_OGDEN_PRONY,
        status,
        8,
        17,
        ogden=OgdenScientificParameters(1e6, 1e3, 1e8, 1e6, 2, 0.1, 20, 2),
    )


HISTORICAL_CONTENT = _content(ScientificApprovalStatus.REFERENCE_UNAPPROVED)
HISTORICAL = RevisionSnapshot(
    RevisionRecord(
        HISTORICAL_REVISION,
        SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
        PROFILE,
        TenantScope(ORG, PROJECT, "internal"),
        1,
        None,
        "urn:cmp:modeling:scientific-calibration-profile:1.0.0",
        "1.0.0",
        content_sha256(HISTORICAL_CONTENT.canonical()),
        NOW,
        ACTOR,
        "Historical reference profile",
        CONTEXT.request_id,
        TRACE,
    ),
    HISTORICAL_CONTENT,
)


class _Repository:
    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        profile_revision_id: UUID,
    ) -> RevisionSnapshot:
        assert context is CONTEXT
        assert decision.permission is Permission.CALIBRATION_EXECUTE
        assert profile_id == PROFILE and profile_revision_id == HISTORICAL_REVISION
        return HISTORICAL


def _service() -> ScientificProfileService:
    return ScientificProfileService(repository=cast(ScientificProfileRepository, _Repository()))


def test_calibration_can_pin_an_exact_historical_profile_revision() -> None:
    value = _service().get_revision_for_calibration(
        CONTEXT,
        _decision(Permission.CALIBRATION_EXECUTE),
        PROFILE,
        HISTORICAL_REVISION,
    )
    assert value.record.revision_id == HISTORICAL_REVISION
    assert value.content.approval_status is ScientificApprovalStatus.REFERENCE_UNAPPROVED


def test_profile_api_cannot_self_assert_domain_approval() -> None:
    with pytest.raises(ScientificProfileConflict, match="governed review transition"):
        _service().create(
            CONTEXT,
            _decision(Permission.MODELING_WRITE),
            CreateScientificProfile(
                "internal",
                _content(ScientificApprovalStatus.DOMAIN_APPROVED),
                "Attempt direct approval",
            ),
        )
