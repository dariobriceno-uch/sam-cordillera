# -*- coding: utf-8 -*-
"""Serie horaria ERA5 por tramo (60-CH alto/medio, G-21 alto/medio), jul-ago 2026.

Solo reanálisis: ERA5-Land (0,1°) para superficie y nieve, ERA5 (0,25°) para la
isoterma 0 °C. No usa estaciones meteorológicas.

Entradas
  salidas/cache/era5land_celdas_horario.csv   (era5_extraer_celdas.py)
  salidas/cache/era5_isoterma_celdas.csv       (idem)
  salidas/geometria/pesos_celdas_era5land.csv  (geometria_tramos.R): celdas que
        atraviesa cada tramo y longitud de camino en cada una
  salidas/geometria/cotas_celdas.csv           (cotas_celdas.R): cota media DEM de
        cada celda ERA5 y ERA5-Land (Copernicus GLO-30)
  salidas/geometria/tramos_resumen.csv

Método
  * Cada variable ERA5-Land del tramo es el promedio de las celdas que el camino
    atraviesa, ponderado por la longitud de camino dentro de cada celda. Si una
    celda no tiene dato en una hora, se renormalizan los pesos de las demás.
  * Isoterma 0 °C: ERA5 entrega la altura del nivel de 0 °C SOBRE EL SUELO del
    modelo (deg0l) y la fija en 0 cuando toda la columna está bajo 0 °C. Para
    pasarla a m s.n.m. se suma la orografía de la celda (aproximada por la cota
    media DEM de la celda de 0,25°) y se usan las celdas de menor orografía de cada
    ruta, donde la censura es mínima. Si aun así deg0l = 0, la isoterma queda
    censurada por arriba (está bajo la cota de la celda) y se marca.
  * Ventanas de 12 h del protocolo: sumas causales sobre las 12 horas que terminan
    en cada hora. Nieve en cm = mm SWE × (100 / densidad de nieve fresca), con
    densidad 100 kg/m³ (razón 10:1) como parámetro.

Salida
  salidas/era5_tramos_horario.csv   una fila por (ruta, tramo, hora UTC)
  salidas/era5_tramos_meta.csv      descripción de cada tramo y de la isoterma
"""
import os
import numpy as np
import pandas as pd

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
SAL = BASE + "/salidas"
TZ = -4                     # Chile continental, invierno
RHO_NIEVE_FRESCA = 100.0    # kg/m3 -> 1 mm SWE = 1 cm de nieve
VENTANA_H = 12
PERIODO = ("2026-07-01 00:00", "2026-08-31 23:00")   # UTC

era = pd.read_csv(SAL + "/cache/era5land_celdas_horario.csv", parse_dates=["fecha_hora_utc"])
iso = pd.read_csv(SAL + "/cache/era5_isoterma_celdas.csv", parse_dates=["fecha_hora_utc"])
pesos = pd.read_csv(SAL + "/geometria/pesos_celdas_era5land.csv")
cotas = pd.read_csv(SAL + "/geometria/cotas_celdas.csv")
cotas.columns = ["ruta", "tramo", "producto", "lat", "lon", "z_media_m", "z_min_m", "z_max_m"]
resumen = pd.read_csv(SAL + "/geometria/tramos_resumen.csv")

VARS = ["t2m_C", "tsn_C", "u10_ms", "v10_ms", "tp_mm", "sf_mm", "smlt_mm", "es_mm", "sde_m", "snowc_pct", "rsn_kgm3"]


def promedio_ponderado(df, w):
    """df: (hora x celda) valores; w: pesos por celda. Renormaliza sobre celdas con dato."""
    v = df.values
    ww = np.where(np.isnan(v), 0.0, w[None, :])
    s = ww.sum(axis=1)
    out = np.where(s > 0, np.nansum(v * ww, axis=1) / np.where(s > 0, s, 1), np.nan)
    return pd.Series(out, index=df.index), pd.Series((~np.isnan(v)).sum(axis=1), index=df.index)


