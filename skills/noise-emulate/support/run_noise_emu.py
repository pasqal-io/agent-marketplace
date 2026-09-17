#!/usr/bin/env python3
"""
run_noise_emu.py — GPU noise emulation runner.

RUNS ON: this machine, or a GPU node through SLURM. No batch is submitted and
nothing is billed; the only cloud call reads the device's noise model, which is
free.

Fetches the FRESNEL_CAN1 noise_model live from the Pasqal cloud SDK,
prints all parameter values being used, then runs 1 noiseless + N noisy MPS
trajectories sequentially on GPU. Optionally sweeps calibration offsets
(omega_offset, delta_offset, R_offset) for an extended sensitivity envelope.

Results are saved to a self-documenting .npz file for plot_noise_emu.py.

Sequence builder contract
-------------------------
The --seq-file must define a function with this signature:

    def build_sequence(
        omega_offset: float = 1.0,
        delta_offset: float = 0.0,
        R_offset:     float = 1.0,
        **kwargs,                    # any extra physics params passed via --seq-kwargs
    ) -> pulser.Sequence:
        ...

The builder receives the nominal physics kwargs from --seq-kwargs PLUS the
calibration offset values. It must return a fully built (non-parametric)
pulser.Sequence with a valid register.

Three-curve model
-----------------
  · Noiseless nominal   — user's exact sequence, no noise       (reference)
  · Noisy nominal       — same sequence + FCAN1 noise           (stochastic noise alone)
  · Noisy QPU-matched   — sequence at calibrated QPU params     (what QPU actually ran)
                          only produced when --qpu-manifest is given

The third curve is the scientifically correct comparison with QPU data: it uses
the same omega and detuning the QPU was submitted with (omega/omega_ratio and
delta+delta_offset from calibration), so noise model ↔ QPU is apples-to-apples.

Output .npz layout
------------------
    n_traj              (n_traj+1, n_times, n_sites)  idx 0 = noiseless nominal
    c_traj              (n_traj+1, n_times, n_sites, n_sites)
    times               (n_times,)                    normalised ∈ (0, 1]
    total_duration      (1,)                          ns
    coords              (n_sites, 2)                  atom positions (µm)
    noise_model_json    (1,)                          JSON string of NoiseModel
    seq_kwargs_json     (1,)                          JSON string of seq_kwargs
    cal_n               (n_cal, n_times, n_sites)     noiseless at ±offsets [optional]
    cal_c               (n_cal, n_times, n_sites, n_sites)                  [optional]
    cal_labels_json     (1,)                          JSON list of offset labels [optional]
    n_traj_qpu          (n_traj, n_times, n_sites)    noisy at QPU-matched params [optional]
    c_traj_qpu          (n_traj, n_times, n_sites, n_sites)                        [optional]
    qpu_offset_json     (1,)                          JSON of {omega_offset, delta_offset, R_offset}

Usage
-----
python run_noise_emu.py \\
    --seq-file    seq_builder.py \\
    --fn-name     build_sequence \\
    --seq-kwargs  '{"N": 6, "hx": 4.0, "t": 4000}' \\
    --n-traj      40 \\
    --max-chi     512 \\
    --n-times     75 \\
    --out-dir     results/ \\
    --cal-offsets '{"omega_offset": 0.03, "delta_offset": 0.2, "R_offset": 0.01}' \\
    --qpu-manifest results/<experiment>/qpu/batch_ids.json
"""

import argparse
import importlib.util
import itertools
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pulser
from pulser.json.abstract_repr.deserializer import deserialize_device
try:
    from emu_mps import MPSBackend, MPSConfig, Occupation, CorrelationMatrix, BitStrings
except ModuleNotFoundError:
    # emu-mps (and the torch build under it) is the heaviest dependency in the
    # toolkit and this is the only script that needs it. Imported at module
    # scope it made `--help` fail with a traceback instead of printing usage,
    # and made every wiring check depend on a GPU-class install. main() reports
    # the missing package once a run actually starts, which is where it belongs.
    MPSBackend = MPSConfig = Occupation = CorrelationMatrix = BitStrings = None

import spec_noise
from pasqal_auth import ensure_credentials


# ── Optional noise overrides ────────────────────────────────────────────────────
# By default the device's as-shipped noise model is used unchanged. Each field can
# be overridden via CLI (--device-T2, --device-temperature, --device-detuning-sigma)
# for sensitivity studies or site-specific calibration; a negative value (the
# default) keeps the shipped value.


