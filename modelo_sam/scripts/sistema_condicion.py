# -*- coding: utf-8 -*-
r"""Sistema de condición invernal para caminos de alta montaña (propuesta, oct 2026).

Cuatro piezas por tramo k y bloque de 6 h t:
  1. Índice de severidad andino  SV  (notas 0-5 por variable, tipo Walker, + veto del protocolo)
  2. Índice de peligro            H   (avalancha y remoción en masa, separado)
  3. Balance de despeje           N   (nieve por despejar, capacidad c, arrastre por viento)
  4. Máquina de estados           E0..E5 (abierto, restricción, cierre parcial, cierre técnico/despeje,
                                  cierre total por tormenta, cierre por peligro)
La capa administrativa (cierre por horario, binacional, sanitaria, tránsito) es exógena: los
bloques observados "cerrado_horario" se excluyen de la verificación.

Calibración: (c, theta) se ajustan SOLO con la G-21 (ruta con protocolo municipal funcionando) y
se transfieren a la 60-CH, para no meter en la física la decisión binacional que queremos evaluar.
Contrafactual: estado que el modelo considera justificado en cada bloque de los cierres de la 60-CH.

Entradas: salidas/era5_tramos_6h.csv, salidas/era5_rafagas_6h.csv (era5_rafagas.py),
          salidas/estado_caminos_6h.csv, salidas/geometria/pesos_celdas_era5land.csv
Salidas : salidas/sistema/  (bloques, metricas, contrafactual, parametros, figuras)
"""
import os, json, itertools, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
SAL = BASE + "/salidas"
OUT = SAL + "/sistema"
os.makedirs(OUT, exist_ok=True)
DT = 6.0  # horas por bloque

# ----------------------------------------------------------------------------------------
# Parámetros de la propuesta (los marcados "supuesto" se prueban en la sensibilidad)
# ----------------------------------------------------------------------------------------
P = dict(
    delta_nieve_m=300,          # supuesto: la nieve llega ~300 m bajo la isoterma 0 °C
    cortes=dict(                # notas 0-5: nota = número de cortes superados (>=)
        S=[0.5, 5, 12.5, 20, 25],       # nieve efectiva en 6 h, cm (anclas 1/25/50 cm en 12 h del protocolo, a la mitad)
        r=[0.5, 1, 2, 3, 4],            # tasa de nevada efectiva, cm por hora con nieve
        dur=[1, 6, 12, 18, 23],         # horas con nieve en 24 h
        G=[10, 15, 20, 25, 30],         # ráfaga máxima del bloque, m/s
        phi=[0.05, 0.25, 0.5, 0.75, 0.95],  # fracción del tramo bajo nieve
        R=[0.5, 2.5, 5, 10, 15],        # lluvia en 6 h sobre manto (>= 10 cm), mm (cortes de 12 h a la mitad)
        HN72=[10, 20, 30, 50, 80],      # nieve nueva 72 h en zonas de partida (celda), cm
        R72=[10, 20, 40, 60, 100],      # lluvia 72 h con isoterma sobre la cota media, mm
    ),
    beta=dict(S=0.45, phi=0.15, r=0.10, dur=0.10, G=0.10, R=0.10),   # pesos tipo Walker (suman 1)
    veto={0: 0, 1: 1, 2: 3, 3: 4},     # nivel del protocolo -> piso del índice
    umbral_E=dict(restriccion=1.0, parcial=2.5, cierre=3.5),   # niveles de la severidad
    H_umbral=4,                 # H >= H*: cierre por peligro y cuadrillas fuera (u = 0); se calibra
    # v3: cada índice tiene tres niveles (restricción, cierre parcial, cierre); None = sin ese nivel.
        H_niveles=dict(E1=3, E2=4), # criterio: la G-21 no tiene registros de restricción para calibrarlos
    N_parcial=30,               # nieve por despejar (cm) que lleva a cierre parcial (criterio)
    despeje_tras_cierre=True,   # el cierre por despeje (E3) exige que la ruta viniera cerrada
    hn_min_sobrecarga=30,       # cm de nieve nueva en 72 h para que cuenten calentamiento, lluvia o arrastre
    exposicion=dict(alto=1.0, medio=0.5),   # supuesto: exposición a avalanchas por tramo
    li_pomeroy=(9.43, 0.18, 0.0033),        # Ut(10) = a + bT + cT^2 (Li y Pomeroy 1997, p. 211)
    factor_rafaga=1.6,          # supuesto: ráfaga / viento medio en terreno complejo
    arrastre_frac=0.10,         # supuesto: fracción de la nieve 72 h redepositada por bloque con arrastre
    theta1_cm=5,                # nieve en calzada que ya exige restricción (cadenas)
    evento_cm=0.5,              # nieve en 6 h que define un evento de nieve (1 cm en 12 h, a la mitad)
    R2_mm=1.0,                  # "presencia de precipitación líquida" (como en modelo_cierre.py)
)

