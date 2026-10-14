# -*- coding: utf-8 -*-
"""Consolidado horario julio-agosto 2026 para las rutas 60-CH y G-21.

Cruza:
  - ERA5-Land (GRIB, celda 0.1 deg mas cercana a la estacion de referencia)
  - Precipitacion horaria RRR1h de la estacion DMC del sector

Salidas: salidas/consolidado_horario.csv | .xlsx (horario + resumen diario)
"""
import os, sys, glob, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from leer_grib import preparar, abrir

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
GRIB = {"2026-07": BASE + "/datos/era5_temperatura_nieve/d14cd9f95b1e5020bbc086e33eafc011.grib",
        "2026-08": BASE + "/datos/era5_temperatura_nieve/data.grib"}

SITIOS = {
    "60-CH": dict(sitio="Los Libertadores", est_codigo=320051, lat=-32.84555, lon=-70.11917,
                  alt_est=2955, carpeta="los_libertadores_60CH"),
    "G-21":  dict(sitio="El Colorado", est_codigo=330077, lat=-33.35000, lon=-70.29361,
                  alt_est=2750, carpeta="el_colorado_G21"),
}
TZ = -4  # Chile continental, invierno (UTC-4)

preparar()


_CACHE = {}


def _datasets(path):
    if path not in _CACHE:
        _CACHE[path] = abrir(path)
    return _CACHE[path]


def _con(dss, var):
    """Primer dataset del GRIB que contiene la variable."""
    return [d for d in dss if var in d.data_vars][0]


def era5_sitio(path, lat, lon):
    """Serie horaria de una celda ERA5-Land. Devuelve DataFrame indexado en UTC."""
    dss = _datasets(path)

    # --- instantaneas horarias (time = 744 h) ---
    inst = _con(dss, "sd").sel(latitude=lat, longitude=lon, method="nearest")
    stl = {f"stl{i}_C": _con(dss, f"stl{i}").sel(latitude=lat, longitude=lon,
                                                 method="nearest")[f"stl{i}"].values - 273.15
           for i in (1, 2)}
    df_i = pd.DataFrame({
        "sd_mm_swe": inst.sd.values * 1000,
        "tsn_C": inst.tsn.values - 273.15,
        "skt_C": inst.skt.values - 273.15,
        "rsn_kgm3": inst.rsn.values,
        "asn": inst.asn.values,
        **stl,
    }, index=pd.DatetimeIndex(inst.time.values, name="fecha_hora_utc"))

    # --- bloque dia x step 1..24 h ---
    def aplanar(ds, campos, acumulados=()):
        d = ds.sel(latitude=lat, longitude=lon, method="nearest")
        out = {}
        for c in campos:
            v = d[c].values.copy()                       # (dia, step)
            if c in acumulados:                          # acumulado desde las 00 UTC
                v = np.diff(v, axis=1, prepend=0.0)
            out[c] = v.ravel()
        vt = (d.time.values[:, None] + d.step.values[None, :]).ravel()
        return pd.DataFrame(out, index=pd.DatetimeIndex(vt, name="fecha_hora_utc"))

    acc = _con(dss, "t2m")
    cob = _con(dss, "snowc")
    cob = cob.assign_coords(longitude=(((cob.longitude + 180) % 360) - 180))
    df_a = aplanar(acc, ["t2m", "d2m", "sf", "smlt"], acumulados=("sf", "smlt"))
    df_a = pd.DataFrame({"t2m_C": df_a.t2m - 273.15, "d2m_C": df_a.d2m - 273.15,
                         "sf_mm_swe": df_a.sf * 1000, "smlt_mm_swe": df_a.smlt * 1000})
    df_c = aplanar(cob, ["sde", "snowc"]).rename(columns={"sde": "sde_m", "snowc": "snowc_pct"})
    return df_i.join(df_a, how="outer").join(df_c, how="outer")


def precip_estacion(carpeta):
    """RRR1h horaria (mm) de los .xls de la DMC; son HTML, no xls binario."""
    frames = []
    for f in glob.glob(BASE + "/datos/estaciones_dmc/" + carpeta + "/*.xls"):
        d = pd.read_html(f)[0]
        col = [c for c in d.columns if c.startswith("RRR1h")]
        if not col:
            continue
        idx = pd.to_datetime(d["Fecha"] + " " + d["Hora (UTC)"], format="%d-%m-%Y %H:%M")
        frames.append(pd.Series(d[col[0]].values, index=idx, name="precip_estacion_mm"))
    s = pd.concat(frames).sort_index()
    s.index.name = "fecha_hora_utc"
    return s[~s.index.duplicated()]


filas = []
for ruta, cfg in SITIOS.items():
    # los dos GRIB se solapan el 31-jul y cada uno trae NaN en horas distintas de ese
    # dia frontera: se rellenan mutuamente en vez de quedarse con el primero
    partes = [era5_sitio(p, cfg["lat"], cfg["lon"]) for p in GRIB.values()]
    era = partes[0]
    for otra in partes[1:]:
        era = era.combine_first(otra)
    era = era.sort_index()
    era = era.loc["2026-07-01":"2026-08-31 23:00"]
    df = era.join(precip_estacion(cfg["carpeta"]), how="left")

    df.insert(0, "ruta", ruta)
    df.insert(1, "sitio", cfg["sitio"])
    df.insert(2, "estacion_codigo", cfg["est_codigo"])
    df["precip_estacion_falta"] = df["precip_estacion_mm"].isna()
    df["hora_local"] = df.index + pd.Timedelta(hours=TZ)
    df["mes"] = df.index.strftime("%Y-%m")
    # indicadores operacionales para el camino
    df["bajo_cero"] = df["t2m_C"] < 0
    df["nieve_cayendo"] = df["sf_mm_swe"] > 0.1
    df["nieve_intensa"] = df["sf_mm_swe"] > 1.0
    df["riesgo_hielo_calzada"] = (df["stl1_C"] < 0) & (df["t2m_C"] < 2)
    df["precip_solida"] = df["nieve_cayendo"] & (df["precip_estacion_mm"].fillna(0) > 0)
    filas.append(df.reset_index())

