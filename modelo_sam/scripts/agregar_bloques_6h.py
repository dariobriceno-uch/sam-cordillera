# -*- coding: utf-8 -*-
"""Agrega la serie horaria ERA5 por tramo y el estado observado de las rutas a bloques de 6 h.

Bloques en hora local (UTC-4): 00-06, 06-12, 12-18 y 18-24. El bloque se identifica por su
hora de inicio local (bloque_inicio_local) y se numera 0..3 dentro del día (bloque_dia).

Asignación de cada hora a un bloque
  * Variables acumuladas (tp, sf, lluvia, smlt, es): el valor de ERA5 rotulado t es lo que
    cayó en la hora (t-1, t]; entra al bloque que contiene t-1 h. Así el bloque 00-06 suma
    exactamente la nieve caída entre las 00:00 y las 06:00.
  * Variables instantáneas (t2m, tsn, viento, manto, isoterma) y estado observado: la hora t
    entra al bloque que contiene t (00:00..05:00 para el bloque 00-06).

Agregación por bloque
  * acumuladas: suma de las horas con dato (sf_6h_mm, ...), con n_horas_flujo de respaldo.
  * temperatura, viento, isoterma: media, mínimo y máximo; dirección del viento = media
    vectorial ponderada por la rapidez; manto (sde) = último valor del bloque.
  * Ventanas del protocolo, alineadas a los bloques: S = nieve de este bloque + el anterior
    (12 h exactas), nieve_24h = 4 bloques; R y tp igual que S; isoterma 12 h = media y mínimo
    de las horas de los 2 bloques. Se exige al menos 6 horas con dato en la ventana de 12 h
    (12 en la de 24 h), como en la versión horaria.
  * Estado observado: horas de cada estado en el bloque. estado_observado = cerrado_meteo si
    hubo al menos una hora cerrada por meteorología (coherente con el criterio diario
    "cerrado al menos una hora"); si no, el estado con más horas (empate -> el más restrictivo).

Entradas: salidas/era5_tramos_horario.csv, salidas/estado_caminos_horario.csv
Salidas : salidas/era5_tramos_6h.csv (una fila por ruta, tramo y bloque)
          salidas/estado_caminos_6h.csv (una fila por ruta y bloque)
"""
import numpy as np
import pandas as pd

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
SAL = BASE + "/salidas"
TZ = -4
BLOQUE_H = 6
RHO_NIEVE_FRESCA = 100.0
A_CM_MM = 100.0 / RHO_NIEVE_FRESCA
PERIODO_LOCAL = ("2026-07-01 00:00", "2026-08-31 18:00")    # inicio del primer y último bloque
ESTADOS = ["abierto", "restringido", "cierre_tecnico", "cerrado_meteo", "cerrado_horario"]
SEVERIDAD = {"cerrado_meteo": 4, "cierre_tecnico": 3, "restringido": 2, "cerrado_horario": 1, "abierto": 0}

FLUJOS = ["tp_mm", "sf_mm", "lluvia_mm", "smlt_mm", "es_mm"]

era = pd.read_csv(SAL + "/era5_tramos_horario.csv", parse_dates=["fecha_hora_utc", "fecha_hora_local"])
est = pd.read_csv(SAL + "/estado_caminos_horario.csv", parse_dates=["fecha_hora_utc", "fecha_hora_local"])

bloque = lambda t: t.dt.floor(f"{BLOQUE_H}h")
todos = pd.date_range(pd.Timestamp(PERIODO_LOCAL[0]) - pd.Timedelta(hours=24), PERIODO_LOCAL[1], freq=f"{BLOQUE_H}h")


