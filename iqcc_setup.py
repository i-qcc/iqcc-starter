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
Non-interactive use: '--backend <name>' skips the backend prompt, and the
IQCC API token is passed to install.py via the IQCC_API_TOKEN environment
variable. '--template' and '--vcs-ref' choose the template source (default:
this repo's 'cloud' branch; e.g. a local clone with '--vcs-ref HEAD').
If the destination is already a rendered checkout, rendering is skipped and
install.py is re-run. If it exists, is non-empty and is not a rendered
checkout, this script tells you to run 'copier update' inside it instead of
rendering over it. The rendered
checkout is git-initialised and committed (before and after install.py), so
'uvx copier update --trust --skip-answered' works in it straight away.

'--update' updates an existing checkout instead (to '--vcs-ref'; default: the
newest tagged template version, i.e. the latest published snapshot): it commits
any local changes, runs 'copier update' (user edits are kept; overlapping
edits become inline conflict markers), re-runs install.py with
'--no-iqcc-setup' (no token step, local state untouched), and commits the
result. If copier left conflict markers, it stops before install/commit and
lists the conflicted files. '--template' is ignored in this mode; the
template source recorded in .copier-answers.yml is used.
"""

# Manual equivalent, if you ever need to run copier yourself instead of this
# script (e.g. to debug a failed render or tweak a flag) -- pick backend/
# hardware/os to match your machine:
#
#   uvx copier copy https://github.com/i-qcc/iqcc-starter.git iqcc-workspace --vcs-ref cloud -d backend=<gilboa|arbel|qolab|lucy|meiron> -d hardware=<derived from backend> -d os=<unix|windows> -d environment=workstation --trust
#   cd iqcc-workspace && git init && git add -A && git commit -m "Initial render"
#   uv run install.py && git add -A && git commit -m "Initial install"

import argparse
import re
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_URL = "https://github.com/i-qcc/iqcc-starter.git"
VCS_REF = "cloud"
DEFAULT_DEST = "iqcc-workspace"
# hardware: fixed_freq = fixed-frequency transmons; tunable_transmon = flux-tunable transmons,
# fixed couplers; tunable_coupler = flux-tunable transmons and tunable couplers.
BACKEND_TO_HARDWARE = {'gilboa': 'tunable_transmon', 'arbel': 'tunable_transmon', 'qolab': 'tunable_transmon', 'lucy': 'fixed_freq', 'meiron': 'tunable_coupler'}

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
            f"    cd {dest_dir} && uvx copier update --trust --skip-answered\n"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render and install an iqcc-starter checkout.")
    parser.add_argument("dest_dir", nargs="?", default=DEFAULT_DEST)
    parser.add_argument("--backend", choices=list(BACKEND_TO_HARDWARE))
    parser.add_argument("--template", default=REPO_URL)
    parser.add_argument(
        "--vcs-ref", default=None,
        help=f"Template branch/tag. Default: '{VCS_REF}' for a fresh render; "
        "the newest tagged version for --update.",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Update an existing checkout via 'copier update' (to --vcs-ref, "
        "default: the newest tagged template version), then re-run install.py.",
    )
    return parser.parse_args()


def is_rendered_checkout(dest_dir: Path) -> bool:
    return (dest_dir / ".copier-answers.yml").is_file()


def run_copier_copy(
    dest_dir: Path, backend: str, hardware: str, template: str, vcs_ref: str
) -> None:
    os_choice = detect_os()
    log(
        f"Rendering checkout into '{dest_dir}' (backend={backend}, "
        f"hardware={hardware}, os={os_choice} [auto-detected])..."
    )
    copier_cmd = [
        "copier", "copy", template, str(dest_dir),
        "--vcs-ref", vcs_ref,
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


def run_copier_update(dest_dir: Path, vcs_ref: Optional[str]) -> None:
    # Re-applies the template at vcs_ref (default: copier picks the newest
    # tagged version) on top of the user's edits (3-way merge against the
    # version recorded in .copier-answers.yml). Previous answers are kept;
    # overlapping edits are left as inline conflict markers.
    log(f"Updating '{dest_dir}' to template version '{vcs_ref or 'latest'}'...")
    copier_cmd = [
        "copier", "update", str(dest_dir),
        *(["--vcs-ref", vcs_ref] if vcs_ref else []),
        "--skip-answered",
        "--defaults",
        "--conflict", "inline",
        "--trust",
    ]
    try:
        subprocess.run(copier_cmd, check=True)
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


def run_install(dest_dir: Path, iqcc_setup: bool = True) -> None:
    log(f"Running install.py inside '{dest_dir}'...")
    cmd = ["uv", "run", "install.py"]
    stdin = None
    if not iqcc_setup:
        # Skip the token / state-download step entirely (and never prompt).
        cmd.append("--no-iqcc-setup")
        stdin = subprocess.DEVNULL
    try:
        subprocess.run(
            cmd, cwd=dest_dir, check=True, env=uv_subprocess_env(), stdin=stdin,
        )
    except subprocess.CalledProcessError as exc:
        err(f"'uv run install.py' failed with exit code {exc.returncode}.")


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


def update_checkout(dest_dir: Path, vcs_ref: Optional[str]) -> None:
    if not is_rendered_checkout(dest_dir):
        err(f"'{dest_dir}' is not a rendered iqcc-starter checkout, so there is nothing to update.")
    # copier update needs a clean tree; this commit is also the restore point.
    git_commit_all(dest_dir, "Before template update")
    run_copier_update(dest_dir, vcs_ref)
    # copier leaves overlapping edits as inline conflict markers; never run
    # install.py on, or commit, files that still contain them.
    conflicted = find_conflict_files(dest_dir)
    if conflicted:
        err(
            "'copier update' left merge conflicts in:\n  "
            + "\n  ".join(conflicted)
            + "\nResolve the <<<<<<< / ======= / >>>>>>> markers, then run "
            "'uv run install.py --no-iqcc-setup', 'git add -A' and commit "
            "(nothing was installed or committed). To abandon the update: "
            "'git reset --hard HEAD && git clean -fd' (restores the pre-update commit)."
        )
    # The token and QPU state are already set up; install.py only needs to
    # sync dependencies and qualibrate config for the new template version.
    run_install(dest_dir, iqcc_setup=False)
    version = template_version(dest_dir)
    git_commit_all(dest_dir, f"Update iqcc-starter template to {version}")
    log(f"Done. Checkout at {dest_dir} updated to {version}")


def main() -> None:
    args = parse_args()
    check_prereqs()
    dest_dir = Path.cwd() / args.dest_dir
    if args.update:
        update_checkout(dest_dir, args.vcs_ref)
        return
    if is_rendered_checkout(dest_dir):
        log(f"'{dest_dir}' is already rendered -- skipping render, re-running install.py.")
    else:
        check_existing_dest(dest_dir)
        backend = args.backend
        if backend is None:
            backend = prompt_backend()
        hardware = BACKEND_TO_HARDWARE[backend]
        log(f"Selected backend={backend} -> hardware={hardware} (derived).")
        run_copier_copy(dest_dir, backend, hardware, args.template, args.vcs_ref or VCS_REF)
        init_git_repo(dest_dir)
    run_install(dest_dir)
    git_commit_all(dest_dir, "Initial install: qualibrate config and QUAM state")
    log(f"Done. Checkout ready at {dest_dir}")


if __name__ == "__main__":
    main()
