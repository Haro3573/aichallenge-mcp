from __future__ import annotations

from pathlib import Path
import plistlib
import socket

from aichallenge_mcp.runtime import (
    LAUNCH_AGENT_SERVER_LABEL,
    LAUNCH_AGENT_TUNNEL_LABEL,
    RuntimeController,
    RuntimePaths,
    _server_port_is_bound,
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


def test_doctor_reports_missing_keychain_credential_without_secret(tmp_path: Path, capsys):
    runtime_paths = paths(tmp_path)
    controller = RuntimeController(runtime_paths, keychain_reader=lambda _: None)

    status = controller.doctor()

    output = capsys.readouterr().out
    assert status == 1
    assert "macOS Keychain does not contain the Secure Tunnel runtime credential" in output
    assert "CONTROL_PLANE_API_KEY" not in output


def test_launch_agent_labels_are_distinct_for_both_supervised_processes():
    assert LAUNCH_AGENT_SERVER_LABEL != LAUNCH_AGENT_TUNNEL_LABEL


def test_server_port_check_detects_a_listener_without_starting_another_server():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        _, port = listener.getsockname()

        assert _server_port_is_bound(f"http://127.0.0.1:{port}") is True
