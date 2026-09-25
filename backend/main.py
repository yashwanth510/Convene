import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.api.admin import router as admin_router
from backend.api.routes import router
from backend.api.auth import router as auth_router
from backend.config import config
from backend.storage.database import Database, StoreError
from backend.llm.gateway import Gateway
from backend.core.evidence import EvidenceService
from backend.core.run_service import RunService


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = (
            16 * 1024 * 1024 if scope["path"].endswith("/files/parse") else 512 * 1024
        )
        headers = dict(scope.get("headers", []))
        try:
            announced = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse(
                {"detail": "Invalid content length"}, status_code=400
            )(scope, receive, send)
        if announced > limit:
            return await JSONResponse(
                {"detail": "Request is too large"}, status_code=413
            )(scope, receive, send)
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > limit:
                raise HTTPException(413, "Request is too large")
            return message

        return await self.app(scope, limited_receive, send)


def create_app(database_url=None, gateway_factory=Gateway):
    @asynccontextmanager
    async def lifespan(app):
        if config.APP_ENV == "production":
            if not config.INVITE_CODE or len(config.INVITE_CODE) < 16:
                raise RuntimeError(
                    "Production requires INVITE_CODE of at least 16 characters"
                )
            if not (database_url or config.DATABASE_URL).startswith(
                ("postgresql:", "postgresql+asyncpg:")
            ):
                raise RuntimeError(
                    "Production requires a persistent PostgreSQL DATABASE_URL"
                )
            if (
                not config.CORS_ORIGINS
                or "*" in config.CORS_ORIGINS
                or any(
                    not origin.startswith("https://") for origin in config.CORS_ORIGINS
                )
            ):
                raise RuntimeError("Production requires explicit HTTPS CORS_ORIGINS")
        db = Database(database_url or config.DATABASE_URL)
        gateway = gateway_factory()
        try:
            await db.initialize()
            await db.recover_interrupted()
            app.state.db = db
            app.state.gateway = gateway
            app.state.auth_attempts = {}
            app.state.parse_limit = asyncio.Semaphore(2)
            app.state.runs = RunService(db, gateway, EvidenceService(gateway.client))
            yield
        finally:
            if hasattr(app.state, "runs"):
                await app.state.runs.close()
            await gateway.close()
            await db.close()

    app = FastAPI(
        title="Convene API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if config.APP_ENV != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
    )

    @app.exception_handler(StoreError)
    async def storage_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=error.status)

    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(router, prefix="/api")
    app.include_router(admin_router, prefix="/api/admin")

    @app.get("/")
    async def root():
        return {"app": "Convene", "version": "1.0.0"}

    return app


app = create_app()
