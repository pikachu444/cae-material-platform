"""T-59 Administrator/User and feature-grant HTTP resources."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from cmp.modules.identity_access.adapters.api.authorization import (
    RequestAuthorizationDependency,
)
from cmp.modules.identity_access.adapters.api.security import (
    AuthenticationProblem,
    IdentityHttpError,
    RequestSecurityContextDependency,
)
from cmp.modules.identity_access.application.authorization import (
    GrantProductAccess,
    ProductAccessAdministrationService,
    RevokeProductAccess,
)
from cmp.modules.identity_access.domain.authorization import (
    BindingSubject,
    DataClassification,
    FeatureGrant,
    ProductAccessAssignment,
    ProductAccessSummary,
    ProductRole,
    RoleBindingConflict,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from fastapi import Depends, FastAPI, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

type Reason = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ProductAccessSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_role: ProductRole
    feature_grants: list[FeatureGrant]
    legacy_compatible: bool

    @classmethod
    def from_domain(cls, value: ProductAccessSummary) -> ProductAccessSummaryResponse:
        return cls(
            product_role=value.product_role,
            feature_grants=list(value.feature_grants),
            legacy_compatible=value.legacy_compatible,
        )


class ProductAccessAssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: UUID
    organization_id: UUID
    project_id: UUID | None
    subject_type: Literal["principal", "group"]
    principal_id: UUID | None
    group_issuer: str | None
    group_name: str | None
    product_role: ProductRole
    feature_grants: list[FeatureGrant]
    max_classification: DataClassification
    allow_export_controlled: bool
    valid_from: datetime
    expires_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def from_domain(
        cls, value: ProductAccessAssignment
    ) -> ProductAccessAssignmentResponse:
        return cls(
            assignment_id=value.id,
            organization_id=value.organization_id,
            project_id=value.project_id,
            subject_type="principal" if value.subject.principal_id else "group",
            principal_id=value.subject.principal_id,
            group_issuer=value.subject.group_issuer,
            group_name=value.subject.group_name,
            product_role=value.product_role,
            feature_grants=list(value.feature_grants),
            max_classification=value.max_classification,
            allow_export_controlled=value.allow_export_controlled,
            valid_from=value.valid_from,
            expires_at=value.expires_at,
            revoked_at=value.revoked_at,
        )


class ProductAccessAssignmentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProductAccessAssignmentResponse]


class GrantProductAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_type: Literal["principal", "group"]
    principal_id: UUID | None = None
    group_issuer: Annotated[str | None, StringConstraints(min_length=1, max_length=2048)] = None
    group_name: Annotated[str | None, StringConstraints(min_length=1, max_length=255)] = None
    product_role: ProductRole
    feature_grants: Annotated[list[FeatureGrant], Field(max_length=5)] = Field(
        default_factory=list
    )
    max_classification: DataClassification = DataClassification.INTERNAL
    allow_export_controlled: bool = False
    organization_wide: bool = False
    expires_at: datetime | None = None
    grant_reason: Reason

    @model_validator(mode="after")
    def validate_subject_and_features(self) -> GrantProductAccessRequest:
        if self.subject_type == "principal":
            if (
                self.principal_id is None
                or self.group_issuer is not None
                or self.group_name is not None
            ):
                raise ValueError("principal subject requires only principal_id")
        elif self.principal_id is not None or self.group_issuer is None or self.group_name is None:
            raise ValueError("group subject requires only group_issuer and group_name")
        if len(set(self.feature_grants)) != len(self.feature_grants):
            raise ValueError("feature_grants must be unique")
        return self

    def subject(self) -> BindingSubject:
        if self.subject_type == "principal":
            assert self.principal_id is not None
            return BindingSubject.for_principal(self.principal_id)
        assert self.group_issuer is not None and self.group_name is not None
        return BindingSubject.for_group(self.group_issuer, self.group_name)


class RevokeProductAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


def _context(request: Request) -> SecurityContext:
    context = getattr(request.state, "security_context", None)
    if not isinstance(context, SecurityContext):
        raise RuntimeError("security dependency did not initialize request state")
    return context


def _unavailable(request: Request) -> IdentityHttpError:
    context = _context(request)
    return IdentityHttpError(
        status=503,
        title="Product access unavailable",
        detail="Product access administration is not configured for this deployment.",
        code="CMP-AUTHZ-0002",
        request_id=context.request_id,
        trace_id=context.trace_id,
        problem_type="urn:cmp:problem:authorization",
    )


def install_product_access_api(
    application: FastAPI,
    *,
    service: ProductAccessAdministrationService | None,
    security_dependency: RequestSecurityContextDependency,
    manage_dependency: RequestAuthorizationDependency,
) -> None:
    common_responses: dict[int | str, dict[str, Any]] = {
        401: {"model": AuthenticationProblem},
        403: {"model": AuthenticationProblem},
    }

    @application.get(
        "/api/v1/product-access/me",
        operation_id="getEffectiveProductAccess",
        response_model=ProductAccessSummaryResponse,
        dependencies=[Depends(security_dependency)],
        responses=common_responses,
        tags=["identity"],
    )
    def get_effective_access(request: Request) -> ProductAccessSummaryResponse:
        if service is None:
            raise _unavailable(request)
        return ProductAccessSummaryResponse.from_domain(service.effective(_context(request)))

    @application.get(
        "/api/v1/product-access/assignments",
        operation_id="listProductAccessAssignments",
        response_model=ProductAccessAssignmentListResponse,
        dependencies=[Depends(security_dependency), Depends(manage_dependency)],
        responses=common_responses,
        tags=["identity"],
    )
    def list_assignments(request: Request) -> ProductAccessAssignmentListResponse:
        if service is None:
            raise _unavailable(request)
        return ProductAccessAssignmentListResponse(
            items=[
                ProductAccessAssignmentResponse.from_domain(item)
                for item in service.list_assignments(_context(request))
            ]
        )

    @application.post(
        "/api/v1/product-access/assignments",
        operation_id="grantProductAccess",
        response_model=ProductAccessAssignmentResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(security_dependency), Depends(manage_dependency)],
        responses={**common_responses, 409: {"model": AuthenticationProblem}},
        tags=["identity"],
    )
    def grant_assignment(
        payload: GrantProductAccessRequest, request: Request, response: Response
    ) -> ProductAccessAssignmentResponse:
        if service is None:
            raise _unavailable(request)
        context = _context(request)
        grants = (
            tuple(sorted(FeatureGrant, key=str))
            if payload.product_role is ProductRole.ADMINISTRATOR
            else tuple(sorted(payload.feature_grants, key=str))
        )
        try:
            assignment = service.grant(
                context,
                GrantProductAccess(
                    organization_id=context.organization_id,
                    project_id=None if payload.organization_wide else context.project_id,
                    subject=payload.subject(),
                    product_role=payload.product_role,
                    feature_grants=grants,
                    max_classification=payload.max_classification,
                    allow_export_controlled=payload.allow_export_controlled,
                    expires_at=payload.expires_at,
                    grant_reason=payload.grant_reason,
                ),
            )
        except RoleBindingConflict as error:
            raise IdentityHttpError(
                status=409,
                title="Product access conflict",
                detail="The subject already has an active product assignment in this scope.",
                code="CMP-AUTHZ-0003",
                request_id=context.request_id,
                trace_id=context.trace_id,
                problem_type="urn:cmp:problem:authorization",
            ) from error
        response.headers["Location"] = f"/api/v1/product-access/assignments/{assignment.id}"
        return ProductAccessAssignmentResponse.from_domain(assignment)

    @application.post(
        "/api/v1/product-access/assignments/{assignment_id}/revoke",
        operation_id="revokeProductAccess",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(security_dependency), Depends(manage_dependency)],
        responses=common_responses,
        tags=["identity"],
    )
    def revoke_assignment(
        assignment_id: UUID, payload: RevokeProductAccessRequest, request: Request
    ) -> Response:
        if service is None:
            raise _unavailable(request)
        service.revoke(
            _context(request),
            RevokeProductAccess(assignment_id=assignment_id, reason=payload.reason),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
