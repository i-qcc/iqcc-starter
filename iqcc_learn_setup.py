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
latest QUAM state and wiring. Prompts for 'backend' (or take '--backend
<name>') and derives 'hardware' from it via BACKEND_TO_HARDWARE.

Learn has no curl, so run it with the terminal's own Python:

    python -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_learn_setup.py').read())"

...or, if uv is available and you prefer it:

    uv run https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_learn_setup.py

Options go after the command (e.g. '... .read())" --backend gilboa' with the
python one-liner, or 'uv run <url> --backend gilboa'): '--backend <name>',
'--template' / '--vcs-ref' (default: this repo's 'cloud' branch), and
'--update'.

The destination is always ./iqcc-workspace (the rendered nodes reference that
folder name). If it is already a rendered checkout, rendering is skipped and
learn_setup.py is re-run. If it exists, is non-empty and is not a rendered
checkout, delete it first. The checkout is git-initialised and committed
(before and after learn_setup.py), so 'uvx copier update --trust
--skip-answered' works in it straight away.

'--update' updates the existing checkout instead (to '--vcs-ref'; default: the
newest tagged template version): it commits any local changes, runs 'copier
update' (user edits are kept; overlapping edits become inline conflict
markers), re-runs learn_setup.py with '--no-iqcc-setup' (local state
untouched) and commits the result. If copier left conflict markers it stops
before install/commit and lists the conflicted files.
"""

# Manual equivalent:
#
#   uvx copier copy https://github.com/i-qcc/iqcc-starter.git iqcc-workspace --vcs-ref cloud -d backend=<backend> -d hardware=<derived from backend> -d os=unix -d environment=learn --trust
#   cd iqcc-workspace && git init && git add -A && git commit -m "Initial render" && cd ..
#   python iqcc-workspace/learn_setup.py
#   cd iqcc-workspace && git add -A && git commit -m "Initial install"

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_URL = "https://github.com/i-qcc/iqcc-starter.git"
VCS_REF = "cloud"
DEST_NAME = "iqcc-workspace"
# hardware: fixed_freq = fixed-frequency transmons; tunable_transmon = flux-tunable transmons,
# fixed couplers; tunable_coupler = flux-tunable transmons and tunable couplers.
BACKEND_TO_HARDWARE = {'gilboa': 'tunable_transmon', 'arbel': 'tunable_transmon', 'qolab': 'tunable_transmon', 'lucy': 'fixed_freq', 'meiron': 'tunable_coupler'}

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
            f"...or, if it is a rendered checkout, re-run this script with --update.\n"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render and set up an iqcc-starter checkout on IQCC Learn.")
    parser.add_argument("--backend", choices=list(BACKEND_TO_HARDWARE))
    parser.add_argument("--template", default=REPO_URL)
    parser.add_argument(
        "--vcs-ref", default=None,
        help=f"Template branch/tag. Default: '{VCS_REF}' for a fresh render; "
        "the newest tagged version for --update.",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Update the existing checkout via 'copier update' (to --vcs-ref, "
        "default: the newest tagged template version), then re-run learn_setup.py.",
    )
    return parser.parse_args()


def is_rendered_checkout(dest_dir: Path) -> bool:
    return (dest_dir / ".copier-answers.yml").is_file()


def run_copier_copy(dest_dir: Path, backend: str, hardware: str, template: str, vcs_ref: str) -> None:
    log(f"Rendering checkout into '{dest_dir}' (backend={backend}, hardware={hardware})...")
    copier_cmd = [
        "uvx", "copier", "copy", template, str(dest_dir),
        "--vcs-ref", vcs_ref,
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


def run_copier_update(dest_dir: Path, vcs_ref: Optional[str]) -> None:
    # Re-applies the template at vcs_ref (default: copier picks the newest
    # tagged version) on top of the user's edits (3-way merge against the
    # version recorded in .copier-answers.yml). Previous answers are kept;
    # overlapping edits are left as inline conflict markers.
    log(f"Updating '{dest_dir}' to template version '{vcs_ref or 'latest'}'...")
    copier_cmd = [
        "uvx", "copier", "update", str(dest_dir),
        *(["--vcs-ref", vcs_ref] if vcs_ref else []),
        "--skip-answered",
        "--defaults",
        "--conflict", "inline",
        "--trust",
    ]
    try:
        subprocess.run(copier_cmd, check=True, env=subprocess_env())
    except subprocess.CalledProcessError as exc:
        err(f"'copier update' failed with exit code {exc.returncode}.")


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


def find_conflict_files(dest_dir: Path) -> list[str]:
    # Tracked and new (non-ignored) files in the working tree containing
    # copier's inline conflict markers at the start of a line.
    result = subprocess.run(
        ["git", "grep", "-l", "-I", "--untracked", "--exclude-standard",
         "-E", "^(<<<<<<<|>>>>>>>) ", "--", "."],
        cwd=dest_dir, capture_output=True, text=True,
    )
    return result.stdout.split()


def template_version(dest_dir: Path) -> str:
    # The version copier recorded in .copier-answers.yml after a copy/update.
    answers = (dest_dir / ".copier-answers.yml").read_text()
    match = re.search(r"^_commit:\s*(\S+)", answers, re.MULTILINE)
    return match.group(1) if match else "unknown"


def run_learn_setup(dest_dir: Path, iqcc_setup: bool = True) -> None:
    python = target_python()
    log(f"Running learn_setup.py with {python}...")
    cmd = [python, str(dest_dir / "learn_setup.py")]
    if not iqcc_setup:
        # Skip the IQCC cloud check / state download (local state untouched).
        cmd.append("--no-iqcc-setup")
    try:
        subprocess.run(cmd, check=True, env=subprocess_env())
    except subprocess.CalledProcessError as exc:
        err(f"learn_setup.py failed with exit code {exc.returncode}.")


def update_checkout(dest_dir: Path, vcs_ref: Optional[str]) -> None:
    if not is_rendered_checkout(dest_dir):
        err(f"'{dest_dir}' is not a rendered iqcc-starter checkout, so there is nothing to update.")
    # copier update needs a clean tree; this commit is also the restore point.
    git_commit_all(dest_dir, "Before template update")
    run_copier_update(dest_dir, vcs_ref)
    # copier leaves overlapping edits as inline conflict markers; never run
    # learn_setup.py on, or commit, files that still contain them.
    conflicted = find_conflict_files(dest_dir)
    if conflicted:
        err(
            "'copier update' left merge conflicts in:\n  "
            + "\n  ".join(conflicted)
            + "\nResolve the <<<<<<< / ======= / >>>>>>> markers, then run "
            "'python learn_setup.py --no-iqcc-setup', 'git add -A' and commit "
            "(nothing was installed or committed). To abandon the update: "
            "'git reset --hard HEAD && git clean -fd' (restores the pre-update commit)."
        )
    # State is already downloaded; only refresh the import hook / qualibrate config.
    run_learn_setup(dest_dir, iqcc_setup=False)
    version = template_version(dest_dir)
    git_commit_all(dest_dir, f"Update iqcc-starter template to {version}")
    log(f"Done. Checkout at {dest_dir} updated to {version}")


def main() -> None:
    args = parse_args()
    check_prereqs()
    dest_dir = Path.cwd() / DEST_NAME
    if args.update:
        update_checkout(dest_dir, args.vcs_ref)
        return
    if is_rendered_checkout(dest_dir):
        log(f"'{dest_dir}' is already rendered -- skipping render, re-running learn_setup.py.")
    else:
        check_existing_dest(dest_dir)
        backend = args.backend
        if backend is None:
            backend = prompt_backend()
        hardware = BACKEND_TO_HARDWARE[backend]
        log(f"Selected backend={backend} -> hardware={hardware} (derived).")
        run_copier_copy(dest_dir, backend, hardware, args.template, args.vcs_ref or VCS_REF)
        init_git_repo(dest_dir)
    run_learn_setup(dest_dir)
    git_commit_all(dest_dir, "Initial install: qualibrate config and QUAM state")
    log(f"Done. Checkout ready at {dest_dir}")


main()