# ----------------------------------------------------------------------------------------
# Datos
# ----------------------------------------------------------------------------------------
era = pd.read_csv(SAL + "/era5_tramos_6h.csv", parse_dates=["bloque_inicio_local"])
raf = pd.read_csv(SAL + "/era5_rafagas_6h.csv", parse_dates=["bloque_inicio_local"])
est = pd.read_csv(SAL + "/estado_caminos_6h.csv", parse_dates=["bloque_inicio_local"])
pesos = pd.read_csv(SAL + "/geometria/pesos_celdas_era5land.csv")
era = era.merge(raf, on=["ruta", "tramo", "bloque_inicio_local"], how="left")
# El cuadro del protocolo se aplica de forma continua: nivel del bloque = máximo del nivel horario
# (ventana móvil de 12 h) dentro del bloque. Las horas se asignan al bloque como los flujos (t - 1 h).
hor = pd.read_csv(SAL + "/consolidado_horario.csv", usecols=["ruta", "tramo", "fecha_hora_local", "nivel_regularizado"],
                  parse_dates=["fecha_hora_local"])
hor["bloque_inicio_local"] = (hor.fecha_hora_local - pd.Timedelta(hours=1)).dt.floor("6h")
era = era.merge(hor.groupby(["ruta", "tramo", "bloque_inicio_local"]).nivel_regularizado.max().rename("L_horario").reset_index(),
                on=["ruta", "tramo", "bloque_inicio_local"], how="left")
era = era.sort_values(["ruta", "tramo", "bloque_inicio_local"]).reset_index(drop=True)


def nivel_regularizado(S, R, Z, r2):
    """Cuadro del protocolo completado por bandas de isoterma (idéntico a modelo_cierre.py)."""
    S = np.nan_to_num(S); R = np.nan_to_num(R); Z = np.nan_to_num(Z, nan=np.inf)
    baja, alta = Z < 1500, Z > 2800
    l_baja = np.where(S > 1, 3, 0)
    l_media = np.select([S >= 50, S >= 25, S > 1], [3, 2, 1], default=0)
    l_alta = np.maximum.reduce([np.where(S > 1, 1, 0), np.where(R >= r2, 2, 0), np.where(R >= 20, 3, 0)])
    return np.select([baja, alta], [l_baja, l_alta], default=l_media)


def fraccion_bajo_nieve(Z, ruta, tramo, delta):
    """phi = fracción del largo del tramo con cota > Z - delta.
    Dentro de cada celda se supone la cota del camino repartida uniforme entre su mínimo y máximo."""
    p = pesos[(pesos.ruta == ruta) & (pesos.tramo == tramo)]
    Z = np.nan_to_num(np.asarray(Z, float), nan=9999.0) - delta
    tot = p.longitud_m.sum()
    phi = np.zeros(len(Z))
    for r in p.itertuples():
        rango = max(r.cota_camino_max - r.cota_camino_min, 1)
        phi += r.longitud_m / tot * np.clip((r.cota_camino_max - Z) / rango, 0, 1)
    return phi


def nota(x, cortes):
    x = np.nan_to_num(np.asarray(x, float))
    return np.sum([x >= c for c in cortes], axis=0).astype(float)


def rolling(x, n):
    return pd.Series(x).rolling(n, min_periods=1).sum().values


