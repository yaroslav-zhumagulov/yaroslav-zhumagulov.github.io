# Spin and anomalous Hall effects with WannierBerri and GPAW

Material for a 45-minute hands-on session at NM4QM 2026, *Numerical methods for quantum matter: from
nanographenes to moiré materials* (DIPC, Donostia-San Sebastián, 13–16 October 2026). Everyone runs the same two
notebooks on their own laptop, about six minutes of computing in total.

The session has two parts. In the first we look at graphene: spin–orbit coupling opens a tiny gap (about 40 μeV)
and makes it a quantum spin Hall insulator, and we get the gap and the spin Hall conductivity e/2π from two Wannier
functions built on seven k-points. In the second we look at MnTe, an altermagnet: no net magnetisation, but an
anomalous Hall effect that depends on the direction of the Néel vector. Along the way you build symmetry-adapted
Wannier functions straight from GPAW and switch spin–orbit coupling on for any spin axis without redoing the DFT.

## Setup (do this before the session, about 20 minutes)

```
git clone https://github.com/yaroslav-zhumagulov/wannier-berri-demo
cd wannier-berri-demo
conda env create -f setup/environment.yml
conda activate wbdemo
bash setup/install_wannierberri.sh
python setup/check_setup.py --dft
```

The last command should end with `Ready.`

- On Windows, use WSL2 with Ubuntu.
- If you already have GPAW 26.7, you can skip the conda environment: make a virtual environment on top of it
  (`python -m venv --system-site-packages .venv`), install `irrep==3.3.0`, `ray[default]==2.44.1`, `numba` and
  `jupyterlab` if they are missing, and run the install script inside it.
- `install_wannierberri.sh` installs the master branch of WannierBerri, because the PyPI release does not have the
  altermagnetic Wannierisation yet. In Jupyter or VS Code, make sure the notebook runs with this environment; the first
  cell stops with a message if it finds another WannierBerri.

## During the session

Graphene (minutes 8–19):

```
cd 01_graphene
python 1_dft.py     # 10 s
jupyter lab graphene.ipynb
```

MnTe (minutes 19–37): the same in `02_mnte`, with `mnte.ipynb`; the DFT step takes about 45 s.

Every step of a notebook ends with a checkpoint, the numbers you should get. The "Try it" cells are small
experiments that take seconds, and the bonus steps at the end are for later.

If something goes wrong: unpack `dft-files.tar.gz` (we bring it) in this folder if the DFT step fails, or run
`bash run_all.sh` to do both parts without Jupyter (six minutes). Executed notebooks from our run are in
`reference/`. Without Ray the notebooks still run, only slower.

## What is where

```
setup/            conda environment, WannierBerri install, setup check, packing the DFT files
01_graphene/      DFT script and notebook for graphene
02_mnte/          DFT script and notebook for MnTe
reference/        both notebooks with their output
slides/           the slides (index.html, PDF) and the scripts that make them
03_checks/        convergence checks, not needed for the session (they take hours)
run_all.sh        everything in one go
```

The notebooks are stored without output; `*/results/` has the numbers they save.

## Slides

Open `slides/index.html` in a browser, or the online copy at
https://yaroslav-zhumagulov.github.io/demos/nm4qm-2026/slides/. Press P to present, N for the speaker notes and R to
replay an animation. The slides and the notebooks link to each other: the label in a slide's header opens that step
of the notebook, and each notebook step lists its slides.

To rebuild them after changing the notebooks or the text:

```
python slides/make_figures.py     # figures and animation frames from */results/
python slides/render_latex.py     # formulas (needs latex and dvisvgm)
python slides/link_notebooks.py   # slide numbers in the notebooks, after moving slides
python slides/make_pdf.py         # the PDF (needs playwright with chromium)
```

## Notes

- Tested with Python 3.12, serial GPAW 26.7.0, irrep 3.3.0, Ray 2.44.1 and WannierBerri master at commit
  `450e335`, on an Apple M2 laptop (8 Ray workers). The checkpoint numbers use the PAW
  datasets of gpaw-setups 24.11.0.
- GPAW 26.7 runs its new code by default. The DFT scripts and the notebooks ask for the classic one
  (`legacy_gpaw=True`), whose files irrep and WannierBerri read, and the first cell of each notebook tells irrep 3.3
  where GPAW 26.7 keeps `atomrotations`.
- For the spin Hall plateau of graphene we scale spin–orbit coupling by 1000, because the real gap is too small for
  a uniform k-grid. The last notebook step checks this with the real coupling on a grid refined around K and gets
  0.9997 e/2π.
- MnTe uses PBE+U with U = 4 eV. The band gap comes out too small (0.77 eV against 1.27–1.41 eV measured), and a
  larger U does not fix it. The Hall conductivity is computed at 150 K, the temperature of the measurement.
- The Wannierisation uses random numbers, so the notebooks fix the seed to get the same numbers every time.
- `03_checks/` tests the demo settings: cutoff, vacuum, k-grids, U, the PAW dataset and more. Its results are stored
  in `03_checks/results/`; for example, the graphene gap goes from 35.8 μeV at 400 eV to 41.1 μeV at 600 eV
  (measured: 42.2 μeV).

## References

- S. S. Tsirkin, npj Comput. Mater. 7, 33 (2021): WannierBerri
- J. J. Mortensen et al., J. Chem. Phys. 160, 092503 (2024): GPAW
- M. Iraola et al., Comput. Phys. Commun. 272, 108226 (2022): irrep
- N. Marzari and D. Vanderbilt, Phys. Rev. B 56, 12847 (1997); I. Souza, N. Marzari and D. Vanderbilt, Phys. Rev. B
  65, 035109 (2001): Wannier functions
- X. Wang, J. R. Yates, I. Souza and D. Vanderbilt, Phys. Rev. B 74, 195118 (2006): anomalous Hall conductivity from
  Wannier functions
- C. L. Kane and E. J. Mele, Phys. Rev. Lett. 95, 226801 and 146802 (2005); J. Sichau et al., Phys. Rev. Lett. 122,
  046403 (2019): the gap of graphene
- L. Šmejkal, J. Sinova and T. Jungwirth, Phys. Rev. X 12, 031042 (2022): altermagnets
- R. D. Gonzalez Betancourt et al., Phys. Rev. Lett. 130, 036702 (2023): anomalous Hall effect in MnTe
