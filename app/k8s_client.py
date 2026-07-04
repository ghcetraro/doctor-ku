from __future__ import annotations

import logging
from typing import Optional

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class K8sClient:
    def __init__(self) -> None:
        self._api: Optional[client.CoreV1Api] = None
        self._available = False
        self._error = ""

    @classmethod
    def from_content(cls, kubeconfig_content: str) -> "K8sClient":
        instance = cls()
        if not kubeconfig_content.strip():
            instance._error = "kubeconfig vacio"
            logger.warning("k8s: %s", instance._error)
            return instance
        try:
            config_dict = yaml.safe_load(kubeconfig_content) or {}
            config.load_kube_config_from_dict(config_dict)
            instance._api = client.CoreV1Api()
            instance._api.list_node(limit=1)
            instance._available = True
            logger.info("k8s cliente listo desde kubeconfig remoto")
        except Exception as exc:  # noqa: BLE001
            instance._error = str(exc)
            logger.warning("k8s client init failed: %s", exc)
        return instance

    @property
    def available(self) -> bool:
        return self._available

    @property
    def error(self) -> str:
        return self._error

    def get_node_status(self, node_name: str) -> tuple[Optional[bool], str, str]:
        if not self._available or self._api is None:
            return None, "unknown", self._error or "cliente k8s no disponible"
        try:
            node = self._api.read_node(node_name)
            for condition in node.status.conditions or []:
                if condition.type == "Ready":
                    ready = condition.status == "True"
                    status = "Ready" if ready else "NotReady"
                    logger.info("k8s nodo %s estado=%s", node_name, status)
                    return ready, status, ""
            logger.info("k8s nodo %s estado=NotReady (sin condicion Ready)", node_name)
            return False, "NotReady", ""
        except ApiException as exc:
            if exc.status == 404:
                logger.warning("k8s nodo %s no encontrado en el cluster", node_name)
                return None, "missing", "nodo no encontrado en el cluster"
            logger.error("k8s error leyendo nodo %s: %s", node_name, exc)
            return None, "error", str(exc)
        except Exception as exc:  # noqa: BLE001
            return None, "error", str(exc)

    def delete_node(self, node_name: str, dry_run: bool = False) -> tuple[bool, str]:
        if not self._available or self._api is None:
            return False, self._error or "cliente k8s no disponible"
        if dry_run:
            return True, "dry-run: delete node omitido"
        try:
            logger.info("k8s delete node %s", node_name)
            self._api.delete_node(node_name)
            logger.info("k8s nodo %s eliminado del cluster", node_name)
            return True, "nodo eliminado del cluster"
        except ApiException as exc:
            if exc.status == 404:
                logger.info("k8s nodo %s ya no existe en el cluster", node_name)
                return True, "nodo ya no existia en el cluster"
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