def fetch_fcan1(device_name="FRESNEL_CAN1",
                override_T2_us=None,
                override_temperature_uK=None,
                override_detuning_sigma=None):
    import dataclasses
    from pasqal_cloud import SDK
    creds, _ = ensure_credentials()
    sdk    = SDK(**creds)
    specs  = sdk.get_device_specs_dict()
    if device_name not in specs:
        raise ValueError(f"{device_name} not in available devices: {list(specs.keys())}")
    device = deserialize_device(specs[device_name])
    nm = getattr(device, "noise_model", None) or device.default_noise_model

    if override_T2_us and override_T2_us > 0:
        print(f"  ⚙  Overriding dephasing: T₂ {1/nm.dephasing_rate:.1f} → "
              f"{override_T2_us:.1f} µs (user override)")
        nm = dataclasses.replace(nm, dephasing_rate=1.0 / override_T2_us)

    if override_temperature_uK is not None and override_temperature_uK >= 0:
        print(f"  ⚙  Overriding temperature: {nm.temperature:.1f} → "
              f"{override_temperature_uK:.1f} µK (user override)")
        nm = dataclasses.replace(nm, temperature=override_temperature_uK)

    if override_detuning_sigma is not None and override_detuning_sigma >= 0:
        print(f"  ⚙  Overriding detuning_sigma: {nm.detuning_sigma:.4f} → "
              f"{override_detuning_sigma:.4f} rad/µs (user override)")
        nm = dataclasses.replace(nm, detuning_sigma=override_detuning_sigma)

    return device, nm


def print_noise_model_summary(nm, device_name="FRESNEL_CAN1"):
    """Print a clear table of all active noise channels and their values."""
    print()
    print("=" * 62)
    print(f"  Noise model: {device_name} (fetched live from cloud SDK)")
    print("=" * 62)

    T2 = f"  T₂ = {1/nm.dephasing_rate:.1f} µs" if nm.dephasing_rate else "  (off)"
    T1 = f"  T₁ = {1/nm.relaxation_rate:.1f} µs" if nm.relaxation_rate else "  (off)"

    rows = [
        ("Active channels",    ", ".join(nm.noise_types)),
        ("state_prep_error η", f"{nm.state_prep_error:.4f}"),
        ("p_false_pos  ε",     f"{nm.p_false_pos:.4f}"),
        ("p_false_neg  ε'",    f"{nm.p_false_neg:.4f}"),
        ("temperature",        f"{nm.temperature:.1f} µK"),
        ("laser_waist",        f"{nm.laser_waist:.2f} µm  (Doppler)"),
        ("trap_waist",         f"{nm.trap_waist:.3f} µm"),
        ("trap_depth",         f"{nm.trap_depth:.1f} µK"),
        ("amp_sigma  σ_Ω",     f"{nm.amp_sigma:.5f}  ({nm.amp_sigma*100:.2f}%)"),
        ("detuning_sigma  σ_δ",f"{nm.detuning_sigma:.4f} rad/µs"),
        ("dephasing_rate  γ_z",f"{nm.dephasing_rate:.4f} rad/µs{T2}"),
        ("relaxation_rate γ_r",f"{nm.relaxation_rate:.4f} rad/µs{T1}"),
        ("detuning_hf PSD",    f"{len(nm.detuning_hf_omegas)} freq. points embedded"),
    ]
    for label, value in rows:
        print(f"  {label:<26s}: {value}")
    print("=" * 62)

    # ── Full explicit dump of every parameter actually in the noise model ─────
    # The curated table above highlights the physically important channels; this
    # section prints EVERY field carried by the NoiseModel so nothing is hidden.
    print("  Full NoiseModel parameter dump (every field in use):")
    try:
        full = json.loads(nm.to_abstract_repr())
    except Exception:
        full = {}
    for key in sorted(full):
        val = full[key]
        # The detuning PSD (detuning_hf*) is a long frequency/amplitude table.
        # Don't print its contents — just note it is present and how many points.
        if key.startswith("detuning_hf"):
            npts = len(val) if isinstance(val, (list, tuple)) else "?"
            print(f"    {key:<26s}: PSD table present ({npts} pts) — values omitted")
            continue
        if isinstance(val, (list, tuple)):
            # Try to treat as a flat numeric vector; fall back to a shape summary
            # for nested / non-numeric lists (e.g. effective-noise operators).
            try:
                arr = np.asarray(val, dtype=float)
            except (ValueError, TypeError):
                arr = None
            if arr is not None and arr.ndim == 1 and arr.size > 6:
                preview = ", ".join(f"{x:.4g}" for x in arr[:3])
                print(f"    {key:<26s}: list[{arr.size}]  "
                      f"min={arr.min():.4g} max={arr.max():.4g} "
                      f"mean={arr.mean():.4g}  [{preview}, ...]")
            elif arr is not None and arr.ndim > 1:
                print(f"    {key:<26s}: array shape {arr.shape}")
            else:
                print(f"    {key:<26s}: {val}")
        else:
            print(f"    {key:<26s}: {val}")
    print("=" * 62)
    print()


