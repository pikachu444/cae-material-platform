"""Explicit cross-module read model for Bulk Export source representations."""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.exporting.application.bulk_export import (
    BulkExportSourceResolver,
    ExportCandidate,
)
from cmp.modules.exporting.domain.bulk_bundle import (
    BulkExportConflict,
    BulkExportNotFound,
    ExportMemberKind,
    ExportSelectionMember,
    ExportSourceRef,
    ResolvedBundleFile,
    canonical_json_bytes,
    sha256_bytes,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _filename(value: str, fallback: str) -> str:
    cleaned = _SAFE_FILENAME.sub("-", value).strip(".-")
    return (cleaned or fallback)[:160]


_MODEL_IR_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:cmp:exporting:bulk-material-model-ir-snapshot:1.0.0",
    "title": "CMP solver-neutral Material Model IR snapshot",
    "type": "object",
    "required": ["schema", "identity", "model_family_id", "properties", "parameters"],
    "properties": {
        "schema": {"const": "urn:cmp:exporting:bulk-material-model-ir-snapshot:1.0.0"},
        "identity": {
            "type": "object",
            "required": ["material_model_id", "material_model_revision_id", "content_hash"],
        },
        "model_family_id": {"type": "string"},
        "properties": {"type": "object"},
        "parameters": {"type": "object"},
        "provenance": {"type": "object"},
    },
    "additionalProperties": False,
}


