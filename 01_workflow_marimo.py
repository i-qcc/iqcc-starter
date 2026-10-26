import marimo

__generated_with = "0.14.0"
app = marimo.App(width="medium", app_title="01 · Workflow")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # 01 · Workflow — run any single node

        1. download the **latest QUAM state and wiring** from IQCC,
        2. **pick a node** from the library and the qubits to run it on,
        3. optionally **edit its parameters** (anything you leave alone keeps its default),
        4. **run** it: the node plots the results and **updates the local state**.

        The state is only local, so a bad run costs nothing: download the latest good state again to reset it.
        """
    )
    return


@app.cell
def _(mo):
    mo.callout(
        mo.md(
            "🧩 **QUAlibrate** ([docs](https://qua-platform.github.io/qualibrate/)) runs the nodes · "
            "**QUAM** ([docs](https://qua-platform.github.io/quam/)) holds the state they read and update · "
            "💎 **QUA** ([docs](https://docs.quantum-machines.co/latest/)) is the program each node runs on the OPX."
        ),
        kind="neutral",
    )
    return


@app.cell
def _(mo):
    from pathlib import Path

    # Everything below comes from the active qualibrate config: the same source the nodes use at runtime.
    from qualibrate.core.config.resolvers import get_quam_state_path
    from qualibrate_config.resolvers import get_qualibrate_config, get_qualibrate_config_path

    _config = get_qualibrate_config(get_qualibrate_config_path())
    BACKEND = _config.project
    _configured = get_quam_state_path(_config)
    if not _configured:
        raise RuntimeError(
            "No QUAM state path configured. Run install.py (workstation) or learn_setup.py (Learn) first."
        )
    # install.py / learn_setup.py store an absolute path; a relative one (hand-run `qualibrate config`)
    # means "relative to the checkout root", which is where this notebook lives.
    STATE_PATH = Path(_configured)
    if not STATE_PATH.is_absolute():
        STATE_PATH = (mo.notebook_dir() or Path.cwd()) / STATE_PATH

    mo.hstack(
        [mo.stat(BACKEND, label="Backend", bordered=True), mo.stat(str(STATE_PATH), label="State folder", bordered=True)],
        justify="start",
    )
    return BACKEND, STATE_PATH


@app.cell
def _(mo):
    mo.md("## 1 · Download the latest state and wiring")
    return


@app.cell
def _(mo):
    download = mo.ui.run_button(label="⬇ Download latest state & wiring", kind="neutral")
    mo.hstack(
        [download, mo.md("_Needs IQCC credentials. **Overwrites the local `state.json` and `wiring.json`.**_")],
        justify="start",
        align="center",
    )
    return (download,)


@app.cell
def _(BACKEND, STATE_PATH, download, mo):
    import json

    state_version = object()  # changes on every download, so the qubit picker below re-reads state.json
    _out = mo.md("")
    if download.value:
        from iqcc_cloud_client import IQCC_Cloud

        with mo.status.spinner(f"Downloading state for {BACKEND}…"):
            _qc = IQCC_Cloud(BACKEND)
            _wiring = _qc.state.get_latest("wiring")
            _state = _qc.state.get_latest("state")
            STATE_PATH.mkdir(parents=True, exist_ok=True)
            (STATE_PATH / "wiring.json").write_text(json.dumps(_wiring.data, indent=4))
            (STATE_PATH / "state.json").write_text(json.dumps(_state.data, indent=4))
        _out = mo.callout(mo.md(f"Wrote `wiring.json` and `state.json` to `{STATE_PATH}`"), kind="success")
    _out
    return json, state_version


@app.cell
def _(mo):
    mo.md("## 2 · Pick a node and qubits")
    return


@app.cell
def _(mo):
    from qualibrate import QualibrationLibrary

    library = QualibrationLibrary.get_active_library()
    _names = sorted(library.nodes)
    node_name = mo.ui.dropdown(
        _names, value="05_T1" if "05_T1" in _names else _names[0], searchable=True, label="Node", full_width=True
    )
    return library, node_name


@app.cell
def _(STATE_PATH, json, state_version):
    import random

    state_version  # re-run after a download
    # Read from state.json, so this works wherever the checkout runs (no `config` import needed).
    _state = json.loads((STATE_PATH / "state.json").read_text())
    ACTIVE_QUBITS = _state.get("active_qubit_names") or list(_state.get("qubits", {}))
    return ACTIVE_QUBITS, random


@app.cell
def _(ACTIVE_QUBITS, mo, random):
    qubits = mo.ui.multiselect(
        ACTIVE_QUBITS, value=[random.choice(ACTIVE_QUBITS)] if ACTIVE_QUBITS else [], label="Qubits", full_width=True
    )
    return (qubits,)


@app.cell
def _(library, mo, node_name, qubits):
    _node = library.nodes[node_name.value]
    _doc = (getattr(_node, "description", None) or (_node.__doc__ or "")).strip()
    mo.vstack(
        [
            mo.hstack([node_name, qubits], widths="equal", align="end"),
            mo.md("_No qubit selected = all active qubits._"),
            mo.callout(mo.md(_doc), kind="info") if _doc else mo.md(""),
        ]
    )
    return


@app.cell
def _(mo):
    mo.md("## 3 · Parameters")
    return


@app.cell
def _(json, mo):
    import enum
    import typing

    def _is_literal(tp):
        return typing.get_origin(tp) is typing.Literal

    def widget_for(field, default):
        """One input widget per pydantic field; anything exotic becomes a JSON text box."""
        tp = field.annotation
        label = field.title or ""
        if isinstance(default, bool):
            return mo.ui.switch(value=default)
        if isinstance(default, int) and not isinstance(default, bool):
            return mo.ui.number(value=default, step=1)
        if isinstance(default, float):
            return mo.ui.number(value=default)
        if isinstance(tp, type) and issubclass(tp, enum.Enum):
            return mo.ui.dropdown([m.value for m in tp], value=getattr(default, "value", default))
        if _is_literal(tp):
            return mo.ui.dropdown(list(typing.get_args(tp)), value=default)
        if isinstance(default, str):
            return mo.ui.text(value=default, full_width=True)
        return mo.ui.text(value="" if default is None else json.dumps(default), full_width=True)

    def read_value(widget, default):
        """Widget value back to the python type of the default (JSON text boxes are parsed)."""
        value = widget.value
        if isinstance(widget, mo.ui.text) and not isinstance(default, str):
            return None if value.strip() == "" else json.loads(value)
        return value

    return read_value, widget_for


@app.cell
def _(library, mo, node_name, widget_for):
    reset = mo.ui.button(label="↺ Reset to defaults")
    reset  # clicking re-creates the form below
    _node = library.nodes[node_name.value]
    DEFAULTS = {k: v for k, v in _node.parameters.model_dump().items() if k not in ("qubits", "simulate")}
    _fields = type(_node.parameters).model_fields
    simulate = mo.ui.switch(
        value=bool(_node.parameters.model_dump().get("simulate", False)), label="Simulate (OPX simulator)"
    )
    param_form = mo.ui.dictionary({k: widget_for(_fields[k], v) for k, v in DEFAULTS.items()})
    return DEFAULTS, param_form, reset, simulate


@app.cell
def _(DEFAULTS, library, mo, node_name, param_form, read_value, reset):
    _fields = type(library.nodes[node_name.value].parameters).model_fields
    _rows = [
        mo.hstack(
            [mo.md(f"**{k}**"), w, mo.md(f"<small>{_fields[k].description or ''}</small>")],
            widths=[2, 2, 5],
            align="center",
        )
        for k, w in param_form.items()
    ]

    OVERRIDES, _errors = {}, []
    for k, w in param_form.items():
        try:
            v = read_value(w, DEFAULTS[k])
        except ValueError as e:
            _errors.append(f"`{k}`: {e}")
            continue
        if v != DEFAULTS[k]:
            OVERRIDES[k] = v

    mo.vstack(
        [
            mo.hstack([reset], justify="end"),
            mo.accordion({f"All parameters ({len(DEFAULTS)})": mo.vstack(_rows)}),
            mo.callout(mo.md("Invalid value: " + "; ".join(_errors)), kind="danger") if _errors else mo.md(""),
            mo.md("**Changed from default**"),
            mo.ui.table([{"parameter": k, "default": str(DEFAULTS[k]), "value": str(v)} for k, v in OVERRIDES.items()],
                        selection=None)
            if OVERRIDES
            else mo.md("_nothing changed — running with the node's defaults_"),
        ]
    )
    return (OVERRIDES,)


@app.cell
def _(mo):
    mo.md("## 4 · Run")
    return


@app.cell
def _(mo, simulate):
    run = mo.ui.run_button(label="▶ Run node", kind="success")
    mo.hstack([run, simulate], justify="start", align="center")
    return (run,)


@app.cell
def _(OVERRIDES, library, mo, node_name, qubits, run, simulate):
    import traceback

    mo.stop(not run.value, mo.callout(mo.md("Choose a node and press **Run**."), kind="info"))
    node = library.nodes[node_name.value]
    _kwargs = dict(OVERRIDES, simulate=simulate.value)
    if qubits.value:
        _kwargs["qubits"] = list(qubits.value)
    summary, run_error = None, None
    with mo.status.spinner(f"Running {node_name.value}…"):
        try:
            summary = node.run(**_kwargs)
        except Exception:
            run_error = traceback.format_exc()
    return node, run_error, summary


@app.cell
def _(mo, node, node_name, run_error, summary):
    if run_error:
        _out = mo.vstack(
            [
                mo.callout(mo.md(f"**{node_name.value}** failed."), kind="danger"),
                mo.accordion({"Traceback": mo.md(f"```\n{run_error}\n```")}),
            ]
        )
    else:
        _badges = []
        for _q, _o in (summary.outcomes or {}).items():
            _ok = str(getattr(_o, "value", _o)).lower() == "successful"
            _badges.append(mo.callout(mo.md(f"**{_q}** · {getattr(_o, 'value', _o)}"), kind="success" if _ok else "danger"))
        _figs = {}
        for _name, _fig in node.results.get("figures", {}).items():
            try:
                _figs[_name] = mo.mpl.interactive(_fig)
            except Exception:
                _figs[_name] = _fig
        _out = mo.vstack(
            [
                mo.md(f"### Results · data saved as run id **{node.snapshot_idx}**"),
                mo.hstack(_badges, justify="start") if _badges else mo.md("_no outcomes reported_"),
                mo.ui.tabs(_figs) if _figs else mo.md("_no figures_"),
                mo.md("_The node's state updates were written to the **local** state. Download again to reset it._"),
            ]
        )
    _out
    return


if __name__ == "__main__":
    app.run()
