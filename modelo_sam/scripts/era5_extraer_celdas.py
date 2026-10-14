# -*- coding: utf-8 -*-
"""Extrae a tablas horarias todas las celdas de los GRIB nuevos (ERA5-Land + ERA5).

Entrada: datos/era5/  (8 GRIB ERA5-Land, 4 GRIB ERA5 isoterma)
Salida : salidas/cache/era5land_celdas_horario.csv   una fila por (ruta, recorte, celda, hora UTC)
         salidas/cache/era5_isoterma_celdas.csv       idem para deg0l (ERA5, 0,25 grados)

No agrega ni pondera: eso lo hace consolidar_horario_era5.py con los pesos de
salidas/geometria/pesos_celdas_era5land.csv.
"""
import os, sys, glob, warnings, time
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from leer_grib import preparar

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
RAW = BASE + "/datos/era5"
CACHE = BASE + "/salidas/cache"
os.makedirs(CACHE, exist_ok=True)

ARCHIVOS = {  # (ruta, recorte) -> lista de GRIB ERA5-Land
    ("60-CH", "alto"):  [RAW + "/Tramos Altos/CH60 Tramo Alto Julio.grib", RAW + "/Tramos Altos/CH60 Tramo Alto Agosto.grib"],
    ("60-CH", "medio"): [RAW + "/Tramos medios/CH-60.Tramo_medio_JULIO/data.grib", RAW + "/Tramos medios/CH-60.Tramo_Medio.AGOSTO.grib"],
    ("G-21", "alto"):   [RAW + "/Tramos Altos/G21 Tramo Alto Julio.grib", RAW + "/Tramos Altos/G21 Tramo Alto Agosto.grib"],
    ("G-21", "medio"):  [RAW + "/Tramos medios/G-21.Tramo_Medio_JULIO/data.grib", RAW + "/Tramos medios/G-21.Tramo_medio_AGOSTO/data.grib"],
}
ISOTERMA = {
    ("60-CH", "alto"):  RAW + "/Tramos Altos/CH60 Isoterma Tramo Alto.grib",
    ("60-CH", "medio"): RAW + "/Tramos medios/CH-60.Isotermo_Tramo_Medio/data.grib",
    ("G-21", "alto"):   RAW + "/Tramos Altos/G21 Isoterma Tramo Alto.grib",
    ("G-21", "medio"):  RAW + "/Tramos medios/G-21.Isotermo_Tramo_Medio/data.grib",
}
ACUMULADAS = ("sf", "smlt", "es", "tp")       # acumuladas desde las 00 UTC del dia (step 1..24)
K = 273.15

preparar()
import cfgrib


def abrir(path):
    # sin archivo .idx: en OneDrive el indice queda "incompatible" y cfgrib lo reconstruye igual
    return cfgrib.open_datasets(path, indexpath="")


def largo(ds, campos):
    """Dataset (time[,step],lat,lon) -> DataFrame largo con columna fecha_hora_utc."""
    ds = ds.assign_coords(longitude=(((ds.longitude + 180) % 360) - 180))
    if "step" in ds.dims:
        vt = (ds.time.values[:, None] + ds.step.values[None, :])
        out = {}
        for c in campos:
            if c not in ds:
                continue
            v = ds[c].values                       # (time, step, lat, lon)
            if c in ACUMULADAS:
                v = np.diff(v, axis=1, prepend=0.0)
            out[c] = v
        vt_flat = np.repeat(vt.ravel(), ds.sizes["latitude"] * ds.sizes["longitude"])
    else:
        out = {c: ds[c].values[:, None, :, :] for c in campos if c in ds}
        vt_flat = np.repeat(ds.time.values, ds.sizes["latitude"] * ds.sizes["longitude"])
    lat = np.tile(np.repeat(ds.latitude.values, ds.sizes["longitude"]), int(vt_flat.size / (ds.sizes["latitude"] * ds.sizes["longitude"])))
    lon = np.tile(ds.longitude.values, int(vt_flat.size / ds.sizes["longitude"]))
    df = pd.DataFrame({"fecha_hora_utc": vt_flat, "lat": np.round(lat, 2), "lon": np.round(lon, 2)})
    for c, v in out.items():
        df[c] = v.ravel()
    return df


t0 = time.time()
partes = []
for (ruta, rec), paths in ARCHIVOS.items():
    mensual = []
    for p in paths:
        dss = abrir(p)
        d_inst = [d for d in dss if "rsn" in d][0]
        d_acc = [d for d in dss if "t2m" in d][0]
        d_cob = [d for d in dss if "sde" in d][0]
        a = largo(d_inst, ["rsn", "tsn"])
        b = largo(d_acc, ["t2m", "u10", "v10", "tp", "sf", "smlt", "es"])
        c = largo(d_cob, ["sde", "snowc"])
        m = a.merge(b, on=["fecha_hora_utc", "lat", "lon"], how="outer").merge(c, on=["fecha_hora_utc", "lat", "lon"], how="outer")
        mensual.append(m.set_index(["fecha_hora_utc", "lat", "lon"]))
        print(f"  {ruta} {rec} {os.path.basename(os.path.dirname(p)) if p.endswith('data.grib') else os.path.basename(p)}: {len(m)} filas  [{time.time()-t0:.0f} s]", flush=True)
    # los dos meses se solapan en el dia frontera y cada uno trae NaN en horas distintas: se rellenan mutuamente
    df = mensual[0].combine_first(mensual[1]).reset_index()
    df.insert(0, "recorte", rec)
    df.insert(0, "ruta", ruta)
    partes.append(df)

era = pd.concat(partes, ignore_index=True)
era = era.sort_values(["ruta", "recorte", "lat", "lon", "fecha_hora_utc"])
# unidades
for c in ("t2m", "tsn"):
    era[c] = era[c] - K
for c in ("tp", "sf", "smlt", "es"):
    era[c] = era[c] * 1000            # m -> mm equivalente en agua
era = era.rename(columns={"t2m": "t2m_C", "tsn": "tsn_C", "tp": "tp_mm", "sf": "sf_mm", "smlt": "smlt_mm", "es": "es_mm",
                          "sde": "sde_m", "snowc": "snowc_pct", "rsn": "rsn_kgm3", "u10": "u10_ms", "v10": "v10_ms"})
era = era.round(4)
era.to_csv(CACHE + "/era5land_celdas_horario.csv", index=False)
print("ERA5-Land celdas:", era.shape, "periodo", era.fecha_hora_utc.min(), "->", era.fecha_hora_utc.max(), f"[{time.time()-t0:.0f} s]", flush=True)

partes = []
for (ruta, rec), p in ISOTERMA.items():
    ds = abrir(p)[0]
    df = largo(ds, ["deg0l"])
    df.insert(0, "recorte", rec)
    df.insert(0, "ruta", ruta)
    partes.append(df)
    print(f"  isoterma {ruta} {rec}: {len(df)} filas", flush=True)
iso = pd.concat(partes, ignore_index=True).rename(columns={"deg0l": "deg0l_m"})
iso = iso.sort_values(["ruta", "recorte", "lat", "lon", "fecha_hora_utc"]).round(2)
iso.to_csv(CACHE + "/era5_isoterma_celdas.csv", index=False)
print("ERA5 isoterma celdas:", iso.shape, f"[{time.time()-t0:.0f} s]")
print("nulos ERA5-Land por columna:"); print(era.isna().sum()[lambda s: s > 0])
