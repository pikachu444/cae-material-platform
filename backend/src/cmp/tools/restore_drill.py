"""Isolated PostgreSQL/object-store restore drill with digest and lineage evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from time import perf_counter
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATABASE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class RestoreDrillError(RuntimeError):
    """The drill cannot prove a safe and complete restore."""


@dataclass(frozen=True, slots=True)
class ObjectEvidence:
    kind: str
    object_id: str
    storage_key: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ObjectVerification:
    object_id: str
    status: str
    expected_sha256: str
    observed_sha256: str | None
    expected_size_bytes: int
    observed_size_bytes: int | None


def _safe_object_path(root: Path, storage_key: str) -> Path:
    if "\\" in storage_key or "\x00" in storage_key:
        raise RestoreDrillError("object storage key contains a forbidden separator")
    key = PurePosixPath(storage_key)
    if key.is_absolute() or not key.parts or any(part in {"", ".", ".."} for part in key.parts):
        raise RestoreDrillError("object storage key is unsafe")
    object_root = (root / "objects").resolve(strict=True)
    candidate = object_root.joinpath(*key.parts).with_suffix(".blob").resolve(strict=False)
    try:
        candidate.relative_to(object_root)
    except ValueError as error:
        raise RestoreDrillError("object storage key escapes the restored root") from error
    return candidate


def _digest(path: Path) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise RestoreDrillError("restored object is not a regular file")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def verify_objects(
    root: Path, evidence: tuple[ObjectEvidence, ...]
) -> tuple[ObjectVerification, ...]:
    results: list[ObjectVerification] = []
    for item in evidence:
        if _SHA256.fullmatch(item.sha256) is None or item.size_bytes < 0:
            raise RestoreDrillError("database object evidence is malformed")
        path = _safe_object_path(root, item.storage_key)
        if not path.exists():
            results.append(
                ObjectVerification(
                    item.object_id,
                    "missing",
                    item.sha256,
                    None,
                    item.size_bytes,
                    None,
                )
            )
            continue
        observed_sha256, observed_size = _digest(path)
        status = (
            "verified"
            if observed_sha256 == item.sha256 and observed_size == item.size_bytes
            else "mismatch"
        )
        results.append(
            ObjectVerification(
                item.object_id,
                status,
                item.sha256,
                observed_sha256,
                item.size_bytes,
                observed_size,
            )
        )
    return tuple(results)


@dataclass(frozen=True, slots=True)
class _DatabaseTarget:
    command_url: str
    psycopg_url: str
    password: str | None
    maintenance_url: str


def _database_target(value: str, database: str) -> _DatabaseTarget:
    normalized = value.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.hostname is None:
        raise RestoreDrillError("source DSN must be a PostgreSQL URL")
    username = unquote(parsed.username or "")
    if not username:
        raise RestoreDrillError("source DSN must contain an owner username")
    host = parsed.hostname
    port = parsed.port
    hostname = f"[{host}]" if ":" in host else host
    authority = f"{quote(username, safe='')}@{hostname}"
    if port is not None:
        authority += f":{port}"
    query = parsed.query
    command_url = urlunsplit(("postgresql", authority, f"/{quote(database)}", query, ""))
    password = unquote(parsed.password) if parsed.password is not None else None
    password_part = f":{quote(password, safe='')}" if password is not None else ""
    psycopg_authority = f"{quote(username, safe='')}{password_part}@{hostname}"
    if port is not None:
        psycopg_authority += f":{port}"
    psycopg_url = urlunsplit(("postgresql", psycopg_authority, f"/{quote(database)}", query, ""))
    maintenance_url = urlunsplit(("postgresql", psycopg_authority, "/postgres", query, ""))
    return _DatabaseTarget(command_url, psycopg_url, password, maintenance_url)


def _run(command: list[str], *, password: str | None) -> None:
    environment = os.environ.copy()
    if password is not None:
        environment["PGPASSWORD"] = password
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1:] or ["command failed"]
        raise RestoreDrillError(f"PostgreSQL restore command failed: {detail[0][:500]}")


def _copy_object_store(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    if source.is_symlink() or not (source / "objects").is_dir():
        raise RestoreDrillError("object-store source is not a supported filesystem adapter root")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source / "objects", destination / "objects", copy_function=shutil.copy2)
    for path in (destination / "objects").rglob("*"):
        if path.is_symlink():
            raise RestoreDrillError("object snapshot contains a symbolic link")


def _object_evidence(
    connection: psycopg.Connection[tuple[object, ...]], limit: int
) -> tuple[ObjectEvidence, ...]:
    query = """
        SELECT kind, object_id, storage_key, sha256, size_bytes FROM (
          SELECT kind, object_id, storage_key, sha256, size_bytes FROM (
            SELECT DISTINCT ON (raw.id)
                   'raw_asset' AS kind, raw.id::text AS object_id,
                   stored.storage_key, raw.sha256::text, raw.size_bytes
            FROM artifact.raw_asset raw
            JOIN artifact.artifact stored
              ON stored.organization_id=raw.organization_id
             AND stored.project_id=raw.project_id
             AND stored.source_raw_asset_id=raw.id
             AND stored.sha256=raw.sha256
            ORDER BY raw.id, stored.created_at, stored.id
          ) raw_objects
          UNION ALL
          SELECT 'artifact' AS kind, id::text AS object_id, storage_key,
                 sha256::text, size_bytes
          FROM artifact.artifact
        ) restored_objects
        ORDER BY CASE kind WHEN 'raw_asset' THEN 0 ELSE 1 END, object_id
        LIMIT %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (limit,))
        return tuple(
            ObjectEvidence(str(kind), str(object_id), str(key), str(digest), int(str(size)))
            for kind, object_id, key, digest, size in cursor.fetchall()
        )


