#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# submit_slurm.sh — run noise-emulation trajectories on GPU via SLURM.
#
# Strict ordering: (1) noiseless first, (2) noisy array (after noiseless done),
# (3) merge+plot (after noisy array done).
#
# Rationale: noiseless must finish first — it sets the evaluation times that
# all noisy trajectories use. This avoids race conditions and makes the signal
# visible early.
#
# Usage (env-var driven; only SEQFILE and OUTDIR are required):
#   SEQFILE=seq_builder.py \
#   SEQKWARGS='{"N":6,"hx":4.0,"t":4000}' \
#   OUTDIR=results/my_run \
#   NTRAJ=40 \
#   bash <skill-dir>/support/submit_slurm.sh
#
# Overridable env vars (defaults in brackets):
#   FN_NAME [build_sequence]  NTRAJ [20]  CHI [128]  NTIMES [75]  DT [10]
#   PARTITION [internal]  GRES [gpu:a100:1]  ACCOUNT []  TIME [08:00:00]
#   CPUS [4]  VENV [$PULSER_VENV or ~/pulser-venv]  NOISE_MODEL_JSON [<OUTDIR>/noise_model.json]
#   COVERAGE [0.75]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

: "${SEQFILE:?set SEQFILE=path/to/seq_builder.py}"
: "${OUTDIR:?set OUTDIR=results/run_dir}"
SEQKWARGS="${SEQKWARGS:-{\}}"
FN_NAME="${FN_NAME:-build_sequence}"
NTRAJ="${NTRAJ:-20}"
CHI="${CHI:-128}"   # convergence-validated for S(π,π)/2-pt obs up to 6×6; raise to 200+ for larger N / entanglement / full-dist observables
NTIMES="${NTIMES:-75}"
DT="${DT:-10}"      # validated identical to dt=4 for S(π,π) up to 6×6 (~50 steps/Rabi period); lower for faster drives
PARTITION="${PARTITION:-internal}"
GRES="${GRES:-gpu:a100:1}"
TIME="${TIME:-08:00:00}"
CPUS="${CPUS:-4}"
VENV="${VENV:-${PULSER_VENV:-$HOME/pulser-venv}}"
COVERAGE="${COVERAGE:-0.75}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$SCRIPT_DIR/run_noise_emu.py"
PLOTTER="$SCRIPT_DIR/plot_noise_emu.py"
ACCT_FLAG=""; [ -n "${ACCOUNT:-}" ] && ACCT_FLAG="--account=$ACCOUNT"

mkdir -p "$OUTDIR/trajs"
NOISE_MODEL_JSON="${NOISE_MODEL_JSON:-$OUTDIR/noise_model.json}"

# ── Step 1 — fetch+cache the noise model once, on this (online) node ──────────
if [ ! -s "$NOISE_MODEL_JSON" ]; then
  echo "[submit_slurm] fetching noise model on login node → $NOISE_MODEL_JSON"
  source "$VENV/bin/activate"
  python "$RUNNER" --seq-file "$SEQFILE" --fn-name "$FN_NAME" \
                   --seq-kwargs "$SEQKWARGS" --out-dir "$OUTDIR" --save-noise-model
else
  echo "[submit_slurm] reusing existing noise model snapshot: $NOISE_MODEL_JSON"
fi

# ── Step 2 — noiseless trajectory first (single GPU job, no array) ─────────────
NOISELESS_JOB="$OUTDIR/_noiseless_job.sh"
cat > "$NOISELESS_JOB" <<'EOF'
#!/bin/bash
#SBATCH --job-name=nemu_nl
#SBATCH --partition=PARTITION_PLACEHOLDER
#SBATCH --gres=GRES_PLACEHOLDER
#SBATCH --cpus-per-task=CPUS_PLACEHOLDER
#SBATCH --time=TIME_PLACEHOLDER
#SBATCH --output=OUTDIR_PLACEHOLDER/trajs/noiseless_%j.out
#SBATCH --error=OUTDIR_PLACEHOLDER/trajs/noiseless_%j.err
set -euo pipefail
source VENV_PLACEHOLDER/bin/activate
python -u RUNNER_PLACEHOLDER --run-id 0 --n-traj NTRAJ_PLACEHOLDER \
    --seq-file SEQFILE_PLACEHOLDER --fn-name FN_NAME_PLACEHOLDER \
    --seq-kwargs 'SEQKWARGS_PLACEHOLDER' \
    --noise-model-json NOISE_MODEL_JSON_PLACEHOLDER \
    --max-chi CHI_PLACEHOLDER --n-times NTIMES_PLACEHOLDER --dt DT_PLACEHOLDER \
    --out-dir OUTDIR_PLACEHOLDER/trajs
