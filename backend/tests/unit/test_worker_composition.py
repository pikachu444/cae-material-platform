from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.apps import worker as worker_module
from cmp.apps.worker import (
    HandlerResult,
    WorkerCycleResult,
    _build_workers,
)
from cmp.bootstrap.demo_identity import DEMO_WORKER_RUNNER_ID
from cmp.bootstrap.security import IdentityServices
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    AuthenticationRequest,
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.jobs.application.jobs import ClaimedAttempt, FinalizeResult
from cmp.modules.jobs.domain.jobs import AttemptState, Failure, FailureCategory
from cmp.modules.modeling.adapters.worker import (
    linear_viscoelastic_calibration_worker as calibration_worker_module,
)
from cmp.modules.modeling.adapters.worker.linear_viscoelastic_calibration_worker import (
    LinearViscoelasticCalibrationWorker,
    WorkerCompositionError,
)

ORG = UUID("84000000-0000-4000-8000-000000000001")
PROJECT = UUID("84000000-0000-4000-8000-000000000002")
ACTOR = UUID("84000000-0000-4000-8000-000000000003")
NOW = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)


class _Security:
    def __init__(self) -> None:
        self.tokens: list[str] = []

    def authenticate(self, request: AuthenticationRequest) -> SecurityContext:
        self.tokens.append(request.access_token)
        return SecurityContext(
            principal=Principal(ACTOR, PrincipalType.SERVICE, "Calibration worker", True),
            organization_id=ORG,
            project_id=PROJECT,
            issuer="urn:test-worker",
            subject="calibration-worker",
            token_id=request.access_token,
            groups=(),
            scopes=(),
            request_id=request.request_id,
            trace_id=request.trace_id,
            authenticated_at=NOW,
        )


class _Authorization:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Permission]] = []

    def authorize(
        self,
        context: SecurityContext,
        permission: Permission,
    ) -> AuthorizationDecision:
        self.calls.append((context.token_id, permission))
        return AuthorizationDecision(
            principal_id=ACTOR,
            organization_id=ORG,
            project_id=PROJECT,
            permission=permission,
            roles=(Role.JOB_RUNNER,),
            database_permissions=database_permissions_for(permission),
            max_classification=DataClassification.INTERNAL,
            allow_export_controlled=False,
            request_id=context.request_id,
            trace_id=context.trace_id,
            decided_at=NOW,
        )


class _IdleJobs:
    def __init__(self) -> None:
        self.accepted: list[tuple[str, ...]] = []
        self.runner_ids: list[UUID] = []

    def claim(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: Any,
    ) -> None:
        del context, decision
        self.accepted.append(command.accepted_job_types)
        self.runner_ids.append(command.runner_id)
        return None


def test_configured_worker_authenticates_each_cycle_and_accepts_only_plugin_run() -> None:
    security = _Security()
    authorization = _Authorization()
    jobs = _IdleJobs()
    tokens = iter(("worker-token-0001", "worker-token-0002"))
    worker = LinearViscoelasticCalibrationWorker(
        jobs=jobs,  # type: ignore[arg-type]
        artifacts=object(),  # type: ignore[arg-type]
        plugins=object(),  # type: ignore[arg-type]
        calibration=object(),  # type: ignore[arg-type]
        security=security,  # type: ignore[arg-type]
        authorization=authorization,  # type: ignore[arg-type]
        access_token=lambda: next(tokens),
    )

    first = asyncio.run(worker.run_once())
    second = asyncio.run(worker.run_once())

    assert first.status == second.status == "idle"
    assert first.handlers_registered == second.handlers_registered == 1
    assert security.tokens == ["worker-token-0001", "worker-token-0002"]
    assert jobs.accepted == [("plugin.run",), ("plugin.run",)]
    assert jobs.runner_ids == [DEMO_WORKER_RUNNER_ID, DEMO_WORKER_RUNNER_ID]
    assert [permission for _, permission in authorization.calls] == [
        Permission.JOB_EXECUTE,
        Permission.PLUGIN_READ,
        Permission.ARTIFACT_READ,
        Permission.ARTIFACT_WRITE,
        Permission.JOB_EXECUTE,
        Permission.PLUGIN_READ,
        Permission.ARTIFACT_READ,
        Permission.ARTIFACT_WRITE,
    ]
    assert all(token == expected for token, expected in zip(
        (call[0] for call in authorization.calls),
        ("worker-token-0001",) * 4 + ("worker-token-0002",) * 4,
        strict=True,
    ))


