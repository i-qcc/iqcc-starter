# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
iqcc_learn_setup.py

One-command setup for the IQCC Learn JupyterLab environment. Renders an
iqcc-starter checkout (environment=learn) into ./iqcc-workspace via 'uvx
copier', then runs that checkout's learn_setup.py, which creates the working
folders, installs the import hook, configures qualibrate and downloads the
latest QUAM state and wiring. Prompts for 'backend' and derives 'hardware'
from it via BACKEND_TO_HARDWARE.

Learn has no curl, so run it with the terminal's own Python:

    python -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_learn_setup.py').read())"

...or, if uv is available and you prefer it:

    uv run https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_learn_setup.py

The destination is always ./iqcc-workspace (the rendered nodes reference that
folder name). If it already exists, delete it first or use 'copier update'.
The checkout is git-initialised and committed (before and after
learn_setup.py), so 'uvx copier update --trust --skip-answered' works in it straight away.
"""

# Manual equivalent:
#
#   uvx copier copy https://github.com/i-qcc/iqcc-starter.git iqcc-workspace --vcs-ref cloud -d backend=<backend> -d hardware=<derived from backend> -d os=unix -d environment=learn --trust
#   cd iqcc-workspace && git init && git add -A && git commit -m "Initial render" && cd ..
#   python iqcc-workspace/learn_setup.py
#   cd iqcc-workspace && git add -A && git commit -m "Initial install"

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/i-qcc/iqcc-starter.git"
VCS_REF = "cloud"
DEST_NAME = "iqcc-workspace"
BACKEND_TO_HARDWARE = {'gilboa': 'tunable', 'arbel': 'tunable', 'lucy': 'fixed', 'qolab': 'fixed'}

CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def log(msg: str) -> None:
    print(f"[iqcc-learn-setup] {msg}")


def err(msg: str) -> None:
    print(f"[iqcc-learn-setup][ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def subprocess_env() -> dict:
    # Under 'uv run' VIRTUAL_ENV points at uv's ephemeral script env; nested
    # 'uvx' calls should not inherit it.
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    return env


def target_python() -> str:
    # learn_setup.py must run with the Python the notebooks/terminal use,
    # since it writes the .pth hook into that interpreter's site-packages.
    # 'python -c' / 'python -' gives us that as sys.executable; under
    # 'uv run' it is uv's ephemeral env, so look the real one up on PATH.
    venv = os.environ.get("VIRTUAL_ENV")
    if not venv:
        return sys.executable
    venv_bin = str(Path(venv) / "bin")
    clean_path = os.pathsep.join(
        p for p in os.environ.get("PATH", "").split(os.pathsep) if p != venv_bin
    )
    for name in ("python3", "python"):
        found = shutil.which(name, path=clean_path)
        if found:
            return found
    err("Could not find a system 'python' on PATH outside uv's temporary environment.")


def check_prereqs() -> None:
    for tool in ("uv", "git"):
        if shutil.which(tool) is None:
            err(f"'{tool}' is required but was not found on PATH.")
    log("Found uv and git on PATH.")


def check_existing_dest(dest_dir: Path) -> None:
    if dest_dir.exists() and any(dest_dir.iterdir()):
        err(
            f"'{dest_dir}' already exists and is not empty. Delete it to start "
            f"fresh:\n\n    rm -rf {dest_dir}\n\n"
            f"...or pull in template updates with:\n\n"
            f"    cd {dest_dir} && uvx copier update --trust --skip-answered\n"
        )


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
    log(f"Rendering checkout into '{dest_dir}' (backend={backend}, hardware={hardware})...")
    copier_cmd = [
        "uvx", "copier", "copy", REPO_URL, str(dest_dir),
        "--vcs-ref", VCS_REF,
        "-d", f"backend={backend}",
        "-d", f"hardware={hardware}",
        "-d", "os=unix",
        "-d", "environment=learn",
        "--trust",
    ]
    try:
        subprocess.run(copier_cmd, check=True, env=subprocess_env())
    except subprocess.CalledProcessError as exc:
        err(f"'copier copy' failed with exit code {exc.returncode}.")


def git_commit_all(dest_dir: Path, message: str) -> None:
    # Stage everything and commit; no-op when the tree is already clean.
    # Falls back to a throwaway identity (for this one commit only, never
    # written to git config) when the machine has none configured.
    def git(*args: str, **kw):
        return subprocess.run(["git", *args], cwd=dest_dir, **kw)

    try:
        git("add", "-A", check=True)
        status = git("status", "--porcelain", check=True, capture_output=True, text=True)
        if not status.stdout.strip():
            return
        identity = git("config", "user.email", capture_output=True, text=True)
        fallback = (
            [] if identity.stdout.strip()
            else ["-c", "user.name=iqcc-setup", "-c", "user.email=iqcc-setup@localhost"]
        )
        git(*fallback, "commit", "-q", "-m", message, check=True)
    except subprocess.CalledProcessError as exc:
        err(f"git failed with exit code {exc.returncode}.")


def init_git_repo(dest_dir: Path) -> None:
    # 'copier update' only works on a git-tracked project with a clean tree.
    log("Initialising git repository...")
    try:
        subprocess.run(["git", "init", "-q"], cwd=dest_dir, check=True)
    except subprocess.CalledProcessError as exc:
        err(f"'git init' failed with exit code {exc.returncode}.")
    git_commit_all(dest_dir, "Initial render of iqcc-starter template")


def run_learn_setup(dest_dir: Path) -> None:
    python = target_python()
    log(f"Running learn_setup.py with {python}...")
    try:
        subprocess.run([python, str(dest_dir / "learn_setup.py")], check=True, env=subprocess_env())
    except subprocess.CalledProcessError as exc:
        err(f"learn_setup.py failed with exit code {exc.returncode}.")


def main() -> None:
    check_prereqs()
    dest_dir = Path.cwd() / DEST_NAME
    check_existing_dest(dest_dir)
    backend = prompt_backend()
    hardware = BACKEND_TO_HARDWARE[backend]
    log(f"Selected backend={backend} -> hardware={hardware} (derived).")
    run_copier_copy(dest_dir, backend, hardware)
    init_git_repo(dest_dir)
    run_learn_setup(dest_dir)
    git_commit_all(dest_dir, "Initial install: qualibrate config and QUAM state")
    log(f"Done. Checkout ready at {dest_dir}")


main()