def _counts(connection: psycopg.Connection[tuple[object, ...]]) -> dict[str, int]:
    relations = {
        "artifact": "artifact.artifact",
        "raw_asset": "artifact.raw_asset",
        "release": "governance.release",
        "release_artifact": "governance.release_artifact",
        "bulk_export_bundle": "exporting.bulk_export_bundle",
        "provenance_entity": "provenance.entity",
        "provenance_activity": "provenance.activity",
        "provenance_usage": "provenance.usage",
        "provenance_generation": "provenance.generation",
    }
    values: dict[str, int] = {}
    with connection.cursor() as cursor:
        for label, relation in relations.items():
            cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.SQL(relation)))
            row = cursor.fetchone()
            values[label] = int(str(row[0])) if row is not None else 0
    return values


def _release_integrity(connection: psycopg.Connection[tuple[object, ...]]) -> tuple[int, int]:
    verified = 0
    mismatched = 0
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT sha256::text, size_bytes, content_text "
            "FROM governance.release_artifact ORDER BY id"
        )
        for expected_sha, expected_size, content in cursor.fetchall():
            payload = str(content).encode("utf-8")
            if hashlib.sha256(payload).hexdigest() == str(expected_sha) and len(payload) == int(
                str(expected_size)
            ):
                verified += 1
            else:
                mismatched += 1
    return verified, mismatched


def _release_sample_status(*, release_count: int, verified_artifacts: int) -> str:
    if release_count == 0:
        return "not_present_in_source"
    if verified_artifacts == 0:
        return "release_has_no_verified_artifact"
    return "verified"