# ── Load sequence builder ──────────────────────────────────────────────────────

def load_builder(seq_file: str, fn_name: str):
    path = Path(seq_file).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Sequence builder file not found: {path}")
    spec = importlib.util.spec_from_file_location("_seq_builder", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, fn_name):
        raise AttributeError(
            f"Function '{fn_name}' not found in {path}. "
            f"Available names: {[n for n in dir(mod) if not n.startswith('_')]}"
        )
    return getattr(mod, fn_name)


# ── One MPS trajectory ─────────────────────────────────────────────────────────

def run_one_trajectory(seq: pulser.Sequence, config: "MPSConfig") -> tuple:
    """Run one MPS trajectory.

    Returns (n_occ, c_corr, times, total_duration, bitstrings), where bitstrings is a
    dict {bitstring: count} sampled at the FINAL time, or None if the config carries no
    BitStrings observable.

    n_occ is the raw Rydberg occupation ⟨n⟩ ∈ [0, 1].
    To get magnetisation use:  σᶻ = 2⟨n⟩ − 1
      → ground state (n=0) gives σᶻ = −1
      → Rydberg state (n=1) gives σᶻ = +1
    This is the convention used throughout plot_noise_emu.py.
    Do NOT use 1 − 2⟨n⟩, which gives the wrong sign.

    Why bitstrings matter: ⟨n_i⟩ and ⟨n_i n_j⟩ are not enough for magnitude-averaged
    observables such as ⟨|m|⟩ or any higher moment (Binder cumulant), which need the
    full sampling distribution. Bitstrings also put the emulator on exactly the same
    footing as the QPU, whose only output is shot bitstrings.
    """
    result    = MPSBackend(seq, config=config).run()
    occ_tag   = "occupation"
    corr_tag  = "correlation_matrix"
    rtimes    = result.get_result_times(occ_tag)
    n_sites   = len(seq.register.qubit_ids)
    n_t       = len(rtimes)

    n_arr  = np.zeros((n_t, n_sites), dtype=np.float64)
    c_arr  = np.zeros((n_t, n_sites, n_sites), dtype=np.float64)
    for it, t in enumerate(rtimes):
        n_arr[it]  = np.asarray(result.get_result(occ_tag,  t), dtype=np.float64)
        c_arr[it]  = np.asarray(result.get_result(corr_tag, t), dtype=np.float64)

    bits = None
    try:
        btimes = result.get_result_times("bitstrings")
        if btimes:
            bits = {str(k): int(v)
                    for k, v in dict(result.get_result("bitstrings", btimes[-1])).items()}
    except Exception:
        bits = None

    return (n_arr, c_arr, np.asarray(rtimes, dtype=np.float64),
            result.total_duration, bits)


# ── Calibration offset sweeps ──────────────────────────────────────────────────

