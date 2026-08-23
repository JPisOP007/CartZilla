"""Application entry point.

One process serves both the JSON API under ``/api`` and the static frontend at
``/``. That keeps deployment to a single service with no CORS configuration and
no separate frontend build step.

Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.catalog.data import all_products

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Load and validate the catalog at boot rather than on the first request,
    # so a malformed data file fails fast and visibly.
    logger.info("catalog loaded: %d products", len(all_products()))
    yield


app = FastAPI(
    lifespan=lifespan,
    title="CartZilla",
    description=(
        "A voice-driven shopping list with natural-language command parsing, "
        "catalog search and explainable recommendations. The API is stateless: "
        "the browser owns the shopping list."
    ),
    version=__version__,
)

app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a readable error instead of leaking a traceback to the user."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something went wrong on our end. Please try again.",
        },
    )


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    """Plain liveness endpoint for platform health checks."""
    return {"status": "ok"}


class RevalidatedStaticFiles(StaticFiles):
    """Static assets that are always revalidated before use.

    With only ETag and Last-Modified and no explicit Cache-Control, browsers
    fall back to *heuristic* caching and may keep an ES module for hours. That
    produces the worst kind of deployment bug: a stale frontend talking to a
    freshly deployed backend, where the API returns two items and the page
    only knows how to add one.

    "no-cache" does not mean "do not store" - the browser still caches, it just
    revalidates first, so the usual response is an empty 304. These assets are
    a few kilobytes, so correctness is worth far more than the saved request.
    """

    def file_response(self, *args: object, **kwargs: object) -> Response:
        response = super().file_response(*args, **kwargs)  # type: ignore[arg-type]
        response.headers.setdefault("Cache-Control", "no-cache")
        return response


if WEB_DIR.is_dir():
    # html=True serves index.html at "/" and gives a sensible 404 page.
    app.mount("/", RevalidatedStaticFiles(directory=WEB_DIR, html=True), name="web")
else:  # pragma: no cover - only hit if the build is packaged incorrectly.
    logger.warning("web directory not found at %s; serving API only", WEB_DIR)

    @app.get("/", include_in_schema=False)
    def _missing_frontend() -> dict[str, str]:
        return {"detail": "Frontend assets are not available in this deployment."}
