from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from app.config import resolve_install_script_path, settings
from app.k3s_utils import (
    build_k8s_client,
    build_ssh_client,
    extract_bootstrap_server,
    obtain_k3s_token,
    obtain_k3s_version,
    obtain_kubeconfig,
    remove_etcd_ghost_member,
)
from app.k8s_client import K8sClient
from app.metrics import (
    FAILURE_STREAK,
    K3S_UP,
    LAST_CHECK_TIMESTAMP,
    NODE_READY,
    REMEDIATION_DURATION,
    REMEDIATION_TOTAL,
    SSH_UP,
)
from app.models import ClusterConfig, NodeCheckResult, NodeConfig
from app.notifier import Notifier
from app.ssh_client import SSHClient

logger = logging.getLogger(__name__)

_K3S_FORCE_CLEANUP = [
    "sudo systemctl stop k3s k3s-agent 2>/dev/null || true",
    "sudo systemctl disable k3s k3s-agent 2>/dev/null || true",
    "sudo rm -f /etc/systemd/system/k3s.service /etc/systemd/system/k3s.service.env",
    "sudo rm -f /etc/systemd/system/k3s-agent.service /etc/systemd/system/k3s-agent.service.env",
    "sudo systemctl daemon-reload 2>/dev/null || true",
    "sudo rm -rf /var/lib/rancher/k3s",
]


