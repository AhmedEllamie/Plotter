from __future__ import annotations

from fastapi import FastAPI

from diwan_signature.dependency_injection import ServiceProvider, get_service_provider
from diwan_signature.web.fastapi_app.printer_controller import create_printer_router


def create_app(provider: ServiceProvider | None = None) -> FastAPI:
    provider = provider or get_service_provider()
    app = FastAPI(title="Diwan Signature API", version="1.0.0")
    app.include_router(create_printer_router(provider))

    @app.get("/")
    async def root():
        return {"message": "Diwan Signature API"}

    return app


app = create_app()

