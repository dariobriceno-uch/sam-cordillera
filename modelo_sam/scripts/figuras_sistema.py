# -*- coding: utf-8 -*-
"""Figuras del documento del sistema de condición invernal (PDF vectorial para LaTeX)."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

from pathlib import Path
BASE = Path(__file__).resolve().parents[2].as_posix()   # raíz del repositorio
S = BASE + "/modelo_sam/salidas/sistema"
FIG = BASE + "/documento_tecnico/fig"
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({"font.family": "Cambria", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e",
                     "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6, "legend.frameon": False})
TXT2 = "#52514e"
COL_E = {"E0": "#d9d8d2", "E1": "#1baf7a", "E2": "#eda100", "E3": "#e34948", "E4": "#2a78d6", "E5": "#4a3aa7"}
NOM_E = {"E0": "E0 abierto", "E1": "E1 restricción", "E2": "E2 cierre parcial", "E3": "E3 cierre por tormenta",
         "E4": "E4 despeje", "E5": "E5 cierre por peligro"}
COL_O = {"abierto": "#d9d8d2", "restringido": "#eda100", "cierre_tecnico": "#2a78d6", "cerrado_meteo": "#e34948", "cerrado_horario": "#8c8a83"}
NOM_O = {"abierto": "abierto", "restringido": "restringido", "cierre_tecnico": "cierre técnico", "cerrado_meteo": "cerrado (meteo)",
         "cerrado_horario": "cerrado por horario"}
C_SV, C_H = "#2a78d6", "#eb6834"

b = pd.read_csv(S + "/bloques.csv", parse_dates=["bloque_inicio_local"])
r = pd.read_csv(S + "/estado_ruta.csv", parse_dates=["bloque_inicio_local"])
est = pd.read_csv(BASE + "/modelo_sam/salidas/estado_caminos_6h.csv", parse_dates=["bloque_inicio_local"])
W6 = pd.Timedelta(hours=6)


def franja(ax, t, valores, colores, y0, alto=0.8):
    for ti, v in zip(t, valores):
        if isinstance(v, str) and v in colores:
            ax.add_patch(plt.Rectangle((mdates.date2num(ti), y0), 0.25, alto, color=colores[v], lw=0))


def serie_ruta(ruta, archivo):
    alto = b[(b.ruta == ruta) & (b.tramo == "alto")].sort_values("bloque_inicio_local")
    rr = r[r.ruta == ruta].sort_values("bloque_inicio_local")
    eo = est[est.ruta == ruta].sort_values("bloque_inicio_local")
    t = alto.bloque_inicio_local
    fig, axs = plt.subplots(4, 1, figsize=(7.2, 7.6), sharex=True, gridspec_kw=dict(height_ratios=[1.1, 1.1, 1.0, 0.75]))
    ax = axs[0]
    ax.bar(t + W6 / 2, alto.nieve_12h_cm, width=0.22, color="#c3c2b7", label="nieve 12 h en la celda ERA5-Land")
    ax.bar(t + W6 / 2, alto.S12_ef, width=0.22, color=C_SV, label="nieve efectiva sobre el camino ($S^*$)")
    for y, lab in [(25, "25 cm"), (50, "50 cm")]:
        ax.axhline(y, color=TXT2, lw=0.7, ls=":"); ax.text(t.iloc[0], y + 1, lab, color=TXT2, fontsize=7)
    ax.set_ylabel("cm en 12 h"); ax.set_title(f"{ruta}, tramo alto: nieve", loc="left", fontsize=9.5, color="#0b0b0b")
    ax.legend(loc="upper right", fontsize=7.5)
    ax = axs[1]
    ax.step(t, alto.SV_hibrida, where="post", color=C_SV, lw=1.6, label="severidad $SV$ (regla híbrida)")
    ax.step(t, alto.H, where="post", color=C_H, lw=1.6, label="peligro $H$")
    for y in (1, 2.5, 3.5, 5):
        ax.axhline(y, color=TXT2, lw=0.6, ls=":")
    ax.text(t.iloc[0], 5.1, "$H^*=5$", fontsize=7, color=TXT2)
    ax.set_ylim(0, 6.6); ax.set_yticks(range(6)); ax.set_ylabel("índice 0–5"); ax.set_title("índices de severidad y de peligro", loc="left", fontsize=9.5)
    ax.legend(loc="upper right", fontsize=7.5, ncol=2, bbox_to_anchor=(1, 1.04))
    ax = axs[2]
    ax.plot(t, alto.N, color="#0b0b0b", lw=1.4, label="nieve por despejar $N$")
    ax.axhline(50, color=TXT2, lw=0.7, ls=":"); ax.text(t.iloc[0], 53, r"$\theta = 50$ cm", fontsize=7, color=TXT2)
    ax.set_ylabel("cm"); ax.set_title("balance de despeje (capacidad calibrada)", loc="left", fontsize=9.5)
    ax = axs[3]
    franja(ax, eo.bloque_inicio_local, eo.estado, COL_O, 1.1)
    franja(ax, rr.bloque_inicio_local, rr.E, COL_E, 0.0)
    ax.set_ylim(0, 2.0); ax.set_yticks([0.4, 1.5]); ax.set_yticklabels(["modelo", "observado"]); ax.grid(False)
    ax.set_title("estado de la ruta", loc="left", fontsize=9.5)
    ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1, 8, 15, 22]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    ax.set_xlim(t.iloc[0], t.iloc[-1] + W6)
    h1 = [Patch(color=COL_E[e], label=NOM_E[e]) for e in COL_E]
    h2 = [Patch(color=COL_O[e], label=NOM_O[e]) for e in COL_O]
    fig.legend(handles=h1 + h2, loc="lower center", ncol=4, fontsize=7.2, bbox_to_anchor=(0.5, -0.005))
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    fig.savefig(FIG + "/" + archivo); plt.close(fig)


serie_ruta("60-CH", "serie_60CH.pdf")
serie_ruta("G-21", "serie_G21.pdf")

# contrafactual: horas observadas como cerradas (60-CH) según el estado del modelo
cf = pd.read_csv(S + "/contrafactual_60CH.csv")
fig, ax = plt.subplots(figsize=(7.2, 2.3))
orden = ["E5", "E4", "E3", "E2", "E1", "E0"]
for i, f in enumerate(cf.itertuples()):
    x0 = 0
    for e in orden:
        v = getattr(f, f"h_{e}")
        if v:
            ax.barh(i, v, left=x0, color=COL_E[e], edgecolor="white", linewidth=1.5, height=0.62)
            if v >= 45:
                ax.text(x0 + v / 2, i, f"{v}", ha="center", va="center", fontsize=7.5, color="white" if e in ("E5", "E4", "E3") else "#0b0b0b")
            x0 += v
ax.set_yticks(range(len(cf))); ax.set_yticklabels([f"capacidad {e}" for e in cf.escenario])
ax.invert_yaxis(); ax.set_xlabel("horas de cierre meteorológico observado en la 60-CH (julio–agosto 2026)")
ax.set_xlim(0, cf.horas_cerradas_obs.max()); ax.grid(axis="y", visible=False)
ax.legend(handles=[Patch(color=COL_E[e], label=NOM_E[e]) for e in orden], loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=3, fontsize=7.3)
fig.tight_layout(); fig.savefig(FIG + "/contrafactual_60CH.pdf", bbox_inches="tight"); plt.close(fig)

# curva de la capacidad
cc = pd.read_csv(S + "/curva_capacidad_G21.csv")
fig, ax = plt.subplots(figsize=(4.6, 2.4))
ax.plot(cc.c, cc.kappa_ponderado, color=C_SV, lw=2, marker="o", ms=5)
ax.set_xlabel("capacidad de despeje $c$ (cm/h)"); ax.set_ylabel("kappa ponderado, G-21")
ax.axvline(6, color=TXT2, lw=0.7, ls=":"); ax.text(6.15, cc.kappa_ponderado.min() + 0.02, "6 cm/h: desde aquí\nya no mejora", fontsize=7, color=TXT2)
fig.tight_layout(); fig.savefig(FIG + "/curva_capacidad.pdf"); plt.close(fig)
print("figuras en", FIG, os.listdir(FIG))