# ----------------------------------------------------------------------------------------
# Piezas 1 y 2: variables, notas, severidad y peligro (no dependen de c ni theta)
# ----------------------------------------------------------------------------------------
def construir_base(P):
  partes = []
  for (ruta, tramo), d in era.groupby(["ruta", "tramo"]):
      d = d.reset_index(drop=True).copy()
      C = P["cortes"]
      d["phi12"] = fraccion_bajo_nieve(d.isoterma_12h_media, ruta, tramo, P["delta_nieve_m"])
      d["phi6"] = fraccion_bajo_nieve(d.isoterma_msnm, ruta, tramo, P["delta_nieve_m"])
      d["S12_ef"] = d.nieve_12h_cm.fillna(0) * d.phi12              # nieve efectiva sobre el camino, 12 h
      d["S6_ef"] = d.nieve_6h_cm.fillna(0) * d.phi6
      # severidad en el bloque de 6 h (oct 2026); el piso del protocolo sigue en 12 h, como lo define el protocolo
      d["tasa_ef"] = d.S6_ef / np.maximum(d.horas_nevando.fillna(0), 1)
      d["dur24"] = rolling(d.horas_nevando.fillna(0).values, 4)
      d["R6_manto"] = np.where(d.sde_m.fillna(0) >= 0.10, d.lluvia_6h_mm.fillna(0), 0)
      d["HN72"] = rolling(d.nieve_6h_cm.fillna(0).values, 12)       # en la celda: zonas de partida altas
      d["HN72_ef"] = rolling(d.S6_ef.values, 12)
      d["R72"] = rolling(d.lluvia_6h_mm.fillna(0).values, 12)
      d["dZ24"] = d.isoterma_msnm - d.isoterma_msnm.shift(4)
      # arrastre: ráfaga sobre el umbral de Li y Pomeroy (escalado a ráfaga), nieve seca y >= 5 cm en 72 h
      a, b, c2 = P["li_pomeroy"]
      d["Ut10"] = a + b * d.t2m_C + c2 * d.t2m_C ** 2
      tmax24 = d.t2m_max_C.rolling(4, min_periods=1).max()
      lluv24 = rolling(d.lluvia_6h_mm.fillna(0).values, 4)
      seca = (tmax24 < 0) & (lluv24 < 0.5)
      d["arrastre"] = (d.rafaga_max_ms >= P["factor_rafaga"] * d.Ut10) & seca & (d.HN72_ef >= 5)
      # notas 0-5
      evento = d.nieve_6h_cm.fillna(0) > P["evento_cm"]
      d["c_S"] = nota(d.S6_ef, C["S"])
      d["c_r"] = nota(d.tasa_ef, C["r"]) * evento
      d["c_dur"] = nota(d.dur24, C["dur"]) * evento
      d["c_phi"] = nota(d.phi6, C["phi"]) * evento
      d["c_G"] = nota(d.rafaga_max_ms, C["G"]) * (evento | d.arrastre)
      d["c_R"] = nota(d.R6_manto, C["R"])
      B = P["beta"]
      d["W"] = sum(B[k] * d["c_" + k] for k in B)
      d["L_protocolo"] = np.maximum(nivel_regularizado(d.nieve_12h_cm.values, d.lluvia_12h_mm.values, d.isoterma_12h_media.values, P["R2_mm"]),
                                    d.L_horario.fillna(0).values).astype(int)
      d["veto"] = d.L_protocolo.map(P["veto"]).astype(float)
      # peligro
      e = P["exposicion"][tramo]
      arr24 = d.arrastre.rolling(4, min_periods=1).max().astype(bool)
      calent = (d.dZ24 >= 500) & (d.sde_m >= 0.3)
      lluvia_sobre_nieve = (d.lluvia_12h_mm >= 5) & (d.sde_m >= 0.3)
      carga = d.HN72 >= P["hn_min_sobrecarga"]          # sobrecargas solo con nieve nueva importante
      hav = nota(d.HN72, C["HN72"]) + (arr24 & carga) + ((calent | lluvia_sobre_nieve) & carga)
      d["H_av"] = np.floor(np.minimum(hav, 5) * e + 0.5)
      cota_media = (pesos[(pesos.ruta == ruta) & (pesos.tramo == tramo)].pipe(lambda p: (p.cota_camino_media * p.longitud_m).sum() / p.longitud_m.sum()))
      d["H_rm"] = nota(d.R72, C["R72"]) * (d.isoterma_msnm > cota_media)
      d["H"] = np.maximum(d.H_av, d.H_rm)
      # tres reglas de combinación
      d["SV_hibrida"] = np.maximum(d.veto, d.W)
      d["SV_walker"] = d.W
      d["SV_con_peligro"] = np.maximum(d.veto, 0.85 * d.W + 0.15 * d.H)
      partes.append(d)
  return pd.concat(partes, ignore_index=True)


base = construir_base(P)


# ----------------------------------------------------------------------------------------
# Piezas 3 y 4: balance y máquina de estados (dependen de c, theta y de la regla de SV)
# ----------------------------------------------------------------------------------------
ESTADOS = ["E0", "E1", "E2", "E3", "E4", "E5"]
# Orden por magnitud (oct 2026): el cierre por despeje (E3) es menor que el cierre por tormenta (E4),
# y este menor que el cierre por peligro (E5).
NOMBRE = dict(E0="abierto", E1="abierto con restricción", E2="cierre parcial (solo bajada)",
              E3="cierre técnico / despeje", E4="cierre total por tormenta", E5="cierre por peligro")
GRAVEDAD = {e: i for i, e in enumerate(ESTADOS)}          # orden para combinar tramos de una ruta
CLASE3 = dict(E0=0, E1=0, E2=1, E3=2, E4=2, E5=2)        # abierto / restricción-parcial / cerrado
CIERRE = {"N": "E3", "SV": "E4", "H": "E5"}              # estado de cierre de cada índice


