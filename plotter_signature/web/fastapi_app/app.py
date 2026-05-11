from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from plotter_signature.dependency_injection import ServiceProvider, get_service_provider
from plotter_signature.infrastructure.errors.api_error_codes import (
    fastapi_http_exception_legacy_token,
    fastapi_validation_error_legacy_token,
    format_fastapi_message,
    numeric_code_for_legacy,
)
from plotter_signature.infrastructure.security.api_key_auth import (
    API_KEY_REQUIRED_MESSAGE,
    get_configured_api_key,
)
from plotter_signature.web.fastapi_app.printer_controller import create_printer_router
from plotter_signature.web.last_api_error import clear_last_api_error, record_api_error
from plotter_signature.web.startup_serial import run_startup_autoconnect


def create_app(provider: ServiceProvider | None = None) -> FastAPI:
    if not get_configured_api_key():
        raise RuntimeError(API_KEY_REQUIRED_MESSAGE)

    provider = provider or get_service_provider()

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ARG001
        await asyncio.to_thread(run_startup_autoconnect, provider.printer_service)
        yield

    app = FastAPI(title="Plotter Signature API", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def clear_last_api_error_after_mutating_success(request: Request, call_next):
        response = await call_next(request)
        if request.method not in ("GET", "HEAD") and 200 <= response.status_code < 300:
            clear_last_api_error()
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        legacy = fastapi_http_exception_legacy_token(exc.status_code, exc.detail)
        final_message = format_fastapi_message(legacy, exc.detail)
        numeric = numeric_code_for_legacy(legacy)
        record_api_error(
            error_code=numeric,
            message=final_message,
            status_code=exc.status_code,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": final_message,
                "data": None,
                "errorCode": numeric,
                "details": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        legacy = fastapi_validation_error_legacy_token()
        preview = str(exc.errors())[:4000]
        final_message = format_fastapi_message(legacy, f"Validation failed: {preview}")
        numeric = numeric_code_for_legacy(legacy)
        record_api_error(
            error_code=numeric,
            message=final_message,
            status_code=422,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": final_message,
                "data": None,
                "errorCode": numeric,
                "details": exc.errors(),
            },
        )

    app.include_router(create_printer_router(provider))

    @app.get("/")
    async def root():
        return {"message": "Plotter Signature API"}

    return app


app = create_app()
