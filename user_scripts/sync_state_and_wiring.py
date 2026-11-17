"""Three-way sync of the local QuAM state with the latest IQCC cloud state.

``state.json`` is merged value by value from three versions:

* base  - the cloud dataset the local files were downloaded from (ID in ``<state folder>/.sync_base/``),
* local - the current ``state.json`` in the active Qualibrate project's state folder,
* cloud - the latest state on the IQCC cloud.

Per value: only cloud changed -> cloud; both changed differently -> conflict (asked); only local
changed -> asked as well (default answer: the cloud value). ``wiring.json`` is never merged, it is
copied from the cloud.

Pins (``--keep`` patterns and the ``.sync_keep`` file) force a path to stay local without asking.
``--keep-local-changes`` keeps values that only changed locally silently instead of asking.

The backend must be the active qualibrate project (default: the active project itself); switch
first with ``switch_backend.py <backend>``. Pins go in ``.sync_keep`` at the checkout root.

Usage (dry run is the default, nothing is written without ``--apply``)::

    uv run sync_state_and_wiring [backend]
    ... --diff                 # open cloud-vs-merged diff in VS Code, write nothing
    ... --apply                # asks about every unpinned change (Enter = cloud value)
    ... --apply --keep-local-changes   # silently keep values only changed locally
    ... --apply --keep 'qubits/*/resonator/operations/readout_drachma' --prefer cloud
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # as the `user_scripts` package (the `uv run sync_state_and_wiring` entry point)
    from .sync_base import BASE_DIRNAME, write_sync_base
except ImportError:  # run as a plain script: python user_scripts/sync_state_and_wiring.py
    from sync_base import BASE_DIRNAME, write_sync_base

logger = logging.getLogger(__name__)

BACKUP_DIRNAME = ".sync_backup"
KEEP_FILENAME = ".sync_keep"
FILES = ("state.json", "wiring.json")
REPO_ROOT = Path(__file__).resolve().parents[1]


class _Missing:
    """Sentinel for an absent key (distinct from a JSON null)."""

    def __repr__(self) -> str:
        return "<missing>"


MISSING = _Missing()


@dataclass
class Decision:
    path: str
    kind: str  # "conflict" (both changed) or "local-only" (asked unless --keep-local-changes)
    base: Any
    local: Any
    cloud: Any


def load_keep_patterns(keep_file: Path | None, extra: list[str] | None = None) -> list[str]:
    """Read pin patterns: one per line, ``#`` comments allowed, plus any ``--keep`` flags."""
    patterns: list[str] = []
    if keep_file and keep_file.is_file():
        for line in keep_file.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                patterns.append(line)
    patterns.extend(p.strip("/") for p in (extra or []) if p.strip())
    return patterns


def _pinned(path: str, keep: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pat) for pat in keep)


def merge_trees(
    base: Any,
    local: Any,
    cloud: Any,
    keep: list[str] | None = None,
    safe: bool = False,
    choices: dict[str, str] | None = None,
    prefer: str | None = None,
) -> tuple[Any, list[Decision], list[Decision]]:
    """Three-way merge of JSON trees.

    Returns ``(merged, resolved, pending)``. ``pending`` holds decisions that still need an
    answer (not in ``choices`` and no ``prefer``); their merged value is the cloud value, so the
    result is only safe to write once ``pending`` is empty. ``resolved`` lists every decision
    that was answered. Lists and scalars are compared whole.
    """
    keep = keep or []
    choices = choices or {}
    resolved: list[Decision] = []
    pending: list[Decision] = []

    def decide(path: str, kind: str, b: Any, l: Any, c: Any) -> Any:
        d = Decision(path, kind, b, l, c)
        choice = choices.get(path) or prefer
        if choice is None:
            pending.append(d)
            return c
        resolved.append(d)
        return l if choice == "local" else c

    def rec(b: Any, l: Any, c: Any, path: str) -> Any:
        if path and _pinned(path, keep):
            return l
        if l == c:
            return l
        if isinstance(l, dict) and isinstance(c, dict):
            bd = b if isinstance(b, dict) else {}
            out: dict[str, Any] = {}
            # Keep cloud key order, then keys that exist only locally.
            for k in [*c.keys(), *(k for k in l if k not in c)]:
                sub = f"{path}/{k}" if path else k
                v = rec(bd.get(k, MISSING), l.get(k, MISSING), c.get(k, MISSING), sub)
                if v is not MISSING:
                    out[k] = v
            return out
        # Leaf (or a dict vs non-dict mismatch): decide as a whole.
        if b == c:  # only local changed
            return decide(path, "local-only", b, l, c) if safe else l
        if b == l:  # only cloud changed
            return c
        return decide(path, "conflict", b, l, c)

    return rec(base, local, cloud, ""), resolved, pending


