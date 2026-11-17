"""Switch the active backend (qualibrate project), optionally downloading its state.

    uv run python user_scripts/switch_backend.py <backend> [--download]
    uv run python user_scripts/switch_backend.py            # list backends

Nodes, notebooks and the qualibrate app all follow the active project: its
QUAM state folder, its data folder and (through config/quam_builder) its QUAM
class. To add a backend this checkout doesn't have yet, run
'uv run install.py --backend <backend>'.
"""

import argparse
import os
import shutil
import subprocess
import sys


def qualibrate_executable() -> str:
    # Next to this interpreter first (the venv's bin/Scripts folder, reliable
    # even when the venv isn't activated), then PATH.
    for name in ("qualibrate", "qualibrate.exe"):
        candidate = os.path.join(os.path.dirname(sys.executable), name)
        if os.path.isfile(candidate):
            return candidate
    on_path = shutil.which("qualibrate")
    if on_path:
        return on_path
    raise SystemExit("Could not find the 'qualibrate' executable; run 'uv run install.py' first.")


def qualibrate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([qualibrate_executable(), *args], capture_output=True, text=True)


def switch_backend(backend: str) -> None:
    result = qualibrate("project", "switch", backend)
    if result.returncode != 0:
        raise SystemExit(
            f"Could not switch to '{backend}': {(result.stderr or result.stdout).strip()}\n"
            f"Add it first with: uv run install.py --backend {backend}"
        )
    print(f"Active backend is now '{backend}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("backend", nargs="?", help="Backend to switch to; omit to list backends.")
    parser.add_argument(
        "--download", action="store_true",
        help="Then download its latest state and wiring from IQCC cloud (overwrites the local state).",
    )
    args = parser.parse_args()
    if args.backend is None:
        print(qualibrate("project", "list").stdout.strip())
        print(qualibrate("project", "current").stdout.strip())
        sys.exit(0)
    switch_backend(args.backend)
    if args.download:
        from download_state_and_wiring import download_state_and_wiring

        download_state_and_wiring(args.backend)