filas = []
meta = []
for (ruta, tramo), pw in pesos.groupby(["ruta", "tramo"], sort=False):
    sub = era[(era.ruta == ruta) & (era.recorte == tramo)]
    # celdas del tramo (si alguna no está en el recorte homónimo, se busca en el otro recorte de la ruta)
    partes = []
    for _, c in pw.iterrows():
        s = sub[(sub.lat.round(2) == round(c.lat, 2)) & (sub.lon.round(2) == round(c.lon, 2))]
        if s.empty:
            s = era[(era.ruta == ruta) & (era.lat.round(2) == round(c.lat, 2)) & (era.lon.round(2) == round(c.lon, 2))]
            s = s.drop_duplicates("fecha_hora_utc")
        s = s.set_index("fecha_hora_utc")[VARS].copy()
        s["viento_ms"] = np.hypot(s.u10_ms, s.v10_ms)
        s["lluvia_mm"] = (s.tp_mm - s.sf_mm).clip(lower=0)
        s.columns = pd.MultiIndex.from_product([s.columns, [f"{c.lat:.1f},{c.lon:.1f}"]])
        partes.append(s)
    wide = pd.concat(partes, axis=1).sort_index()
    wide = wide.loc[PERIODO[0]:PERIODO[1]]
    w = pw.peso.values
    out = pd.DataFrame(index=wide.index)
    for v in VARS + ["viento_ms", "lluvia_mm"]:
        out[v], n = promedio_ponderado(wide[v], w)
    out["n_celdas_validas"] = n
    out["viento_dir_deg"] = (270 - np.degrees(np.arctan2(out.v10_ms, out.u10_ms))) % 360
    out.insert(0, "tramo", tramo)
    out.insert(0, "ruta", ruta)
    filas.append(out.reset_index())

    r = resumen[(resumen.ruta == ruta) & (resumen.tramo == tramo)].iloc[0]
    zc = cotas[(cotas.producto == "ERA5-Land") & (cotas.ruta == ruta) & (cotas.tramo == tramo)]
    zc = pw.merge(zc[["lat", "lon", "z_media_m"]], on=["lat", "lon"], how="left")
    meta.append(dict(ruta=ruta, tramo=tramo, definicion=r.definicion, longitud_km=r.longitud_km,
                     n_celdas=len(pw), celdas=r.celdas,
                     cota_camino_min=r.cota_min, cota_camino_media=r.cota_media, cota_camino_max=r.cota_max,
                     cota_celdas_ponderada=round(float(np.average(zc.z_media_m, weights=zc.peso))),
                     pesos=" ".join(f"{p:.2f}" for p in pw.peso)))

hor = pd.concat(filas, ignore_index=True)

# ---- isoterma 0 °C por ruta ------------------------------------------------------
iso_ruta = {}
for ruta in hor.ruta.unique():
    zc = cotas[(cotas.producto == "ERA5") & (cotas.ruta == ruta)].drop_duplicates(["lat", "lon"])
    lon_min = zc.lon.min()                       # columna más occidental: menor orografía, menor censura
    zc = zc[zc.lon == lon_min]
    d = iso[iso.ruta == ruta].drop_duplicates(["fecha_hora_utc", "lat", "lon"])
    d = d.merge(zc[["lat", "lon", "z_media_m"]], on=["lat", "lon"])
    d["censurada"] = d.deg0l_m <= 0
    d["z0"] = np.where(d.censurada, np.nan, d.z_media_m + d.deg0l_m)
    g = d.groupby("fecha_hora_utc").agg(isoterma_msnm=("z0", "mean"), frac_censurada=("censurada", "mean"),
                                        z_sup=("z_media_m", "min"))
    g["isoterma_censurada"] = g.isoterma_msnm.isna() & (g.frac_censurada > 0)
    g["isoterma_msnm"] = g.isoterma_msnm.fillna(g.z_sup)   # cota superior cuando todas las celdas están censuradas
    g = g.drop(columns="z_sup")
    iso_ruta[ruta] = g.round({"isoterma_msnm": 0, "frac_censurada": 2})
    for m in meta:
        if m["ruta"] == ruta:
            m["isoterma_celdas_era5"] = " ".join(f"({la:.2f},{lo:.2f}) z={z:.0f} m" for la, lo, z in zip(zc.lat, zc.lon, zc.z_media_m))
            m["isoterma_horas_censuradas"] = int(g.isoterma_censurada.sum())

