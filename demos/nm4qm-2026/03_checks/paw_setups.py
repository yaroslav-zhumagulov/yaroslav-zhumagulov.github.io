"""Graphene SOC gap and the carbon PAW dataset.

The first-order SOC of the p_z Wannier functions comes from the d partial waves of the carbon dataset
(graphene_checks.py), so the dataset itself is a convergence parameter. Here it is varied with GPAW's
own generator: the distributed dataset (2s,s,2p,p,d, r_c = 1.2 Bohr), the same projectors regenerated,
a smaller augmentation radius, one or three p projectors, more d projectors and f projectors. For each:
SCF at 800 eV (1000 eV for r_c = 1.0), NSCF with 60 bands on the 6x6 irreducible points, and the gap at
K with SOC from all channels, from p only, and from d only.

Optional, not needed for the talk. Run:  python paw_setups.py   (about 20 min)
"""
import io
import os
import subprocess
import sys
import warnings
from contextlib import redirect_stdout

import numpy as np
import gpaw.spinorbit
from ase import Atoms
from gpaw import GPAW, PW, setup_paths
from gpaw.spinorbit import soc_eigenstates
from irrep.spacegroup import SpaceGroup

import wannierberri as wb
from wannierberri.symmetry.projections import Projection, ProjectionsSet

warnings.simplefilter("ignore")
np.random.seed(0)  # the Wannierisation draws random numbers: fix them for reproducible output
HERE = os.path.abspath("work/setups")
os.makedirs(HERE, exist_ok=True)
setup_paths.insert(0, HERE)
K = np.array([1 / 3, 1 / 3, 0])
energy = wb.calculators.tabulate.Energy(degen_thresh=1e-8)
soc_full = gpaw.spinorbit.soc

# tag: (projectors, radius in Bohr, cutoff in eV, description); "paw" is the dataset distributed with GPAW
DATASETS = {
    "paw": (None, None, 800, "distributed (gpaw-setups): 2s,s,2p,p,d"),
    "ref": ("2s,s,2p,p,d", "1.2", 800, "regenerated: 2s,s,2p,p,d, r_c = 1.2"),
    "r10": ("2s,s,2p,p,d", "1.0", 1000, "regenerated, r_c = 1.0 Bohr"),
    "p1": ("2s,s,2p,d", "1.2", 800, "one p projector (2p)"),
    "p3": ("2s,s,2p,p,p,d", "1.2", 800, "three p projectors"),
    "dd": ("2s,s,2p,p,d,d", "1.2", 800, "two d projectors"),
    "ddd": ("2s,s,2p,p,d,d,d", "1.2", 800, "three d projectors"),
    "f": ("2s,s,2p,p,d,f", "1.2", 800, "one d and one f projector"),
    "ddf": ("2s,s,2p,p,d,d,f", "1.2", 800, "two d and one f projector"),
    "ddff": ("2s,s,2p,p,d,d,f,f", "1.2", 800, "two d and two f projectors"),
}


def only_l(l_keep):
    """PAW SOC matrix restricted to partial waves with angular momentum l_keep."""
    def soc(setup, xc, D_sp):
        dVL_vii = soc_full(setup, xc, D_sp)
        l_i = np.concatenate([[l] * (2 * l + 1) for l in setup.l_j])
        keep = np.isin(l_i, l_keep)
        return dVL_vii * np.outer(keep, keep)
    return soc


def dft(tag, ecut):
    path = f"work/setups/g-{tag}-nscf.gpw"
    if not os.path.exists(path):
        a = 2.46
        atoms = Atoms("C2", cell=[[a, 0, 0], [-a / 2, a * np.sqrt(3) / 2, 0], [0, 0, 15]],
                      scaled_positions=[[1 / 3, 2 / 3, 0], [2 / 3, 1 / 3, 0]], pbc=True)
        calc = GPAW(mode=PW(ecut), xc="PBE", setups={"C": tag}, kpts={"size": (6, 6, 1), "gamma": True},
                    txt=None)
        atoms.calc = calc
        atoms.get_potential_energy()
        kpts = SpaceGroup.from_gpaw(calc).get_irreducible_kpoints_grid((6, 6, 1))
        calc.fixed_density(kpts=kpts, nbands=60, txt=None).write(path, mode="all")
    return GPAW(path, txt=None)


def gap_wannier(calc):
    EF = calc.get_fermi_level()
    sg = SpaceGroup.from_gpaw(calc)
    pz = Projection(position_num=[[1 / 3, 2 / 3, 0], [2 / 3, 1 / 3, 0]], orbital="pz", spacegroup=sg)
    with redirect_stdout(io.StringIO()):
        wandata = wb.WannierDataSOC.from_gpaw(calc, projections=ProjectionsSet([pz]), seedname="work/setups/g",
                                              IBend=20)   # the 20 bands of the demo
        wandata.wannierise(froz_min=EF - 2.9, froz_max=EF + 2.8, frozen_states={0: [1]}, num_iter=100, sitesym=True)
        system = wb.SystemSOC.from_wannierdata(wandata, berry=True)
        system.set_soc_axis(alpha_soc=1)
    E = wb.evaluate_k(system, k=K, calculators={"E": energy}).data[0]
    return E[2] - E[1]


def gap_gpaw(calc):
    iK = np.argmin(np.linalg.norm(calc.get_ibz_k_points() - K, axis=1))
    E = soc_eigenstates(calc).eigenvalues()[iK] - calc.get_fermi_level()
    E = np.sort(E[np.argsort(np.abs(E))[:4]])
    return E[2] - E[1]


lines = ["# Kane-Mele gap at K (ueV) for different carbon PAW datasets; Wannier / GPAW (second variation, 60 bands)",
         "# last column: largest change of the 6 lowest bands (no SOC) on the 6x6 grid against the distributed dataset",
         f"# {'dataset':40s} {'all channels':>16s} {'p only':>16s} {'d only':>16s} {'bands (meV)':>12s}"]
E_ref = None
for tag, (projectors, radius, ecut, label) in DATASETS.items():
    if projectors and not os.path.exists(f"{HERE}/C.{tag}.PBE"):
        subprocess.run([sys.executable, "-m", "gpaw", "dataset", "C", "-f", "PBE", "-s", "-P", projectors,
                        "-r", radius, "-w", "-t", tag], cwd=HERE, check=True, capture_output=True)
    row = []
    for l_keep in ([0, 1, 2, 3], [1], [2]):
        gpaw.spinorbit.soc = only_l(l_keep)
        calc = dft(tag, ecut)
        try:
            row.append(f"{gap_wannier(calc) * 1e6:6.1f} / {gap_gpaw(calc) * 1e6:5.1f}")
        except ValueError as err:   # irrep refuses states that break the symmetry (a sign of ghost states)
            row.append("failed")
            print(f"{tag}: {str(err).splitlines()[0]}", flush=True)
    gpaw.spinorbit.soc = soc_full
    E = np.array([calc.get_eigenvalues(kpt=k)[:6] for k in range(len(calc.get_ibz_k_points()))])
    E -= calc.get_fermi_level()
    E_ref = E if E_ref is None else E_ref
    lines.append(f"{label + f', {ecut} eV':42s} " + "  ".join(f"{r:>16s}" for r in row)
                 + f"  {np.abs(E - E_ref).max() * 1e3:10.1f}")
    print(lines[-1], flush=True)

open("results/paw_setups.txt", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