def simular(d, sv_col, c, theta, peligro_en_estados=True, P=P):
    """Tres niveles por índice (1 restricción, 2 cierre parcial, 3 cierre); el estado es el E más alto que
    alcanza cualquiera de los tres. En el cierre: peligro (E5) > tormenta (E4) > despeje (E3); la causa de
    los niveles 1 y 2 se nombra en el mismo orden."""
    U = P["umbral_E"]; h1, h2 = P["H_niveles"]["E1"], P["H_niveles"]["E2"]; n2 = P["N_parcial"]
    sv = d[sv_col].values; H = d.H.values
    S6 = d.S6_ef.values; arr = d.arrastre.values; hn = d.HN72_ef.values
    N = 0.0; prev = "E0"
    Ns, Es, causas, eta = np.zeros(len(d)), [], [], np.full(len(d), np.nan)
    for t in range(len(d)):
        peligro = peligro_en_estados and H[t] >= P["H_umbral"]
        u = 0.0 if peligro else 1.0
        A = P["arrastre_frac"] * hn[t] if arr[t] else 0.0
        N = max(0.0, N + S6[t] + A - u * c * DT)
        # nivel = el más alto cuyo umbral se alcanza (un nivel sin umbral se salta)
        n_sv = 3 if sv[t] >= U["cierre"] else 2 if sv[t] >= U["parcial"] else 1 if sv[t] >= U["restriccion"] else 0
        n_h = 0
        if peligro_en_estados:
            n_h = 3 if peligro else 2 if (h2 is not None and H[t] >= h2) else 1 if (h1 is not None and H[t] >= h1) else 0
        cierre_N = N > theta and (not P["despeje_tras_cierre"] or prev in ("E3", "E4", "E5"))
        n_n = 3 if cierre_N else 2 if (n2 is not None and N > n2) else 1 if N > P["theta1_cm"] else 0
        nivel = max(n_sv, n_h, n_n)
        causa = "H" if n_h == nivel else ("SV" if n_sv == nivel else "N")
        s = CIERRE[causa] if nivel == 3 else f"E{nivel}"
        if s in ("E3", "E4", "E5"):
            eta[t] = max(N - theta, 0) / c          # horas de despeje que faltan (sin contar espera por peligro)
        Ns[t] = N; Es.append(s); causas.append(causa if nivel else ""); prev = s
    return Ns, np.array(Es), eta, np.array(causas)


def correr(sv_col, c, theta, peligro_en_estados=True, base_=None, P_=None):
    base_ = base if base_ is None else base_
    P_ = P if P_ is None else P_
    out = []
    for (ruta, tramo), d in base_.groupby(["ruta", "tramo"]):
        d = d.reset_index(drop=True)
        N, E, eta, causa = simular(d, sv_col, c, theta, peligro_en_estados, P_)
        out.append(pd.DataFrame(dict(ruta=ruta, tramo=tramo, bloque_inicio_local=d.bloque_inicio_local, N=N, E=E, eta_h=eta, causa=causa)))
    t = pd.concat(out, ignore_index=True)
    # estado de la ruta = el tramo en peor estado
    t["g"] = t.E.map(GRAVEDAD)
    idx = t.groupby(["ruta", "bloque_inicio_local"]).g.idxmax()
    r = t.loc[idx, ["ruta", "bloque_inicio_local", "E", "causa", "N", "eta_h", "tramo"]].rename(columns={"tramo": "tramo_critico"})
    return t.drop(columns="g"), r.reset_index(drop=True)


# observado -> 3 clases; los bloques "cerrado_horario" (capa administrativa) se excluyen
obs = est[["ruta", "bloque_inicio_local", "estado", "horas_cerrado_meteo", "horas_restringido", "horas_cierre_tecnico", "horas_abierto", "horas_cerrado_horario"]].copy()
obs["y"] = np.select([obs.estado.eq("cerrado_meteo"), obs.estado.isin(["restringido", "cierre_tecnico"]), obs.estado.eq("abierto")], [2, 1, 0], default=-1)


def evaluar(r, ruta=None):
    m = r.merge(obs, on=["ruta", "bloque_inicio_local"])
    m = m[m.y >= 0]
    if ruta:
        m = m[m.ruta == ruta]
    yhat = m.E.map(CLASE3).values; y = m.y.values
    return metricas(y, yhat) | dict(n=len(m))


def kappa_pond(y, yhat, k=3):
    O = np.zeros((k, k))
    for a, b in zip(y, yhat):
        O[a, b] += 1
    W = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)]) / (k - 1) ** 2
    E = np.outer(O.sum(1), O.sum(0)) / O.sum()
    return 1 - (W * O).sum() / (W * E).sum() if (W * E).sum() else np.nan


