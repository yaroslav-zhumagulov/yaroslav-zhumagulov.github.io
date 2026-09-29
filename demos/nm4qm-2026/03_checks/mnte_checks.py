"""MnTe checks (optional, not needed for the talk): how far can the anomalous Hall numbers of the demo be trusted?

All on the Wannier model of the demo (6x6x4 NSCF grid) unless stated:
1. k-grid convergence of sigma_xy(E_F) for the Neel vector along y (perpendicular to a), 48^2 to 256^2 in plane.
2. Hubbard U = 3, 4, 5 eV, each relative to its own valence band top.
3. External (position-operator) terms on and off.
4. The in-plane Neel-angle scan on two grids, and the exact symmetry relations
   sigma(-phi) = -sigma(phi), sigma(phi + 60) = -sigma(phi).
5. The degeneracy threshold.
6. The Wannier (NSCF) grid: models built on 6x6x4, 9x9x6 and 12x12x8.

sigma_xy(E) and the number of states N(E) are stored without smoothing (T = 0); the Fermi-Dirac
occupation at any temperature is applied afterwards (smooth()).

Needs ../02_mnte/gpaw/nscf.gpw and the MnTe runs of dft_scan.py. Heavy: about 5 h on 8 cores in total;
each part is cached in results/. Run with fewer Ray workers to keep the machine usable, e.g. RAY_CPUS=4.
"""
import io
import os
import time
import warnings
from contextlib import redirect_stdout

import numpy as np
from gpaw import GPAW
from irrep.spacegroup import SpaceGroup

import wannierberri as wb
from wannierberri.parallel import ray_init
from wannierberri.smoother import FermiDiracSmoother
from wannierberri.symmetry.projections import Projection, ProjectionsSet

warnings.simplefilter("ignore")
np.random.seed(0)  # the Wannierisation draws random numbers: fix them for reproducible output
os.makedirs("results", exist_ok=True)
DEGEN = 1e-4     # eV; 1e-5 gives identical results, 1e-3 does not
T_PHYS = 150     # K, temperature of the Hall measurement of Gonzalez Betancourt et al. (2023)
P_EXP = 4.9e18   # cm^-3, their hole density
N_W = 26         # spin orbitals per cell, all filled in the undoped crystal
PHI_Y = 90       # Neel vector along y = [01-10], perpendicular to a
DEMO = ("../02_mnte/gpaw/nscf.gpw", "mnte-nscf6")         # the model of the demo: 6x6x4 Wannier grid


def model(nscf, tag):
    """The Wannier model of the demo (mnte.ipynb, section 2) for a given NSCF run, cached in work/."""
    calc = GPAW(nscf, txt=None)
    EF = calc.get_fermi_level()
    # irrep matches the moments with an absolute tolerance of 1e-8 muB; drop the numerical noise on Te
    moments = np.round(calc.get_magnetic_moments(), 6)
    calc.get_magnetic_moments = lambda *args, **kwargs: moments
    if not os.path.exists(f"work/{tag}"):
        sg = SpaceGroup.from_gpaw(calc)
        Te = [[1 / 3, 2 / 3, 1 / 4], [2 / 3, 1 / 3, 3 / 4]]
        projections = ProjectionsSet([
            Projection(position_num=[0, 0, 0], orbital="d", spacegroup=sg),
            Projection(position_num=Te, orbital="sp2", spacegroup=sg, xaxis=[0, -1, 0], rotate_basis=True),
            Projection(position_num=Te, orbital="pz", spacegroup=sg)])
        with redirect_stdout(io.StringIO()):
            wandata = wb.WannierDataSOC.from_gpaw(calc, projections=projections, altermagnetic=True,
                                                  IBstart=8, seedname=f"work/{tag}")
            wandata.wannierise(froz_min=-np.inf, froz_max=EF + 0.1, num_iter=200, sitesym=True)
            wb.SystemSOC.from_wannierdata(wandata, berry=True).save_npz(f"work/{tag}")
    with redirect_stdout(io.StringIO()):
        return wb.SystemSOC.from_npz(f"work/{tag}"), EF


