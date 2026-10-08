#!/usr/bin/env bash
# Set up everything for the hands-on session, once, before it (10-15 min, about 2 GB):
#     bash setup/setup.sh
# Creates (or updates) the conda environment wbdemo, installs WannierBerri into it, registers it
# as the Jupyter kernel "Python (wannier-berri-demo)" and runs the setup check with the graphene
# DFT step. It ends with "Ready." when everything works; running it again updates the environment.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV=wbdemo

# conda on the PATH, or a fresh Miniforge/Miniconda whose shell set-up has not run yet
CONDA=${CONDA_EXE:-$(command -v conda || true)}
for c in ~/miniforge3/bin/conda ~/miniconda3/bin/conda ~/anaconda3/bin/conda; do
    if [ -z "$CONDA" ] && [ -x "$c" ]; then CONDA=$c; fi
done
if [ -z "$CONDA" ]; then
    echo 'conda not found. Install Miniforge, open a new terminal and run this script again:'
    echo '    curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"'
    echo '    bash Miniforge3-$(uname)-$(uname -m).sh'
    exit 1
fi
run() { "$CONDA" run -n "$ENV" --no-capture-output "$@"; }

echo "== 1/4  conda environment $ENV (5-10 min)"
if "$CONDA" env list | awk '{print $1}' | grep -qx "$ENV"; then
    "$CONDA" env update -q -n "$ENV" -f setup/environment.yml
else
    "$CONDA" env create -q -n "$ENV" -f setup/environment.yml
fi

echo "== 2/4  WannierBerri (1-2 min)"
run bash setup/install_wannierberri.sh

echo "== 3/4  Jupyter kernel"
run python -m ipykernel install --user --name "$ENV" --display-name "Python (wannier-berri-demo)" \
    --env OMP_NUM_THREADS 1

echo "== 4/4  check, with the graphene DFT step"
run python setup/check_setup.py --dft
echo
echo "Before each part of the session:  conda activate $ENV  (see README.md, \"During the session\")"
