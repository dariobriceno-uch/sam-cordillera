# -*- coding: utf-8 -*-
r"""Modelo de cierre de ruta a partir del protocolo de Lo Barnechea (Niveles y Gatillantes).

Fuente del cuadro: "Protocolo cierre de caminos públicos del Centro de Montaña Lo
Barnechea", 3 jul 2026, sección 6 (Niveles y Gatillantes) y 7 (Criterio de cierre).

Resolución: bloques de 6 h en hora local (00-06, 06-12, 12-18, 18-24), armados por
agregar_bloques_6h.py. La ventana de 12 h del protocolo son exactamente 2 bloques.

Notación (tramo i, bloque t de 6 h, ventana W = 12 h = 2 bloques):
    S_i(t) = (100/rho) * [ sf_i(t) + sf_i(t-1) ]           nieve caída en 12 h  [cm]  (sf_i: mm en el bloque)
    R_i(t) = [ (tp_i - sf_i)(t) + (tp_i - sf_i)(t-1) ]     precipitación líquida en 12 h [mm]
    Z(t)   = altura media de la isoterma 0 °C en la ventana [m s.n.m.]
    (V: visibilidad y D: vehículos/día no están en ERA5 -> gatillantes omitidos)

Cuadro del protocolo, escrito como conjunto de gatillantes g_{l,j}(S,R,Z) por nivel l:
    Nivel 1:  1 < S < 25                                       (cualquier Z)
    Nivel 2:  25 <= S < 50  y  1500 <= Z <= 2800
              R >= r2                                          ("presencia de precipitación líquida")
    Nivel 3:  1 < S < 50   y   900 <= Z <= 1500
              S >= 50      y  1501 <= Z <= 2800
              R >= 20      y  Z > 2800
    L(t) = max{ l : algún g_{l,j}(t) se cumple },  L = 0 si ninguno.

El cuadro deja combinaciones sin nivel (p. ej. S entre 25 y 50 con Z < 1500, o
S >= 50 con Z > 2800). Versión regularizada por banda de isoterma b(Z):
    b = baja  (Z < 1500):   L* = 3·1[S > 1]
    b = media (1500..2800): L* = 1·1[1 < S < 25] + 2·1[25 <= S < 50] + 3·1[S >= 50]
    b = alta  (Z > 2800):   L* = max( 1·1[S > 1], 2·1[R >= r2], 3·1[R >= 20] )
que coincide con el cuadro en todas las celdas definidas y es monótona en S y R.

Regla de cierre del protocolo (sección 7): Nivel 3 -> cierre total; Nivel 2 -> cierre
parcial (solo bajada). Decisión diaria: L_d = max_t L(t) sobre los 4 bloques del día local.

Persistencia (lo que el cuadro no modela): el camino sigue cerrado mientras haya
nieve por despejar. Balance con capacidad de despeje c [cm/h], aplicado por bloque de Δ = 6 h:
    N(t) = max{ 0, N(t-1) + a·sf(t) - c·Δ },   a = 100/rho
    cerrado(t) = 1  si L*(t) = 3  o  (cerrado(t-1) = 1 y N(t) > theta)
Parámetros (c, theta) se calibran por búsqueda en grilla maximizando el CSI diario
contra los cierres observados (matriz del colega).

Contraste estadístico clásico: regresión logística diaria
    logit P(C_d = 1) = b0 + b1·S_d + b2·Z_d + b3·R_d + b4·C_{d-1}
ajustada por máxima verosimilitud (scipy), con C_{d-1} como término de persistencia.

Entradas: salidas/era5_tramos_6h.csv, salidas/estado_caminos_6h.csv (agregar_bloques_6h.py)
Salidas : salidas/consolidado_6h.csv / .xlsx (base definitiva por bloque de 6 h)
          salidas/modelo_cierre_diario.csv, _episodios.csv, _metricas.csv,
          salidas/modelo_cierre_parametros.json
"""
import os, json, itertools, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
SAL = BASE + "/salidas"
TZ = -4
RHO = 100.0            # kg/m3 nieve fresca (razón 10:1); a = 100/RHO cm por mm SWE
A_CM_MM = 100.0 / RHO
R2 = 1.0               # mm/12 h: umbral de "presencia de precipitación líquida" (nivel 2)
TRAMO_OPERATIVO = "alto"   # el estado observado es de toda la ruta; se compara con el tramo alto
BLOQUE_H = 6               # horas por bloque
ESTADOS = ["abierto", "restringido", "cierre_tecnico", "cerrado_meteo", "cerrado_horario"]