def _short(v: Any, n: int = 70) -> str:
    s = repr(v)
    return s if len(s) <= n else s[: n - 3] + "..."


def _group(path: str) -> str:
    return "/".join(path.split("/")[:3])


def prompt_for(pending: list[Decision], ask: Callable[[str], str] = input) -> dict[str, str]:
    """Ask the user per decision. ``l``/``c`` answer one; ``L``/``C`` answer the whole group
    (same first three path segments); ``s`` or Enter takes the cloud value."""
    choices: dict[str, str] = {}
    group_choice: dict[str, str] = {}
    for d in pending:
        g = _group(d.path)
        if g in group_choice:
            choices[d.path] = group_choice[g]
            continue
        print(f"\n[{d.kind}] {d.path}\n  base : {_short(d.base)}\n  local: {_short(d.local)}\n  cloud: {_short(d.cloud)}")
        while True:
            a = ask("  keep [l]ocal / [c]loud (default) / [L]ocal for all in group / [C]loud for all: ").strip()
            if a in ("", "s", "c", "C", "l", "L"):
                break
        choice = "local" if a in ("l", "L") else "cloud"
        choices[d.path] = choice
        if a in ("L", "C"):
            group_choice[g] = choice
    return choices


def read_base_state(folder: Path, client: Any) -> tuple[Any, str]:
    """Return ``(base_state, source)``: fetched from the cloud by the saved ID, else the cache
    copy, else ``MISSING``."""
    base_dir = folder / BASE_DIRNAME
    meta_file = base_dir / "meta.json"
    if meta_file.is_file():
        state_id = json.loads(meta_file.read_text()).get("state_id")
        if state_id is not None:
            try:
                ds = client.state.get(state_id)
                if ds is not None:
                    return ds.data, f"cloud dataset {state_id}"
            except Exception as e:  # noqa: BLE001 - any fetch problem falls back to the cache
                logger.warning(f"Could not fetch base dataset {state_id} ({e}); using the cached copy")
    cache = base_dir / "state.json"
    if cache.is_file():
        return json.loads(cache.read_text()), "cached copy in .sync_base"
    return MISSING, "none"


def diff_paths(a: Any, b: Any, path: str = "") -> list[str]:
    """Paths of the values that differ between two JSON trees (lists and scalars compared whole)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for k in [*a, *(k for k in b if k not in a)]:
            out += diff_paths(a.get(k, MISSING), b.get(k, MISSING), f"{path}/{k}" if path else k)
        return out
    return [] if a == b else [path]


def open_diff(left: Path, right: Path) -> None:
    """Open VS Code's diff view (``code --diff``); if ``code`` is unavailable, print the two paths."""
    if shutil.which("code"):
        subprocess.run(["code", "--diff", str(left), str(right)], check=False)
    else:
        print(f"'code' not found on PATH. Compare these files yourself:\n  {left}\n  {right}")


def show_diff(cloud_state: Any, merged: Any, opener: Callable[[Path, Path], None] = open_diff) -> Path:
    """Write the cloud state and the merged result to a temp folder and open them side by side.

    Left = latest cloud version, right = merged result, so the right side shows exactly what
    differs from the cloud (your kept local values). Returns the temp folder.
    """
    tmp = Path(tempfile.mkdtemp(prefix="state_sync_diff_"))
    left, right = tmp / "cloud_state.json", tmp / "merged_state.json"
    left.write_text(json.dumps(cloud_state, indent=4))
    right.write_text(json.dumps(merged, indent=4))
    changed = diff_paths(cloud_state, merged)
    print(f"Merged result differs from the cloud in {len(changed)} value(s); diff files in {tmp}")
    opener(left, right)
    return tmp


def resolve_target(backend: str | None, folder: str | None) -> tuple[str, Path]:
    """``(backend, state folder)``: the active qualibrate project's, unless ``folder`` is given."""
    if folder is None:
        try:
            from .download_state_and_wiring import active_project_state_path
        except ImportError:
            from download_state_and_wiring import active_project_state_path

        project, folder = active_project_state_path()
        if backend is None:
            backend = project
        elif backend != project:
            raise ValueError(
                f"'{backend}' is not the active qualibrate project ('{project}'). Switch first: "
                f"uv run python user_scripts/switch_backend.py {backend}"
            )
    elif backend is None:
        raise ValueError("Pass the backend name together with --folder.")
    return backend, Path(folder)


