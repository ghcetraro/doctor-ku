from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

METRICS_FILE = Path(os.environ.get("METRICS_FILE", "/data/metrics.prom"))
METRICS_PORT = int(os.environ.get("METRICS_PORT", "8080"))
START_TIME = time.time()


def read_job_metrics() -> str:
    if METRICS_FILE.exists():
        return METRICS_FILE.read_text(encoding="utf-8").strip()
    return ""


def write_job_metrics(body: str) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = METRICS_FILE.with_suffix(".prom.tmp")
    tmp.write_text(body.strip() + "\n", encoding="utf-8")
    tmp.replace(METRICS_FILE)


def build_metrics() -> bytes:
    lines = [
        "# HELP doctorku_exporter_up El exporter de metricas esta activo.",
        "# TYPE doctorku_exporter_up gauge",
        "doctorku_exporter_up 1",
        "# HELP doctorku_exporter_uptime_seconds Tiempo activo del exporter en segundos.",
        "# TYPE doctorku_exporter_uptime_seconds gauge",
        f"doctorku_exporter_uptime_seconds {time.time() - START_TIME:.3f}",
        "# HELP doctorku_metrics_file_present 1 si hay metricas de la ultima ejecucion del CronJob.",
        "# TYPE doctorku_metrics_file_present gauge",
        f"doctorku_metrics_file_present {1 if read_job_metrics() else 0}",
    ]

    job_metrics = read_job_metrics()
    if job_metrics:
        lines.append(job_metrics)

    return ("\n".join(lines) + "\n").encode("utf-8")


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/metrics", "/metrics/"):
            body = build_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path in ("/health", "/healthz", "/"):
            payload = {
                "status": "ok",
                "metrics_file": str(METRICS_FILE),
                "metrics_file_exists": METRICS_FILE.exists(),
                "uptime_seconds": round(time.time() - START_TIME, 3),
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/internal/update":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8").strip()
        if not body:
            self.send_response(400)
            self.end_headers()
            return

        write_job_metrics(body)
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    server = HTTPServer(("", METRICS_PORT), MetricsHandler)
    print(f"metrics-exporter escuchando en :{METRICS_PORT}, archivo={METRICS_FILE}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
