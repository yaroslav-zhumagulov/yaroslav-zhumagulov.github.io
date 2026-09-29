#!/usr/bin/env bash
# Run the whole hands-on part without Jupyter: both DFT steps and both notebooks
# (about 6 min on 8 cores). The executed notebooks go to reference/; the notebooks in
# 01_graphene/ and 02_mnte/ stay as they are.
#
#   bash run_all.sh              # graphene and MnTe
#   bash run_all.sh graphene     # one of them
#   NP=2 bash run_all.sh         # fewer MPI ranks for GPAW (default 4)
#   MPIRUN=/path/to/mpirun bash run_all.sh   # the mpirun that belongs to GPAW's MPI library
set -euo pipefail
cd "$(dirname "$0")"
NP=${NP:-4}
MPIRUN=${MPIRUN:-mpirun}
KERNEL=${KERNEL:-python3}

run_part() {
    local dir=$1 notebook=$2 t0
    t0=$SECONDS
    echo "== $dir: DFT with $NP MPI ranks"
    (cd "$dir" && "$MPIRUN" -np "$NP" python 1_dft.py > /dev/null)
    echo "   $((SECONDS - t0)) s"
    t0=$SECONDS
    echo "== $dir/$notebook"
    jupyter nbconvert --to notebook --execute --log-level WARN --ExecutePreprocessor.timeout=1800 \
        --ExecutePreprocessor.kernel_name="$KERNEL" "$dir/$notebook" --output-dir reference
    echo "   $((SECONDS - t0)) s"
}

case "${1:-all}" in
    all)      run_part 01_graphene graphene.ipynb; run_part 02_mnte mnte.ipynb ;;
    graphene) run_part 01_graphene graphene.ipynb ;;
    mnte)     run_part 02_mnte mnte.ipynb ;;
    *)        echo "usage: bash run_all.sh [all|graphene|mnte]"; exit 1 ;;
esac
echo "Done: executed notebooks in reference/, numbers in */results/."
