# -*- coding: utf-8 -*-
"""Estaciones meteorologicas cercanas a las rutas 60-CH y G-21.

Fuentes:
  - data/processed/tramos.gpkg del catastro de caminos de montana (repositorio
    catastro-caminos-montana, clonado junto a este o en CATASTRO_CAMINOS)
  - modelo_sam/datos/estaciones_dmc/Catastro...SACLIM....xls (catastro nacional, HTML)
"""
import sqlite3, struct, math
import pandas as pd
from shapely import wkb
from shapely.geometry import Point
from shapely.ops import linemerge, unary_union, nearest_points, transform as sh_transform
from pyproj import Transformer

import os
from pathlib import Path
BASE = Path(__file__).resolve().parents[2].as_posix()   # raíz del repositorio
CAM  = os.environ.get("CATASTRO_CAMINOS", BASE + "/../catastro_caminos")
GPKG = CAM + "/data/processed/tramos.gpkg"
XLS  = BASE + "/modelo_sam/datos/estaciones_dmc/CatastrodeEstacionesdelSistemaSACLIM_2026-09-07_19_07.xls"
OUT  = BASE + "/modelo_sam/salidas/estaciones_cercanas_60CH_G21.xlsx"

UMBRAL_M = 30000.0  # radio maximo de busqueda (m)

def gpkg_wkb(blob):
    """Quita la cabecera GeoPackage y devuelve el WKB."""
    assert blob[:2] == b"GP"
    flags = blob[3]
    env = (flags >> 1) & 0x07
    ndim = {0: 0, 1: 4, 2: 6, 3: 6, 4: 8}[env]
    return blob[8 + 8 * (ndim // 2) * 0 + 8 + ndim * 8 - 8:] if False else blob[8 + ndim * 8:]

# --- 1. geometria de las rutas ------------------------------------------------
con = sqlite3.connect(GPKG)
cols = "id_tramo, rol, nombre_camino, km_inicio, km_fin, cota_min, cota_max, cota_media, comuna, region"
rows = con.execute(f"select {cols}, geom from tramos").fetchall()
con.close()

RUTAS = {"Ruta 60 CH": "60-CH", "G-21": "G-21"}
tramos = {v: [] for v in RUTAS.values()}
for r in rows:
    rol = (r[1] or "").strip()
    if rol in RUTAS:
        g = wkb.loads(gpkg_wkb(r[-1]))
        tramos[RUTAS[rol]].append(dict(zip(cols.split(", "), r[:-1])) | {"geom": g})

fwd = Transformer.from_crs(4326, 32719, always_xy=True).transform
inv = Transformer.from_crs(32719, 4326, always_xy=True).transform

rutas_m = {}
for k, lst in tramos.items():
    for t in lst:
        t["geom_m"] = sh_transform(fwd, t["geom"])
    rutas_m[k] = unary_union([t["geom_m"] for t in lst])
    print(k, len(lst), "tramos", round(rutas_m[k].length / 1000, 1), "km")

# --- 2. catastro de estaciones ------------------------------------------------
est = pd.read_html(XLS)[0]
est = est.dropna(subset=["Latitud", "Longitud"]).copy()
est["geom_m"] = [sh_transform(fwd, Point(lo, la)) for lo, la in zip(est["Longitud"], est["Latitud"])]

# --- 3. distancias ------------------------------------------------------------
def tabla(ruta_key):
    linea = rutas_m[ruta_key]
    lst = tramos[ruta_key]
    out = []
    for _, e in est.iterrows():
        p = e["geom_m"]
        d = p.distance(linea)
        if d > UMBRAL_M:
            continue
        # tramo mas cercano
        t = min(lst, key=lambda t: p.distance(t["geom_m"]))
        pr = nearest_points(t["geom_m"], p)[0]
        prg = sh_transform(inv, pr)
        cota = t["cota_media"]
        out.append({
            "ruta": ruta_key,
            "codigo_nacional": e["Codigo Nacional"],
            "codigo_oaci": e["Codigo OACI"],
            "nombre_estacion": e["Nombre"],
            "propietario": e["Propietario"],
            "tipo": e["Tipo"],
            "clasificacion": e["Clasificacion"],
            "zona_geografica": e["Zona Geografica"],
            "region_estacion": e["Region"],
            "latitud": e["Latitud"],
            "longitud": e["Longitud"],
            "altitud_estacion_m": e["Altitud (Mts)"],
            "fecha_creacion": e["Fecha Creacion"],
            "emite_metar": e["Emite METAR"],
            "emite_synop": e["Emite SYNOP"],
            "dist_ruta_m": round(d, 1),
            "dist_ruta_km": round(d / 1000, 2),
            "categoria_cercania": ("A. <=5 km" if d <= 5000 else
                                   "B. 5-15 km" if d <= 15000 else
                                   "C. 15-30 km"),
            "tramo_mas_cercano": t["id_tramo"],
            "comuna_tramo": t["comuna"],
            "cota_min_tramo_m": None if t["cota_min"] is None else round(t["cota_min"], 1),
            "cota_max_tramo_m": None if t["cota_max"] is None else round(t["cota_max"], 1),
            "cota_media_tramo_m": None if cota is None else round(cota, 1),
            "delta_vs_cota_media_m": None if cota is None else round(e["Altitud (Mts)"] - cota, 1),
            "lat_punto_ruta": round(prg.y, 6),
            "lon_punto_ruta": round(prg.x, 6),
        })
    return pd.DataFrame(out).sort_values("dist_ruta_m")

t60 = tabla("60-CH")
tg21 = tabla("G-21")
todo = pd.concat([t60, tg21], ignore_index=True)

crit = pd.DataFrame({
    "elemento": [
        "Unidad de medida",
        "Criterio de cercania",
        "Umbral maximo",
        "Categoria A", "Categoria B", "Categoria C",
        "Geometria de ruta 60-CH", "Geometria de ruta G-21",
        "Fuente geometria vial", "Fuente catastro estaciones",
        "CRS de calculo", "Estaciones evaluadas",
        "Estaciones dentro de 30 km (60-CH)", "Estaciones dentro de 30 km (G-21)",
    ],
    "valor": [
        "metros / kilometros",
        "Distancia euclidiana minima entre la estacion y la polilinea de la ruta (no distancia al punto medio ni a la comuna)",
        f"{UMBRAL_M/1000:.0f} km",
        "<= 5 km: representativa del camino",
        "5-15 km: uso con correccion (altitud/exposicion)",
        "15-30 km: solo referencia regional",
        f"{len(tramos['60-CH'])} tramos, {rutas_m['60-CH'].length/1000:.1f} km",
        f"{len(tramos['G-21'])} tramos, {rutas_m['G-21'].length/1000:.1f} km",
        "catastro_caminos/data/processed/tramos.gpkg (Red Vial MOP, EPSG:4326)",
        "Catastro Sistema SACLIM (DMC), descarga 2026-09-07",
        "EPSG:32719 (UTM 19S)",
        str(len(est)),
        str(len(t60)), str(len(tg21)),
    ],
})

with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    todo.to_excel(w, sheet_name="Todas", index=False)
    t60.to_excel(w, sheet_name="Ruta 60-CH", index=False)
    tg21.to_excel(w, sheet_name="Ruta G-21", index=False)
    crit.to_excel(w, sheet_name="Criterios", index=False)

print(OUT)
print(todo.groupby(["ruta", "categoria_cercania"]).size())
print(todo[["ruta","nombre_estacion","propietario","altitud_estacion_m","dist_ruta_km","delta_vs_cota_media_m"]].head(30).to_string())
