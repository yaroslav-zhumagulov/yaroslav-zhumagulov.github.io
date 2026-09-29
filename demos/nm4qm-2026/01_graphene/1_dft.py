"""Step 1 - DFT for graphene with GPAW.

* SCF on a 6x6x1 Gamma-centred grid (spin-paired, no SOC).
* NSCF on the irreducible k-points of the same grid (7 of 36), with empty
  bands for the Wannierisation.
* Band structure along G-K-M-G, only to benchmark the Wannier bands.

Run:  mpirun -np 4 python 1_dft.py
"""
import os

import numpy as np
from ase import Atoms
from gpaw import GPAW, PW
from irrep.spacegroup import SpaceGroup

os.makedirs("gpaw", exist_ok=True)

a = 2.46   # in-plane lattice constant (Angstrom)
c = 15.0   # out-of-plane period (Angstrom)
atoms = Atoms("C2",
              cell=[[a, 0, 0], [-a / 2, a * np.sqrt(3) / 2, 0], [0, 0, c]],
              scaled_positions=[[1 / 3, 2 / 3, 0], [2 / 3, 1 / 3, 0]],
              pbc=True)

calc = GPAW(mode=PW(400),
            xc="PBE",
            kpts={"size": (6, 6, 1), "gamma": True},
            txt="gpaw/scf.txt")
atoms.calc = calc
atoms.get_potential_energy()
calc.write("gpaw/scf.gpw")

sg = SpaceGroup.from_gpaw(calc)
kpts_irr = sg.get_irreducible_kpoints_grid((6, 6, 1))
calc_nscf = calc.fixed_density(kpts=kpts_irr, nbands=20, txt="gpaw/nscf.txt")
calc_nscf.write("gpaw/nscf.gpw", mode="all")

calc_bands = calc.fixed_density(kpts={"path": "GKMG", "npoints": 90},
                                symmetry="off",
                                txt="gpaw/bands.txt")
calc_bands.write("gpaw/bands.gpw")
