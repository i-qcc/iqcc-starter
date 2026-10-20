import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", app_title="Start here: anatomy of a node")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    QUA_DOCS = "https://docs.quantum-machines.co/latest/"
    QUAM_DOCS = "https://qua-platform.github.io/quam/"
    QB_DOCS = "https://github.com/qua-platform/quam-builder"
    QLB_DOCS = "https://qua-platform.github.io/qualibrate/"
    QLIBS_DOCS = "https://github.com/qua-platform/qualibration-libs"
    PYQUA_DOCS = "https://github.com/qua-platform/py-qua-tools"

    # The notebook lives in the checkout root, wherever the kernel was started from.
    ROOT = mo.notebook_dir()

    # Everything below comes from the active qualibrate config: the same source the nodes use at runtime.
    from qualibrate.core.config.resolvers import get_quam_state_path
    from qualibrate_config.resolvers import get_qualibrate_config, get_qualibrate_config_path

    _config = get_qualibrate_config(get_qualibrate_config_path())
    BACKEND = _config.project
    _configured = get_quam_state_path(_config)
    mo.stop(
        not _configured,
        mo.callout(
            mo.md("No QUAM state path configured. Run `install.py` (workstation) or `learn_setup.py` (Learn) first."),
            kind="danger",
        ),
    )
    # A relative path in the config means "relative to the checkout root".
    STATE_PATH = ROOT / _configured

    mo.md(
        f"""
        # 00 · Start here: anatomy of a calibration node

        A *node* is one calibration experiment. This notebook takes the real
        `calibrations/02a_resonator_spectroscopy.py` node and walks through it **one cell per part**.
        Unlike a plain script, this notebook is **reactive**: move a slider and everything downstream
        re-computes. Hardware is only touched when you press a button.

        | | Package | Role |
        |---|---|---|
        | 💎 | **QUA** (`qm.qua`) · [docs]({QUA_DOCS}) | The pulse-level language that runs on the OPX. *This is where the experiment actually happens.* |
        | 🧩 | **QUAM** · [docs]({QUAM_DOCS}) | The Python object model of your quantum machine (qubits, resonators, pulses). |
        | 🧩 | **quam-builder** · [docs]({QB_DOCS}) | Builds QUAM classes for a concrete QPU architecture. |
        | 🧩 | **QUAlibrate** · [docs]({QLB_DOCS}) | Wraps an experiment into a node: parameters, run-actions, results, saving. |
        | 🧩 | **qualibration-libs** · [docs]({QLIBS_DOCS}) | Reusable helpers: qubit selection, data fetching, simulation. |

        Green callouts (💎) are **QUA**, the gem. Blue callouts (🧩) are the supporting packages.
        Backend: `{BACKEND}`
        """
    )
    return (
        PYQUA_DOCS,
        QB_DOCS,
        QLB_DOCS,
        QLIBS_DOCS,
        QUAM_DOCS,
        QUA_DOCS,
        ROOT,
        STATE_PATH,
        mo,
    )


@app.cell(hide_code=True)
def _(QUA_DOCS, mo):
    def qua_note(text):
        return mo.callout(mo.md(f"💎 **QUA**: {text} [QUA docs]({QUA_DOCS})"), kind="success")

    def pkg_note(text):
        return mo.callout(mo.md(f"🧩 {text}"), kind="info")

    return pkg_note, qua_note


@app.cell(hide_code=True)
def _(mo, qua_note):
    mo.vstack(
        [
            mo.md("## 1 · Imports\nGrouped by package so you can see who provides what."),
            qua_note(
                "marimo does not allow `from qm.qua import *`, so we import the module as `qua`. "
                "A bonus for learning: **every QUA call in this notebook is visibly prefixed with `qua.`** "
                "(`qua.program`, `qua.declare`, `qua.for_`, `qua.save` ...)."
            ),
        ]
    )
    return


