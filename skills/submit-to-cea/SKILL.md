---
name: submit-to-cea
description: Submit a Pulser parametric experiment to Ruby, the neutral-atom QPU hosted at CEA/TGCC on the irene supercomputer, over SSH — generate the job bundle, deploy it, launch the ccc_msub jobs, monitor them, collect the results, with no manual copying. The templates are TGCC-specific and say what a sibling Bull or Slurm site needs changed; use qpu-submit for a cloud-API QPU. Triggered by phrases like "submit to CEA", "launch on Ruby", "submit to TGCC".
argument-hint: "[sequence-file-or-description]"
---

# submit-to-cea

This skill takes a Pulser parametric experiment from source code to running QPU
jobs on a machine reached over SSH, entirely autonomously. The user never needs
to copy files, run remote commands, or touch the server manually.

The name is deliberate: what is bundled here was written for and tested against
**Ruby at CEA/TGCC**, and the deployment path is that site's. It generalises to a
sibling cluster by editing three files (**Site scope**, below), but calling it
generic would promise a portability nothing here has tested.

RUNS ON: a QPU behind an HPC scheduler, over SSH. Node hours and shots are
billed to someone's allocation, and jobs queued remotely cannot be recalled.
File generation (Phase 3) happens on this machine and costs nothing.

## Decisions that are not yours

"Autonomously" describes the file copying and the job plumbing, not the
decisions. Ask, recommend, and wait:

- **the site and the account/allocation** the node hours are billed to
- **the shot count and the parameter list** — how many jobs, and what they sweep
- **whether to launch now** given the QPU availability check (Phase 4.1)
- **what to do when jobs fail or the QPU is down** — wait, resubmit, or stop

After about **three** attempts at the same obstacle — SSH refused, jobs dying in
the queue, a container that will not start — stop and report: what was tried,
what the scheduler said, and what is known. Then offer waiting for the site,
changing the target, or abandoning the run. Do not loop on a cluster that is
telling you no.

## Where the outputs land

Locally, in the experiment's own tree — the generated bundle is part of the
record, not scratch:

```
experiments/<name>/
  analysis/hpc/            the generated submit_<name>.py, launch and job scripts
  results/qpu/             collected results, batch ids, logs
  figures/                 figures made for the report
  NOTEBOOK.md              one appended block per phase that touched the cluster
```

Remote paths stay under `$HOME/$HPC_REMOTE_DIR` as documented below. Report the
local and remote path of everything you generate; nothing is left in the working
directory's root.

**Two variables** define the target, set once per session:

```bash
# Values shown are the reference site's; ask the user for theirs.
HPC_HOST=irene             # an ssh alias defined in ~/.ssh/config (see below)
HPC_REMOTE_DIR=cea_deploy  # working directory under $HOME on the remote machine
```

Every command below uses `"$HPC_HOST"`. Never hardcode a hostname.

**Prerequisite:** `ssh "$HPC_HOST" "echo ok"` must work from this machine. If it
doesn't, walk the user through **Getting access** below before anything else.

## Site scope — read this before adapting to another cluster

The bundled templates target a **Bull/TGCC-style site**: `ccc_msub` for
submission, `#MSUB` job headers, `ccc_mstat`/`ccc_mpeek` for monitoring, and
`pcocc-rs` containers for the runtime. The worked reference below is **Ruby**,
the Pasqal QPU hosted at TGCC on the `irene` supercomputer (CEA/GENCI).

A site with a different scheduler needs three files adapted —
`templates/submit_cea_template.sh` (job headers and container invocation),
`templates/launch_template.sh` (submission and monitoring commands), and
`support/setup_cea_env.sh` (environment bootstrap). Everything else, including
the sequence utilities and the result collector, is scheduler-agnostic. A Slurm
port is roughly: `#MSUB` → `#SBATCH`, `ccc_msub` → `sbatch`, `ccc_mstat` →
`squeue`, and drop the `pcocc-rs` wrapper if the site exposes Python directly.

---

## Getting access — reference site (Ruby at TGCC)

TGCC access is granted per person, per project. **No GENCI/EuroHPC allocation
or TGCC account yet?** That whole application — eDARI or EuroHPC, then the
TGCC computing account, identity form and security screening — is the
`apply-genci-tgcc-cea` skill's job, not this one; send the user there (or to
`choose-access-method` first if they haven't settled on CEA/GENCI versus
Pasqal Cloud at all). The two steps below are this skill's own, once that
account exists:

1. **SSH configuration.** TGCC uses password authentication (`authorized_keys`
   is not honored). Add an alias to `~/.ssh/config` so the rest of this skill
   works verbatim, and reuse one connection to avoid re-typing the password:

   ```
   Host irene
       HostName irene-fr.ccc.cea.fr
       User <your_tgcc_login>
       ControlMaster auto
       ControlPath ~/.ssh/cm-%r@%h:%p
       ControlPersist 8h
   ```

   The alias name is what goes in `HPC_HOST`. Then authenticate once
   interactively (`ssh "$HPC_HOST"`) — subsequent calls in this skill ride the
   shared connection without prompting. (`apply-genci-tgcc-cea` ends at
   credentials arriving by email from TGCC and explicitly defers this step
   here — there is no gap between the two skills, just this one thing left
   to do.)
2. **Remote environment — optional, set up once.** The compute nodes have no
   internet, so Pulser is pushed from your machine into a container venv
   (`~/pulser-env/`) that persists between sessions. **You do not run this every
   time:** Phase 0 probes for it and only sends you to **Environment setup**
   (below) when it is missing, or when the user asks to rebuild it. A cluster
   that already has a working `~/pulser-env/` needs nothing here.

For questions about the account itself (not the SSH setup above):
`hotline.tgcc@cea.fr`.

---

## Phase 0 — Connectivity check

```bash
ssh -o ConnectTimeout=15 "$HPC_HOST" "echo ok" 2>/dev/null && echo "HOST OK" || echo "HOST DOWN"
```

If `HOST OK` → proceed.

If `HOST DOWN`, diagnose:

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| Timeout / no route | Your IP is not whitelisted (wrong network/VPN), or the login node is under load | Confirm you're on the registered institutional network; retry after 15 s |
| `Permission denied` | Wrong password, expired account, or too many concurrent sessions | Re-authenticate interactively with `ssh "$HPC_HOST"`; if it persists, contact the site's support desk (TGCC: `hotline.tgcc@cea.fr`) |
| Password prompt hangs the tool | No live ControlMaster connection | Ask the user to run `ssh "$HPC_HOST"` once in their own terminal to authenticate, then retry |

**Retry policy:** on transient failures, silently wait ~15 s and retry, up to 3
attempts. Only surface the error to the user if all attempts fail, and include
the diagnosis. **Never store, type, or echo the user's password yourself** —
authentication is theirs to perform interactively.

All remote files live under `~/$HPC_REMOTE_DIR/`. Always use `nohup` for
long-running scripts.

### Phase 0.1 — Environment probe

Connectivity is not enough — the `ccc-quantum` container needs a working
`~/pulser-env/`. Probe it:

```bash
ssh "$HPC_HOST" 'pcocc-rs run ccc-quantum -- bash -c "
source ~/pulser-env/bin/activate 2>/dev/null || { echo \"ENV MISSING: no venv\"; exit 0; }
python3 - <<EOF
try:
    import pulser, pulser_myqlm
    print(\"ENV OK\", \"pulser\", pulser.__version__,
          \"pulser-myqlm\", getattr(pulser_myqlm, \"__version__\", \"?\"))
except Exception as e:
    print(\"ENV MISSING:\", e)
EOF
"'
```

- **`ENV OK`** → skip all environment setup and go straight to Phase 1, **unless
  the user explicitly asked to (re)build the environment** — then run
  **Environment setup** below.
- **`ENV MISSING`** → tell the user the container has no usable Pulser and
  **ask** whether to set it up now — it downloads packages and writes to their
  remote home, so do not start unprompted. On yes, run **Environment setup**
  below. If they decline, stop: submission cannot proceed without it.

Run **Environment setup** in exactly these two cases — `ENV MISSING`, or an
explicit user request. Never as a routine step.

---

## Environment setup (only on `ENV MISSING`, or an explicit user request)

The compute nodes have no internet, so Pulser and any missing dependencies are
downloaded on **this** machine and pushed to the cluster. This runs **once per
cluster** — Phase 0.1 skips it on every later session.

### E.1 — Resolve versions