def run_calibration_sweeps(builder, seq_kwargs: dict, mps_base_cfg: dict,
                           cal_offsets: dict) -> tuple:
    """
    For each calibration parameter independently, run noiseless at ±offset.
    Returns (cal_n, cal_c, labels) where cal_n has shape (n_runs, n_times, n_sites).

    cal_offsets: dict mapping param_name → ±magnitude.
      e.g. {"omega_offset": 0.03, "delta_offset": 0.2, "R_offset": 0.01}

    Nominal values: omega_offset=1.0, delta_offset=0.0, R_offset=1.0.
    Each param is swept at [nominal-mag, nominal+mag] with all others at nominal.
    This gives 2 × len(cal_offsets) extra noiseless runs.
    """
    NOMINAL = {"omega_offset": 1.0, "delta_offset": 0.0, "R_offset": 1.0}
    config  = MPSConfig(**mps_base_cfg)

    cal_n_list, cal_c_list, labels = [], [], []
    total_runs = 2 * len(cal_offsets)
    run_idx = 0

    for param, magnitude in cal_offsets.items():
        nom = NOMINAL.get(param, 0.0 if "delta" in param else 1.0)
        for sign, tag in [(-1, "low"), (+1, "high")]:
            kw = {**seq_kwargs, param: nom + sign * magnitude}
            label = f"{param}={kw[param]:+.4g}"
            run_idx += 1
            print(f"  [{run_idx}/{total_runs}] Cal offset: {label}")
            seq = builder(**kw)
            n, c, _, _, _ = run_one_trajectory(seq, config)
            cal_n_list.append(n)
            cal_c_list.append(c)
            labels.append(label)

    return (
        np.stack(cal_n_list),   # (n_runs, n_times, n_sites)
        np.stack(cal_c_list),
        labels,
    )


# ── Self-documenting filename ──────────────────────────────────────────────────

