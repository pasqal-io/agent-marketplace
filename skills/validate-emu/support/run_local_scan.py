#!/usr/bin/env python3
"""Local emulator scan — noiseless + noisy, on this machine, no cloud, no cost.

The same spec + sequence contract as the cloud runner and the same output files,
so `plot_emu_scan.py` and `harvest-and-analyze` read either one unchanged. What
differs is where it runs and what it is worth: exact state-vector emulation on
the CPU, which is free and immediate but caps out around a dozen atoms.

Run this first. It answers "is the implementation right, and does the observable
respond to the scan at all" for the price of a few seconds, and it needs no
account. The cloud scan then answers the question this one cannot: does the
signal survive the *live* device's noise at the *real* register size.

Two things this deliberately does not pretend:

  · Without --live-device the noise model is a documented stand-in, not the
    device's. A noisy verdict from it is indicative, not a hardware go-ahead —
    `verdict.json` says so in `gates_hardware`.
  · A register that fits here is usually smaller than the one you want to run.
    Scaling N down changes the physics; the point is to catch implementation
    errors before paying for the real size, not to substitute for it.

Usage:
    python run_local_scan.py \\
        --spec       experiment_spec.json \\
        --seq-file   my_experiment_sequence.py \\
        --out-dir    results/my_experiment/emu_local/ \\
        [--shots 200] [--noiseless-only] [--max-atoms 14] \\
        [--seq-kwargs '{"N": 3}'] [--live-device]

Outputs (in --out-dir), same schema as the cloud scan:
    emu_noiseless.json   observable scan curve, noiseless
    emu_noise.json       observable scan curve, noisy
    verdict.json         {go, reasons, retention, scope, gates_hardware}
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

# Qutip emulates the full state vector: cost is exponential in the atom count,
# and the noisy path carries a density matrix, so it turns over sooner. These
# are measured, not guessed — 9 atoms noisy takes seconds, 16 does not finish.
DEFAULT_MAX_ATOMS = 14
NOISY_MAX_ATOMS   = 12

# Fallback noise magnitudes, used only when no live device is fetched. Same
# values the cloud runner falls back to, so the two agree on what "typical"
# means; none of them is a measurement of the machine you will submit to.
STANDIN_NOISE = {
    "dephasing_rate":  0.05,
    "relaxation_rate": 0.01,
    "p_false_pos":     0.015,
    "p_false_neg":     0.09,
}


def _load_seq_module(path: str):
    spec = importlib.util.spec_from_file_location("seq_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _resolve_device(name: str, live: bool):
    """Return (device, description, is_live).

    Fetching live specs costs nothing — it reads the device description, not
    emulator time — but it needs credentials, so it stays opt-in.
    """
    if live:
        from pasqal_auth import load_credentials
        from pasqal_cloud.pasqal_cloud_client import PasqalCloudClient
        from pulser.json.abstract_repr.deserializer import deserialize_device
        specs = PasqalCloudClient(**load_credentials()).get_device_specs_dict()
        if name not in specs:
            raise SystemExit(f"✘ device {name!r} not available in this project. "
                             f"Available: {sorted(specs)}")
        return deserialize_device(specs[name]), f"{name} (live specs)", True

    import pulser.devices as devices
    for candidate in (name, "AnalogDevice"):
        device = getattr(devices, candidate, None)
        if device is not None:
            if candidate != name:
                print(f"  {name} is not a device Pulser ships; standing in with "
                      f"{candidate}")
            return device, f"{candidate} (Pulser bundled stand-in)", False
    raise SystemExit("✘ Pulser ships no AnalogDevice to stand in with")


def _noise_model(device, is_live: bool):
    """Build the noise model and say where every number came from."""
    from pulser.noise_model import NoiseModel
    live_nm = getattr(device, "noise_model", None) if is_live else None
    fields  = {k: getattr(live_nm, k, v) for k, v in STANDIN_NOISE.items()}
    params  = dict(fields)
    params["source"] = ("live device noise model" if live_nm is not None
                        else "stand-in constants, not this device's calibration")
    return NoiseModel(**fields), params, live_nm is not None


def main():
    ap = argparse.ArgumentParser(
        description="Emulate a spec-driven scan locally, noiseless and noisy.")
    ap.add_argument("--spec",           required=True)
    ap.add_argument("--seq-file",       required=True)
    ap.add_argument("--out-dir",        required=True)
    ap.add_argument("--shots",          type=int, default=200,
                    help="shots per scan point (default 200; local shots are free "
                         "but the emulation behind them is not)")
    ap.add_argument("--noiseless-only", action="store_true")
    ap.add_argument("--max-atoms",      type=int, default=DEFAULT_MAX_ATOMS,
                    help=f"refuse a register larger than this (default "
                         f"{DEFAULT_MAX_ATOMS}); raising it is how a scan runs "
                         "for hours instead of seconds")
    ap.add_argument("--seq-kwargs",     default="{}",
                    help='JSON overriding the spec\'s fixed_params, to shrink the '
                         'register for a local run: \'{"N": 3}\'')
    ap.add_argument("--device",         default=None,
                    help="device name (default: spec.device)")
    ap.add_argument("--live-device",    action="store_true",
                    help="fetch the real device specs and noise model from the "
                         "cloud (needs credentials, costs no emulator time) "
                         "instead of using Pulser's bundled stand-in")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    out  = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    scan     = spec["scan"]
    variable = scan["variable"]
    values   = scan["values"]
    fixed    = {**scan.get("fixed_params", {}), **json.loads(args.seq_kwargs)}

    mod            = _load_seq_module(args.seq_file)
    build_sequence = getattr(mod, spec.get("builder_fn", "build_sequence"))
    compute_obs    = mod.compute_observable

    device, device_desc, is_live = _resolve_device(
        args.device or spec["device"], args.live_device)

    print(f"=== validate-emu (local): {spec['experiment_name']} ===")
    print(f"  device   {device_desc}")
    print(f"  {variable} ∈ {values}")
    print(f"  shots={args.shots}  overrides={json.loads(args.seq_kwargs) or 'none'}")

    from pulser_simulation import QutipBackendV2
    from pulser.backend import EmulationConfig
    from pulser.backend.default_observables import BitStrings

    noise, noise_params, live_noise = (None, None, False)
    if not args.noiseless_only:
        noise, noise_params, live_noise = _noise_model(device, is_live)
        print(f"  noise    {noise_params['source']}")
    print()

    # Size is checked on a real build rather than on spec["register"]["N_atoms"],
    # because --seq-kwargs may have shrunk it and the builder is the only thing
    # that knows the resulting register.
    probe    = build_sequence(device=device, **{**fixed, variable: values[0]})
    n_atoms  = len(probe.register.qubits)
    if n_atoms > args.max_atoms:
        raise SystemExit(
            f"✘ {n_atoms} atoms is past the local emulator's reach "
            f"(--max-atoms {args.max_atoms}).\n"
            "  Shrink the register for a local check — --seq-kwargs "
            "'{\"N\": 3}' or whatever your builder takes — to verify the\n"
            "  implementation and the observable, then run the real size where "
            "it fits:\n"
            "    · run_emu_scan.py         cloud emulator, live noise model, "
            "the verdict that gates hardware\n"
            "    · noise-emulate           MPS emulator locally, on a GPU "
            "cluster, or in the cloud — larger N\n"
            "  Exact state-vector emulation costs 2^N; this is a wall, not a "
            "tuning parameter.")
    if noise is not None and n_atoms > NOISY_MAX_ATOMS:
        print(f"  {n_atoms} atoms is heavy for the noisy path "
              f"(> {NOISY_MAX_ATOMS}); it carries a density matrix. Expect "
              "minutes per point.\n")

    def run_point(val, noise_model):
        seq = build_sequence(device=device, **{**fixed, variable: val})
        cfg = EmulationConfig(
            observables=[BitStrings(evaluation_times=[1.0], num_shots=args.shots)],
            noise_model=noise_model,
        )
        results = QutipBackendV2(seq, config=cfg).run()
        return dict(results.get_tagged_results()["bitstrings"][-1])

    def scan_all(noise_model, label):
        records = []
        for val in values:
            t0     = time.time()
            counts = run_point(val, noise_model)
            obs    = compute_obs(counts) if counts else float("nan")
            records.append({
                "scan_value": val,
                "observable": obs,
                "n_shots":    sum(counts.values()),
                "n_unique":   len(counts),
                "batch_id":   "",          # local: nothing to look up later
            })
            print(f"  [{label}] {variable}={val}  obs={obs:.4f}  "
                  f"({time.time()-t0:.1f}s)", flush=True)
        return records

    nl_records = scan_all(None, "noiseless")
    n_records  = scan_all(noise, "noisy") if noise is not None else []

    def write(name, backend, records, extra=None):
        (out / name).write_text(json.dumps({
            "ts":            time.strftime("%Y-%m-%dT%H:%M:%S"),
            "experiment":    spec["experiment_name"],
            "backend":       backend,
            "device":        device_desc,
            "n_atoms":       n_atoms,
            "scan_variable": variable,
            "shots":         args.shots,
            "seq_kwargs":    fixed,
            **(extra or {}),
            "records":       records,
        }, indent=2))

    write("emu_noiseless.json", "qutip_local_noiseless", nl_records)
    if n_records:
        write("emu_noise.json", "qutip_local_noisy", n_records,
              {"noise_params": noise_params})

    # ── verdict ──────────────────────────────────────────────────────────────
    # Same fields as the cloud verdict, plus two that keep this one in its lane.
    verdict = {
        "go":             True,
        "reasons":        [],
        "scope":          "local emulator",
        "gates_hardware": False,
    }
    min_ret = spec.get("validation", {}).get("noise_retention_min", 0.50)

    nl_obs = [r["observable"] for r in nl_records if not np.isnan(r["observable"])]
    if not nl_obs and nl_records:
        # Every point nan, with shots in hand at every point, is not physics: the
        # observable rejected the bitstrings it was given. The usual cause is a
        # register-size mismatch — compute_observable closing over the spec's N
        # while --seq-kwargs emulated a smaller one, so every shot is discarded
        # as the wrong length and nan reads as "no signal". Say that, rather than
        # letting the user conclude the experiment failed.
        verdict["go"] = False
        verdict["reasons"].append(
            f"compute_observable returned nan at every point, though each ran "
            f"{args.shots} shots on {n_atoms} atoms. That is the observable "
            "rejecting the data, not an absent signal — check that it derives "
            "its geometry from the bitstring length rather than from a fixed N")
    elif not nl_obs or max(nl_obs) <= 0:
        verdict["go"] = False
        verdict["reasons"].append(
            "noiseless signal is zero or negative — the implementation or the "
            "scan range is wrong, and no amount of hardware will fix it")
    else:
        verdict["nl_max"] = float(max(nl_obs))

    n_obs = [r["observable"] for r in n_records if not np.isnan(r["observable"])]
    if nl_obs and n_obs and max(nl_obs) > 0:
        retention = max(n_obs) / max(nl_obs)
        verdict["n_max"]     = float(max(n_obs))
        verdict["retention"] = float(retention)
        if retention < min_ret:
            verdict["go"] = False
            verdict["reasons"].append(
                f"noise retention {retention:.0%} < threshold {min_ret:.0%}")
        else:
            verdict["reasons"].append(
                f"noise retention {retention:.0%} ≥ {min_ret:.0%}")

    if n_atoms < spec.get("register", {}).get("N_atoms", n_atoms):
        verdict["reasons"].append(
            f"emulated {n_atoms} atoms, the spec asks for "
            f"{spec['register']['N_atoms']} — a downsized check, not the experiment")
    if live_noise:
        verdict["reasons"].append(
            "noise model came from the live device, but at this register size "
            "only — the cloud scan is still what gates hardware")
    else:
        verdict["reasons"].append(
            "noise model is a stand-in, not this device's calibration")

    (out / "verdict.json").write_text(json.dumps(verdict, indent=2))

    # ── summary ──────────────────────────────────────────────────────────────
    print(f"\n=== local scan summary ({variable}, {n_atoms} atoms) ===")
    nl_map = {r["scan_value"]: r["observable"] for r in nl_records}
    n_map  = {r["scan_value"]: r["observable"] for r in n_records}
    print(f"  {'value':>10}  {'noiseless':>12}  {'noisy':>12}")
    for val in values:
        print(f"  {val:>10}  {nl_map.get(val, float('nan')):>12.4f}  "
              f"{n_map.get(val, float('nan')):>12.4f}")

    print(f"\n  Verdict: {'GO ✓' if verdict['go'] else 'NO-GO ✗'}  "
          "(local scope — does not authorise hardware)")
    for reason in verdict["reasons"]:
        print(f"    {reason}")
    print(f"\n  Results: {out}")
    print("  Next: run_emu_scan.py at the real register size for the verdict "
          "that gates a QPU submission.")


if __name__ == "__main__":
    main()