era = pd.read_csv(SAL + "/era5_tramos_6h.csv", parse_dates=["bloque_inicio_local", "bloque_fin_local", "bloque_inicio_utc"])
est = pd.read_csv(SAL + "/estado_caminos_6h.csv", parse_dates=["bloque_inicio_local"])


# ------------------------------------------------------------------------------------
# 1. niveles del protocolo, bloque a bloque
# ------------------------------------------------------------------------------------
def nivel_protocolo(S, R, Z):
    """Cuadro literal: máximo de los gatillantes satisfechos (NaN -> 0)."""
    S = np.nan_to_num(S, nan=0.0); R = np.nan_to_num(R, nan=0.0); Z = np.nan_to_num(Z, nan=np.inf)
    g1 = (S > 1) & (S < 25)
    g2 = ((S >= 25) & (S < 50) & (Z >= 1500) & (Z <= 2800)) | (R >= R2)
    g3 = ((S > 1) & (S < 50) & (Z >= 900) & (Z <= 1500)) | ((S >= 50) & (Z > 1500) & (Z <= 2800)) | ((R >= 20) & (Z > 2800))
    return np.select([g3, g2, g1], [3, 2, 1], default=0)


def nivel_regularizado(S, R, Z):
    """Misma tabla, completada por bandas de isoterma para que sea monótona en S y R."""
    S = np.nan_to_num(S, nan=0.0); R = np.nan_to_num(R, nan=0.0); Z = np.nan_to_num(Z, nan=np.inf)
    baja, alta = Z < 1500, Z > 2800
    media = ~baja & ~alta
    l_baja = np.where(S > 1, 3, 0)
    l_media = np.select([S >= 50, S >= 25, S > 1], [3, 2, 1], default=0)
    l_alta = np.maximum.reduce([np.where(S > 1, 1, 0), np.where(R >= R2, 2, 0), np.where(R >= 20, 3, 0)])
    return np.select([baja, media, alta], [l_baja, l_media, l_alta], default=0)


era = era.sort_values(["ruta", "tramo", "bloque_inicio_local"]).reset_index(drop=True)
Z = era.isoterma_12h_media.values
era["nivel_protocolo"] = nivel_protocolo(era.nieve_12h_cm.values, era.lluvia_12h_mm.values, Z)
era["nivel_regularizado"] = nivel_regularizado(era.nieve_12h_cm.values, era.lluvia_12h_mm.values, Z)
era["banda_isoterma"] = np.select([Z < 1500, Z > 2800], ["baja (<1500)", "alta (>2800)"], default="media (1500-2800)")
era.loc[era.isoterma_12h_media.isna(), "banda_isoterma"] = ""

# ------------------------------------------------------------------------------------
# 2. base definitiva por bloque: ERA5 por tramo + estado observado de la ruta
# ------------------------------------------------------------------------------------
est_cols = ["ruta", "bloque_inicio_local", "estado", "regimen", "nivel", "cerrado", "transitable_todo_tipo",
            "id_registro", "fuente_estado", "causa"] + ["horas_" + e for e in ESTADOS]
est_cols = [c for c in est_cols if c in est.columns]
estm = est[est_cols].rename(columns={"estado": "estado_observado", "regimen": "regimen_observado",
                                     "nivel": "nivel_observado", "cerrado": "cerrado_observado",
                                     "id_registro": "id_registro_matriz", "fuente_estado": "fuente_estado_observado",
                                     "causa": "causa_observada", "horas_cerrado_meteo": "horas_cerrado_obs",
                                     **{"horas_" + e: "horas_" + e + "_obs" for e in ESTADOS if e != "cerrado_meteo"}})
hor = era.merge(estm, on=["ruta", "bloque_inicio_local"], how="left")
hor["cerrado_observado"] = hor.cerrado_observado.eq(True)
hor["fecha_local"] = hor.bloque_inicio_local.dt.date

