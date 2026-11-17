"""Record which cloud versions a local state folder was downloaded from.

Tiny stand-alone helper (standard library only). The download scripts call it after writing
``state.json``/``wiring.json``; ``sync_state_and_wiring`` reads what it writes. The on-disk
format is the contract between them:

    <state folder>/.sync_base/meta.json   {"state_id", "wiring_id", "state_parent_id"}
    <state folder>/.sync_base/state.json  cache copy of the cloud state
    <state folder>/.sync_base/wiring.json cache copy of the cloud wiring
"""

import json
from pathlib import Path
from typing import Any

BASE_DIRNAME = ".sync_base"


def write_sync_base(folder: str | Path, state_ds: Any, wiring_ds: Any) -> None:
    """Record which cloud versions ``folder`` now corresponds to.

    Call right after writing cloud data into ``folder``. ``state_ds`` / ``wiring_ds`` are the
    ``Dataset`` objects returned by ``qc.state`` (they need ``.id`` and ``.data``).
    """
    base_dir = Path(folder) / BASE_DIRNAME
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "state.json").write_text(json.dumps(state_ds.data, indent=4))
    (base_dir / "wiring.json").write_text(json.dumps(wiring_ds.data, indent=4))
    meta = {
        "state_id": state_ds.id,
        "wiring_id": wiring_ds.id,
        "state_parent_id": getattr(state_ds, "parent_id", None),
    }
    (base_dir / "meta.json").write_text(json.dumps(meta, indent=4))
