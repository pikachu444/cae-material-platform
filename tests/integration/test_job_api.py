from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4, uuid5

import httpx
from cmp.apps.api import create_app
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp
from cmp.modules.identity_access.adapters.oidc.pyjwt import (
    OidcAccessTokenConfig,
    PyJwtAccessTokenVerifier,
)
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import (
    BindingSubject,
    DataClassification,
    Role,
    RoleBinding,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    SecurityContext,
    VerifiedAccessToken,
)
from cmp.modules.jobs.application.jobs import SubmitResult
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    ImmutableJobSpec,
    JobDetails,
    JobNotFound,
    JobRecord,
    JobState,
    ResourcePolicy,
    RetryKind,
)

PROJECT_ROOT = Path(__file__).parents[2]
ORG = UUID("84000000-0000-4000-8000-000000000001")
PROJECT = UUID("84000000-0000-4000-8000-000000000002")
REQUEST = UUID("84000000-0000-4000-8000-000000000003")
JOB = UUID("84000000-0000-4000-8000-000000000004")
ATTEMPT = UUID("84000000-0000-4000-8000-000000000005")
ACTOR = UUID("84000000-0000-4000-8000-000000000006")
NAMESPACE = UUID("84000000-0000-4000-8000-000000000007")
NOW = datetime(2026, 7, 11, 8, 0, tzinfo=UTC)
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


class _Principals:
    def resolve_or_provision(
        self, token: VerifiedAccessToken, observed_at: datetime
    ) -> Principal:
        del observed_at
        return Principal(
            uuid5(NAMESPACE, f"{token.issuer}\0{token.subject}"),
            token.principal_type,
            token.display_name,
            True,
        )


class _Bindings:
    def __init__(self, binding: RoleBinding) -> None:
        self.binding = binding

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[RoleBinding, ...]:
        del context, observed_at
        return (self.binding,)


def _security(idp: DevelopmentTestIdp) -> SecurityContextService:
    verifier = PyJwtAccessTokenVerifier(
        config=OidcAccessTokenConfig(
            issuer=idp.issuer,
            audience=idp.audience,
            clock_skew_seconds=0,
        ),
        signing_keys=idp.signing_key_resolver(),
    )
    return SecurityContextService(verifier=verifier, principals=_Principals())


def _spec() -> ImmutableJobSpec:
    document = cast(
        dict[str, Any],
        json.loads(
            (PROJECT_ROOT / "contracts/examples/positive/job-spec.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["job_id"] = str(JOB)
    document["attempt_id"] = str(ATTEMPT)
    document["execution"]["deadline"] = "2030-01-01T00:00:00Z"
    return ImmutableJobSpec.from_validated_document(document)


def _details(state: JobState = JobState.QUEUED) -> JobDetails:
    spec = _spec()
    attempt_state = AttemptState(state.value)
    ended_at = NOW if attempt_state in {AttemptState.CANCELLED, AttemptState.TIMED_OUT} else None
    job = JobRecord(
        JOB,
        ORG,
        PROJECT,
        DataClassification.INTERNAL,
        "reference.operation",
        state,
        0,
        NOW,
        ACTOR,
        uuid4(),
        f"00-{uuid4().hex}-{uuid4().hex[:16]}-01",
        spec.deadline,
        ResourcePolicy(1000, 1024, 0, 3),
        1,
        ATTEMPT,
        None,
        None,
        None,
        None,
        NOW,
    )
    attempt = AttemptRecord(
        ATTEMPT,
        JOB,
        1,
        attempt_state,
        RetryKind.INITIAL,
        "initial submission",
        spec,
        None,
        None,
        None,
        None,
        None,
        None,
        ended_at,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    return JobDetails(job, (attempt,))


class _JobService:
    def __init__(self) -> None:
        self.submissions = 0

    def submit(self, context: object, decision: object, command: object) -> SubmitResult:
        del context, decision, command
        self.submissions += 1
        return SubmitResult(_details(), False)

    def get(self, context: object, decision: object, job_id: UUID) -> JobDetails:
        del context, decision
        if job_id != JOB:
            raise JobNotFound(str(job_id))
        return _details()

    def cancel(self, context: object, decision: object, command: object) -> JobDetails:
        del context, decision, command
        return _details(JobState.CANCELLED)

    def retry(self, context: object, decision: object, command: object) -> JobDetails:
        del context, decision, command
        return _details()


def _application() -> tuple[object, DevelopmentTestIdp, _JobService]:
    idp = DevelopmentTestIdp()
    binding = RoleBinding(
        id=uuid5(NAMESPACE, "job-api-binding"),
        organization_id=ORG,
        project_id=PROJECT,
        subject=BindingSubject.for_group(idp.issuer, "job-users"),
        role=Role.TEST_ENGINEER,
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        valid_from=datetime.now(UTC) - timedelta(minutes=1),
    )
    authorization = AuthorizationService(bindings=_Bindings(binding))
    jobs = _JobService()
    application = create_app(
        Settings(environment="test"),
        _security(idp),
        authorization,
        cast(Any, jobs),
    )
    return application, idp, jobs


def _request(
    application: object,
    token: str,
    method: str,
    path: str,
    *,
    body: object | None = None,
    extra_headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=cast(Any, application))
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Request-ID": str(REQUEST),
            "traceparent": TRACE,
            **(extra_headers or {}),
        }
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body, headers=headers)

    return asyncio.run(send())


def _token(idp: DevelopmentTestIdp, *, authorized: bool = True) -> str:
    return idp.issue_user_token(
        subject="job-api-user",
        organization_id=ORG,
        project_id=PROJECT,
        display_name="Job API User",
        groups=("job-users",) if authorized else (),
    )


def test_submit_job_returns_202_location_and_idempotency_metadata() -> None:
    application, idp, jobs = _application()
    body = {
        "job_type": "reference.operation",
        "classification": "internal",
        "job_spec": _spec().document(),
        "resource_policy": {
            "cpu_millis": 1000,
            "memory_mb": 1024,
            "gpu_count": 0,
            "max_attempts": 3,
        },
    }
    response = _request(
        application,
        _token(idp),
        "POST",
        "/api/v1/jobs",
        body=body,
        extra_headers={"Idempotency-Key": str(REQUEST)},
    )

    assert response.status_code == 202
    assert response.headers["location"] == f"/api/v1/jobs/{JOB}"
    assert response.headers["idempotent-replay"] == "false"
    assert response.json()["attempts"][0]["job_spec_digest"] == _spec().digest
    assert jobs.submissions == 1

    invalid = _request(
        application,
        _token(idp),
        "POST",
        "/api/v1/jobs",
        body={"job_type": "reference.operation", "classification": "internal"},
        extra_headers={"Idempotency-Key": str(REQUEST)},
    )
    assert invalid.status_code == 422
    assert invalid.headers["content-type"].startswith("application/problem+json")
    assert invalid.json()["code"] == "CMP-JOB-0002"
    assert jobs.submissions == 1


def test_job_routes_enforce_authorization_and_sanitize_missing_job() -> None:
    application, idp, _ = _application()
    denied = _request(
        application,
        _token(idp, authorized=False),
        "GET",
        f"/api/v1/jobs/{JOB}",
    )
    missing = _request(
        application,
        _token(idp),
        "GET",
        f"/api/v1/jobs/{uuid5(NAMESPACE, 'missing-job')}",
    )

    assert denied.status_code == 403
    assert denied.json()["code"] == "CMP-AUTHZ-0001"
    assert missing.status_code == 404
    assert missing.json()["code"] == "CMP-JOB-0001"
    assert "tenant" in missing.json()["detail"]