# ------------------------------------------------------------------------------------
# 3. tabla diaria (día local) por ruta y tramo
# ------------------------------------------------------------------------------------
def agg_diario(df):
    return pd.Series(dict(
        t2m_media=df.t2m_C.mean(), t2m_min=df.t2m_C.min(), t2m_max=df.t2m_C.max(),
        horas_bajo_cero=int(df.horas_bajo_cero.sum()),
        nieve_dia_cm=df.sf_6h_mm.sum() * A_CM_MM, lluvia_dia_mm=df.lluvia_6h_mm.sum(),
        S_max12_cm=df.nieve_12h_cm.max(), R_max12_mm=df.lluvia_12h_mm.max(),
        Z_media=df.isoterma_msnm.mean(), Z_min=df.isoterma_min_msnm.min(), Z_max=df.isoterma_max_msnm.max(),
        sde_fin_m=df.sde_m.iloc[-1], dsde_dia_cm=(df.sde_m.iloc[-1] - df.sde_m.iloc[0]) * 100,
        viento_max_ms=df.viento_max_ms.max(), horas_viento_fuerte=int(df.horas_viento_fuerte.sum()),
        L_protocolo=int(df.nivel_protocolo.max()), L_regularizado=int(df.nivel_regularizado.max()),
        bloques_L3=int((df.nivel_regularizado == 3).sum()),
        horas_cerrado_obs=int(df.horas_cerrado_obs.sum()),
        horas_restringido_obs=int(df.horas_restringido_obs.sum()),
        bloques_cerrado_obs=int(df.cerrado_observado.sum()),
        cerrado_obs=bool(df.cerrado_observado.any()),
        cerrado_obs_dia_completo=bool(df.horas_cerrado_obs.sum() >= 24),
        estado_obs_dominante=df.estado_observado.mode().iloc[0] if df.estado_observado.notna().any() else "",
    ))


dia = hor.groupby(["ruta", "tramo", "fecha_local"]).apply(agg_diario, include_groups=False).reset_index()
dia["mes"] = pd.to_datetime(dia.fecha_local).dt.strftime("%Y-%m")
dia = dia[(pd.to_datetime(dia.fecha_local) >= "2026-07-01") & (pd.to_datetime(dia.fecha_local) <= "2026-08-31")]   # días locales completos del periodo
dia = dia.sort_values(["ruta", "tramo", "fecha_local"]).reset_index(drop=True)
dia["cerrado_obs_ayer"] = dia.groupby(["ruta", "tramo"]).cerrado_obs.shift(1).fillna(False).astype(bool)


# ------------------------------------------------------------------------------------
# 4. métricas de verificación (diarias, binarias)
# ------------------------------------------------------------------------------------
def metricas(obs, pred):
    obs = np.asarray(obs, bool); pred = np.asarray(pred, bool)
    a = int((obs & pred).sum()); b = int((~obs & pred).sum()); c = int((obs & ~pred).sum()); d = int((~obs & ~pred).sum())
    n = a + b + c + d
    pod = a / (a + c) if a + c else np.nan          # probabilidad de detección (sensibilidad)
    far = b / (a + b) if a + b else np.nan          # razón de falsas alarmas
    csi = a / (a + b + c) if a + b + c else np.nan  # índice de éxito crítico
    acc = (a + d) / n if n else np.nan
    pofd = b / (b + d) if b + d else np.nan
    hss_den = ((a + c) * (c + d) + (a + b) * (b + d))
    hss = 2 * (a * d - b * c) / hss_den if hss_den else np.nan
    return dict(aciertos=a, falsas_alarmas=b, omisiones=c, negativos_correctos=d, n=n,
                POD=pod, FAR=far, CSI=csi, exactitud=acc, POFD=pofd, HSS=hss)


filas_m = []
for (ruta, tramo), d in dia.groupby(["ruta", "tramo"]):
    obs = d.cerrado_obs.values
    filas_m.append(dict(modelo="protocolo literal (L=3)", ruta=ruta, tramo=tramo, **metricas(obs, d.L_protocolo >= 3)))
    filas_m.append(dict(modelo="protocolo literal (L>=2)", ruta=ruta, tramo=tramo, **metricas(obs, d.L_protocolo >= 2)))
    filas_m.append(dict(modelo="regularizado (L*=3)", ruta=ruta, tramo=tramo, **metricas(obs, d.L_regularizado >= 3)))
    filas_m.append(dict(modelo="regularizado (L*>=2)", ruta=ruta, tramo=tramo, **metricas(obs, d.L_regularizado >= 2)))
    filas_m.append(dict(modelo="persistencia trivial (C_d = C_d-1)", ruta=ruta, tramo=tramo, **metricas(obs, d.cerrado_obs_ayer)))


