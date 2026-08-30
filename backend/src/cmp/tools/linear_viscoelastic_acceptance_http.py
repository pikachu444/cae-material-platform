"""HTTP/session and immutable resource primitives for linear-viscoelastic acceptance."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, cast

import httpx


class LinearViscoelasticAcceptanceError(RuntimeError):
    """The live acceptance API rejected or lost required evidence."""


def response_json(response: httpx.Response) -> dict[str, Any]:
    """Decode one successful object response and preserve useful failure evidence."""

    if response.is_error:
        try:
            detail: object = response.json()
        except ValueError:
            detail = response.text[:1000]
        raise LinearViscoelasticAcceptanceError(
            f"{response.request.method} {response.request.url.path} returned "
            f"{response.status_code}: {detail}"
        )
    value = response.json()
    if not isinstance(value, dict):
        raise LinearViscoelasticAcceptanceError("live API returned a non-object response")
    return cast(dict[str, Any], value)


def required_mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LinearViscoelasticAcceptanceError(f"{name} is missing from the live response")
    return cast(dict[str, Any], value)


def required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LinearViscoelasticAcceptanceError(f"{name} is missing from the live response")
    return value


def response_items(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = value.get("items")
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise LinearViscoelasticAcceptanceError("live list response has no object items")
    return cast(list[dict[str, Any]], raw)


def response_list(response: httpx.Response) -> list[dict[str, Any]]:
    """Decode one successful list response from the calibration API."""

    if response.is_error:
        try:
            detail: object = response.json()
        except ValueError:
            detail = response.text[:1000]
        raise LinearViscoelasticAcceptanceError(
            f"{response.request.method} {response.request.url.path} returned "
            f"{response.status_code}: {detail}"
        )
    value = response.json()
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise LinearViscoelasticAcceptanceError("live list response has no object items")
    return cast(list[dict[str, Any]], value)


def revision_id(value: Mapping[str, Any]) -> str:
    revision = required_mapping(value.get("current_revision"), "current_revision")
    return required_string(revision.get("id"), "current_revision.id")


def current_revision_content(value: Mapping[str, Any]) -> Mapping[str, Any]:
    revision = required_mapping(value.get("current_revision"), "current revision")
    content = revision.get("content")
    if content is None:
        content = value.get("content")
    return required_mapping(content, "current revision content")


def artifact_reference(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return only immutable Artifact identity/fact fields accepted by API resources."""

    return {
        "artifact_id": value["artifact_id"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
        "media_type": value["media_type"],
    }


def upload_artifact(
    client: httpx.Client,
    *,
    value: bytes,
    filename: str,
    media_type: str,
    idempotency_key: str,
    test_run_revision_id: str | None = None,
) -> dict[str, Any]:
    """Upload exact bytes through the normal multipart Artifact API."""

    digest = hashlib.sha256(value).hexdigest()
    body: dict[str, Any] = {
        "classification": "internal",
        "original_filename": filename,
        "media_type": media_type,
        "expected_size_bytes": len(value),
        "expected_sha256": digest,
    }
    if test_run_revision_id is not None:
        body["test_run_revision_id"] = test_run_revision_id
    created = response_json(
        client.post("/uploads", json=body, headers={"Idempotency-Key": idempotency_key})
    )
    upload = required_mapping(created.get("upload"), "upload")
    capability = required_string(created.get("upload_capability"), "upload_capability")
    upload_id = required_string(upload.get("upload_id"), "upload.upload_id")
    part_size = int(upload["part_size_bytes"])
    part_count = int(upload["expected_part_count"])
    if upload.get("state") == "open":
        for part_number in range(1, part_count + 1):
            start = (part_number - 1) * part_size
            response = client.put(
                f"/uploads/{upload_id}/parts/{part_number}",
                content=value[start : start + part_size],
                headers={"Content-Type": media_type, "Upload-Capability": capability},
            )
            response_json(response)
    completed = response_json(
        client.post(
            f"/uploads/{upload_id}:complete",
            headers={"Upload-Capability": capability},
        )
    )
    raw_asset = required_mapping(completed.get("raw_asset"), "raw_asset")
    return {
        "raw_asset_id": required_string(raw_asset.get("raw_asset_id"), "raw_asset_id"),
        "artifact_id": required_string(
            completed.get("available_artifact_id"), "available_artifact_id"
        ),
        "sha256": digest,
        "size_bytes": len(value),
        "media_type": media_type,
    }


@contextmanager
def authenticated_client(api_base_url: str) -> Iterator[httpx.Client]:
    """Acquire a fresh demo access token and yield one scoped API session."""

    base_url = api_base_url.rstrip("/")
    with httpx.Client(base_url=base_url, timeout=90.0) as anonymous:
        token = required_string(
            response_json(anonymous.get("/demo-identity/token")).get("access_token"),
            "access_token",
        )
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=90.0,
    ) as client:
        yield client
