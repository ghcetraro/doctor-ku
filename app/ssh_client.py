from __future__ import annotations

import io
import logging
import re
import shlex
import socket
import time
from typing import Literal, Optional

import paramiko

logger = logging.getLogger(__name__)

_TOKEN_MASK = re.compile(r"(K3S_TOKEN=)(\S+)")


def _mask_secrets(text: str) -> str:
    return _TOKEN_MASK.sub(r"\1***", text)


class SSHClient:
    def __init__(
        self,
        host: str,
        user: str,
        private_key: str,
        port: int = 22,
        timeout: int = 15,
    ) -> None:
        self.host = host
        self.user = user
        self.private_key = private_key
        self.port = port
        self.timeout = timeout

    def check_connectivity(self) -> tuple[bool, str]:
        if not self.private_key.strip():
            return False, "sin clave ssh configurada"
        try:
            client = self._connect()
            client.close()
            logger.info("ssh ok %s@%s:%s", self.user, self.host, self.port)
            return True, ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("ssh check failed %s@%s: %s", self.user, self.host, exc)
            return False, str(exc)

    def run_commands(
        self,
        commands: list[str],
        *,
        delay_seconds: float = 0,
        timeout_seconds: float = 600,
    ) -> tuple[bool, str]:
        if not commands:
            return True, ""
        if not self.private_key.strip():
            return False, "sin clave ssh configurada"

        client: Optional[paramiko.SSHClient] = None
        try:
            client = self._connect()
            output_parts: list[str] = []
            pending = [cmd for cmd in commands if cmd.strip()]
            for index, command in enumerate(pending):
                logger.info("ssh %s@%s: %s", self.user, self.host, _mask_secrets(command))
                _, stdout, stderr = client.exec_command(command, timeout=int(timeout_seconds))
                exit_code = stdout.channel.recv_exit_status()
                out = stdout.read().decode("utf-8", errors="replace").strip()
                err = stderr.read().decode("utf-8", errors="replace").strip()
                if out:
                    logger.info("ssh stdout %s@%s: %s", self.user, self.host, out[:500])
                    output_parts.append(out)
                if err:
                    logger.info("ssh stderr %s@%s: %s", self.user, self.host, err[:500])
                    output_parts.append(err)
                if exit_code != 0:
                    combined = "\n".join(output_parts)
                    logger.error(
                        "ssh comando fallo %s@%s exit=%s cmd=%s",
                        self.user,
                        self.host,
                        exit_code,
                        _mask_secrets(command),
                    )
                    return False, f"comando fallo ({exit_code}): {command}\n{combined}"
                if delay_seconds > 0 and index < len(pending) - 1:
                    logger.info(
                        "ssh espera %s@%s: %.1fs antes del siguiente comando",
                        self.user,
                        self.host,
                        delay_seconds,
                    )
                    time.sleep(delay_seconds)
            logger.info("ssh comandos ok %s@%s (%s)", self.user, self.host, len(pending))
            return True, "\n".join(output_parts)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ssh command failed %s@%s", self.user, self.host)
            return False, str(exc)
        finally:
            if client is not None:
                client.close()

    def _load_private_key(self, key_data: str) -> paramiko.PKey:
        key_file = io.StringIO(key_data)
        for key_class in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
            key_file.seek(0)
            try:
                return key_class.from_private_key(key_file)
            except paramiko.SSHException:
                continue
        raise paramiko.SSHException("formato de clave ssh no soportado")

    def _connect(self) -> paramiko.SSHClient:
        pkey = self._load_private_key(self.private_key)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            pkey=pkey,
            timeout=self.timeout,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        return client

    def tcp_reachable(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=5):
                return True
        except OSError:
            return False

    def read_file(self, remote_path: str, *, use_sudo: bool = False) -> tuple[bool, str]:
        quoted = shlex.quote(remote_path)
        prefix = "sudo " if use_sudo else ""
        ok, output = self.run_commands([f"{prefix}cat {quoted}"])
        if not ok:
            return False, output
        return True, output

    def check_k3s_active(self, role: Literal["master", "worker"]) -> tuple[bool, str]:
        services = ("k3s", "k3s-agent") if role == "master" else ("k3s-agent", "k3s")
        for service in services:
            quoted = shlex.quote(service)
            ok, output = self.run_commands([f"systemctl is-active --quiet {quoted}"])
            if ok:
                logger.info("k3s activo %s@%s servicio=%s", self.user, self.host, service)
                return True, ""
        return False, f"ningun servicio k3s activo ({', '.join(services)})"

    def upload_content(self, content: str, remote_path: str, mode: int = 0o755) -> tuple[bool, str]:
        if not self.private_key.strip():
            return False, "sin clave ssh configurada"

        client: Optional[paramiko.SSHClient] = None
        try:
            client = self._connect()
            sftp = client.open_sftp()
            with sftp.file(remote_path, "w") as remote_file:
                remote_file.write(content)
            sftp.chmod(remote_path, mode)
            sftp.close()
            logger.info("ssh upload ok %s@%s:%s", self.user, self.host, remote_path)
            return True, remote_path
        except Exception as exc:  # noqa: BLE001
            logger.exception("ssh upload failed %s@%s:%s", self.user, self.host, remote_path)
            return False, str(exc)
        finally:
            if client is not None:
                client.close()