# ------------------------------------------------------------------------------------
# 5. modelo con persistencia: balance de nieve por despejar (calibrado)
# ------------------------------------------------------------------------------------
def simular_persistencia(df, s_cierre, c_despeje, theta, usar_nivel=True):
    """Devuelve la serie por bloque cerrado(t) para un tramo.
    Cierra cuando L*(t)=3 (o S >= s_cierre si usar_nivel=False) y se mantiene cerrado
    mientras la nieve por despejar N(t) > theta.  N(t) = max(0, N(t-1) + a sf(t) - c·Δ), Δ = 6 h."""
    sf = np.nan_to_num(df.sf_6h_mm.values) * A_CM_MM
    S = np.nan_to_num(df.nieve_12h_cm.values)
    L = df.nivel_regularizado.values
    N = 0.0; cerrado = False
    out = np.zeros(len(df), bool)
    for k in range(len(df)):
        N = max(0.0, N + sf[k] - c_despeje * BLOQUE_H)
        gatillo = (L[k] == 3) if usar_nivel else (S[k] >= s_cierre)
        if gatillo:
            cerrado = True
        elif cerrado and N <= theta:
            cerrado = False
        out[k] = cerrado
    return out


def diario_desde_horario(df, cerrado_h):
    tmp = pd.DataFrame({"fecha_local": df.fecha_local.values, "c": cerrado_h})
    return tmp.groupby("fecha_local").c.any()


GRILLA_C = [0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]      # cm/h de despeje neto
GRILLA_TH = [0, 5, 10, 20, 30, 50, 80]                               # cm que pueden quedar para reabrir
GRILLA_S = [10, 15, 20, 25, 30, 40, 50]                              # cm/12 h para la variante por umbral
param = {}
for (ruta, tramo), df in hor.groupby(["ruta", "tramo"]):
    df = df.reset_index(drop=True)
    obs = dia[(dia.ruta == ruta) & (dia.tramo == tramo)].set_index("fecha_local").cerrado_obs
    mejor = None
    for c, th in itertools.product(GRILLA_C, GRILLA_TH):
        pred = diario_desde_horario(df, simular_persistencia(df, None, c, th, usar_nivel=True)).reindex(obs.index).fillna(False)
        m = metricas(obs.values, pred.values)
        if mejor is None or (m["CSI"], m["HSS"]) > (mejor[0]["CSI"], mejor[0]["HSS"]):
            mejor = (m, dict(c_despeje_cm_h=c, theta_cm=th))
    filas_m.append(dict(modelo="regularizado + persistencia (calibrado)", ruta=ruta, tramo=tramo, **mejor[0]))
    param[f"{ruta}|{tramo}|nivel+persistencia"] = mejor[1] | {k: (round(v, 3) if isinstance(v, float) else v) for k, v in mejor[0].items()}
    mejor2 = None
    for s, c, th in itertools.product(GRILLA_S, GRILLA_C, GRILLA_TH):
        pred = diario_desde_horario(df, simular_persistencia(df, s, c, th, usar_nivel=False)).reindex(obs.index).fillna(False)
        m = metricas(obs.values, pred.values)
        if mejor2 is None or (m["CSI"], m["HSS"]) > (mejor2[0]["CSI"], mejor2[0]["HSS"]):
            mejor2 = (m, dict(s_cierre_cm_12h=s, c_despeje_cm_h=c, theta_cm=th))
    filas_m.append(dict(modelo="umbral de nieve + persistencia (calibrado)", ruta=ruta, tramo=tramo, **mejor2[0]))
    param[f"{ruta}|{tramo}|umbral+persistencia"] = mejor2[1] | {k: (round(v, 3) if isinstance(v, float) else v) for k, v in mejor2[0].items()}
    # series por bloque del modelo calibrado, para la base y el visor
    p1 = mejor[1]; p2 = mejor2[1]
    hor.loc[(hor.ruta == ruta) & (hor.tramo == tramo), "cerrado_modelo_persistencia"] = simular_persistencia(df, None, p1["c_despeje_cm_h"], p1["theta_cm"], True)
    hor.loc[(hor.ruta == ruta) & (hor.tramo == tramo), "cerrado_modelo_umbral"] = simular_persistencia(df, p2["s_cierre_cm_12h"], p2["c_despeje_cm_h"], p2["theta_cm"], False)