def make_filename(seq_kwargs: dict, n_traj: int, max_chi: int, timestamp: str) -> str:
    parts = ["FCAN1"]
    for k, v in sorted(seq_kwargs.items()):
        parts.append(f"{k}{v}")
    parts.extend([f"ntraj{n_traj}", f"chi{max_chi}", timestamp])
    return "_".join(str(p) for p in parts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run GPU noise emulation with FRESNEL_CAN1 noise model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--seq-file",    required=False, default=None,
                        help="Path to Python file containing the sequence builder.")
    parser.add_argument("--fn-name",     default="build_sequence",
                        help="Name of the builder function (default: build_sequence).")
    parser.add_argument("--seq-kwargs",  default="{}", type=json.loads,
                        help='JSON dict of physics kwargs passed to the builder, '
                             'e.g. \'{"N": 6, "hx": 4.0, "t": 4000}\'.')
    parser.add_argument("--n-traj",      type=int, default=40,
                        help="Number of noisy MC trajectories (default: 40).")
    parser.add_argument("--max-chi",     type=int, default=128,
                        help="MPS max bond dimension (default: 128). Convergence-validated "
                             "for S(π,π)/2-point/local observables on systems up to 6×6 "
                             "(noiseless S(π,π) agrees with χ=200 to ~0.05%%; calibrated "
                             "2026-06 on the t_fall sweep). For larger N, entanglement "
                             "entropy / full-distribution / higher-moment observables, or "
                             "longer anneals, raise to 200+ and re-validate.")
    parser.add_argument("--n-times",     type=int, default=75,
                        help="Number of observable evaluation times (default: 75).")
    parser.add_argument("--out-dir",     default="results/",
                        help="Output directory for .npz file (default: results/).")
    parser.add_argument("--device-name", default="FRESNEL_CAN1",
                        help="Cloud device to fetch noise model from (default: FRESNEL_CAN1).")
    parser.add_argument("--cal-offsets", default=None, type=json.loads,
                        help='JSON dict of calibration ±magnitudes per offset parameter, '
                             'e.g. \'{"omega_offset": 0.03, "delta_offset": 0.2, '
                             '"R_offset": 0.01}\'. '
                             'Each param is swept at [nominal−mag, nominal+mag].')
    parser.add_argument("--qpu-manifest", default=None,
                        help='Path to batch_ids.json from submit_qpu.py. When given, '
                             'runs an additional N noisy trajectories at the measured '
                             'calibration offsets so the emulation matches what the QPU '
                             'actually executed.')
    parser.add_argument("--dt",          type=int, default=10,
                        help="MPS time step in ns (default: 10). Convergence-validated for "
                             "S(π,π) up to 6×6 (identical to dt=4; ~50 steps per ~500 ns "
                             "Rabi period). Combined with max-chi=128 this is ~2.5× faster "
                             "than the old (χ=200, dt=4) with no accuracy change. For much "
                             "faster drives (shorter Rabi period) lower dt and re-validate.")
    parser.add_argument("--device-T2",   type=float, default=-1.0,
                        help="Override the device dephasing T₂ in µs. Default (negative) "
                             "keeps the device's as-shipped value.")
    parser.add_argument("--device-temperature", type=float, default=-1.0,
                        help="Override the device temperature in µK. Default (negative) "
                             "keeps the device's as-shipped value.")
    parser.add_argument("--device-detuning-sigma", type=float, default=-1.0,
                        help="Override the device detuning_sigma in rad/µs. Default (negative) "
                             "keeps the device's as-shipped value.")
    # ── Parallel mode ─────────────────────────────────────────────────────────
    parser.add_argument("--run-id",      type=int, default=None,
                        help="Parallel mode: run only this single trajectory and save "
                             "partial_<run-id>.npz. run-id=0 → noiseless, "
                             "run-id=1..n-traj → noisy. Combine with --merge afterwards.")
    parser.add_argument("--spec",        default=None,
                        help="the experiment_spec.json this sequence came from. "
                             "If it carries a noise model of its own, this is "
                             "what --noise-source can switch to.")
    parser.add_argument("--noise-source", default="device",
                        choices=("device", "paper"),
                        help="whose noise model to emulate: this device's "
                             "(default) or the one the source described "
                             "(needs --spec)")
    parser.add_argument("--noise-model-json", default=None,
                        help="Path to pre-saved noise model JSON (avoids cloud fetch per "
                             "parallel job). Generate with --save-noise-model first.")
    parser.add_argument("--save-noise-model", action="store_true",
                        help="Fetch the noise model and save it to <out-dir>/noise_model.json, "
                             "then exit. Use before submitting parallel jobs.")
    parser.add_argument("--bitstrings",  type=int, default=0,
                        help="If >0, also sample this many shot bitstrings from the "
                             "final state and store them in the .npz as a JSON "
                             "{bitstring: count} map. Needed for magnitude-averaged "
                             "observables like <|m|> and for higher moments, which "
                             "cannot be reconstructed from <n_i> and <n_i n_j>. "
                             "Default 0 = off (previous behaviour).")
    parser.add_argument("--merge",       action="store_true",
                        help="Merge all partial_*.npz files in <out-dir> into a full .npz. "
                             "Run after all --run-id jobs complete.")
    args = parser.parse_args()

    if MPSConfig is None:
        raise SystemExit(
            "emu-mps is not installed in this environment — install the skill's "
            "dependencies first:\n"
            "  pip install -r support/requirements.txt\n"
            "For a run without emu-mps, use cloud mode (run_noise_emu_cloud.py).")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # ── Mode: save noise model only ───────────────────────────────────────────
    if args.save_noise_model:
        print(f"Fetching {args.device_name} noise model...")
        _, noise_model = fetch_fcan1(args.device_name, override_T2_us=args.device_T2,
                                 override_temperature_uK=args.device_temperature,
                                 override_detuning_sigma=args.device_detuning_sigma)
        print_noise_model_summary(noise_model, args.device_name)
        out_nm = out_dir / "noise_model.json"
        out_nm.write_text(noise_model.to_abstract_repr())
        print(f"Saved → {out_nm}")
        return

    # ── Mode: merge partials ──────────────────────────────────────────────────
    if args.merge:
        partials = sorted(out_dir.glob("partial_*.npz"),
                          key=lambda p: int(p.stem.split("_")[1]))
        if not partials:
            print(f"No partial_*.npz found in {out_dir}"); return
        print(f"Merging {len(partials)} partial files...")

        arrays_n, arrays_c = [], []
        times, total_dur, coords = None, None, None
        nm_json, sq_json = None, None

        for pf in partials:
            d = np.load(pf, allow_pickle=False)
            arrays_n.append(d["n"])
            arrays_c.append(d["c"])
            if times is None:
                times     = d["times"].tolist()
                total_dur = float(d["total_duration"][0])
            if "coords"           in d and coords  is None: coords  = d["coords"]
            if "noise_model_json" in d and nm_json is None: nm_json = str(d["noise_model_json"][0])
            if "seq_kwargs_json"  in d and sq_json is None: sq_json = str(d["seq_kwargs_json"][0])

        n_all = np.stack(arrays_n)   # (n_traj+1, n_times, n_sites)
        c_all = np.stack(arrays_c)
        fname     = make_filename(args.seq_kwargs, len(arrays_n) - 1, args.max_chi, timestamp)
        save_path = out_dir / (fname + ".npz")
        save_kw   = dict(n_traj=n_all, c_traj=c_all,
                         times=np.array(times),
                         total_duration=np.array([total_dur]))
        if coords  is not None: save_kw["coords"]           = coords
        if nm_json is not None: save_kw["noise_model_json"] = np.array([nm_json])
        if sq_json is not None: save_kw["seq_kwargs_json"]  = np.array([sq_json])
        np.savez(save_path, **save_kw)
        print(f"Saved → {save_path}  (shape: {n_all.shape})")
        print(save_path)
        return

    print("RUNS ON: this machine or a SLURM GPU node — nothing is submitted "
          "and nothing is billed.\n  The only cloud call reads the device's "
          "noise model, which is free.")

    # ── Load or fetch noise model ─────────────────────────────────────────────
    if args.noise_model_json:
        from pulser.noise_model import NoiseModel
        noise_model = NoiseModel.from_abstract_repr(Path(args.noise_model_json).read_text())
        print(f"Loaded noise model from {args.noise_model_json}")
    else:
        print(f"Fetching {args.device_name} noise model from Pasqal cloud SDK...")
        _, noise_model = fetch_fcan1(args.device_name, override_T2_us=args.device_T2,
                                 override_temperature_uK=args.device_temperature,
                                 override_detuning_sigma=args.device_detuning_sigma)
        print_noise_model_summary(noise_model, args.device_name)

    # The source's own noise model, when the spec carries one. Never silent: the
    # difference is printed whichever way the choice goes.
    if args.spec:
        spec_dict = json.loads(Path(args.spec).read_text())
        wanted    = (spec_dict.get("noise_model") or {}).get("params") or {}
        device_params = {k: getattr(noise_model, k, "—") for k in wanted}
        _, noise_model, _ = spec_noise.resolve(
            args.noise_source, spec_dict, noise_model, device_params)[0]
    elif args.noise_source != "device":
        parser.error("--noise-source needs --spec: the source's noise model is "
                     "recorded in the spec, not in the sequence file")

    if args.seq_file is None:
        parser.error("--seq-file is required unless using --save-noise-model or --merge")

    # ── Build nominal sequence ─────────────────────────────────────────────────
    builder     = load_builder(args.seq_file, args.fn_name)
    seq_nominal = builder(**args.seq_kwargs)

    n_sites   = len(seq_nominal.register.qubit_ids)
    qubit_ids = seq_nominal.register.qubit_ids
    coords    = np.array([seq_nominal.register.qubits[q] for q in qubit_ids])

    print(f"Sequence: {n_sites} qubits  |  duration = {seq_nominal.get_duration()} ns")
    print(f"Register coords shape: {coords.shape}\n")

    # ── Evaluation times (evenly spaced on normalised axis, rounded to dt grid) ─
    # Start from total/n_times so the final point is always total (not dt).
    # np.linspace(dt, total, 1) would return [dt], not [total] — the wrong end.
    _total_ns = seq_nominal.get_duration()
    raw_times_ns = np.clip(
        np.round(np.linspace(_total_ns / args.n_times, _total_ns, args.n_times) / args.dt
                 ).astype(int) * args.dt,
        args.dt, _total_ns,
    )
    eval_times = (raw_times_ns / _total_ns).tolist()

    occupation  = Occupation(evaluation_times=eval_times)
    correlation = CorrelationMatrix(evaluation_times=eval_times)
    _obs = [occupation, correlation]
    if args.bitstrings > 0:
        # Sample ONLY at the final time. Bitstring sampling needs the full state, so
        # doing it at all n_times would multiply cost and file size for snapshots we
        # never analyse -- every observable we want from shots (<|m|>, higher moments)
        # is an end-of-ramp quantity.
        _obs.append(BitStrings(evaluation_times=[1.0], num_shots=args.bitstrings))

    mps_base = dict(
        with_modulation        = True,
        dt                     = args.dt,
        max_bond_dim           = args.max_chi,
        precision              = 1e-16,
        extra_krylov_tolerance = 1e4,
        observables            = _obs,
        autosave_dt            = int(1e9),   # effectively disabled — MPS snapshots are too heavy
    )

    # ── Mode: single trajectory (parallel SLURM) ─────────────────────────────
    if args.run_id is not None:
        out_file = out_dir / f"partial_{args.run_id}.npz"
        if out_file.exists():
            print(f"Already done: {out_file}"); return

        if args.run_id == 0:
            print(f"[run_id=0] Noiseless trajectory...")
            config = MPSConfig(**mps_base)
        else:
            print(f"[run_id={args.run_id}/{args.n_traj}] Noisy trajectory...")
            config = MPSConfig(**mps_base, noise_model=noise_model)

        n_arr, c_arr, times, total_dur, bits = run_one_trajectory(seq_nominal, config)
        np.savez(out_file,
                 n=n_arr, c=c_arr,
                 times=np.array(times),
                 total_duration=np.array([total_dur]),
                 run_id=np.array([args.run_id]),
                 coords=coords,
                 bitstrings_json=np.array([json.dumps(bits) if bits else ""]),
                 noise_model_json=np.array([noise_model.to_abstract_repr()]),
                 seq_kwargs_json=np.array([json.dumps(args.seq_kwargs)]))
        print(f"Saved → {out_file}")
        return

    # ── Noiseless trajectory (always at nominal — the user's exact design) ───
    print(f"[0]  Noiseless trajectory (nominal)...")
    n_nl, c_nl, times, total_dur, _ = run_one_trajectory(
        seq_nominal, MPSConfig(**mps_base)
    )
    print(f"  → {len(times)} time points, total_duration = {total_dur:.1f} ns")

    # ── Noisy trajectories at nominal — only run when no QPU manifest given ──
    # When a QPU manifest IS given, the QPU-matched trajectories below replace
    # these. Running both would waste compute for a curve we don't show.
    mps_noisy  = MPSConfig(**mps_base, noise_model=noise_model)
    if not args.qpu_manifest:
        n_traj_arr = np.zeros((args.n_traj, len(times), n_sites), dtype=np.float64)
        c_traj_arr = np.zeros((args.n_traj, len(times), n_sites, n_sites), dtype=np.float64)
        for i in range(args.n_traj):
            print(f"[{i+1}/{args.n_traj}]  Noisy trajectory (nominal)...", flush=True)
            n_traj_arr[i], c_traj_arr[i], _, _, _ = run_one_trajectory(seq_nominal, mps_noisy)
    else:
        # Placeholder — n_traj will only contain the noiseless run (index 0).
        # All noisy trajectories go into n_traj_qpu below.
        n_traj_arr = np.zeros((0, len(times), n_sites), dtype=np.float64)
        c_traj_arr = np.zeros((0, len(times), n_sites, n_sites), dtype=np.float64)

    # ── Assemble: index 0 = noiseless nominal  ────────────────────────────────
    n_all = np.concatenate([n_nl[np.newaxis], n_traj_arr], axis=0)
    c_all = np.concatenate([c_nl[np.newaxis], c_traj_arr], axis=0)

    # ── QPU-matched noisy trajectories ────────────────────────────────────────
    # If a QPU manifest is provided, run N additional noisy trajectories at the
    # calibrated parameters the QPU was actually submitted with. This is the
    # physically meaningful comparison: same sequence + same noise model.
    #
    # Convention (submit_qpu.py submits WITH compensation):
    #   omega_quench  = omega_nominal / omega_ratio  → builder omega_offset = 1/ratio
    #   delta_quench  = delta_nominal + delta_off    → builder delta_offset = delta_off/(2π)
    #   R_offset      = manifest["R_offset"]
    n_traj_qpu, c_traj_qpu, qpu_offset_kw = None, None, {}

    if args.qpu_manifest:
        with open(args.qpu_manifest) as f:
            qpu_manifest = json.load(f)

        calib  = qpu_manifest.get("calibration", {})
        r_off  = qpu_manifest.get("R_offset", 1.0)
        om_ratio   = calib.get("omega_ratio",  1.0)
        delta_off  = calib.get("delta_offset", 0.0)   # rad/µs

        # Convert to builder kwargs (builder adds 2π×delta_offset to detuning in rad/µs)
        qpu_offset_kw = {
            "omega_offset": 1.0 / om_ratio,
            "delta_offset": delta_off / (2 * np.pi),   # rad/µs → MHz-like builder units
            "R_offset":     r_off,
        }
        # qpu-submit records the kwargs it actually passed to the builder. Prefer
        # them: the derivation above cannot know about a compensation capped at
        # the channel maximum, and replaying an uncapped Ω would compare the
        # emulation against a sequence the QPU never ran.
        qpu_offset_kw.update(qpu_manifest.get("builder_kwargs", {}))

        print(f"\n{'='*62}")
        print(f"  QPU manifest: {Path(args.qpu_manifest).name}")
        print(f"  Measured offsets from calibration:")
        print(f"    omega_ratio  = {om_ratio:.5f}  (hardware Ω / setpoint)")
        print(f"    delta_offset = {delta_off/(2*np.pi):+.4f} MHz  ({delta_off:+.4f} rad/µs)")
        print(f"    R_offset     = {r_off:.4f}")
        print(f"  QPU was submitted with compensation → QPU ran at:")
        print(f"    omega_quench  = omega × {1/om_ratio:.5f}")
        print(f"    delta_quench  = delta_nom + {delta_off/(2*np.pi):+.4f} MHz")
        print(f"  Trajectory [0] of these will be shown as the 'noisy nominal' single")
        print(f"  reference line; all {args.n_traj} form the QPU-matched envelope.")
        print(f"{'='*62}\n")

        seq_qpu = builder(**{**args.seq_kwargs, **qpu_offset_kw})
        mps_qpu = MPSConfig(**mps_base, noise_model=noise_model)
        n_traj_qpu = np.zeros((args.n_traj, len(times), n_sites), dtype=np.float64)
        c_traj_qpu = np.zeros((args.n_traj, len(times), n_sites, n_sites), dtype=np.float64)

        for i in range(args.n_traj):
            label = "(noisy nominal ref)" if i == 0 else ""
            print(f"[{i+1}/{args.n_traj}]  Noisy QPU-matched {label}", flush=True)
            n_traj_qpu[i], c_traj_qpu[i], _, _, _ = run_one_trajectory(seq_qpu, mps_qpu)

        print(f"  Done. [0] = single noisy nominal; [0..{args.n_traj-1}] = envelope.\n")

    # ── Calibration offset sweeps (noiseless only — fast) ─────────────────────
    cal_n, cal_c, cal_labels = None, None, []
    if args.cal_offsets:
        print(f"\nCalibration offset sweeps ({2*len(args.cal_offsets)} noiseless runs)...")
        cal_n, cal_c, cal_labels = run_calibration_sweeps(
            builder, args.seq_kwargs, mps_base, args.cal_offsets
        )
        print(f"  Done. {len(cal_labels)} offset curves computed.\n")

    # ── Save .npz ─────────────────────────────────────────────────────────────
    fname     = make_filename(args.seq_kwargs, args.n_traj, args.max_chi, timestamp)
    save_path = out_dir / (fname + ".npz")

    save_kw = dict(
        n_traj           = n_all,
        c_traj           = c_all,
        times            = times,
        total_duration   = np.array([total_dur]),
        coords           = coords,
        noise_model_json = np.array([noise_model.to_abstract_repr()]),
        seq_kwargs_json  = np.array([json.dumps(args.seq_kwargs)]),
    )
    if cal_n is not None:
        save_kw["cal_n"]          = cal_n
        save_kw["cal_c"]          = cal_c
        save_kw["cal_labels_json"]= np.array([json.dumps(cal_labels)])

    if n_traj_qpu is not None:
        save_kw["n_traj_qpu"]    = n_traj_qpu
        save_kw["c_traj_qpu"]    = c_traj_qpu
        save_kw["qpu_offset_json"]= np.array([json.dumps(qpu_offset_kw)])

    np.savez(save_path, **save_kw)
    print(f"\n{'='*62}")
    print(f"  Saved → {save_path}")
    print(f"  n_traj shape : {n_all.shape}  (index 0 = noiseless)")
    print(f"  c_traj shape : {c_all.shape}")
    if cal_n is not None:
        print(f"  cal_n  shape : {cal_n.shape}  ({len(cal_labels)} offset curves)")
    if n_traj_qpu is not None:
        print(f"  n_traj_qpu   : {n_traj_qpu.shape}  (QPU-matched noisy, NO index 0)")
        print(f"  QPU offsets  : {qpu_offset_kw}")
    print(f"{'='*62}\n")
    print(save_path)   # last line: machine-readable path for the skill agent


if __name__ == "__main__":
    main()
