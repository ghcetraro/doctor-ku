from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from app.checker import ClusterChecker, Remediator
from app.config import load_app_config, settings
from app.config_validate import log_config_issues
from app.logging_config import setup_logging
from app.metrics import sync_remediation_metrics
from app.metrics_push import publish_metrics
from app.notifier import Notifier
from app.state_store import (
    load_state,
    now_iso,
    save_state,
    serialize_results,
)

logger = logging.getLogger(__name__)


def _notify(coro: Any) -> None:
    asyncio.run(coro)


def run_checks() -> int:
    setup_logging(settings.log_level)
    config = load_app_config()
    log_config_issues(config)
    sync_remediation_metrics(config.clusters)

    state = load_state()
    notifier = Notifier(config.notification)
    remediator = Remediator(notifier, failure_counts=dict(state.failure_counts))
    checker = ClusterChecker(remediator, notifier)

    exit_code = 0
    timezone = config.global_.timezone

    for cluster in config.clusters:
        logger.info("runner inicio cluster=%s", cluster.name)
        try:
            results = checker.check_cluster(
                cluster,
                _notify,
                remediation_enabled=config.remediation.enabled,
            )
        except Exception:  # noqa: BLE001
            logger.exception("runner error cluster=%s", cluster.name)
            exit_code = 1
            continue

        state.last_results[cluster.name] = serialize_results(results)
        state.last_run_at[cluster.name] = now_iso(timezone)
        state.failure_counts = dict(remediator.export_failure_counts())

        for result in results:
            if result.remediated and not result.remediation_ok:
                exit_code = 1

        logger.info(
            "runner fin cluster=%s nodos=%s remediations=%s",
            cluster.name,
            len(results),
            sum(1 for item in results if item.remediated),
        )

    save_state(state)
    return exit_code


def main() -> None:
    exit_code = 1
    try:
        exit_code = run_checks()
    except Exception:  # noqa: BLE001
        logger.exception("runner fallo")
    finally:
        publish_metrics(run_success=exit_code == 0)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
