"""PostgreSQL evidence for atomic Neutral target delivery (UXC-06C2).

The fixture deliberately uses the non-bypass ``cmp_app`` role.  A concrete
Neutral Material and current Materials Record binding are seeded by the admin
connection, then the card revision, lifecycle projection, Catalog binding,
outbox event, and immutable receipt are written through the real SQL adapters
under the ``EXPORT_EXECUTE`` RLS capability closure.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.catalog.adapters.persistence.records import SqlAlchemyCatalogRecordRepository
from cmp.modules.catalog.domain.records import CatalogRecordQuery
from cmp.modules.exporting.adapters.persistence.neutral_hyperelastic_repository import (
    SqlAlchemyNeutralHyperelasticExportingRepository,
    neutral_solver_card_revision_table,
    neutral_solver_card_table,
)
from cmp.modules.exporting.adapters.persistence.target_delivery_receipts import (
    SqlTargetDeliveryReceiptRecorder,
    delivery_receipt_table,
)
from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    NEUTRAL_SOLVER_CARD_PROFILE_SCHEMA_ID,
    NEUTRAL_SOLVER_CARD_PROFILE_SCHEMA_VERSION,
    NEUTRAL_SOLVER_CARD_SCHEMA_ID,
    NEUTRAL_SOLVER_CARD_SCHEMA_VERSION,
    CreateNeutralHyperelasticSolverCard,
    NeutralHyperelasticSolverCardSnapshot,
)
from cmp.modules.exporting.application.service import RevisionSnapshot
from cmp.modules.exporting.application.target_delivery import (
    CreateTargetDelivery,
    TargetDeliveryConflict,
    TargetDeliveryService,
)
from cmp.modules.exporting.application.target_preview import TargetPreview, TargetPreviewService
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    ABAQUS_EXPORTER_ID,
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticSolverCardContent,
)
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.jobs.adapters.persistence.events import SqlAlchemyOutboxWriter
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import NeutralHyperelasticParameters
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyRevisionProvenanceHook,
)
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.review_release.adapters.persistence.publication import (
    review_publication_projection_table,
)
from cmp.modules.units.adapters.persistence.profiles import SqlAlchemyUnitProfileRepository
from cmp.modules.units.application.profiles import CommonUnitService, CreateUnitProfile
from cmp.modules.units.domain.profiles import (
    UnitApplication,
    UnitApplicationRole,
    UnitProfileContent,
    UnitProfilePin,
    UnitProfileSelection,
)
from cmp.modules.units.domain.system import DimensionId
from cmp.shared.application.revisions import CreateRevisionedAggregate, RevisionService
from cmp.shared.domain.revisions import TenantScope, content_sha256
from sqlalchemy.engine import URL, CursorResult, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")
pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
ORG = UUID("76000000-0000-4000-8000-000000000101")
PROJECT = UUID("76000000-0000-4000-8000-000000000102")
ACTOR = UUID("76000000-0000-4000-8000-000000000103")
SCHEMA_ID = UUID("76000000-0000-4000-8000-000000000104")
SCHEMA_REVISION_ID = UUID("76000000-0000-4000-8000-000000000105")
RECORD_ID = UUID("76000000-0000-4000-8000-000000000106")
RECORD_REVISION_ID = UUID("76000000-0000-4000-8000-000000000107")
MATERIAL_ID = UUID("76000000-0000-4000-8000-000000000108")
MATERIAL_REVISION_ID = UUID("76000000-0000-4000-8000-000000000109")
STATE_ID = UUID("76000000-0000-4000-8000-00000000010a")
STATE_REVISION_ID = UUID("76000000-0000-4000-8000-00000000010b")
PROPERTY_SET_ID = UUID("76000000-0000-4000-8000-00000000010c")
PROPERTY_SET_REVISION_ID = UUID("76000000-0000-4000-8000-00000000010d")
ARTIFACT_PENDING_ID = UUID("76000000-0000-4000-8000-00000000010e")
ARTIFACT_ID = UUID("76000000-0000-4000-8000-00000000010f")
NEUTRAL_ID = UUID("76000000-0000-4000-8000-000000000110")
NEUTRAL_REVISION_ID = UUID("76000000-0000-4000-8000-000000000111")
NO_BINDING_NEUTRAL_ID = UUID("76000000-0000-4000-8000-000000000112")
NO_BINDING_NEUTRAL_REVISION_ID = UUID("76000000-0000-4000-8000-000000000113")
NEUTRAL_CANDIDATE_ID = UUID("76000000-0000-4000-8000-000000000114")
NO_BINDING_CANDIDATE_ID = UUID("76000000-0000-4000-8000-000000000115")
MATERIAL_BINDING_ID = UUID("76000000-0000-4000-8000-000000000116")
NEUTRAL_BINDING_ID = UUID("76000000-0000-4000-8000-000000000117")
MODEL_IR_REVISION_ID = UUID("76000000-0000-4000-8000-000000000118")
PROCESSING_OUTPUT_ID = UUID("76000000-0000-4000-8000-000000000119")
PROCESSING_OUTPUT_REVISION_ID = UUID("76000000-0000-4000-8000-00000000011a")
CARD_ID = UUID("76000000-0000-4000-8000-000000000120")
PROFILE_CARD_ID = UUID("76000000-0000-4000-8000-000000000128")
LEGACY_COMPAT_CARD_ID = UUID("76000000-0000-4000-8000-000000000129")
UNIT_PROFILE_ID = UUID("76000000-0000-4000-8000-00000000012a")
MODEL_ID = UUID("76000000-0000-4000-8000-000000000121")
MODEL_REVISION_ID = UUID("76000000-0000-4000-8000-000000000122")
REVIEW_CARD_REQUEST_ID = UUID("76000000-0000-4000-8000-000000000123")
REVIEW_MODEL_REQUEST_ID = UUID("76000000-0000-4000-8000-000000000124")
REVIEW_RECORD_REQUEST_ID = UUID("76000000-0000-4000-8000-000000000125")
REVIEW_SOLVER_CARD_ID = UUID("76000000-0000-4000-8000-000000000126")
REVIEW_SOLVER_CARD_REVISION_ID = UUID("76000000-0000-4000-8000-000000000127")
REQUEST_ID = UUID("76000000-0000-4000-8000-00000000011b")
TRACE_ID = "target-delivery-fixture"
NEUTRAL_SHA = "a" * 64
REPORT_SHA = "b" * 64
EXPORTER_SHA = "c" * 64
RECORD_SHA = "d" * 64
ARTIFACT_SHA = "e" * 64
TARGET = NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s")
CARD_TEXT = "*MATERIAL, NAME=TARGET_CARD\n*HYPERELASTIC, NEO HOOKE\n"
CARD_SHA = hashlib.sha256(CARD_TEXT.encode("utf-8")).hexdigest()
REFERENCE_MODEL_DIGEST = "a4e39b23b5d656abb50399b1ae76b799e01872f4f6ebe44a59bc8c901b622cd6"
REFERENCE_EXPORTER_DIGEST = "65a3f7ea55150a9c660b4303d12a168d8366bb1e41c6c86684a1e8a2fde20a20"


def _psycopg_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return url


def _alembic_config(database_url: URL) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return config


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Target delivery user", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://target-delivery.invalid",
        subject=str(ACTOR),
        token_id=str(ACTOR),
        groups=(),
        scopes=("openid",),
        request_id=REQUEST_ID,
        trace_id=TRACE_ID,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.EXPORT_EXECUTE,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(Permission.EXPORT_EXECUTE),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _artifact_seed(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            """
            INSERT INTO artifact.artifact_pending (
              organization_id, project_id, id, classification, state, artifact_kind,
              artifact_role, schema_ref, media_type, expected_size_bytes, expected_sha256,
              staging_object_key, final_object_key, encryption_profile, source_raw_asset_id,
              idempotency_key, submission_digest, reserved_artifact_id, available_artifact_id,
              attempt_count, failure_code, created_at, created_by, request_id, trace_id,
              updated_at, terminal_at
            ) VALUES (
              :org, :project, :pending, :classification, 'pending', 'derived',
              'target.neutral-evidence', 'urn:cmp:target-delivery:fixture', 'application/json',
              2, :digest, :staging,
              artifact.content_object_key(:org, :project, CAST(:key_classification AS text),
                                          CAST(:key_digest AS text)),
              'none', NULL, :idempotency, :digest, :artifact, NULL, 0, NULL,
              :now, :actor, :request, :trace, :now, NULL
            )
            """
        ),
        {
            "org": ORG,
            "project": PROJECT,
            "pending": ARTIFACT_PENDING_ID,
            "classification": DataClassification.INTERNAL.value,
            "digest": ARTIFACT_SHA,
            "key_classification": DataClassification.INTERNAL.value,
            "key_digest": ARTIFACT_SHA,
            "staging": f"staging/{ARTIFACT_PENDING_ID}",
            "idempotency": "target-delivery:artifact",
            "artifact": ARTIFACT_ID,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
        },
    )
    connection.execute(
        sa.text(
            """UPDATE artifact.artifact_pending SET state='promoting', attempt_count=1,
                    updated_at=:now WHERE organization_id=:org AND project_id=:project AND id=:id"""
        ),
        {"org": ORG, "project": PROJECT, "id": ARTIFACT_PENDING_ID, "now": NOW},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO artifact.artifact (
              organization_id, project_id, id, classification, artifact_kind, artifact_role,
              schema_ref, media_type, size_bytes, sha256, storage_key, encryption_profile,
              source_raw_asset_id, source_pending_id, created_at, created_by
            ) VALUES (
              :org, :project, :artifact, :classification, 'derived', 'target.neutral-evidence',
              'urn:cmp:target-delivery:fixture', 'application/json', 2, :digest,
              artifact.content_object_key(:org, :project, CAST(:key_classification AS text),
                                          CAST(:key_digest AS text)),
              'none', NULL, :pending, :now, :actor
            )
            """
        ),
        {
            "org": ORG,
            "project": PROJECT,
            "artifact": ARTIFACT_ID,
            "classification": DataClassification.INTERNAL.value,
            "digest": ARTIFACT_SHA,
            "key_classification": DataClassification.INTERNAL.value,
            "key_digest": ARTIFACT_SHA,
            "pending": ARTIFACT_PENDING_ID,
            "now": NOW,
            "actor": ACTOR,
        },
    )
    connection.execute(
        sa.text(
            """UPDATE artifact.artifact_pending
               SET state='available', available_artifact_id=:artifact, updated_at=:now,
                   terminal_at=:now
             WHERE organization_id=:org AND project_id=:project AND id=:pending"""
        ),
        {
            "org": ORG,
            "project": PROJECT,
            "pending": ARTIFACT_PENDING_ID,
            "artifact": ARTIFACT_ID,
            "now": NOW,
        },
    )