Default to the latest **stable** release of each package on PyPI — never a
pre-release (`a`/`b`/`rc`/`dev` are all excluded by the version regex below):

```bash
for pkg in pulser-core pulser-myqlm; do
  curl -sf "https://pypi.org/pypi/$pkg/json" | python3 -c "
import json, sys, re
rel = json.load(sys.stdin)['releases']
ok = [v for v, files in rel.items()
      if files and not files[0].get('yanked') and re.fullmatch(r'[0-9]+(\.[0-9]+)*', v)]
ok.sort(key=lambda s: [int(x) for x in s.split('.')])
print('$pkg', ok[-1])
"
done
```

Show both versions to the user and ask whether to use them or pin different
ones. Reject any version they give that contains a letter — that is a
pre-release. Also grab the container's Python version, needed for the download:

```bash
PYVER=$(ssh "$HPC_HOST" 'pcocc-rs run ccc-quantum -- python3 -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")"')
```

### E.2 — Download on this machine

```bash
PKGDIR="$(pwd)/cea_pkgs"; mkdir -p "$PKGDIR"
python3 -m pip download --no-deps --only-binary :all: \
    --python-version "$PYVER" --platform manylinux2014_x86_64 --platform any \
    --dest "$PKGDIR" "pulser-core==<CORE_VERSION>" "pulser-myqlm==<MYQLM_VERSION>"
```

`--no-deps` is deliberate: dependencies are resolved against the container in
E.4, not mirrored blindly from here.

### E.3 — Upload and build the venv

Template/support paths are relative to this skill's directory — expand them.

```bash
ssh "$HPC_HOST" "mkdir -p ~/cea_pkgs ~/$HPC_REMOTE_DIR"
rsync -avz "$PKGDIR"/ "$HPC_HOST":~/cea_pkgs/
scp support/setup_cea_env.sh "$HPC_HOST":~/$HPC_REMOTE_DIR/
ssh "$HPC_HOST" 'pcocc-rs run ccc-quantum -- bash ~/'"$HPC_REMOTE_DIR"'/setup_cea_env.sh'
```

