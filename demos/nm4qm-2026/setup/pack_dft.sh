#!/usr/bin/env bash
# Pack the GPAW results so that someone whose DFT step fails can go on with the notebooks.
# Organisers: run the DFT steps once, then  bash setup/pack_dft.sh  and share dft-files.tar.gz
# (about 40 MB). Participants unpack it in the repository root:  tar -xzf dft-files.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
tar -czf dft-files.tar.gz 01_graphene/gpaw/nscf.gpw 01_graphene/gpaw/bands.gpw 02_mnte/gpaw/nscf.gpw
ls -lh dft-files.tar.gz
