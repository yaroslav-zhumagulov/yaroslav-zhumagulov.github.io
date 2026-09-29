"""Graphene checks: is the 36 ueV Kane-Mele gap of the Wannier model a converged, physical number?

1. Wannier gap at K vs GPAW second-variation SOC, for cutoff, vacuum, number of bands, SCF and NSCF grids.
2. Which PAW channel gives the gap: SOC restricted to l = 1 (p) or l = 2 (d) partial waves
   (at the converged cutoff; the PAW dataset itself is varied in paw_setups.py).
3. Wannier interpolation error along G-K-M-G for NSCF grids 6x6, 9x9, 12x12.
4. Spin Hall conductivity with and without the external (position-operator) terms, inside and outside the gap.

Optional, not needed for the talk. Needs the runs from dft_scan.py.  Run:  python graphene_checks.py   (about 10 min)
"""
import io
import warnings
from contextlib import redirect_stdout

import numpy as np
import gpaw.spinorbit
from gpaw import GPAW
from gpaw.spinorbit import soc_eigenstates
from irrep.spacegroup import SpaceGroup

import wannierberri as wb
from wannierberri.symmetry.projections import Projection, ProjectionsSet

warnings.simplefilter("ignore")
np.random.seed(0)  # the Wannierisation draws random numbers: fix them for reproducible output
K = np.array([1 / 3, 1 / 3, 0])
energy = wb.calculators.tabulate.Energy(degen_thresh=1e-8)
soc_full = gpaw.spinorbit.soc


def only_l(l_keep):
    """PAW SOC matrix restricted to partial waves with angular momentum l_keep."""
    def soc(setup, xc, D_sp):
        dVL_vii = soc_full(setup, xc, D_sp)
        l_i = np.concatenate([[l] * (2 * l + 1) for l in setup.l_j])
        keep = np.isin(l_i, l_keep)
        return dVL_vii * np.outer(keep, keep)
    return soc


def wannier_model(calc):
    EF = calc.get_fermi_level()
    sg = SpaceGroup.from_gpaw(calc)
    pz = Projection(position_num=[[1 / 3, 2 / 3, 0], [2 / 3, 1 / 3, 0]], orbital="pz", spacegroup=sg)
    with redirect_stdout(io.StringIO()):
        wandata = wb.WannierDataSOC.from_gpaw(calc, projections=ProjectionsSet([pz]), seedname="work/g")
        wandata.wannierise(froz_min=EF - 2.9, froz_max=EF + 2.8, frozen_states={0: [1]},
                           num_iter=100, sitesym=True)
        return wb.SystemSOC.from_wannierdata(wandata, berry=True)


def gap_wannier(system):
    system.set_soc_axis(alpha_soc=1)
    E = wb.evaluate_k(system, k=K, calculators={"E": energy}).data[0]
    return E[2] - E[1]


def gap_gpaw(calc):
    iK = np.argmin(np.linalg.norm(calc.get_ibz_k_points() - K, axis=1))
    E = soc_eigenstates(calc).eigenvalues()[iK] - calc.get_fermi_level()
    E = np.sort(E[np.argsort(np.abs(E))[:4]])
    return E[2] - E[1]


lines = ["# Kane-Mele gap at K (ueV): Wannier model (2 pz functions) vs GPAW (second variation, all bands)"]
runs = [("g400", "demo: 400 eV, c = 15 A, 20 bands, 6x6"), ("g600", "600 eV"), ("g800", "800 eV"),
        ("g400-c20", "c = 20 A"), ("g400-nb60", "60 bands"), ("g600-nb60", "600 eV, 60 bands"),
        ("g400-scf12", "SCF grid 12x12"), ("g400-k9", "NSCF 9x9"), ("g400-k12", "NSCF 12x12")]
systems = {}
for tag, label in runs:
    calc = GPAW(f"work/{tag}-nscf.gpw", txt=None)
    systems[tag] = wannier_model(calc)
    lines.append(f"{label:40s} Wannier {gap_wannier(systems[tag]) * 1e6:6.1f}   GPAW {gap_gpaw(calc) * 1e6:6.1f}")

lines.append("# PAW channel decomposition (600 eV, 60 bands)")
for l_keep, label in [([1], "p only (l = 1)"), ([2], "d only (l = 2)"), ([0, 1, 2], "all")]:
    gpaw.spinorbit.soc = only_l(l_keep)
    calc = GPAW("work/g600-nb60-nscf.gpw", txt=None)
    lines.append(f"{label:40s} Wannier {gap_wannier(wannier_model(calc)) * 1e6:6.1f}   GPAW {gap_gpaw(calc) * 1e6:6.1f}")
gpaw.spinorbit.soc = soc_full

system = systems["g400"]
system.set_soc_axis(alpha_soc=0)
EF = GPAW("work/g400-nscf.gpw", txt=None).get_fermi_level()
E_D = wb.evaluate_k(system, k=K, calculators={"E": energy}).data[0][0] - EF
lines.append(f"# Dirac point relative to the GPAW Fermi level (demo): {E_D * 1e6:+.1f} ueV")

lines.append("# interpolation error along G-K-M-G, bands inside the frozen window (meV)")
bs = GPAW("work/g400-bands.gpw", txt=None).band_structure()
EF = GPAW("work/g400-nscf.gpw", txt=None).get_fermi_level()
E_dft = bs.energies[0] - EF
for tag in ("g400", "g400-k9", "g400-k12"):
    system = systems[tag]
    system.set_soc_axis(alpha_soc=0)
    E_w = wb.evaluate_k_path(system, path=wb.Path(system, k_list=bs.path.kpts)).get_eigenvalues()[:, ::2] - EF
    err = []
    for Ew, Ed in zip(E_w, E_dft):
        for e in Ew[(Ew > -2.9) & (Ew < 2.8)]:
            err.append(np.abs(Ed - e).min())
    lines.append(f"{tag:40s} max {np.max(err) * 1e3:7.2f}   mean {np.mean(err) * 1e3:7.3f}")

lines.append("# spin Hall conductivity (e/2pi), alpha = 1000 (gap +-18 meV), 600x600 grid, at E_F - E_F0 = -60, 0, +60 meV")
system.set_soc_axis(alpha_soc=1000)
e2h, c = 3.874045865e-5, system.real_lattice[2, 2] * 1e-10
Efermi = EF + np.array([-0.06, 0.0, 0.06])
for ext in (False, True):
    shc = wb.calculators.static.SHC(Efermi=Efermi,
                                    kwargs_formula={"spin_current_type": "simple", "external_terms": ext})
    with redirect_stdout(io.StringIO()):
        r = wb.run(system, grid=wb.Grid(system, NK=(600, 600, 1)), calculators={"shc": shc}, fout_name="work/g")
    lines.append(f"external terms {str(ext):25s} {np.round(r.results['shc'].data[:, 0, 1, 2] * c / e2h, 4)}")

open("results/graphene_checks.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
