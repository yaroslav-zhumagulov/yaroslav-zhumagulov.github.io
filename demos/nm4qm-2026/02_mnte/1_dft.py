"""Step 1 - DFT for the altermagnet MnTe with GPAW.

* Collinear antiferromagnet (no SOC), PBE+U with U = 4 eV on Mn-d
  (the value used by Kriegner et al., PRB 96, 214418 (2017)).
* Experimental lattice constants; 400 eV is converged to 3 meV in the gap
  (see 03_checks/).
* SCF on a 6x6x4 Gamma-centred grid.
* NSCF on the irreducible k-points of the same grid (24 of 144), with empty
  bands for the Wannierisation.

Run:  python 1_dft.py
"""
import os

import numpy as np
from ase import Atoms
from gpaw import GPAW, PW
from irrep.spacegroup import SpaceGroup

os.makedirs("gpaw", exist_ok=True)

a, c = 4.148, 6.711   # NiAs structure, experimental (Angstrom)
atoms = Atoms("Mn2Te2",
              cell=[[a, 0, 0], [-a / 2, a * np.sqrt(3) / 2, 0], [0, 0, c]],
              scaled_positions=[[0, 0, 0], [0, 0, 1 / 2],
                                [1 / 3, 2 / 3, 1 / 4], [2 / 3, 1 / 3, 3 / 4]],
              magmoms=[5, -5, 0, 0],
              pbc=True)

calc = GPAW(mode=PW(400),
            xc="PBE",
            setups={"Mn": ":d,4.0"},
            kpts={"size": (6, 6, 4), "gamma": True},
            legacy_gpaw=True,  # GPAW 26.7: irrep and WannierBerri read the files of the classic code
            txt="gpaw/scf.txt")
atoms.calc = calc
atoms.get_potential_energy()
calc.write("gpaw/scf.gpw")

sg = SpaceGroup.from_gpaw(calc)
kpts_irr = sg.get_irreducible_kpoints_grid((6, 6, 4))
calc_nscf = calc.fixed_density(kpts=kpts_irr, nbands=40, txt="gpaw/nscf.txt")
calc_nscf.write("gpaw/nscf.gpw", mode="all")
