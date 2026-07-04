from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram

if TYPE_CHECKING:
    from app.models import ClusterConfig

REMEDIATION_RESULTS = ("success", "failed", "dry_run", "unremediated")
_HISTOGRAM_SEEDED: set[tuple[str, str]] = set()

SSH_UP = Gauge(
    "doctorku_ssh_up",
    "1 si el nodo responde por SSH",
    ["cluster", "node"],
)

K3S_UP = Gauge(
    "doctorku_k3s_up",
    "1 si k3s esta activo en el nodo",
    ["cluster", "node"],
)

NODE_READY = Gauge(
    "doctorku_node_ready",
    "1 si el nodo esta Ready en Kubernetes",
    ["cluster", "node"],
)

REMEDIATION_TOTAL = Counter(
    "doctorku_remediation_total",
    "Total de remediaciones ejecutadas",
    ["cluster", "node", "result"],
)

LAST_CHECK_TIMESTAMP = Gauge(
    "doctorku_last_check_timestamp",
    "Timestamp Unix del ultimo chequeo del cluster",
    ["cluster"],
)

REMEDIATION_DURATION = Histogram(
    "doctorku_remediation_duration_seconds",
    "Duracion de cada remediacion en segundos",
    ["cluster", "node"],
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800),
)

FAILURE_STREAK = Gauge(
    "doctorku_failure_streak",
    "Cantidad de ciclos fallidos consecutivos por nodo",
    ["cluster", "node"],
)


def sync_remediation_metrics(clusters: list[ClusterConfig]) -> None:
    """Pre-registra contadores e histograma en 0 para que Prometheus/Grafana no muestren 'No data'."""
    for cluster in clusters:
        for node in cluster.nodes:
            for result in REMEDIATION_RESULTS:
                REMEDIATION_TOTAL.labels(
                    cluster=cluster.name,
                    node=node.name,
                    result=result,
                )
            key = (cluster.name, node.name)
            if key not in _HISTOGRAM_SEEDED:
                REMEDIATION_DURATION.labels(
                    cluster=cluster.name,
                    node=node.name,
                ).observe(0)
                _HISTOGRAM_SEEDED.add(key)
