from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import httpx
from prometheus_client import REGISTRY, generate_latest

logger = logging.getLogger(__name__)


def publish_metrics(*, run_success: bool) -> None:
    job_metrics = generate_latest(REGISTRY).decode("utf-8").strip()
    timestamp = time.time()
    extra = "\n".join(
        [
            "# HELP doctorku_last_run_success 1 si la ultima ejecucion del runner termino ok.",
            "# TYPE doctorku_last_run_success gauge",
            f"doctorku_last_run_success {1 if run_success else 0}",
            "# HELP doctorku_last_run_timestamp_seconds Timestamp Unix de la ultima ejecucion del runner.",
            "# TYPE doctorku_last_run_timestamp_seconds gauge",
            f"doctorku_last_run_timestamp_seconds {timestamp:.3f}",
        ]
    )
    body = f"{job_metrics}\n{extra}\n"

    push_url = os.getenv("METRICS_PUSH_URL", "").strip()
    if push_url:
        try:
            response = httpx.post(
                push_url,
                content=body,
                headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
                timeout=10,
            )
            response.raise_for_status()
            logger.info("metricas enviadas a %s", push_url)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("no se pudieron enviar metricas a %s: %s", push_url, exc)

    metrics_file = os.getenv("METRICS_FILE", "").strip()
    if metrics_file:
        path = Path(metrics_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".prom.tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)
        logger.info("metricas escritas en %s", path)
        return

    logger.warning("METRICS_PUSH_URL y METRICS_FILE no configurados, metricas no publicadas")