# ------------------------------------------------------------------------------------
# 1. ERA5 por tramo
# ------------------------------------------------------------------------------------
def agregar_tramo(h):
    h = h.copy()
    h["b_inst"] = bloque(h.fecha_hora_local)
    h["b_flujo"] = bloque(h.fecha_hora_local - pd.Timedelta(hours=1))
    rad = np.radians(h.viento_dir_deg)
    h["_u"] = -h.viento_ms * np.sin(rad)          # componentes del vector (dirección "desde donde sopla")
    h["_v"] = -h.viento_ms * np.cos(rad)

    fl = h.groupby("b_flujo").agg(**{c.replace("_mm", "_6h_mm"): (c, lambda s: s.sum(min_count=1)) for c in FLUJOS},
                                  n_horas_flujo=("sf_mm", "count")).reindex(todos)
    ins = h.groupby("b_inst").agg(
        t2m_C=("t2m_C", "mean"), t2m_min_C=("t2m_C", "min"), t2m_max_C=("t2m_C", "max"),
        tsn_C=("tsn_C", "mean"),
        viento_ms=("viento_ms", "mean"), viento_max_ms=("viento_ms", "max"), _u=("_u", "mean"), _v=("_v", "mean"),
        sde_m=("sde_m", "last"), snowc_pct=("snowc_pct", "mean"), rsn_kgm3=("rsn_kgm3", "mean"),
        isoterma_msnm=("isoterma_msnm", "mean"), isoterma_min_msnm=("isoterma_msnm", "min"),
        isoterma_max_msnm=("isoterma_msnm", "max"), isoterma_censurada=("isoterma_censurada", "any"),
        _iso_sum=("isoterma_msnm", "sum"), _iso_n=("isoterma_msnm", "count"),
        horas_bajo_cero=("bajo_cero", "sum"), horas_nevando=("nieve_cayendo", "sum"),
        horas_nieve_intensa=("nieve_intensa", "sum"), horas_lloviendo=("lloviendo", "sum"),
        horas_viento_fuerte=("viento_fuerte", "sum"), n_horas=("t2m_C", "count"),
        n_celdas_validas=("n_celdas_validas", "min"),
    ).reindex(todos)
    b = fl.join(ins)
    b["viento_dir_deg"] = (np.degrees(np.arctan2(-b._u, -b._v)) % 360).where(b.viento_ms > 0)

    # ventanas del protocolo alineadas a los bloques
    def ventana(col, nb, n_min):
        s = b[col].rolling(nb, min_periods=1).sum()
        n = b.n_horas_flujo.rolling(nb, min_periods=1).sum()
        return s.where(n >= n_min)
    b["sf_12h_mm"] = ventana("sf_6h_mm", 2, 6)
    b["nieve_12h_cm"] = b.sf_12h_mm * A_CM_MM
    b["nieve_24h_cm"] = ventana("sf_6h_mm", 4, 12) * A_CM_MM
    b["lluvia_12h_mm"] = ventana("lluvia_6h_mm", 2, 6)
    b["tp_12h_mm"] = ventana("tp_6h_mm", 2, 6)
    b["nieve_6h_cm"] = b.sf_6h_mm * A_CM_MM
    b["dsde_12h_cm"] = (b.sde_m - b.sde_m.shift(2)) * 100
    n12 = b._iso_n.rolling(2, min_periods=1).sum()
    b["isoterma_12h_media"] = (b._iso_sum.rolling(2, min_periods=1).sum() / n12).where(n12 >= 6)
    b["isoterma_12h_min"] = b.isoterma_min_msnm.rolling(2, min_periods=1).min().where(n12 >= 6)
    return b.drop(columns=["_u", "_v", "_iso_sum", "_iso_n"])


partes = []
for (ruta, tramo), h in era.groupby(["ruta", "tramo"], sort=False):
    b = agregar_tramo(h)
    b.insert(0, "tramo", tramo)
    b.insert(0, "ruta", ruta)
    partes.append(b.rename_axis("bloque_inicio_local").reset_index())
blo = pd.concat(partes, ignore_index=True)
blo = blo[(blo.bloque_inicio_local >= PERIODO_LOCAL[0]) & (blo.bloque_inicio_local <= PERIODO_LOCAL[1])]
blo["bloque_fin_local"] = blo.bloque_inicio_local + pd.Timedelta(hours=BLOQUE_H)
blo["bloque_inicio_utc"] = blo.bloque_inicio_local - pd.Timedelta(hours=TZ)
blo["fecha_local"] = blo.bloque_inicio_local.dt.date
blo["bloque_dia"] = blo.bloque_inicio_local.dt.hour // BLOQUE_H
blo["bloque"] = blo.bloque_inicio_local.dt.strftime("%H") + "-" + blo.bloque_fin_local.dt.strftime("%H").replace("00", "24")
blo["mes"] = blo.bloque_inicio_local.dt.strftime("%Y-%m")
for c in ["horas_bajo_cero", "horas_nevando", "horas_nieve_intensa", "horas_lloviendo", "horas_viento_fuerte",
          "n_horas", "n_horas_flujo", "n_celdas_validas"]:
    blo[c] = blo[c].fillna(0).astype(int)