hor = pd.concat(filas, ignore_index=True)

cols = ["ruta", "sitio", "estacion_codigo", "fecha_hora_utc", "hora_local", "mes",
        "t2m_C", "d2m_C", "skt_C", "tsn_C", "stl1_C", "stl2_C",
        "sf_mm_swe", "smlt_mm_swe", "sd_mm_swe", "sde_m", "snowc_pct", "rsn_kgm3", "asn",
        "precip_estacion_mm", "precip_estacion_falta",
        "bajo_cero", "nieve_cayendo", "nieve_intensa", "riesgo_hielo_calzada", "precip_solida"]
hor = hor[cols].round(3)

# ---- resumen diario -----------------------------------------------------
hor["fecha"] = hor["fecha_hora_utc"].dt.date
dia = hor.groupby(["ruta", "sitio", "fecha"]).agg(
    t2m_media_C=("t2m_C", "mean"), t2m_min_C=("t2m_C", "min"), t2m_max_C=("t2m_C", "max"),
    horas_bajo_cero=("bajo_cero", "sum"),
    nieve_mm_swe=("sf_mm_swe", "sum"), horas_nevando=("nieve_cayendo", "sum"),
    derretimiento_mm=("smlt_mm_swe", "sum"),
    sd_mm_swe_fin=("sd_mm_swe", "last"), snowc_pct_media=("snowc_pct", "mean"),
    precip_estacion_mm=("precip_estacion_mm", "sum"),
    horas_sin_dato_estacion=("precip_estacion_falta", "sum"),
    horas_riesgo_hielo=("riesgo_hielo_calzada", "sum"),
).round(2).reset_index()

# ---- resumen mensual ----------------------------------------------------
mes = hor.groupby(["ruta", "sitio", "mes"]).agg(
    t2m_media_C=("t2m_C", "mean"), t2m_min_C=("t2m_C", "min"), t2m_max_C=("t2m_C", "max"),
    horas_bajo_cero=("bajo_cero", "sum"),
    nieve_total_mm_swe=("sf_mm_swe", "sum"), horas_nevando=("nieve_cayendo", "sum"),
    horas_nieve_intensa=("nieve_intensa", "sum"),
    derretimiento_total_mm=("smlt_mm_swe", "sum"),
    sd_mediana_mm_swe=("sd_mm_swe", "median"), sd_max_mm_swe=("sd_mm_swe", "max"),
    precip_estacion_total_mm=("precip_estacion_mm", "sum"),
    horas_sin_dato_estacion=("precip_estacion_falta", "sum"),
    horas_riesgo_hielo=("riesgo_hielo_calzada", "sum"),
).round(2).reset_index()

dic = pd.DataFrame([
    ("fecha_hora_utc", "Hora UTC. Las variables acumuladas (sf, smlt) corresponden a la hora que termina en ese instante."),
    ("hora_local", "UTC-4 (horario de invierno de Chile continental)."),
    ("t2m_C / d2m_C", "ERA5-Land: temperatura y punto de rocio a 2 m, en C."),
    ("skt_C / tsn_C / stl1_C", "Temperatura de piel, de la capa de nieve y del suelo 0-7 cm, en C."),
    ("sf_mm_swe", "Nieve caida en la hora, mm de equivalente en agua. Derivada del acumulado diario del GRIB (diferencia entre pasos)."),
    ("smlt_mm_swe", "Derretimiento en la hora, mm equivalente en agua. Idem tratamiento."),
    ("sd_mm_swe / sde_m", "Manto acumulado: equivalente en agua (mm) y espesor (m)."),
    ("snowc_pct", "Fraccion de la celda cubierta de nieve (%)."),
    ("rsn_kgm3 / asn", "Densidad del manto y albedo de la nieve."),
    ("precip_estacion_mm", "RRR1h de la estacion DMC del sector. NaN = hora sin dato (ver precip_estacion_falta)."),
    ("bajo_cero", "t2m < 0 C."),
    ("nieve_cayendo / nieve_intensa", "sf > 0,1 mm/h  /  sf > 1,0 mm/h."),
    ("riesgo_hielo_calzada", "stl1 < 0 C y t2m < 2 C: suelo congelado con aire frio."),
    ("precip_solida", "Hora con precipitacion medida en estacion y nevada en ERA5."),
    ("Celda ERA5", "0,1 deg (~9 km) mas cercana a la estacion; la orografia del modelo no coincide con la cota real del camino."),
    ("Cobertura espacial", "El dominio GRIB cubre 84% de la G-21 y solo 18,5% de la 60-CH (tramo andino)."),
], columns=["campo", "definicion"])

os.makedirs(BASE + "/salidas", exist_ok=True)
hor.drop(columns="fecha").to_csv(BASE + "/salidas/consolidado_horario.csv", index=False)
with pd.ExcelWriter(BASE + "/salidas/consolidado_horario.xlsx", engine="openpyxl") as w:
    for r in SITIOS:
        hor[hor.ruta == r].drop(columns="fecha").to_excel(w, sheet_name="Horario " + r, index=False)
    dia.to_excel(w, sheet_name="Resumen diario", index=False)
    mes.to_excel(w, sheet_name="Resumen mensual", index=False)
    dic.to_excel(w, sheet_name="Diccionario", index=False)

print(hor.shape, "filas horarias")
print(mes.to_string())
print("nulos por columna:")
print(hor.isna().sum()[lambda s: s > 0])