`setup_cea_env.sh` creates `~/pulser-env/` (system site packages on, so the
container's numpy/scipy are reused), installs every archive in `~/cea_pkgs/`
with `--no-deps`, then tries `import pulser` and `import pulser_myqlm`. It prints
one `MISSING: <module>` line per unmet import and exits non-zero.

### E.4 — Satisfy remaining dependencies

For each `MISSING: <module>` line:

- **`qat…` or `myqlm`** → **stop here.** myQLM / QAT cannot be built in the
  `ccc-quantum` container. Report it to the user: the environment cannot be
  completed this way and needs a container image that already ships myQLM.
- **anything else** → tell the user which dependency is missing and ask whether
  to fetch it the same way. On yes:

  ```bash
  python3 -m pip download --no-deps --only-binary :all: \
      --python-version "$PYVER" --platform manylinux2014_x86_64 --platform any \
      --dest "$PKGDIR" "<module>"
  rsync -avz "$PKGDIR"/ "$HPC_HOST":~/cea_pkgs/
  ssh "$HPC_HOST" 'pcocc-rs run ccc-quantum -- bash ~/'"$HPC_REMOTE_DIR"'/setup_cea_env.sh'
  ```

  Re-running the script re-installs the whole `~/cea_pkgs/` set and re-checks the
  imports. Repeat until it exits 0, a `qat`/`myqlm` dependency appears, or the
  user declines. If `pip download` finds no compatible wheel for a dependency
  (native code, no `manylinux` build), say so — that is a hard limit, like the
  myQLM case.

pip resolves the latest stable release of each dependency by default; pass
`"<module>==<version>"` only if the user asks.

When `setup_cea_env.sh` exits 0, the environment is ready — go to Phase 1.

---

## Phase 1 — Gather the sequence

Ask the user to share their Pulser sequence. Accept any of:
- A Python file path — read the file
- Pasted code in the conversation
- A Jupyter notebook path — read it and look at the code cells

From the code, extract:
1. **The builder function** — the function that constructs the `Sequence`. If inline, wrap it:
   ```python
   def build_para_<name>_sequence(N, device, <other_params>):
       ...
       return para_seq
   ```
2. **Parametric variable** — must be declared as `para_seq.declare_variable("params")`. Rename to `"params"` if it has a different name.
3. **Fixed parameters** — numeric constants that are not the sweep variable (e.g. `Omega_max`, `hx`, `R`).
4. **Register layout** — how the register is built and the inter-atom spacing.

---

## Phase 2 — Gather experiment parameters

Ask the user for the following (offer sensible defaults):

| Parameter | What to ask | Default |
|-----------|------------|---------|
| **Experiment name** | Short identifier, e.g. `myexp_N8_T3`. No spaces. | infer from sequence |
| **Sweep variable** | What the parametric variable represents (e.g. time T in µs) | — |
| **Parameter range** | Min, max, n_points — or explicit list. Durations must be multiples of 4 ns. | — |
| **Number of shots** | Shots per job | 200 |
| **Output directory** | Results directory on TGCC | `QPU_results` |
| **GENCI project code** | The `#MSUB -A` allocation code (format `genXXXXX`) — from your PI | ask, no default |
| **Wall time** | MSUB wall time in seconds | 7000 |

**Generating the parameter list:**
- Duration in µs → ns, round to nearest 4 ns:
  ```python
  times = [float(round(t * 1000 / 4) * 4) for t in np.linspace(t_min_us, t_max_us, n_points)]
  ```
- Duration already in ns: round to nearest 4.
- Dimensionless (detuning, ratio): no rounding.

---

## Phase 3 — Generate files locally

Template and support paths below (`templates/…`, `support/…`) are relative to
**this skill's directory** — expand them to its absolute location.

Create `cea_bundle_<name>/` in the current working directory.

### 3.1 — submit_<name>.py

Read template: `templates/submit_template.py`

Replace every `<<PLACEHOLDER>>`:

| Placeholder | Value |
|-------------|-------|
| `<<EXPERIMENT_NAME>>` | experiment name |
| `<<N_SHOTS>>` (×2) | number of shots |
| `<<N_QUBITS>>` | integer number of qubits |
| `<<PARAMETER_VALUES_LIST>>` | full Python list literal |
| `<<FIXED_PARAMS_DICT_ENTRIES>>` | key-value pairs for params dict |
| `<<BUILDER_FUNCTION_NAME>>` | `build_para_<name>_sequence` |
| `<<BUILDER_CALL_ARGS>>` | keyword args after `N=params["N"], device=device` |
| `<<PARAMS_JSON_FIELDS>>` | dict literal to save to JSON |
| `<<OUTPUT_DIR>>` | default output directory string |
| `<<TOOLKIT_VERSION>>` | the `version` field of the toolkit's `plugin.json`, two directories above this skill — read it, do not recall it |

`<<TOOLKIT_VERSION>>` feeds the provenance stamp near the top of the template:
Pulser writes it into every serialized sequence, which is what identifies the
submission as agent-generated once it reaches the QPU. The bundle runs on a
cluster with no manifest beside it, so the version has to be a literal here
rather than a lookup at run time.

Write to `cea_bundle_<name>/$HPC_REMOTE_DIR/submit_<name>.py`.

### 3.2 — launch_cea_jobs.sh

Read template: `templates/launch_template.sh`

Replace:
- `<<EXPERIMENT_NAME>>` → experiment name
- `<<N_JOBS_MINUS_1>>` → `len(times) - 1`
- `<<N_JOBS>>` → `len(times)`
- `<<OUTPUT_DIR>>` → output directory

Write to `cea_bundle_<name>/$HPC_REMOTE_DIR/launch_cea_jobs.sh`.

### 3.3 — submit_cea.sh

Read template: `templates/submit_cea_template.sh`

Replace:
- `<<EXPERIMENT_NAME>>` → experiment name
- `<<MSUB_PROJECT_CODE>>` → GENCI allocation code
- `<<WALL_TIME_S>>` → wall time in seconds
- `<<N_SHOTS>>` → number of shots

Write to `cea_bundle_<name>/$HPC_REMOTE_DIR/submit_cea.sh`.

### 3.4 — utils/sequence_utils.py with new builder

1. Read `support/utils/sequence_utils.py` verbatim
2. Append the new builder function at the very end (separated by two blank lines)

Write to `cea_bundle_<name>/$HPC_REMOTE_DIR/utils/sequence_utils.py`.

### 3.5 — Copy supporting files

```bash
SKILL_DIR="<absolute path to this skill's directory>"
BUNDLE=cea_bundle_<name>

cp $SKILL_DIR/support/utils/__init__.py       $BUNDLE/$HPC_REMOTE_DIR/utils/__init__.py
cp $SKILL_DIR/support/utils/pulser_utils.py   $BUNDLE/$HPC_REMOTE_DIR/utils/pulser_utils.py
cp $SKILL_DIR/support/utils/rhombus_utils.py  $BUNDLE/$HPC_REMOTE_DIR/utils/rhombus_utils.py
cp $SKILL_DIR/support/setup_cea_env.sh        $BUNDLE/$HPC_REMOTE_DIR/setup_cea_env.sh
cp $SKILL_DIR/support/collect_results.py      $BUNDLE/$HPC_REMOTE_DIR/collect_results.py
```

---

## Phase 4 — Deploy directly to the cluster over SSH

Do NOT zip or ask the user to copy anything. Deploy the generated files straight to the server.

### 4.1 — Test QPU availability first

The two adjacent quoted strings are deliberate: the first is double-quoted so
`$HPC_REMOTE_DIR` expands here, the second stays single-quoted so the nested
Python quoting below survives untouched.

```bash
ssh "$HPC_HOST" "cd ~/$HPC_REMOTE_DIR && "'pcocc-rs run ccc-quantum -- bash -c "
source ../pulser-env/bin/activate
python3 - <<EOF
from pulser_myqlm import PulserQLMConnection
try:
    conn = PulserQLMConnection(timeout=30)
    device = conn.fetch_available_devices().get(\"qat.qpus:PasqalQPU\")
    print(\"QPU UP:\", device.name if device else \"not found\")
except Exception as e:
    print(\"QPU DOWN:\", e)
EOF
"'
```

If the QPU is down, report it to the user and stop. Do not submit jobs to a down QPU.

### 4.2 — Rsync generated files to the cluster

```bash
rsync -avz cea_bundle_<name>/$HPC_REMOTE_DIR/ "$HPC_HOST":~/$HPC_REMOTE_DIR/
```

Verify the key files landed:
```bash
ssh "$HPC_HOST" "ls ~/$HPC_REMOTE_DIR/submit_<name>.py ~/$HPC_REMOTE_DIR/launch_cea_jobs.sh ~/$HPC_REMOTE_DIR/submit_cea.sh"
```

### 4.3 — Check nothing is already running for this experiment

Launching is not idempotent: the launcher queues a fresh job per scan point every
time it runs, and each one spends allocation hours. Nothing on the cluster
prevents a duplicate.

```bash
ssh "$HPC_HOST" "ccc_mstat 2>/dev/null | head -20; ls -t ~/$HPC_REMOTE_DIR/logs/ 2>/dev/null | head -5"
```

If jobs for this experiment are already queued or running, **do not launch
again** — report what is there and let the user decide. Monitor the existing jobs
instead (Phase 5).

### 4.4 — Launch jobs with nohup

Two gates first, and neither can be skipped:

- **Emulation.** `validate-emu` must have returned a GO for this sequence. If it
  has not run, say so and offer to run it — the local mode first, it is free.
- **The user's go-ahead.** Show the plan — jobs × shots, wall time, the GENCI
  project code — and wait for a yes. `launch_cea_jobs.sh` refuses to run
  without `CONFIRM=yes`; set it **only** to carry that yes, and ask again if
  the plan changes.

```bash
LAUNCH_LOG="logs/launch_$(date +%Y%m%d_%H%M%S).out"
ssh "$HPC_HOST" "cd ~/$HPC_REMOTE_DIR && mkdir -p logs && CONFIRM=yes nohup bash launch_cea_jobs.sh > $LAUNCH_LOG 2>&1 & echo PID:\$!"
```

Save the PID for monitoring. Report the launch log path to the user.

### 4.5 — Confirm jobs are queued

Wait ~10 seconds, then verify the MSUB scheduler received the job:
```bash
ssh "$HPC_HOST" "ccc_mstat 2>/dev/null | head -20"
```

Also read the first few lines of the launch log:
```bash
ssh "$HPC_HOST" "tail -5 ~/$HPC_REMOTE_DIR/$LAUNCH_LOG"
```

---

## Phase 5 — Report status to the user

After launch, tell the user:
1. QPU status (confirmed UP)
2. Experiment name, number of jobs, parameter range
3. The launch log path on the remote machine: `~/$HPC_REMOTE_DIR/<LAUNCH_LOG>`
4. How to monitor (give them the exact commands):
   ```bash
   # Live launcher log:
   ssh "$HPC_HOST" "tail -f ~/$HPC_REMOTE_DIR/<LAUNCH_LOG>"

   # MSUB queue:
   ssh "$HPC_HOST" "ccc_mstat"
   ```
5. When all jobs are done, collect the results and sync them back. Substitute the
   experiment name, job count, and output directory computed in Phases 2–3:
   ```bash
   NAME="<name>"            # experiment name
   N_JOBS=<N_JOBS>          # total number of jobs
   OUTPUT_DIR="<output_dir>"  # output directory on the remote machine (e.g. QPU_results)
   LOCAL_DIR="$(pwd)/${NAME}_QPU_results_$(date +%Y%m%d)"

   # Merge the per-job JSON files on the remote machine (safe to re-run while jobs finish):
   ssh "$HPC_HOST" "cd ~/$HPC_REMOTE_DIR && \
       python3 collect_results.py --name \"$NAME\" --n-jobs $N_JOBS --output-dir \"$OUTPUT_DIR\"; \
       echo 'collect_results.py exit code: '\$?"

   # Rsync the merged results back to this machine:
   mkdir -p "$LOCAL_DIR"
   rsync -avz --progress "$HPC_HOST":"~/$HPC_REMOTE_DIR/${OUTPUT_DIR}/" "$LOCAL_DIR/"
   echo "Data available at: $LOCAL_DIR/"
   ```
   `collect_results.py` exit code 0 = all jobs merged; exit code 1 = some still pending
   (normal while jobs are running). The merged JSONL lands at
   `<output_dir>/batch_ids/<name>.json` on the remote machine and is mirrored into `$LOCAL_DIR/` here.
6. **Next step**: `harvest-and-analyze`, pointed at the merged file — it computes
   the observable, compares it with the emulated baseline and returns the
   accept/reject verdict. This skill stops at raw data on disk.

---

## Critical quoting rule for submit_cea.sh

The `pcocc-rs run ccc-quantum -- bash -c "..."` pattern uses **double quotes**. Inside double quotes, the **outer MSUB shell** expands `$VAR` before passing the string to `bash -c`. This is intentional — `$CEA_JOB_INDEX`, `$CEA_R_INDEX`, `$BRIDGE_MSUB_PWD` are all set in the MSUB environment and must be expanded by the outer shell.

**Never escape job-index variables with a backslash** (`\$CEA_JOB_INDEX` is wrong — it prevents expansion and passes a literal empty string to the inner shell).

Only escape variables that must be evaluated by the **inner** `bash -c` shell (e.g. `$?`, `$$`, loop variables defined inside the string itself).

---

## Important conventions (always enforce)

- Parametric variable **must** be `para_seq.declare_variable("params")`. No other name.
- All duration values **must** be multiples of 4 ns (hardware clock). Round during parameter list generation.
- Builder **must** call `.with_automatic_layout(device)` on the register.
- Import builder via `import utils.sequence_utils as su` — never inline it in the submit script.
- Environment setup is **optional** — run it only when Phase 0.1 reports `ENV MISSING`, or when the user explicitly asks to (re)build it. Never as a routine step. `setup_cea_env.sh` reads archives from `~/cea_pkgs/` (override with a path argument) and creates `~/pulser-env/` regardless of the working directory.
- Never try to build `myqlm` or any `qat…` package in the container — it will not work. Surface it to the user and stop.
- Always use `nohup ... &` when launching long-running scripts over SSH.
- If SSH is refused, wait a few seconds and retry silently — do not surface this as an error to the user unless it persists beyond 3 attempts.
- Say where each step runs before running it, and record every number you report
  in a file: the collected results, the job ids, the scheduler output. A number
  quoted from a terminal nobody kept is a number nobody can check.
- Append a `NOTEBOOK.md` block for each phase that touched the cluster: host,
  remote directory, job ids, what was submitted, what came back.
