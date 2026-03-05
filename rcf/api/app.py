"""FastAPI application — entry point for the RCF REST API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from rcf.api.routes import cases, lawyers, owners, properties

_WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

app = FastAPI(
    title="RCF — Refund Claim Finder",
    description="API for browsing refund eligibility cases and managing the lawyer-owner marketplace.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
app.include_router(properties.router, prefix="/api/properties", tags=["properties"])
app.include_router(lawyers.router, prefix="/api/lawyers", tags=["lawyers"])
app.include_router(owners.router, prefix="/api/owners", tags=["owners"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def serve_gui():
    return FileResponse(_WEB_DIR / "index.html")