hor["cerrado_modelo_persistencia"] = hor.cerrado_modelo_persistencia.astype(bool)
hor["cerrado_modelo_umbral"] = hor.cerrado_modelo_umbral.astype(bool)
for col, dst in [("cerrado_modelo_persistencia", "cerrado_mod_persistencia"), ("cerrado_modelo_umbral", "cerrado_mod_umbral")]:
    dd = hor.groupby(["ruta", "tramo", "fecha_local"])[col].any().rename(dst).reset_index()
    dia = dia.merge(dd, on=["ruta", "tramo", "fecha_local"], how="left")


# ------------------------------------------------------------------------------------
# 6. regresión logística diaria (tramo operativo, ambas rutas, con persistencia)
# ------------------------------------------------------------------------------------
def ajustar_logit(X, y):
    X1 = np.column_stack([np.ones(len(X)), X])
    def nll(b):
        z = X1 @ b
        return np.sum(np.logaddexp(0, z) - y * z) + 1e-3 * np.sum(b[1:] ** 2)   # leve ridge: separación casi perfecta
    r = minimize(nll, np.zeros(X1.shape[1]), method="BFGS")
    p = 1 / (1 + np.exp(-(X1 @ r.x)))
    return r.x, p


def auc(y, p):
    y = np.asarray(y, bool); order = np.argsort(p)
    ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    n1, n0 = y.sum(), (~y).sum()
    return (ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan


dop = dia[dia.tramo == TRAMO_OPERATIVO].copy()
dop["Z_media_f"] = dop.Z_media.fillna(dop.Z_media.mean())
Xcols = ["S_max12_cm", "Z_media_f", "R_max12_mm", "cerrado_obs_ayer"]
X = dop[Xcols].astype(float)
X = X.fillna(X.mean()).values
esc = X.std(axis=0); esc[esc == 0] = 1; mu = X.mean(axis=0)
Xs = (X - mu) / esc
y = dop.cerrado_obs.values.astype(float)
beta_s, p = ajustar_logit(Xs, y)
beta = np.concatenate([[beta_s[0] - np.sum(beta_s[1:] * mu / esc)], beta_s[1:] / esc])   # en unidades originales
dop["p_logit"] = p
logit_res = dict(variables=["intercepto"] + Xcols, coeficientes=[round(float(b), 5) for b in beta],
                 coeficientes_estandarizados=[round(float(b), 3) for b in beta_s],
                 AUC=round(float(auc(y, p)), 3), positivos=int(y.sum()),
                 **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in metricas(y, p >= 0.5).items()})
# sin persistencia (solo meteorología), para ver cuánto explica el clima por sí solo
beta2_s, p2 = ajustar_logit(Xs[:, :3], y)
logit_res_meteo = dict(variables=["intercepto"] + Xcols[:3], coeficientes_estandarizados=[round(float(b), 3) for b in beta2_s],
                       AUC=round(float(auc(y, p2)), 3), **{k: (round(v, 3) if isinstance(v, float) else v) for k, v in metricas(y, p2 >= 0.5).items()})
dop["p_logit_meteo"] = p2
filas_m.append(dict(modelo="logística diaria S,Z,R + C(d-1)", ruta="ambas", tramo=TRAMO_OPERATIVO, **metricas(y, p >= 0.5)))
filas_m.append(dict(modelo="logística diaria S,Z,R (sin persistencia)", ruta="ambas", tramo=TRAMO_OPERATIVO, **metricas(y, p2 >= 0.5)))
dia = dia.merge(dop[["ruta", "tramo", "fecha_local", "p_logit", "p_logit_meteo"]], on=["ruta", "tramo", "fecha_local"], how="left")


