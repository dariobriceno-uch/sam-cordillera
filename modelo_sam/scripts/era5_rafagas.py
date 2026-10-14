# -*- coding: utf-8 -*-
"""Ráfagas y viento ERA5 (0,25°) por tramo, horario y en bloques de 6 h.

Entrada: datos/era5/VIento/*.grib  (ERA5: fg10, i10fg, u10, v10, u100, v100)
         salidas/geometria/pesos_celdas_era5land.csv               (pesos por largo de camino)
Salida : salidas/cache/era5_rafagas_tramos_horario.csv
         salidas/era5_rafagas_6h.csv   (ruta, tramo, bloque_inicio_local, rafaga_max_ms, rafaga_media_ms, viento100_ms)

Cada celda ERA5-Land del tramo toma el punto ERA5 de 0,25° más cercano; el tramo es el
promedio ponderado por longitud de camino (mismos pesos que el resto del pipeline).
fg10 en t es la ráfaga máxima de la hora (t-1, t]: se asigna al bloque que contiene t-1 h,
igual que las acumuladas en agregar_bloques_6h.py.
"""
import os, sys, glob, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from leer_grib import preparar

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
RAW = BASE + "/datos/era5/VIento"
SAL = BASE + "/salidas"
TZ = -4
ARCHIVOS = {("60-CH", "alto"): "60CH Viento Tramo Alto.grib", ("60-CH", "medio"): "60CH Viento Tramo Medio.grib",
            ("G-21", "alto"): "G-21_Tramo_alto.grib", ("G-21", "medio"): "G-21_Tramo_medio.grib"}

preparar()
import eccodes   # lectura mensaje a mensaje: evita la indexación lenta de cfgrib en OneDrive

pesos = pd.read_csv(SAL + "/geometria/pesos_celdas_era5land.csv")
filas = []
for (ruta, tramo), nombre in ARCHIVOS.items():
    print("leyendo", nombre, flush=True)
    p = pesos[(pesos.ruta == ruta) & (pesos.tramo == tramo)]
    reg = {}          # (variable, fecha valida) -> valor del tramo
    idx = None
    with open(os.path.join(RAW, nombre), "rb") as fh:
        while True:
            h = eccodes.codes_grib_new_from_file(fh)
            if h is None:
                break
            try:
                var = eccodes.codes_get(h, "shortName")
                if idx is None:
                    ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
                    lats = eccodes.codes_get_array(h, "distinctLatitudes")
                    lons = eccodes.codes_get_array(h, "distinctLongitudes")
                    lons = ((lons + 180) % 360) - 180
                    # orden del arreglo de valores: filas de latitud (norte->sur), columnas de longitud
                    lat_desc = eccodes.codes_get(h, "jScansPositively") == 0
                    lat_ord = np.sort(lats)[::-1] if lat_desc else np.sort(lats)
                    idx = [(int(np.abs(lat_ord - r.lat).argmin()), int(np.abs(lons - r.lon).argmin()), r.peso) for r in p.itertuples()]
                    wsum = sum(w for *_, w in idx)
                v = eccodes.codes_get_values(h).reshape(nj, ni)
                val = sum(v[i, j] * w for i, j, w in idx) / wsum
                vd, vt = eccodes.codes_get(h, "validityDate"), eccodes.codes_get(h, "validityTime")
                t = pd.Timestamp(f"{vd} {vt:04d}")
                reg[(var, t)] = val
            finally:
                eccodes.codes_release(h)
    s = pd.Series(reg)
    s.index = pd.MultiIndex.from_tuples(s.index, names=["var", "t"])
    w = s.unstack("var")
    df = pd.DataFrame(index=w.index)
    for c, nombre in (("10fg", "fg10"), ("fg10", "fg10"), ("i10fg", "i10fg")):
        if c in w:
            df[nombre] = w[c]
    if "10u" in w or "u10" in w:
        u, vv = w.get("10u", w.get("u10")), w.get("10v", w.get("v10"))
        df["viento10"] = np.hypot(u, vv)
    if "100u" in w or "u100" in w:
        u, vv = w.get("100u", w.get("u100")), w.get("100v", w.get("v100"))
        df["viento100"] = np.hypot(u, vv)
    df = df.sort_index()
    df.index.name = "fecha_hora_utc"
    df = df.reset_index()
    df.insert(0, "tramo", tramo); df.insert(0, "ruta", ruta)
    filas.append(df)
    print("  ", ruta, tramo, df.shape, df.fecha_hora_utc.min(), df.fecha_hora_utc.max(), flush=True)

h = pd.concat(filas, ignore_index=True)
os.makedirs(SAL + "/cache", exist_ok=True)
h.to_csv(SAL + "/cache/era5_rafagas_tramos_horario.csv", index=False)

# bloques de 6 h en hora local; la ráfaga de la hora (t-1, t] va al bloque que contiene t-1 h
loc = pd.to_datetime(h.fecha_hora_utc) + pd.Timedelta(hours=TZ) - pd.Timedelta(hours=1)
h["bloque_inicio_local"] = loc.dt.floor("6h")
b = h.groupby(["ruta", "tramo", "bloque_inicio_local"]).agg(
    rafaga_max_ms=("fg10", "max"), rafaga_media_ms=("fg10", "mean"),
    viento10_era5_ms=("viento10", "mean"), viento100_ms=("viento100", "mean")).reset_index()
b.to_csv(SAL + "/era5_rafagas_6h.csv", index=False)
print(b.groupby(["ruta", "tramo"])[["rafaga_max_ms", "rafaga_media_ms", "viento100_ms"]].describe(percentiles=[.5, .95]).round(1).T)