class SqlAlchemyBulkExportSourceResolver(BulkExportSourceResolver):
    """Read exact revisions through a bounded, read-only exporting projection."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        artifacts: ArtifactService,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._artifacts = artifacts

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            yield session

    def _source_refs_for_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> tuple[ExportSourceRef, ...]:
        refs: list[ExportSourceRef] = []
        with self._session(context, decision) as session:
            dataset_rows = session.execute(
                sa.text(
                    """
                    SELECT DISTINCT gdr.raw_asset_id, gdr.raw_artifact_id,
                           gd.id AS dataset_id, gdr.id AS dataset_revision_id,
                           gdr.data_artifact_id, data_artifact.media_type AS data_media_type
                    FROM datasets.governed_dataset gd
                    JOIN datasets.governed_dataset_revision gdr
                      ON gdr.aggregate_id = gd.id
                     AND gdr.organization_id = gd.organization_id
                     AND gdr.project_id = gd.project_id
                    JOIN artifact.artifact data_artifact
                      ON data_artifact.id = gdr.data_artifact_id
                     AND data_artifact.organization_id = gdr.organization_id
                     AND data_artifact.project_id = gdr.project_id
                    JOIN testing.test_run tr ON tr.id = gd.test_run_id
                    JOIN testing.specimen sp ON sp.id = tr.specimen_id
                    JOIN catalog.material_state ms ON ms.id = sp.material_state_id
                    WHERE ms.material_id = :material_id
                      AND gd.organization_id = :organization_id
                      AND gd.project_id = :project_id
                    ORDER BY gdr.id
                    """
                ),
                {
                    "material_id": material_id,
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                },
            ).mappings()
            seen_raw: set[tuple[UUID, UUID]] = set()
            for row in dataset_rows:
                raw_pair = (
                    cast(UUID, row["raw_asset_id"]),
                    cast(UUID, row["raw_artifact_id"]),
                )
                if raw_pair not in seen_raw:
                    refs.append(
                        ExportSourceRef(
                            ExportMemberKind.RAW_ORIGINAL,
                            raw_asset_id=raw_pair[0],
                            artifact_id=raw_pair[1],
                        )
                    )
                    seen_raw.add(raw_pair)
                data_media_type = str(row["data_media_type"])
                kinds = (
                    (
                        ExportMemberKind.DATASET_PARQUET,
                        ExportMemberKind.DATASET_CSV,
                    )
                    if data_media_type == "application/vnd.apache.parquet"
                    else (ExportMemberKind.DATASET_CSV,)
                    if data_media_type == "text/csv"
                    else ()
                )
                for kind in kinds:
                    refs.append(
                        ExportSourceRef(
                            kind,
                            artifact_id=cast(UUID, row["data_artifact_id"]),
                            dataset_id=cast(UUID, row["dataset_id"]),
                            dataset_revision_id=cast(UUID, row["dataset_revision_id"]),
                        )
                    )
            model_rows = session.execute(
                sa.text(
                    """
                    SELECT mm.id AS model_id, mmr.id AS revision_id
                    FROM modeling.material_model mm
                    JOIN modeling.material_model_revision mmr
                      ON mmr.aggregate_id = mm.id
                     AND mmr.organization_id = mm.organization_id
                     AND mmr.project_id = mm.project_id
                    JOIN catalog.material_state ms ON ms.id = mm.material_state_id
                    WHERE ms.material_id = :material_id
                      AND mm.organization_id = :organization_id
                      AND mm.project_id = :project_id
                    ORDER BY mm.id, mmr.revision_no
                    """
                ),
                {
                    "material_id": material_id,
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                },
            ).mappings()
            for row in model_rows:
                for kind in (
                    ExportMemberKind.MODEL_IR_JSON,
                    ExportMemberKind.MODEL_IR_SCHEMA,
                ):
                    refs.append(
                        ExportSourceRef(
                            kind,
                            material_model_id=cast(UUID, row["model_id"]),
                            material_model_revision_id=cast(UUID, row["revision_id"]),
                        )
                    )
            card_rows = session.execute(
                sa.text(
                    """
                    SELECT sc.id AS card_id, scr.id AS revision_id
                    FROM exporting.solver_card sc
                    JOIN exporting.solver_card_revision scr
                      ON scr.aggregate_id = sc.id
                     AND scr.organization_id = sc.organization_id
                     AND scr.project_id = sc.project_id
                    JOIN modeling.material_model mm ON mm.id = sc.material_model_id
                    JOIN catalog.material_state ms ON ms.id = mm.material_state_id
                    WHERE ms.material_id = :material_id
                      AND sc.organization_id = :organization_id
                      AND sc.project_id = :project_id
                    ORDER BY sc.id, scr.revision_no
                    """
                ),
                {
                    "material_id": material_id,
                    "organization_id": context.organization_id,
                    "project_id": context.project_id,
                },
            ).mappings()
            for row in card_rows:
                for kind in (
                    ExportMemberKind.SOLVER_MAPPING_REPORT,
                    ExportMemberKind.SOLVER_CARD_NATIVE,
                ):
                    refs.append(
                        ExportSourceRef(
                            kind,
                            solver_card_id=cast(UUID, row["card_id"]),
                            solver_card_revision_id=cast(UUID, row["revision_id"]),
                        )
                    )
        return tuple(refs)

    async def discover(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> tuple[ExportCandidate, ...]:
        refs = self._source_refs_for_material(context, decision, material_id)
        candidates = [await self.inspect(context, decision, source) for source in refs]
        return tuple(candidates)

    async def _artifact_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        maximum_bytes: int,
    ) -> bytes:
        _, value = await self._artifacts.read_verified_bytes(
            context, decision, artifact_id, maximum_bytes=maximum_bytes
        )
        return value

    def _raw_metadata(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
    ) -> tuple[DataClassification, str, int, str, str, str]:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.text(
                        """
                    SELECT ra.classification, ra.original_filename, a.sha256,
                           a.size_bytes, a.media_type
                    FROM artifact.raw_asset ra
                    JOIN artifact.artifact a
                      ON a.id = :artifact_id
                     AND a.source_raw_asset_id = ra.id
                     AND a.organization_id = ra.organization_id
                     AND a.project_id = ra.project_id
                    WHERE ra.id = :raw_asset_id
                    """
                    ),
                    {
                        "raw_asset_id": source.raw_asset_id,
                        "artifact_id": source.artifact_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("raw original is not visible")
        name = _filename(str(row["original_filename"]), "raw-source.bin")
        return (
            DataClassification(str(row["classification"])),
            str(row["sha256"]),
            int(row["size_bytes"]),
            str(row["media_type"]),
            f"raw/{source.raw_asset_id}/{name}",
            f"Raw original · {name}",
        )

    def _dataset_metadata(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
    ) -> dict[str, Any]:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.text(
                        """
                    SELECT gdr.classification, gdr.representation, gdr.data_schema,
                           gdr.row_count, a.sha256, a.size_bytes, a.media_type
                    FROM datasets.governed_dataset_revision gdr
                    JOIN artifact.artifact a
                      ON a.id = :artifact_id
                     AND a.organization_id = gdr.organization_id
                     AND a.project_id = gdr.project_id
                    WHERE gdr.aggregate_id = :dataset_id
                      AND gdr.id = :revision_id
                    """
                    ),
                    {
                        "dataset_id": source.dataset_id,
                        "revision_id": source.dataset_revision_id,
                        "artifact_id": source.artifact_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("Dataset revision is not visible")
        return dict(row)

    def _model_row(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
    ) -> dict[str, Any]:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.text(
                        """
                    SELECT * FROM modeling.material_model_revision
                    WHERE aggregate_id = :model_id AND id = :revision_id
                    """
                    ),
                    {
                        "model_id": source.material_model_id,
                        "revision_id": source.material_model_revision_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("Material Model revision is not visible")
        return dict(row)

    def _model_document(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
    ) -> tuple[DataClassification, str, bytes]:
        row = self._model_row(context, decision, source)
        family = str(row["model_family_id"])
        parameters: dict[str, object] = {}
        if "linear-viscoelastic-prony" in family:
            with self._session(context, decision) as session:
                terms = session.execute(
                    sa.text(
                        """
                        SELECT ordinal, g_ratio, k_ratio, relaxation_time_s
                        FROM modeling.linear_viscoelastic_prony_term
                        WHERE material_model_id = :model_id
                          AND material_model_revision_id = :revision_id
                        ORDER BY ordinal
                        """
                    ),
                    {
                        "model_id": source.material_model_id,
                        "revision_id": source.material_model_revision_id,
                    },
                ).mappings()
                parameters["prony_terms"] = [dict(term) for term in terms]
        elif "ogden-prony-hyperviscoelastic" in family:
            with self._session(context, decision) as session:
                ogden = (
                    session.execute(
                        sa.text(
                            """
                        SELECT ogden_mu_pa, ogden_alpha, law62_poisson_ratio
                        FROM modeling.ogden_prony_revision
                        WHERE material_model_id = :model_id
                          AND material_model_revision_id = :revision_id
                        """
                        ),
                        {
                            "model_id": source.material_model_id,
                            "revision_id": source.material_model_revision_id,
                        },
                    )
                    .mappings()
                    .one()
                )
                terms = session.execute(
                    sa.text(
                        """
                        SELECT ordinal, g_ratio, relaxation_time_s
                        FROM modeling.ogden_prony_term
                        WHERE material_model_id = :model_id
                          AND material_model_revision_id = :revision_id
                        ORDER BY ordinal
                        """
                    ),
                    {
                        "model_id": source.material_model_id,
                        "revision_id": source.material_model_revision_id,
                    },
                ).mappings()
                parameters.update(dict(ogden))
                parameters["shear_prony_terms"] = [dict(term) for term in terms]
        elif "tabulated-plasticity" in family:
            parameters.update(
                {
                    "hardening_curve_artifact_id": str(row["hardening_curve_artifact_id"]),
                    "hardening_curve_sha256": row["hardening_curve_sha256"],
                    "hardening_curve_point_count": row["hardening_curve_point_count"],
                    "voce_q_pa": row["voce_q_pa"],
                    "voce_b": row["voce_b"],
                }
            )
        else:
            parameters["linear_elastic"] = True
        document = {
            "schema": "urn:cmp:exporting:bulk-material-model-ir-snapshot:1.0.0",
            "identity": {
                "material_model_id": str(row["aggregate_id"]),
                "material_model_revision_id": str(row["id"]),
                "revision_no": int(row["revision_no"]),
                "content_hash": str(row["content_hash"]),
                "source_schema_id": str(row["schema_id"]),
                "source_schema_version": str(row["schema_version"]),
            },
            "model_family_id": family,
            "properties": {
                "density_kg_per_m3": row["density_kg_per_m3"],
                "youngs_modulus_pa": row["youngs_modulus_pa"],
                "poisson_ratio": row["poisson_ratio"],
                "source_yield_stress_pa": row["source_yield_stress_pa"],
                "reference_temperature_k": row["reference_temperature_k"],
            },
            "parameters": parameters,
            "provenance": {
                "material_id": str(row["material_id"]),
                "material_revision_id": str(row["material_revision_id"]),
                "material_state_id": str(row["material_state_id"]),
                "material_state_revision_id": str(row["material_state_revision_id"]),
                "property_set_id": str(row["property_set_id"]),
                "property_set_revision_id": str(row["property_set_revision_id"]),
                "non_production": bool(row["non_production"]),
            },
        }
        return (
            DataClassification(str(row["classification"])),
            family,
            canonical_json_bytes(document),
        )

    def _card_row(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
    ) -> dict[str, Any]:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.text(
                        """
                    SELECT scr.*,
                           linear.prony_terms_mapping_status,
                           linear.bulk_mapping_status,
                           ogden.ogden_mapping_status,
                           ogden.prony_mapping_status,
                           ogden.volumetric_mapping_status
                    FROM exporting.solver_card_revision scr
                    LEFT JOIN exporting.linear_viscoelastic_solver_card_revision linear
                      ON linear.solver_card_id = scr.aggregate_id
                     AND linear.solver_card_revision_id = scr.id
                    LEFT JOIN exporting.ogden_prony_solver_card_revision ogden
                      ON ogden.solver_card_id = scr.aggregate_id
                     AND ogden.solver_card_revision_id = scr.id
                    WHERE scr.aggregate_id = :card_id AND scr.id = :revision_id
                    """
                    ),
                    {
                        "card_id": source.solver_card_id,
                        "revision_id": source.solver_card_revision_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise BulkExportNotFound("Solver Card revision is not visible")
        return dict(row)

    def _mapping_report(self, row: dict[str, Any]) -> bytes:
        status_fields = {
            key: value
            for key, value in row.items()
            if key.endswith("_mapping_status") and value is not None
        }
        document = {
            "schema": "urn:cmp:exporting:bulk-mapping-report-snapshot:1.0.0",
            "solver_card_id": str(row["aggregate_id"]),
            "solver_card_revision_id": str(row["id"]),
            "material_model_id": str(row["material_model_id"]),
            "material_model_revision_id": str(row["material_model_revision_id"]),
            "target": {
                "solver": row["target_solver"],
                "version": row["target_version"],
                "unit_system": row["target_unit_system"],
            },
            "mapping_report_sha256": str(row["mapping_report_sha256"]),
            "statuses": status_fields,
            "exporter": {
                "id": row["exporter_id"],
                "version": row["exporter_version"],
                "digest": row["exporter_digest"],
            },
            "non_production": bool(row["non_production"]),
        }
        return canonical_json_bytes(document)

    async def _render(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
        *,
        maximum_bytes: int,
    ) -> tuple[DataClassification, bytes, str, str, str]:
        if source.kind is ExportMemberKind.RAW_ORIGINAL:
            classification, _, _, media, path, label = self._raw_metadata(context, decision, source)
            assert source.artifact_id is not None
            value = await self._artifact_bytes(context, decision, source.artifact_id, maximum_bytes)
            return classification, value, media, path, label
        if source.kind in {
            ExportMemberKind.DATASET_PARQUET,
            ExportMemberKind.DATASET_CSV,
        }:
            row = self._dataset_metadata(context, decision, source)
            assert source.artifact_id is not None
            value = await self._artifact_bytes(context, decision, source.artifact_id, maximum_bytes)
            representation = str(row["representation"])
            label = f"Dataset {representation} · {row['data_schema']} · {row['row_count']} rows"
            base = f"datasets/{source.dataset_id}/{source.dataset_revision_id}"
            if source.kind is ExportMemberKind.DATASET_PARQUET:
                return (
                    DataClassification(str(row["classification"])),
                    value,
                    str(row["media_type"]),
                    f"{base}/data.parquet",
                    label,
                )
            if str(row["media_type"]) == "text/csv":
                return (
                    DataClassification(str(row["classification"])),
                    value,
                    "text/csv",
                    f"{base}/data.csv",
                    label.replace("Dataset", "Readable CSV"),
                )
            read_table = cast(Any, pq.read_table)
            write_csv = cast(Any, pacsv).write_csv
            table = read_table(pa.BufferReader(value))
            output = pa.BufferOutputStream()
            write_csv(table, output)
            csv_bytes = output.getvalue().to_pybytes()
            return (
                DataClassification(str(row["classification"])),
                csv_bytes,
                "text/csv",
                f"{base}/data.csv",
                label.replace("Dataset", "Readable CSV"),
            )
        if source.kind in {
            ExportMemberKind.MODEL_IR_JSON,
            ExportMemberKind.MODEL_IR_SCHEMA,
        }:
            classification, family, ir = self._model_document(context, decision, source)
            base = f"models/{source.material_model_id}/{source.material_model_revision_id}"
            if source.kind is ExportMemberKind.MODEL_IR_JSON:
                return classification, ir, "application/json", f"{base}/ir.json", family
            schema = canonical_json_bytes(_MODEL_IR_SCHEMA)
            return (
                classification,
                schema,
                "application/schema+json",
                f"{base}/ir.schema.json",
                f"IR schema · {family}",
            )
        row = self._card_row(context, decision, source)
        classification = DataClassification(str(row["classification"]))
        base = f"cards/{source.solver_card_id}/{source.solver_card_revision_id}"
        solver = str(row["target_solver"])
        material_name = _filename(
            str(row["material_name"] or row["card_title"] or "MATERIAL"),
            "MATERIAL",
        )
        if source.kind is ExportMemberKind.SOLVER_MAPPING_REPORT:
            return (
                classification,
                self._mapping_report(row),
                "application/json",
                f"{base}/mapping-report.json",
                f"{solver} mapping report · {material_name}",
            )
        extension = "inp" if solver == "abaqus" else "rad"
        return (
            classification,
            str(row["card_text"]).encode("utf-8"),
            "text/plain",
            f"{base}/{material_name}.{extension}",
            f"{solver} native card · {material_name}",
        )

    async def inspect(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
    ) -> ExportCandidate:
        if source.kind is ExportMemberKind.RAW_ORIGINAL:
            classification, digest, size, media, path, label = self._raw_metadata(
                context, decision, source
            )
            return ExportCandidate(source, classification, digest, size, media, path, label)
        classification, value, media, path, label = await self._render(
            context, decision, source, maximum_bytes=64 * 1024 * 1024
        )
        return ExportCandidate(
            source,
            classification,
            sha256_bytes(value),
            len(value),
            media,
            path,
            label,
        )

    async def resolve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        member: ExportSelectionMember,
        *,
        maximum_bytes: int,
    ) -> ResolvedBundleFile:
        classification, value, media, path, _ = await self._render(
            context, decision, member.source, maximum_bytes=maximum_bytes
        )
        if classification is not member.classification or media != member.media_type:
            raise BulkExportConflict("source metadata changed after Selection creation")
        if path != member.archive_path:
            # A caller may choose an explicit path. Only source bytes and media are immutable.
            path = member.archive_path
        if sha256_bytes(value) != member.source_sha256 or len(value) != member.source_size_bytes:
            raise BulkExportConflict("source bytes changed after Selection creation")
        return ResolvedBundleFile(member, value)