@app.cell
def _(ROOT):
    import sys

    # Make the checkout importable (`config`, `calibration_utils`), whatever the working directory.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import numpy as np
    import xarray as xr
    import matplotlib.pyplot as plt
    from dataclasses import asdict

    # ── 💎 QUA ── the pulse-level language
    from qm import qua, generate_qua_script

    # ── py-qua-tools ── small helpers around QUA (loops, units, progress, multi-user sessions)
    from qualang_tools.loops import from_array
    from qualang_tools.multi_user import qm_session
    from qualang_tools.units import unit

    # ── 🧩 QUAlibrate ── the node framework
    from qualibrate import QualibrationNode

    # ── 🧩 quam-builder ── `Quam` resolves to the architecture class for your QPU
    from config.quam_builder import Quam

    # ── this repo ── the analysis/plotting for this particular experiment
    from calibration_utils.resonator_spectroscopy import (
        Parameters,
        process_raw_dataset,
        fit_raw_data,
        log_fitted_results,
        plot_raw_amplitude_with_fit,
        plot_raw_phase,
    )

    # ── 🧩 qualibration-libs ── shared helpers
    from qualibration_libs.parameters import get_qubits
    from qualibration_libs.runtime import simulate_and_plot
    from qualibration_libs.data import XarrayDataFetcher
    from qualibration_libs.analysis import lorentzian_dip

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:  # the explorer falls back to matplotlib
        go = make_subplots = None
    return (
        Parameters,
        QualibrationNode,
        Quam,
        XarrayDataFetcher,
        asdict,
        fit_raw_data,
        from_array,
        generate_qua_script,
        get_qubits,
        go,
        log_fitted_results,
        lorentzian_dip,
        make_subplots,
        np,
        plot_raw_amplitude_with_fit,
        plot_raw_phase,
        plt,
        process_raw_dataset,
        qm_session,
        qua,
        simulate_and_plot,
        unit,
        xr,
    )


@app.cell(hide_code=True)
def _(QB_DOCS, QUAM_DOCS, mo, pkg_note):
    mo.vstack(
        [
            mo.md("## 2 · Load the machine"),
            pkg_note(
                f"**QUAM** ([docs]({QUAM_DOCS})) · **quam-builder** ([docs]({QB_DOCS})): `Quam.load(...)` reads "
                "`state.json` + `wiring.json` and returns a Python object tree: `machine.qubits['q1'].resonator`, "
                "`.xy`, `.z` ... quam-builder defines the classes in that tree for your QPU architecture."
            ),
        ]
    )
    return


@app.cell
def _(Quam, STATE_PATH, mo):
    mo.stop(
        not (STATE_PATH / "state.json").exists(),
        mo.callout(
            mo.md(
                f"`state.json` not found in `{STATE_PATH}`. Fetch the latest state first "
                "(run `01_workflow.ipynb`, `learn_setup.py`, or `user_scripts/download_state_and_wiring.py`)."
            ),
            kind="danger",
        ),
    )
    machine = Quam.load(str(STATE_PATH))
    qubit_names = list(machine.qubits)
    mo.md(f"Loaded **{len(qubit_names)} qubits**: {', '.join(f'`{q}`' for q in qubit_names)}")
    return (qubit_names,)


@app.cell(hide_code=True)
def _(mo, pkg_note):
    mo.vstack(
        [
            mo.md("## 3 · Control panel (parameters)"),
            pkg_note(
                "**QUAlibrate**: `node.parameters` is what the QUAlibrate GUI exposes and what graphs override. "
                "In a script you edit them in a `custom_param` action; here, these widgets *are* the parameters. "
                "The structure comes from `calibration_utils/resonator_spectroscopy/parameters.py` "
                "(composed from **qualibration-libs** mixins)."
            ),
        ]
    )
    return


@app.cell
def _(mo, qubit_names):
    qubit_sel = mo.ui.multiselect(qubit_names, value=qubit_names[:1], label="Qubits")
    span = mo.ui.slider(5, 100, value=30, step=5, label="Span [MHz]", show_value=True)
    step = mo.ui.slider(0.05, 1.0, value=0.1, step=0.05, label="Step [MHz]", show_value=True)
    shots = mo.ui.slider(10, 1000, value=100, step=10, label="Shots (averages)", show_value=True)
    mode = mo.ui.radio(
        ["Run on OPX", "Replay a past run", "Simulate"], value="Run on OPX", label="Mode"
    )
    replay_id = mo.ui.number(start=1, stop=10_000_000, value=1, label="Data id to replay")
    run_btn = mo.ui.run_button(label="▶ Run on the OPX")
    mo.hstack(
        [mo.vstack([qubit_sel, shots]), mo.vstack([span, step]), mo.vstack([mode, replay_id])],
        justify="start",
        gap=3,
    )
    return mode, qubit_sel, replay_id, run_btn, shots, span, step