EOF

sed -i "s|PARTITION_PLACEHOLDER|$PARTITION|g" "$NOISELESS_JOB"
sed -i "s|GRES_PLACEHOLDER|$GRES|g" "$NOISELESS_JOB"
sed -i "s|CPUS_PLACEHOLDER|$CPUS|g" "$NOISELESS_JOB"
sed -i "s|TIME_PLACEHOLDER|$TIME|g" "$NOISELESS_JOB"
sed -i "s|OUTDIR_PLACEHOLDER|$OUTDIR|g" "$NOISELESS_JOB"
sed -i "s|VENV_PLACEHOLDER|$VENV|g" "$NOISELESS_JOB"
sed -i "s|RUNNER_PLACEHOLDER|$RUNNER|g" "$NOISELESS_JOB"
sed -i "s|NTRAJ_PLACEHOLDER|$NTRAJ|g" "$NOISELESS_JOB"
sed -i "s|SEQFILE_PLACEHOLDER|$SEQFILE|g" "$NOISELESS_JOB"
sed -i "s|FN_NAME_PLACEHOLDER|$FN_NAME|g" "$NOISELESS_JOB"
sed -i "s|SEQKWARGS_PLACEHOLDER|$SEQKWARGS|g" "$NOISELESS_JOB"
sed -i "s|NOISE_MODEL_JSON_PLACEHOLDER|$NOISE_MODEL_JSON|g" "$NOISELESS_JOB"
sed -i "s|CHI_PLACEHOLDER|$CHI|g" "$NOISELESS_JOB"
sed -i "s|NTIMES_PLACEHOLDER|$NTIMES|g" "$NOISELESS_JOB"
sed -i "s|DT_PLACEHOLDER|$DT|g" "$NOISELESS_JOB"

NL_JOBID=$(sbatch --parsable $ACCT_FLAG "$NOISELESS_JOB")
echo "[submit_slurm] noiseless job: $NL_JOBID  (single GPU, must finish first)"

# ── Step 3 — noisy array (starts only after noiseless DONE) ──────────────────
NOISY_JOB="$OUTDIR/_noisy_job.sh"
cat > "$NOISY_JOB" <<'EOF'
#!/bin/bash
#SBATCH --job-name=nemu_n
#SBATCH --partition=PARTITION_PLACEHOLDER
#SBATCH --gres=GRES_PLACEHOLDER
#SBATCH --cpus-per-task=CPUS_PLACEHOLDER
#SBATCH --time=TIME_PLACEHOLDER
#SBATCH --output=OUTDIR_PLACEHOLDER/trajs/noisy_%a_%j.out
#SBATCH --error=OUTDIR_PLACEHOLDER/trajs/noisy_%a_%j.err
set -euo pipefail
source VENV_PLACEHOLDER/bin/activate
python -u RUNNER_PLACEHOLDER --run-id $((SLURM_ARRAY_TASK_ID + 1)) --n-traj NTRAJ_PLACEHOLDER \
    --seq-file SEQFILE_PLACEHOLDER --fn-name FN_NAME_PLACEHOLDER \
    --seq-kwargs 'SEQKWARGS_PLACEHOLDER' \
    --noise-model-json NOISE_MODEL_JSON_PLACEHOLDER \
    --max-chi CHI_PLACEHOLDER --n-times NTIMES_PLACEHOLDER --dt DT_PLACEHOLDER \
    --out-dir OUTDIR_PLACEHOLDER/trajs
