from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import plistlib
import socket
from types import SimpleNamespace

import pytest

from aichallenge_mcp.runtime import (
    LAUNCH_AGENT_SERVER_LABEL,
    LAUNCH_AGENT_TUNNEL_LABEL,
    RuntimeController,
    RuntimeConfigurationError,
    RuntimePaths,
    build_parser,
    _server_port_is_bound,
    _http_endpoint_is_ok,
    launch_agent_plist,
    tunnel_health_url,
)


def paths(tmp_path: Path) -> RuntimePaths:
    project_dir = tmp_path / "project"
    python = project_dir / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    tunnel_client = tmp_path / "bin/tunnel-client"
    tunnel_client.parent.mkdir()
    tunnel_client.touch()
    config = tmp_path / "tunnel.yaml"
    config.write_text(
        "control_plane:\n  api_key: env:CONTROL_PLANE_API_KEY\nhealth:\n  listen_addr: 127.0.0.1:9123\n",
        encoding="utf-8",
    )
    config.chmod(0o600)
    return RuntimePaths(
        project_dir=project_dir,
        python=python,
        tunnel_client=tunnel_client,
        tunnel_config=config,
        runtime_dir=tmp_path / "runtime",
        log_dir=tmp_path / "logs",
        launch_agents_dir=tmp_path / "LaunchAgents",
    )


def test_tunnel_health_url_reads_only_loopback_health_address(tmp_path: Path):
    config = tmp_path / "tunnel.yaml"
    config.write_text(
        "control_plane:\n  api_key: env:CONTROL_PLANE_API_KEY\nhealth:\n  listen_addr: 127.0.0.1:9123\n",
        encoding="utf-8",
    )

    assert tunnel_health_url(config) == "http://127.0.0.1:9123"


def test_tunnel_health_url_rejects_non_loopback_address(tmp_path: Path):
    config = tmp_path / "tunnel.yaml"
    config.write_text("health:\n  listen_addr: 0.0.0.0:9123\n", encoding="utf-8")

    assert tunnel_health_url(config) is None


def test_launch_agent_plists_restart_without_embedding_credentials(tmp_path: Path):
    runtime_paths = paths(tmp_path)
    plist = launch_agent_plist(
        label=LAUNCH_AGENT_TUNNEL_LABEL,
        program_arguments=[str(runtime_paths.python), "-m", "aichallenge_mcp.runtime", "run-tunnel"],
        paths=runtime_paths,
    )
    encoded = plistlib.dumps(plist).decode("utf-8")

    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] == {"SuccessfulExit": False}
    assert plist["ThrottleInterval"] == 10
    assert "CONTROL_PLANE_API_KEY" not in encoded
    assert "EnvironmentVariables" not in plist


def test_tunnel_launch_agent_keeps_keychain_service_name_but_not_credential(tmp_path: Path):
    runtime_paths = paths(tmp_path)
    runtime_paths = replace(runtime_paths, keychain_service="existing-openai-key")
    controller = RuntimeController(runtime_paths)
    command = [
        str(runtime_paths.python),
        "-m",
        "aichallenge_mcp.runtime",
        "run-tunnel",
        "--tunnel-config",
        str(runtime_paths.tunnel_config),
        "--keychain-service",
        runtime_paths.keychain_service,
    ]
    plist = launch_agent_plist(label=LAUNCH_AGENT_TUNNEL_LABEL, program_arguments=command, paths=runtime_paths)
    encoded = plistlib.dumps(plist).decode("utf-8")

    assert "existing-openai-key" in encoded
    assert "CONTROL_PLANE_API_KEY" not in encoded


def test_doctor_reports_missing_existing_tunnel_credential_without_secret(tmp_path: Path, capsys):
    runtime_paths = paths(tmp_path)
    controller = RuntimeController(runtime_paths, credential_reader=lambda _: None)

    status = controller.doctor()

    output = capsys.readouterr().out
    assert status == 1
    assert "existing Secure Tunnel runtime credential is unavailable" in output
    assert "CONTROL_PLANE_API_KEY" not in output


def test_launch_agent_labels_are_distinct_for_both_supervised_processes():
    assert LAUNCH_AGENT_SERVER_LABEL != LAUNCH_AGENT_TUNNEL_LABEL


def test_runtime_parser_accepts_tunnel_configuration_after_the_command():
    args = build_parser().parse_args(
        ["run-tunnel", "--tunnel-config", "/tmp/aichallenge-tunnel.yaml", "--keychain-service", "openai"]
    )

    assert args.command == "run-tunnel"
    assert args.tunnel_config == "/tmp/aichallenge-tunnel.yaml"
    assert args.keychain_service == "openai"


def test_start_tunnel_refuses_to_spawn_without_an_existing_tunnel_credential(tmp_path: Path):
    controller = RuntimeController(paths(tmp_path), credential_reader=lambda _: None)
    controller._spawn = lambda *_: pytest.fail("tunnel process must not start")  # type: ignore[method-assign]

    with pytest.raises(RuntimeConfigurationError, match="credential"):
        controller.start_tunnel()


def test_tunnel_daemon_clean_exit_is_restartable_for_launchd(tmp_path: Path, monkeypatch):
    controller = RuntimeController(paths(tmp_path), credential_reader=lambda _: "not-printed")
    monkeypatch.setattr(controller, "_require_tunnel_prerequisites", lambda: None)
    monkeypatch.setattr("aichallenge_mcp.runtime.subprocess.run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))

    assert controller.run_tunnel() == 1


def test_server_port_check_detects_a_listener_without_starting_another_server():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        _, port = listener.getsockname()

        assert _server_port_is_bound(f"http://127.0.0.1:{port}") is True


def test_plain_text_health_endpoint_is_accepted(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr("aichallenge_mcp.runtime.urlopen", lambda *_args, **_kwargs: Response())

    assert _http_endpoint_is_ok("http://127.0.0.1:8080/readyz") is True


def test_active_tunnel_skips_conflicting_second_configuration_probe(tmp_path: Path, monkeypatch):
    controller = RuntimeController(paths(tmp_path), credential_reader=lambda _: "not-printed")
    monkeypatch.setattr(controller, "_tunnel_check", lambda: type("Check", (), {"ok": True})())
    monkeypatch.setattr("aichallenge_mcp.runtime.subprocess.run", lambda *_args, **_kwargs: pytest.fail("must not probe"))

    result = controller._tunnel_config_check()

    assert result.ok is True
