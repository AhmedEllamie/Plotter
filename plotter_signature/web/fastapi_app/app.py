from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from plotter_signature.dependency_injection import ServiceProvider, get_service_provider
from plotter_signature.infrastructure.security.api_key_auth import (
    API_KEY_REQUIRED_MESSAGE,
    get_configured_api_key,
)
from plotter_signature.web.fastapi_app.printer_controller import create_printer_router
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
    app.include_router(create_printer_router(provider))

    @app.get("/")
    async def root():
        return {"message": "Plotter Signature API"}

    return app


app = create_app()

