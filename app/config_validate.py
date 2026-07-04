from __future__ import annotations

import logging

from app.config import resolve_install_script_path, resolve_node_ssh_key, settings
from app.models import AppConfig
from app.notifier import is_usable_hook_url

logger = logging.getLogger(__name__)

_SSH_PLACEHOLDER_MARKERS = (
    "reemplazar",
    "changeme",
    "placeholder",
    "example",
)


def _is_placeholder_ssh_key(key: str) -> bool:
    normalized = key.strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in _SSH_PLACEHOLDER_MARKERS)


def validate_app_config(config: AppConfig) -> list[str]:
    issues: list[str] = []

    if config.notification.enabled and not is_usable_hook_url(config.notification.hook_url):
        issues.append(
            "notificacion habilitada pero hook_url invalida o placeholder "
            f"({config.notification.hook_url!r})"
        )

    install_script = resolve_install_script_path("k3s-install.sh")
    if not install_script.is_file():
        issues.append(f"script k3s no encontrado en {settings.scripts_dir}")

    for cluster in config.clusters:
        if not cluster.k3s_kubeconfig_path.strip():
            issues.append(f"cluster={cluster.name}: k3s_kubeconfig_path vacio")
        if not cluster.k3s_token_path.strip():
            issues.append(f"cluster={cluster.name}: k3s_token_path vacio")

        for node in cluster.nodes:
            ssh_key = resolve_node_ssh_key(cluster.ssh_key, node, settings.ssh_keys_dir)
            if _is_placeholder_ssh_key(ssh_key):
                issues.append(
                    f"cluster={cluster.name} nodo={node.name}: clave ssh ausente o placeholder"
                )

        script_path = resolve_install_script_path(cluster.commands.install_script)
        if not script_path.is_file():
            issues.append(
                f"cluster={cluster.name}: install_script no encontrado ({script_path})"
            )

    return issues


def log_config_issues(config: AppConfig) -> None:
    issues = validate_app_config(config)
    if not issues:
        logger.info("validacion de configuracion ok clusters=%s", len(config.clusters))
        return

    logger.warning(
        "configuracion incompleta (%s problemas); chequeos pueden fallar:",
        len(issues),
    )
    for issue in issues:
        logger.warning("  - %s", issue)
