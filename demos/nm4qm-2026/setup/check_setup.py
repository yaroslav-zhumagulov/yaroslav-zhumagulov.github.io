"""Check that the environment is ready for the hands-on session (about 20 s).

    python setup/check_setup.py            # imports, versions, PAW datasets, patches, Ray
    python setup/check_setup.py --dft      # also run the graphene DFT step (10 s on 4 cores)
    MPIRUN=/path/to/mpirun python setup/check_setup.py   # if several MPI libraries are installed

Everything marked FAIL has to be fixed before the session; WARN means the notebooks run,
but some numbers may differ slightly from the checkpoints on the slides.
"""
import hashlib
import importlib
import inspect
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# ids (md5 of the dataset files) of the PAW datasets used for the checkpoint numbers: gpaw-setups-24.11.0
PAW_IDS = {"C": "4aa54d4b901d75f77cc0ea3eec22967b", "Mn": "00ec47dccfe5670b984398596635e8a7",
           "Te": "e44b9ef4772d7e5a1c6a47e6d6496588"}
problems, warnings = [], []


def report(ok, what, detail="", warn=False):
    tag = "ok  " if ok else ("WARN" if warn else "FAIL")
    print(f"  [{tag}] {what}" + (f": {detail}" if detail else ""))
    if not ok:
        (warnings if warn else problems).append(what)


def clean_env():
    """Environment for a child mpirun: importing GPAW here may have started MPI in this process."""
    return {k: v for k, v in os.environ.items() if not k.startswith(("OMPI_", "PMIX_", "PRTE_", "OPAL_", "PMI_"))}


def module(name):
    try:
        return importlib.import_module(name)
    except Exception as err:          # ImportError, or a broken binary module
        report(False, f"import {name}", str(err).splitlines()[0])
        return None


print(f"Python {sys.version.split()[0]} at {sys.executable}")
report(sys.version_info >= (3, 10), "Python 3.10 or newer")

print("\nGPAW")
gpaw = module("gpaw")
if gpaw:
    report(True, "gpaw", gpaw.__version__)
    import gpaw.mpi
    report(bool(gpaw.mpi.have_mpi), "GPAW compiled with MPI")
    mpirun = os.environ.get("MPIRUN", "mpirun")
    report(shutil.which(mpirun) is not None, "mpirun on the PATH", shutil.which(mpirun) or "not found")
    if shutil.which(mpirun):
        # a launcher from another MPI library starts independent serial copies instead of one parallel run
        try:
            out = subprocess.run([mpirun, "-np", "2", sys.executable, "-c",
                                  "from gpaw.mpi import world; print('SIZE', world.size)"],
                                 capture_output=True, text=True, timeout=120, env=clean_env()).stdout
            sizes = [line.split()[1] for line in out.splitlines() if line.startswith("SIZE")]
            report(sizes == ["2", "2"], "mpirun starts one GPAW run on 2 ranks",
                   "ok" if sizes == ["2", "2"] else f"got ranks of size {sizes}: this mpirun belongs to another "
                   "MPI library; use the one GPAW was built with (set MPIRUN=/path/to/mpirun)")
        except subprocess.TimeoutExpired:
            report(False, "mpirun starts one GPAW run on 2 ranks", "timed out after 120 s")
    from gpaw.setup_data import search_for_file
    for element, expected in PAW_IDS.items():
        try:
            path, content = search_for_file(f"{element}.PBE")
            same = hashlib.md5(content).hexdigest() == expected
            report(same, f"PAW dataset {element}.PBE", path if same else f"{path} is a different version", warn=True)
        except Exception as err:
            report(False, f"PAW dataset {element}.PBE", f"not found ({err}); pip install gpaw-data")

print("\nirrep, WannierBerri, Ray, Jupyter")
irrep = module("irrep")
if irrep:
    version = tuple(int(v) for v in irrep.__version__.split(".")[:2])
    report(version >= (3, 2), "irrep 3.2 or newer", irrep.__version__)
wb = module("wannierberri")
if wb:
    report("0033c84" in wb.__version__, "WannierBerri master at 0033c84", wb.__version__, warn=True)
    report("altermagnetic" in inspect.signature(wb.WannierDataSOC.from_gpaw).parameters,
           "altermagnetic Wannierisation (WannierBerri master)")
    src = Path(wb.__file__).parent
    report("self.system_up.has_R_mat('dV_soc')" in (src / "system/system_soc.py").read_text(),
           "patch 0001 (SOC for non-magnetic systems)")
    report("remotes_collected" in (src / "run_grid.py").read_text(),
           "patch 0002 (Ray collects every k-point once)")
ray = module("ray")
if ray:
    t0 = time.time()
    try:
        ray.init(num_cpus=2, include_dashboard=False, logging_level="error", log_to_driver=False)
        square = ray.remote(lambda x: x * x)
        report(ray.get(square.remote(7)) == 49, "Ray runs a task", f"{ray.__version__}, {time.time() - t0:.0f} s to start")
        ray.shutdown()
    except Exception as err:
        report(False, "Ray runs a task", str(err).splitlines()[0])
report(shutil.which("jupyter") is not None, "jupyter on the PATH")

ncpu = os.cpu_count() or 1
print(f"\n{ncpu} CPU cores. Expected compute on this machine: graphene about {max(1, round(10 / ncpu))} min, "
      f"MnTe about {max(4, round(34 / ncpu))} min (Apple M2, 8 cores: 1.1 and 4.2 min).")

if "--dft" in sys.argv and not problems:
    print("\nGraphene DFT step (mpirun -np 4 python 1_dft.py):")
    t0 = time.time()
    run = subprocess.run([os.environ.get("MPIRUN", "mpirun"), "-np", str(min(4, ncpu)), sys.executable, "1_dft.py"],
                         cwd=ROOT / "01_graphene", capture_output=True, text=True, env=clean_env())
    report(run.returncode == 0 and (ROOT / "01_graphene/gpaw/nscf.gpw").exists(),
           "graphene DFT", f"{time.time() - t0:.0f} s" if run.returncode == 0 else run.stderr.strip()[-300:])

print()
if problems:
    print("Not ready. Fix: " + "; ".join(problems))
    sys.exit(1)
print("Ready." + (f" Warnings: {'; '.join(warnings)}" if warnings else ""))
