# IQCC Starter

This repo is the starting point for running **pulse-level experiments on quantum
hardware** through the Quantum Machines (QM) software stack. It's a working Python
project template, not a tutorial: rendering it gives you a working set of
calibration scripts, a structured model of your quantum setup, and the plumbing to
pull your system's current state from the cloud and run against real (or simulated)
hardware. The rest of this README walks through what's here, starting broad and
getting more technical as it goes — skim what you need, and follow the links for
anything you want to go deeper on.

Render your own checkout with:

```
uv run https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_setup.py
```

No credential is needed to fetch the template — this repo is public. You will be
prompted for the backends to set up (pick one or more; each becomes a `qualibrate`
project in the same checkout, and more can be added later), and separately, during
install, for an IQCC Cloud API token per backend (used to pull its current state; see
[Installing](#installing) below). A token already saved for a backend in
`~/.config/iqcc_cloud/config.toml` is reused without prompting.

Options (append them to the command above):

- `<dest_dir>` — where to render (default `./iqcc-workspace`). If it is already a
  rendered checkout, rendering is skipped and `install.py` is re-run.
- `--backend <name>` — skip the backend prompt; repeat it for several backends. The
  checkout gets the calibration nodes for the hardware of the backends you pick. With
  `--update`, it adds the backend to an existing checkout instead (rendering the extra
  nodes if its hardware needs them, then setting up its token and state).
- `--update` — update an existing checkout to the newest published template version
  instead of rendering a new one; see [Updating your checkout](#updating-your-checkout).
- `--template <path-or-url>` and `--vcs-ref <ref>` — pick the template source and
  version (default for a fresh render: this repo's `cloud` branch).

For unattended runs, set `IQCC_API_TOKEN_<BACKEND>` (e.g. `IQCC_API_TOKEN_GILBOA`) to
each backend's IQCC Cloud API token (or `IQCC_API_TOKEN` when setting up one backend);
install then never prompts, and an invalid token is an error. With no terminal attached and no
saved token, the token step is skipped.

### Where to start

Once setup finishes, open these in your checkout:

- `00_start_here.ipynb` — a step-by-step walkthrough of one calibration (power Rabi),
  explaining each part, with links to the docs of every package it uses.
- `01_workflow.ipynb` — downloads the latest state, then runs a calibration node of
  your choice (default `05_T1`) on a random active qubit and shows the results.
- `01_workflow_marimo.py` — the interactive version of the same workflow: pick a node
  and qubits, edit its parameters in a form, run it, and see the plots. Launch it with
  `uv run marimo run 01_workflow_marimo.py` (use `marimo edit` to modify it).

All three follow the active backend's state, so they work on whichever backend you
have selected.

### Updating your checkout

The template evolves (new nodes, fixes, setup changes). Updating pulls those into
your checkout **without losing your own edits or your local state**. Run it from the
directory that contains the checkout (or pass its path as `<dest_dir>`):

```
uv run https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_setup.py --update
```

By default this moves you to the newest published version; pass `--vcs-ref <tag>` to
pick a specific one. What it does, in order:

1. Commits your local changes, because Copier needs a clean git tree. (The checkout is
   a git repo from the first setup on.)
2. Runs `copier update`: template changes are merged with your edits.
3. If your edits overlap the template's, it **stops** and lists the files containing
   conflict markers (`<<<<<<<` / `>>>>>>>`). Resolve them, commit, and run `--update`
   again.
4. Re-runs `install.py` without asking for a token and without re-downloading state,
   so your local `config/quam-state/` is kept.
5. Commits the result, with the new template version in the commit message.

Running `--update` again when you're already current changes nothing.

**Checkouts from before multi-backend.** A checkout created when each checkout held a
single backend is converted on update: that backend becomes a `qualibrate` project
(same state folder, data folder and token) and stays the active one. Nothing is
re-downloaded. Afterwards you can add more backends as described in
[Backends](#backends).

**Adding a backend while updating.** `--update --backend <name>` updates and adds the
backend in one go; if its hardware needs nodes your checkout doesn't have yet, they're
rendered, then the backend's token and state are set up. Existing backends keep their
local state.

**On IQCC Learn**, use the same `--update` flag with the Learn command (see below).
It keeps your edits and your local state, and doesn't re-download.

### On IQCC Learn (JupyterLab)

The IQCC Learn environment already has the QM stack installed, so it skips the
install flow above. From a Jupyter terminal (needs `uv` and `git`; no curl required):

```
python -c "import urllib.request as u; exec(u.urlopen('https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_learn_setup.py').read())"
```

It prompts for a `backend`, renders the checkout into `./iqcc-workspace`, sets up
`qualibrate` and the import hook, and downloads the latest `state.json` /
`wiring.json` into `iqcc-workspace/config/quam-state/<backend>/`. If the IQCC cloud
rejects your Learn credentials, setup fails and tells you that nodes can't run until
that's fixed. To start over, delete `iqcc-workspace` and re-run.

The same options as above work here, appended after the command: `--backend <name>`
(one backend only on Learn),
`--update` (update to the newest template version, keeping your edits and your local
state), and `--template` / `--vcs-ref`.

## Folder organization

| Folder | What's in it |
|---|---|
| `00_start_here.ipynb`, `01_workflow.ipynb`, `01_workflow_marimo.py` | Onboarding notebooks and an interactive app: a guided walkthrough of one calibration, and a run-a-node workflow. See [Where to start](#where-to-start). |
| `calibrations/` | The calibration scripts you run, numbered to suggest run order (e.g. `00_hello_qua.py`, `02a_resonator_spectroscopy.py`, ...). Each one defines a `qualibrate` node: a self-contained, runnable step that builds a QUA program, runs it, and saves its results. |
| `calibration_utils/` | Shared code imported by the scripts in `calibrations/` — one subpackage per calibration, each holding its parameter definitions and, where relevant, its data-analysis and plotting logic. `calibrations/*.py` is the entry point; `calibration_utils/` is the reusable logic behind it. |
| `config/` | Everything that describes *this* project's setup: which QUAM class models your QPU (`quam_builder/`), `qualibrate`'s own configuration (`qualibrate/`, one project per backend), and the live state of your quantum system (`quam-state/`, holding `wiring.json`/`state.json` in one folder per backend). |
| `data/` | Where calibration runs write their output datasets (one folder per backend). |
| `logs/` | Where `qualibrate` writes run logs. |
| `user_scripts/` | Small utility scripts you run directly: `download_state_and_wiring.py` pulls the latest system state from the cloud into `config/quam-state/`, and `switch_backend.py` changes which backend you're working on. |
| `_build_assets/` | Internal build/runtime plumbing — sets up the environment variables described below. Not something you need to touch day-to-day. |

`install.py` (see [Installing](#installing) below) is what wires `config/`, `data/`,
and `logs/` together the first time you set the project up.

## QM packages used in this repo

Running an experiment here means going from a pulse-level program, up through a
model of your physical system, up through an orchestration layer that runs and
tracks calibrations, connected to a cloud service that keeps that model in sync with
the real hardware. Each package below is one layer of that stack, roughly in that
order.

**[QUA](https://docs.quantum-machines.co/)** (package `qm-qua`) is the pulse-level
language for programming quantum hardware — the actual sequences of pulses, waits,
and measurements sent to the machine. It's imported directly (`from qm.qua import
*`) in every script under `calibrations/`, where the pulse sequence for that
calibration is written using it (e.g. `calibrations/00_hello_qua.py`).

**[QUAM](https://qua-platform.github.io/quam/)** (package `quam`, the "Quantum
Abstract Machine") is a structured, persistent model of your quantum setup —
qubits, resonators, drive lines, couplers, and their calibrated parameters — that
sits above QUA. Rather than hand-writing hardware configuration for every script,
each calibration loads this model once (`Quam.load()`) and reads/writes to it as
qubits get characterized.

**[quam-builder](https://github.com/qua-platform/quam-builder)** builds the
concrete QUAM class for your specific QPU architecture. `config/quam_builder/`
resolves to the right one for this project, so the rest of the code just imports
`Quam` without needing to know the underlying architecture details.

**[qualibrate](https://qua-platform.github.io/qualibrate/)** is the calibration
orchestration layer: it wraps a QUAM model plus a QUA program into a reusable,
trackable `QualibrationNode` (what each script in `calibrations/` defines), and can
chain nodes together into a `QualibrationGraph` for multi-step bring-up or retuning
workflows. It also owns its own run history, storage layout, and CLI, configured via
`config/qualibrate/`.

**[qualibration-libs](https://github.com/qua-platform/qualibration-libs)** is a
helper library used inside calibration nodes for the parts common to most
calibrations — fetching and shaping result data, running simulations, common
parameter definitions, fitting/analysis utilities. You'll see it imported throughout
`calibrations/` and `calibration_utils/`.

**iqcc-cloud-client** is the cloud connectivity layer. Its `IQCC_Cloud` client
fetches the latest known state and wiring of your quantum system from the cloud
(`user_scripts/download_state_and_wiring.py`) — this is what keeps the QUAM model in
`config/quam-state/` in sync with the real hardware, and what `install.py` uses to
populate it on first setup.

## Technical repo details

### Installing

After checking out the project, run:

```
uv run install.py
```

This installs dependencies (`uv sync`), configures `qualibrate` (log folder,
calibration library folder) with one project per backend, each with its own QUAM
state folder (`config/quam-state/<backend>/`) and data folder (`data/<backend>/`),
verifies the environment bootstrap described below is working, and downloads the
latest QUAM state and wiring of each backend. It asks which backends to set up
(pick several), or take them from `--backend <name>` (repeatable); re-running it with
no `--backend` works on the backends you already have. The first backend becomes the
active one.

For each download it needs an IQCC Cloud API token: it uses `IQCC_API_TOKEN_<BACKEND>`
(e.g. `IQCC_API_TOKEN_GILBOA`) if set, or `IQCC_API_TOKEN` when only one backend is
being set up, else a token already saved for that backend in
`~/.config/iqcc_cloud/config.toml`, else asks you to paste one (Enter skips that
backend's download, with a warning that you can't run nodes on it yet; so does having
no terminal). Whatever the source, the token is then checked against IQCC cloud — if
the cloud rejects it (or has no state for that backend) the install fails and says so,
since no node can run without the downloaded state. `--no-iqcc-setup` skips the token
and download step entirely. It's idempotent — safe to re-run any time (re-running
re-downloads the state, replacing your local copy).

### Backends

Your checkout has the calibration nodes for the hardware of the backends you chose
(the common nodes, plus the fixed-frequency and/or flux-tunable ones); the **active
backend** decides what they run on. It's the active `qualibrate` project, and it picks
the QUAM state folder the nodes load and save, the data folder runs are written to, and
the QUAM class (`config/quam_builder/` maps each backend to its hardware). A node meant
for other hardware than the active backend's fails when it runs.

```
uv run python user_scripts/switch_backend.py                       # list backends, show the active one
uv run python user_scripts/switch_backend.py <backend>             # switch
uv run python user_scripts/switch_backend.py <backend> --download  # switch, then pull its latest state
uv run install.py --backend <backend>                              # add a backend (same hardware as one you have)
```

A backend with other hardware also needs that hardware's nodes. Add it from the folder
that contains this checkout with the setup script, which renders those nodes too and
then sets the backend up (state and token included):

```
uv run https://raw.githubusercontent.com/i-qcc/iqcc-starter/cloud/iqcc_setup.py --update <this-folder> --backend <backend>
```

`qualibrate project switch <backend>` does the same switch. The notebooks, the marimo
app and the `qualibrate` web app follow the active backend too.

### Environment variables

This project's `.venv` automatically sets three environment variables on every
interpreter startup (`uv run`, an activated venv, `.venv/bin/qualibrate`,
`calibrations/*.py`, pytest, Jupyter kernels) via a `.pth` file installed into
`site-packages` at `uv sync` time. There is no shell rc file involved, and the
project's values always win over anything already set in your environment.

| Variable | Value |
|---|---|
| `REPO_ROOT` | this checkout's root |
| `QUALIBRATE_CONFIG_FILE` | `<REPO_ROOT>/config/qualibrate` (a directory) |
| `IQCC_DEFAULT_TIMEOUT` | from `pyproject.toml`'s `[tool.iqcc] default-timeout` |

There is no `QUAM_STATE_PATH`: the active backend's `qualibrate` project holds the
QUAM state path, and the bootstrap unsets an inherited `QUAM_STATE_PATH` (it would
override the project). Set `IQCC_BOOTSTRAP_QUIET=1` to silence the warnings printed to
stderr when an inherited value gets replaced or unset.

The bootstrap module lives at `_build_assets/_iqcc_bootstrap.py` and is
copied into `site-packages` at install time. Editing it requires
`uv sync --reinstall-package iqcc_client_tools` to take effect.
