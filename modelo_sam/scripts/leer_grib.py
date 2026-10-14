# -*- coding: utf-8 -*-
"""Abre los GRIB de ERA5-Land en Windows sin instalar ecCodes aparte.

Requisitos (ya instalados en este equipo):
    pip install cfgrib eccodes ecmwflibs xarray
Ademas: shim en %LOCALAPPDATA%/eccodes_shim/lib/libeccodes.dll (copia de
ecmwflibs/eccodes.dll). Lo crea la funcion preparar() si no existe.

Uso:
    from leer_grib import preparar, abrir
    preparar()
    dss = abrir(r"...\data.grib")   # lista de xr.Dataset (hipercubos separados)
"""
import os, shutil


def preparar():
    import ecmwflibs
    d = os.path.dirname(ecmwflibs.__file__)
    os.add_dll_directory(d)
    home = os.path.join(os.environ["LOCALAPPDATA"], "eccodes_shim")
    lib = os.path.join(home, "lib", "libeccodes.dll")
    if not os.path.exists(lib):
        os.makedirs(os.path.dirname(lib), exist_ok=True)
        shutil.copy(os.path.join(d, "eccodes.dll"), lib)
    os.environ["ECCODES_HOME"] = home


def abrir(path):
    import cfgrib
    return cfgrib.open_datasets(path)


def horario_desde_acumulado(da):
    """sf/smlt vienen acumulados dentro del dia (step 1..24 h desde las 00 UTC).
    Devuelve la tasa horaria (diferencia entre steps consecutivos)."""
    return da.diff("step", label="upper").combine_first(da.isel(step=0))


if __name__ == "__main__":
    import sys
    preparar()
    for ds in abrir(sys.argv[1]):
        print(dict(ds.sizes), list(ds.data_vars))