def _catalog_seed(connection: sa.Connection) -> None:
    classification = DataClassification.INTERNAL.value
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.schema_table
              (id, organization_id, project_id, classification, current_revision_id,
               created_at, created_by, updated_at, table_key)
            VALUES (:id, :org, :project, :classification, :revision, :now, :actor, :now,
                    'target_delivery_materials')
            """
        ),
        {
            "id": SCHEMA_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "revision": SCHEMA_REVISION_ID,
            "now": NOW,
            "actor": ACTOR,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.schema_table_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, table_key, name, description
            ) VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:catalog:schema-table', '1.0.0', :digest, :now, :actor,
              'target delivery fixture schema', :request, :trace,
              'target_delivery_materials', 'Target Delivery Materials', 'fixture')
            """
        ),
        {
            "revision": SCHEMA_REVISION_ID,
            "id": SCHEMA_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": "1" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.catalog_record
              (id, organization_id, project_id, classification, current_revision_id,
               created_at, created_by, updated_at, table_id)
            VALUES (:id, :org, :project, :classification, :revision, :now, :actor, :now, :table)
            """
        ),
        {
            "id": RECORD_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "revision": RECORD_REVISION_ID,
            "now": NOW,
            "actor": ACTOR,
            "table": SCHEMA_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.catalog_record_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, table_id, table_revision_id,
              name, external_key, description
            ) VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:catalog:record', '1.0.0', :digest, :now, :actor,
              'target delivery fixture record', :request, :trace, :table, :table_revision,
              'Target Delivery Record', 'target-delivery-record', 'fixture')
            """
        ),
        {
            "revision": RECORD_REVISION_ID,
            "id": RECORD_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": RECORD_SHA,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
            "table": SCHEMA_ID,
            "table_revision": SCHEMA_REVISION_ID,
        },
    )
    # The Neutral revision references an exact Material/State/Property Set chain.
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.material
              (id, organization_id, project_id, classification, current_revision_id,
               created_at, created_by, updated_at)
            VALUES (:id, :org, :project, :classification, :revision, :now, :actor, :now)
            """
        ),
        {
            "id": MATERIAL_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "revision": MATERIAL_REVISION_ID,
            "now": NOW,
            "actor": ACTOR,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.material_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, name, material_code,
              material_family, description
            ) VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:catalog:material', '1.0.0', :digest, :now, :actor,
              'target delivery fixture material', :request, :trace, 'Target Material',
              'TARGET-160', 'synthetic', 'fixture')
            """
        ),
        {
            "revision": MATERIAL_REVISION_ID,
            "id": MATERIAL_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": "2" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.material_state
              (id, organization_id, project_id, classification, current_revision_id,
               created_at, created_by, updated_at, material_id)
            VALUES (:id, :org, :project, :classification, :revision, :now, :actor, :now, :material)
            """
        ),
        {
            "id": STATE_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "revision": STATE_REVISION_ID,
            "now": NOW,
            "actor": ACTOR,
            "material": MATERIAL_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.material_state_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, material_id,
              material_revision_id, name, manufacturing_route, heat_treatment, lot_or_batch,
              description
            ) VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:catalog:material-state', '1.0.0', :digest, :now, :actor,
              'target delivery fixture state', :request, :trace, :material, :material_revision,
              'Target State', 'reference', NULL, 'LOT-160', 'fixture')
            """
        ),
        {
            "revision": STATE_REVISION_ID,
            "id": STATE_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": "3" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
            "material": MATERIAL_ID,
            "material_revision": MATERIAL_REVISION_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.property_set
              (id, organization_id, project_id, classification, current_revision_id,
               created_at, created_by, updated_at, material_state_id)
            VALUES (:id, :org, :project, :classification, :revision, :now, :actor, :now, :state)
            """
        ),
        {
            "id": PROPERTY_SET_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "revision": PROPERTY_SET_REVISION_ID,
            "now": NOW,
            "actor": ACTOR,
            "state": STATE_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.property_set_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, material_state_id,
              material_state_revision_id, density_kg_per_m3, density_source_kind,
              density_source_reference, youngs_modulus_pa, youngs_modulus_source_kind,
              youngs_modulus_source_reference, poisson_ratio, poisson_ratio_source_kind,
              poisson_ratio_source_reference, yield_stress_pa, yield_stress_source_kind,
              yield_stress_source_reference
            ) VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:catalog:property-set', '1.0.0', :digest, :now, :actor,
              'target delivery fixture properties', :request, :trace, :state, :state_revision,
              1100, 'manual', NULL, 1000000000, 'manual', NULL, 0.3, 'manual', NULL,
              NULL, NULL, NULL)
            """
        ),
        {
            "revision": PROPERTY_SET_REVISION_ID,
            "id": PROPERTY_SET_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": "4" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
            "state": STATE_ID,
            "state_revision": STATE_REVISION_ID,
        },
    )


