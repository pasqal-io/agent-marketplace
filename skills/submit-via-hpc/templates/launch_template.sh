#!/bin/bash
# Launcher for <<EXPERIMENT_NAME>> on CEA Ruby QPU.
# Sequential submission via ccc_msub -w (one MSUB job = one parameter point).
#
# Usage:
#   bash launch_cea_jobs.sh
#
# To resubmit a subset (e.g. failed or missing jobs):
#   INDICES=(3 7 22 41)
#   Then re-run: bash launch_cea_jobs.sh

# === CONFIGURE PER EXPERIMENT ===
INDICES=($(seq 0 <<N_JOBS_MINUS_1>>))   # all <<N_JOBS>> parameter points (0-indexed)
# ================================

N_JOBS=${#INDICES[@]}
echo "Submitting $N_JOBS jobs to CEA QPU for experiment: <<EXPERIMENT_NAME>>"

for i in "${INDICES[@]}"; do
    export CEA_JOB_INDEX=$i
    ccc_msub -w submit_cea.sh
    echo "Submitted job index $i"
done

echo ""
echo "All $N_JOBS jobs submitted. They will run sequentially."
echo "Monitor with:  ccc_mstat"
echo "Peek at job:   ccc_mpeek <jobid>"
echo ""
echo "Collect results (run from ~/cea_deploy/):"
echo "  python3 collect_results.py --name <<EXPERIMENT_NAME>> --n-jobs $N_JOBS --output-dir <<OUTPUT_DIR>>"