blo["isoterma_censurada"] = blo.isoterma_censurada.eq(True)

cols = ["ruta", "tramo", "bloque_inicio_local", "bloque_fin_local", "bloque_inicio_utc", "fecha_local", "bloque_dia",
        "bloque", "mes", "n_horas", "n_horas_flujo",
        "t2m_C", "t2m_min_C", "t2m_max_C", "tsn_C", "viento_ms", "viento_max_ms", "viento_dir_deg",
        "tp_6h_mm", "sf_6h_mm", "nieve_6h_cm", "lluvia_6h_mm", "smlt_6h_mm", "es_6h_mm",
        "sde_m", "snowc_pct", "rsn_kgm3",
        "isoterma_msnm", "isoterma_min_msnm", "isoterma_max_msnm", "isoterma_censurada",
        "sf_12h_mm", "nieve_12h_cm", "nieve_24h_cm", "lluvia_12h_mm", "tp_12h_mm", "dsde_12h_cm",
        "isoterma_12h_media", "isoterma_12h_min",
        "horas_bajo_cero", "horas_nevando", "horas_nieve_intensa", "horas_lloviendo", "horas_viento_fuerte",
        "n_celdas_validas"]
blo = blo[cols].round(3)
blo.to_csv(SAL + "/era5_tramos_6h.csv", index=False)


# ------------------------------------------------------------------------------------
# 2. estado observado por ruta
# ------------------------------------------------------------------------------------
est["bloque_inicio_local"] = bloque(est.fecha_hora_local)
filas = []
for (ruta, b0), g in est.groupby(["ruta", "bloque_inicio_local"]):
    horas = g.estado.value_counts()
    if horas.get("cerrado_meteo", 0) > 0:
        e = "cerrado_meteo"
    else:
        e = max(horas.index, key=lambda k: (horas[k], SEVERIDAD.get(k, -1)))
    ref = g[g.estado == e].iloc[0]                 # primera hora del bloque con ese estado
    fila = dict(ruta=ruta, bloque_inicio_local=b0, estado=e,
                **{"horas_" + k: int(horas.get(k, 0)) for k in ESTADOS},
                horas_con_dato=int(g.estado.notna().sum()),
                cerrado=bool(g.cerrado.any()), transitable_todo_tipo=bool(g.transitable_todo_tipo.all()),
                nivel=int(g.nivel.max()), regimen=ref.regimen, id_registro=";".join(dict.fromkeys(g.id_registro.dropna().astype(str))) or None,
                fuente_estado=ref.fuente_estado, causa=ref.causa)
    filas.append(fila)
eb = pd.DataFrame(filas)
eb = eb[(eb.bloque_inicio_local >= PERIODO_LOCAL[0]) & (eb.bloque_inicio_local <= PERIODO_LOCAL[1])]
eb.to_csv(SAL + "/estado_caminos_6h.csv", index=False)

print("ERA5 6 h:", blo.shape, blo.groupby(["ruta", "tramo"]).size().to_dict())
print("periodo:", blo.bloque_inicio_local.min(), "->", blo.bloque_inicio_local.max())
print("nulos:"); print(blo.isna().sum()[lambda s: s > 0].to_string())
print("estado 6 h:", eb.shape); print(eb.groupby("ruta").estado.value_counts().to_string())
chk = era.groupby(["ruta", "tramo"]).sf_mm.sum().round(1).rename("sf_horario").to_frame().join(
    blo.groupby(["ruta", "tramo"]).sf_6h_mm.sum().round(1).rename("sf_6h"))
print(chk.to_string())