def top_band(system, k_red, batch=500):
    """Energy of the highest valence band at the reduced k-points."""
    energy = {"Energy": wb.calculators.tabulate.Energy(degen_thresh=1e-6)}
    out = []
    for i in range(0, len(k_red), batch):
        with redirect_stdout(io.StringIO()):
            tab = wb.evaluate_k_path(system, path=wb.Path(system, k_list=k_red[i:i + batch]),
                                     tabulators=energy, parallel=False)
        out.append(tab.get_eigenvalues()[:, N_W - 1])
    return np.concatenate(out)


def band_top(system, EF, phi):
    """Valence band maximum (eV, relative to E_F0) with SOC for an in-plane Neel vector at phi (deg)."""
    with redirect_stdout(io.StringIO()):
        system.set_soc_axis(theta=90, phi=phi, units="degrees")
    grid = np.meshgrid(np.arange(24) / 24, np.arange(24) / 24, np.linspace(0, 0.5, 13), indexing="ij")
    k = np.stack(grid, -1).reshape(-1, 3)
    E = top_band(system, k)
    best_E, best_k = -np.inf, None
    for k0 in k[np.argsort(E)[::-1][:6]]:  # the valence band has several close maxima: zoom into each
        step = 1 / 24
        for _ in range(4):
            d = np.stack(np.meshgrid(*[np.linspace(-step, step, 7)] * 3, indexing="ij"), -1).reshape(-1, 3)
            E0 = top_band(system, k0 + d)
            k0, step = k0 + d[E0.argmax()], step / 3
        if E0.max() > best_E:
            best_E, best_k = E0.max(), k0
    return best_E - EF, best_k