def metricas(y, yhat):
    y = np.asarray(y); yhat = np.asarray(yhat)
    obs_c, pre_c = y == 2, yhat == 2
    a = int((obs_c & pre_c).sum()); b = int((~obs_c & pre_c).sum()); c = int((obs_c & ~pre_c).sum()); d = int((~obs_c & ~pre_c).sum())
    hss_den = (a + c) * (c + d) + (a + b) * (b + d)
    return dict(exactitud_3clases=float((y == yhat).mean()) if len(y) else np.nan,
                kappa_ponderado=float(kappa_pond(y, yhat)),
                aciertos=a, falsas_alarmas=b, omisiones=c, negativos_correctos=d,
                POD=a / (a + c) if a + c else np.nan, FAR=b / (a + b) if a + b else np.nan,
                CSI=a / (a + b + c) if a + b + c else np.nan,
                HSS=2 * (a * d - b * c) / hss_den if hss_den else np.nan)


def confusion(r, ruta):
    m = r.merge(obs, on=["ruta", "bloque_inicio_local"])
    m = m[(m.y >= 0) & (m.ruta == ruta)]
    return pd.crosstab(m.y.map({0: "obs abierto", 1: "obs restringido/técnico", 2: "obs cerrado"}),
                       m.E.map(lambda e: f"{e} {NOMBRE[e]}"))


# ----------------------------------------------------------------------------------------
# Calibración con la G-21
# ----------------------------------------------------------------------------------------
GRILLA_C = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]
GRILLA_TH = [5, 10, 20, 30, 50]
GRILLA_H = [3, 4, 5]
# (1) c, theta y H* se calibran con la regla de un solo umbral de peligro y de despeje (niveles intermedios apagados)
P_cal = dict(P, H_niveles=dict(E1=None, E2=None), N_parcial=None, despeje_tras_cierre=True)
cal = []
for c, th, hu in itertools.product(GRILLA_C, GRILLA_TH, GRILLA_H):
    _, r = correr("SV_hibrida", c, th, True, base, dict(P_cal, H_umbral=hu))
    cal.append(dict(c=c, theta=th, H_umbral=hu, **evaluar(r, "G-21")))
cal = pd.DataFrame(cal).sort_values(["kappa_ponderado", "CSI", "c"], ascending=[False, False, True])
# la G-21 casi no distingue capacidades: se toma la MENOR capacidad que alcanza el mejor kappa (cota inferior)
mejor_k = cal.kappa_ponderado.max()
top = cal[cal.kappa_ponderado >= mejor_k - 1e-9].sort_values(["c", "theta"])
C_CAL, TH_CAL, H_CAL = float(top.iloc[0].c), float(top.iloc[0].theta), int(top.iloc[0].H_umbral)
P["H_umbral"] = H_CAL
curva_c = cal[(cal.H_umbral == H_CAL)].groupby("c").kappa_ponderado.max().round(3)
curva_c.to_csv(OUT + "/curva_capacidad_G21.csv")
cal.round(3).to_csv(OUT + "/calibracion_G21.csv", index=False)

# (2) niveles intermedios (restricción y cierre parcial) del peligro y de la nieve por despejar.
# La G-21 no los identifica: tiene 1 bloque observado restringido y la restricción cuenta como abierto.
# Se fijan por criterio (oct 2026): H 3 -> restricción, H 4 -> cierre parcial, N > 30 cm -> cierre parcial.
# La grilla queda como diagnóstico de cuánto cuesta cada opción en la G-21.
diag = []
for h1, h2, n2, e4 in itertools.product([2, 3, 4, None], [3, 4, None], [10, 20, 30, None], [True, False]):
    if (h1 is not None and h2 is not None and h1 >= h2) or any(x is not None and x >= H_CAL for x in (h1, h2)):
        continue
    if n2 is not None and not (P["theta1_cm"] < n2 < TH_CAL):
        continue
    Pd = dict(P, H_niveles=dict(E1=h1, E2=h2), N_parcial=n2, despeje_tras_cierre=e4)
    _, r = correr("SV_hibrida", C_CAL, TH_CAL, True, base, Pd)
    diag.append(dict(H_E1=h1, H_E2=h2, N_E2=n2, despeje_tras_cierre=e4, **{f"{k}_G21": v for k, v in evaluar(r, "G-21").items()},
                     kappa_60CH=evaluar(r, "60-CH")["kappa_ponderado"]))
pd.DataFrame(diag).sort_values("kappa_ponderado_G21", ascending=False).round(3).to_csv(OUT + "/calibracion_niveles_G21.csv", index=False)
P["H_niveles"] = dict(E1=3, E2=4)
P["N_parcial"] = 30
P["despeje_tras_cierre"] = True

