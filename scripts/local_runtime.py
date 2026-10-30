"""Manage a native, project-owned PostgreSQL 16 cluster and FastAPI process.

The shell entry point selects Python; this stdlib-only controller bootstraps its
venv, checks prerequisites, and owns process cleanup. It never invokes Docker.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib.metadata
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATABASE = "ecommerce_recommendations"


def message(text: str) -> None:
    print(f"[local] {text}", flush=True)


def port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise ValueError(f"Invalid port: {value!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError("Ports must be between 1 and 65535")
    return port


def process_identity(pid: int | None) -> str:
    """PID plus start time prevents a stale record from signaling a reused PID."""
    if not pid or pid <= 1:
        return ""
    result = subprocess.run(
        ["ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "args="],
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def process_matches(record: dict | None, marker: str) -> bool:
    if not record or not isinstance(record.get("pid"), int):
        return False
    actual = process_identity(record["pid"])
    return bool(actual and actual == record.get("identity") and marker in actual)


def check_port(port: int, label: str) -> None:
    """Check before installing dependencies, training, or starting any services."""
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            variable = "LOCAL_API_PORT" if label == "API" else "LOCAL_PG_PORT"
            raise RuntimeError(
                f"{label} port {port} is occupied. Stop its existing service or set {variable} to a free port."
            ) from None


def find_postgres() -> Path:
    """Support explicit binaries, PATH, Postgres.app, Homebrew and Linux packages."""
    explicit = os.environ.get("LOCAL_PG_BIN")
    candidates = [Path(explicit).expanduser()] if explicit else []
    if not explicit:
        on_path = shutil.which("pg_ctl")
        if on_path:
            candidates.append(Path(on_path).resolve().parent)
        candidates.extend(
            [
                Path.home() / "Applications/Postgres.app/Contents/Versions/16/bin",
                Path("/Applications/Postgres.app/Contents/Versions/16/bin"),
                Path("/opt/homebrew/opt/postgresql@16/bin"),
                Path("/usr/local/opt/postgresql@16/bin"),
                Path("/usr/lib/postgresql/16/bin"),
            ]
        )
        # A custom Homebrew prefix is used only after checking the common paths.
        if not any(
            (candidate / "pg_ctl").exists() for candidate in candidates
        ) and shutil.which("brew"):
            prefix = subprocess.run(
                ["brew", "--prefix", "postgresql@16"], capture_output=True, text=True
            )
            if prefix.returncode == 0:
                candidates.append(Path(prefix.stdout.strip()) / "bin")
    commands = ["postgres", "pg_ctl", "initdb", "psql", "createdb"]
    for candidate in candidates:
        if not all(os.access(candidate / command, os.X_OK) for command in commands):
            continue
        version = subprocess.run(
            [str(candidate / "postgres"), "--version"], capture_output=True, text=True
        )
        if version.returncode == 0 and re.search(r"\b16\.", version.stdout):
            return candidate.resolve()
    raise RuntimeError(
        "Native PostgreSQL 16 binaries were not found. On macOS install the PostgreSQL 16 "
        "build from https://postgresapp.com/downloads.html into ~/Applications or /Applications. "
        "Homebrew users can run: brew install postgresql@16. "
        "Alternatively set LOCAL_PG_BIN to the directory containing PostgreSQL 16's pg_ctl/initdb/psql."
    )


class LocalRuntime:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.directory = (
            Path(os.environ.get("LOCAL_RUNTIME_DIR", ROOT / ".runtime/local"))
            .expanduser()
            .resolve()
        )
        self.data = self.directory / "pgdata"
        self.state_path = self.directory / "state.json"
        self.pg_port = port_number(os.environ.get("LOCAL_PG_PORT", "55433"))
        self.api_port = port_number(os.environ.get("LOCAL_API_PORT", "8000"))
        if self.pg_port == self.api_port:
            raise ValueError("LOCAL_PG_PORT and LOCAL_API_PORT must differ")
        self.pg_bin: Path | None = None
        self.child: subprocess.Popen | None = None
        self.database_started = False
        self.owns_state = False
        self.lock = None
        self.env = os.environ.copy()
        self.state = self.read_state()

    def read_state(self) -> dict:
        if not self.state_path.exists():
            return {}
        try:
            value = json.loads(self.state_path.read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            raise RuntimeError(
                f"Cannot read runtime state: {self.state_path}"
            ) from None

    def write_state(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n")
        temporary.replace(self.state_path)

    def check_owner(self, *, create: bool = False) -> None:
        """An explicit runtime-dir override must not take over another project's DB."""
        owner = self.directory / "owner.json"
        if owner.exists():
            if json.loads(owner.read_text()).get("project_root") != str(ROOT):
                raise RuntimeError(
                    "This runtime directory belongs to another project; choose a fresh LOCAL_RUNTIME_DIR."
                )
        elif self.data.exists():
            raise RuntimeError(
                "Database directory has no project ownership marker; existing data was preserved."
            )
        elif create:
            owner.write_text(json.dumps({"project_root": str(ROOT)}) + "\n")

    def run(self, command: list[str], *, capture: bool = False) -> str:
        """Track startup commands too, so interrupting a seed/training run leaves no orphan."""
        self.child = subprocess.Popen(
            command,
            cwd=BACKEND,
            env=self.env,
            start_new_session=True,
            stdout=subprocess.PIPE if capture else None,
            text=True,
        )
        try:
            output, _ = self.child.communicate()
            if self.child.returncode:
                raise RuntimeError(
                    f"Command failed ({self.child.returncode}): {Path(command[0]).name}. See output above."
                )
            return output or ""
        finally:
            self.terminate_child()

    def terminate_child(self) -> None:
        child = self.child
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        self.child = None

    def pg_running(self) -> bool:
        if not self.pg_bin or not (self.data / "PG_VERSION").exists():
            return False
        return (
            subprocess.run(
                [str(self.pg_bin / "pg_ctl"), "-D", str(self.data), "status"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )

    def dependencies(self) -> None:
        """Only install when an exact direct dependency is missing or has changed."""
        needed = False
        for line in (BACKEND / "requirements.txt").read_text().splitlines():
            match = re.fullmatch(r"([\w.-]+)==(.+)", line.strip())
            if match:
                try:
                    needed |= importlib.metadata.version(match[1]) != match[2]
                except importlib.metadata.PackageNotFoundError:
                    needed = True
        if needed:
            if sys.prefix == sys.base_prefix:
                raise RuntimeError(
                    "Dependency installation requires a virtual environment. Use the project's .venv."
                )
            message("Installing pinned backend dependencies...")
            self.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--only-binary=:all:",
                    "-r",
                    "requirements.txt",
                ]
            )

    def configure_environment(self) -> None:
        password_path = self.directory / "db-password"
        if not password_path.exists():
            if self.data.exists():
                raise RuntimeError(
                    "Local credential file is missing. Restore db-password for this cluster; existing data was preserved."
                )
            password_path.write_text(secrets.token_hex(24) + "\n")
            password_path.chmod(0o600)
        password = password_path.read_text().strip()
        if not re.fullmatch(r"[a-f0-9]{48}", password):
            raise RuntimeError(
                "Invalid local credential file; restore the original db-password for this cluster."
            )
        passfile = self.directory / "pgpass"
        passfile.write_text(f"127.0.0.1:{self.pg_port}:*:postgres:{password}\n")
        passfile.chmod(0o600)
        # Do not inherit a terminal's unrelated PostgreSQL service/connection settings.
        for key in [
            "PGHOST",
            "PGPORT",
            "PGDATABASE",
            "PGUSER",
            "PGPASSWORD",
            "PGSERVICE",
            "PGSERVICEFILE",
            "PGOPTIONS",
            "PGPASSFILE",
        ]:
            self.env.pop(key, None)
        self.env.update(
            {
                "PGHOST": "127.0.0.1",
                "PGPORT": str(self.pg_port),
                "PGUSER": "postgres",
                "PGPASSFILE": str(passfile),
                "PGSSLMODE": "disable",
                "PYTHONUNBUFFERED": "1",
                "DATABASE_URL": f"postgresql+psycopg2://postgres:{quote(password, safe='')}@127.0.0.1:{self.pg_port}/{DATABASE}",
                "MODEL_BUNDLE_DIR": str(BACKEND / "models/bundle"),
            }
        )

    def start_database(self) -> None:
        assert self.pg_bin is not None
        if self.data.exists() and not (self.data / "PG_VERSION").exists():
            raise RuntimeError(
                f"Incomplete database directory {self.data}; inspect it before retrying. It has not been deleted."
            )
        if not self.data.exists():
            message(f"Initializing native PostgreSQL in {self.data}")
            self.run(
                [
                    str(self.pg_bin / "initdb"),
                    "-D",
                    str(self.data),
                    "-U",
                    "postgres",
                    "--pwfile",
                    str(self.directory / "db-password"),
                    "--auth-host=scram-sha-256",
                    "--auth-local=trust",
                    "--encoding=UTF8",
                    "--locale=C",
                ]
            )
        if (self.data / "PG_VERSION").read_text().strip() != "16":
            raise RuntimeError(
                "This launcher requires a PostgreSQL 16 cluster; existing data was preserved."
            )
        if self.pg_running():
            if not self.pg_owned():
                raise RuntimeError(
                    "Running postmaster does not belong to this project; refusing to connect to it."
                )
            actual_port = int(
                (self.data / "postmaster.pid").read_text().splitlines()[3]
            )
            if actual_port != self.pg_port:
                raise RuntimeError(
                    f"Project PostgreSQL already runs on {actual_port}; use LOCAL_PG_PORT={actual_port} or stop it first."
                )
            message("Reusing the running project PostgreSQL instance.")
        else:
            check_port(self.pg_port, "PostgreSQL")
            # Disable Unix sockets: long workspace paths exceed macOS socket limits.
            config = self.data / "local-launcher.conf"
            config.write_text(
                f"listen_addresses = '127.0.0.1'\nport = {self.pg_port}\nunix_socket_directories = ''\ntimezone = 'UTC'\n"
            )
            main_config = self.data / "postgresql.conf"
            if "include = 'local-launcher.conf'" not in main_config.read_text():
                with main_config.open("a") as output:
                    output.write(
                        "\n# Project-local launcher settings\ninclude = 'local-launcher.conf'\n"
                    )
            self.database_started = (
                True  # Also clean up if pg_ctl is interrupted mid-start.
            )
            self.run(
                [
                    str(self.pg_bin / "pg_ctl"),
                    "-D",
                    str(self.data),
                    "-l",
                    str(self.directory / "postgres.log"),
                    "-w",
                    "start",
                ]
            )
        exists = self.run(
            [
                str(self.pg_bin / "psql"),
                "-X",
                "-w",
                "-d",
                "postgres",
                "-Atqc",
                f"SELECT 1 FROM pg_database WHERE datname = '{DATABASE}'",
            ],
            capture=True,
        ).strip()
        if exists != "1":
            self.run([str(self.pg_bin / "createdb"), "-w", DATABASE])

    def pg_owned(self) -> bool:
        """Verify the actual postmaster's data directory before asking pg_ctl to stop it."""
        try:
            pid = int((self.data / "postmaster.pid").read_text().splitlines()[0])
        except (OSError, ValueError, IndexError):
            return False
        identity = process_identity(pid)
        return "postgres" in identity and str(self.data) in identity

    def start(self) -> None:
        os.umask(0o077)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = (self.directory / "launcher.lock").open("a+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            self.lock = None
            raise RuntimeError(
                "This project's local launcher is already running. Use ./scripts/local.sh status or stop."
            ) from None
        check_port(self.api_port, "API")
        self.pg_bin = find_postgres()
        self.check_owner(create=True)
        if not self.pg_running():
            check_port(self.pg_port, "PostgreSQL")
        self.state = {
            "launcher": {"pid": os.getpid(), "identity": process_identity(os.getpid())},
            "api": None,
            "pg_bin": str(self.pg_bin),
            "pg_port": self.pg_port,
            "api_port": self.api_port,
        }
        self.write_state()
        self.owns_state = True
        self.dependencies()
        self.configure_environment()
        bundle = BACKEND / "models/bundle"
        artifacts = [
            bundle / name
            for name in ["manifest.json", "evaluation.json", "recommender.joblib"]
        ]
        artifacts.append(BACKEND / "data/processed/purchases.csv")
        if self.args.retrain or not all(item.exists() for item in artifacts):
            message(
                "Preparing/training the model. The first run can take several minutes..."
            )
            self.run([sys.executable, "-m", "src.train_model"])
        # Validate before starting a DB or touching its schema/data.
        self.run(
            [
                sys.executable,
                "-c",
                "from app.services.recommendation_service import load_bundle; load_bundle()",
            ]
        )
        self.start_database()
        message("Applying migrations and seeding the matching purchase snapshot...")
        self.run([sys.executable, "-m", "alembic", "upgrade", "head"])
        self.run([sys.executable, "-m", "src.seed_database"])
        with (self.directory / "api.log").open("a") as log:
            self.child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--app-dir",
                    str(BACKEND),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(self.api_port),
                ],
                cwd=BACKEND,
                env=self.env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self.state["api"] = {
                "pid": self.child.pid,
                "identity": process_identity(self.child.pid),
            }
            self.write_state()
            expected_model = json.loads((bundle / "manifest.json").read_text())[
                "model_version"
            ]
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if self.child.poll() is not None:
                    raise RuntimeError(
                        f"FastAPI exited before becoming ready. See {self.directory / 'api.log'}"
                    )
                payload = self.ready_payload(self.api_port)
                if (
                    payload.get("model_version") == expected_model
                    and self.child.poll() is None
                ):
                    break
                time.sleep(0.3)
            else:
                raise RuntimeError(
                    f"API readiness timed out. See {self.directory / 'api.log'}"
                )
            # Record the post-exec identity as well as the PID for safe orphan cleanup.
            self.state["api"]["identity"] = process_identity(self.child.pid)
            self.write_state()
            message(f"PostgreSQL: 127.0.0.1:{self.pg_port} ({DATABASE})")
            message(f"FastAPI: http://127.0.0.1:{self.api_port}/docs")
            message(
                f"Logs: {self.directory / 'api.log'} and {self.directory / 'postgres.log'}"
            )
            message(
                "Ready. Ctrl+C stops this launcher's services and retains the database."
            )
            if self.child.wait() != 0:
                raise RuntimeError(
                    f"FastAPI exited unexpectedly. See {self.directory / 'api.log'}"
                )

    @staticmethod
    def ready_payload(port: int) -> dict:
        try:
            with urlopen(f"http://127.0.0.1:{port}/ready", timeout=1) as response:
                return json.load(response)
        except (URLError, OSError, ValueError):
            return {}

    def stop_database(self) -> None:
        if self.pg_running():
            if not self.pg_owned():
                raise RuntimeError(
                    "Postmaster identity does not match this data directory; refusing to stop it."
                )
            subprocess.run(
                [
                    str(self.pg_bin / "pg_ctl"),
                    "-D",
                    str(self.data),
                    "-m",
                    "fast",
                    "-w",
                    "-t",
                    "30",
                    "stop",
                ],
                check=True,
            )

    def cleanup(self) -> None:
        if self.lock is None:
            return  # A duplicate launch must not clean up another launcher's services.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            self.terminate_child()
            if self.database_started:
                message("Stopping the PostgreSQL instance started by this launcher...")
                self.stop_database()
        finally:
            if self.owns_state:
                self.state.update({"launcher": None, "api": None})
                self.write_state()
            self.lock.close()
            self.lock = None

    def stop(self) -> None:
        launcher = self.state.get("launcher")
        if process_matches(launcher, str(Path(__file__).resolve())):
            os.kill(launcher["pid"], signal.SIGTERM)
            deadline = time.monotonic() + 35
            while process_matches(launcher, str(Path(__file__).resolve())):
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "Shutdown is still in progress; inspect the logs before retrying."
                    )
                time.sleep(0.2)
            message("Local launcher stopped. Database files retained.")
            return
        if launcher and process_identity(launcher.get("pid")):
            raise RuntimeError(
                "Saved launcher PID is not this project's process; refusing to signal it."
            )
        # Recover verified project-owned orphans after an abrupt controller exit.
        api = self.state.get("api")
        if process_matches(api, str(BACKEND)) and "uvicorn" in api["identity"]:
            os.killpg(api["pid"], signal.SIGTERM)
            deadline = time.monotonic() + 15
            while process_matches(api, str(BACKEND)):
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "API shutdown is still in progress; retry after inspecting api.log."
                    )
                time.sleep(0.2)
        if (self.data / "PG_VERSION").exists():
            self.check_owner()
            self.pg_bin = find_postgres()
            self.stop_database()
        if self.directory.exists():
            self.state.update({"launcher": None, "api": None})
            self.write_state()
        message("Project-local services stopped. Database files retained.")

    def status(self) -> int:
        pg_port = self.state.get("pg_port", self.pg_port)
        api_port = self.state.get("api_port", self.api_port)
        if (self.data / "PG_VERSION").exists():
            self.check_owner()
            self.pg_bin = find_postgres()
        database_running = self.pg_running() and self.pg_owned()
        api_running = process_matches(self.state.get("api"), str(BACKEND))
        ready = api_running and self.ready_payload(api_port).get("status") == "ready"
        message(
            f"PostgreSQL: {'running' if database_running else 'stopped'} (127.0.0.1:{pg_port})"
        )
        message(
            f"FastAPI: {'ready' if ready else 'starting' if api_running else 'stopped'} (http://127.0.0.1:{api_port})"
        )
        message(f"Runtime files: {self.directory}")
        return 0 if database_running and ready else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="./scripts/local.sh",
        description=__doc__,
        epilog="Overrides: LOCAL_API_PORT (8000), LOCAL_PG_PORT (55433), LOCAL_PG_BIN, LOCAL_PYTHON, LOCAL_RUNTIME_DIR.",
    )
    parser.add_argument(
        "command", nargs="?", choices=["start", "stop", "status"], default="start"
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Regenerate/evaluate the model before starting",
    )
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error(
            "Python 3.14 is required; use the project .venv or set LOCAL_PYTHON."
        )
    if args.retrain and args.command != "start":
        parser.error("--retrain is only valid when starting")
    if os.geteuid() == 0:
        parser.error("Run as your normal user; PostgreSQL does not run as root.")
    # A fresh checkout can bootstrap an isolated venv without global pip changes.
    if (
        args.command == "start"
        and sys.prefix == sys.base_prefix
        and not os.environ.get("LOCAL_PYTHON")
    ):
        import venv

        target = ROOT / ".venv"
        message(f"Creating Python 3.14 environment: {target}")
        venv.create(target, with_pip=True)
        interpreter = target / "bin/python"
        os.execv(
            interpreter,
            [str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]],
        )
    runtime = None
    try:
        runtime = LocalRuntime(args)
        if args.command == "status":
            return runtime.status()
        if args.command == "stop":
            runtime.stop()
            return 0

        def interrupted(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, interrupted)
        signal.signal(signal.SIGTERM, interrupted)
        runtime.start()
        return 0
    except KeyboardInterrupt:
        message("Stopping local services...")
        return 0
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        message(f"ERROR: {error}")
        return 1
    finally:
        if runtime is not None and args.command == "start":
            runtime.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
