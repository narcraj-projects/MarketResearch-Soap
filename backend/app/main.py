"""FastAPI scaffold; no research, database or paid-service calls at startup."""
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal

from app.config import Settings
from app.api import router
from app.db import build_engine
from app.security import IngressGuard, configure_private_logging
from fastapi.exceptions import RequestValidationError
from app.api_schemas import Error


class Health(BaseModel):
    status: Literal["alive", "ready", "not_ready"]
    mode: Literal["replay"] = "replay"
    database: Literal["not_checked"] = "not_checked"
    external_calls_enabled: Literal[False] = False


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.initialized = True
        try:
            yield
        finally:
            application.state.initialized = False
            if application.state.engine is not None:
                application.state.engine.dispose()

    application = FastAPI(title="Lather Lens", version="0.1.0", lifespan=lifespan,
        responses={code: {"model": Error} for code in (400, 413, 414, 415, 422, 429, 431)})
    configure_private_logging()
    application.add_middleware(IngressGuard)

    @application.exception_handler(RequestValidationError)
    async def private_validation_error(request: Request, error: RequestValidationError):
        # Pydantic hide_input_in_errors does not redact FastAPI's JSON errors.
        return JSONResponse(status_code=422, content={"detail": "invalid_request"})

    application.state.settings = settings
    application.state.initialized = False
    # Construct one pool without connecting; avoids racing pool creation on requests.
    application.state.engine = build_engine(settings) if settings.database_url is not None else None
    application.include_router(router)

    @application.middleware("http")
    async def private_api(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "Authorization"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @application.get("/health/live", response_model=Health)
    def live() -> Health:
        return Health(status="alive")

    @application.get("/health/ready", response_model=Health, responses={503: {"model": Health}})
    def ready(request: Request) -> Health | JSONResponse:
        if not request.app.state.initialized:
            return JSONResponse(status_code=503, content=Health(status="not_ready").model_dump())
        return Health(status="ready")

    return application


app = create_app()
