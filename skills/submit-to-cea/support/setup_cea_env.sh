#!/bin/bash
# Build (or top up) the Pulser venv inside the ccc-quantum container.
#
# The compute nodes have no internet, so this installs from archives that were
# downloaded on a machine that does and rsync'd to ~/cea_pkgs/ (see the skill's
# "Environment setup" section). Versions are whatever those archives are — this
# script pins nothing. Re-run it after adding more archives to the same dir; it
# reinstalls the whole set and re-checks the imports.
#
# Usage:  bash setup_cea_env.sh [PKG_DIR]        (PKG_DIR default: ~/cea_pkgs)
#
# Exit 0  -> `import pulser` and `import pulser_myqlm` both work.
# Exit 1  -> prints one `MISSING: <module>` line per unmet import; the caller
#            decides whether to fetch it (a `qat`/`myqlm` line means: give up).

set -euo pipefail

PKG_DIR="${1:-$HOME/cea_pkgs}"
ENV_DIR="$HOME/pulser-env"

shopt -s nullglob
pkgs=("$PKG_DIR"/*.whl "$PKG_DIR"/*.tar.gz)
if [ ${#pkgs[@]} -eq 0 ]; then
    echo "ERROR: no .whl or .tar.gz archives in $PKG_DIR" >&2
    exit 1
fi

if [ ! -d "$ENV_DIR" ]; then
    echo "Creating venv: $ENV_DIR (system site packages on -> reuse container numpy/scipy)"
    /usr/bin/python3 -c "import venv; venv.create('$ENV_DIR', system_site_packages=True)"
fi
# shellcheck disable=SC1091
source "$ENV_DIR/bin/activate"

echo "Installing ${#pkgs[@]} archive(s) from $PKG_DIR (--no-deps)..."
pip install --no-deps --no-index --no-build-isolation "${pkgs[@]}"

# Report unmet imports for the caller (SKILL.md "Environment setup", step E.4).
rc=0
python3 - <<'EOF' || rc=$?
import importlib, sys

missing = []
for mod in ("pulser", "pulser_myqlm"):
    try:
        importlib.import_module(mod)
    except ModuleNotFoundError as e:
        missing.append(e.name or mod)
    except ImportError as e:
        missing.append(getattr(e, "name", None) or mod)

for m in dict.fromkeys(missing):  # de-dup, keep order
    print(f"MISSING: {m}")
sys.exit(1 if missing else 0)
EOF

if [ "$rc" -eq 0 ]; then
    echo "ENV OK: $(python3 -c 'import pulser, pulser_myqlm; print("pulser", pulser.__version__, "pulser-myqlm", getattr(pulser_myqlm, "__version__", "?"))')"
    echo "Activate with:  source $ENV_DIR/bin/activate"
fi
exit "$rc"