def run(system, EF, phi, nk, external_terms=True, degen_thresh=DEGEN, nkz=None):
    """Unsmoothed sigma_xy(E) (S/cm) and N(E) (states per cell) for an in-plane Neel vector at phi (deg)."""
    Efermi = np.linspace(EF - 1.2, EF + 0.2, 1401)
    calculators = {"ahc": wb.calculators.static.AHC(Efermi=Efermi, degen_thresh=degen_thresh,
                                                    kwargs_formula={"external_terms": external_terms}),
                   "cumdos": wb.calculators.static.CumDOS(Efermi=Efermi)}
    t0 = time.time()
    with redirect_stdout(io.StringIO()):
        system.set_soc_axis(theta=90, phi=phi, units="degrees")
        r = wb.run(system, grid=wb.Grid(system, NK=(nk, nk, nkz or 2 * nk // 3)), calculators=calculators,
                   fout_name="work/mnte")
    return Efermi - EF, r.results["ahc"].data[:, 2] / 100, r.results["cumdos"].data, time.time() - t0


def smooth(E, y, T):
    """Fermi-Dirac occupation at T (K) applied to T = 0 data on the uniform energy grid E (last axis)."""
    y = np.asarray(y)
    return y if T == 0 else FermiDiracSmoother(E, T_Kelvin=T)(y, axis=y.ndim - 1)


def holes(N, volume_cm3):
    """Hole density (cm^-3) from the number of states per cell below E_F."""
    return (N_W - np.asarray(N)) / volume_cm3


def e_at_p(E, p, target):
    """E_F at which the hole density equals target (log interpolation where p > 0)."""
    ok = p > 1e15
    return np.interp(np.log(target), np.log(p[ok][::-1]), E[ok][::-1])


def log(line):
    print(line, flush=True)
    with open("results/mnte_checks.log", "a") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    ray_init(num_cpus=int(os.environ.get("RAY_CPUS", os.cpu_count())), logging_level="error", log_to_driver=False)
    system, EF = model(*DEMO)
    volume = abs(np.linalg.det(system.real_lattice)) * 1e-24

    # 1. k-grid convergence
    conv = "results/mnte_ahc_convergence.npz"
    if not os.path.exists(conv):
        Ev = {phi: band_top(system, EF, phi) for phi in (0, 15, 30, 90)}
        for phi, (e, k) in Ev.items():
            log(f"band top, phi = {phi:2d}: E_v - E_F0 = {e:+.4f} eV at k = {np.round(k, 3)}")
        data = dict(nk=[], sigma=[], N=[], seconds=[], Ev=Ev[PHI_Y][0], volume_cm3=volume,
                    Ev_phi=[Ev[p][0] for p in (0, 15, 30, 90)])
        for nk in (48, 96, 144, 192, 256):
            E, s, n, t = run(system, EF, PHI_Y, nk)
            for key, value in zip(("nk", "sigma", "N", "seconds"), (nk, s, n, t)):
                data[key].append(value)
            log(f"n || y, NK = {nk}: {t:.0f} s")
        np.savez(conv, E=E, **data)

    # 2. Hubbard U on the 144 x 144 x 96 grid
    if not os.path.exists("results/mnte_U.npz"):
        c = np.load(conv)
        i144 = list(c["nk"]).index(144)
        out = {"E_U4": c["E"], "sigma_U4": c["sigma"][i144], "N_U4": c["N"][i144], "Ev_U4": c["Ev"]}
        for U in (3, 5):
            sys_U, EF_U = model(f"work/mnte-U{U}-nscf.gpw", f"mnte-U{U}")
            Ev_U, k_U = band_top(sys_U, EF_U, PHI_Y)
            log(f"band top, U = {U} eV: E_v - E_F0 = {Ev_U:+.4f} eV at k = {np.round(k_U, 3)}")
            E, s, n, t = run(sys_U, EF_U, PHI_Y, 144)
            log(f"U = {U} eV, NK = 144: {t:.0f} s")
            out.update({f"E_U{U}": E, f"sigma_U{U}": s, f"N_U{U}": n, f"Ev_U{U}": Ev_U})
        np.savez("results/mnte_U.npz", volume_cm3=volume, **out)

    # 3. external terms
    if not os.path.exists("results/mnte_external_terms.npz"):
        c = np.load(conv)
        E, s, _, t = run(system, EF, PHI_Y, 144, external_terms=False)
        log(f"external terms off, NK = 144: {t:.0f} s")
        np.savez("results/mnte_external_terms.npz", E=E, sigma_true=c["sigma"][list(c["nk"]).index(144)],
                 sigma_false=s)

    # 4. Neel-angle scan on two grids, plus the symmetry relations on the coarse one
    if not os.path.exists("results/mnte_neel_convergence.npz"):
        phis = np.arange(0, 30.1, 2.5)
        scan = {}
        for nk in (96, 144):
            scan[nk] = []
            for phi in phis:
                E, s, _, t = run(system, EF, phi, nk)
                scan[nk].append(s)
                log(f"scan NK = {nk}, phi = {phi:4.1f}: {t:.0f} s")
        sym = {name: run(system, EF, phi, 48)[1]
               for name, phi in [("phi", 10), ("minus_phi", -10), ("phi_plus_60", 70)]}
        np.savez("results/mnte_neel_convergence.npz", phi=phis, E=E, sigma96=scan[96], sigma144=scan[144],
                 **{f"sym_{k}": v for k, v in sym.items()})

    # 5. degeneracy threshold on the 96 x 96 x 64 grid
    if not os.path.exists("results/mnte_degen_thresh.npz"):
        c = np.load(conv)
        out = {"1e-04": c["sigma"][list(c["nk"]).index(96)]}
        for dg in (1e-2, 1e-3, 1e-5):
            E, s, _, t = run(system, EF, PHI_Y, 96, degen_thresh=dg)
            out[f"{dg:.0e}"] = s
            log(f"degen_thresh = {dg:.0e}, NK = 96: {t:.0f} s")
        np.savez("results/mnte_degen_thresh.npz", E=E, **out)

    # 6. Wannier grid: the same density, NSCF on 6x6x4, 9x9x6 (the demo) and 12x12x8
    if not os.path.exists("results/mnte_nscf_grid.npz"):
        out = {}
        for n in (6, 9, 12):
            sys_n, EF_n = model(f"work/mnte-nscf{n}-nscf.gpw", f"mnte-nscf{n}")
            Ev_n, k_n = band_top(sys_n, EF_n, PHI_Y)
            log(f"band top, NSCF {n}: E_v - E_F0 = {Ev_n:+.4f} eV at k = {np.round(k_n, 3)}")
            E, s, N, t = run(sys_n, EF_n, PHI_Y, 144)
            log(f"NSCF {n}, NK = 144: {t:.0f} s")
            out.update({f"E_{n}": E, f"sigma_{n}": s, f"N_{n}": N, f"Ev_{n}": Ev_n})
        np.savez("results/mnte_nscf_grid.npz", volume_cm3=volume, **out)
