"""Helpers for ``01_workflow.ipynb``: run one node, review the state updates it proposes, accept them.

A node run with ``interactive=True`` *records* its state updates on the node instead of applying them
(the machine is left unchanged, as in the QUAlibrate web app). ``NodeRun.accept`` applies the ones you choose.
Only the active state is written; the run's own snapshot keeps the state the run started from.
QUAlibrate only records scalar updates (int, float, bool, str, None); a node that changes a list or dict
changes its in-memory machine without a proposal, and ``accept`` does not save that.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display
from qualibrate.core.utils.node.record_state_update import update_machine_attribute

__all__ = ["NodeRun", "run_node", "diff_vs_run"]

_STATE_FILES = ("state.json", "wiring.json")


@dataclass
class NodeRun:
    """The outcome of one interactive node run. ``node`` holds the results, ``summary`` the run summary."""

    node: Any
    summary: Any

    @property
    def changes(self) -> dict[str, dict[str, Any]]:
        """Proposed state updates by QUAM path, e.g. ``{"#/qubits/q1/T1": {"old": ..., "new": ...}}``."""
        return dict(self.summary.state_updates)

    @property
    def figures(self) -> dict[str, Any]:
        figures = dict(self.node.results.get("figures", {}))
        if "simulation" in self.node.results:
            figures["simulation"] = self.node.results["simulation"]["figure"]
        return figures

    def changes_table(self) -> pd.DataFrame:
        """One row per proposed update: path, old, new and the relative change in percent (numbers only)."""
        rows = []
        for path, change in self.changes.items():
            old, new = change["old"], change["new"]
            numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (old, new))
            pct = 100 * (new - old) / abs(old) if numeric and old else None
            rows.append({"path": path, "old": old, "new": new, "change_%": pct})
        return pd.DataFrame(rows, columns=["path", "old", "new", "change_%"])

    def show(self) -> None:
        """Print outcomes and fit results, show the figures, then the table of proposed state updates."""
        print("outcomes:", {q: getattr(o, "value", o) for q, o in self.summary.outcomes.items()})
        if self.summary.error:
            print("ERROR:", self.summary.error)
        for qubit, result in self.node.results.get("fit_results", {}).items():
            print(qubit, {k: v for k, v in result.items() if not hasattr(v, "__len__") or isinstance(v, str)})
        if self.node.snapshot_idx is not None:
            print("data saved as run id:", self.node.snapshot_idx)
        for name, fig in self.figures.items():
            print("figure:", name)
            display(fig)
        plt.close("all")
        if self.changes:
            print(f"\nproposed state updates ({len(self.changes)}), not applied yet:")
            display(self.changes_table())
        else:
            print("\nno state updates proposed")

    def accept(self, state_path: Path, keys: Optional[Iterable[str]] = None) -> list[str]:
        """Apply the proposed updates (all, or only the given paths) to the machine and save it to ``state_path``."""
        changes = self.changes
        keys = list(changes) if keys is None else list(keys)
        unknown = [k for k in keys if k not in changes]
        if unknown:
            raise KeyError(f"not proposed by this run: {unknown}; proposed: {list(changes)}")
        if not keys:
            print("nothing to accept")
            return []
        # Apply onto a fresh load of the current state, not onto node.machine: the node may have mutated
        # that in ways QUAlibrate does not record (e.g. list values), and after a load_data_id replay it
        # holds the old run's state.
        machine = type(self.node.machine).load(str(state_path))
        for key in keys:
            update_machine_attribute(machine, key, changes[key]["new"])
        machine.save(str(state_path))
        print(f"accepted {len(keys)} update(s), state saved to {state_path}")
        return keys


def run_node(library, name: str, **params) -> NodeRun:
    """Run ``library.nodes[name]`` with ``params`` as an interactive run (state updates proposed, not applied)."""
    node = library.nodes[name]
    summary = node.run(interactive=True, **params)
    return NodeRun(node=node, summary=summary)


def _flat(d: dict, prefix: str = "#") -> dict[str, Any]:
    out = {}
    for k, v in d.items():
        key = f"{prefix}/{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key))
        else:
            out[key] = v
    return out


def _read_state(folder: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for name in _STATE_FILES:
        if (folder / name).exists():
            merged.update(json.loads((folder / name).read_text()))
    return _flat(merged)


def diff_vs_run(run_id: int, state_path: Path, storage_location: Path) -> pd.DataFrame:
    """Compare the state in ``state_path`` with the state saved by run ``run_id`` (``#<id>_*`` under ``storage_location``)."""
    folders = sorted(Path(storage_location).glob(f"*/#{run_id}_*/quam_state"))
    if not folders:
        raise FileNotFoundError(f"no saved run #{run_id} under {storage_location}")
    current, then = _read_state(Path(state_path)), _read_state(folders[0])
    rows = [
        {"path": key, "current": current.get(key), f"run_{run_id}": then.get(key)}
        for key in sorted(current.keys() | then.keys())
        if current.get(key) != then.get(key)
    ]
    return pd.DataFrame(rows, columns=["path", "current", f"run_{run_id}"])