# ------------------------------------------------------------------------------------
# 7. episodios observados de cierre y anticipación del modelo
# ------------------------------------------------------------------------------------
# Los episodios se identifican en la serie horaria del estado observado (corridas de horas
# cerrado_meteo), para no fusionar cierres separados por pocas horas; luego se cruzan con los
# bloques que contienen su primera y última hora. 72 h = 12 bloques, 24 h = 4 bloques.
B72, B24 = 72 // BLOQUE_H, 24 // BLOQUE_H
est_h = pd.read_csv(SAL + "/estado_caminos_horario.csv", parse_dates=["fecha_hora_local"])
episodios = []
for ruta, df in hor[hor.tramo == TRAMO_OPERATIVO].groupby("ruta"):
    df = df.sort_values("bloque_inicio_local").reset_index(drop=True)
    eh = est_h[est_h.ruta == ruta].sort_values("fecha_hora_local").reset_index(drop=True)
    c = eh.estado.eq("cerrado_meteo").values
    ini = np.where(c & ~np.r_[False, c[:-1]])[0]; fin = np.where(c & ~np.r_[c[1:], False])[0]
    for i0, i1 in zip(ini, fin):
        h0, h1 = eh.fecha_hora_local[i0], eh.fecha_hora_local[i1]
        a = int(np.searchsorted(df.bloque_inicio_local.values, np.datetime64(h0.floor(f"{BLOQUE_H}h"))))
        b = int(np.searchsorted(df.bloque_inicio_local.values, np.datetime64(h1.floor(f"{BLOQUE_H}h"))))
        t0 = df.bloque_inicio_local[a]
        ventana = df.iloc[max(0, a - B72):b + 1]
        l3 = ventana[ventana.nivel_regularizado == 3]
        primer_l3 = l3.bloque_inicio_local.min() if len(l3) else pd.NaT
        # anticipación del modelo calibrado (umbral + persistencia): solo si estaba abierto en algún bloque
        # de las 72 h previas; si venía cerrado desde antes no anticipa nada (queda NaT)
        previa = ventana[ventana.bloque_inicio_local < t0]
        pm = ventana[ventana.cerrado_modelo_umbral]
        primer_pm = pm.bloque_inicio_local.min() if len(pm) and (~previa.cerrado_modelo_umbral).any() else pd.NaT
        modelo_ya_cerrado = bool(len(previa)) and bool(previa.cerrado_modelo_umbral.iloc[0])
        ids = eh.id_registro[i0:i1 + 1].dropna().astype(str).str.split(";").explode().str.strip()
        causa = eh.causa[i0:i1 + 1].dropna()
        episodios.append(dict(
            ruta=ruta, inicio_local=h0, fin_local=h1, horas=int(i1 - i0 + 1), dias=round((i1 - i0 + 1) / 24, 1),
            bloque_inicio=t0, bloque_fin=df.bloque_inicio_local[b], bloques=int(b - a + 1),
            nieve_en_episodio_cm=round(df.sf_6h_mm[a:b + 1].sum() * A_CM_MM, 1),
            nieve_72h_previas_cm=round(df.sf_6h_mm[max(0, a - B72):a].sum() * A_CM_MM, 1),
            S_max12_cm=round(df.nieve_12h_cm[max(0, a - B24):b + 1].max(), 1),
            Z_min_msnm=df.isoterma_min_msnm[max(0, a - B24):b + 1].min(),
            L_max_protocolo=int(df.nivel_protocolo[max(0, a - B24):b + 1].max()),
            L_max_regularizado=int(df.nivel_regularizado[max(0, a - B24):b + 1].max()),
            primer_L3_regularizado=primer_l3,
            anticipacion_L3_h=(h0 - primer_l3) / pd.Timedelta(hours=1) if pd.notna(primer_l3) else np.nan,
            primer_cierre_modelo_calibrado=primer_pm,
            anticipacion_modelo_h=(h0 - primer_pm) / pd.Timedelta(hours=1) if pd.notna(primer_pm) else np.nan,
            modelo_ya_cerrado_al_inicio=modelo_ya_cerrado,
            bloques_modelo_cerrado_en_episodio=int(df.cerrado_modelo_umbral[a:b + 1].sum()),
            causa_matriz=causa.iloc[0] if len(causa) else "",
            ids_matriz=";".join(dict.fromkeys(ids)),
        ))
episodios = pd.DataFrame(episodios)

