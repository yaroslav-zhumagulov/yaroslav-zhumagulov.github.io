#!/usr/bin/env bash
# Install WannierBerri master at the tested commit, plus the two fixes in patches/.
# Run it inside the activated environment:  bash setup/install_wannierberri.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
SRC=${WB_SRC:-$HERE/.wannier-berri}          # where the source goes (git-ignored)
COMMIT=0033c84

if [ ! -d "$SRC/.git" ]; then
    # history without file contents, and no tests/ (250 MB of test data): about 25 MB instead of 700
    git clone --quiet --filter=blob:none --no-checkout https://github.com/wannier-berri/wannier-berri.git "$SRC"
    git -C "$SRC" sparse-checkout set --no-cone '/*' '!/tests/'
fi
cd "$SRC"
git fetch --quiet origin
git checkout --quiet --force "$COMMIT"       # also drops patches applied by an earlier run
git apply "$HERE"/patches/*.patch
python -m pip install --quiet .
python -c "import wannierberri as wb; print('WannierBerri', wb.__version__, 'installed')"
