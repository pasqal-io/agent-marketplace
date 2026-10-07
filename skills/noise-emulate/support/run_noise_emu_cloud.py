#!/usr/bin/env python3
"""Cloud noise emulation — time-evolution envelope on Pasqal Cloud EMU_MPS.

RUNS ON: Pasqal Cloud emulators (EMU_MPS). Metered emulator time, not QPU
shots. A diagnostic, not the gate: validate-emu decides whether to submit.

No GPU needed: every trajectory runs on the Pasqal Cloud emulator fleet.

Unlike the local-GPU noise-emulate (qpu-internal plugin), which samples the
state at many evaluation times along ONE simulated evolution, the cloud
version builds ONE SEQUENCE PER OBSERVATION TIME (the same thing the real
QPU does) and submits each as an EMU_MPS batch:

  - 1 noiseless batch per time point
  - 1 noisy batch per time point (FC1 calibrated noise model)   [default]
  - optionally K extra independent noisy batches per time point
    (--n-envelope K) to estimate a quantile envelope client-side

Usage:
    python run_noise_emu_cloud.py \\
        --seq-file   seq_builder.py \\
        --seq-kwargs '{"N": 5, "hx": 6.0}' \\
        --t-max      4000 \\
        [--t-var t] [--t-min 16] [--n-times 15] [--t-list "[16,100,500]"] \\
        [--shots 500] [--n-envelope 0] [--poll 30] \\
        [--T2 <us>] [--temperature <uK>] [--detuning-sigma <rad/us>] \\
        [--resume] \\
        --out-dir results/noise_emu_cloud/

The sequence file must follow the spec-to-sequence contract:
    build_sequence(device=None, **params) -> pulser.Sequence   (non-parametric)
    compute_observable(counts: dict[str, int]) -> float
The observation time is passed to build_sequence as the --t-var kwarg (ns).

Outputs (in --out-dir):
    batch_ids.json           all submitted batch IDs (written immediately)
    noise_emu_cloud.json     per-time records: noiseless, noisy, quantiles
Use plot_noise_emu_cloud.py to render the envelope figure (.png).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import spec_noise
from batch_tags import build_tags
from pasqal_auth import account_summary, ensure_credentials

_CLOCK_NS = 4  # FC1 sequence durations must be multiples of 4 ns


def _load_seq_module(path: str):
    spec = importlib.util.spec_from_file_location("seq_mod", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _counts_from_job(job) -> dict[str, int]:
    fr = getattr(job, "full_result", None)
    if isinstance(fr, dict):
        return dict(fr.get("counter") or {})
    return {}


def _cloud_noise_model(device, t2_us: float | None = None,
                       temperature_uk: float | None = None,
                       detuning_sigma: float | None = None) -> tuple:
    """Noise model for cloud EMU_MPS, defaulting to the device's shipped values.

    Built from scratch rather than replacing fields on the device model: the
    device model carries state_prep_error and register/trap-noise fields that
    crash cloud EMU_MPS execution. Same construction as validate-emu.
    Optional args override individual fields; None keeps the shipped value.

    Returns (noise_model, overridable_noise_params) — the second being only the
    three fields a caller can override here, which is what the source-vs-device
    difference report compares. The rest are taken from the device as shipped.
    """
    from pulser.noise_model import NoiseModel
    nm = getattr(device, "noise_model", None)
    dephasing_rate = (1.0 / t2_us) if t2_us else getattr(nm, "dephasing_rate", 0.05)
    temperature    = (temperature_uk if temperature_uk is not None
                      else getattr(nm, "temperature", 20.0))
    det_sigma      = (detuning_sigma if detuning_sigma is not None
                      else getattr(nm, "detuning_sigma", 0.0))
    noise_model = NoiseModel(
        temperature=temperature,
        dephasing_rate=dephasing_rate,
        detuning_sigma=det_sigma,
        relaxation_rate=getattr(nm, "relaxation_rate", 0.01),
        amp_sigma=getattr(nm, "amp_sigma", 0.01),
        p_false_pos=getattr(nm, "p_false_pos", 0.015),
        p_false_neg=getattr(nm, "p_false_neg", 0.09),
        laser_waist=getattr(nm, "laser_waist", None),
    )
    overridable_noise_params = {
        "T2_us":                round(1.0 / dephasing_rate, 3) if dephasing_rate else None,
        "temperature_uk":       temperature,
        "detuning_sigma_radus": det_sigma,
    }
    return noise_model, overridable_noise_params


def _round_clock(t: float) -> int:
    return max(_CLOCK_NS * 4, int(round(t / _CLOCK_NS) * _CLOCK_NS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq-file",   required=True,
                    help="sequence file with build_sequence() and compute_observable()")
    ap.add_argument("--fn-name",    default="build_sequence")
    ap.add_argument("--seq-kwargs", default="{}", type=json.loads,
                    help="fixed kwargs for the builder (JSON), excluding the time variable")
    ap.add_argument("--t-var",      default="t",
                    help="name of the builder kwarg that carries the observation time in ns")
    ap.add_argument("--t-min",      type=float, default=16)
    ap.add_argument("--t-max",      type=float, default=None)
    ap.add_argument("--n-times",    type=int, default=15,
                    help="number of observation times between t-min and t-max")
    ap.add_argument("--t-list",     default=None, type=json.loads,
                    help="explicit JSON list of observation times in ns (overrides t-min/t-max/n-times)")
    ap.add_argument("--shots",      type=int, default=500)
    ap.add_argument("--n-envelope", type=int, default=0,
                    help="extra independent noisy batches per time point for a "
                         "quantile envelope (0 = mean curve only). Batch count is "
                         "n_times*(2+K) — keep K and n_times modest.")
    ap.add_argument("--poll",       type=int, default=30)
    ap.add_argument("--device-name", default="FRESNEL_CAN1")
    ap.add_argument("--T2",         type=float, default=None,
                    help="override effective dephasing T2 in us [default: device value]")
    ap.add_argument("--temperature", type=float, default=None,
                    help="override atom temperature in uK [default: device value]")
    ap.add_argument("--detuning-sigma", type=float, default=None,
                    help="override shot-to-shot detuning sigma in rad/us [default: device value]")
    ap.add_argument("--resume",     action="store_true",
                    help="skip submission and re-poll the batches in <out-dir>/batch_ids.json")
    ap.add_argument("--out-dir",    required=True)
    ap.add_argument("--project-id", default=None,
                    help="the project the user chose to pay for this emulation. "
                         "Required: run `python pasqal_auth.py --whoami` first, "
                         "show them the projects and credits, and ask.")
    ap.add_argument("--spec",       default=None,
                    help="the experiment_spec.json this sequence came from. "
                         "Used for the batch labels and, if it carries a noise "
                         "model of its own, for --noise-source.")
    ap.add_argument("--tag",        action="append", default=[],
                    help="extra batch label, in the user's own words; repeatable")
    ap.add_argument("--noise-source", default="device",
                    choices=("device", "paper"),
                    help="whose noise model to emulate: this device's (default) "
                         "or the one the source described (needs --spec)")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ids_file = out / "batch_ids.json"
    # A plain re-run into a directory that already records batches would pay
    # for the scan twice and overwrite the first set of IDs. Refuse before the
    # credential load, as validate-emu's run_emu_scan.py does.
    if ids_file.exists() and not args.resume:
        raise SystemExit(
            f"✘ {ids_file} already exists — this scan was already submitted.\n"
            "  Poll the batches it recorded:  --resume\n"
            "  Or submit a genuinely new scan into a different --out-dir.")

    if args.t_list is not None:
        times = sorted({_round_clock(t) for t in args.t_list})
    else:
        if args.t_max is None and not args.resume:
            ap.error("--t-max is required (or pass --t-list / --resume)")
        if args.t_max is not None:
            times = sorted({_round_clock(t) for t in
                            np.linspace(args.t_min, args.t_max, args.n_times)})
        else:
            times = []

    mod         = _load_seq_module(args.seq_file)
    builder     = getattr(mod, args.fn_name)
    compute_obs = mod.compute_observable

    creds, _ = ensure_credentials(project_id=args.project_id,
                                  require_explicit_project=True)
    from pasqal_cloud import PasqalCloudConnection
    from pasqal_cloud.device import DeviceTypeName
    from pasqal_cloud.job import CreateJob
    from pasqal_cloud.pasqal_cloud_client import PasqalCloudClient
    from pulser.backend import EmulationConfig
    from pulser.backend.default_observables import BitStrings

    conn   = PasqalCloudConnection(**creds)
    device = conn.fetch_available_devices()[args.device_name]
    sdk    = PasqalCloudClient(**creds)

    noise_model, overridable_noise_params = _cloud_noise_model(
        device, args.T2, args.temperature, args.detuning_sigma)

    # A spec is optional here — this skill can be pointed at a bare sequence
    # file — but without one there is no source noise model to offer and no
    # experiment name for the labels.
    spec = (json.loads(Path(args.spec).read_text()) if args.spec else
            {"experiment_name": Path(args.seq_file).stem,
             "scan": {"variable": args.t_var}})
    noise_label, noise_model, overridable_noise_params = spec_noise.resolve(
        args.noise_source, spec, noise_model, overridable_noise_params)[0]
    tags = build_tags(spec, args.device_name, args.shots, "noise-emulate",
                      extra=args.tag) + [f"noise:{noise_label}"]

    noisy_cfg = EmulationConfig(
        noise_model=noise_model,
        # n_trajectories left unset: the backend resolves it from its own
        # configuration. The envelope comes from the --n-envelope repeated
        # batches anyway, not from trajectory averaging inside one.
        observables=[BitStrings(evaluation_times=[1.0], num_shots=args.shots)],
    ).to_abstract_repr()

    # ── submit (or resume) ────────────────────────────────────────────────────
    if args.resume:
        if not ids_file.exists():
            raise FileNotFoundError(f"--resume: {ids_file} not found")
        saved       = json.loads(ids_file.read_text())
        times       = [int(t) for t in saved["times"]]
        nl_batches  = {int(k): v for k, v in saved["noiseless"].items()}
        n_batches   = {int(k): v for k, v in saved["noisy"].items()}
        env_batches = {int(k): v for k, v in saved.get("envelope", {}).items()}
        print(f"=== noise-emulate (cloud, RESUME): {len(times)} time points ===")
    else:
        n_batch_total = len(times) * (2 + args.n_envelope)
        print("RUNS ON: Pasqal Cloud emulators (EMU_MPS) — metered.")
        print(f"=== noise-emulate (cloud): {Path(args.seq_file).stem} ===")
        print(account_summary(sdk, creds["project_id"], creds.get("region"),
                              creds.get("username")))
        print(f"  labels: {', '.join(tags)}")
        print(f"  {args.t_var} ∈ {times} ns  ({len(times)} points)")
        print(f"  shots={args.shots}  device={args.device_name}  "
              f"envelope K={args.n_envelope}  →  {n_batch_total} EMU_MPS batches")
        # The source's model carries different fields from the device's, so
        # print whatever it actually has rather than assuming the device's keys.
        print("  noise model: " + ",  ".join(
            f"{k}={v}" for k, v in overridable_noise_params.items() if k != "source"))
        print(f"  noise source: {overridable_noise_params.get('source', noise_label)}\n")

        nl_batches:  dict[int, str] = {}
        n_batches:   dict[int, str] = {}
        env_batches: dict[int, list[str]] = {}

        for t in times:
            seq = builder(device=device, **{**args.seq_kwargs, args.t_var: t})
            srz = seq.to_abstract_repr()

            b = sdk.create_batch(serialized_sequence=srz,
                                 jobs=[CreateJob(runs=args.shots)],
                                 device_type=DeviceTypeName.EMU_MPS, wait=False,
                                 tags=tags + ["backend:emu-noiseless",
                                              f"t:{t}"])
            nl_batches[t] = str(b.id)

            b = sdk.create_batch(serialized_sequence=srz,
                                 jobs=[CreateJob(runs=args.shots)],
                                 device_type=DeviceTypeName.EMU_MPS, wait=False,
                                 backend_configuration=noisy_cfg,
                                 tags=tags + ["backend:emu-noisy", f"t:{t}"])
            n_batches[t] = str(b.id)

            env_batches[t] = []
            for _ in range(args.n_envelope):
                b = sdk.create_batch(serialized_sequence=srz,
                                     jobs=[CreateJob(runs=args.shots)],
                                     device_type=DeviceTypeName.EMU_MPS, wait=False,
                                     backend_configuration=noisy_cfg,
                                     tags=tags + ["backend:emu-envelope",
                                                  f"t:{t}"])
                env_batches[t].append(str(b.id))

            print(f"  [submitted] {args.t_var}={t}  "
                  f"nl={nl_batches[t][:8]}…  noisy={n_batches[t][:8]}…"
                  + (f"  +{args.n_envelope} envelope" if args.n_envelope else ""),
                  flush=True)

        ids_file.write_text(json.dumps({
            "ts":       time.strftime("%Y-%m-%dT%H:%M:%S"),
            "seq_file": args.seq_file,
            "t_var":    args.t_var,
            "times":    times,
            "shots":    args.shots,
            "noiseless": {str(k): v for k, v in nl_batches.items()},
            "noisy":     {str(k): v for k, v in n_batches.items()},
            "envelope":  {str(k): v for k, v in env_batches.items()},
            "overridable_noise_params": overridable_noise_params,
        }, indent=2))
        print(f"\n  batch_ids saved → {ids_file}  "
              f"(re-poll later with --resume)\n")

    # ── poll ─────────────────────────────────────────────────────────────────
    def poll_all(batch_map: dict[int, str], label: str) -> dict[int, dict]:
        pending, done, t0 = set(batch_map), {}, time.time()
        while pending:
            for t in sorted(pending):
                B  = sdk.get_batch(batch_map[t])
                st = B.ordered_jobs[0].status
                if st == "DONE":
                    done[t] = _counts_from_job(B.ordered_jobs[0])
                    pending.discard(t)
                    print(f"  [{label} DONE] {args.t_var}={t}  "
                          f"{sum(done[t].values())} shots  "
                          f"({time.time()-t0:.0f}s)", flush=True)
                elif st in ("ERROR", "CANCELED", "TIMED_OUT"):
                    print(f"  [{label} {st}] {args.t_var}={t}  skip")
                    pending.discard(t)
            if pending:
                time.sleep(args.poll)
        return done

    nl_counts = poll_all(nl_batches, "noiseless")
    n_counts  = poll_all(n_batches,  "noisy")
    env_counts: dict[int, list[dict]] = {}
    for t, ids in (env_batches or {}).items():
        if ids:
            got = poll_all(dict(enumerate(ids)), f"env t={t}")
            env_counts[t] = [got[i] for i in sorted(got)]

    # ── records ──────────────────────────────────────────────────────────────
    records = []
    identical_env_warned = False
    for t in times:
        nl_c = nl_counts.get(t, {})
        n_c  = n_counts.get(t, {})
        rec = {
            "t":              t,
            "noiseless_obs":  compute_obs(nl_c) if nl_c else float("nan"),
            "noisy_obs":      compute_obs(n_c)  if n_c  else float("nan"),
            "n_shots":        sum(n_c.values()),
            "batch_noiseless": nl_batches.get(t, ""),
            "batch_noisy":     n_batches.get(t, ""),
        }
        env = env_counts.get(t, [])
        if env:
            vals = [compute_obs(c) for c in env if c] + \
                   ([rec["noisy_obs"]] if n_c else [])
            vals = [v for v in vals if not np.isnan(v)]
            if len(set(json.dumps(c, sort_keys=True) for c in env)) == 1 \
                    and len(env) > 1 and not identical_env_warned:
                print("  ⚠ envelope batches returned identical counts — server "
                      "seeding may be deterministic; envelope is not meaningful.")
                identical_env_warned = True
            if vals:
                q = np.quantile(vals, [0.10, 0.25, 0.50, 0.75, 0.90])
                rec.update(env_n=len(vals),
                           q10=float(q[0]), q25=float(q[1]), median=float(q[2]),
                           q75=float(q[3]), q90=float(q[4]))
        records.append(rec)

    result = {
        "ts":       time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backend":  "EMU_MPS_cloud",
        "device":   args.device_name,
        "seq_file": args.seq_file,
        "t_var":    args.t_var,
        "shots":    args.shots,
        "n_envelope": args.n_envelope,
        "overridable_noise_params": overridable_noise_params,
        "records": records,
    }
    res_file = out / "noise_emu_cloud.json"
    res_file.write_text(json.dumps(result, indent=2))

    # ── summary ──────────────────────────────────────────────────────────────
    print(f"\n=== cloud noise emulation summary ===")
    print(f"  {'t (ns)':>8}  {'noiseless':>12}  {'noisy':>12}")
    for r in records:
        print(f"  {r['t']:>8}  {r['noiseless_obs']:>12.4f}  {r['noisy_obs']:>12.4f}")
    print(f"\n  Results: {res_file}")


if __name__ == "__main__":
    main()
