# -*- coding: utf-8 -*-
"""
Genera salidas/dashboard_SAM_Cordillera.html: la meteorología ERA5 / ERA5-Land por tramo, el estado
observado de los caminos y los resultados de SAM-Cordillera (severidad, peligro, nieve por despejar y
estados E0 a E5), en bloques de 6 h locales.

Uso (desde la carpeta "modelo_sam"):
    python scripts/generar_dashboard_sam.py

Además de las salidas meteorológicas, lee las del sistema (scripts/sistema_condicion.py):
    salidas/sistema/bloques.csv, estado_ruta.csv, metricas.csv, episodios.csv,
    contrafactual_60CH.csv, sensibilidad.csv, parametros.json

Lee:
    salidas/consolidado_6h.csv
    salidas/modelo_cierre_diario.csv
    salidas/modelo_cierre_episodios.csv
    salidas/modelo_cierre_metricas.csv
    salidas/modelo_cierre_parametros.json
    salidas/era5_tramos_meta.csv
    salidas/estado_caminos_eventos.csv
    scripts/dashboard_plantilla.html
    scripts/fuentes_embebidas.css
Escribe:
    salidas/dashboard_SAM_Cordillera.html
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
SALIDAS = RAIZ / "salidas"
SCRIPTS = RAIZ / "scripts"
SISTEMA = SALIDAS / "sistema"
ESTADOS_SAM = ["E0", "E1", "E2", "E3", "E4", "E5"]

RUTAS = ["60-CH", "G-21"]
TRAMOS = ["alto", "medio"]
ESTADOS = ["abierto", "restringido", "cierre_tecnico", "cerrado_meteo", "cerrado_horario"]
COL_HORAS_EST = {"abierto": "horas_abierto_obs", "restringido": "horas_restringido_obs", "cierre_tecnico": "horas_cierre_tecnico_obs",
                 "cerrado_meteo": "horas_cerrado_obs", "cerrado_horario": "horas_cerrado_horario_obs"}
PASO_H = 6   # horas por bloque

# Descripción en lenguaje llano de cada tramo (docs/modelo_cierre.md, sección 1)
DESCRIPCION_TRAMO = {
    ("60-CH", "alto"): "de la barrera de Guardia Vieja al túnel Cristo Redentor; es el trecho que la autoridad cierra",
    ("60-CH", "medio"): "de Río Blanco a Guardia Vieja, el trecho anterior a la barrera",
    ("G-21", "alto"): "Farellones y los accesos a los centros de esquí (G-21-2, G-21-3, G-21-4, G-249, G-251)",
    ("G-21", "medio"): "la subida de curvas entre La Ermita y la curva 32 (G-21-1-13)",
}
NOMBRE_RUTA = {
    "60-CH": "Ruta 60-CH · Los Andes – Los Libertadores",
    "G-21": "Ruta G-21 · Farellones – El Colorado",
}
MODELOS_TABLA = [            # orden de la tabla de desempeño (salidas/sistema/metricas.csv)
    "protocolo (cuadro, sin persistencia)",
    "peligro dentro de la severidad",
    "Walker pura",
    "híbrida (propuesta)",
    "persistencia (bloque anterior)",
]
NOMBRE_MODELO = {
    "protocolo (cuadro, sin persistencia)": "Protocolo Lo Barnechea",
    "peligro dentro de la severidad": "peligro como variable de la severidad",
    "Walker pura": "severidad de Walker sin piso",
    "híbrida (propuesta)": "SAM-Cordillera (regla híbrida)",
    "persistencia (bloque anterior)": "persistencia del estado observado",
}
MODELO_CALIBRADO = "híbrida (propuesta)"


# ------------------------------------------------------------------ utilidades
def num(x, dec: int = 1):
    """Redondea y convierte NaN/None a None (-> null en JSON)."""
    if x is None:
        return None
    try:
        if isinstance(x, str):
            return x
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        return None
    if isinstance(x, (bool,)):
        return bool(x)
    v = float(x)
    if math.isnan(v) or math.isinf(v):
        return None
    if dec == 0:
        return int(round(v))
    r = round(v, dec)
    return int(r) if r == int(r) else r


def col(df: pd.DataFrame, nombre: str, dec: int = 1) -> list:
    return [num(v, dec) for v in df[nombre].tolist()]


def col_bool(df: pd.DataFrame, nombre: str) -> list:
    out = []
    for v in df[nombre].tolist():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(None)
        elif isinstance(v, str):
            out.append(1 if v.strip().lower() in ("true", "1", "sí", "si") else 0)
        else:
            out.append(1 if bool(v) else 0)
    return out


def col_cat(df: pd.DataFrame, nombre: str, catalogo: list) -> list:
    """Codifica una columna de texto como índice en `catalogo` (se amplía si hace falta)."""
    out = []
    for v in df[nombre].tolist():
        if v is None or (isinstance(v, float) and math.isnan(v)) or v == "":
            out.append(None)
            continue
        v = str(v)
        if v not in catalogo:
            catalogo.append(v)
        out.append(catalogo.index(v))
    return out


def texto(x) -> str | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return str(x)


# ------------------------------------------------------------------ carga
def cargar():
    h = pd.read_csv(SALIDAS / "consolidado_6h.csv")
    d = pd.read_csv(SALIDAS / "modelo_cierre_diario.csv")
    ep = pd.read_csv(SALIDAS / "modelo_cierre_episodios.csv")
    met = pd.read_csv(SALIDAS / "modelo_cierre_metricas.csv")
    meta = pd.read_csv(SALIDAS / "era5_tramos_meta.csv")
    ev = pd.read_csv(SALIDAS / "estado_caminos_eventos.csv")
    hh = pd.read_csv(SALIDAS / "era5_tramos_horario.csv", parse_dates=["fecha_hora_local"])
    eh = pd.read_csv(SALIDAS / "estado_caminos_horario.csv", parse_dates=["fecha_hora_local"])
    with open(SALIDAS / "modelo_cierre_parametros.json", encoding="utf-8") as f:
        # el JSON de parámetros trae NaN literales (válidos para Python, no para JSON estricto)
        par = json.load(f)
    sis = {
        "b": pd.read_csv(SISTEMA / "bloques.csv"),
        "r": pd.read_csv(SISTEMA / "estado_ruta.csv"),
        "met": pd.read_csv(SISTEMA / "metricas.csv"),
        "ep": pd.read_csv(SISTEMA / "episodios.csv"),
        "cf": pd.read_csv(SISTEMA / "contrafactual_60CH.csv"),
        "sens": pd.read_csv(SISTEMA / "sensibilidad.csv"),
    }
    with open(SISTEMA / "parametros.json", encoding="utf-8") as f:
        sis["par"] = json.load(f)
    return h, d, ep, met, meta, ev, par, hh, eh, sis


def serie_horaria(hh: pd.DataFrame, eh: pd.DataFrame, inicio: pd.Timestamp, n_horas: int) -> dict:
    """Series hora a hora alineadas al inicio de los bloques, para el gráfico "de horas a bloques".
    Índice h = hora local que empieza en inicio + h. La nieve rotulada t por ERA5 (caída en t-1..t)
    se guarda en h = t-1, igual que en agregar_bloques_6h.py; temperatura y estado, en h = t."""
    horas = pd.date_range(inicio, periods=n_horas, freq="h")
    out = {"tramos": {}, "est": {}}
    for r in RUTAS:
        for t in TRAMOS:
            g = hh[(hh.ruta == r) & (hh.tramo == t)].set_index("fecha_hora_local")
            sf = g.sf_mm.copy(); sf.index = sf.index - pd.Timedelta(hours=1)
            out["tramos"][f"{r}|{t}"] = {
                "sf": [num(v, 2) for v in sf.reindex(horas).tolist()],           # cm de nieve en la hora (10:1)
                "t2m": [num(v, 1) for v in g.t2m_C.reindex(horas).tolist()],
            }
        e = eh[eh.ruta == r].set_index("fecha_hora_local").estado.reindex(horas)
        out["est"][r] = [None if texto(v) is None else ESTADOS.index(v) for v in e.tolist()]
    return out


def armar_datos() -> dict:
    h, d, ep, met, meta, ev, par, hh, eh, sis = cargar()
    sb = sis["b"].sort_values(["ruta", "tramo", "bloque_inicio_local"]).reset_index(drop=True)
    sr = sis["r"].sort_values(["ruta", "bloque_inicio_local"]).reset_index(drop=True)

    h = h.sort_values(["ruta", "tramo", "bloque_inicio_local"]).reset_index(drop=True)
    d = d.sort_values(["ruta", "tramo", "fecha_local"]).reset_index(drop=True)

    # --- eje temporal común -------------------------------------------------
    base = h[(h.ruta == RUTAS[0]) & (h.tramo == TRAMOS[0])]
    n = len(base)
    inicio_local = str(base.bloque_inicio_local.iloc[0])       # "2026-07-01 00:00:00"
    fin_local = str(base.bloque_fin_local.iloc[-1])
    inicio_iso = inicio_local.replace(" ", "T")[:16]
    t0 = pd.Timestamp(inicio_local)
    for r in RUTAS:
        for t in TRAMOS:
            g = h[(h.ruta == r) & (h.tramo == t)]
            assert len(g) == n, f"{r} {t}: {len(g)} bloques, se esperaban {n}"
            assert str(g.bloque_inicio_local.iloc[0]) == inicio_local

    dias = sorted(d.fecha_local.unique().tolist())
    dia_offset = {dd: int((pd.Timestamp(dd) - t0) / pd.Timedelta(hours=PASO_H)) for dd in dias}   # en bloques

    # --- catálogos de texto -------------------------------------------------
    regimenes: list[str] = []
    causas: list[str] = []
    fuentes: list[str] = []
    bandas = ["baja (<1500)", "media (1500-2800)", "alta (>2800)"]

    # --- series por ruta (isoterma y estado observado: iguales en ambos tramos)
    rutas_h = {}
    for r in RUTAS:
        g = h[(h.ruta == r) & (h.tramo == "alto")].reset_index(drop=True)
        est = []
        for v in g.estado_observado.tolist():
            est.append(None if texto(v) is None else ESTADOS.index(v))
        rutas_h[r] = {
            "iso": col(g, "isoterma_msnm", 0),
            "isoM": col(g, "isoterma_12h_media", 0),
            "isoMin": col(g, "isoterma_12h_min", 0),
            "isoBmin": col(g, "isoterma_min_msnm", 0),
            "isoBmax": col(g, "isoterma_max_msnm", 0),
            "banda": [None if texto(v) is None else bandas.index(v) for v in g.banda_isoterma.tolist()],
            "isoCens": col_bool(g, "isoterma_censurada"),
            "est": est,
            "reg": col_cat(g, "regimen_observado", regimenes),
            "causa": col_cat(g, "causa_observada", causas),
            "fuente": col_cat(g, "fuente_estado_observado", fuentes),
            "cobs": col_bool(g, "cerrado_observado"),
            "hcer": col(g, "horas_cerrado_obs", 0),
        }
        gr_ = sr[sr.ruta == r].reset_index(drop=True)
        assert len(gr_) == n and str(gr_.bloque_inicio_local.iloc[0]) == inicio_local
        rutas_h[r]["E"] = [ESTADOS_SAM.index(v) for v in gr_.E.tolist()]
        rutas_h[r]["tc"] = [TRAMOS.index(v) for v in gr_.tramo_critico.tolist()]

    # --- series por ruta|tramo ----------------------------------------------
    tramos_h = {}
    for r in RUTAS:
        for t in TRAMOS:
            g = h[(h.ruta == r) & (h.tramo == t)].reset_index(drop=True)
            tramos_h[f"{r}|{t}"] = {
                "t2m": col(g, "t2m_C", 1),
                "tmin": col(g, "t2m_min_C", 1),
                "tmax": col(g, "t2m_max_C", 1),
                "tsn": col(g, "tsn_C", 1),
                "viento": col(g, "viento_ms", 1),
                "sf": col(g, "nieve_6h_cm", 1),    # cm de nieve en el bloque (10:1)
                "lluvia": col(g, "lluvia_6h_mm", 1),
                "s12": col(g, "nieve_12h_cm", 1),  # S
                "s24": col(g, "nieve_24h_cm", 1),
                "r12": col(g, "lluvia_12h_mm", 1), # R
                "sde": col(g, "sde_m", 2),
                "dsde": col(g, "dsde_12h_cm", 1),
                "L": col(g, "nivel_protocolo", 0),
                "Lr": col(g, "nivel_regularizado", 0),
                "mu": col_bool(g, "cerrado_modelo_umbral"),
                "mp": col_bool(g, "cerrado_modelo_persistencia"),
                "ncel": col(g, "n_celdas_validas", 0),
            }
            gs = sb[(sb.ruta == r) & (sb.tramo == t)].reset_index(drop=True)
            assert len(gs) == n and str(gs.bloque_inicio_local.iloc[0]) == inicio_local
            tramos_h[f"{r}|{t}"].update({
                "SV": col(gs, "SV_hibrida", 2), "H": col(gs, "H", 0), "N": col(gs, "N", 1),
                "Sef": col(gs, "S6_ef", 1), "phi": col(gs, "phi6", 2),
                "E": [ESTADOS_SAM.index(v) for v in gs.E.tolist()],
            })
            del tramos_h[f"{r}|{t}"]["mu"], tramos_h[f"{r}|{t}"]["mp"]

    # --- diario por ruta|tramo ----------------------------------------------
    diario = {}
    for r in RUTAS:
        for t in TRAMOS:
            g = d[(d.ruta == r) & (d.tramo == t)].reset_index(drop=True)
            assert g.fecha_local.tolist() == dias
            diario[f"{r}|{t}"] = {
                "tmed": col(g, "t2m_media", 1), "tmin": col(g, "t2m_min", 1), "tmax": col(g, "t2m_max", 1),
                "hbc": col(g, "horas_bajo_cero", 0),
                "nieve": col(g, "nieve_dia_cm", 1), "lluvia": col(g, "lluvia_dia_mm", 1),
                "smax": col(g, "S_max12_cm", 1), "rmax": col(g, "R_max12_mm", 1),
                "zmed": col(g, "Z_media", 0), "zmin": col(g, "Z_min", 0), "zmax": col(g, "Z_max", 0),
                "sde": col(g, "sde_fin_m", 2), "dsde": col(g, "dsde_dia_cm", 1),
                "vmax": col(g, "viento_max_ms", 1),
                "L": col(g, "L_protocolo", 0), "Lr": col(g, "L_regularizado", 0),
                "bL3": col(g, "bloques_L3", 0),
                "hcer": col(g, "horas_cerrado_obs", 0), "hres": col(g, "horas_restringido_obs", 0),
                "cobs": col_bool(g, "cerrado_obs"), "cobsDia": col_bool(g, "cerrado_obs_dia_completo"),
                "estdom": [None if texto(v) is None else ESTADOS.index(v) for v in g.estado_obs_dominante.tolist()],
            }
            gs = sb[(sb.ruta == r) & (sb.tramo == t)].copy()
            gs["fecha"] = gs.bloque_inicio_local.str[:10]
            gs["Ei"] = gs.E.map(ESTADOS_SAM.index)
            dd_ = gs.groupby("fecha").agg(Emax=("Ei", "max"), bcer=("Ei", lambda v: int((v >= 3).sum())),
                                          SVmax=("SV_hibrida", "max"), Hmax=("H", "max"), Nmax=("N", "max")).reindex(dias)
            diario[f"{r}|{t}"].update({"Emax": [None if pd.isna(v) else int(v) for v in dd_.Emax],
                                       "bcer": [None if pd.isna(v) else int(v) for v in dd_.bcer],
                                       "SVmax": [num(v, 2) for v in dd_.SVmax], "Hmax": [num(v, 0) for v in dd_.Hmax],
                                       "Nmax": [num(v, 1) for v in dd_.Nmax]})

    # --- metadatos de tramo -------------------------------------------------
    meta_out = {}
    for _, row in meta.iterrows():
        meta_out.setdefault(row.ruta, {})[row.tramo] = {
            "definicion": texto(row.definicion),
            "descripcion": DESCRIPCION_TRAMO[(row.ruta, row.tramo)],
            "longitud_km": num(row.longitud_km, 1),
            "n_celdas": num(row.n_celdas, 0),
            "celdas": texto(row.celdas),
            "cota_min": num(row.cota_camino_min, 0),
            "cota_media": num(row.cota_camino_media, 0),
            "cota_max": num(row.cota_camino_max, 0),
            "cota_celdas": num(row.cota_celdas_ponderada, 0),
            "pesos": texto(row.pesos),
            "iso_celdas": texto(row.isoterma_celdas_era5),
            "iso_censuradas": num(row.isoterma_horas_censuradas, 0),
        }

    # --- indicadores de las fichas -----------------------------------------
    kpi = {}
    for r in RUTAS:
        gr = h[(h.ruta == r) & (h.tramo == "alto")]
        dr = d[(d.ruta == r) & (d.tramo == "alto")]
        k = {
            "tramos": {},
            "obs": {
                "h_" + e: int(gr[COL_HORAS_EST[e]].sum()) for e in ESTADOS
            },
        }
        k["obs"]["h_sin_dato"] = int(PASO_H * len(gr) - sum(k["obs"].values()))
        k["obs"]["bloques_cerrado"] = int(gr.cerrado_observado.sum())
        k["obs"]["episodios"] = int((ep.ruta == r).sum())
        k["obs"]["dias_cerrado"] = int(dr.cerrado_obs.sum())
        k["obs"]["dias_cerrado_completo"] = int(dr.cerrado_obs_dia_completo.sum())
        k["obs"]["dias_restringido"] = int((dr.horas_restringido_obs > 0).sum())
        k["obs"]["horas_episodio_max"] = num(ep[ep.ruta == r].horas.max(), 0)
        k["iso_mediana"] = num(gr.isoterma_msnm.median(), 0)
        k["iso_min"] = num(gr.isoterma_msnm.min(), 0)
        k["h_banda"] = {b: int((gr.banda_isoterma == b).sum()) for b in bandas}
        for t in TRAMOS:
            g = h[(h.ruta == r) & (h.tramo == t)]
            dg = d[(d.ruta == r) & (d.tramo == t)]
            gs = sb[(sb.ruta == r) & (sb.tramo == t)]
            k["tramos"][t] = {
                "nieve_cm": num(g.nieve_6h_cm.sum(), 0),
                "nieve_jul_cm": num(g[g.mes == "2026-07"].nieve_6h_cm.sum(), 0),
                "nieve_ago_cm": num(g[g.mes == "2026-08"].nieve_6h_cm.sum(), 0),
                "s12_max": num(g.nieve_12h_cm.max(), 1),
                "s12_max_fecha": texto(g.loc[g.nieve_12h_cm.idxmax(), "bloque_inicio_local"])[:16],
                "manto_max": num(g.sde_m.max(), 2),
                "manto_fin": num(g.sde_m.iloc[-1], 2),
                "hbc": int(g.horas_bajo_cero.sum()),
                "h_nevando": int(g.horas_nevando.sum()),
                "tmed": num(g.t2m_C.mean(), 1),
                "tmin": num(g.t2m_min_C.min(), 1),
                "tmax": num(g.t2m_max_C.max(), 1),
                "lluvia_mm": num(g.lluvia_6h_mm.sum(), 1),
                "bloques_L2": int((g.nivel_regularizado >= 2).sum()),
                "bloques_modelo": int(gs.E.isin(["E3", "E4", "E5"]).sum()),
                "SVmax": num(gs.SV_hibrida.max(), 1), "Hmax": num(gs.H.max(), 0), "Nmax": num(gs.N.max(), 0),
                "dias_nevada": int((dg.nieve_dia_cm >= 1).sum()),
                "dias_L3": int((dg.L_regularizado == 3).sum()),
                "dias_L2": int((dg.L_regularizado >= 2).sum()),

            }
        mm = sis["met"]
        m = mm[(mm.modelo == MODELO_CALIBRADO) & (mm.ruta == r)].iloc[0]
        er = sr[sr.ruta == r]
        k["sam"] = {
            "a": int(m.aciertos), "b": int(m.falsas_alarmas), "c": int(m.omisiones), "d": int(m.negativos_correctos),
            "n": int(m.n), "POD": num(m.POD, 2), "FAR": num(m.FAR, 2), "CSI": num(m.CSI, 2), "HSS": num(m.HSS, 2),
            "kappa": num(m.kappa_ponderado, 2), "exactitud": num(m.exactitud_3clases, 2),
            "bloques_cerrado": int(er.E.isin(["E3", "E4", "E5"]).sum()),
            "tramos_distintos": None,
        }
        pv = sb[sb.ruta == r].pivot_table(index="bloque_inicio_local", columns="tramo", values="E", aggfunc="first")
        k["sam"]["tramos_distintos"] = int((pv.alto != pv.medio).sum())
        kpi[r] = k

    # --- métricas -----------------------------------------------------------
    metricas = []
    for _, row in sis["met"].iterrows():
        metricas.append({
            "modelo": row.modelo, "nombre": NOMBRE_MODELO.get(row.modelo, row.modelo), "ruta": row.ruta,
            "a": num(row.aciertos, 0), "b": num(row.falsas_alarmas, 0),
            "c": num(row.omisiones, 0), "d": num(row.negativos_correctos, 0), "n": num(row.n, 0),
            "POD": num(row.POD, 2), "FAR": num(row.FAR, 2), "CSI": num(row.CSI, 2), "HSS": num(row.HSS, 2),
            "kappa": num(row.kappa_ponderado, 2), "exactitud": num(row.exactitud_3clases, 2),
        })

    # --- parámetros de SAM-Cordillera ------------------------------------
    P = sis["par"]
    parametros = {
        "rho": num(par.get("rho_nieve_fresca_kg_m3"), 0),
        "cortes": P["cortes"], "beta": P["beta"], "veto": P["veto"], "umbral_E": P["umbral_E"],
        "H_niveles": P["H_niveles"], "H_umbral": P["H_umbral_calibrado"], "N_parcial": P["N_parcial"],
        "theta1": P["theta1_cm"], "c": P["c_calibrado_cm_h"], "theta": P["theta_calibrado_cm"],
        "exposicion": P["exposicion"], "delta": P["delta_nieve_m"], "gamma": P["factor_rafaga"],
        "alfa": P["arrastre_frac"], "hn_sobrecarga": P["hn_min_sobrecarga"],
        "curva_capacidad": P["curva_capacidad"],
        "ordinal": {"variables": P["ordinal"]["variables"], "coef": P["ordinal"]["coef_estandarizados"]},
        "contrafactual": [{"esc": row.escenario, "c": num(row.c_cm_h, 1), "obs": int(row.horas_cerradas_obs),
                           **{e: int(row["h_" + e]) for e in ESTADOS_SAM},
                           "sin": int(row.h_sin_respaldo), "pct": num(row.pct_sin_respaldo, 1)} for _, row in sis["cf"].iterrows()],
        "sensibilidad": [{"sup": re.sub(r"\s*\(v\d+\)", "", row.supuesto), "kG": num(row.kappa_G21, 3), "csiG": num(row.CSI_G21, 3), "farG": num(row.FAR_G21, 3),
                          "kC": num(row.kappa_60CH, 3), "pct": num(row.pct_sin_respaldo_60CH, 1), "pel": num(row.pct_por_peligro_60CH, 1)}
                         for _, row in sis["sens"].iterrows()],
    }

    # --- episodios de cierre observados ------------------------------------
    episodios = []
    for _, row in sis["ep"].iterrows():
        episodios.append({
            "ruta": row.ruta, "inicio": texto(row.inicio)[:16], "fin": texto(row.fin)[:16],
            "horas": num(row.horas_obs, 0), "bloques": num(row.bloques, 0),
            **{e: num(row["bloques_" + e], 0) for e in ESTADOS_SAM},
            "h_modelo": num(row.horas_modelo_cerrado, 0), "error_h": num(row.error_duracion_h, 0),
            "causa": texto(row.causa),
        })

    # --- eventos contiguos de estado observado (sin los cierres por horario)
    eventos = []
    for _, row in ev.iterrows():
        if row.estado not in ESTADOS:
            continue
        eventos.append({
            "ruta": row.ruta, "estado": ESTADOS.index(row.estado),
            "regimen": texto(row.regimen),
            "inicio": texto(row.inicio_local)[:16], "fin": texto(row.fin_local)[:16],
            "horas": num(row.horas, 0), "causa": texto(row.causa),
        })

    # --- vacíos conocidos, contados desde los datos -------------------------
    vacios = {}
    for r in RUTAS:
        for t in TRAMOS:
            g = h[(h.ruta == r) & (h.tramo == t)]
            vacios[f"{r}|{t}"] = {
                "tsn": int(g.tsn_C.isna().sum()),            # bloques
                "smlt": int(g.smlt_6h_mm.isna().sum()),
                "s12": int(g.nieve_12h_cm.isna().sum()),
                "s24": int(g.nieve_24h_cm.isna().sum()),
                "incompletos": int((g.n_horas_flujo < PASO_H).sum()),
                "estado": int(g.estado_observado.isna().sum()),
                "viento_max": num(g.viento_max_ms.max(), 1),
            }

    return {
        "inicio": inicio_iso,
        "fin": fin_local[:16],
        "n": n,
        "paso_h": PASO_H,
        "rutas": RUTAS,
        "tramos": TRAMOS,
        "nombres": NOMBRE_RUTA,
        "estados": ESTADOS,
        "regimenes": regimenes,
        "causas": causas,
        "fuentes": fuentes,
        "bandas": bandas,
        "dias": dias,
        "diaOffset": dia_offset,
        "meta": meta_out,
        "rutas_h": rutas_h,
        "tramos_h": tramos_h,
        "horario": serie_horaria(hh, eh, t0, n * PASO_H),
        "diario": diario,
        "kpi": kpi,
        "metricas": metricas,
        "modelos_tabla": MODELOS_TABLA,
        "estados_sam": ESTADOS_SAM,
        "modelo_calibrado": MODELO_CALIBRADO,
        "parametros": parametros,
        "episodios": episodios,
        "eventos": eventos,
        "vacios": vacios,
    }


# ------------------------------------------------------------------ salida
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # consolas cp1252 de Windows
    datos = armar_datos()
    js = json.dumps(datos, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    json.loads(js)                                   # valida que sea JSON estricto
    js = js.replace("</", "<\\/")                    # nunca cerrar el <script> por accidente

    plantilla = (SCRIPTS / "dashboard_plantilla_sam.html").read_text(encoding="utf-8")
    fuentes = (SCRIPTS / "fuentes_embebidas.css").read_text(encoding="utf-8")
    for marca in ("__DATOS__", "__FUENTES__"):
        if plantilla.count(marca) != 1:
            raise SystemExit(f"la plantilla debe contener exactamente una vez {marca}")
    html = plantilla.replace("__FUENTES__", fuentes).replace("__DATOS__", js)

    destino = SALIDAS / "dashboard_SAM_Cordillera.html"
    destino.write_text(html, encoding="utf-8")

    # --- verificación del archivo escrito -----------------------------------
    leido = destino.read_text(encoding="utf-8")
    m = re.search(r'<script id="datos" type="application/json">(.*?)</script>', leido, re.S)
    if not m:
        raise SystemExit("no se encontró el bloque de datos en el HTML generado")
    recuperado = json.loads(m.group(1).replace("<\\/", "</"))
    assert recuperado["n"] == datos["n"]
    # el bloque JSON no puede traer NaN/Infinity/undefined; el HTML visible tampoco
    # (el código JS sí usa Number.isNaN y -Infinity legítimamente, por eso se excluye)
    for mala in ("NaN", "undefined", "Infinity"):
        if re.search(r"\b" + mala + r"\b", m.group(1)):
            raise SystemExit(f"el bloque de datos contiene '{mala}'")
    visible = re.sub(r"<script\b.*?</script>", "", leido.replace(fuentes, ""), flags=re.S)
    for mala in ("NaN", "undefined", "null"):
        if re.search(r"\b" + mala + r"\b", visible):
            raise SystemExit(f"el HTML visible contiene '{mala}'")
    kb_total = len(leido.encode("utf-8")) / 1024
    kb_fuentes = len(fuentes.encode("utf-8")) / 1024
    kb_datos = len(js.encode("utf-8")) / 1024
    print(f"OK  {destino}")
    print(f"    tamaño total {kb_total:,.0f} kB · fuentes {kb_fuentes:,.0f} kB · datos {kb_datos:,.0f} kB · "
          f"sin fuentes {kb_total - kb_fuentes:,.0f} kB")
    print(f"    {datos['n']} bloques de {PASO_H} h × {len(datos['tramos_h'])} tramos · {len(datos['dias'])} días · "
          f"{len(datos['episodios'])} episodios · {len(datos['metricas'])} filas de métricas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