def sync(
    backend: str | None = None,
    folder: str | None = None,
    keep_patterns: list[str] | None = None,
    keep_file: Path | None = None,
    keep_local_changes: bool = False,
    prefer: str | None = None,
    apply: bool = False,
    diff: bool = False,
    client: Any = None,
    ask: Callable[[str], str] = input,
    opener: Callable[[Path, Path], None] = open_diff,
) -> bool:
    """Run the sync. Returns True if files were written (or a dry run found nothing blocking).

    ``client`` (an ``IQCC_Cloud``-like object with ``.state.get`` / ``.state.get_latest``) lets tests skip the network.
    """
    # Default: every change that is not pinned (--keep / .sync_keep) is a decision, including values
    # only changed locally (default answer: cloud). --keep-local-changes keeps those silently.
    safe = not keep_local_changes

    backend, folder_p = resolve_target(backend, folder)
    base_dir = folder_p / BASE_DIRNAME

    if client is None:
        from iqcc_cloud_client import IQCC_Cloud

        client = IQCC_Cloud(quantum_computer_backend=backend)
    cloud_state_ds = client.state.get_latest("state")
    cloud_wiring_ds = client.state.get_latest("wiring")
    cloud_state, cloud_wiring = cloud_state_ds.data, cloud_wiring_ds.data

    local_state = json.loads((folder_p / "state.json").read_text())
    base_state, base_source = read_base_state(folder_p, client)
    if base_state is MISSING:
        print(f"No base in {base_dir}: every difference between local and cloud will need a decision "
              f"(or pass --prefer / --keep).")
    else:
        print(f"Base: {base_source}; cloud is dataset {cloud_state_ds.id}.")

    keep = load_keep_patterns(keep_file if keep_file is not None else REPO_ROOT / KEEP_FILENAME, keep_patterns)
    merge = lambda choices=None: merge_trees(
        base_state, local_state, cloud_state, keep=keep, safe=safe, choices=choices, prefer=prefer
    )
    merged, resolved, pending = merge()

    print(f"Pins: {keep or 'none'}")
    print(f"Decisions already answered: {len(resolved)}, still open: {len(pending)}")
    if not apply:
        for d in pending:
            print(f"  [{d.kind}] {d.path}: local={_short(d.local, 40)} cloud={_short(d.cloud, 40)}")
        if diff:
            if pending:
                print(f"Note: {len(pending)} open decision(s) are shown with their cloud value in the diff.")
            show_diff(cloud_state, merged, opener)
        print("Dry run: nothing written. Re-run with --apply.")
        return not pending

    if pending:
        choices = prompt_for(pending, ask)
        merged, resolved, pending = merge(choices)
        assert not pending, "unanswered decisions remain"

    if set(merged) != set(cloud_state):
        raise RuntimeError("Merged state's top-level keys differ from the cloud state; aborting.")

    if diff:
        show_diff(cloud_state, merged, opener)
        if ask("Write these changes? [y/N]: ").strip().lower() not in ("y", "yes"):
            print("Aborted: nothing written.")
            return False

    backup = folder_p / BACKUP_DIRNAME / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup.mkdir(parents=True)
    for name in FILES:
        if (folder_p / name).is_file():
            shutil.copy2(folder_p / name, backup / name)

    (folder_p / "state.json").write_text(json.dumps(merged, indent=4))
    (folder_p / "wiring.json").write_text(json.dumps(cloud_wiring, indent=4))
    write_sync_base(folder_p, cloud_state_ds, cloud_wiring_ds)
    print(f"Written to {folder_p} (backup: {backup}). Base updated.")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("backend", nargs="?", default=None, help="Default: the active qualibrate project.")
    p.add_argument("--folder", help="State folder (default: the active qualibrate project's QUAM state path)")
    p.add_argument("--apply", action="store_true", help="Write the result (default: dry run)")
    p.add_argument("--diff", action="store_true",
                   help="Open VS Code's diff of the latest cloud state vs the merged result (with --apply: asks before writing)")
    p.add_argument("--keep-local-changes", action="store_true",
                   help="Keep every value that only changed locally without asking (default: ask, Enter = cloud value)")
    p.add_argument("--prefer", choices=["local", "cloud"], help="Answer all open decisions in bulk (conflicts and local-only changes)")
    p.add_argument("--keep", action="append", default=[], metavar="PATTERN",
                   help="Pin a path pattern to local, e.g. 'qubits/*/resonator/operations/readout_drachma' (repeatable)")
    p.add_argument("--keep-file", type=Path, help=f"Pin file (default: <repo>/{KEEP_FILENAME})")
    a = p.parse_args(argv)
    ok = sync(
        a.backend, a.folder, a.keep, a.keep_file,
        keep_local_changes=a.keep_local_changes, prefer=a.prefer, apply=a.apply, diff=a.diff,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
