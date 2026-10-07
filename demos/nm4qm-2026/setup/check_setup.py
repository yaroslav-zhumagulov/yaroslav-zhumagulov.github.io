"""Check that the environment is ready for the hands-on session (about 20 s).

    python setup/check_setup.py            # imports, versions, PAW datasets, Ray
    python setup/check_setup.py --dft      # also run the graphene DFT step (10 s)

Everything marked FAIL has to be fixed before the session; WARN means the notebooks run,
but some numbers may differ slightly from the checkpoints in the notebooks.
"""
import hashlib
import importlib
import inspect
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# the WannierBerri commit used for the checkpoint numbers, set in install_wannierberri.sh
WB_COMMIT = re.search(r"^COMMIT=(\w+)$", (ROOT / "setup/install_wannierberri.sh").read_text(), re.M)[1]
# ids (md5 of the dataset files) of the PAW datasets used for the checkpoint numbers: gpaw-setups-24.11.0
PAW_IDS = {"C": "4aa54d4b901d75f77cc0ea3eec22967b", "Mn": "00ec47dccfe5670b984398596635e8a7",
           "Te": "e44b9ef4772d7e5a1c6a47e6d6496588"}
problems, warnings = [], []


def report(ok, what, detail="", warn=False):
    tag = "ok  " if ok else ("WARN" if warn else "FAIL")
    print(f"  [{tag}] {what}" + (f": {detail}" if detail else ""))
    if not ok:
        (warnings if warn else problems).append(what)


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
    version = tuple(int(v) for v in gpaw.__version__.split(".")[:2])
    report(version >= (26, 7), "GPAW 26.7 or newer", gpaw.__version__)
    from gpaw.setup_data import search_for_file
    for element, expected in PAW_IDS.items():
        try:
            path, content = search_for_file(f"{element}.PBE")
            same = hashlib.md5(content).hexdigest() == expected
            report(same, f"PAW dataset {element}.PBE", path if same else f"{path} is a different version", warn=True)
        except Exception as err:
            report(False, f"PAW dataset {element}.PBE", f"not found ({err}); pip install gpaw-data")

print("\nirrep, WannierBerri, numba, Ray, Jupyter")
irrep = module("irrep")
if irrep:
    version = tuple(int(v) for v in irrep.__version__.split(".")[:2])
    report(version >= (3, 3), "irrep 3.3 or newer", irrep.__version__)
wb = module("wannierberri")
if wb:
    report(WB_COMMIT in wb.__version__, f"WannierBerri master at {WB_COMMIT}", wb.__version__, warn=True)
    report("altermagnetic" in inspect.signature(wb.WannierDataSOC.from_gpaw).parameters,
           "altermagnetic Wannierisation (WannierBerri master)")
numba = module("numba")   # the tetrahedron method of WannierBerri
if numba:
    report(True, "numba", numba.__version__)
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
    print("\nGraphene DFT step (python 1_dft.py):")
    t0 = time.time()
    run = subprocess.run([sys.executable, "1_dft.py"], cwd=ROOT / "01_graphene", capture_output=True, text=True)
    report(run.returncode == 0 and (ROOT / "01_graphene/gpaw/nscf.gpw").exists(),
           "graphene DFT", f"{time.time() - t0:.0f} s" if run.returncode == 0 else run.stderr.strip()[-300:])

print()
if problems:
    print("Not ready. Fix: " + "; ".join(problems))
    sys.exit(1)
print("Ready." + (f" Warnings: {'; '.join(warnings)}" if warnings else ""))
