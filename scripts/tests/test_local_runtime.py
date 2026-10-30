"""Exercise launcher boundaries in subprocesses, including foreign-process safety."""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts/local.sh"


class LocalEnvironment(dict):
    # Pytest failure reports should not dump inherited terminal credentials.
    def __repr__(self):
        return "<local test environment>"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def local_env(tmp_path):
    api, pg = free_port(), free_port()
    while pg == api:
        pg = free_port()
    return LocalEnvironment(
        {
            **os.environ,
            "LOCAL_PYTHON": sys.executable,
            "LOCAL_RUNTIME_DIR": str(tmp_path / "native runtime with spaces"),
            "LOCAL_API_PORT": str(api),
            "LOCAL_PG_PORT": str(pg),
            "LOCAL_PG_BIN": str(tmp_path / "not-installed"),
        }
    )


def invoke(local_env, *args):
    return subprocess.run(
        ["bash", str(LAUNCHER), *args],
        cwd="/tmp",
        env=local_env,
        capture_output=True,
        text=True,
        timeout=40,
    )


def test_help_works_from_another_directory_without_services(local_env):
    result = invoke(local_env, "--help")
    assert result.returncode == 0
    assert "--retrain" in result.stdout
    assert not Path(local_env["LOCAL_RUNTIME_DIR"]).exists()


def test_status_reports_stopped_without_creating_database(local_env):
    result = invoke(local_env, "status")
    assert result.returncode == 1
    assert "PostgreSQL: stopped" in result.stdout
    assert "FastAPI: stopped" in result.stdout
    assert not Path(local_env["LOCAL_RUNTIME_DIR"]).exists()


@pytest.mark.parametrize("value", ["0", "65536", "not-a-port"])
def test_invalid_ports_fail_before_initialization(local_env, value):
    local_env["LOCAL_API_PORT"] = value
    result = invoke(local_env)
    assert result.returncode == 1
    assert "port" in result.stdout.lower()
    assert not Path(local_env["LOCAL_RUNTIME_DIR"]).exists()


def test_occupied_port_is_not_stopped_or_reused(local_env):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        local_env["LOCAL_API_PORT"] = str(listener.getsockname()[1])
        result = invoke(local_env)
        assert result.returncode == 1
        assert "LOCAL_API_PORT" in result.stdout
        assert "occupied" in result.stdout
        with socket.create_connection(listener.getsockname(), timeout=1):
            pass  # A real connection proves the unrelated listener is still alive.
    assert not (Path(local_env["LOCAL_RUNTIME_DIR"]) / "pgdata").exists()


def test_missing_postgres_gives_installation_instructions(local_env):
    result = invoke(local_env)
    assert result.returncode == 1
    assert "PostgreSQL 16" in result.stdout
    assert "LOCAL_PG_BIN" in result.stdout
    assert not (Path(local_env["LOCAL_RUNTIME_DIR"]) / "pgdata").exists()


