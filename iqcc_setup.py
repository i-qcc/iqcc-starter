# /// script
# requires-python = ">=3.12,<=3.13"
# dependencies = ["copier"]
# ///
"""
iqcc_setup.py

Renders an iqcc-starter checkout via copier -- no credentials required, since
the template lives in the public i-qcc/iqcc-starter repo. A checkout holds one
qualibrate project per backend and the calibration nodes for the hardware of
those backends (the common nodes always, plus fixed-frequency and/or
flux-tunable ones). This script asks which backends to set up (see
prompt_backends(); several can be picked), derives the hardware layers they need
(see hardware_layers_for()) for the render, and passes the backends to the
checkout's install.py, which creates the projects. The 'os' choice is
auto-detected on the machine this script actually runs on (see detect_os()), so
this same iqcc_setup.py works whether you're on unix or windows. A backend
whose hardware the checkout already has can be added later with
'uv run install.py --backend <name>'; one that needs more nodes is added with
'uv run iqcc_setup.py --update --backend <name>' (see below).

Meant to be run straight from the published copy, with no local checkout of
anything:

    uv run https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_setup.py

...or, if you already have a local copy of it:

    uv run iqcc_setup.py [dest_dir]

Destination defaults to ./iqcc-workspace; a positional argument overrides it.
Non-interactive use: '--backend <name>' (repeatable) skips the backend
prompt, and the IQCC API tokens are passed to install.py via environment
variables (IQCC_API_TOKEN_<BACKEND>, or IQCC_API_TOKEN for a single backend). '--template' and '--vcs-ref' choose the template source (default:
this repo's 'cloud' branch; e.g. a local clone with '--vcs-ref HEAD').
If the destination is already a rendered checkout, rendering is skipped and
install.py is re-run (with the '--backend' choices, if any). If it exists, is non-empty and is not a rendered
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
template source recorded in .copier-answers.yml is used. '--backend <name>'
(repeatable) also adds backends in this mode: the hardware layers are widened if
those backends need nodes the checkout lacks (the answers file records them),
and install.py then sets the new backends up, token and state download
included. A checkout rendered
when a checkout held a single backend is migrated on the way: its backend
(read from .copier-answers.yml before the update) becomes a qualibrate
project, keeping its state, data and token (install.py --migrate-from).
"""

# Manual equivalent, if you ever need to run copier yourself instead of this
# script (e.g. to debug a failed render or tweak a flag) -- pick os to match
# your machine and the backends you need:
#
#   uvx copier copy https://github.com/i-qcc/iqcc-starter.git iqcc-workspace --vcs-ref cloud -d os=<unix|windows> -d environment=workstation -d hardware_layers=<fixed_freq,tunable_transmon,tunable_coupler subset> --trust
#   cd iqcc-workspace && git init && git add -A && git commit -m "Initial render"
#   uv run install.py --backend <gilboa|arbel|qolab|lucy|meiron> [--backend ...] && git add -A && git commit -m "Initial install"

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
# Keep identical to iqcc_learn_setup.py and config/quam_builder/__init__.py.jinja. Here
# the keys are the backend choices and the values pick which hardware layers of nodes to render;
# the checkout itself maps backend -> QUAM class.
BACKEND_TO_HARDWARE = {'gilboa': 'tunable_transmon', 'arbel': 'tunable_transmon', 'qolab': 'tunable_transmon', 'lucy': 'fixed_freq', 'meiron': 'tunable_coupler'}
# Canonical order of copier's `hardware_layers` values.
HARDWARE_LAYERS = ("fixed_freq", "tunable_transmon", "tunable_coupler")

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


def prompt_backends() -> list[str]:
    choices = list(BACKEND_TO_HARDWARE)
    while True:
        print()
        print(f"{CYAN}{BOLD}┌───────────────────────────────────────────────────┐{RESET}")
        print(f"{CYAN}{BOLD}│  ⚙️  Select backends                                  │{RESET}")
        print(f"{CYAN}{BOLD}└───────────────────────────────────────────────────┘{RESET}")
        for i, choice in enumerate(choices, 1):
            print(f"  {i}) {choice}")
        print(f"{YELLOW}Pick one or more, separated by spaces or commas (e.g. '1 4').{RESET}")
        print()
        raw = input(f"{BOLD}Backends:{RESET} ")
        print()
        picked: list[str] = []
        bad: list[str] = []
        for item in raw.replace(",", " ").split():
            if item.isdigit() and 1 <= int(item) <= len(choices):
                item = choices[int(item) - 1]
            if item in choices:
                if item not in picked:
                    picked.append(item)
            else:
                bad.append(item)
        if picked and not bad:
            return picked
        print(f"{YELLOW}Invalid selection '{raw.strip()}', try again.{RESET}")


