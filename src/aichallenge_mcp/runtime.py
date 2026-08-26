"""Self-healing local runtime for the private ChatGPT plugin.

The MCP server remains private. This module supervises the two local processes
that make the private connection usable: the server and OpenAI's
``tunnel-client``. It never writes or prints the tunnel control-plane key.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import getpass
import json
import os
from pathlib import Path
import plistlib
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen


LAUNCH_AGENT_SERVER_LABEL = "com.aichallenge-mcp.server"
LAUNCH_AGENT_TUNNEL_LABEL = "com.aichallenge-mcp.tunnel"
KEYCHAIN_SERVICE = "aichallenge-mcp.tunnel-control-plane"
DEFAULT_SERVER_URL = "http://127.0.0.1:8000"


class RuntimeConfigurationError(RuntimeError):
    """Raised for a safe-to-display local runtime configuration problem."""


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Local paths used by the private-plugin supervisor."""

    project_dir: Path
    python: Path
    tunnel_client: Path
    tunnel_config: Path
    runtime_dir: Path
    log_dir: Path
    launch_agents_dir: Path
    server_url: str = DEFAULT_SERVER_URL
    keychain_service: str = KEYCHAIN_SERVICE

    @classmethod
    def from_environment(
        cls,
        *,
        project_dir: str | None = None,
        tunnel_config: str | None = None,
        tunnel_client: str | None = None,
    ) -> RuntimePaths:
        home = Path.home()
        resolved_project_dir = Path(
            project_dir or os.getenv("AICHALLENGE_MCP_PROJECT_DIR") or Path.cwd()
        ).expanduser().resolve()
        configured_python = os.getenv("AICHALLENGE_MCP_PYTHON")
        python = Path(configured_python).expanduser() if configured_python else resolved_project_dir / ".venv/bin/python"
        configured_tunnel_client = tunnel_client or os.getenv("AICHALLENGE_TUNNEL_CLIENT")
        resolved_tunnel_client = Path(configured_tunnel_client).expanduser() if configured_tunnel_client else _find_tunnel_client()
        return cls(
            project_dir=resolved_project_dir,
            python=python,
            tunnel_client=resolved_tunnel_client,
            tunnel_config=Path(
                tunnel_config
                or os.getenv("AICHALLENGE_TUNNEL_CONFIG")
                or home / ".config/tunnel-client/aichallenge-mcp.yaml"
            ).expanduser(),
            runtime_dir=home / "Library/Application Support/AIChallengeMCP",
            log_dir=home / "Library/Logs/AIChallengeMCP",
            launch_agents_dir=home / "Library/LaunchAgents",
            server_url=os.getenv("AICHALLENGE_MCP_SERVER_URL", DEFAULT_SERVER_URL).rstrip("/"),
            keychain_service=os.getenv("AICHALLENGE_MCP_KEYCHAIN_SERVICE", KEYCHAIN_SERVICE),
        )


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def _find_tunnel_client() -> Path:
    found = shutil.which("tunnel-client")
    if found:
        return Path(found)
    return Path.home() / ".local/bin/tunnel-client"


def _server_port_is_bound(server_url: str) -> bool:
    parsed = urlparse(server_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=0.5):
            return True
    except OSError:
        return False


def _safe_url_json(url: str, *, timeout: float = 2) -> dict[str, Any] | None:
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - loopback URL is operator configured
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def tunnel_health_url(config_path: Path) -> str | None:
    """Read only the non-secret loopback health address from the YAML profile."""
    configured = os.getenv("AICHALLENGE_TUNNEL_HEALTH_URL")
    if configured:
        return configured.rstrip("/")
    if not config_path.is_file():
        return None

    in_health = False
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw_line == "health:":
            in_health = True
            continue
        if raw_line and not raw_line[0].isspace():
            in_health = False
        if in_health and stripped.startswith("listen_addr:"):
            address = stripped.partition(":")[2].strip().split("#", 1)[0].strip().strip('"\'')
            if address.startswith("127.0.0.1:") or address.startswith("localhost:"):
                return f"http://{address}"
            return None
    return None


