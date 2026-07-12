#!/usr/bin/env python3
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = ROOT / "docker" / "docker-compose.yml"
CONTAINER_NAME = "ollama"


def run_command(command, cwd=None, check=True):
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}"
        )
    return completed


def docker_available():
    return shutil.which("docker") is not None


def compose_command():
    if shutil.which("docker") is None:
        return None

    if run_command(["docker", "compose", "version"], check=False).returncode == 0:
        return ["docker", "compose"]
    if shutil.which("docker-compose") is not None:
        return ["docker-compose"]
    return None


def container_exists(name):
    result = run_command(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        check=False,
    )
    return bool(result.stdout.strip())


def container_running(name):
    result = run_command(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        check=False,
    )
    return bool(result.stdout.strip())


def ensure_ollama_container():
    if not docker_available():
        print("Docker is not available on this system.")
        return False

    print("Docker is available.")

    if container_exists(CONTAINER_NAME):
        if container_running(CONTAINER_NAME):
            print(f"Container '{CONTAINER_NAME}' is already running.")
            return True

        print(f"Container '{CONTAINER_NAME}' exists but is not running. Starting it...")
        run_command(["docker", "start", CONTAINER_NAME], check=False)
        return True

    print(f"Container '{CONTAINER_NAME}' was not found. Deploying it with Docker Compose...")
    if not COMPOSE_FILE.exists():
        print(f"Compose file not found: {COMPOSE_FILE}")
        return False

    compose = compose_command()
    if compose is None:
        print("Docker Compose is not available on this system.")
        return False

    run_command(compose + ["-f", str(COMPOSE_FILE), "up", "-d"], cwd=ROOT)
    return True


def list_models():
    if not docker_available():
        print("Unable to list models because Docker is unavailable.")
        return

    if not container_exists(CONTAINER_NAME):
        print(f"Container '{CONTAINER_NAME}' is not available, so no models can be listed.")
        return

    print("Checking available Ollama models...")
    for attempt in range(1, 31):
        result = run_command(["docker", "exec", CONTAINER_NAME, "ollama", "list"], check=False)
        if result.returncode == 0:
            print("Available models:")
            print(result.stdout.strip() or "No models available.")
            return

        if attempt == 30:
            print("Unable to fetch models from Ollama after waiting for startup.")
            if result.stderr.strip():
                print(result.stderr.strip())
            return

        time.sleep(2)
        print(f"Ollama is still starting (attempt {attempt}/30); waiting...")


if __name__ == "__main__":
    try:
        if ensure_ollama_container():
            list_models()
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)
