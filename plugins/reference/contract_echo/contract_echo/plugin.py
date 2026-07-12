"""Seven contract-only extension entrypoints sharing one generic echo implementation."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import ClassVar

from cmp_plugin_sdk import (
    Diagnostic,
    DiagnosticSeverity,
    ExtensionDescriptor,
    ExtensionOutcome,
    ExtensionStatus,
    ExtensionType,
    RunContext,
    RunnerJobSpec,
    ValidationReport,
)


class _ContractEcho:
    extension_type: ClassVar[ExtensionType]

    def describe(self) -> ExtensionDescriptor:
        return ExtensionDescriptor(self.extension_type, ("contract_echo",))

    def validate_job(self, job: RunnerJobSpec) -> ValidationReport:
        if job.operation != "run":
            return ValidationReport.reject(
                Diagnostic(
                    "CMP-TCK-0001",
                    DiagnosticSeverity.ERROR,
                    "Synthetic contract fixture supports operation 'run' only.",
                )
            )
        return ValidationReport.ok()

    def run(self, context: RunContext, job: RunnerJobSpec) -> ExtensionOutcome:
        behavior = str(job.config.get("behavior", "echo"))
        if behavior == "network":
            socket.create_connection(("127.0.0.1", 9), timeout=0.1)
        elif behavior == "process":
            subprocess.run(["forbidden-child-process"], check=False)
        elif behavior == "path_traversal":
            context.temporary_path("../escape")
        elif behavior == "ambient_read":
            workspace_probe = context.temporary_path("probe")
            Path(workspace_probe.parent.parent / "job-spec.json").read_bytes()
        elif behavior == "symlink":
            os.symlink("outside", context.temporary_path("linked"))
        elif behavior == "hang":
            while True:
                time.sleep(0.05)
        elif behavior == "cancel":
            while True:
                context.raise_if_cancelled()
                time.sleep(0.01)

        if behavior == "rng":
            payload = str(context.rng.getrandbits(64)).encode("ascii")
        elif behavior == "oversize":
            payload = b"x" * int(job.config.get("output_bytes", 1024))
        elif job.inputs:
            payload = context.read_input(job.inputs[0].role)
        else:
            payload = b"contract-echo"
        media_type = str(job.config.get("media_type", "application/octet-stream"))
        for expected in job.expected_outputs:
            context.write_output(
                role=expected.role,
                media_type=media_type,
                schema_ref=expected.schema_ref,
                data=payload,
            )
        return ExtensionOutcome(
            ExtensionStatus.FAILED
            if behavior == "failed_output"
            else ExtensionStatus.SUCCEEDED
        )


class ImporterExtension(_ContractEcho):
    extension_type = ExtensionType.IMPORTER


class ProcessorExtension(_ContractEcho):
    extension_type = ExtensionType.PROCESSOR


class StatisticalAnalyzerExtension(_ContractEcho):
    extension_type = ExtensionType.STATISTICAL_ANALYZER


class MaterialModelExtension(_ContractEcho):
    extension_type = ExtensionType.MATERIAL_MODEL


class CalibratorExtension(_ContractEcho):
    extension_type = ExtensionType.CALIBRATOR


class ValidatorExtension(_ContractEcho):
    extension_type = ExtensionType.VALIDATOR


class SolverExporterExtension(_ContractEcho):
    extension_type = ExtensionType.SOLVER_EXPORTER
