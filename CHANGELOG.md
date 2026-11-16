# Changelog

Notable changes to the IQCC starter template, newest first. Every push to `cloud`
publishes a tagged snapshot (`v0.1.<run>`); significant releases get a named tag
(`v0.2.0`, ...) and an entry here. To move a checkout to a newer version, see
"Updating your checkout" in the [README](README.md).

## v0.2.0 — 2026-11-16

**Multi-backend workspaces.** One checkout can now hold several backends.

- Each backend is its own `qualibrate` project (`config/qualibrate/projects/<backend>/`)
  with its own state (`config/quam-state/<backend>/`) and data (`data/<backend>/`)
  folders. The active project decides which one nodes load and save, and which QUAM
  class is used (`config/quam_builder/` maps backend → hardware).
- Setup takes several backends (`iqcc_setup.py --backend a --backend b`, or a
  multi-select prompt). The checkout renders only the node layers its backends need
  (`hardware_layers` answer: `fixed_freq`, `tunable_transmon`, `tunable_coupler`).
- New `user_scripts/switch_backend.py` (`<backend> [--download]`); adding a backend is
  `install.py --backend <b>`, or `iqcc_setup.py --update --backend <b>` when its
  hardware needs nodes the checkout lacks.
- The environment bootstrap no longer sets `QUAM_STATE_PATH` (and unsets an inherited
  one); the active project provides the state path.
- **Migration:** `iqcc_setup.py --update` converts a single-backend checkout: its
  backend becomes a project (same state, data, token) and stays active; nothing is
  re-downloaded. Run it twice and the second run is a no-op.
- Learn (`environment=learn`) is unchanged and still single-backend.
- Added `00_start_here.ipynb`, `01_workflow.ipynb`, `01_workflow_marimo.py`.
- Repo commit: `bc62a2c`.

## Earlier (v0.1.x)

- Dependency bump: quam-builder v0.7.0, qualibration-libs v0.3.2, qualibrate 2.0.0,
  qm-qua 1.5.0, iqcc-cloud-client 0.22.0 (`8cb9876`).
- IQCC token verified against the cloud at install; `--update` defaults to the newest
  tagged version; saved tokens reused; `--update` stops on conflict markers
  (`abac4f7`, `a0599ae`).
- Public distribution via `iqcc-starter` and `iqcc_setup.py` / `iqcc_learn_setup.py`.
