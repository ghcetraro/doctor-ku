from __future__ import annotations

import logging
import re
import shlex
from typing import Optional
from urllib.parse import urlparse

import yaml

from app.config import resolve_node_ssh_key, settings
from app.k8s_client import K8sClient
from app.models import ClusterConfig, NodeConfig
from app.ssh_client import SSHClient

logger = logging.getLogger(__name__)

_K3S_VERSION_RE = re.compile(r"(v[\d.]+[+k3s\d]*)")

_ETCD_CERTS = (
    "--cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt "
    "--cert=/var/lib/rancher/k3s/server/tls/etcd/client.crt "
    "--key=/var/lib/rancher/k3s/server/tls/etcd/client.key"
)

_LOCAL_API_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def extract_bootstrap_server(kubeconfig_content: str) -> str:
    raw = yaml.safe_load(kubeconfig_content) or {}
    clusters = raw.get("clusters") or []
    if not clusters:
        raise ValueError("kubeconfig sin clusters")

    cluster_by_name = {item.get("name"): item for item in clusters if item.get("name")}
    current_context = raw.get("current-context", "")
    context = next(
        (item for item in raw.get("contexts") or [] if item.get("name") == current_context),
        None,
    )
    cluster_name = ""
    if context:
        cluster_name = (context.get("context") or {}).get("cluster", "")

    cluster_entry = cluster_by_name.get(cluster_name) or clusters[0]
    server = ((cluster_entry.get("cluster") or {}).get("server") or "").strip()
    if not server:
        raise ValueError("kubeconfig sin server URL")
    return server


def rewrite_kubeconfig_server(kubeconfig_content: str, server_host: str) -> str:
    raw = yaml.safe_load(kubeconfig_content) or {}
    changed = False
    for cluster_entry in raw.get("clusters") or []:
        cluster_data = cluster_entry.get("cluster") or {}
        server = (cluster_data.get("server") or "").strip()
        if not server:
            continue
        parsed = urlparse(server)
        hostname = (parsed.hostname or "").lower()
        if hostname not in _LOCAL_API_HOSTS:
            continue
        port = parsed.port or 6443
        scheme = parsed.scheme or "https"
        cluster_data["server"] = f"{scheme}://{server_host}:{port}"
        cluster_entry["cluster"] = cluster_data
        changed = True

    if not changed:
        return kubeconfig_content

    logger.info("kubeconfig server reescrito de localhost a host=%s", server_host)
    return yaml.safe_dump(raw, default_flow_style=False, sort_keys=False)


def build_ssh_client(cluster: ClusterConfig, node: NodeConfig) -> SSHClient:
    ssh_key = resolve_node_ssh_key(cluster.ssh_key, node, settings.ssh_keys_dir)
    return SSHClient(
        host=node.host,
        user=node.ssh_user or cluster.ssh_user,
        private_key=ssh_key,
        port=node.ssh_port or cluster.ssh_port,
    )


def iter_nodes(cluster: ClusterConfig) -> list[NodeConfig]:
    return list(cluster.nodes)


def find_accessible_node(
    cluster: ClusterConfig,
    *,
    require_k3s: bool = False,
    exclude: Optional[set[str]] = None,
) -> tuple[Optional[NodeConfig], Optional[SSHClient], str]:
    excluded = exclude or set()
    for node in iter_nodes(cluster):
        if node.name in excluded:
            continue
        ssh = build_ssh_client(cluster, node)
        ssh_ok, ssh_error = ssh.check_connectivity()
        if not ssh_ok:
            logger.info(
                "cluster=%s nodo=%s ssh no disponible: %s",
                cluster.name,
                node.name,
                ssh_error,
            )
            continue
        if require_k3s:
            k3s_ok, k3s_error = ssh.check_k3s_active(node.role)
            if not k3s_ok:
                logger.info(
                    "cluster=%s nodo=%s k3s no activo: %s",
                    cluster.name,
                    node.name,
                    k3s_error,
                )
                continue
        logger.info("cluster=%s nodo fuente=%s", cluster.name, node.name)
        return node, ssh, ""
    return None, None, "ningun nodo accesible por ssh"


def read_remote_file(
    ssh: SSHClient,
    remote_path: str,
    *,
    use_sudo: bool = False,
) -> tuple[bool, str]:
    if remote_path.startswith("/etc/rancher"):
        use_sudo = True
    return ssh.read_file(remote_path, use_sudo=use_sudo)


def obtain_kubeconfig(cluster: ClusterConfig) -> tuple[str, str, Optional[NodeConfig]]:
    for node in iter_nodes(cluster):
        ssh = build_ssh_client(cluster, node)
        ssh_ok, ssh_error = ssh.check_connectivity()
        if not ssh_ok:
            continue
        k3s_ok, k3s_error = ssh.check_k3s_active(node.role)
        if not k3s_ok:
            logger.info(
                "cluster=%s nodo=%s omitido para kubeconfig: %s",
                cluster.name,
                node.name,
                k3s_error,
            )
            continue
        ok, content = read_remote_file(ssh, cluster.k3s_kubeconfig_path)
        if not ok or not content.strip():
            logger.info(
                "cluster=%s nodo=%s sin kubeconfig en %s",
                cluster.name,
                node.name,
                cluster.k3s_kubeconfig_path,
            )
            continue
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            logger.warning(
                "cluster=%s nodo=%s kubeconfig invalido: %s",
                cluster.name,
                node.name,
                exc,
            )
            continue
        content = rewrite_kubeconfig_server(content, node.host)
        logger.info(
            "cluster=%s kubeconfig obtenido desde nodo=%s path=%s",
            cluster.name,
            node.name,
            cluster.k3s_kubeconfig_path,
        )
        return content, "", node

    return "", "no se pudo obtener kubeconfig desde ningun nodo", None