# ----------------------------------------------------------------------------------------
# Verificación: variantes de combinación, líneas base
# ----------------------------------------------------------------------------------------
filas = []
tramos_res, rutas_res = {}, {}
for nombre, col, pel in [("híbrida (propuesta)", "SV_hibrida", True), ("Walker pura", "SV_walker", True),
                         ("peligro dentro de la severidad", "SV_con_peligro", False)]:
    t, r = correr(col, C_CAL, TH_CAL, pel)
    tramos_res[nombre], rutas_res[nombre] = t, r
    for ruta in ["G-21", "60-CH"]:
        filas.append(dict(modelo=nombre, ruta=ruta, **evaluar(r, ruta)))
# protocolo regularizado sin persistencia (nivel de la ruta = máximo de tramos)
prot = base.groupby(["ruta", "bloque_inicio_local"]).L_protocolo.max().reset_index()
prot["E"] = prot.L_protocolo.map({0: "E0", 1: "E1", 2: "E2", 3: "E4"})   # alerta 3 = cierre por tormenta
for ruta in ["G-21", "60-CH"]:
    filas.append(dict(modelo="protocolo (cuadro, sin persistencia)", ruta=ruta, **evaluar(prot, ruta)))
# persistencia trivial: el estado observado del bloque anterior
po = obs.sort_values(["ruta", "bloque_inicio_local"]).copy()
po["yp"] = po.groupby("ruta").y.shift(1)
for ruta in ["G-21", "60-CH"]:
    q = po[(po.ruta == ruta) & (po.y >= 0) & (po.yp >= 0)]
    filas.append(dict(modelo="persistencia (bloque anterior)", ruta=ruta, **metricas(q.y.values, q.yp.astype(int).values), n=len(q)))
met = pd.DataFrame(filas)
met.round(3).to_csv(OUT + "/metricas.csv", index=False)

# ----------------------------------------------------------------------------------------
# Logit ordinal (G-21) -> probabilidades en la 60-CH
# ----------------------------------------------------------------------------------------
t_h, r_h = tramos_res["híbrida (propuesta)"], rutas_res["híbrida (propuesta)"]
feat = base.groupby(["ruta", "bloque_inicio_local"]).agg(SV=("SV_hibrida", "max"), H=("H", "max")).reset_index()
feat = feat.merge(t_h.groupby(["ruta", "bloque_inicio_local"]).N.max().reset_index(), on=["ruta", "bloque_inicio_local"])
feat = feat.merge(obs[["ruta", "bloque_inicio_local", "y"]], on=["ruta", "bloque_inicio_local"], how="left")
X_COLS = ["SV", "H", "N"]


def ajustar_ordinal(X, y, l2=0.05):
    k = X.shape[1]

    def nll(p):
        b, a1, la = p[:k], p[k], p[k + 1]
        a2 = a1 + np.exp(la)
        z = X @ b
        F1, F2 = 1 / (1 + np.exp(-(a1 - z))), 1 / (1 + np.exp(-(a2 - z)))
        pr = np.select([y == 0, y == 1, y == 2], [F1, F2 - F1, 1 - F2])
        return -np.sum(np.log(np.clip(pr, 1e-12, 1))) + l2 * np.sum(b ** 2)
    r = minimize(nll, np.r_[np.zeros(k), 0.0, 0.0], method="BFGS")
    return r.x


def predecir_ordinal(par, X):
    k = X.shape[1]
    b, a1, a2 = par[:k], par[k], par[k] + np.exp(par[k + 1])
    z = X @ b
    F1, F2 = 1 / (1 + np.exp(-(a1 - z))), 1 / (1 + np.exp(-(a2 - z)))
    return np.column_stack([F1, F2 - F1, 1 - F2])


g = feat[(feat.ruta == "G-21") & (feat.y >= 0)]
mu, sd = g[X_COLS].mean(), g[X_COLS].std().replace(0, 1)
par = ajustar_ordinal(((g[X_COLS] - mu) / sd).values, g.y.astype(int).values)
pr = predecir_ordinal(par, ((feat[X_COLS] - mu) / sd).fillna(0).values)
feat["p_abierto"], feat["p_restr"], feat["p_cerrado"] = pr.T
ordinal = dict(variables=X_COLS, coef_estandarizados=[round(float(v), 3) for v in par[:3]],
               umbrales=[round(float(par[3]), 3), round(float(par[3] + np.exp(par[4])), 3)],
               n_G21=int(len(g)), cerrados_G21=int((g.y == 2).sum()))
for ruta in ["G-21", "60-CH"]:
    q = feat[(feat.ruta == ruta) & (feat.y >= 0)]
    ordinal[f"metricas_{ruta}"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in metricas(q.y.values, pr[q.index].argmax(1)).items()}