# ------------------------------------------------------------------------------------
# 8. salidas
# ------------------------------------------------------------------------------------
met = pd.DataFrame(filas_m).round(3)
dia = dia.round(2)
cols = ["ruta", "tramo", "bloque_inicio_local", "bloque_fin_local", "bloque_inicio_utc", "fecha_local", "bloque_dia", "bloque", "mes",
        "n_horas", "n_horas_flujo",
        "t2m_C", "t2m_min_C", "t2m_max_C", "tsn_C", "viento_ms", "viento_max_ms", "viento_dir_deg",
        "tp_6h_mm", "sf_6h_mm", "nieve_6h_cm", "lluvia_6h_mm", "smlt_6h_mm", "es_6h_mm",
        "sde_m", "snowc_pct", "rsn_kgm3", "isoterma_msnm", "isoterma_min_msnm", "isoterma_max_msnm", "isoterma_censurada",
        "sf_12h_mm", "nieve_12h_cm", "nieve_24h_cm", "lluvia_12h_mm", "tp_12h_mm", "dsde_12h_cm",
        "isoterma_12h_media", "isoterma_12h_min", "banda_isoterma",
        "nivel_protocolo", "nivel_regularizado", "cerrado_modelo_persistencia", "cerrado_modelo_umbral",
        "estado_observado", "cerrado_observado", "horas_cerrado_obs"] + ["horas_" + e + "_obs" for e in ESTADOS if e != "cerrado_meteo"] + [
        "regimen_observado", "nivel_observado", "transitable_todo_tipo",
        "id_registro_matriz", "fuente_estado_observado", "causa_observada",
        "horas_bajo_cero", "horas_nevando", "horas_nieve_intensa", "horas_lloviendo", "horas_viento_fuerte", "n_celdas_validas"]
cols = [c for c in cols if c in hor.columns]
hor = hor[cols]
hor.to_csv(SAL + "/consolidado_6h.csv", index=False)
dia.to_csv(SAL + "/modelo_cierre_diario.csv", index=False)
met.to_csv(SAL + "/modelo_cierre_metricas.csv", index=False)
episodios.to_csv(SAL + "/modelo_cierre_episodios.csv", index=False)
with open(SAL + "/modelo_cierre_parametros.json", "w", encoding="utf-8") as f:
    json.dump(dict(resolucion_h=BLOQUE_H, rho_nieve_fresca_kg_m3=RHO, a_cm_por_mm_swe=A_CM_MM, ventana_h=12, r2_mm=R2,
                   tramo_operativo=TRAMO_OPERATIVO, persistencia=param,
                   logistica=logit_res, logistica_solo_meteo=logit_res_meteo), f, ensure_ascii=False, indent=2, default=str)