def obtain_k3s_token(
    cluster: ClusterConfig,
    *,
    exclude: Optional[set[str]] = None,
) -> tuple[str, str, Optional[NodeConfig]]:
    excluded = exclude or set()
    for node in iter_nodes(cluster):
        if node.name in excluded:
            continue
        ssh = build_ssh_client(cluster, node)
        ssh_ok, ssh_error = ssh.check_connectivity()
        if not ssh_ok:
            continue
        k3s_ok, k3s_error = ssh.check_k3s_active(node.role)
        if not k3s_ok:
            continue
        ok, token = read_remote_file(ssh, cluster.k3s_token_path, use_sudo=True)
        token = token.strip()
        if not ok or not token:
            logger.info(
                "cluster=%s nodo=%s sin token en %s",
                cluster.name,
                node.name,
                cluster.k3s_token_path,
            )
            continue
        logger.info(
            "cluster=%s token obtenido desde nodo=%s path=%s",
            cluster.name,
            node.name,
            cluster.k3s_token_path,
        )
        return token, "", node

    return "", "no se pudo obtener token desde ningun nodo sano", None


def build_k8s_client(kubeconfig_content: str) -> K8sClient:
    return K8sClient.from_content(kubeconfig_content)


def obtain_k3s_version(
    cluster: ClusterConfig,
    *,
    exclude: Optional[set[str]] = None,
) -> tuple[str, str, Optional[NodeConfig]]:
    excluded = exclude or set()
    for node in iter_nodes(cluster):
        if node.name in excluded:
            continue
        ssh = build_ssh_client(cluster, node)
        ssh_ok, _ = ssh.check_connectivity()
        if not ssh_ok:
            continue
        k3s_ok, _ = ssh.check_k3s_active(node.role)
        if not k3s_ok:
            continue
        ok, output = ssh.run_commands(["k3s --version"])
        if not ok:
            continue
        match = _K3S_VERSION_RE.search(output)
        if not match:
            logger.warning(
                "cluster=%s nodo=%s version k3s no parseable: %s",
                cluster.name,
                node.name,
                output[:200],
            )
            continue
        version = match.group(1)
        logger.info(
            "cluster=%s version k3s=%s desde nodo=%s",
            cluster.name,
            version,
            node.name,
        )
        return version, "", node
    return "", "no se pudo obtener version k3s desde ningun nodo sano", None


def remove_etcd_ghost_member(
    cluster: ClusterConfig,
    node: NodeConfig,
    *,
    exclude: Optional[set[str]] = None,
) -> tuple[bool, str]:
    """Elimina miembro etcd fantasma de un master ausente del cluster (best-effort)."""
    if node.role != "master":
        return True, "omitido: no es master"

    excluded = (exclude or set()) | {node.name}
    source_node, ssh, error = find_accessible_node(
        cluster,
        require_k3s=True,
        exclude=excluded,
    )
    if not source_node or not ssh:
        return False, f"sin master sano para limpiar etcd: {error}"

    host_pattern = shlex.quote(node.host)
    name_pattern = shlex.quote(node.name)
    script = f"""
set -e
export ETCDCTL_API=3
ETCDCTL="etcdctl --endpoints=https://127.0.0.1:2379 {_ETCD_CERTS}"
if ! command -v etcdctl >/dev/null 2>&1; then
  echo "etcdctl no instalado, omitiendo limpieza etcd"
  exit 0
fi
MEMBER_ID=$($ETCDCTL member list 2>/dev/null | grep -F {name_pattern} | head -1 | cut -d',' -f1 | tr -d ' ')
if [ -z "$MEMBER_ID" ]; then
  MEMBER_ID=$($ETCDCTL member list 2>/dev/null | grep -F {host_pattern} | head -1 | cut -d',' -f1 | tr -d ' ')
fi
if [ -z "$MEMBER_ID" ]; then
  echo "sin miembro etcd fantasma para {node.name}"
  exit 0
fi
echo "eliminando miembro etcd $MEMBER_ID ({node.name})"
$ETCDCTL member remove "$MEMBER_ID"
echo "miembro etcd $MEMBER_ID eliminado"
""".strip()
    ok, output = ssh.run_commands([f"sudo env ETCDCTL_API=3 sh -c {shlex.quote(script)}"])
    if not ok:
        logger.warning(
            "cluster=%s limpieza etcd fallo desde nodo=%s nodo_objetivo=%s: %s",
            cluster.name,
            source_node.name,
            node.name,
            output[:500],
        )
        return False, output
    logger.info(
        "cluster=%s limpieza etcd ok desde nodo=%s nodo_objetivo=%s: %s",
        cluster.name,
        source_node.name,
        node.name,
        output[:300],
    )
    return True, output