# ----------------------------------------------------------------------------------------
# Contrafactual 60-CH: estado justificado en los bloques observados como cerrados
# ----------------------------------------------------------------------------------------
cf = []
ESCENARIOS = [("2 cm/h", 2.0), ("4 cm/h", 4.0), (f"{C_CAL:g} cm/h (calibrada)", C_CAL)]
series_cf = {}
for nombre_e, c in ESCENARIOS:
    _, r = correr("SV_hibrida", c, TH_CAL)
    series_cf[nombre_e] = r
    m = r.merge(obs, on=["ruta", "bloque_inicio_local"])
    m = m[(m.ruta == "60-CH") & (m.y == 2)]
    hrs = m.groupby("E").horas_cerrado_meteo.sum()
    tot = m.horas_cerrado_meteo.sum()
    fila = dict(escenario=nombre_e, c_cm_h=round(c, 2), horas_cerradas_obs=int(tot))
    for e in ESTADOS:
        fila[f"h_{e}"] = int(hrs.get(e, 0))
    fila["h_con_respaldo_cierre"] = int(sum(hrs.get(e, 0) for e in ("E3", "E4", "E5")))
    fila["h_sin_respaldo"] = int(tot - fila["h_con_respaldo_cierre"])
    fila["pct_sin_respaldo"] = round(100 * fila["h_sin_respaldo"] / tot, 1) if tot else np.nan
    cf.append(fila)
cf = pd.DataFrame(cf)
cf.to_csv(OUT + "/contrafactual_60CH.csv", index=False)

# por episodio observado (60-CH y G-21), escenario calibrado
r = rutas_res["híbrida (propuesta)"]
eh = pd.read_csv(SAL + "/estado_caminos_eventos.csv", parse_dates=["inicio_local", "fin_local"])
eps = []
for e in eh[eh.estado.eq("cerrado_meteo")].itertuples():
    q = r[(r.ruta == e.ruta) & (r.bloque_inicio_local >= e.inicio_local.floor("6h")) & (r.bloque_inicio_local <= e.fin_local.floor("6h"))]
    cnt = q.E.value_counts()
    cerr = q.E.isin(["E3", "E4", "E5"])
    eps.append(dict(ruta=e.ruta, inicio=e.inicio_local, fin=e.fin_local, horas_obs=e.horas, bloques=len(q),
                    **{f"bloques_{s}": int(cnt.get(s, 0)) for s in ESTADOS},
                    horas_modelo_cerrado=int(cerr.sum() * DT),
                    error_duracion_h=int(cerr.sum() * DT - e.horas), causa=e.causa))
eps = pd.DataFrame(eps)
eps.to_csv(OUT + "/episodios.csv", index=False)

# días de la 60-CH sin respaldo para cierre total (escenario calibrado, día con algún bloque observado cerrado)
m = r.merge(obs, on=["ruta", "bloque_inicio_local"])
m = m[(m.ruta == "60-CH")]
m["fecha"] = m.bloque_inicio_local.dt.date
dd = m.groupby("fecha").agg(obs_cerrado=("y", lambda s: (s == 2).any()), peor=("E", lambda s: max(s, key=GRAVEDAD.get)),
                            n_cerrado_mod=("E", lambda s: s.isin(["E3", "E4", "E5"]).sum())).reset_index()
dd.to_csv(OUT + "/dias_60CH.csv", index=False)

# ----------------------------------------------------------------------------------------
# Sensibilidad de los supuestos (cambia uno a la vez; mide G-21 kappa y % sin respaldo 60-CH)
# ----------------------------------------------------------------------------------------
import copy


def pct_sin_respaldo(r):
    m = r.merge(obs, on=["ruta", "bloque_inicio_local"])
    m = m[(m.ruta == "60-CH") & (m.y == 2)]
    tot = m.horas_cerrado_meteo.sum()
    con = m[m.E.isin(["E3", "E4", "E5"])].horas_cerrado_meteo.sum()
    return 100 * (tot - con) / tot, 100 * m[m.E == "E5"].horas_cerrado_meteo.sum() / tot