def _neutral_seed(
    connection: sa.Connection,
    *,
    neutral_id: UUID,
    revision_id: UUID,
    candidate_id: UUID,
) -> None:
    classification = DataClassification.INTERNAL.value
    connection.execute(
        sa.text(
            """
            INSERT INTO modeling.neutral_material (
              id, organization_id, project_id, classification, material_state_id,
              current_revision_id, created_at, created_by, updated_at
            ) VALUES (:id, :org, :project, :classification, :state, :revision, :now, :actor, :now)
            """
        ),
        {
            "id": neutral_id,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "state": STATE_ID,
            "revision": revision_id,
            "now": NOW,
            "actor": ACTOR,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO modeling.neutral_material_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, document_artifact_id,
              document_artifact_sha256, document_content_sha256, material_id,
              material_revision_id, material_state_id, material_state_revision_id,
              property_set_id, property_set_revision_id, calibration_plan_id,
              calibration_plan_revision_id, scientific_profile_id,
              scientific_profile_revision_id, mapping_profile_status, mapping_profile_reason,
              mapping_profile_id, mapping_profile_revision_id, processing_recipe_status,
              processing_recipe_reason, processing_recipe_id, processing_recipe_revision_id,
              calibration_run_id, family_candidate_id, candidate_sha256, selection_reason,
              diagnostics_artifact_id, diagnostics_sha256, family, c10_pa, c01_pa, c20_pa,
              c30_pa, ogden_mu_pa, ogden_alpha, density_kg_per_m3, applicable_strain_min,
              applicable_strain_max, validation_status, model_schema_digest, maturity,
              non_production, model_family, selection_kind, processing_output_id,
              processing_output_revision_id, processing_output_sha256, selected_series,
              candidate_families, primary_family, secondary_family, primary_weight,
              youngs_modulus_pa, poisson_ratio, initial_yield_stress_pa,
              hardening_curve_artifact_id, hardening_curve_sha256, hardening_curve_schema_ref,
              hardening_curve_point_count, characterized_strain_max, extension_strain_max,
              extrapolation_policy, approximation_acknowledged, bulk_relaxation_status,
              reference_temperature_k, applicable_time_min_s, applicable_time_max_s,
              prony_overlay_status, prony_overlay_reason, prony_overlay_model_id,
              prony_overlay_model_revision_id, prony_selection_mode, prony_selected_term_count,
              prony_normalized_rmse, prony_bic, prony_fitted_g0_pa, prony_catalog_g0_pa,
              prony_relative_mismatch, prony_acknowledged_max_mismatch
            ) VALUES (
              :revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:modeling:neutral-material', '1.0.0', :digest, :now, :actor,
              'target delivery Neutral fixture', :request, :trace, :artifact, :artifact_sha,
              :artifact_sha, :material, :material_revision, :state, :state_revision,
              :property_set, :property_set_revision, NULL, NULL, NULL, NULL,
              'not_applicable', 'no mapping profile in fixture', NULL, NULL,
              'not_applicable', 'no processing recipe in fixture', NULL, NULL,
              :run, :candidate, :candidate_sha, 'synthetic target-delivery evidence',
              :artifact, :artifact_sha, 'isotropic_tabulated_plasticity', NULL, NULL, NULL,
               NULL, NULL, NULL, 1100, 0, 0.2, 'validated', :model_schema_digest,
              'reference', true, 'isotropic_tabulated_plasticity', 'candidate', NULL,
              NULL, NULL, NULL, ARRAY['isotropic_tabulated_plasticity','neo_hookean'],
              'isotropic_tabulated_plasticity', 'neo_hookean', 0.8, 1000000000, 0.3,
              100000000, :artifact, :artifact_sha, 'urn:cmp:curve:hardening', 2,
               0.2, 0.3, 'bounded fixture extension', true, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
            )
            """
        ),
        {
            "revision": revision_id,
            "id": neutral_id,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": "5" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
            "artifact": ARTIFACT_ID,
            "artifact_sha": ARTIFACT_SHA,
            "material": MATERIAL_ID,
            "material_revision": MATERIAL_REVISION_ID,
            "state": STATE_ID,
            "state_revision": STATE_REVISION_ID,
            "property_set": PROPERTY_SET_ID,
            "property_set_revision": PROPERTY_SET_REVISION_ID,
            "run": UUID(int=0x900),
            "candidate": candidate_id,
            "candidate_sha": "6" * 64,
            "model_schema_digest": "7" * 64,
        },
    )


def _binding_seed(connection: sa.Connection) -> None:
    classification = DataClassification.INTERNAL.value
    values = {
        "org": ORG,
        "project": PROJECT,
        "classification": classification,
        "kind": "neutral_material",
        "object": NEUTRAL_ID,
        "revision": NEUTRAL_REVISION_ID,
        "record": RECORD_ID,
        "now": NOW,
        "actor": ACTOR,
        "request": REQUEST_ID,
        "trace": TRACE_ID,
        "id": NEUTRAL_BINDING_ID,
    }
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.domain_record_identity_binding (
              organization_id, project_id, classification, domain_kind, domain_object_id,
              domain_revision_id, record_id, created_at, created_by, request_id, trace_id
            ) VALUES (:org, :project, :classification, :kind, :object, :revision,
                      :record, :now, :actor, :request, :trace)
            """
        ),
        values,
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.domain_record_binding (
              id, organization_id, project_id, classification, record_id, record_revision_id,
              domain_kind, domain_object_id, domain_revision_id, created_at, created_by,
              request_id, trace_id
            ) VALUES (:id, :org, :project, :classification, :record, :record_revision,
                      :kind, :object, :revision, :now, :actor, :request, :trace)
            """
        ),
        {**values, "record_revision": RECORD_REVISION_ID},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.domain_record_identity_binding (
              organization_id, project_id, classification, domain_kind, domain_object_id,
              domain_revision_id, record_id, created_at, created_by, request_id, trace_id
            ) VALUES (:org, :project, :classification, 'material', :object, :revision,
                      :record, :now, :actor, :request, :trace)
            """
        ),
        {
            **values,
            "object": MATERIAL_ID,
            "revision": MATERIAL_REVISION_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO catalog.domain_record_binding (
              id, organization_id, project_id, classification, record_id, record_revision_id,
              domain_kind, domain_object_id, domain_revision_id, created_at, created_by,
              request_id, trace_id
            ) VALUES (:id, :org, :project, :classification, :record, :record_revision,
                      'material', :object, :revision, :now, :actor, :request, :trace)
            """
        ),
        {
            **values,
            "id": MATERIAL_BINDING_ID,
            "object": MATERIAL_ID,
            "revision": MATERIAL_REVISION_ID,
            "record_revision": RECORD_REVISION_ID,
        },
    )


def _review_subject_seed(connection: sa.Connection) -> None:
    """Seed current model/card heads used by the publication fail-closed regression."""

    classification = DataClassification.INTERNAL.value
    connection.execute(
        sa.text(
            """
            INSERT INTO modeling.material_model (
              id, organization_id, project_id, classification, current_revision_id,
              created_at, created_by, updated_at, material_state_id
            ) VALUES (
              :id, :org, :project, :classification, :revision,
              :now, :actor, :now, :state
            )
            """
        ),
        {
            "id": MODEL_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "revision": MODEL_REVISION_ID,
            "now": NOW,
            "actor": ACTOR,
            "state": STATE_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO modeling.material_model_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, model_family_id,
              model_schema_digest, material_id, material_revision_id, material_state_id,
              material_state_revision_id, property_set_id, property_set_revision_id,
              density_kg_per_m3, youngs_modulus_pa, poisson_ratio, source_yield_stress_pa,
              applicable_temperature_min_k, applicable_temperature_max_k,
              applicable_strain_rate_min_per_s, applicable_strain_rate_max_per_s,
              applicability_note, reference_temperature_k, non_production,
              calibration_evidence_kind
            ) VALUES (
              :revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:modeling:material-model', '1.0.0', :digest, :now, :actor,
              'issue 160 publication regression model', :request, :trace,
              'urn:cmp:reference:isotropic-linear-elasticity:1.0.0', :model_digest,
              :material, :material_revision, :state, :state_revision,
              :property_set, :property_set_revision, 7850, 210000000000, 0.3,
              355000000, 250, 450, 0, 10, 'synthetic regression model', 293.15, true,
              'manual_catalog_projection'
            )
            """
        ),
        {
            "revision": MODEL_REVISION_ID,
            "id": MODEL_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": "1" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
            "model_digest": REFERENCE_MODEL_DIGEST,
            "material": MATERIAL_ID,
            "material_revision": MATERIAL_REVISION_ID,
            "state": STATE_ID,
            "state_revision": STATE_REVISION_ID,
            "property_set": PROPERTY_SET_ID,
            "property_set_revision": PROPERTY_SET_REVISION_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO exporting.solver_card (
              id, organization_id, project_id, classification, current_revision_id,
              created_at, created_by, updated_at, material_model_id, target_solver,
              target_version, target_unit_system, solver_material_id
            ) VALUES (
              :id, :org, :project, :classification, :revision,
              :now, :actor, :now, :model, 'openradioss', '2025', 'kg_m_s', 160
            )
            """
        ),
        {
            "id": REVIEW_SOLVER_CARD_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "revision": REVIEW_SOLVER_CARD_REVISION_ID,
            "now": NOW,
            "actor": ACTOR,
            "model": MODEL_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO exporting.solver_card_revision (
              id, aggregate_id, organization_id, project_id, classification, revision_no,
              based_on_revision_id, schema_id, schema_version, content_hash, created_at,
              created_by, change_reason, request_id, trace_id, material_model_id,
              material_model_revision_id, model_schema_digest, target_solver, target_version,
              target_unit_system, solver_material_id, card_title, density_kg_per_m3,
              youngs_modulus_pa, poisson_ratio, source_yield_stress_pa,
              applicable_temperature_min_k, applicable_temperature_max_k,
              applicable_strain_rate_min_per_s, applicable_strain_rate_max_per_s,
              density_mapping_status, youngs_modulus_mapping_status,
              poisson_ratio_mapping_status, source_yield_mapping_status,
              temperature_applicability_mapping_status, strain_rate_applicability_mapping_status,
              unit_system_mapping_status, mapping_report_sha256, card_text, card_sha256,
              exporter_id, exporter_version, exporter_digest, non_production
            ) VALUES (
              :revision, :id, :org, :project, :classification, 1, NULL,
              'urn:cmp:exporting:solver-card', '1.0.0', :digest, :now, :actor,
              'issue 160 publication regression card', :request, :trace,
              :model, :model_revision, :model_digest, 'openradioss', '2025', 'kg_m_s', 160,
              'Issue 160 regression card', 7850, 210000000000, 0.3, 355000000,
              250, 450, 0, 10, 'exact', 'exact', 'exact', 'exact', 'exact', 'exact', 'exact',
              :report_digest, :card_text, :card_digest,
              'cmp.reference.openradioss-elast', '1.0.0', :exporter_digest, true
            )
            """
        ),
        {
            "revision": REVIEW_SOLVER_CARD_REVISION_ID,
            "id": REVIEW_SOLVER_CARD_ID,
            "org": ORG,
            "project": PROJECT,
            "classification": classification,
            "digest": "2" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request": REQUEST_ID,
            "trace": TRACE_ID,
            "model": MODEL_ID,
            "model_revision": MODEL_REVISION_ID,
            "model_digest": REFERENCE_MODEL_DIGEST,
            "report_digest": "3" * 64,
            "card_text": CARD_TEXT,
            "card_digest": CARD_SHA,
            "exporter_digest": REFERENCE_EXPORTER_DIGEST,
        },
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[tuple[Engine, Engine]]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_target_delivery_{uuid4().hex}"
    cluster_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: Engine | None = None
    try:
        command.upgrade(_alembic_config(database_url), "head")
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE ROLE cmp_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOBYPASSRLS"
            )
            connection.exec_driver_sql(
                "GRANT USAGE ON SCHEMA governance, revisioning, access_control, catalog, "
                "identity, datasets, modeling, exporting, processing, testing, artifact, events, "
                "provenance, units, plugin TO cmp_app"
            )
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA governance, catalog, "
                "exporting, events, provenance, units TO cmp_app"
            )
            connection.exec_driver_sql(
                "GRANT SELECT ON ALL TABLES IN SCHEMA identity, datasets, modeling, processing, "
                "testing, artifact, plugin TO cmp_app"
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA revisioning, access_control TO cmp_app"
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO identity.principal
                      (id, principal_type, display_name, active, created_at, updated_at)
                    VALUES (:actor, 'user', 'Target delivery user', true, :now, :now)
                    """
                ),
                {"actor": ACTOR, "now": NOW},
            )
            _artifact_seed(connection)
            _catalog_seed(connection)
            _neutral_seed(
                connection,
                neutral_id=NEUTRAL_ID,
                revision_id=NEUTRAL_REVISION_ID,
                candidate_id=NEUTRAL_CANDIDATE_ID,
            )
            _neutral_seed(
                connection,
                neutral_id=NO_BINDING_NEUTRAL_ID,
                revision_id=NO_BINDING_NEUTRAL_REVISION_ID,
                candidate_id=NO_BINDING_CANDIDATE_ID,
            )
            _binding_seed(connection)
            _review_subject_seed(connection)
        app_engine = sa.create_engine(database_url.set(username="cmp_app"))
        yield admin_engine, app_engine
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster_engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql("DROP ROLE IF EXISTS cmp_app")
        cluster_engine.dispose()


class _PreviewService:
    def __init__(self, preview: TargetPreview) -> None:
        self.preview = preview

    async def preview_for_delivery(self, *_: object, **__: object) -> TargetPreview:
        return self.preview


class _Cards:
    def __init__(
        self,
        *,
        repository: SqlAlchemyNeutralHyperelasticExportingRepository,
        neutral_id: UUID = NEUTRAL_ID,
        neutral_revision_id: UUID = NEUTRAL_REVISION_ID,
        card_id: UUID = CARD_ID,
        unit_applications: tuple[UnitApplication, ...] = (),
    ) -> None:
        self.repository = repository
        self.neutral_id = neutral_id
        self.neutral_revision_id = neutral_revision_id
        self.card_id = card_id
        self.unit_applications = unit_applications
        self.calls = 0

    async def create_card(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        _command: object,
        additional_hooks: tuple[object, ...] = (),
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, SimpleNamespace]:
        self.calls += 1
        command_value = cast(CreateNeutralHyperelasticSolverCard, _command)
        content = NeutralHyperelasticSolverCardContent(
            neutral_material_id=self.neutral_id,
            neutral_material_revision_id=self.neutral_revision_id,
            neutral_material_sha256=NEUTRAL_SHA,
            family=HyperelasticFamily.NEO_HOOKEAN,
            target=TARGET,
            solver_material_id=901,
            material_name="TARGET_CARD",
            density_kg_per_m3=1100.0,
            parameters=NeutralHyperelasticParameters(
                HyperelasticFamily.NEO_HOOKEAN,
                c10_pa=1_000_000.0,
            ),
            applicable_strain_min=0.0,
            applicable_strain_max=0.2,
            mapping_statuses=(
                ("density", "exact"),
                ("constitutive_parameters", "exact"),
                ("volumetric_response", "exact"),
                ("applicability", "exact"),
                ("calibration_evidence", "exact"),
                ("unit_system", "exact"),
            ),
            mapping_report_sha256=REPORT_SHA,
            card_text=CARD_TEXT,
            card_sha256=CARD_SHA,
            exporter_id=ABAQUS_EXPORTER_ID,
            exporter_version="1.0.0",
            exporter_digest=EXPORTER_SHA,
            unit_profile=command_value.unit_profile,
            unit_applications=self.unit_applications,
        )
        record = RevisionService(
            aggregate_type="exporting.neutral_solver_card",
            store=self.repository.solver_card_store(
                context=context,
                decision=decision,
                additional_hooks=additional_hooks,  # type: ignore[arg-type]
                unit_profile=command_value.unit_profile,
                unit_applications=self.unit_applications,
            ),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=self.card_id,
                scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
                schema_id=(
                    NEUTRAL_SOLVER_CARD_SCHEMA_ID
                    if command_value.unit_profile is None
                    else NEUTRAL_SOLVER_CARD_PROFILE_SCHEMA_ID
                ),
                schema_version=(
                    NEUTRAL_SOLVER_CARD_SCHEMA_VERSION
                    if command_value.unit_profile is None
                    else NEUTRAL_SOLVER_CARD_PROFILE_SCHEMA_VERSION
                ),
                content=content,
                created_by=ACTOR,
                change_reason="Deliver exact target artifact",
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        snapshot = NeutralHyperelasticSolverCardSnapshot(
            record.aggregate_id,
            content.neutral_material_id,
            TARGET,
            content.solver_material_id,
            content.material_name,
            RevisionSnapshot(record, content),
            command_value.unit_profile,
            self.unit_applications,
        )
        return snapshot, SimpleNamespace(digest=REPORT_SHA)


def _preview(
    *,
    neutral_id: UUID = NEUTRAL_ID,
    neutral_revision_id: UUID = NEUTRAL_REVISION_ID,
    preview_identity: str = "1" * 64,
    unit_profile: UnitProfilePin | None = None,
    unit_applications: tuple[UnitApplication, ...] = (),
) -> TargetPreview:
    return TargetPreview(
        preview_identity=preview_identity,
        filename="TARGET_CARD-abaqus-2025.inp",
        native_text=CARD_TEXT,
        native_sha256=CARD_SHA,
        mapping_report_sha256=REPORT_SHA,
        mapping={"items": [{"status": "exact"}]},
        source={
            "processing_output_id": str(PROCESSING_OUTPUT_ID),
            "processing_output_revision_id": str(PROCESSING_OUTPUT_REVISION_ID),
            "processing_output_sha256": "8" * 64,
            "material_id": str(MATERIAL_ID),
            "material_revision_id": str(MATERIAL_REVISION_ID),
            "material_state_id": str(STATE_ID),
            "material_state_revision_id": str(STATE_REVISION_ID),
            "material_model_ir_revision_id": str(MODEL_IR_REVISION_ID),
            "neutral_material_id": str(neutral_id),
            "neutral_material_revision_id": str(neutral_revision_id),
        },
        target={
            "solver": TARGET.solver,
            "version": TARGET.version,
            "unit_system": TARGET.unit_system,
            "solver_material_id": "901",
            "material_name": "TARGET_CARD",
        },
        acknowledgement_identity=None,
        unit_profile=unit_profile,
        unit_applications=unit_applications,
    )


def _command(
    *,
    preview_identity: str = "1" * 64,
    unit_profile: UnitProfilePin | None = None,
) -> CreateTargetDelivery:
    return CreateTargetDelivery(
        processing_output_id=PROCESSING_OUTPUT_ID,
        processing_output_revision_id=PROCESSING_OUTPUT_REVISION_ID,
        neutral_material_id=NEUTRAL_ID,
        neutral_material_revision_id=NEUTRAL_REVISION_ID,
        target=TARGET,
        solver_material_id=901,
        material_name="TARGET_CARD",
        preview_identity=preview_identity,
        expected_mapping_report_sha256=REPORT_SHA,
        acknowledgement_identity=None,
        unit_profile=unit_profile,
    )


def _solver_unit_profile_content() -> UnitProfileContent:
    return UnitProfileContent(
        profile_key="target_delivery_pg_kg_m_s",
        label="Target delivery PostgreSQL kg-m-s",
        description="Non-production profile-bearing target delivery evidence.",
        non_production=True,
        selections=(
            UnitProfileSelection(
                "mass.density", DimensionId.MASS_PER_VOLUME, "g/cm3", "g/cm3", "kg/m3"
            ),
            UnitProfileSelection(
                "hyperelastic.coefficient",
                DimensionId.FORCE_PER_AREA,
                "MPa",
                "MPa",
                "Pa",
            ),
            UnitProfileSelection("strain.engineering", DimensionId.STRAIN, "%", "%", "1"),
        ),
    )


def _solver_unit_applications() -> tuple[UnitApplication, ...]:
    return (
        UnitApplication(
            "solver_card.density",
            UnitApplicationRole.SOLVER_EXPORT,
            "mass.density",
            DimensionId.MASS_PER_VOLUME,
            "kg/m3",
        ),
        UnitApplication(
            "solver_card.constitutive_parameters",
            UnitApplicationRole.SOLVER_EXPORT,
            "hyperelastic.coefficient",
            DimensionId.FORCE_PER_AREA,
            "Pa",
        ),
        UnitApplication(
            "solver_card.applicability.engineering_strain",
            UnitApplicationRole.SOLVER_EXPORT,
            "strain.engineering",
            DimensionId.STRAIN,
            "1",
        ),
    )


def _service(
    app_engine: Engine,
    preview: TargetPreview,
    *,
    cards: _Cards | None = None,
    card_neutral_id: UUID = NEUTRAL_ID,
    card_neutral_revision_id: UUID = NEUTRAL_REVISION_ID,
    card_id: UUID = CARD_ID,
    unit_applications: tuple[UnitApplication, ...] = (),
) -> tuple[TargetDeliveryService, _Cards, SecurityContext, AuthorizationDecision]:
    sessions = sessionmaker(app_engine, class_=Session)
    rls = SqlAlchemyRlsContext()
    repository = SqlAlchemyNeutralHyperelasticExportingRepository(
        session_factory=sessions,
        rls_context=rls,
        revision_hooks=(SqlInitialLifecycleHook(), SqlAlchemyRevisionProvenanceHook()),
    )
    card_service = cards or _Cards(
        repository=repository,
        neutral_id=card_neutral_id,
        neutral_revision_id=card_neutral_revision_id,
        card_id=card_id,
        unit_applications=unit_applications,
    )
    recorder = SqlTargetDeliveryReceiptRecorder(
        session_factory=sessions,
        rls_context=rls,
        writer=SqlAlchemyOutboxWriter(),
    )
    context = _context()
    decision = _decision(context)
    service = TargetDeliveryService(
        previews=cast(TargetPreviewService, _PreviewService(preview)),
        cards=card_service,  # type: ignore[arg-type]
        receipts=recorder,
    )
    return service, card_service, context, decision


def test_target_delivery_commits_card_lifecycle_binding_receipt_and_replay(
    postgres: tuple[Engine, Engine],
) -> None:
    admin_engine, app_engine = postgres
    service, cards, context, decision = _service(app_engine, _preview())
    delivered, first = asyncio.run(service.deliver(context, decision, _command()))
    assert delivered.preview_identity == first.delivery_identity
    assert cards.calls == 1
    replayed_preview, second = asyncio.run(service.deliver(context, decision, _command()))
    assert replayed_preview.preview_identity == delivered.preview_identity
    assert second == first
    assert cards.calls == 1

    with admin_engine.connect() as connection:
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(neutral_solver_card_table)
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(neutral_solver_card_revision_table)
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM governance.lifecycle_projection "
                    "WHERE aggregate_type='exporting.neutral_solver_card'"
                )
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM catalog.domain_record_binding "
                    "WHERE domain_kind='neutral_solver_card'"
                )
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(delivery_receipt_table)
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM events.outbox_event "
                    "WHERE event_type='io.cmp.exporting.solver-card-delivered.v1'"
                )
            ).scalar_one()
            == 1
        )


def test_publication_neutral_binding_requires_exact_record_approval(
    postgres: tuple[Engine, Engine],
) -> None:
    """Card/model approvals cannot publish a Neutral-bound Record without Record approval."""

    admin_engine, app_engine = postgres
    context = _context()
    catalog_decision = AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.CATALOG_READ,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=tuple(
            sorted(
                {
                    *database_permissions_for(Permission.CATALOG_READ),
                    *database_permissions_for(Permission.MODELING_READ),
                    *database_permissions_for(Permission.EXPORT_READ),
                }
            )
        ),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=REQUEST_ID,
        trace_id=TRACE_ID,
        decided_at=NOW,
    )
    query = CatalogRecordQuery(
        table_id=SCHEMA_ID,
        record_id=RECORD_ID,
        published_only=True,
        domain_binding_kind="neutral_material",
        domain_binding_object_id=NEUTRAL_ID,
        domain_binding_revision_id=NEUTRAL_REVISION_ID,
    )
    repository = SqlAlchemyCatalogRecordRepository(
        session_factory=sessionmaker(app_engine),
        rls_context=SqlAlchemyRlsContext(),
    )

    # Both upstream projections are approved/current and carry the same exact
    # Neutral pin as the Record binding. Neither projection is a configurable
    # Record approval, so the Neutral-bound Record must remain hidden.
    with admin_engine.begin() as connection:
        connection.execute(
            sa.insert(review_publication_projection_table),
            [
                {
                    "organization_id": ORG,
                    "project_id": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "review_request_id": REVIEW_MODEL_REQUEST_ID,
                    "subject_type": "modeling.material_model",
                    "subject_id": MODEL_ID,
                    "subject_revision_id": MODEL_REVISION_ID,
                    "neutral_material_id": NEUTRAL_ID,
                    "neutral_material_revision_id": NEUTRAL_REVISION_ID,
                    "neutral_artifact_sha256": ARTIFACT_SHA,
                    "record_id": RECORD_ID,
                    "record_revision_id": RECORD_REVISION_ID,
                    "record_table_id": SCHEMA_ID,
                    "record_table_revision_id": SCHEMA_REVISION_ID,
                    "published_at": NOW,
                    "published_by": ACTOR,
                },
                {
                    "organization_id": ORG,
                    "project_id": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "review_request_id": REVIEW_CARD_REQUEST_ID,
                    "subject_type": "exporting.solver_card",
                    "subject_id": REVIEW_SOLVER_CARD_ID,
                    "subject_revision_id": REVIEW_SOLVER_CARD_REVISION_ID,
                    "neutral_material_id": NEUTRAL_ID,
                    "neutral_material_revision_id": NEUTRAL_REVISION_ID,
                    "neutral_artifact_sha256": ARTIFACT_SHA,
                    "record_id": RECORD_ID,
                    "record_revision_id": RECORD_REVISION_ID,
                    "record_table_id": SCHEMA_ID,
                    "record_table_revision_id": SCHEMA_REVISION_ID,
                    "published_at": NOW,
                    "published_by": ACTOR,
                },
            ],
        )
    assert (
        repository.search_records(
            context=context,
            decision=catalog_decision,
            query=query,
        ).total_count
        == 0
    )

    # Only the exact configurable-record approval for the same immutable
    # Record revision may publish the already-bound Neutral selection.
    with admin_engine.begin() as connection:
        connection.execute(
            sa.insert(review_publication_projection_table).values(
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                review_request_id=REVIEW_RECORD_REQUEST_ID,
                subject_type="catalog.configurable_record",
                subject_id=RECORD_ID,
                subject_revision_id=RECORD_REVISION_ID,
                neutral_material_id=NEUTRAL_ID,
                neutral_material_revision_id=NEUTRAL_REVISION_ID,
                neutral_artifact_sha256=ARTIFACT_SHA,
                record_id=RECORD_ID,
                record_revision_id=RECORD_REVISION_ID,
                record_table_id=SCHEMA_ID,
                record_table_revision_id=SCHEMA_REVISION_ID,
                published_at=NOW,
                published_by=ACTOR,
            )
        )
    published = repository.search_records(
        context=context,
        decision=catalog_decision,
        query=query,
    )
    assert published.total_count == 1
    assert published.items[0].current.record.revision_id == RECORD_REVISION_ID


@pytest.mark.parametrize(
    ("neutral_id", "neutral_revision_id", "message"),
    [
        (NO_BINDING_NEUTRAL_ID, NO_BINDING_NEUTRAL_REVISION_ID, "no Materials Record binding"),
        (
            NEUTRAL_ID,
            UUID("76000000-0000-4000-8000-000000000121"),
            "source does not match its exact Neutral revision",
        ),
    ],
)
def test_target_delivery_missing_or_mismatched_neutral_binding_rolls_back(
    postgres: tuple[Engine, Engine],
    neutral_id: UUID,
    neutral_revision_id: UUID,
    message: str,
) -> None:
    admin_engine, app_engine = postgres
    service, cards, context, decision = _service(
        app_engine,
        _preview(
            neutral_id=neutral_id,
            neutral_revision_id=neutral_revision_id,
            preview_identity="2" * 64,
        ),
        cards=None,
        card_neutral_id=(neutral_id if neutral_id == NO_BINDING_NEUTRAL_ID else NEUTRAL_ID),
        card_neutral_revision_id=(
            neutral_revision_id if neutral_id == NO_BINDING_NEUTRAL_ID else NEUTRAL_REVISION_ID
        ),
        card_id=UUID(
            "76000000-0000-4000-8000-000000000121"
            if neutral_id == NO_BINDING_NEUTRAL_ID
            else "76000000-0000-4000-8000-000000000122"
        ),
    )
    with pytest.raises(TargetDeliveryConflict, match=message):
        asyncio.run(service.deliver(context, decision, _command(preview_identity="2" * 64)))
    assert cards.calls == 1

    with admin_engine.connect() as connection:
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(neutral_solver_card_table)
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(neutral_solver_card_revision_table)
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.select(sa.func.count()).select_from(delivery_receipt_table)
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM catalog.domain_record_binding "
                    "WHERE domain_kind='neutral_solver_card'"
                )
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM events.outbox_event "
                    "WHERE event_type='io.cmp.exporting.solver-card-delivered.v1'"
                )
            ).scalar_one()
            == 1
        )


def test_profile_bearing_delivery_persists_exact_typed_trace_provenance_and_rls(
    postgres: tuple[Engine, Engine],
) -> None:
    admin_engine, app_engine = postgres
    context = _context()
    unit_decision = AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.UNITS_WRITE,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(Permission.UNITS_WRITE),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )
    sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
    unit_service = CommonUnitService(
        repository=SqlAlchemyUnitProfileRepository(
            session_factory=sessions,
            rls_context=SqlAlchemyRlsContext(),
            revision_hooks=(SqlAlchemyRevisionProvenanceHook(),),
        ),
        id_factory=lambda: UNIT_PROFILE_ID,
    )
    profile = unit_service.create_profile(
        context,
        unit_decision,
        CreateUnitProfile(
            classification=DataClassification.INTERNAL,
            content=_solver_unit_profile_content(),
            change_reason="Create exact profile-bearing target-delivery fixture.",
        ),
    )
    pin = profile.pin
    applications = _solver_unit_applications()
    preview_identity = "9" * 64
    profile_preview = _preview(
        preview_identity=preview_identity,
        unit_profile=pin,
        unit_applications=applications,
    )
    service, cards, context, decision = _service(
        app_engine,
        profile_preview,
        card_id=PROFILE_CARD_ID,
        unit_applications=applications,
    )

    delivered, receipt = asyncio.run(
        service.deliver(
            context,
            decision,
            _command(preview_identity=preview_identity, unit_profile=pin),
        )
    )
    readback = cards.repository.get_solver_card_revision(
        context=context,
        decision=decision,
        solver_card_id=PROFILE_CARD_ID,
        solver_card_revision_id=receipt.solver_card_revision_id,
    )

    assert delivered.unit_profile == pin
    assert receipt.unit_profile == pin
    assert receipt.unit_applications == applications
    assert readback.unit_profile == pin
    assert readback.unit_applications == applications
    assert readback.current.content.unit_profile == pin
    assert readback.current.content.unit_applications == applications
    assert readback.current.record.schema_id == NEUTRAL_SOLVER_CARD_PROFILE_SCHEMA_ID
    assert readback.current.record.schema_version == NEUTRAL_SOLVER_CARD_PROFILE_SCHEMA_VERSION
    assert readback.current.record.content_hash == content_sha256(
        readback.current.content.canonical()
    )

    legacy_identity = "8" * 64
    legacy_service, _, legacy_context, legacy_decision = _service(
        app_engine,
        _preview(preview_identity=legacy_identity),
        card_id=LEGACY_COMPAT_CARD_ID,
    )
    _, legacy_receipt = asyncio.run(
        legacy_service.deliver(
            legacy_context,
            legacy_decision,
            _command(preview_identity=legacy_identity),
        )
    )
    assert legacy_receipt.unit_profile is None
    assert legacy_receipt.unit_applications == ()
    assert legacy_receipt.native_sha256 == receipt.native_sha256 == CARD_SHA

    with admin_engine.connect() as connection:
        card_profile = (
            connection.execute(
                sa.text(
                    "SELECT unit_profile_id, unit_profile_revision_id, unit_profile_sha256 "
                    "FROM exporting.neutral_solver_card_unit_profile "
                    "WHERE solver_card_id=:card"
                ),
                {"card": PROFILE_CARD_ID},
            )
            .mappings()
            .one()
        )
        assert card_profile == {
            "unit_profile_id": pin.profile_id,
            "unit_profile_revision_id": pin.revision_id,
            "unit_profile_sha256": pin.content_sha256,
        }
        stored_card_applications = (
            connection.execute(
                sa.text(
                    "SELECT location, application_role, quantity_semantics, dimension, unit_id "
                    "FROM exporting.neutral_solver_card_unit_application "
                    "WHERE solver_card_id=:card ORDER BY ordinal"
                ),
                {"card": PROFILE_CARD_ID},
            )
            .mappings()
            .all()
        )
        assert [dict(row) for row in stored_card_applications] == [
            {
                "location": item.location,
                "application_role": item.role.value,
                "quantity_semantics": item.quantity_semantics,
                "dimension": item.dimension.value,
                "unit_id": item.unit_id,
            }
            for item in applications
        ]
        delivery_profile = (
            connection.execute(
                sa.text(
                    "SELECT unit_profile_id, unit_profile_revision_id, unit_profile_sha256 "
                    "FROM exporting.solver_card_delivery_receipt WHERE receipt_id=:receipt"
                ),
                {"receipt": receipt.receipt_id},
            )
            .mappings()
            .one()
        )
        assert delivery_profile == card_profile
        stored_delivery_applications = (
            connection.execute(
                sa.text(
                    "SELECT location, application_role, quantity_semantics, dimension, unit_id "
                    "FROM exporting.solver_card_delivery_unit_application "
                    "WHERE receipt_id=:receipt ORDER BY ordinal"
                ),
                {"receipt": receipt.receipt_id},
            )
            .mappings()
            .all()
        )
        assert [dict(row) for row in stored_delivery_applications] == [
            {
                "location": item.location,
                "application_role": item.role.value,
                "quantity_semantics": item.quantity_semantics,
                "dimension": item.dimension.value,
                "unit_id": item.unit_id,
            }
            for item in applications
        ]
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM provenance.usage usage "
                    "JOIN provenance.entity entity "
                    "ON entity.organization_id=usage.organization_id "
                    "AND entity.project_id=usage.project_id AND entity.id=usage.entity_id "
                    "WHERE entity.reference_type='units.unit_profile.revision' "
                    "AND entity.reference_id=:revision AND usage.role='unit_profile'"
                ),
                {"revision": pin.revision_id},
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM provenance.derivation derivation "
                    "JOIN provenance.entity used "
                    "ON used.organization_id=derivation.organization_id "
                    "AND used.project_id=derivation.project_id "
                    "AND used.id=derivation.used_entity_id "
                    "JOIN provenance.entity generated "
                    "ON generated.organization_id=derivation.organization_id "
                    "AND generated.project_id=derivation.project_id "
                    "AND generated.id=derivation.generated_entity_id "
                    "WHERE used.reference_type='units.unit_profile.revision' "
                    "AND used.reference_id=:profile_revision "
                    "AND generated.reference_type='exporting.neutral_solver_card.revision' "
                    "AND generated.reference_id=:card_revision "
                    "AND derivation.derivation_kind='unit_profile_application'"
                ),
                {
                    "profile_revision": pin.revision_id,
                    "card_revision": receipt.solver_card_revision_id,
                },
            ).scalar_one()
            == 1
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM exporting.neutral_solver_card_unit_profile "
                    "WHERE solver_card_id=:card"
                ),
                {"card": LEGACY_COMPAT_CARD_ID},
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM exporting.neutral_solver_card_unit_application "
                    "WHERE solver_card_id=:card"
                ),
                {"card": LEGACY_COMPAT_CARD_ID},
            ).scalar_one()
            == 0
        )
        assert connection.execute(
            sa.text(
                "SELECT unit_profile_id, unit_profile_revision_id, unit_profile_sha256 "
                "FROM exporting.solver_card_delivery_receipt WHERE receipt_id=:receipt"
            ),
            {"receipt": legacy_receipt.receipt_id},
        ).one() == (None, None, None)

    rls = SqlAlchemyRlsContext()
    with sessions() as session, session.begin():
        rls.bind_authorization(session, context, decision)
        result = session.execute(
            sa.text(
                "UPDATE exporting.neutral_solver_card_unit_application "
                "SET location='mutated' WHERE solver_card_id=:card"
            ),
            {"card": PROFILE_CARD_ID},
        )
        assert cast(CursorResult[Any], result).rowcount == 0
    with pytest.raises(sa.exc.DBAPIError, match="immutable"):
        with admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE exporting.neutral_solver_card_unit_application "
                    "SET location='mutated' WHERE solver_card_id=:card"
                ),
                {"card": PROFILE_CARD_ID},
            )

    other_project = UUID("76000000-0000-4000-8000-0000000001ff")
    other_context = replace(context, project_id=other_project)
    other_decision = replace(
        decision,
        project_id=other_project,
        permission=Permission.EXPORT_READ,
        database_permissions=database_permissions_for(Permission.EXPORT_READ),
    )
    with sessions() as session, session.begin():
        rls.bind_authorization(session, other_context, other_decision)
        assert (
            session.scalar(
                sa.text(
                    "SELECT count(*) FROM exporting.neutral_solver_card_unit_profile "
                    "WHERE solver_card_id=:card"
                ),
                {"card": PROFILE_CARD_ID},
            )
            == 0
        )
        assert (
            session.scalar(
                sa.text(
                    "SELECT count(*) FROM exporting.solver_card_delivery_unit_application "
                    "WHERE receipt_id=:receipt"
                ),
                {"receipt": receipt.receipt_id},
            )
            == 0
        )
