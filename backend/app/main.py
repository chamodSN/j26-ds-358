from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers the tables)
from app.config import settings
from app.db import Base, engine
from app.routers import auth, catalog, history, saved, search, system
from app.services.ebay import ebay


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.is_production and settings.secret_key.startswith("dev-only"):
        raise RuntimeError("Set a real SECRET_KEY in .env before running in production.")
    Base.metadata.create_all(engine)  # simple for v1. Move to Alembic later.
    yield
    await ebay.aclose()


app = FastAPI(title="Vero API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(catalog.router)
app.include_router(saved.router)
app.include_router(history.router)