"""Node-free static Web front door with a same-origin API proxy."""

from __future__ import annotations

import argparse
import math
import os
from collections.abc import Sequence
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

_HOP_BY_HOP = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
_DEFAULT_API_TIMEOUT_SECONDS = 30.0
_API_CONNECT_TIMEOUT_SECONDS = 5.0


def _proxy_headers(headers: httpx.Headers) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.lower() not in _HOP_BY_HOP}


def create_app(
    *,
    static_root: Path,
    api_target: str,
    transport: httpx.AsyncBaseTransport | None = None,
    api_timeout_seconds: float = _DEFAULT_API_TIMEOUT_SECONDS,
) -> FastAPI:
    """Create the immutable-build Web server without requiring Node at runtime."""

    root = static_root.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise ValueError(f"Web build is missing index.html: {index}")
    target = api_target.rstrip("/")
    if not target.startswith(("http://", "https://")):
        raise ValueError("API target must be an explicit HTTP(S) URL")
    if not math.isfinite(api_timeout_seconds) or api_timeout_seconds <= 0:
        raise ValueError("API timeout must be a finite positive number")
    timeout = httpx.Timeout(
        api_timeout_seconds,
        connect=min(_API_CONNECT_TIMEOUT_SECONDS, api_timeout_seconds),
    )

    application = FastAPI(
        title="CAE Material Platform Web front door",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    assets = root / "assets"
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="assets")

    @application.get("/.cmp/health", include_in_schema=False)
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @application.api_route(
        "/api/{path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def proxy_api(path: str, request: Request) -> Response:
        query = request.url.query
        url = f"{target}/api/{path}"
        if query:
            url = f"{url}?{query}"
        headers = {
            key: value for key, value in request.headers.items() if key.lower() not in _HOP_BY_HOP
        }
        try:
            async with httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                timeout=timeout,
            ) as client:
                upstream = await client.request(
                    request.method,
                    url,
                    headers=headers,
                    content=await request.body(),
                )
        except httpx.TimeoutException:
            return JSONResponse(
                status_code=504,
                content={
                    "code": "CMP-WEB-API-TIMEOUT",
                    "detail": "The upstream API did not respond within the configured timeout.",
                },
                headers={"Retry-After": "1"},
            )
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=_proxy_headers(upstream.headers),
        )

    @application.get("/{path:path}", include_in_schema=False)
    def static_or_spa(path: str) -> FileResponse:
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    return application


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=os.getenv("CMP_WEB_STATIC_ROOT"))
    parser.add_argument(
        "--api-target",
        default=os.getenv("CMP_WEB_API_TARGET", "http://127.0.0.1:8000"),
    )
    parser.add_argument("--host", default=os.getenv("CMP_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CMP_WEB_PORT", "5173")))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.root is None:
        raise SystemExit("CMP_WEB_STATIC_ROOT or --root is required")
    import uvicorn

    application = create_app(static_root=args.root, api_target=args.api_target)
    uvicorn.run(application, host=args.host, port=args.port, access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
