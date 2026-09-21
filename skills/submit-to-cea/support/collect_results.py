#!/usr/bin/env python3
"""Collect per-job result files into a single JSONL file and report missing jobs."""

import json
import glob
import os
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description='Collect per-job CEA result files into one JSONL')
    parser.add_argument(
        '--name',
        type=str,
        required=True,
        help='Experiment name (e.g. scan_transition_cst_rate_6_v5_wait_100_FM1_shape_rhombus_side_N_100)'
    )
    parser.add_argument(
        '--n-jobs',
        type=int,
        default=85,
        help='Expected number of jobs (default: 85)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='QPU_results',
        help='Output directory (default: QPU_results)'
    )
    args = parser.parse_args()

    batch_ids_path = os.path.join(args.output_dir, "batch_ids")
    pattern = os.path.join(batch_ids_path, f"{args.name}_job_*.json")
    files = glob.glob(pattern)

    # Parse job indices from filenames
    completed = {}
    for f in files:
        basename = os.path.basename(f)
        # Extract index from {name}_job_{idx}.json
        idx_str = basename.replace(f"{args.name}_job_", "").replace(".json", "")
        try:
            idx = int(idx_str)
            completed[idx] = f
        except ValueError:
            print(f"Warning: skipping unexpected file {basename}")

    # Report status
    missing = sorted(set(range(args.n_jobs)) - set(completed.keys()))
    print(f"Found {len(completed)}/{args.n_jobs} completed jobs")

    if missing:
        print(f"Missing {len(missing)} jobs: {missing}")
        print(f"To resubmit missing jobs:")
        for idx in missing:
            print(f"  export CEA_JOB_INDEX={idx} && ccc_msub submit_cea.sh")

    # Merge into single JSONL, sorted by job index
    output_file = os.path.join(batch_ids_path, f"{args.name}.json")
    sorted_indices = sorted(completed.keys())

    with open(output_file, 'w') as out:
        for idx in sorted_indices:
            with open(completed[idx], 'r') as f:
                data = json.load(f)
                json.dump(data, out)
                out.write("\n")

    print(f"Merged {len(sorted_indices)} results into {output_file}")

    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