def test_duplicate_launcher_does_not_overwrite_live_state(local_env):
    directory = Path(local_env["LOCAL_RUNTIME_DIR"])
    directory.mkdir()
    state = {"sentinel": "existing launch"}
    (directory / "state.json").write_text(json.dumps(state))
    with (directory / "launcher.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = invoke(local_env)
    assert result.returncode == 1
    assert "already running" in result.stdout
    assert json.loads((directory / "state.json").read_text()) == state


def test_stop_refuses_to_signal_foreign_process(local_env):
    directory = Path(local_env["LOCAL_RUNTIME_DIR"])
    directory.mkdir()
    identity = subprocess.check_output(
        ["ps", "-ww", "-p", str(os.getpid()), "-o", "lstart=", "-o", "args="],
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    ).strip()
    (directory / "state.json").write_text(
        json.dumps({"launcher": {"pid": os.getpid(), "identity": identity}})
    )
    result = invoke(local_env, "stop")
    assert result.returncode == 1
    assert "refusing to signal" in result.stdout
    os.kill(os.getpid(), 0)  # The unrelated parent process remains alive.


@pytest.mark.skipif(
    os.getenv("RUN_NATIVE_LOCAL_TESTS") != "1",
    reason="Requires native PostgreSQL 16 and prepared real-data bundle",
)
def test_native_lifecycle_ctrl_c_restart_and_stop(local_env, tmp_path):
    """A real cluster proves cold setup, retained data, restart and both stop paths."""
    local_env.pop("LOCAL_PG_BIN", None)
    if os.getenv("LOCAL_PG_BIN"):
        local_env["LOCAL_PG_BIN"] = os.environ["LOCAL_PG_BIN"]
    directory = Path(local_env["LOCAL_RUNTIME_DIR"])
    port = int(local_env["LOCAL_API_PORT"])
    model_path = ROOT / "backend/models/bundle/recommender.joblib"
    model_before = model_path.stat().st_mtime_ns
    process = None
    log_path = tmp_path / "launcher.log"

    def start():
        with log_path.open("a") as log:
            child = subprocess.Popen(
                ["bash", str(LAUNCHER)],
                cwd="/tmp",
                env=local_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        return child

    def wait_ready(child):
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            assert child.poll() is None, log_path.read_text()
            try:
                with urlopen(f"http://127.0.0.1:{port}/ready", timeout=1) as response:
                    if json.load(response).get("status") == "ready":
                        return
            except (OSError, URLError):
                pass
            time.sleep(0.3)
        pytest.fail(log_path.read_text())

    def row_count():
        state = json.loads((directory / "state.json").read_text())
        env = {**local_env, "PGPASSFILE": str(directory / "pgpass")}
        return subprocess.check_output(
            [
                str(Path(state["pg_bin"]) / "psql"),
                "-X",
                "-w",
                "-h",
                "127.0.0.1",
                "-p",
                local_env["LOCAL_PG_PORT"],
                "-U",
                "postgres",
                "-d",
                "ecommerce_recommendations",
                "-Atqc",
                "SELECT count(*) FROM user_interactions",
            ],
            env=env,
            text=True,
        ).strip()

    try:
        process = start()
        wait_ready(process)
        assert invoke(local_env, "status").returncode == 0
        count = row_count()
        assert count == "386326"
        with urlopen(f"http://127.0.0.1:{port}/recommend/12347?top_k=3") as response:
            body = json.load(response)
            assert body["recommendation_strategy"] == "user_cosine"
            assert len(body["recommended_products"]) == 3
        # Simulate terminal Ctrl+C, then verify both listeners were released.
        os.killpg(process.pid, signal.SIGINT)
        assert process.wait(timeout=40) == 0, log_path.read_text()
        assert invoke(local_env, "status").returncode == 1
        for selected in [port, int(local_env["LOCAL_PG_PORT"])]:
            with socket.socket() as probe:
                assert probe.connect_ex(("127.0.0.1", selected)) != 0
        assert (directory / "pgdata/PG_VERSION").exists()
        process = start()
        wait_ready(process)
        assert row_count() == count
        assert (
            model_path.stat().st_mtime_ns == model_before
        )  # Normal startup never retrains.
        assert invoke(local_env, "stop").returncode == 0
        assert process.wait(timeout=40) == 0
        assert invoke(local_env, "stop").returncode == 0
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=40)


def test_stop_refuses_database_owned_by_another_project(local_env):
    directory = Path(local_env["LOCAL_RUNTIME_DIR"])
    (directory / "pgdata").mkdir(parents=True)
    (directory / "pgdata/PG_VERSION").write_text("16\n")
    (directory / "owner.json").write_text(
        json.dumps({"project_root": "/another-project"})
    )
    result = invoke(local_env, "stop")
    assert result.returncode == 1
    assert "belongs to another project" in result.stdout
    assert (directory / "pgdata/PG_VERSION").exists()


def test_reuse_refuses_foreign_postmaster_before_connecting(local_env, monkeypatch):
    import runpy
    from types import SimpleNamespace

    for key in ["LOCAL_RUNTIME_DIR", "LOCAL_API_PORT", "LOCAL_PG_PORT"]:
        monkeypatch.setenv(key, local_env[key])
    controller = runpy.run_path(str(ROOT / "scripts/local_runtime.py"))["LocalRuntime"](
        SimpleNamespace(command="start", retrain=False)
    )
    controller.data.mkdir(parents=True)
    (controller.data / "PG_VERSION").write_text("16\n")
    controller.pg_bin = Path("/not-needed")
    monkeypatch.setattr(controller, "pg_running", lambda: True)
    monkeypatch.setattr(controller, "pg_owned", lambda: False)

    def unexpected_connection(*args, **kwargs):
        pytest.fail("No database command may run against an unverified postmaster")

    monkeypatch.setattr(controller, "run", unexpected_connection)
    with pytest.raises(RuntimeError, match="refusing to connect"):
        controller.start_database()
