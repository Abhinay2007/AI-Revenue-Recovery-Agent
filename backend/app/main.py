import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import db_health, health, recovery
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.health import check_database_health

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("application startup")
    init_db()
    with SessionLocal() as db:
        check_database_health(db)
    logger.info("database connection ok")
    yield
    logger.info("application shutdown")


app = FastAPI(title="AI Revenue Recovery Agent", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(db_health.router)
app.include_router(recovery.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("api error")
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