def _dangling_lineage(connection: psycopg.Connection[tuple[object, ...]]) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              (SELECT count(*) FROM provenance.usage u
               LEFT JOIN provenance.activity a ON a.organization_id=u.organization_id
                 AND a.project_id=u.project_id AND a.id=u.activity_id
               LEFT JOIN provenance.entity e ON e.organization_id=u.organization_id
                 AND e.project_id=u.project_id AND e.id=u.entity_id
               WHERE a.id IS NULL OR e.id IS NULL)
              +
              (SELECT count(*) FROM provenance.generation g
               LEFT JOIN provenance.activity a ON a.organization_id=g.organization_id
                 AND a.project_id=g.project_id AND a.id=g.activity_id
               LEFT JOIN provenance.entity e ON e.organization_id=g.organization_id
                 AND e.project_id=g.project_id AND e.id=g.entity_id
               WHERE a.id IS NULL OR e.id IS NULL)
            """
        )
        row = cursor.fetchone()
        return int(str(row[0])) if row is not None else 0


def run_drill(
    *,
    source_url: str,
    object_store_root: Path,
    work_root: Path,
    sample_limit: int,
) -> Path:
    if not 1 <= sample_limit <= 10_000:
        raise RestoreDrillError("sample limit must be between 1 and 10000")
    started_at = datetime.now(UTC)
    started_clock = perf_counter()
    drill_id = started_at.strftime("%Y%m%dT%H%M%SZ") + f"-{uuid4().hex[:8]}"
    restore_database = f"cmp_restore_{uuid4().hex[:16]}"
    if _DATABASE.fullmatch(restore_database) is None:
        raise RestoreDrillError("generated restore database name is invalid")
    drill_root = work_root.resolve(strict=False) / drill_id
    drill_root.mkdir(parents=True, exist_ok=False)
    dump_path = drill_root / "metadata.dump"
    restored_objects = drill_root / "object-restore"
    report_path = drill_root / "report.json"
    source_database = unquote(urlsplit(source_url.replace("+psycopg", "")).path.lstrip("/"))
    if not source_database:
        raise RestoreDrillError("source DSN must select a database")
    source = _database_target(source_url, source_database)
    target = _database_target(source_url, restore_database)
    created = False
    report: dict[str, object] = {
        "drill_id": drill_id,
        "status": "failed",
        "started_at": started_at.isoformat(),
        "restore_database": restore_database,
    }
    try:
        _run(
            ["pg_dump", "--format=custom", "--file", str(dump_path), source.command_url],
            password=source.password,
        )
        dump_sha256, dump_size = _digest(dump_path)
        _copy_object_store(object_store_root, restored_objects)
        with psycopg.connect(source.maintenance_url, autocommit=True) as maintenance:
            maintenance.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(restore_database)
                )
            )
            created = True
        _run(
            [
                "pg_restore",
                "--exit-on-error",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                target.command_url,
                str(dump_path),
            ],
            password=target.password,
        )
        with psycopg.connect(source.psycopg_url) as source_connection:
            source_counts = _counts(source_connection)
        with psycopg.connect(target.psycopg_url) as restored_connection:
            restored_counts = _counts(restored_connection)
            evidence = _object_evidence(restored_connection, sample_limit)
            release_verified, release_mismatched = _release_integrity(restored_connection)
            dangling = _dangling_lineage(restored_connection)
        verification = verify_objects(restored_objects, evidence)
        failed_objects = [item for item in verification if item.status != "verified"]
        raw_sample_ids = {item.object_id for item in evidence if item.kind == "raw_asset"}
        raw_verified = sum(
            item.status == "verified" and item.object_id in raw_sample_ids for item in verification
        )
        counts_match = source_counts == restored_counts
        raw_sample_ok = source_counts["raw_asset"] == 0 or raw_verified > 0
        release_sample_status = _release_sample_status(
            release_count=source_counts["release"],
            verified_artifacts=release_verified,
        )
        release_sample_ok = release_sample_status != "release_has_no_verified_artifact"
        status = (
            "passed"
            if counts_match
            and not failed_objects
            and raw_sample_ok
            and release_sample_ok
            and release_mismatched == 0
            and dangling == 0
            else "failed"
        )
        report.update(
            {
                "status": status,
                "completed_at": datetime.now(UTC).isoformat(),
                "duration_seconds": round(perf_counter() - started_clock, 3),
                "metadata_dump": {"sha256": dump_sha256, "size_bytes": dump_size},
                "source_counts": source_counts,
                "restored_counts": restored_counts,
                "counts_match": counts_match,
                "objects_sampled": len(verification),
                "objects_verified": len(verification) - len(failed_objects),
                "raw_assets_sampled": len(raw_sample_ids),
                "raw_assets_verified": raw_verified,
                "object_results": [asdict(item) for item in verification],
                "release_artifacts_verified": release_verified,
                "release_artifacts_mismatched": release_mismatched,
                "release_sample_status": release_sample_status,
                "dangling_lineage_edges": dangling,
                "rpo_target_minutes": 15,
                "rto_target_hours": 4,
            }
        )
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if status != "passed":
            raise RestoreDrillError(f"restore verification failed; inspect {report_path}")
        return report_path
    except Exception as error:
        report["completed_at"] = datetime.now(UTC).isoformat()
        report["duration_seconds"] = round(perf_counter() - started_clock, 3)
        report["failure_type"] = type(error).__name__
        if not report_path.exists():
            report_path.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        raise
    finally:
        if created:
            with psycopg.connect(source.maintenance_url, autocommit=True) as maintenance:
                maintenance.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(restore_database)
                    )
                )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an isolated CMP metadata/object restore drill."
    )
    parser.add_argument("--source-url", default=os.getenv("CMP_DATABASE_URL"))
    parser.add_argument("--object-store-root", default=os.getenv("CMP_UPLOAD_STORAGE_ROOT"))
    parser.add_argument("--work-root", default="/var/lib/cmp/restore-reports")
    parser.add_argument("--sample-limit", type=int, default=100)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.source_url or not args.object_store_root:
        raise SystemExit("--source-url and --object-store-root are required")
    try:
        report = run_drill(
            source_url=str(args.source_url),
            object_store_root=Path(args.object_store_root),
            work_root=Path(args.work_root),
            sample_limit=args.sample_limit,
        )
    except RestoreDrillError as error:
        print(f"restore drill failed: {error}")
        return 1
    print(f"restore drill passed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
