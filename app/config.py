from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models import AppConfig, ClusterConfig, GlobalConfig, NodeConfig


def resolve_check_cron(cluster: ClusterConfig, global_config: GlobalConfig) -> str:
    cron = (cluster.check_cron or global_config.default_check_cron).strip()
    if not cron:
        raise ValueError(f"cluster={cluster.name}: check_cron no configurado")
    return cron


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    config_path: Path = Path("/config/clusters.yaml")
    host: str = "0.0.0.0"
    port: int = 8080
    ssh_keys_dir: Path = Path("/secrets/ssh")
    scripts_dir: Path = Path("/scripts")
    log_level: str = "INFO"
    run_timeout_seconds: int = 1500


settings = Settings()


def load_app_config(path: Optional[Path] = None) -> AppConfig:
    config_file = path or settings.config_path
    if not config_file.exists():
        return AppConfig()

    with config_file.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    _expand_env_vars(raw)
    return AppConfig.model_validate(raw)


def _expand_env_vars(value: object) -> object:
    if isinstance(value, dict):
        return {key: _expand_env_vars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def resolve_ssh_key(
    *,
    key_name: str = "",
    key_path: str = "",
    inline_key: str = "",
    keys_dir: Path,
) -> str:
    if inline_key.strip():
        return inline_key.strip()

    if key_path.strip():
        path = Path(key_path)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        if keys_dir.exists():
            by_name = keys_dir / path.name
            if by_name.is_file():
                return by_name.read_text(encoding="utf-8")

    if key_name.strip() and keys_dir.exists():
        candidate = keys_dir / key_name.strip()
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")

    return ""


def resolve_node_ssh_key(cluster_ssh_key: str, node: NodeConfig, keys_dir: Path) -> str:
    return resolve_ssh_key(
        key_name=node.ssh_key or cluster_ssh_key,
        key_path=node.ssh_key_path,
        inline_key=node.ssh_private_key,
        keys_dir=keys_dir,
    )


def resolve_install_script_path(cluster_install_script: str) -> Path:
    script_name = cluster_install_script.strip() or "k3s-install.sh"
    return settings.scripts_dir / script_name
