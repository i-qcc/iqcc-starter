"""Download the latest QUAM state and wiring of a backend from IQCC cloud.

    uv run python user_scripts/download_state_and_wiring.py [backend]

The files go into the active qualibrate project's QUAM state folder, so the
backend must be the active project (default: the active project itself).
To switch backend and download in one go, use switch_backend.py --download.
This overwrites the local state.json / wiring.json.
"""

import argparse
import json
import logging
import os

from iqcc_cloud_client import IQCC_Cloud
from qualibrate.core.config.resolvers import get_quam_state_path
from qualibrate_config.resolvers import get_qualibrate_config, get_qualibrate_config_path

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def active_project_state_path() -> tuple[str, str]:
    """(active project name, its QUAM state folder) from the qualibrate config."""
    config = get_qualibrate_config(get_qualibrate_config_path())
    state_path = get_quam_state_path(config)
    if not state_path:
        raise ValueError(
            f"The active qualibrate project '{config.project}' has no QUAM state path; "
            "run 'uv run install.py' to set it up."
        )
    return config.project, str(state_path)


def download_state_and_wiring(quantum_computer_backend: str | None = None, folder_path: str | None = None) -> None:
    """
    Download the latest state and wiring files from the quantum computer backend.

    Args:
        quantum_computer_backend (str | None): The backend to download from. Defaults
            to the active qualibrate project; any other backend must be switched to first.
        folder_path (str | None): Optional explicit folder path to save the files.
            If not provided, uses the active qualibrate project's QUAM state path.
    """
    try:
        if folder_path is None:
            project, folder_path = active_project_state_path()
            if quantum_computer_backend is None:
                quantum_computer_backend = project
            elif quantum_computer_backend != project:
                raise ValueError(
                    f"'{quantum_computer_backend}' is not the active qualibrate project "
                    f"('{project}'). Switch first: "
                    f"uv run python user_scripts/switch_backend.py {quantum_computer_backend} --download"
                )
        elif quantum_computer_backend is None:
            raise ValueError("Pass the backend name together with an explicit folder_path.")

        logger.info(f"Connecting to quantum computer backend: {quantum_computer_backend}")
        qc = IQCC_Cloud(quantum_computer_backend=quantum_computer_backend)

        logger.info("Fetching latest wiring and state files")
        latest_wiring = qc.state.get_latest("wiring")
        latest_state = qc.state.get_latest("state")

        logger.info(f"State folder path: {folder_path}")

        # Create the directory if it doesn't exist
        os.makedirs(folder_path, exist_ok=True)

        # Save the files
        wiring_path = os.path.join(folder_path, "wiring.json")
        state_path = os.path.join(folder_path, "state.json")

        with open(wiring_path, "w") as f:
            json.dump(latest_wiring.data, f, indent=4)
        logger.info(f"Saved wiring file to: {wiring_path}")

        with open(state_path, "w") as f:
            json.dump(latest_state.data, f, indent=4)
        logger.info(f"Saved state file to: {state_path}")

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("backend", nargs="?", default=None, help="Default: the active qualibrate project.")
    download_state_and_wiring(parser.parse_args().backend)