class Remediator:
    def __init__(
        self,
        notifier: Notifier,
        *,
        failure_counts: dict[str, int] | None = None,
    ) -> None:
        self.notifier = notifier
        self._failure_counts: dict[str, int] = dict(failure_counts or {})

    def export_failure_counts(self) -> dict[str, int]:
        return dict(self._failure_counts)

    def _key(self, cluster: str, node: str) -> str:
        return f"{cluster}/{node}"

    def get_failure_count(self, cluster: str, node: str) -> int:
        return self._failure_counts.get(self._key(cluster, node), 0)

    def reset_failure_count(self, cluster: str, node: str) -> None:
        key = self._key(cluster, node)
        self._failure_counts[key] = 0
        FAILURE_STREAK.labels(cluster=cluster, node=node).set(0)

    def increment_failure_count(self, cluster: str, node: str) -> int:
        key = self._key(cluster, node)
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        count = self._failure_counts[key]
        FAILURE_STREAK.labels(cluster=cluster, node=node).set(count)
        return count

    def _render(
        self,
        template: str,
        *,
        k3s_token: str,
        bootstrap_server: str,
        install_script_path: str,
        node: NodeConfig,
        k3s_version: str = "",
    ) -> str:
        replacements = {
            "{{K3S_TOKEN}}": k3s_token,
            "{{K3S_VERSION}}": k3s_version,
            "{{BOOTSTRAP_SERVER}}": bootstrap_server,
            "{{K3S_INSTALL_SCRIPT}}": install_script_path,
            "{{NODE_NAME}}": node.name,
            "{{NODE_HOST}}": node.host,
        }
        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        return rendered

    def _load_install_script(self, cluster: ClusterConfig) -> tuple[bool, str]:
        script_path = resolve_install_script_path(cluster.commands.install_script)
        if not script_path.is_file():
            return False, f"script de instalacion no encontrado: {script_path}"
        return True, script_path.read_text(encoding="utf-8")

    def remediate(
        self,
        cluster: ClusterConfig,
        node: NodeConfig,
        k8s: K8sClient,
        kubeconfig_content: str,
    ) -> tuple[bool, str, float]:
        remediation = cluster.remediation
        if not remediation.enabled:
            logger.info(
                "remediacion omitida cluster=%s nodo=%s (deshabilitada)",
                cluster.name,
                node.name,
            )
            return False, "remediacion deshabilitada", 0.0

        logger.info(
            "inicio remediacion cluster=%s nodo=%s host=%s role=%s dry_run=%s",
            cluster.name,
            node.name,
            node.host,
            node.role,
            remediation.dry_run,
        )
        started = time.monotonic()
        steps: list[str] = []
        node_missing = False

        ssh = build_ssh_client(cluster, node)
        ssh_ok, ssh_error = ssh.check_connectivity()
        if not ssh_ok:
            duration = time.monotonic() - started
            reason = f"sin acceso ssh al nodo: {ssh_error}"
            logger.error(
                "remediacion imposible cluster=%s nodo=%s: %s",
                cluster.name,
                node.name,
                reason,
            )
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="unremediated").inc()
            return False, reason, duration

        if remediation.dry_run:
            duration = time.monotonic() - started
            msg = "dry-run: remediacion simulada"
            logger.info(
                "remediacion dry-run cluster=%s nodo=%s ssh=%s k8s=%s",
                cluster.name,
                node.name,
                ssh_ok,
                k8s.available,
            )
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="dry_run").inc()
            REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
            return True, msg, duration

        cmd_delay = float(cluster.commands.command_delay_seconds)
        pre_cmds = [
            self._render(
                cmd,
                k3s_token="",
                bootstrap_server="",
                install_script_path=cluster.commands.remote_install_script,
                node=node,
            )
            for cmd in cluster.commands.pre_remediation
        ]
        if pre_cmds:
            ok, output = ssh.run_commands(pre_cmds, delay_seconds=cmd_delay)
            steps.append(f"pre: {output}")
            if not ok:
                duration = time.monotonic() - started
                REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
                REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
                return False, f"pre_remediation fallo: {output}", duration

        if k8s.available:
            _, node_status, _ = k8s.get_node_status(node.name)
            node_missing = node_status == "missing"
            if node_missing:
                steps.append("delete node: omitido (nodo ausente del cluster)")
                logger.info(
                    "cluster=%s nodo=%s ausente del cluster, omitiendo delete",
                    cluster.name,
                    node.name,
                )
            else:
                ok, output = k8s.delete_node(node.name, dry_run=False)
                steps.append(f"delete node: {output}")
                if not ok:
                    duration = time.monotonic() - started
                    REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
                    REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
                    return False, f"delete node fallo: {output}", duration

        if node.role == "master" and node_missing:
            ok, output = remove_etcd_ghost_member(
                cluster,
                node,
                exclude={node.name},
            )
            steps.append(f"etcd cleanup: {output}")
            if not ok:
                logger.warning(
                    "cluster=%s nodo=%s limpieza etcd fallo, continuando remediacion: %s",
                    cluster.name,
                    node.name,
                    output[:300],
                )

        uninstall_cmds = [
            self._render(
                cmd,
                k3s_token="",
                bootstrap_server="",
                install_script_path=cluster.commands.remote_install_script,
                node=node,
            )
            for cmd in cluster.commands.uninstall
        ]
        ok, output = ssh.run_commands(uninstall_cmds, delay_seconds=cmd_delay)
        steps.append(f"uninstall: {output}")
        if not ok:
            duration = time.monotonic() - started
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
            REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
            return False, f"uninstall fallo: {output}", duration

        ok, output = ssh.run_commands(_K3S_FORCE_CLEANUP, delay_seconds=cmd_delay)
        steps.append(f"cleanup: {output}")
        if not ok:
            duration = time.monotonic() - started
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
            REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
            return False, f"cleanup k3s fallo: {output}", duration

        token, token_error, _ = obtain_k3s_token(cluster, exclude={node.name})
        if not token:
            duration = time.monotonic() - started
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
            REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
            return False, f"token no obtenido: {token_error}", duration
        steps.append("token: obtenido desde nodo sano")

        try:
            bootstrap_server = extract_bootstrap_server(kubeconfig_content)
        except ValueError as exc:
            duration = time.monotonic() - started
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
            REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
            return False, f"bootstrap_server no derivado: {exc}", duration

        install_template = (
            cluster.commands.master_install
            if node.role == "master"
            else cluster.commands.worker_install
        )
        uses_local_script = "{{K3S_INSTALL_SCRIPT}}" in install_template
        remote_script = cluster.commands.remote_install_script
        if uses_local_script:
            ok, script_content = self._load_install_script(cluster)
            if not ok:
                duration = time.monotonic() - started
                REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
                REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
                return False, script_content, duration

            ok, output = ssh.upload_content(script_content, remote_script)
            steps.append(f"upload script: {output}")
            if not ok:
                duration = time.monotonic() - started
                REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
                REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
                return False, f"upload script fallo: {output}", duration

        k3s_version, version_error, _ = obtain_k3s_version(cluster, exclude={node.name})
        if not k3s_version:
            logger.warning(
                "cluster=%s nodo=%s sin version k3s del cluster: %s",
                cluster.name,
                node.name,
                version_error,
            )
        else:
            steps.append(f"k3s version: {k3s_version}")
        install_cmd = self._render(
            install_template,
            k3s_token=token,
            bootstrap_server=bootstrap_server,
            install_script_path=remote_script,
            node=node,
            k3s_version=k3s_version,
        )
        ok, output = ssh.run_commands(
            [install_cmd],
            delay_seconds=cmd_delay,
            timeout_seconds=900,
        )
        steps.append(f"install: {output or '(sin salida)'}")
        if not ok:
            journal_ok, journal = ssh.run_commands(
                ["sudo journalctl -u k3s -u k3s-agent -n 40 --no-pager 2>/dev/null || true"],
                timeout_seconds=30,
            )
            if journal_ok and journal.strip():
                steps.append(f"journal: {journal[-1500:]}")
            duration = time.monotonic() - started
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
            REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
            return False, f"install fallo: {output}", duration

        k3s_ok, k3s_error = self._wait_for_k3s_active(ssh, node.role, timeout_seconds=180)
        steps.append(f"verify k3s: {'activo' if k3s_ok else k3s_error}")
        if not k3s_ok:
            _, journal = ssh.run_commands(
                ["sudo journalctl -u k3s -u k3s-agent -n 40 --no-pager 2>/dev/null || true"],
                timeout_seconds=30,
            )
            if journal.strip():
                steps.append(f"journal: {journal[-1500:]}")
            duration = time.monotonic() - started
            REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
            REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
            return False, f"k3s inactivo tras install: {k3s_error}; {'; '.join(steps)}", duration

        if k8s.available:
            node_ok, node_msg = self._wait_for_node_in_cluster(k8s, node.name, timeout_seconds=180)
            steps.append(f"verify k8s: {node_msg}")
            if not node_ok:
                duration = time.monotonic() - started
                REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
                REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
                return False, f"nodo no aparecio en k8s: {node_msg}; {'; '.join(steps)}", duration

        post_cmds = [
            self._render(
                cmd,
                k3s_token=token,
                bootstrap_server=bootstrap_server,
                install_script_path=remote_script,
                node=node,
            )
            for cmd in cluster.commands.post_remediation
        ]
        if post_cmds:
            ok, output = ssh.run_commands(post_cmds, delay_seconds=cmd_delay)
            steps.append(f"post: {output}")
            if not ok:
                duration = time.monotonic() - started
                REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="failed").inc()
                REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
                return False, f"post_remediation fallo: {output}", duration

        duration = time.monotonic() - started
        REMEDIATION_TOTAL.labels(cluster=cluster.name, node=node.name, result="success").inc()
        REMEDIATION_DURATION.labels(cluster=cluster.name, node=node.name).observe(duration)
        logger.info(
            "remediacion ok cluster=%s nodo=%s duracion=%.1fs pasos=%s",
            cluster.name,
            node.name,
            duration,
            "; ".join(steps),
        )
        return True, "; ".join(steps), duration

    def _wait_for_k3s_active(
        self,
        ssh: SSHClient,
        role: str,
        *,
        timeout_seconds: float = 180,
        poll_seconds: float = 5,
    ) -> tuple[bool, str]:
        deadline = time.monotonic() + timeout_seconds
        last_error = ""
        while time.monotonic() < deadline:
            k3s_up, k3s_error = ssh.check_k3s_active(role)  # type: ignore[arg-type]
            if k3s_up:
                return True, ""
            last_error = k3s_error
            time.sleep(poll_seconds)
        return False, last_error or f"timeout {timeout_seconds:.0f}s esperando k3s"

    def _wait_for_node_in_cluster(
        self,
        k8s: K8sClient,
        node_name: str,
        *,
        timeout_seconds: float = 180,
        poll_seconds: float = 5,
    ) -> tuple[bool, str]:
        deadline = time.monotonic() + timeout_seconds
        last_status = "missing"
        while time.monotonic() < deadline:
            node_ready, node_status, k8s_error = k8s.get_node_status(node_name)
            last_status = node_status
            if node_ready is True:
                return True, "Ready"
            if k8s_error and node_status in ("missing", "error", "unknown"):
                last_status = k8s_error
            time.sleep(poll_seconds)
        return False, last_status