def read_keychain_secret(service: str) -> str | None:
    """Read an operator-provisioned Keychain item without exposing its value."""
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-a", getpass.getuser(), "-s", service, "-w"],
        check=False,
        capture_output=True,
        text=True,
    )
    secret = result.stdout.strip() if result.returncode == 0 else ""
    return secret or None


def launch_agent_plist(*, label: str, program_arguments: list[str], paths: RuntimePaths) -> dict[str, Any]:
    """Return a restart-on-crash user LaunchAgent without embedding credentials."""
    is_tunnel = label == LAUNCH_AGENT_TUNNEL_LABEL
    name = "tunnel" if is_tunnel else "server"
    return {
        "Label": label,
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(paths.project_dir),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "StandardOutPath": str(paths.log_dir / f"{name}.log"),
        "StandardErrorPath": str(paths.log_dir / f"{name}.error.log"),
    }


class RuntimeController:
    """Diagnose, launch, and install the local private-plugin runtime."""

    def __init__(
        self,
        paths: RuntimePaths,
        *,
        keychain_reader: Callable[[str], str | None] = read_keychain_secret,
    ) -> None:
        self.paths = paths
        self._keychain_reader = keychain_reader

    def checks(self, *, verify_tunnel_config: bool = False) -> list[Check]:
        checks = [
            Check("project", self.paths.project_dir.is_dir(), "project directory is available"),
            Check("python", self.paths.python.is_file(), "managed virtual-environment Python is available"),
            Check("tunnel-client", self.paths.tunnel_client.is_file(), "tunnel-client executable is available"),
            self._config_check(),
            self._server_check(),
            self._tunnel_check(),
            self._launchd_check(LAUNCH_AGENT_SERVER_LABEL),
            self._launchd_check(LAUNCH_AGENT_TUNNEL_LABEL),
        ]
        if verify_tunnel_config:
            checks.append(self._tunnel_config_check())
        return checks

    def doctor(self) -> int:
        checks = self.checks(verify_tunnel_config=True)
        for check in checks:
            mark = "PASS" if check.ok else "FAIL"
            print(f"{mark:4} {check.name}: {check.detail}")
        return 0 if all(check.ok for check in checks if check.name not in {"launchd-server", "launchd-tunnel"}) else 1

    def status(self) -> int:
        checks = self.checks()
        print(json.dumps({"checks": [check.to_dict() for check in checks]}, ensure_ascii=False, indent=2))
        return 0 if all(check.ok for check in checks if check.name in {"server", "tunnel"}) else 1

    def start_server(self) -> int:
        if self._server_check().ok:
            print("MCP server is already ready.")
            return 0
        self._require_local_server_prerequisites()
        if _server_port_is_bound(self.paths.server_url):
            raise RuntimeConfigurationError(
                "the MCP port is occupied by a process that does not expose the required /readyz endpoint"
            )
        self._ensure_runtime_directories()
        self._spawn(
            [str(self.paths.python), "-m", "aichallenge_mcp.server"],
            self.paths.log_dir / "server.log",
            self.paths.log_dir / "server.error.log",
        )
        if self._wait_for(lambda: self._server_check().ok):
            print("MCP server is ready.")
            return 0
        print("MCP server did not become ready; inspect the local server error log.")
        return 1

    def start_tunnel(self) -> int:
        if self._tunnel_check().ok:
            print("Secure Tunnel client is already ready.")
            return 0
        self._require_tunnel_prerequisites()
        self._ensure_runtime_directories()
        self._spawn(
            [str(self.paths.python), "-m", "aichallenge_mcp.runtime", "run-tunnel", "--config", str(self.paths.tunnel_config)],
            self.paths.log_dir / "tunnel.log",
            self.paths.log_dir / "tunnel.error.log",
        )
        if self._wait_for(lambda: self._tunnel_check().ok, attempts=20):
            print("Secure Tunnel client is ready.")
            return 0
        print("Secure Tunnel client did not become ready; inspect the local tunnel error log.")
        return 1

    def up(self) -> int:
        server_status = self.start_server()
        if server_status:
            return server_status
        return self.start_tunnel()

    def run_server(self) -> int:
        from .server import main as server_main

        server_main()
        return 0

    def run_tunnel(self) -> int:
        self._require_tunnel_prerequisites()
        secret = self._keychain_reader(self.paths.keychain_service)
        if secret is None:
            raise RuntimeConfigurationError(
                "macOS Keychain does not contain the required Secure Tunnel runtime credential"
            )
        environment = os.environ.copy()
        environment["CONTROL_PLANE_API_KEY"] = secret
        completed = subprocess.run(
            [str(self.paths.tunnel_client), "run", "--config", str(self.paths.tunnel_config)],
            check=False,
            env=environment,
        )
        return completed.returncode

    def install_launchd(self) -> int:
        self._require_local_server_prerequisites()
        self._require_tunnel_prerequisites()
        if not self._server_check().ok and _server_port_is_bound(self.paths.server_url):
            raise RuntimeConfigurationError(
                "the MCP port is occupied by a process that does not expose the required /readyz endpoint"
            )
        if self._keychain_reader(self.paths.keychain_service) is None:
            raise RuntimeConfigurationError(
                "Refusing to install LaunchAgents: the Secure Tunnel runtime credential is not in macOS Keychain"
            )
        config_check = self._tunnel_config_check()
        if not config_check.ok:
            raise RuntimeConfigurationError("Refusing to install LaunchAgents: tunnel configuration is not ready")

        self._ensure_runtime_directories()
        self.paths.launch_agents_dir.mkdir(parents=True, exist_ok=True)
        server_path = self.paths.launch_agents_dir / f"{LAUNCH_AGENT_SERVER_LABEL}.plist"
        tunnel_path = self.paths.launch_agents_dir / f"{LAUNCH_AGENT_TUNNEL_LABEL}.plist"
        self._write_plist(
            server_path,
            launch_agent_plist(
                label=LAUNCH_AGENT_SERVER_LABEL,
                program_arguments=[str(self.paths.python), "-m", "aichallenge_mcp.runtime", "run-server"],
                paths=self.paths,
            ),
        )
        self._write_plist(
            tunnel_path,
            launch_agent_plist(
                label=LAUNCH_AGENT_TUNNEL_LABEL,
                program_arguments=[
                    str(self.paths.python),
                    "-m",
                    "aichallenge_mcp.runtime",
                    "run-tunnel",
                    "--config",
                    str(self.paths.tunnel_config),
                ],
                paths=self.paths,
            ),
        )
        for path in (server_path, tunnel_path):
            self._bootout_if_loaded(path)
            self._run_launchctl("bootstrap", f"gui/{os.getuid()}", str(path))
        print("Installed launchd self-healing agents for the MCP server and Secure Tunnel client.")
        return self.up()

    def uninstall_launchd(self) -> int:
        for label in (LAUNCH_AGENT_SERVER_LABEL, LAUNCH_AGENT_TUNNEL_LABEL):
            self._run_launchctl("bootout", f"gui/{os.getuid()}/{label}", allow_failure=True)
            path = self.paths.launch_agents_dir / f"{label}.plist"
            if path.exists():
                path.unlink()
        print("Removed AI Challenge MCP launchd agents.")
        return 0

    def _config_check(self) -> Check:
        if not self.paths.tunnel_config.is_file():
            return Check("tunnel-config", False, "tunnel configuration file is missing")
        mode = self.paths.tunnel_config.stat().st_mode & 0o777
        if mode & 0o077:
            return Check("tunnel-config", False, "tunnel configuration file is readable by group or others")
        return Check("tunnel-config", True, "private tunnel configuration file is available")

    def _server_check(self) -> Check:
        payload = _safe_url_json(f"{self.paths.server_url}/readyz")
        ready = payload is not None and payload.get("status") == "ready"
        return Check("server", ready, "MCP /readyz responds" if ready else "MCP /readyz is not ready")

    def _tunnel_check(self) -> Check:
        health_url = tunnel_health_url(self.paths.tunnel_config)
        if health_url is None:
            return Check("tunnel", False, "tunnel health URL is not configured on loopback")
        payload = _safe_url_json(f"{health_url}/readyz")
        ready = payload is not None and payload.get("status") in {"ready", "ok"}
        return Check("tunnel", ready, "tunnel /readyz responds" if ready else "tunnel /readyz is not ready")

    def _launchd_check(self, label: str) -> Check:
        result = self._run_launchctl("print", f"gui/{os.getuid()}/{label}", allow_failure=True)
        name = "launchd-tunnel" if label == LAUNCH_AGENT_TUNNEL_LABEL else "launchd-server"
        return Check(name, result.returncode == 0, "LaunchAgent is loaded" if result.returncode == 0 else "LaunchAgent is not loaded")

    def _tunnel_config_check(self) -> Check:
        if not self._config_check().ok:
            return Check("tunnel-config-validation", False, "tunnel configuration cannot be validated")
        secret = self._keychain_reader(self.paths.keychain_service)
        if secret is None:
            return Check(
                "tunnel-config-validation",
                False,
                "macOS Keychain does not contain the Secure Tunnel runtime credential",
            )
        environment = os.environ.copy()
        environment["CONTROL_PLANE_API_KEY"] = secret
        result = subprocess.run(
            [str(self.paths.tunnel_client), "doctor", "--config", str(self.paths.tunnel_config)],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        detail = "tunnel-client configuration validates" if result.returncode == 0 else "tunnel-client configuration validation failed"
        return Check("tunnel-config-validation", result.returncode == 0, detail)

    def _require_local_server_prerequisites(self) -> None:
        if not self.paths.project_dir.is_dir() or not self.paths.python.is_file():
            raise RuntimeConfigurationError("project directory or managed virtual-environment Python is unavailable")

    def _require_tunnel_prerequisites(self) -> None:
        config = self._config_check()
        if not config.ok:
            raise RuntimeConfigurationError(config.detail)
        if not self.paths.tunnel_client.is_file():
            raise RuntimeConfigurationError("tunnel-client executable is unavailable")
        if tunnel_health_url(self.paths.tunnel_config) is None:
            raise RuntimeConfigurationError("tunnel health.listen_addr must use a fixed 127.0.0.1 port")

    def _ensure_runtime_directories(self) -> None:
        self.paths.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.paths.log_dir.mkdir(parents=True, exist_ok=True)

    def _spawn(self, command: list[str], stdout_path: Path, stderr_path: Path) -> None:
        with stdout_path.open("a", encoding="utf-8") as stdout, stderr_path.open("a", encoding="utf-8") as stderr:
            subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)  # noqa: S603

    @staticmethod
    def _wait_for(predicate: Callable[[], bool], *, attempts: int = 12) -> bool:
        for _ in range(attempts):
            if predicate():
                return True
            time.sleep(0.5)
        return False

    @staticmethod
    def _write_plist(path: Path, contents: dict[str, Any]) -> None:
        with path.open("wb") as handle:
            plistlib.dump(contents, handle, sort_keys=False)

    @staticmethod
    def _run_launchctl(*arguments: str, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(["/bin/launchctl", *arguments], check=False, capture_output=True, text=True)
        if result.returncode and not allow_failure:
            raise RuntimeConfigurationError("launchctl could not complete the requested local runtime operation")
        return result

    def _bootout_if_loaded(self, path: Path) -> None:
        self._run_launchctl("bootout", f"gui/{os.getuid()}", str(path), allow_failure=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the private AI Challenge MCP runtime")
    parser.add_argument("--project-dir")
    parser.add_argument("--tunnel-config")
    parser.add_argument("--tunnel-client")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "command",
        choices=("doctor", "status", "up", "run-server", "run-tunnel", "install-launchd", "uninstall-launchd"),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = RuntimePaths.from_environment(
        project_dir=args.project_dir,
        tunnel_config=args.tunnel_config,
        tunnel_client=args.tunnel_client,
    )
    controller = RuntimeController(paths)
    handlers: dict[str, Callable[[], int]] = {
        "doctor": controller.doctor,
        "status": controller.status,
        "up": controller.up,
        "run-server": controller.run_server,
        "run-tunnel": controller.run_tunnel,
        "install-launchd": controller.install_launchd,
        "uninstall-launchd": controller.uninstall_launchd,
    }
    try:
        raise SystemExit(handlers[args.command]())
    except RuntimeConfigurationError as exc:
        print(f"Runtime configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
