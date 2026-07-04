from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Coroutine
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.checker import ClusterChecker, Remediator
from app.config import load_app_config, resolve_check_cron
from app.config_validate import log_config_issues
from app.metrics import sync_remediation_metrics
from app.models import AppConfig, NodeCheckResult
from app.notifier import Notifier

logger = logging.getLogger(__name__)


class DoctorScheduler:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()
        self._config: AppConfig = AppConfig()
        self._last_results: dict[str, list[NodeCheckResult]] = {}
        self._last_run_at: dict[str, str] = {}
        self._notifier = Notifier(AppConfig().notification)
        self._remediator = Remediator(self._notifier, failure_counts={})
        self._checker = ClusterChecker(self._remediator, self._notifier)
        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(
            target=self._run_async_loop,
            name="doctor-ku-async",
            daemon=True,
        )
        self._async_thread.start()

    def start(self) -> None:
        self.reload()
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("scheduler iniciado")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self._async_loop.call_soon_threadsafe(self._async_loop.stop)
        logger.info("scheduler detenido")

    def reload(self) -> None:
        self._config = load_app_config()
        log_config_issues(self._config)
        sync_remediation_metrics(self._config.clusters)
        self._notifier = Notifier(self._config.notification)
        self._remediator = Remediator(self._notifier, failure_counts={})
        self._checker = ClusterChecker(self._remediator, self._notifier)

        for job in self._scheduler.get_jobs():
            self._scheduler.remove_job(job.id)

        tz = ZoneInfo(self._config.global_.timezone)
        for cluster in self._config.clusters:
            cron = resolve_check_cron(cluster, self._config.global_)
            self._scheduler.add_job(
                self._run_cluster_check,
                trigger=CronTrigger.from_crontab(cron, timezone=tz),
                id=f"cluster-{cluster.name}",
                kwargs={"cluster_name": cluster.name},
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info(
                "job programado para cluster %s cron=%r timezone=%s",
                cluster.name,
                cron,
                self._config.global_.timezone,
            )

    def _run_cluster_check(self, cluster_name: str) -> None:
        logger.info("ejecutando job cluster=%s", cluster_name)
        cluster = next((item for item in self._config.clusters if item.name == cluster_name), None)
        if cluster is None:
            logger.warning("cluster %s no encontrado en config", cluster_name)
            return

        try:
            results = self._checker.check_cluster(
                cluster,
                self._schedule_notification,
                remediation_enabled=self._config.remediation.enabled,
            )
            self._last_results[cluster_name] = results
            self._last_run_at[cluster_name] = datetime.now(
                ZoneInfo(self._config.global_.timezone)
            ).isoformat()
        except Exception:  # noqa: BLE001
            logger.exception("error chequeando cluster %s", cluster_name)

    def _schedule_notification(self, coro: Coroutine[Any, Any, bool]) -> None:
        asyncio.run_coroutine_threadsafe(coro, self._async_loop)

    def _run_async_loop(self) -> None:
        asyncio.set_event_loop(self._async_loop)
        self._async_loop.run_forever()

    def get_status(self) -> dict[str, Any]:
        return {
            "remediation": self._config.remediation.model_dump(),
            "clusters": [
                {
                    "name": cluster.name,
                    "check_cron": resolve_check_cron(cluster, self._config.global_),
                    "timezone": self._config.global_.timezone,
                    "remediation": cluster.remediation.model_dump(),
                    "last_run_at": self._last_run_at.get(cluster.name),
                    "nodes": [
                        result.model_dump()
                        for result in self._last_results.get(cluster.name, [])
                    ],
                }
                for cluster in self._config.clusters
            ],
            "notification": self._config.notification.model_dump(),
        }