def hardware_layers_for(backends: list[str]) -> list[str]:
    # The node layers a set of backends needs, in canonical order, as copier's
    # `hardware_layers` value. Copier adds tunable_transmon under tunable_coupler.
    needed = {BACKEND_TO_HARDWARE[b] for b in backends}
    return [layer for layer in HARDWARE_LAYERS if layer in needed]


def existing_projects(dest_dir: Path) -> list[str]:
    # Backends that already have a (non-empty) qualibrate project in the checkout.
    projects = dest_dir / "config" / "qualibrate" / "projects"
    if not projects.is_dir():
        return []
    return sorted(
        p.name for p in projects.iterdir()
        if p.name in BACKEND_TO_HARDWARE
        and (p / "config.toml").is_file() and (p / "config.toml").read_text().strip()
    )


def checkout_layers(dest_dir: Path, migrate_from: Optional[str]) -> list[str]:
    # The layers a checkout needs today: what its answers file records
    # (`hardware_layers`, or the single `hardware` of an older checkout), plus
    # those of its backends. Read before 'copier update' changes the answers.
    answers = (dest_dir / ".copier-answers.yml").read_text()
    layers: set[str] = set()
    match = re.search(r"^hardware_layers:\s*(\S+)", answers, re.MULTILINE)
    if match:
        layers.update(match.group(1).strip("'\"").split(","))
    match = re.search(r"^hardware:\s*(\S+)", answers, re.MULTILINE)
    if match:
        layers.add(match.group(1).strip("'\""))
    backends = existing_projects(dest_dir) + ([migrate_from] if migrate_from else [])
    layers.update(BACKEND_TO_HARDWARE[b] for b in backends)
    return [layer for layer in HARDWARE_LAYERS if layer in layers]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render and install an iqcc-starter checkout.")
    parser.add_argument("dest_dir", nargs="?", default=DEFAULT_DEST)
    parser.add_argument(
        "--backend", action="append", choices=list(BACKEND_TO_HARDWARE), default=[],
        help="Backend to set up (repeatable). Skips the prompt; with --update, adds "
        "the backend (widening the rendered node set if its hardware needs it).",
    )
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


def run_copier_copy(dest_dir: Path, template: str, vcs_ref: str, layers: list[str]) -> None:
    os_choice = detect_os()
    log(f"Rendering checkout into '{dest_dir}' (os={os_choice} [auto-detected], nodes: {', '.join(layers)})...")
    copier_cmd = [
        "copier", "copy", template, str(dest_dir),
        "--vcs-ref", vcs_ref,
        "-d", f"os={os_choice}",
        "-d", "environment=workstation",
        "-d", f"hardware_layers={','.join(layers)}",
        "--trust",
    ]
    try:
        subprocess.run(copier_cmd, check=True)
    except subprocess.CalledProcessError as exc:
        err(f"'copier copy' failed with exit code {exc.returncode}.")