def test_partial_identity_composition_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        worker_module,
        "build_identity_services",
        lambda settings: IdentityServices(
            None, cast(Any, object()), None, None
        ),
    )

    with pytest.raises(WorkerCompositionError, match="identity composition is partial"):
        _build_workers(Settings())


@pytest.mark.parametrize("outcome", ("success", "failure", "cancel"))
def test_attempt_root_cleanup_runs_for_every_inner_worker_outcome(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    security = _Security()
    authorization = _Authorization()
    jobs = _IdleJobs()
    cleaned: list[bool] = []

    class _Materializer:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def cleanup_all(self) -> None:
            cleaned.append(True)

    class _InnerWorker:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        async def run_once(self) -> WorkerCycleResult:
            if outcome == "failure":
                raise RuntimeError("inner worker failure")
            if outcome == "cancel":
                raise asyncio.CancelledError()
            return WorkerCycleResult(status="succeeded", handlers_registered=1)

    monkeypatch.setattr(
        calibration_worker_module,
        "LinearViscoelasticCalibrationMaterializer",
        _Materializer,
    )
    monkeypatch.setattr(worker_module, "DurableJobWorker", _InnerWorker)
    worker = LinearViscoelasticCalibrationWorker(
        jobs=jobs,  # type: ignore[arg-type]
        artifacts=object(),  # type: ignore[arg-type]
        plugins=object(),  # type: ignore[arg-type]
        calibration=object(),  # type: ignore[arg-type]
        security=security,  # type: ignore[arg-type]
        authorization=authorization,  # type: ignore[arg-type]
        access_token=lambda: "worker-token-0001",
    )

    if outcome == "failure":
        with pytest.raises(RuntimeError, match="inner worker failure"):
            asyncio.run(worker.run_once())
    elif outcome == "cancel":
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(worker.run_once())
    else:
        assert asyncio.run(worker.run_once()).status == "succeeded"
    assert cleaned == [True]


@pytest.mark.parametrize("retry_scheduled", (False, True))
def test_calibration_failure_reconciliation_uses_durable_finalize_disposition(
    retry_scheduled: bool,
) -> None:
    security = _Security()
    authorization = _Authorization()
    calls: list[dict[str, object]] = []

    class _Calibration:
        def record_execution_failure(self, *args: object, **kwargs: object) -> None:
            del args
            calls.append(kwargs)

    worker = LinearViscoelasticCalibrationWorker(
        jobs=_IdleJobs(),  # type: ignore[arg-type]
        artifacts=object(),  # type: ignore[arg-type]
        plugins=object(),  # type: ignore[arg-type]
        calibration=_Calibration(),  # type: ignore[arg-type]
        security=security,  # type: ignore[arg-type]
        authorization=authorization,  # type: ignore[arg-type]
        access_token=lambda: "worker-token-0001",
    )
    run_id = UUID("84000000-0000-4000-8000-000000000010")
    attempt_id = UUID("84000000-0000-4000-8000-000000000011")
    job_id = UUID("84000000-0000-4000-8000-000000000012")
    document = {
        "operation": "execute_plan",
        "extension": {
            "plugin_id": "cmp.linear_viscoelastic.calibrator",
            "package_digest": "sha256:" + "a" * 64,
        },
        "config": {"run_id": str(run_id)},
    }
    claimed = SimpleNamespace(
        job=SimpleNamespace(
            id=job_id,
            job_type="plugin.run",
            submitted_at=NOW,
            deadline=NOW,
        ),
        attempt=SimpleNamespace(
            id=attempt_id,
            attempt_no=2,
            spec=SimpleNamespace(document=lambda: document),
        ),
    )
    result = HandlerResult(
        outcome=AttemptState.FAILED,
        failure=Failure(
            FailureCategory.TRANSIENT_INFRASTRUCTURE,
            "handler_exception",
            "temporary process failure",
        ),
    )
    finalized = SimpleNamespace(retry_scheduled=retry_scheduled)
    context = security.authenticate(
        AuthenticationRequest("worker-token-0001", UUID(int=20), "trace")
    )
    decision = authorization.authorize(context, Permission.JOB_EXECUTE)

    asyncio.run(
        worker._reconcile_after_finalize(
            context,
            decision,
            cast(ClaimedAttempt, claimed),
            result,
            cast(FinalizeResult, finalized),
        )
    )

    assert calls and calls[0]["run_id"] == run_id
    assert calls[0]["attempt_id"] == attempt_id
    assert calls[0]["retry_scheduled"] is retry_scheduled