@app.cell
def _(mo, np, qubit_sel, span, step):
    mo.stop(not qubit_sel.value, mo.callout(mo.md("Select at least one qubit."), kind="warn"))
    _dfs = np.arange(-span.value / 2, span.value / 2, step.value)
    mo.hstack(
        [
            mo.stat(len(_dfs), label="Sweep points"),
            mo.stat(f"{_dfs[0]:.2f} → {_dfs[-1]:.2f} MHz", label="Detuning range"),
            mo.stat(len(qubit_sel.value), label="Qubits"),
        ],
        justify="start",
    )
    return


@app.cell(hide_code=True)
def _(QLB_DOCS, mo, pkg_note):
    mo.vstack(
        [
            mo.md("## 4 · Create the node"),
            pkg_note(
                f"**QUAlibrate** ([docs]({QLB_DOCS})): `QualibrationNode[Parameters, Quam]` ties together a **name**, "
                "a **description**, typed **parameters** and the **machine**. The two type arguments only give you "
                "editor type hints. The node is named `00_start_here_marimo_resonator_spectroscopy` so it can't clash "
                "with the real `02a` node. Each control-panel change builds a fresh node."
            ),
        ]
    )
    return


@app.cell
def _(
    Parameters,
    QualibrationNode,
    Quam,
    STATE_PATH,
    mode,
    qubit_sel,
    replay_id,
    shots,
    span,
    step,
):
    description = """
    1D RESONATOR SPECTROSCOPY
    Sweep the readout frequency, demodulate I/Q, and fit the resonator resonance.
    State update: qubit.resonator.f_01 and qubit.resonator.RF_frequency
    """

    node = QualibrationNode[Parameters, Quam](
        name="00_start_here_marimo_resonator_spectroscopy",
        description=description,
        parameters=Parameters(
            qubits=list(qubit_sel.value),
            sweep=dict(
                num_shots=shots.value,
                frequency_span_in_mhz=float(span.value),
                frequency_step_in_mhz=float(step.value),
            ),
            simulate=mode.value == "Simulate",
            load_data_id=int(replay_id.value) if mode.value == "Replay a past run" else None,
        ),
        machine=Quam.load(str(STATE_PATH)),
    )
    return (node,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 5 · Sweep axes (plain Python / NumPy)
    `@node.run_action` turns a function into a named step of the node. `skip_if=` decides when it is skipped
    (for example when replaying stored data). No QUA yet: we decide *which frequencies* to measure and name the
    axes of the resulting dataset.
    """)
    return


@app.cell
def _(Parameters, QualibrationNode, Quam, get_qubits, node, np, unit, xr):
    @node.run_action(skip_if=node.parameters.load_data_id is not None)
    def _define_sweep(node: QualibrationNode[Parameters, Quam]):
        u = unit(coerce_to_integer=True)  # py-qua-tools: u.MHz, u.us, u.ns ... as plain numbers
        node.namespace["qubits"] = qubits = get_qubits(node)  # qualibration-libs: resolve parameters.qubits
        span = node.parameters.sweep.frequency_span_in_mhz * u.MHz
        step = node.parameters.sweep.frequency_step_in_mhz * u.MHz
        dfs = np.arange(-span / 2, +span / 2, step)
        node.namespace["dfs"] = dfs
        node.namespace["sweep_axes"] = {
            "qubit": xr.DataArray(qubits.get_names()),
            "detuning": xr.DataArray(dfs, attrs={"long_name": "readout frequency", "units": "Hz"}),
        }

    qubits = node.namespace.get("qubits")
    dfs = node.namespace.get("dfs")
    sweep_axes = node.namespace.get("sweep_axes")
    return dfs, qubits


@app.cell(hide_code=True)
def _(mo, qua_note):
    mo.vstack(
        [
            mo.md("## 6 · The QUA program"),
            qua_note(
                "Everything inside `with qua.program()` is **QUA**. It is compiled and executed *on the OPX*, "
                "in real time, not in Python. `declare` creates variables that live on the hardware, `for_` is a "
                "hardware loop, `save` streams a value back to the host, `stream_processing` decides what is "
                "averaged on the OPX before it ever reaches Python."
            ),
        ]
    )
    return


@app.cell
def _(
    Parameters,
    QualibrationNode,
    Quam,
    dfs,
    from_array,
    node,
    qua,
    qubits,
    unit,
):
    @node.run_action(skip_if=node.parameters.load_data_id is not None)
    def _create_qua_program(node: QualibrationNode[Parameters, Quam]):
        u = unit(coerce_to_integer=True)
        num_qubits = len(qubits)
        n_avg = node.parameters.sweep.num_shots

        # ═══════════════════════ 💎 QUA PROGRAM STARTS HERE ═══════════════════════
        with qua.program() as node.namespace["qua_program"]:
            # 🧩 QUAM helper: declares the I, Q, n QUA variables + their streams, one per qubit
            I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
            df = qua.declare(int)  # 💎 a variable living on the OPX

            for multiplexed_qubits in qubits.batch():  # python-side: groups of qubits measured together
                for qubit in multiplexed_qubits.values():
                    node.machine.initialize_qpu(target=qubit)  # 🧩 QUAM: set flux points etc.
                qua.align()  # 💎 synchronise all channels
                with qua.for_(n, 0, n < n_avg, n + 1):  # 💎 hardware averaging loop
                    qua.save(n, n_st)  # 💎 stream the iteration counter (progress)
                    with qua.for_(*from_array(df, dfs)):  # 💎 hardware loop over frequency (from_array: py-qua-tools)
                        for i, qubit in multiplexed_qubits.items():
                            rr = qubit.resonator  # 🧩 QUAM object: a channel with its pulses and frequencies
                            rr.update_frequency(df + rr.intermediate_frequency)  # 💎 QUA update_frequency, driven by QUAM
                            rr.measure("readout", qua_vars=(I[i], Q[i]))  # 💎 play readout pulse + demodulate
                            rr.wait(rr.depletion_time * u.ns)  # 💎 let the resonator ring down
                            qua.save(I[i], I_st[i])  # 💎 send I to the stream
                            qua.save(Q[i], Q_st[i])  # 💎 send Q to the stream
                        qua.align()

            # 💎 stream_processing() also runs on the OPX: buffer one sweep and average over shots
            with qua.stream_processing():
                n_st.save("n")
                for i in range(num_qubits):
                    I_st[i].buffer(len(dfs)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(dfs)).average().save(f"Q{i + 1}")
        # ═══════════════════════ 💎 QUA PROGRAM ENDS HERE ═════════════════════════

    qua_program = node.namespace.get("qua_program")
    return (qua_program,)


@app.cell(hide_code=True)
def _(generate_qua_script, mo, node, qua_note, qua_program):
    mo.stop(qua_program is None)
    try:
        _script = generate_qua_script(qua_program, node.machine.generate_config())
    except Exception as exc:  # noqa: BLE001 - purely informational
        _script = f"# could not generate the script: {exc!r}"
    mo.vstack(
        [
            qua_note(
                "Curious what the Python above *became*? `generate_qua_script` prints the QUA program that is sent "
                "to the OPX. `node.machine.generate_config()` turns the QUAM tree into the **QUA config** "
                "(the OPX's hardware description)."
            ),
            mo.accordion({"🔍 The QUA your Python generated": mo.md(f"```python\n{_script}\n```")}),
        ]
    )
    return


@app.cell(hide_code=True)
def _(PYQUA_DOCS, QLIBS_DOCS, mo, mode, qua_note, run_btn):
    mo.vstack(
        [
            mo.md("## 7 · Simulate, execute, or replay"),
            qua_note(
                "`node.machine.connect()` opens a `QuantumMachinesManager`; `qm.execute(program)` sends the program "
                "to the OPX; with **Simulate** it runs on the OPX *simulator* instead and returns waveforms "
                "(only available when you have a direct QOP connection, **not** on IQCC cloud backends, where "
                "you will get an error)."
            ),
            mo.md(
                f"🧩 **qualibration-libs** ([docs]({QLIBS_DOCS})): `simulate_and_plot`, `XarrayDataFetcher` · "
                f"**py-qua-tools** ([docs]({PYQUA_DOCS})): `qm_session` (waits for a free machine). "
                "**Replay** reloads a stored dataset by id, so you can practise the analysis with no hardware at all."
            ),
            run_btn if mode.value == "Run on OPX" else mo.md(""),
        ]
    )
    return


@app.cell
def _(
    Parameters,
    QualibrationNode,
    Quam,
    XarrayDataFetcher,
    get_qubits,
    mo,
    mode,
    node,
    qm_session,
    qua_program,
    run_btn,
    simulate_and_plot,
):
    # Hardware only runs after the button press; moving a slider never launches a job.
    mo.stop(
        mode.value == "Run on OPX" and not run_btn.value,
        mo.callout(mo.md("Press **▶ Run on the OPX** above to execute."), kind="neutral"),
    )

    @node.run_action(skip_if=node.parameters.load_data_id is not None or not node.parameters.simulate)
    def _simulate_qua_program(node: QualibrationNode[Parameters, Quam]):
        qmm = node.machine.connect()  # 💎 QuantumMachinesManager
        config = node.machine.generate_config()  # 🧩 QUAM -> 💎 QUA config
        samples, fig, wf_report = simulate_and_plot(qmm, config, qua_program, node.parameters)
        node.results["simulation"] = {"figure": fig, "wf_report": wf_report, "samples": samples}

    @node.run_action(skip_if=node.parameters.load_data_id is not None or node.parameters.simulate)
    def _execute_qua_program(node: QualibrationNode[Parameters, Quam]):
        qmm = node.machine.connect()
        config = node.machine.generate_config()
        with qm_session(qmm, config, timeout=node.parameters.timeout) as qm:  # py-qua-tools: wait for a free machine
            node.namespace["job"] = job = qm.execute(qua_program)  # 💎 run on the OPX
            data_fetcher = XarrayDataFetcher(job, node.namespace["sweep_axes"])  # 🧩 qualibration-libs: stream -> xarray
            # marimo's progress bar replaces py-qua-tools' `progress_counter` used in scripts
            with mo.status.progress_bar(total=node.parameters.sweep.num_shots, title="Running on the OPX") as bar:
                done = 0
                for dataset in data_fetcher:
                    now = int(data_fetcher.get("n", 0))
                    bar.update(increment=max(now - done, 0))
                    done = max(now, done)
            node.log(job.execution_report())
        node.results["ds_raw"] = dataset

    @node.run_action(skip_if=node.parameters.load_data_id is None)
    def _load_data(node: QualibrationNode[Parameters, Quam]):
        load_data_id = node.parameters.load_data_id
        node.load_from_id(node.parameters.load_data_id)
        node.parameters.load_data_id = load_data_id
        node.namespace["qubits"] = get_qubits(node)

    sim_fig = node.results.get("simulation", {}).get("figure")
    ds_raw = node.results.get("ds_raw")
    active_qubits = node.namespace.get("qubits")
    return active_qubits, ds_raw, sim_fig


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 8 · Analyse
    Pure Python from here on: no hardware involved. The fit functions live in
    `calibration_utils/resonator_spectroscopy/analysis.py`. The node records an **outcome**
    (`successful` / `failed`) per qubit, which the state update uses later.
    """)
    return