def run_copier_update(dest_dir: Path, vcs_ref: Optional[str], layers: list[str]) -> None:
    # Re-applies the template at vcs_ref (default: copier picks the newest
    # tagged version) on top of the user's edits (3-way merge against the
    # version recorded in .copier-answers.yml). Previous answers are kept;
    # overlapping edits are left as inline conflict markers.
    log(f"Updating '{dest_dir}' to template version '{vcs_ref or 'latest'}'...")
    copier_cmd = [
        "copier", "update", str(dest_dir),
        *(["--vcs-ref", vcs_ref] if vcs_ref else []),
        "-d", f"hardware_layers={','.join(layers)}",
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


def run_install(
    dest_dir: Path,
    backends: list[str],
    iqcc_setup: bool = True,
    migrate_from: Optional[str] = None,
) -> None:
    log(f"Running install.py inside '{dest_dir}'...")
    cmd = ["uv", "run", "install.py"]
    for backend in backends:
        cmd += ["--backend", backend]
    if migrate_from:
        cmd += ["--migrate-from", migrate_from]
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


def legacy_backend(dest_dir: Path) -> Optional[str]:
    # A checkout rendered when a checkout held a single backend recorded it in
    # .copier-answers.yml (and pyproject.toml's [tool.iqcc] project-name). Read
    # it before 'copier update' drops both.
    answers = (dest_dir / ".copier-answers.yml").read_text()
    match = re.search(r"^backend:\s*(\S+)", answers, re.MULTILINE)
    if match:
        return match.group(1).strip("'\"")
    match = re.search(
        r"^project-name\s*=\s*\"([^\"]+)\"",
        (dest_dir / "pyproject.toml").read_text(),
        re.MULTILINE,
    )
    return match.group(1) if match else None


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


def update_checkout(dest_dir: Path, vcs_ref: Optional[str], add_backends: list[str]) -> None:
    if not is_rendered_checkout(dest_dir):
        err(f"'{dest_dir}' is not a rendered iqcc-starter checkout, so there is nothing to update.")
    # copier update needs a clean tree; this commit is also the restore point.
    git_commit_all(dest_dir, "Before template update")
    migrate_from = legacy_backend(dest_dir)
    if migrate_from:
        log(f"Single-backend checkout ('{migrate_from}'): it becomes qualibrate project '{migrate_from}'.")
    # Backends to add: not yet projects (an existing one keeps its local state).
    configured = existing_projects(dest_dir)
    new_backends = [b for b in add_backends if b not in configured and b != migrate_from]
    layers = checkout_layers(dest_dir, migrate_from)
    for backend in new_backends:
        if BACKEND_TO_HARDWARE[backend] not in layers:
            layers.append(BACKEND_TO_HARDWARE[backend])
            log(f"Backend '{backend}' needs the '{BACKEND_TO_HARDWARE[backend]}' nodes; adding them.")
    layers = [layer for layer in HARDWARE_LAYERS if layer in layers]
    run_copier_update(dest_dir, vcs_ref, layers)
    # copier leaves overlapping edits as inline conflict markers; never run
    # install.py on, or commit, files that still contain them.
    conflicted = find_conflict_files(dest_dir)
    if conflicted:
        err(
            "'copier update' left merge conflicts in:\n  "
            + "\n  ".join(conflicted)
            + "\nResolve the <<<<<<< / ======= / >>>>>>> markers, then run "
            f"'uv run install.py --no-iqcc-setup{f' --migrate-from {migrate_from}' if migrate_from else ''}'"
            f"{''.join(f' and then uv run install.py --backend {b}' for b in new_backends)}, "
            "'git add -A' and commit "
            "(nothing was installed or committed). To abandon the update: "
            "'git reset --hard HEAD && git clean -fd' (restores the pre-update commit)."
        )
    # The token and QPU state are already set up; install.py only needs to
    # sync dependencies and qualibrate config for the new template version.
    run_install(dest_dir, [], iqcc_setup=False, migrate_from=migrate_from)
    if new_backends:
        # Only the new backends: they get the token / state-download step, the
        # existing ones are left alone.
        run_install(dest_dir, new_backends)
    version = template_version(dest_dir)
    message = f"Update iqcc-starter template to {version}"
    if new_backends:
        message += f" (added backends: {', '.join(new_backends)})"
    if migrate_from:
        message += f" (migrated to multi-backend: '{migrate_from}' is now a qualibrate project)"
    git_commit_all(dest_dir, message)
    log(f"Done. Checkout at {dest_dir} updated to {version}")


def main() -> None:
    args = parse_args()
    check_prereqs()
    dest_dir = Path.cwd() / args.dest_dir
    if args.update:
        update_checkout(dest_dir, args.vcs_ref, args.backend)
        return
    if is_rendered_checkout(dest_dir):
        log(f"'{dest_dir}' is already rendered -- skipping render, re-running install.py.")
    else:
        check_existing_dest(dest_dir)
        if not args.backend:
            args.backend = prompt_backends()
        log(f"Selected backends: {', '.join(args.backend)}.")
        run_copier_copy(dest_dir, args.template, args.vcs_ref or VCS_REF, hardware_layers_for(args.backend))
        init_git_repo(dest_dir)
    run_install(dest_dir, args.backend)
    git_commit_all(dest_dir, "Initial install: qualibrate config and QUAM state")
    log(f"Done. Checkout ready at {dest_dir}")


if __name__ == "__main__":
    main()
