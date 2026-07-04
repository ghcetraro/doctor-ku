from __future__ import annotations

from typing import Literal, Optional

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, field_validator


def validate_cron_expression(expr: str) -> str:
    cron = expr.strip()
    if not cron:
        raise ValueError("expresion cron vacia")
    try:
        CronTrigger.from_crontab(cron)
    except ValueError as exc:
        raise ValueError(f"expresion cron invalida: {cron!r} ({exc})") from exc
    return cron


class NotificationConfig(BaseModel):
    enabled: bool = False
    hook_url: str = ""
    hook_method: str = "POST"
    hook_headers: dict[str, str] = Field(default_factory=dict)
    hook_timeout_seconds: int = 10


class RemediationCommands(BaseModel):
    install_script: str = "k3s-install.sh"
    remote_install_script: str = "/tmp/k3s-install.sh"
    command_delay_seconds: int = 5
    uninstall: list[str] = Field(
        default_factory=lambda: [
            "sudo test -x /usr/local/bin/k3s-uninstall.sh && sudo /usr/local/bin/k3s-uninstall.sh || true",
            "sudo test -x /usr/local/bin/k3s-agent-uninstall.sh && sudo /usr/local/bin/k3s-agent-uninstall.sh || true",
        ]
    )
    master_install: str = (
        "curl -sfL https://get.k3s.io | sudo env K3S_TOKEN={{K3S_TOKEN}} "
        "INSTALL_K3S_VERSION={{K3S_VERSION}} INSTALL_K3S_FORCE_RESTART=true "
        "sh -s - server --server {{BOOTSTRAP_SERVER}}"
    )
    worker_install: str = (
        "curl -sfL https://get.k3s.io | sudo env K3S_URL={{BOOTSTRAP_SERVER}} "
        "K3S_TOKEN={{K3S_TOKEN}} INSTALL_K3S_VERSION={{K3S_VERSION}} "
        "INSTALL_K3S_FORCE_RESTART=true sh -"
    )
    pre_remediation: list[str] = Field(default_factory=list)
    post_remediation: list[str] = Field(default_factory=list)


class RemediationGlobalConfig(BaseModel):
    enabled: bool = True


class RemediationConfig(BaseModel):
    enabled: bool = True
    max_nodes_per_cycle: int = 1
    failure_threshold: int = 2
    dry_run: bool = False


class NodeConfig(BaseModel):
    name: str
    host: str
    role: Literal["master", "worker"]
    ssh_user: str = ""
    ssh_port: int = 22
    ssh_key: str = ""
    ssh_key_path: str = ""
    ssh_private_key: str = ""


class ClusterConfig(BaseModel):
    name: str
    check_cron: str = ""
    k3s_kubeconfig_path: str = "/etc/rancher/k3s/k3s.yaml"
    k3s_token_path: str = "/var/lib/rancher/k3s/server/node-token"
    ssh_key: str = ""
    ssh_user: str = "root"
    ssh_port: int = 22
    remediation: RemediationConfig = Field(default_factory=RemediationConfig)
    commands: RemediationCommands = Field(default_factory=RemediationCommands)
    nodes: list[NodeConfig] = Field(default_factory=list)

    @field_validator("check_cron")
    @classmethod
    def validate_check_cron(cls, value: str) -> str:
        if not value.strip():
            return ""
        return validate_cron_expression(value)


class GlobalConfig(BaseModel):
    default_check_cron: str = "0 */6 * * *"
    timezone: str = "America/Argentina/Buenos_Aires"

    @field_validator("default_check_cron")
    @classmethod
    def validate_default_check_cron(cls, value: str) -> str:
        return validate_cron_expression(value)


class AppConfig(BaseModel):
    global_: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    remediation: RemediationGlobalConfig = Field(default_factory=RemediationGlobalConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    clusters: list[ClusterConfig] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class NodeCheckResult(BaseModel):
    cluster: str
    node: str
    ssh_up: bool
    k3s_up: bool = False
    node_ready: Optional[bool] = None
    node_status: str = "unknown"
    ssh_error: str = ""
    k3s_error: str = ""
    k8s_error: str = ""
    consecutive_failures: int = 0
    remediated: bool = False
    remediation_ok: bool = False
    remediation_result: str = ""
    remediation_duration_seconds: float = 0.0