EOF

sed -i "s|PARTITION_PLACEHOLDER|$PARTITION|g" "$NOISY_JOB"
sed -i "s|GRES_PLACEHOLDER|$GRES|g" "$NOISY_JOB"
sed -i "s|CPUS_PLACEHOLDER|$CPUS|g" "$NOISY_JOB"
sed -i "s|TIME_PLACEHOLDER|$TIME|g" "$NOISY_JOB"
sed -i "s|OUTDIR_PLACEHOLDER|$OUTDIR|g" "$NOISY_JOB"
sed -i "s|VENV_PLACEHOLDER|$VENV|g" "$NOISY_JOB"
sed -i "s|RUNNER_PLACEHOLDER|$RUNNER|g" "$NOISY_JOB"
sed -i "s|NTRAJ_PLACEHOLDER|$NTRAJ|g" "$NOISY_JOB"
sed -i "s|SEQFILE_PLACEHOLDER|$SEQFILE|g" "$NOISY_JOB"
sed -i "s|FN_NAME_PLACEHOLDER|$FN_NAME|g" "$NOISY_JOB"
sed -i "s|SEQKWARGS_PLACEHOLDER|$SEQKWARGS|g" "$NOISY_JOB"
sed -i "s|NOISE_MODEL_JSON_PLACEHOLDER|$NOISE_MODEL_JSON|g" "$NOISY_JOB"
sed -i "s|CHI_PLACEHOLDER|$CHI|g" "$NOISY_JOB"
sed -i "s|NTIMES_PLACEHOLDER|$NTIMES|g" "$NOISY_JOB"
sed -i "s|DT_PLACEHOLDER|$DT|g" "$NOISY_JOB"

ARRAY_SPEC="0-$((NTRAJ-1))"; [ -n "${ARRAY_MAX:-}" ] && ARRAY_SPEC="$ARRAY_SPEC%$ARRAY_MAX"
NOISY_JOBID=$(sbatch --parsable $ACCT_FLAG --dependency=afterok:"$NL_JOBID" --array="$ARRAY_SPEC" "$NOISY_JOB")
echo "[submit_slurm] noisy array job: $NOISY_JOBID  (tasks 1-$NTRAJ, starts after $NL_JOBID)"

# ── Step 4 — merge + plot, after noisy array finishes ───────────────────────
MERGE_JOB="$OUTDIR/_merge_job.sh"
cat > "$MERGE_JOB" <<EOF
#!/bin/bash
#SBATCH --job-name=nemu_merge
#SBATCH --partition=$PARTITION
#SBATCH --cpus-per-task=2
#SBATCH --time=00:30:00
#SBATCH --output=$OUTDIR/merge_%j.out
#SBATCH --error=$OUTDIR/merge_%j.err
set -euo pipefail
source "$VENV/bin/activate"
python "$RUNNER" --merge --out-dir "$OUTDIR/trajs" \\
    --seq-kwargs '$SEQKWARGS' --max-chi $CHI
MERGED=\$(ls -t "$OUTDIR/trajs"/FCAN1_*.npz | head -1)
python "$PLOTTER" --result "\$MERGED" --out "$OUTDIR/noise_plot.pdf" --coverage $COVERAGE
echo "[merge] plotted \$MERGED → $OUTDIR/noise_plot.pdf"
EOF

MERGE_JOBID=$(sbatch --parsable $ACCT_FLAG --dependency=afterok:"$NOISY_JOBID" "$MERGE_JOB")
echo "[submit_slurm] merge+plot job: $MERGE_JOBID  (runs after $NOISY_JOBID)"
echo "[submit_slurm] watch: squeue -u \$USER | grep nemu"
echo "[submit_slurm] noiseless result ready ~$(($NTRAJ / 4 + 30))min from now"
echo "[submit_slurm] full result ready ~$(($NTRAJ * 20 / 4 + 30))min from now"
