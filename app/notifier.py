from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models import NotificationConfig

logger = logging.getLogger(__name__)

_PLACEHOLDER_HOSTS = frozenset({"example.com", "example.org", "localhost"})


def is_usable_hook_url(url: str) -> bool:
    url = url.strip()
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in _PLACEHOLDER_HOSTS:
        return False
    if "example" in host or "changeme" in host:
        return False
    return True


class Notifier:
    def __init__(self, config: NotificationConfig) -> None:
        self.config = config
        self._hook_misconfigured = config.enabled and not is_usable_hook_url(config.hook_url)
        if self._hook_misconfigured:
            logger.warning(
                "notificaciones habilitadas pero hook_url invalida o placeholder: %r",
                config.hook_url,
            )

    async def send_unremediated(
        self,
        cluster: str,
        node: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> bool:
        if not self._can_send():
            logger.warning(
                "no se pudo remediar %s/%s: %s (notificacion no disponible)",
                cluster,
                node,
                reason,
            )
            return False

        payload = {
            "event": "doctorku_unremediated",
            "cluster": cluster,
            "node": node,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        return await self._send(payload)

    async def send_remediation_result(
        self,
        cluster: str,
        node: str,
        result: str,
        duration_seconds: float,
        details: dict[str, Any] | None = None,
    ) -> bool:
        if not self._can_send():
            return False

        payload = {
            "event": "doctorku_remediation",
            "cluster": cluster,
            "node": node,
            "result": result,
            "duration_seconds": duration_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        return await self._send(payload)

    def _can_send(self) -> bool:
        return self.config.enabled and is_usable_hook_url(self.config.hook_url)

    async def _send(self, payload: dict[str, Any]) -> bool:
        if not self._can_send():
            return False
        try:
            async with httpx.AsyncClient(timeout=self.config.hook_timeout_seconds) as client:
                response = await client.request(
                    self.config.hook_method.upper(),
                    self.config.hook_url,
                    json=payload,
                    headers=self.config.hook_headers,
                )
                response.raise_for_status()
                logger.info("notificacion enviada: %s", payload.get("event"))
                return True
        except httpx.ConnectError as exc:
            logger.warning("fallo envio de notificacion (conexion): %s", exc)
            return False
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "fallo envio de notificacion (http %s): %s",
                exc.response.status_code,
                exc,
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("fallo envio de notificacion: %s", exc)
            return False