CAMBIOS = [
    ("base (propuesta)", {}),
    ("margen de nieve δ = 150 m", {"delta_nieve_m": 150}),
    ("margen de nieve δ = 500 m", {"delta_nieve_m": 500}),
    ("exposición tramos medios = 1", {"exposicion": {"alto": 1.0, "medio": 1.0}}),
    ("exposición tramos altos = 0,75", {"exposicion": {"alto": 0.75, "medio": 0.5}}),
    ("factor de ráfaga γ = 2,0", {"factor_rafaga": 2.0}),
    ("factor de ráfaga γ = 1,3", {"factor_rafaga": 1.3}),
    ("sin nieve arrastrada (α = 0)", {"arrastre_frac": 0.0}),
    ("umbral de peligro H* = 5", {"H_umbral": 5}),
    ("sobrecargas desde 20 cm", {"hn_min_sobrecarga": 20}),
    ("sobrecargas desde 50 cm", {"hn_min_sobrecarga": 50}),
    ("pesos de Walker (nieve 0,80)", {"beta": dict(S=0.80, phi=0.04, r=0.04, dur=0.04, G=0.04, R=0.04)}),
    # comprobación: la regla anterior (v2), con un solo umbral de peligro y de despeje, y su calibración (c 6, θ 50, H* 5)
    ("un solo umbral por índice (v2)", {"H_niveles": dict(E1=None, E2=None), "N_parcial": None, "despeje_tras_cierre": True,
                                        "H_umbral": 5, "_c": 6.0, "_theta": 50.0}),
]
sens = []
for nombre_s, cambio in CAMBIOS:
    Pm = copy.deepcopy(P); Pm.update(cambio)
    c_s, th_s = Pm.pop("_c", C_CAL), Pm.pop("_theta", TH_CAL)
    bm = construir_base(Pm)
    _, rm = correr("SV_hibrida", c_s, th_s, True, bm, Pm)
    mg, mc = evaluar(rm, "G-21"), evaluar(rm, "60-CH")
    sr, e5 = pct_sin_respaldo(rm)
    sens.append(dict(supuesto=nombre_s, kappa_G21=mg["kappa_ponderado"], CSI_G21=mg["CSI"], FAR_G21=mg["FAR"],
                     kappa_60CH=mc["kappa_ponderado"], pct_sin_respaldo_60CH=sr, pct_por_peligro_60CH=e5))
sens = pd.DataFrame(sens).round(3)
sens.to_csv(OUT + "/sensibilidad.csv", index=False)

# criterio de decisión aprendido en la G-21 (logit ordinal) aplicado a los cierres de la 60-CH
q = feat[(feat.ruta == "60-CH") & (feat.y == 2)].merge(obs[["ruta", "bloque_inicio_local", "horas_cerrado_meteo"]], on=["ruta", "bloque_inicio_local"])
q["clase"] = q[["p_abierto", "p_restr", "p_cerrado"]].values.argmax(1)
ordinal["60CH_cierres_obs_horas_por_clase_predicha"] = {k: int(v) for k, v in q.groupby("clase").horas_cerrado_meteo.sum().rename({0: "abierto", 1: "restriccion", 2: "cerrado"}).items()}
ordinal["60CH_cierres_obs_p_cerrado_media"] = round(float(q.p_cerrado.mean()), 3)

# ----------------------------------------------------------------------------------------
# Salidas
# ----------------------------------------------------------------------------------------
bl = base.merge(t_h, on=["ruta", "tramo", "bloque_inicio_local"]).merge(
    obs[["ruta", "bloque_inicio_local", "estado"]].rename(columns={"estado": "estado_observado"}), on=["ruta", "bloque_inicio_local"], how="left")
cols = ["ruta", "tramo", "bloque_inicio_local", "nieve_12h_cm", "nieve_6h_cm", "isoterma_12h_media", "phi6", "S6_ef", "tasa_ef", "dur24",
        "rafaga_max_ms", "Ut10", "arrastre", "lluvia_12h_mm", "R72", "HN72", "dZ24", "sde_m",
        "c_S", "c_r", "c_dur", "c_phi", "c_G", "c_R", "W", "L_protocolo", "veto", "SV_hibrida", "SV_walker", "SV_con_peligro",
        "H_av", "H_rm", "H", "N", "E", "causa", "eta_h", "estado_observado"]
bl[cols].round(3).to_csv(OUT + "/bloques.csv", index=False)
r_h.merge(feat[["ruta", "bloque_inicio_local", "p_abierto", "p_restr", "p_cerrado"]], on=["ruta", "bloque_inicio_local"]).round(3).to_csv(OUT + "/estado_ruta.csv", index=False)
for nombre_e, rr in series_cf.items():
    rr.assign(escenario=nombre_e).to_csv(OUT + f"/estado_ruta_c{nombre_e.split()[0]}.csv", index=False)
with open(OUT + "/parametros.json", "w", encoding="utf-8") as f:
    json.dump(dict(P, c_calibrado_cm_h=C_CAL, theta_calibrado_cm=TH_CAL, H_umbral_calibrado=H_CAL, curva_capacidad=curva_c.to_dict(), ordinal=ordinal), f, ensure_ascii=False, indent=1, default=str)

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
print("calibración G-21 (top 5):"); print(cal.head(5).round(3).to_string(index=False))
print("\nmétricas:"); print(met.round(3).to_string(index=False))
print("\nconfusión G-21:"); print(confusion(r_h, "G-21"))
print("\nconfusión 60-CH:"); print(confusion(r_h, "60-CH"))
print("\nordinal:", json.dumps(ordinal, ensure_ascii=False))
print("\ncontrafactual 60-CH:"); print(cf.to_string(index=False))
print("\nepisodios:"); print(eps.drop(columns="causa").to_string(index=False))
