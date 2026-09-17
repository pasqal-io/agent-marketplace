"""The noise model the source described, when it is not the device's.

A paper or a patent often states its own error budget — a T₂, a detection
fidelity, an atom temperature. Those numbers are part of the claim being
reproduced, and they are usually *not* the numbers the QPU you are about to use
will deliver. Both models answer a real question, and they answer different
ones:

  · the **device** model says what this machine will do to this signal. It is
    the only basis for a hardware recommendation.
  · the **paper** model says whether the source's claim reproduces under the
    source's own assumptions. A disagreement between the two is a result, not a
    bug.

So this module never picks. `idea-to-spec` records what the source said in
`spec["noise_model"]`, this prints the difference field by field, and the user
chooses with `--noise-source`. What is forbidden is the silent option: running
the paper's optimistic T₂ and reporting the retention as if the device had given
it.

This file is vendored byte-identical into each skill's `support/` directory, so
a skill keeps working when installed or copied on its own. Edit one copy and
`scripts/check_manifests.py` fails until the others match.
"""
from __future__ import annotations

CHOICES = ("device", "paper", "both")


def spec_noise_params(spec: dict) -> dict | None:
    """The source's own noise parameters, or None if it stated none.

    `source: "device"` means the spec is deliberately deferring to the machine,
    which is not the same as a spec that never mentioned noise — but both mean
    there is nothing here to choose between.
    """
    block = spec.get("noise_model") or {}
    params = block.get("params") or {}
    if not params or block.get("source") in (None, "device"):
        return None
    return dict(params)


def _accepted_fields(NoiseModel: type) -> set[str]:
    """Which keyword arguments this Pulser version's NoiseModel takes."""
    import inspect
    return set(inspect.signature(NoiseModel).parameters) - {"self", "kwargs"}


def build_spec_noise(spec: dict) -> tuple:
    """(NoiseModel, params) from the spec's block, or (None, None).

    Unknown keys are dropped and named rather than passed through: a paper's
    "readout_fidelity" is not a NoiseModel field, and a TypeError three
    functions deep is a worse answer than saying which number was ignored.
    """
    params = spec_noise_params(spec)
    if not params:
        return None, None
    from pulser.noise_model import NoiseModel

    accepted = _accepted_fields(NoiseModel)
    kept     = {k: v for k, v in params.items() if k in accepted}
    dropped  = sorted(set(params) - set(kept))
    if dropped:
        print(f"  ⚠  the source's noise model names {dropped}, which this "
              "Pulser's NoiseModel does not take — ignored, and not silently "
              "folded into anything else.")
    if not kept:
        return None, None
    reported = dict(kept)
    block = spec.get("noise_model") or {}
    reported["source"] = (
        f"the source's own noise model ({block.get('why', 'no reason recorded')})")
    return NoiseModel(**kept), reported


def difference_report(spec: dict,
                      overridable_noise_params: dict | None) -> str:
    """Field-by-field difference between the source's model and the device's.

    Only the parameters the pipeline can actually override on the device model
    are compared, which is what `overridable_noise_params` carries: the source
    may state a dozen numbers, but a difference in one the device model will not
    take is not a difference this run can act on.
    """
    spec_params   = spec_noise_params(spec) or {}
    device_params = {k: v for k, v in (overridable_noise_params or {}).items()
                     if k != "source"}
    lines = ["  the source specifies its own noise model:"]
    for key in sorted(set(spec_params) | set(device_params)):
        mine   = spec_params.get(key, "—")
        theirs = device_params.get(key, "—")
        mark   = "  ←" if mine != theirs else ""
        lines.append(f"    {key:<18} source {mine!s:<12} device {theirs!s:<12}{mark}")
    return "\n".join(lines)


def resolve(choice: str, spec: dict, device_noise,
            overridable_noise_params: dict | None) -> list[tuple]:
    """The noisy run(s) to perform: a list of (label, NoiseModel, params).

    `device` is the default everywhere, and staying on it is fine — but if the
    source stated its own model, the user is told it exists and what it would
    change, every time. An unmentioned alternative is a decision made for them.
    """
    if choice not in CHOICES:
        raise SystemExit(f"✘ --noise-source must be one of {CHOICES}")

    spec_noise_model, spec_params = build_spec_noise(spec)
    device_run = ("device", device_noise, overridable_noise_params)

    if spec_noise_model is None:
        if choice != "device":
            raise SystemExit(
                f"✘ --noise-source {choice} was asked for, but the spec carries "
                "no noise model of its own.\n"
                '  Add one in idea-to-spec: {"noise_model": {"source": "paper", '
                '"params": {...}, "why": "..."}}')
        return [device_run]

    print(difference_report(spec, overridable_noise_params))
    if choice == "device":
        print("  running the DEVICE model — what the hardware will actually do.\n"
              "  To reproduce the source's claim under its own assumptions: "
              "--noise-source paper (or both).")
        return [device_run]
    if choice == "paper":
        print("  running the SOURCE's model. This is not what the hardware will "
              "do, and no verdict from it gates a submission.")
        return [("paper", spec_noise_model, spec_params)]
    print("  running BOTH: the device model gives the verdict, the source's "
          "model says whether its claim reproduces on its own terms.")
    return [device_run, ("paper", spec_noise_model, spec_params)]


def _self_test() -> None:
    """Offline asserts. Needs no Pulser: only the paths that avoid NoiseModel."""
    assert spec_noise_params({}) is None
    assert spec_noise_params({"noise_model": {"source": "device",
                                              "params": {"T2": 1}}}) is None
    spec = {"noise_model": {"source": "paper", "params": {"T2": 4.0},
                            "why": "Table I"}}
    assert spec_noise_params(spec) == {"T2": 4.0}
    report = difference_report(spec, {"T2": 1.5, "p_false_pos": 0.01,
                                      "source": "live device"})
    assert "T2" in report and "source 4.0" in report and "←" in report, report
    assert "p_false_pos" in report, report
    try:
        resolve("paper", {}, None, None)
    except SystemExit as e:
        assert "carries no noise model" in str(e), str(e)
    else:
        raise AssertionError("--noise-source paper with no spec block must refuse")
    assert resolve("device", {}, "NM", {"source": "x"}) == [("device", "NM",
                                                             {"source": "x"})]
    print("spec_noise self-test OK")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0] + " Importable module; nothing to run.")
    ap.add_argument("--self-test", action="store_true",
                    help="offline asserts on this module's logic")
    if not ap.parse_args().self_test:
        ap.print_help()
    else:
        _self_test()