hor = hor.merge(pd.concat(iso_ruta, names=["ruta", "fecha_hora_utc"]).reset_index(), on=["ruta", "fecha_hora_utc"], how="left")

# ---- ventanas de 12 h ------------------------------------------------------------
hor = hor.sort_values(["ruta", "tramo", "fecha_hora_utc"]).reset_index(drop=True)
g = hor.groupby(["ruta", "tramo"], sort=False)
rol = lambda col, fn: g[col].transform(lambda s: getattr(s.rolling(VENTANA_H, min_periods=VENTANA_H // 2), fn)())
hor["sf_12h_mm"] = rol("sf_mm", "sum")
hor["nieve_12h_cm"] = hor.sf_12h_mm * (100.0 / RHO_NIEVE_FRESCA)
hor["lluvia_12h_mm"] = rol("lluvia_mm", "sum")
hor["tp_12h_mm"] = rol("tp_mm", "sum")
hor["dsde_12h_cm"] = (hor.sde_m - g.sde_m.shift(VENTANA_H)) * 100
hor["isoterma_12h_media"] = rol("isoterma_msnm", "mean")
hor["isoterma_12h_min"] = rol("isoterma_msnm", "min")
hor["nieve_24h_cm"] = g.sf_mm.transform(lambda s: s.rolling(24, min_periods=12).sum()) * (100.0 / RHO_NIEVE_FRESCA)

# ---- indicadores horarios (continuidad con la versión anterior) --------------------
hor["fecha_hora_local"] = hor.fecha_hora_utc + pd.Timedelta(hours=TZ)
hor["mes"] = hor.fecha_hora_utc.dt.strftime("%Y-%m")
hor["bajo_cero"] = hor.t2m_C < 0
hor["nieve_cayendo"] = hor.sf_mm > 0.1
hor["nieve_intensa"] = hor.sf_mm > 1.0
hor["lloviendo"] = hor.lluvia_mm > 0.1
hor["viento_fuerte"] = hor.viento_ms > 10.0   # ~36 km/h a 10 m: nieve en suspensión (viento blanco)

cols = ["ruta", "tramo", "fecha_hora_utc", "fecha_hora_local", "mes",
        "t2m_C", "tsn_C", "viento_ms", "viento_dir_deg", "tp_mm", "sf_mm", "lluvia_mm", "smlt_mm", "es_mm",
        "sde_m", "snowc_pct", "rsn_kgm3", "isoterma_msnm", "isoterma_censurada", "frac_censurada",
        "sf_12h_mm", "nieve_12h_cm", "nieve_24h_cm", "lluvia_12h_mm", "tp_12h_mm", "dsde_12h_cm",
        "isoterma_12h_media", "isoterma_12h_min", "n_celdas_validas",
        "bajo_cero", "nieve_cayendo", "nieve_intensa", "lloviendo", "viento_fuerte"]
hor = hor[cols].round(3)
os.makedirs(SAL, exist_ok=True)
hor.to_csv(SAL + "/era5_tramos_horario.csv", index=False)
pd.DataFrame(meta).to_csv(SAL + "/era5_tramos_meta.csv", index=False)

print(hor.shape, "filas;", hor.groupby(["ruta", "tramo"]).size().to_dict())
print("periodo:", hor.fecha_hora_utc.min(), "->", hor.fecha_hora_utc.max())
print("nulos:"); print(hor.isna().sum()[lambda s: s > 0])
print(hor.groupby(["ruta", "tramo"]).agg(t2m=("t2m_C", "mean"), sf_tot=("sf_mm", "sum"), lluvia_tot=("lluvia_mm", "sum"),
      sde_max=("sde_m", "max"), iso_med=("isoterma_msnm", "median"), iso_cens=("isoterma_censurada", "sum"),
      nieve12_max=("nieve_12h_cm", "max"), viento_max=("viento_ms", "max")).round(1).to_string())
print(pd.DataFrame(meta).to_string())