class ClusterChecker:
    def __init__(self, remediator: Remediator, notifier: Notifier) -> None:
        self.remediator = remediator
        self.notifier = notifier

    def check_cluster(
        self,
        cluster: ClusterConfig,
        notify_async: Callable,
        *,
        remediation_enabled: bool = True,
    ) -> list[NodeCheckResult]:
        results: list[NodeCheckResult] = []
        remediation_active = remediation_enabled and cluster.remediation.enabled
        logger.info(
            "inicio chequeo cluster=%s nodos=%s remediation=%s (global=%s cluster=%s) threshold=%s max_nodes=%s",
            cluster.name,
            len(cluster.nodes),
            remediation_active,
            remediation_enabled,
            cluster.remediation.enabled,
            cluster.remediation.failure_threshold,
            cluster.remediation.max_nodes_per_cycle,
        )

        ssh_status: dict[str, tuple[bool, str, SSHClient]] = {}
        for node in cluster.nodes:
            ssh = build_ssh_client(cluster, node)
            ssh_up, ssh_error = ssh.check_connectivity()
            SSH_UP.labels(cluster=cluster.name, node=node.name).set(1 if ssh_up else 0)
            ssh_status[node.name] = (ssh_up, ssh_error, ssh)

        k3s_status: dict[str, tuple[bool, str]] = {}
        for node in cluster.nodes:
            ssh_up, ssh_error, ssh = ssh_status[node.name]
            if not ssh_up:
                k3s_status[node.name] = (False, "ssh no disponible")
                K3S_UP.labels(cluster=cluster.name, node=node.name).set(0)
                continue
            k3s_up, k3s_error = ssh.check_k3s_active(node.role)
            k3s_status[node.name] = (k3s_up, k3s_error)
            K3S_UP.labels(cluster=cluster.name, node=node.name).set(1 if k3s_up else 0)

        kubeconfig_content, kubeconfig_error, _ = obtain_kubeconfig(cluster)
        k8s: Optional[K8sClient] = None
        if kubeconfig_content:
            k8s = build_k8s_client(kubeconfig_content)
        else:
            logger.warning(
                "cluster=%s sin kubeconfig remoto: %s",
                cluster.name,
                kubeconfig_error,
            )

        candidates: list[tuple[NodeConfig, NodeCheckResult]] = []
        for node in cluster.nodes:
            result = self._build_node_result(
                cluster,
                node,
                ssh_status[node.name],
                k3s_status[node.name],
                k8s,
            )
            results.append(result)
            if self._needs_remediation(result, cluster, remediation_enabled):
                candidates.append((node, result))

        if candidates and remediation_active and k8s and k8s.available and kubeconfig_content:
            max_nodes = max(cluster.remediation.max_nodes_per_cycle, 0)
            logger.warning(
                "cluster=%s nodos a remediar=%s (max %s por ciclo)",
                cluster.name,
                [
                    f"{node.name}({result.node_status})"
                    for node, result in candidates
                ],
                max_nodes,
            )
            for node, result in candidates[:max_nodes]:
                ok, message, duration = self.remediator.remediate(
                    cluster,
                    node,
                    k8s,
                    kubeconfig_content,
                )
                result.remediated = True
                result.remediation_ok = ok
                result.remediation_result = message
                result.remediation_duration_seconds = duration

                if ok:
                    self.remediator.reset_failure_count(cluster.name, node.name)
                    logger.info(
                        "remediacion exitosa cluster=%s nodo=%s duracion=%.1fs",
                        cluster.name,
                        node.name,
                        duration,
                    )
                    notify_async(
                        self.notifier.send_remediation_result(
                            cluster.name,
                            node.name,
                            "success",
                            duration,
                            {"message": message},
                        )
                    )
                else:
                    logger.error(
                        "remediacion fallida cluster=%s nodo=%s duracion=%.1fs motivo=%s",
                        cluster.name,
                        node.name,
                        duration,
                        message,
                    )
                    if message.startswith("sin acceso ssh"):
                        notify_async(
                            self.notifier.send_unremediated(
                                cluster.name,
                                node.name,
                                message,
                                {
                                    "ssh_up": result.ssh_up,
                                    "k3s_up": result.k3s_up,
                                    "node_ready": result.node_ready,
                                    "node_status": result.node_status,
                                },
                            )
                        )
                    else:
                        notify_async(
                            self.notifier.send_remediation_result(
                                cluster.name,
                                node.name,
                                "failed",
                                duration,
                                {"message": message},
                            )
                        )
        elif candidates and (not k8s or not k8s.available):
            logger.error(
                "cluster=%s nodos con fallo pero sin acceso k8s para remediar: %s candidatos=%s",
                cluster.name,
                k8s.error if k8s else kubeconfig_error,
                [f"{node.name}({result.node_status})" for node, result in candidates],
            )

        LAST_CHECK_TIMESTAMP.labels(cluster=cluster.name).set(time.time())
        for result in results:
            logger.info(
                "resultado cluster=%s nodo=%s ssh=%s k3s=%s k8s_ready=%s status=%s fallos=%s remediated=%s",
                result.cluster,
                result.node,
                result.ssh_up,
                result.k3s_up,
                result.node_ready,
                result.node_status,
                result.consecutive_failures,
                result.remediated,
            )
        logger.info(
            "fin chequeo cluster=%s nodos=%s remediations=%s",
            cluster.name,
            len(cluster.nodes),
            sum(1 for item in results if item.remediated),
        )
        return results

    def _build_node_result(
        self,
        cluster: ClusterConfig,
        node: NodeConfig,
        ssh_state: tuple[bool, str, SSHClient],
        k3s_state: tuple[bool, str],
        k8s: Optional[K8sClient],
    ) -> NodeCheckResult:
        ssh_up, ssh_error, _ = ssh_state
        k3s_up, k3s_error = k3s_state

        node_ready: Optional[bool] = None
        node_status = "unknown"
        k8s_error = ""
        if k8s and k8s.available:
            node_ready, node_status, k8s_error = k8s.get_node_status(node.name)
            if node_ready is not None:
                NODE_READY.labels(cluster=cluster.name, node=node.name).set(1 if node_ready else 0)
            else:
                NODE_READY.labels(cluster=cluster.name, node=node.name).set(-1)
        else:
            NODE_READY.labels(cluster=cluster.name, node=node.name).set(-1)
            k8s_error = k8s.error if k8s else "cliente k8s no disponible"

        if node_ready is True:
            self.remediator.reset_failure_count(cluster.name, node.name)
            failures = 0
        elif node_ready is False or (node_status == "missing" and ssh_up):
            failures = self.remediator.increment_failure_count(cluster.name, node.name)
        else:
            failures = self.remediator.get_failure_count(cluster.name, node.name)

        return NodeCheckResult(
            cluster=cluster.name,
            node=node.name,
            ssh_up=ssh_up,
            k3s_up=k3s_up,
            node_ready=node_ready,
            node_status=node_status,
            ssh_error=ssh_error,
            k3s_error=k3s_error,
            k8s_error=k8s_error,
            consecutive_failures=failures,
        )

    def _needs_remediation(
        self,
        result: NodeCheckResult,
        cluster: ClusterConfig,
        remediation_enabled: bool = True,
    ) -> bool:
        if not remediation_enabled or not cluster.remediation.enabled:
            return False
        if not result.ssh_up:
            return False
        threshold = cluster.remediation.failure_threshold
        if result.node_status == "missing":
            return result.consecutive_failures >= threshold
        if result.node_ready is not False:
            return False
        return result.consecutive_failures >= threshold
