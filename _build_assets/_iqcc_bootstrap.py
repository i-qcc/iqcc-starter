# _iqcc_bootstrap.py
#
# Copied verbatim into this venv's site-packages at install time via the
# [tool.hatch.build.targets.wheel.force-include] entries in pyproject.toml
# (this applies to the editable install too -- force-include is not skipped
# for PEP 660 editable builds). Loaded on every interpreter startup in this
# venv via the sibling _iqcc_bootstrap.pth file.
#
# Editing this file has NO effect until the copy in site-packages is
# refreshed:
#
#     uv sync --reinstall-package iqcc_client_tools
#
# Standard library only -- no project imports. An exception raised here
# during site initialization breaks every interpreter in the venv,
# including pip and uv themselves, so every code path below is guarded.

import os
import sys
import tomllib
from pathlib import Path

_MARKERS = ("pyproject.toml", "calibration_utils")


def _warn(msg: str) -> None:
    if not os.environ.get("IQCC_BOOTSTRAP_QUIET"):
        print(f"[iqcc-bootstrap] {msg}", file=sys.stderr)


def _has_markers(path: Path) -> bool:
    return all((path / marker).exists() for marker in _MARKERS)


def _project_root():
    # Walk up from sys.prefix (the venv root, e.g. <repo>/.venv) looking for
    # a directory containing BOTH markers -- a single marker alone would
    # also match an unrelated parent project on a dev machine with nested
    # checkouts.
    for parent in Path(sys.prefix).resolve().parents:
        if _has_markers(parent):
            return parent

    # Fallback: scan sys.path. The editable install already puts the bare
    # project root on sys.path, but we do not rely on .pth load order to
    # guarantee that happened before this file ran.
    for entry in sys.path:
        if not entry:
            continue
        p = Path(entry)
        if _has_markers(p):
            return p.resolve()

    return None


def _read_iqcc_table(root: Path) -> dict:
    with (root / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("iqcc", {})


def _set(name: str, value) -> None:
    # Unconditional overwrite: the project's value always wins over
    # anything already present in the environment -- a shell profile, a
    # parent process, CI, or a stale export left over from before this
    # bootstrap existed. No setdefault, no opt-out, no allowlist.
    current = os.environ.get(name)
    if current is not None and current != str(value):
        _warn(f"{name} was {current!r}; project value {value!r} wins")
    os.environ[name] = str(value)


def _set_path_if_exists(name: str, path: Path) -> None:
    if not path.exists():
        _warn(f"{name} target does not exist, skipping: {path}")
        return
    _set(name, str(path))


def _bootstrap() -> None:
    root = _project_root()
    if root is None:
        _warn("could not locate project root (no pyproject.toml + calibration_utils found); skipping")
        return

    table = _read_iqcc_table(root)
    project_name = table.get("project-name")
    default_timeout = table.get("default-timeout")

    if project_name is None:
        _warn("[tool.iqcc] project-name missing from pyproject.toml; skipping PROJECT_NAME")
    else:
        _set("PROJECT_NAME", project_name)

    if default_timeout is None:
        _warn("[tool.iqcc] default-timeout missing from pyproject.toml; skipping IQCC_DEFAULT_TIMEOUT")
    else:
        _set("IQCC_DEFAULT_TIMEOUT", default_timeout)

    _set_path_if_exists("REPO_ROOT", root)

    if project_name is not None:
        _set_path_if_exists("QUAM_STATE_PATH", root / "config" / "quam-state" / project_name)

    # NOTE: this is a directory, not a file, despite the variable name --
    # reproduced exactly as install.py currently computes it. Do not "fix"
    # this to point at config.toml as part of this change (see Follow-ups
    # in the change description).
    _set_path_if_exists("QUALIBRATE_CONFIG_FILE", root / "config" / "qualibrate")


try:
    _bootstrap()
except Exception as exc:  # deliberate: never break interpreter startup
    print(f"[iqcc-bootstrap] {exc!r}", file=sys.stderr)
