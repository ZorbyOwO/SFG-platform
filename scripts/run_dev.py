from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
API_REQUIREMENTS = ROOT / "api" / "requirements.txt"
BIOMETRIC_REQUIREMENTS = ROOT / "api" / "requirements-biometric.txt"
BIOMETRIC_ROOT = ROOT / "biometric"
RUNTIME_DIR = ROOT / "api" / ".runtime"

APP_URL = "http://127.0.0.1:5500"
KIOSK_URL = "http://127.0.0.1:5501"
API_URL = "http://127.0.0.1:8000"
SERVICE_PORTS = (5500, 5501, 8000)


class LauncherError(RuntimeError):
    pass


@dataclass(slots=True)
class Service:
    name: str
    process: subprocess.Popen[bytes]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up and run the complete SFG development system."
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the citizen app in the default browser.",
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Install missing dependencies and generate local secrets, then exit.",
    )
    parser.add_argument(
        "--pause-on-error",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def print_heading(message: str) -> None:
    print(f"\n[SFG] {message}", flush=True)


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def api_is_sfg() -> bool:
    try:
        with urllib.request.urlopen(f"{API_URL}/health", timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and payload.get("status") == "ok"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def existing_services_are_running() -> bool:
    return all(is_port_open(port) for port in SERVICE_PORTS) and api_is_sfg()


def ensure_ports_are_free() -> None:
    occupied = [str(port) for port in SERVICE_PORTS if is_port_open(port)]
    if occupied:
        ports = ", ".join(occupied)
        raise LauncherError(
            f"Port(s) {ports} are already in use. Close the older development "
            "servers, then run this launcher again."
        )


def venv_python_path() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def run_checked(command: list[str], *, cwd: Path = ROOT) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise LauncherError(f"Command failed with exit code {result.returncode}.")


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_python_environment() -> Path:
    python = venv_python_path()
    if not python.exists():
        print_heading("Creating the Python environment (first run only)...")
        run_checked([sys.executable, "-m", "venv", str(ROOT / ".venv")])

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    marker = RUNTIME_DIR / "requirements.sha256"
    current_digest = file_digest(API_REQUIREMENTS)

    current_digest = f"{current_digest}:{file_digest(BIOMETRIC_REQUIREMENTS)}"

    dependency_check = subprocess.run(
        [str(python), "-c", "import fastapi, uvicorn, multipart, httpx, cv2, torch, numpy, cryptography"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if dependency_check.returncode != 0 or not marker.exists() or marker.read_text(
        encoding="utf-8"
    ).strip() != current_digest:
        print_heading("Installing backend dependencies (first run only)...")
        run_checked(
            [str(python), "-m", "pip", "install", "-r", str(API_REQUIREMENTS)]
        )
        print_heading("Installing the face recognition runtime (first run only, ~250 MB)...")
        run_checked(
            [str(python), "-m", "pip", "install", "-r", str(BIOMETRIC_REQUIREMENTS)]
        )
        marker.write_text(current_digest, encoding="utf-8")

    return python


def ensure_biometric_models(python: Path) -> None:
    """Acquire the four commit-pinned model payloads and verify their hashes.

    The payloads are deliberately not committed. This is a no-op once they are
    present and valid, and it fails loudly rather than starting without them.
    """

    acquire = BIOMETRIC_ROOT / "tools" / "acquire_biometric_models.py"
    if not acquire.is_file():
        raise LauncherError(
            "biometric/tools/acquire_biometric_models.py is missing; the face recognition"
            " package is incomplete."
        )
    models = BIOMETRIC_ROOT / "internal" / "biometric-core" / "models"
    expected = (
        models / "face_detection_yunet_2023mar.onnx",
        models / "face_recognition_sface_2021dec.onnx",
        models / "silent_face" / "2.7_80x80_MiniFASNetV2.pth",
        models / "silent_face" / "4_0_0_80x80_MiniFASNetV1SE.pth",
    )
    if all(path.is_file() for path in expected):
        return
    print_heading("Downloading the pinned face recognition models (first run only)...")
    try:
        run_checked([str(python), str(acquire)])
    except LauncherError as error:
        raise LauncherError(
            "The pinned face recognition models could not be downloaded."
            f" Check your internet connection and try again. ({error})"
        ) from error


def find_npm() -> str:
    npm = shutil.which("npm")
    if not npm:
        raise LauncherError(
            "Node.js/npm was not found. Install Node.js 22 or newer, then run again."
        )
    return npm


def ensure_node_environment(npm: str) -> None:
    package_lock = WEB_DIR / "package-lock.json"
    node_modules = WEB_DIR / "node_modules"
    marker = node_modules / ".sfg-package-lock.sha256"
    current_digest = file_digest(package_lock)

    if not node_modules.exists() or not marker.exists() or marker.read_text(
        encoding="utf-8"
    ).strip() != current_digest:
        print_heading("Installing frontend dependencies (first run only)...")
        run_checked([npm, "install"], cwd=WEB_DIR)
        marker.write_text(current_digest, encoding="utf-8")


def ensure_supabase_environment() -> None:
    local_environment = WEB_DIR / ".env.local"
    example_environment = WEB_DIR / ".env.example"
    if not local_environment.exists():
        if not example_environment.exists():
            raise LauncherError("web/.env.example is missing; Supabase cannot be configured.")
        shutil.copyfile(example_environment, local_environment)
        print_heading("Created the local Supabase browser configuration.")


def ensure_dev_secret(python: Path) -> None:
    run_checked([str(python), str(ROOT / "scripts" / "create_dev_secrets.py")])


def read_browser_environment() -> dict[str, str]:
    """Read web/.env.local so the API can verify the same Supabase project."""

    values: dict[str, str] = {}
    local_environment = WEB_DIR / ".env.local"
    if not local_environment.exists():
        return values
    for raw in local_environment.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def process_options() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def start_services(python: Path, npm: str) -> list[Service]:
    frontend_env = os.environ.copy()
    frontend_env.update(
        {
            "VITE_DATA_MODE": "supabase",
            "VITE_API_BASE_URL": API_URL,
        }
    )
    # The trusted tier re-verifies each citizen's Supabase token upstream before
    # reading a frame. Only the public project URL and the browser-safe
    # publishable key are shared; no service-role secret is involved.
    api_env = os.environ.copy()
    browser_config = read_browser_environment()
    if browser_config.get("VITE_SUPABASE_URL"):
        api_env["SUPABASE_URL"] = browser_config["VITE_SUPABASE_URL"]
    if browser_config.get("VITE_SUPABASE_PUBLISHABLE_KEY"):
        api_env["SUPABASE_PUBLISHABLE_KEY"] = browser_config["VITE_SUPABASE_PUBLISHABLE_KEY"]
    # The hosted sealed-template upload path needs a service-class secret. It is
    # read only from the process environment (or api/.env via Settings), never
    # from web/.env.local, so it can never leak into the browser bundle.
    if not api_env.get("SUPABASE_BACKEND_SECRET") and (ROOT / "api" / ".env").is_file():
        pass  # Settings._load_local_env already picks up api/.env

    options = process_options()
    commands = [
        (
            "API",
            [
                str(python),
                "-m",
                "uvicorn",
                "api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT,
            api_env,
        ),
        ("Citizen app", [npm, "run", "dev"], WEB_DIR, frontend_env),
        (
            "Kiosk",
            [
                str(python),
                "-m",
                "http.server",
                "5501",
                "--bind",
                "127.0.0.1",
                "-d",
                str(ROOT / "kiosk"),
            ],
            ROOT,
            None,
        ),
    ]

    services: list[Service] = []
    try:
        for name, command, cwd, environment in commands:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                **options,
            )
            services.append(Service(name=name, process=process))
    except Exception:
        stop_services(services)
        raise
    return services


def services_are_ready() -> bool:
    return all(is_port_open(port) for port in SERVICE_PORTS) and api_is_sfg()


def wait_until_ready(services: list[Service], timeout_seconds: float = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        stopped = [service for service in services if service.process.poll() is not None]
        if stopped:
            names = ", ".join(service.name for service in stopped)
            raise LauncherError(f"The following service stopped during startup: {names}.")
        if services_are_ready():
            return
        time.sleep(0.25)
    raise LauncherError("The services did not become ready within 30 seconds.")


def stop_services(services: list[Service]) -> None:
    running = [service for service in services if service.process.poll() is None]
    if not running:
        return

    print_heading("Stopping development services...")
    if os.name == "nt":
        for service in running:
            subprocess.run(
                [
                    "taskkill",
                    "/PID",
                    str(service.process.pid),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    else:
        for service in running:
            try:
                os.killpg(service.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    for service in running:
        try:
            service.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.process.kill()


def monitor_services(services: list[Service]) -> int:
    while True:
        for service in services:
            exit_code = service.process.poll()
            if exit_code is not None:
                print_heading(f"{service.name} stopped with exit code {exit_code}.")
                return exit_code or 1
        time.sleep(0.5)


def show_ready_message(*, managed_by_launcher: bool = True) -> None:
    stop_message = (
        "Press Ctrl+C once to stop everything."
        if managed_by_launcher
        else "No new services were started. Use the existing server window to stop them."
    )
    print(
        "\n"
        "SFG is ready:\n"
        f"  Citizen app: {APP_URL}\n"
        f"  Kiosk:       {KIOSK_URL}\n"
        f"  API docs:    {API_URL}/docs\n"
        f"  API health:  {API_URL}/health\n"
        f"\n{stop_message}\n",
        flush=True,
    )


def main() -> int:
    args = parse_args()
    try:
        if not args.setup_only and existing_services_are_running():
            print_heading("SFG is already running.")
            show_ready_message(managed_by_launcher=False)
            if not args.no_open:
                webbrowser.open(APP_URL)
            return 0

        if not args.setup_only:
            ensure_ports_are_free()

        python = ensure_python_environment()
        npm = find_npm()
        ensure_node_environment(npm)
        ensure_supabase_environment()
        ensure_dev_secret(python)
        ensure_biometric_models(python)

        if args.setup_only:
            print_heading("Setup is complete. Run run-sfg.cmd to start SFG.")
            return 0

        print_heading("Starting the citizen app, API, and kiosk...")
        services = start_services(python, npm)
        try:
            wait_until_ready(services)
            show_ready_message()
            if not args.no_open:
                webbrowser.open(APP_URL)
            return monitor_services(services)
        finally:
            stop_services(services)
    except KeyboardInterrupt:
        return 0
    except LauncherError as error:
        print(f"\n[SFG] Could not start: {error}", file=sys.stderr, flush=True)
        if args.pause_on_error and sys.stdin.isatty():
            try:
                input("\nPress Enter to close this window...")
            except (EOFError, KeyboardInterrupt):
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