@app.cell
def _(
    Parameters,
    QualibrationNode,
    Quam,
    asdict,
    ds_raw,
    fit_raw_data,
    log_fitted_results,
    mo,
    node,
    process_raw_dataset,
    sim_fig,
):
    mo.stop(
        ds_raw is None,
        mo.vstack(
            [
                mo.callout(
                    mo.md("Simulation only: no data to analyse. Switch the mode to **Run on OPX** or **Replay**."),
                    kind="neutral",
                ),
                sim_fig if sim_fig is not None else mo.md(""),
            ]
        ),
    )

    @node.run_action(skip_if=node.parameters.simulate)
    def _analyse_data(node: QualibrationNode[Parameters, Quam]):
        node.results["ds_raw"] = process_raw_dataset(node.results["ds_raw"], node)
        node.results["ds_fit"], fit_results = fit_raw_data(node.results["ds_raw"], node)
        node.results["fit_results"] = {k: asdict(v) for k, v in fit_results.items()}
        log_fitted_results(node.results["fit_results"], log_callable=node.log)
        node.outcomes = {
            name: ("successful" if r["success"] else "failed") for name, r in node.results["fit_results"].items()
        }

    ds = node.results["ds_raw"]
    ds_fit = node.results["ds_fit"]
    fit_results = node.results["fit_results"]
    return ds, ds_fit, fit_results


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 9 · Results: many qubits, many plots
    Twenty qubits means twenty plots, and nobody wants to scroll through them. So: a **summary** first, a
    **table** to find the qubits that matter (failures, big shifts), and plots only for the **rows you select**.
    """)
    return


@app.cell
def _(active_qubits, fit_results, mo, np):
    _rows = []
    for _q in active_qubits:
        _r = fit_results[_q.name]
        _rows.append(
            {
                "qubit": _q.name,
                "status": "✅" if _r["success"] else "❌",
                "resonator [GHz]": round(_r["frequency"] / 1e9, 6),
                "shift vs state [MHz]": round((_r["frequency"] - _q.resonator.RF_frequency) / 1e6, 3),
                "FWHM [kHz]": round(_r["fwhm"] / 1e3, 1),
            }
        )
    _ok = sum(r["status"] == "✅" for r in _rows)
    fit_table = mo.ui.table(_rows, selection="multi", initial_selection=list(range(len(_rows))), label="Fit results")
    metric = mo.ui.radio(["Amplitude (with fit)", "Phase"], value="Amplitude (with fit)", label="Plot")
    mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(f"{_ok} / {len(_rows)}", label="Successful fits", bordered=True),
                    mo.stat(f"{len(_rows) - _ok}", label="Failed", bordered=True),
                    mo.stat(
                        f"{np.median([r['FWHM [kHz]'] for r in _rows]):.0f} kHz", label="Median FWHM", bordered=True
                    ),
                ],
                justify="start",
            ),
            fit_table,
            metric,
        ]
    )
    return fit_table, metric


@app.cell
def _(
    ds,
    ds_fit,
    fit_table,
    go,
    lorentzian_dip,
    make_subplots,
    metric,
    mo,
    np,
    plt,
):
    mo.stop(not fit_table.value, mo.callout(mo.md("Select rows in the table to plot them."), kind="warn"))
    _names = [r["qubit"] for r in fit_table.value]
    _amp = metric.value.startswith("Amplitude")
    _cols = min(3, len(_names))
    _nrows = int(np.ceil(len(_names) / _cols))

    def _curves(name):
        x = ds.full_freq.sel(qubit=name).values / 1e9
        if _amp:
            y = ds.IQ_abs.sel(qubit=name).values * 1e3  # mV
            f = ds_fit.sel(qubit=name)
            fit = lorentzian_dip(
                ds.detuning,
                float(f.amplitude.values),
                float(f.position.values),
                float(f.width.values) / 2,
                float(f.base_line.mean().values),
            )
            return x, y, np.asarray(fit) * 1e3
        return x, ds.phase.sel(qubit=name).values, None

    if go is not None:
        _fig = make_subplots(rows=_nrows, cols=_cols, subplot_titles=_names)
        for _i, _n in enumerate(_names):
            _x, _y, _fit = _curves(_n)
            _r, _c = _i // _cols + 1, _i % _cols + 1
            _fig.add_scatter(x=_x, y=_y, mode="lines", name=_n, showlegend=False, row=_r, col=_c)
            if _fit is not None:
                _fig.add_scatter(
                    x=_x, y=_fit, mode="lines", line=dict(color="red", dash="dash"), showlegend=False, row=_r, col=_c
                )
            _fig.update_xaxes(title_text="RF frequency [GHz]", row=_r, col=_c)
            _fig.update_yaxes(title_text="|IQ| [mV]" if _amp else "phase [rad]", row=_r, col=_c)
        _fig.update_layout(height=300 * _nrows + 60, margin=dict(t=40, b=40), template="plotly_white")
        explorer = mo.ui.plotly(_fig)
    else:
        _mfig, _axes = plt.subplots(_nrows, _cols, figsize=(5 * _cols, 3.5 * _nrows), squeeze=False)
        for _i, _n in enumerate(_names):
            _ax = _axes[_i // _cols][_i % _cols]
            _x, _y, _fit = _curves(_n)
            _ax.plot(_x, _y)
            if _fit is not None:
                _ax.plot(_x, _fit, "r--")
            _ax.set_title(_n)
        _mfig.tight_layout()
        explorer = _mfig
    return (explorer,)


@app.cell
def _(
    active_qubits,
    ds,
    ds_fit,
    explorer,
    mo,
    plot_raw_amplitude_with_fit,
    plot_raw_phase,
    plt,
):
    # The node's own grid figures (what `02a` saves next to the data)
    _fig_phase = plot_raw_phase(ds, active_qubits)
    _fig_amp = plot_raw_amplitude_with_fit(ds, active_qubits, ds_fit)
    plt.close("all")
    mo.ui.tabs(
        {
            "🔎 Explorer (selected qubits)": explorer,
            "🖼 Node figures (all qubits)": mo.vstack([_fig_amp, _fig_phase]),
        }
    )
    return


@app.cell(hide_code=True)
def _(QLB_DOCS, QUAM_DOCS, mo, pkg_note):
    mo.vstack(
        [
            mo.md("## 10 · Update the state and save"),
            pkg_note(
                f"**QUAlibrate** ([docs]({QLB_DOCS})): `node.record_state_updates()` records every change made to the "
                f"QUAM tree inside the block. **QUAM** ([docs]({QUAM_DOCS})): assigning `q.resonator.f_01 = ...` edits "
                "the machine state itself. `node.save()` stores parameters, data, figures and the updates under `data/`. "
                "Only qubits whose fit succeeded are updated. Review the preview, then apply."
            ),
        ]
    )
    return


@app.cell
def _(active_qubits, fit_results, mo, node):
    _rows = []
    for _q in active_qubits:
        if node.outcomes[_q.name] == "failed":
            continue
        _new = float(fit_results[_q.name]["frequency"])
        _rows.append(
            {
                "qubit": _q.name,
                "old RF_frequency [GHz]": round(_q.resonator.RF_frequency / 1e9, 6),
                "new RF_frequency [GHz]": round(_new / 1e9, 6),
                "change [MHz]": round((_new - _q.resonator.RF_frequency) / 1e6, 3),
            }
        )
    apply_btn = mo.ui.run_button(label="💾 Apply update & save", kind="warn")
    mo.vstack(
        [
            mo.ui.table(_rows, selection=None, label="Proposed updates") if _rows else mo.md("_No successful fits._"),
            apply_btn,
        ]
    )
    return (apply_btn,)


@app.cell
def _(Parameters, QualibrationNode, Quam, apply_btn, mo):
    mo.stop(not apply_btn.value, mo.callout(mo.md("State is **not** modified until you press apply."), kind="neutral"))

    @node.run_action(skip_if=node.parameters.simulate)
    def _update_state(node: QualibrationNode[Parameters, Quam]):
        with node.record_state_updates():
            for q in node.namespace["qubits"]:
                if node.outcomes[q.name] == "failed":
                    continue
                q.resonator.f_01 = float(node.results["fit_results"][q.name]["frequency"])
                q.resonator.RF_frequency = float(node.results["fit_results"][q.name]["frequency"])

    @node.run_action()
    def _save_results(node: QualibrationNode[Parameters, Quam]):
        node.save()

    mo.callout(mo.md("✅ State updated and node saved."), kind="success")
    return


@app.cell(hide_code=True)
def _(QB_DOCS, QLB_DOCS, QLIBS_DOCS, QUAM_DOCS, QUA_DOCS, mo):
    mo.md(
        f"""
        ## Where next
        * Browse `calibrations/`: every node follows this exact shape.
        * Open **`01_workflow.ipynb`** to download the latest state and run several nodes in sequence.
        * Docs: [QUA]({QUA_DOCS}) · [QUAM]({QUAM_DOCS}) · [quam-builder]({QB_DOCS}) · [QUAlibrate]({QLB_DOCS}) · [qualibration-libs]({QLIBS_DOCS})
        """
    )
    return


if __name__ == "__main__":
    app.run()
