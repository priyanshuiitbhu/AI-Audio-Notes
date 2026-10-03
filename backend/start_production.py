"""Run migrations, FastAPI, and the persistent RQ worker in one container.

Keeping both processes in one service lets the existing local storage provider use
a single persistent volume. If either process exits, the container exits so the
hosting platform can restart the complete service.
"""

import os
import signal
import subprocess
import sys
import time


def terminate(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and any(p.poll() is None for p in processes):
        time.sleep(0.2)

    for process in processes:
        if process.poll() is None:
            process.kill()


def main() -> int:
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        check=False,
    )
    if migration.returncode != 0:
        return migration.returncode

    port = os.environ.get("PORT", "8000")
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                port,
                "--proxy-headers",
                "--forwarded-allow-ips=*",
            ]
        ),
        subprocess.Popen([sys.executable, "worker.py"]),
    ]

    stopping = False

    def handle_signal(signum, frame):
        nonlocal stopping
        if not stopping:
            stopping = True
            terminate(processes)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        while not stopping:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    stopping = True
                    terminate(processes)
                    return return_code if return_code != 0 else 1
            time.sleep(1)
    finally:
        terminate(processes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
