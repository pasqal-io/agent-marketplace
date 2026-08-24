#!/bin/bash

# Setup script for CEA/TGCC environment
# Run this script after uploading the zip files and unzipping them
#
# The Pulser version below (1.6.5) is deliberately older than the one CI pins.
# Compute nodes here have no network, so Pulser is installed from a zip a human
# downloaded, alongside Pulser-myQLM 0.8.3 — and that pair is what was last
# validated inside the ccc-quantum container. Bumping it means re-checking myQLM
# against the newer Pulser on the cluster itself; it is not a local edit.

set -e  # Exit on error

echo "========================================="
echo "Setting up CEA environment for Pulser"
echo "========================================="
echo ""
echo "Prerequisites:"
echo "1. Download and upload these zip files to TGCC:"
echo "   - Pulser-1.6.5.zip from https://github.com/pasqal-io/Pulser/releases/tag/v1.6.5"
echo "   - Pulser-myQLM-0.8.3.zip from https://github.com/pasqal-io/Pulser-myQLM/releases/tag/v0.8.3"
echo "2. Unzip them in your home directory"
echo "3. Access the ccc-quantum container: pcocc-rs run ccc-quantum"
echo ""
read -p "Press Enter when ready to continue..."

# Check if we're in the container (optional check)
echo ""
echo "Checking environment..."

# Define environment name
ENV_NAME="pulser-env"

# Create virtual environment with system site packages
echo ""
echo "Creating virtual environment: $ENV_NAME"
/usr/bin/python3 -c "import venv; venv.create('$ENV_NAME', system_site_packages=True)"

# Activate environment
echo "Activating environment..."
source $ENV_NAME/bin/activate

# Install Pulser
echo ""
echo "========================================="
echo "Installing Pulser 1.6.5..."
echo "========================================="
if [ -d "Pulser-1.6.5/pulser-core" ]; then
    cd Pulser-1.6.5/pulser-core
    pip install --no-deps --no-build-isolation .
    cd ../..
    echo "pulser-core installed successfully!"
else
    echo "ERROR: Pulser-1.6.5/pulser-core directory not found!"
    echo "Please unzip Pulser-1.6.5.zip first"
    exit 1
fi

# Install Pulser-myQLM
echo ""
echo "========================================="
echo "Installing Pulser-myQLM 0.8.3..."
echo "========================================="
if [ -d "Pulser-myQLM-0.8.3" ]; then
    cd Pulser-myQLM-0.8.3
    python3 setup.py install
    cd ..
    echo "Pulser-myQLM installed successfully!"
else
    echo "ERROR: Pulser-myQLM-0.8.3 directory not found!"
    echo "Please unzip Pulser-myQLM-0.8.3.zip first"
    exit 1
fi


# numpy and scipy are available as system packages via system_site_packages=True
# No pip install needed (TGCC has no internet access)
echo ""
echo "Verifying system packages..."
python3 -c "import numpy; print(f'  numpy {numpy.__version__} OK')"
python3 -c "import scipy; print(f'  scipy {scipy.__version__} OK')"
python3 -c "import pulser; print(f'  pulser-core OK')"

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "To activate the environment, run:"
echo "    source $ENV_NAME/bin/activate"
echo ""
echo "To submit jobs:"
echo "    python submit_claude.py --backend cea --n-shots 200"
echo ""
