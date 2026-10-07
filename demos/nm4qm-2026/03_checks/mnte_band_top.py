"""MnTe: where is the valence band top with SOC, and how well do the Wannier models place it?

The highest valence band has two close maxima: one near Gamma-A (k_z ~ 0.41 * 2 pi / c) and one in the
k_z = 0 plane. Here GPAW (second-variation SOC, n || y) is evaluated on small k-grids around both, and
compared with the Wannier models built on 6x6x4 (the demo), 9x9x6 and 12x12x8 NSCF grids.

Needs ../02_mnte/gpaw/scf.gpw and the models cached by mnte_checks.py / mnte_validation.py.
Optional. Run:  python mnte_band_top.py   (5 min on 4 cores before; not timed serially)
"""
import io
import os
import warnings
from contextlib import redirect_stdout

import numpy as np
from gpaw import GPAW
from gpaw.spinorbit import soc_eigenstates

import wannierberri as wb
from mnte_checks import model

warnings.simplefilter("ignore")
energy = {"Energy": wb.calculators.tabulate.Energy(degen_thresh=1e-6)}
centres = {"near Gamma-A": np.array([0.021, -0.019, 0.408]), "k_z = 0 plane": np.array([0.85, 0.075, 0.0])}
d = np.linspace(-0.04, 0.04, 5)
local = np.stack(np.meshgrid(d, d, [-0.02, 0.0, 0.02], indexing="ij"), -1).reshape(-1, 3)
kpts = np.concatenate([c + local for c in centres.values()])
n_loc = len(local)

path = "work/mnte-bandtop.gpw"
if not os.path.exists(path):
    GPAW("../02_mnte/gpaw/scf.gpw", txt=None, legacy_gpaw=True).fixed_density(kpts=kpts, symmetry="off", nbands=40,
                                                            txt=None).write(path)
calc = GPAW(path, txt=None, legacy_gpaw=True)
EF = GPAW("../02_mnte/gpaw/nscf.gpw", txt=None, legacy_gpaw=True).get_fermi_level()
E_g = soc_eigenstates(calc, theta=90, phi=90).eigenvalues() - EF      # n || y
top_g = np.sort(E_g, axis=1)[:, 41]                                   # highest of the 26 valence states + 16 semicore

lines = ["# highest valence band with SOC (n || y), maximum over a 5x5x3 k-grid around each valley (eV, from E_F0)"]
lines.append(f"{'':16s} " + "  ".join(f"{name:>14s}" for name in centres))
lines.append(f"{'GPAW':16s} " + "  ".join(f"{top_g[i * n_loc:(i + 1) * n_loc].max():14.3f}" for i in range(2)))
for tag, nscf, label in [("mnte-nscf6", "../02_mnte/gpaw/nscf.gpw", "model 6x6x4 (demo)"),
                         ("mnte-nscf9", "work/mnte-nscf9-nscf.gpw", "model 9x9x6"),
                         ("mnte-nscf12", "work/mnte-nscf12-nscf.gpw", "model 12x12x8")]:
    system, _ = model(nscf, tag)            # same density: compare absolute energies, all from E_F0 of the demo
    with redirect_stdout(io.StringIO()):
        system.set_soc_axis(theta=90, phi=90, units="degrees")
        E_w = wb.evaluate_k_path(system, path=wb.Path(system, k_list=kpts), tabulators=energy,
                                 parallel=False).get_eigenvalues() - EF
    top_w = E_w[:, -1]
    lines.append(f"{label:16s} " + "  ".join(f"{top_w[i * n_loc:(i + 1) * n_loc].max():14.3f}" for i in range(2))
                 + f"   max |E_W - E_GPAW| of the top band: {np.abs(top_w - top_g).max() * 1e3:.0f} meV")

open("results/mnte_band_top.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
