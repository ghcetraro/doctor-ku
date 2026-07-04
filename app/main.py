from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import load_app_config, settings
from app.config_validate import log_config_issues
from app.logging_config import setup_logging
from app.scheduler import DoctorScheduler

setup_logging(settings.log_level)

logger = logging.getLogger(__name__)
doctor_scheduler = DoctorScheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    config = load_app_config()
    log_config_issues(config)
    logger.info(
        "doctor-ku iniciado config=%s clusters=%s log_level=%s",
        settings.config_path,
        len(config.clusters),
        settings.log_level,
    )
    doctor_scheduler.start()
    yield
    doctor_scheduler.shutdown()
    logger.info("doctor-ku detenido")


app = FastAPI(
    title="Doctor-ku",
    description="Monitor y remediador de clusters k3s por SSH y Kubernetes.",
    version="1.0.4",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, Any]:
    config = load_app_config()
    return {
        "status": "ok",
        "clusters": len(config.clusters),
        "config_path": str(settings.config_path),
        "timezone": config.global_.timezone,
    }


@app.get("/status")
def status() -> dict[str, Any]:
    return doctor_scheduler.get_status()


@app.post("/reload")
def reload_config() -> dict[str, str]:
    logger.info("recargando configuracion desde %s", settings.config_path)
    doctor_scheduler.reload()
    return {"status": "reloaded"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
