#!/usr/bin/env python3
"""Check an experiment_spec.json carries what the support scripts read.

RUNS ON: this machine. Reads one file, contacts nothing.

Usage:
    python validate_spec.py experiments/<name>/<name>_spec.json

Exits non-zero, listing every problem, if a field the pipeline reads without a
default is missing — a spec that fails here would otherwise fail at the paid
step. Vendored byte-identical wherever a skill needs it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# The fields the support scripts read without a default, and the one closed
# enum idea-to-spec declares. Keep in step with skills/idea-to-spec/SKILL.md.
REQUIRED = ("experiment_name", "device", "register.N_atoms", "scan.variable",
            "scan.values", "pulse.omega_max_mhz", "shots_per_point",
            "output_dir")
GEOMETRIES = ("square", "chain", "ring", "triangular_rhombus", "custom")


def _dig(data, dotted: str):
    for key in dotted.split("."):
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def spec_problems(spec: dict) -> list[str]:
    problems = [f"missing {field}" for field in REQUIRED
                if _dig(spec, field) is None]
    if _dig(spec, "register.geometry") not in GEOMETRIES:
        problems.append(f"register.geometry must be one of {GEOMETRIES}")
    return problems


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if len(sys.argv) == 2 else 2)
    problems = spec_problems(json.loads(Path(sys.argv[1]).read_text()))
    for problem in problems:
        print(f"✘ {sys.argv[1]}: {problem}")
    if problems:
        sys.exit(1)
    print(f"✔ {sys.argv[1]}: fields the pipeline reads are present")


if __name__ == "__main__":
    main()
