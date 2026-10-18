# /// script
# requires-python = ">=3.12,<=3.13"
# dependencies = ["copier"]
# ///
"""
iqcc_setup.py

Renders an iqcc-starter checkout via copier -- no credentials required, since
the template lives in the public i-qcc/iqcc-starter repo. Prompts for
'backend' interactively (see prompt_backend()) and derives 'hardware' from it
via BACKEND_TO_HARDWARE -- each backend only ever runs on one hardware
architecture, so 'hardware' is never asked for directly. The 'os' choice is
likewise not baked in -- it's auto-detected on the machine this script
actually runs on (see detect_os()), so this same iqcc_setup.py works whether
you're on unix or windows. Then runs that checkout's install.py.

Meant to be run straight from the published copy, with no local checkout of
anything:

    uv run https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_setup.py

...or, if you already have a local copy of it:

    uv run iqcc_setup.py [dest_dir]

Destination defaults to ./iqcc-workspace; a positional argument overrides it.
If that destination already exists and is non-empty, this script tells you to
run 'copier update' inside it instead of rendering over it.
"""

# Manual equivalent, if you ever need to run copier yourself instead of this
# script (e.g. to debug a failed render or tweak a flag) -- pick backend/
# hardware/os to match your machine:
#
#   uvx copier copy https://github.com/i-qcc/iqcc-starter.git iqcc-workspace --vcs-ref cloud -d backend=<gilboa|arbel|lucy> -d hardware=<derived from backend> -d os=<unix|windows> -d environment=workstation --trust

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/i-qcc/iqcc-starter.git"
VCS_REF = "cloud"
DEFAULT_DEST = "iqcc-workspace"
BACKEND_TO_HARDWARE = {'gilboa': 'tunable', 'arbel': 'tunable', 'lucy': 'fixed', 'qolab': 'fixed'}

CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def detect_os() -> str:
    # Best-effort: only picks which .vscode/settings.json variant copier
    # renders, not load-bearing for install correctness.
    return "windows" if platform.system() == "Windows" else "unix"


def log(msg: str) -> None:
    print(f"[iqcc-setup] {msg}")


def err(msg: str) -> None:
    print(f"[iqcc-setup][ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def check_prereqs() -> None:
    # 'uv' is assumed present, since 'uv run' is how this script got
    # invoked in the first place, and 'copier' isn't checked here either --
    # the '# /// script' dependency block above makes 'uv run' install it
    # into this script's ephemeral env regardless of what's on PATH.
    if shutil.which("git") is None:
        err("'git' is required but was not found on PATH.")
    log("Found git on PATH.")


def check_existing_dest(dest_dir: Path) -> None:
    if dest_dir.exists() and any(dest_dir.iterdir()):
        err(
            f"'{dest_dir}' already exists and is not empty. To pull in "
            f"template updates, run this instead:\n\n"
            f"    cd {dest_dir} && copier update --trust\n"
        )


def uv_subprocess_env() -> dict[str, str]:
    # 'uv run iqcc_setup.py' sets VIRTUAL_ENV to its own ephemeral script
    # environment. The nested 'uv run install.py' call below should target
    # the newly rendered checkout's own .venv, not that ephemeral env, so
    # drop VIRTUAL_ENV to avoid uv's "does not match the project environment
    # path" mismatch warning.
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    return env


def prompt_backend() -> str:
    choices = list(BACKEND_TO_HARDWARE)
    while True:
        print()
        print(f"{CYAN}{BOLD}┌───────────────────────────────────────────────────┐{RESET}")
        print(f"{CYAN}{BOLD}│  ⚙️  Select backend                                   │{RESET}")
        print(f"{CYAN}{BOLD}└───────────────────────────────────────────────────┘{RESET}")
        for i, choice in enumerate(choices, 1):
            print(f"  {i}) {choice}")
        print()
        raw = input(f"{BOLD}Backend [1-{len(choices)}]:{RESET} ").strip()
        print()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        if raw in choices:
            return raw
        print(f"{YELLOW}Invalid backend '{raw}', try again.{RESET}")


def run_copier_copy(dest_dir: Path, backend: str, hardware: str) -> None:
    os_choice = detect_os()
    log(
        f"Rendering checkout into '{dest_dir}' (backend={backend}, "
        f"hardware={hardware}, os={os_choice} [auto-detected])..."
    )
    copier_cmd = [
        "copier", "copy", REPO_URL, str(dest_dir),
        "--vcs-ref", VCS_REF,
        "-d", f"backend={backend}",
        "-d", f"hardware={hardware}",
        "-d", f"os={os_choice}",
        "-d", "environment=workstation",
        "--trust",
    ]
    try:
        subprocess.run(copier_cmd, check=True)
    except subprocess.CalledProcessError as exc:
        err(f"'copier copy' failed with exit code {exc.returncode}.")


def run_install(dest_dir: Path) -> None:
    log(f"Running install.py inside '{dest_dir}'...")
    try:
        subprocess.run(
            ["uv", "run", "install.py"],
            cwd=dest_dir, check=True, env=uv_subprocess_env(),
        )
    except subprocess.CalledProcessError as exc:
        err(f"'uv run install.py' failed with exit code {exc.returncode}.")


def main() -> None:
    check_prereqs()
    dest_dir = Path.cwd() / (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DEST)
    check_existing_dest(dest_dir)
    backend = prompt_backend()
    hardware = BACKEND_TO_HARDWARE[backend]
    log(f"Selected backend={backend} -> hardware={hardware} (derived).")
    run_copier_copy(dest_dir, backend, hardware)
    run_install(dest_dir)
    log(f"Done. Checkout ready at {dest_dir}")


if __name__ == "__main__":
    main()
