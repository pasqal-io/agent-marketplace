"""The labels every submitted batch carries, always.

A batch id is a UUID. A month later, nobody knows which of forty of them was the
Kibble-Zurek scan at 25 atoms, and the only way back is a file someone still
has. Tags are the searchable, human-readable handle the cloud offers instead:

    from pasqal_cloud.utils.filters import BatchFilters
    sdk.get_batches(filters=BatchFilters(tag="exp:square_lattice_eom_quench"))

finds every batch of one experiment — emulation, calibration and QPU — and
`sdk.set_batch_tags(batch_id, tags)` amends a batch afterwards. Which is why
nothing here is optional: an untagged batch is a paid result that cannot be
found again, and `--tag` exists so the user's own words travel with it.

Tags are unique strings with no documented length or charset limit; these stay
short, lowercase and space-free so they survive a URL query, except where the
value is a name from the spec (the scan variable, the version), which is kept
verbatim so that searching for what the spec calls it works.

This file is vendored byte-identical into each skill's `support/` directory, so
a skill keeps working when installed or copied on its own. Edit one copy and
`scripts/check_manifests.py` fails until the others match.
"""
from __future__ import annotations

import time


def slug(text: str, limit: int = 40) -> str:
    """Lowercase, hyphenated, ASCII."""
    keep = [c if c.isalnum() else "-" for c in str(text).lower()]
    return "-".join("".join(keep).split("-"))[:limit].strip("-")


def build_tags(spec: dict, device_name: str, shots: int, stage: str,
               n_atoms: int | None = None, extra: list[str] | None = None,
               today: str | None = None) -> list[str]:
    """Labels for one submission. `stage` says what this batch was for.

    Order is stable and duplicates are dropped, so a diff of two submissions is
    readable and the API's uniqueness requirement is met before it is asked for.
    """
    scan = spec.get("scan", {})
    tags = [
        "neutral-atom-toolkit",
        f"exp:{slug(spec['experiment_name'])}",
        f"stage:{stage}",
        f"device:{slug(device_name)}",
        f"scan:{scan.get('variable', 'none')}",          # the spec's own spelling
        f"shots:{shots}",
        f"spec:{spec.get('version', 'unversioned')}",
        f"date:{today or time.strftime('%Y-%m-%d')}",
    ]
    if n_atoms:
        tags.append(f"n_atoms:{n_atoms}")
    if spec.get("objective"):
        tags.append(f"obj:{slug(spec['objective'])}")
    for t in (extra or []):
        tags.append(slug(t, limit=60))
    seen, unique = set(), []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def _self_test() -> None:
    spec = {"experiment_name": "Square Lattice Quench", "version": "1.0",
            "objective": "Does the Z2 order survive a fast quench?",
            "scan": {"variable": "t_ns", "values": [16, 24]}}
    tags = build_tags(spec, "FRESNEL_CAN1", 300, "experiment", n_atoms=25,
                      extra=["Kibble-Zurek run 2"], today="2026-09-02")
    assert "exp:square-lattice-quench" in tags, tags
    assert "stage:experiment" in tags and "device:fresnel-can1" in tags, tags
    assert "scan:t_ns" in tags and "n_atoms:25" in tags and "shots:300" in tags, tags
    assert "date:2026-09-02" in tags and "spec:1.0" in tags, tags
    assert any(t.startswith("obj:does-the-z2-order") for t in tags), tags
    assert "kibble-zurek-run-2" in tags, tags
    assert len(tags) == len(set(tags)), "tags must be unique"
    assert all(" " not in t for t in tags), tags
    bare = build_tags({"experiment_name": "x", "scan": {}}, "EMU_MPS", 100,
                      "emu-noisy", today="2026-01-01")
    assert "scan:none" in bare and "spec:unversioned" in bare, bare
    print("batch_tags self-test OK")


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
