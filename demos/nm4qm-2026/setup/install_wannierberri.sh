#!/usr/bin/env bash
# Install WannierBerri master at the tested commit; the PyPI release does not have the
# altermagnetic Wannierisation yet. Run it inside the activated environment:
#     bash setup/install_wannierberri.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
SRC=${WB_SRC:-$HERE/.wannier-berri}          # where the source goes (git-ignored)
COMMIT=450e335

if [ ! -d "$SRC/.git" ]; then
    # history without file contents, and no tests/ (250 MB of test data): about 25 MB instead of 700
    git clone --quiet --filter=blob:none --no-checkout https://github.com/wannier-berri/wannier-berri.git "$SRC"
    git -C "$SRC" sparse-checkout set --no-cone '/*' '!/tests/'
fi
cd "$SRC"
git fetch --quiet origin
git checkout --quiet --force "$COMMIT"       # --force drops local edits, e.g. patches from an older version of this script
python -m pip install --quiet .
python -c "import wannierberri as wb; print('WannierBerri', wb.__version__, 'installed')"