meta = pd.read_csv(SAL + "/era5_tramos_meta.csv")
dic = pd.DataFrame([
    ("ruta / tramo", "60-CH alto = Guardia Vieja-túnel (recorte ERA5 'Tramo Alto'); 60-CH medio = Río Blanco-Guardia Vieja; G-21 alto = Farellones y accesos a centros (G-21-2..4, G-249, G-251); G-21 medio = subida de curvas (G-21-1-13). Ver hoja Tramos."),
    ("bloque_inicio_local / bloque_fin_local / bloque", "Bloque de 6 h en hora local (UTC-4): 00-06, 06-12, 12-18 o 18-24. bloque_dia = 0..3. bloque_inicio_utc = inicio en UTC."),
    ("n_horas / n_horas_flujo", "Horas ERA5 con dato en el bloque (instantáneas y acumuladas). Los bloques del borde de la serie pueden tener menos de 6."),
    ("asignación de horas", "Las acumuladas de ERA5 rotuladas t (lo caído en t-1..t) van al bloque que contiene t-1 h, así el bloque 00-06 suma lo caído entre 00:00 y 06:00. Las instantáneas y el estado observado van al bloque que contiene t."),
    ("t2m_C / t2m_min_C / t2m_max_C / tsn_C", "ERA5-Land: temperatura del aire a 2 m (media, mínima y máxima horaria del bloque) y de la capa de nieve (media), °C. Promedio de celdas ponderado por longitud de camino."),
    ("viento_ms / viento_max_ms / viento_dir_deg", "Viento a 10 m: rapidez media y máxima horaria del bloque; dirección (de donde sopla) del vector medio."),
    ("tp_6h_mm / sf_6h_mm / lluvia_6h_mm", "Precipitación total, nieve caída y lluvia (tp - sf) del bloque, mm de agua equivalente. nieve_6h_cm = sf_6h_mm × 100/ρ."),
    ("smlt_6h_mm / es_6h_mm", "Derretimiento y evaporación del manto en el bloque, mm."),
    ("sde_m / snowc_pct / rsn_kgm3", "Espesor del manto al final del bloque (m), fracción cubierta (%) y densidad del manto (kg/m3), medias del bloque."),
    ("isoterma_msnm / _min / _max", "Altura de la isoterma 0 °C (ERA5 deg0l + cota DEM de la celda), media, mínima y máxima horaria del bloque, celdas de menor orografía de la ruta. isoterma_censurada = alguna hora con toda la columna bajo 0 °C."),
    ("nieve_12h_cm", "Nieve caída en las 12 h que terminan con el bloque (este bloque + el anterior), en cm: sf_12h_mm × 100/ρ con ρ = 100 kg/m3 (10:1). nieve_24h_cm = 4 bloques. dsde_12h_cm es el cambio de espesor del manto en 12 h (incluye compactación)."),
    ("lluvia_12h_mm / tp_12h_mm", "Lluvia y precipitación total acumuladas en 12 h (2 bloques)."),
    ("isoterma_12h_media / _min", "Media y mínimo horario de la isoterma en la ventana de 12 h (2 bloques)."),
    ("nivel_protocolo", "Nivel de alerta 0-3 del bloque aplicando literalmente el cuadro de gatillantes (solo nieve, isoterma y lluvia)."),
    ("nivel_regularizado", "Nivel 0-3 con la tabla completada por banda de isoterma (monótona)."),
    ("cerrado_modelo_persistencia", "Cierre simulado: gatilla con nivel 3 y persiste mientras la nieve por despejar supere theta (parámetros calibrados por ruta y tramo, ver modelo_cierre_parametros.json). El balance descuenta c × 6 h por bloque."),
    ("cerrado_modelo_umbral", "Idem con gatillo por umbral de nieve en 12 h calibrado."),
    ("estado_observado", "Estado de la ruta en el bloque según las matrices del colega: cerrado_meteo si hubo al menos una hora cerrada por meteorología; si no, el estado con más horas (abierto, restringido, cierre_tecnico, cerrado_horario)."),
    ("cerrado_observado / horas_*_obs", "cerrado_observado = al menos una hora cerrada por meteorología en el bloque. horas_cerrado_obs, horas_abierto_obs, etc.: horas del bloque en cada estado."),
    ("fuente_estado_observado", "matriz (registro explícito), regimen_estructural (resolución vigente) o imputado_sin_registro (régimen normal asumido)."),
    ("horas_bajo_cero / horas_nevando / ...", "Horas del bloque con t2m < 0 °C, con nieve > 0,1 mm/h, > 1 mm/h, con lluvia > 0,1 mm/h y con viento > 10 m/s."),
], columns=["campo", "definicion"])

with pd.ExcelWriter(SAL + "/consolidado_6h.xlsx", engine="openpyxl") as w:
    for (r, t), d in hor.groupby(["ruta", "tramo"]):
        d.to_excel(w, sheet_name=f"{r} {t}", index=False)
    dia.to_excel(w, sheet_name="Diario", index=False)
    episodios.to_excel(w, sheet_name="Episodios cierre", index=False)
    met.to_excel(w, sheet_name="Metricas modelo", index=False)
    meta.to_excel(w, sheet_name="Tramos", index=False)
    dic.to_excel(w, sheet_name="Diccionario", index=False)

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
print("bloques 6 h:", hor.shape, "| diario:", dia.shape)
print("\nbloques por nivel (regularizado) y estado observado, tramo alto:")
print(pd.crosstab([hor[hor.tramo == "alto"].ruta, hor[hor.tramo == "alto"].nivel_regularizado], hor[hor.tramo == "alto"].estado_observado))
print("\nMÉTRICAS DIARIAS (cerrado_meteo observado vs. modelo):")
print(met[["modelo", "ruta", "tramo", "aciertos", "falsas_alarmas", "omisiones", "negativos_correctos", "POD", "FAR", "CSI", "HSS"]].to_string(index=False))
print("\nPARÁMETROS CALIBRADOS:"); print(json.dumps(param, indent=1, ensure_ascii=False))
print("\nLOGÍSTICA:", json.dumps(logit_res, ensure_ascii=False)); print("LOGÍSTICA solo meteo:", json.dumps(logit_res_meteo, ensure_ascii=False))
print("\nEPISODIOS DE CIERRE OBSERVADOS:")
print(episodios.to_string(index=False))
