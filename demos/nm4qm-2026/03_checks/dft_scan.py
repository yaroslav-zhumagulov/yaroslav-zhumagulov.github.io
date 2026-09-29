"""DFT runs for the optional convergence and sensitivity checks (not needed for the talk).

Graphene: plane-wave cutoff, vacuum, SCF and NSCF k-grids, number of bands.
MnTe:     plane-wave cutoff and SCF k-grid (gap on the SCF grid), Hubbard U (with NSCF runs for Wannier models),
          and NSCF (Wannier) grids 6x6x4 (the demo), 9x9x6 and 12x12x8.

Everything goes to work/ (about 1.5 GB); runs whose output exists are skipped.
Run (about 40 min on 4 cores):
    mpirun -np 4 python dft_scan.py
"""
import os

import numpy as np
from ase import Atoms
from gpaw import GPAW, PW
from gpaw.mpi import world
from irrep.spacegroup import SpaceGroup

os.makedirs("work", exist_ok=True)
os.makedirs("results", exist_ok=True)


def graphene(ecut, c, nk, nbands, tag, bands_path=False, nk_scf=6):
    if os.path.exists(f"work/{tag}-nscf.gpw"):
        return
    a = 2.46
    atoms = Atoms("C2", cell=[[a, 0, 0], [-a / 2, a * np.sqrt(3) / 2, 0], [0, 0, c]],
                  scaled_positions=[[1 / 3, 2 / 3, 0], [2 / 3, 1 / 3, 0]], pbc=True)
    calc = GPAW(mode=PW(ecut), xc="PBE", kpts={"size": (nk_scf, nk_scf, 1), "gamma": True}, txt=None)
    atoms.calc = calc
    atoms.get_potential_energy()
    kpts = SpaceGroup.from_gpaw(calc).get_irreducible_kpoints_grid((nk, nk, 1))
    calc.fixed_density(kpts=kpts, nbands=nbands, txt=None).write(f"work/{tag}-nscf.gpw", mode="all")
    if bands_path:
        calc.fixed_density(kpts={"path": "GKMG", "npoints": 90}, symmetry="off",
                           txt=None).write(f"work/{tag}-bands.gpw")


def mnte(ecut, U, tag=None, kscf=(6, 6, 4), nscf=((6, 6, 4),)):
    """SCF (gap and moment on the SCF grid); with a tag also NSCF runs on the irreducible k-points of nscf."""
    a, c = 4.148, 6.711
    atoms = Atoms("Mn2Te2", cell=[[a, 0, 0], [-a / 2, a * np.sqrt(3) / 2, 0], [0, 0, c]],
                  scaled_positions=[[0, 0, 0], [0, 0, 1 / 2], [1 / 3, 2 / 3, 1 / 4], [2 / 3, 1 / 3, 3 / 4]],
                  magmoms=[5, -5, 0, 0], pbc=True)
    calc = GPAW(mode=PW(ecut), xc="PBE", setups={"Mn": f":d,{U}"},
                kpts={"size": kscf, "gamma": True}, txt=None)
    atoms.calc = calc
    atoms.get_potential_energy()
    ef = calc.get_fermi_level()
    e = np.array([calc.get_eigenvalues(kpt=k, spin=0) for k in range(len(calc.get_ibz_k_points()))]) - ef
    row = (ecut, U, kscf[0], calc.get_magnetic_moments()[0], e[:, 21].min() - e[:, 20].max())
    for grid in nscf if tag else ():
        name = f"work/{tag}-nscf.gpw" if grid == (6, 6, 4) else f"work/{tag}-nscf{grid[0]}-nscf.gpw"
        if not os.path.exists(name):
            kpts = SpaceGroup.from_gpaw(calc).get_irreducible_kpoints_grid(grid)
            calc.fixed_density(kpts=kpts, nbands=40, txt=None).write(name, mode="all")
    return row


# graphene: base case (demo settings), cutoff, vacuum, bands and k-grid variations
graphene(400, 15, 6, 20, "g400", bands_path=True)
graphene(400, 15, 6, 60, "g400-nb60")
graphene(600, 15, 6, 20, "g600")
graphene(800, 15, 6, 20, "g800")
graphene(400, 20, 6, 20, "g400-c20")
graphene(400, 15, 9, 20, "g400-k9")
graphene(400, 15, 12, 20, "g400-k12")
graphene(400, 15, 6, 20, "g400-scf12", nk_scf=12)
graphene(600, 15, 6, 60, "g600-nb60")

# MnTe: NSCF (Wannier) grids on the density of the demo; 6x6x4 is the grid of the demo itself
for n, grid in [(6, (6, 6, 4)), (9, (9, 9, 6)), (12, (12, 12, 8))]:
    if not os.path.exists(f"work/mnte-nscf{n}-nscf.gpw"):
        scf = GPAW("../02_mnte/gpaw/scf.gpw", txt=None)
        kpts = SpaceGroup.from_gpaw(scf).get_irreducible_kpoints_grid(grid)
        scf.fixed_density(kpts=kpts, nbands=40, txt=None).write(f"work/mnte-nscf{n}-nscf.gpw", mode="all")

# MnTe: cutoff, SCF k-grid and U
table = "results/mnte_dft_scan.txt"
rows = [mnte(e, 4.0) for e in (400, 600, 800)]
rows += [mnte(400, 4.0, tag="mnte-k9", kscf=(9, 9, 6))]
rows += [mnte(400, U, tag=f"mnte-U{U:.0f}") for U in (3.0, 5.0)]
if world.rank == 0:
    np.savetxt(table, rows, fmt="%8.3f",
               header="ecut(eV)  U(eV)  N_k,scf  m_Mn(muB)  gap on the SCF grid (eV), no SOC")
    print(open(table).read())
