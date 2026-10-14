# -*- coding: utf-8 -*-
"""Figura 2 de la postulación (PNG 300 dpi): índices y estados de la G-21 y la 60-CH, julio y agosto de 2026.
La figura 1 (arquitectura) y la tabla comparativa se compilan aparte desde fig_png/*.tex; este script escribe
fig_png/umbrales_calibrados.tex, con los cortes y umbrales que usa la figura 1."""
import os
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.transforms as mtransforms
from matplotlib.patches import Patch

from pathlib import Path
BASE = Path(__file__).resolve().parents[2].as_posix()   # raíz del repositorio
S = BASE + "/modelo_sam/salidas/sistema"
OUT = BASE + "/documento_tecnico/fig_png"
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({"font.family": "Cambria", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e",
                     "axes.grid": True, "grid.color": "#ecebe6", "grid.linewidth": 0.6, "legend.frameon": False,
                     "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.facecolor": "white"})
TXT, TXT2 = "#0b0b0b", "#52514e"
COL_E = {"E0": "#d9d8d2", "E1": "#1baf7a", "E2": "#eda100", "E3": "#2a78d6", "E4": "#e34948", "E5": "#4a3aa7"}
NOM_E = {"E0": "E0 abierto", "E1": "E1 abierto con restricción", "E2": "E2 cierre parcial", "E3": "E3 cerrado por despeje",
         "E4": "E4 cerrado por tormenta", "E5": "E5 cerrado por peligro"}
COL_O = {"abierto": "#d9d8d2", "restringido": "#eda100", "cerrado_meteo": "#e34948", "cerrado_horario": "#8c8a83"}
NOM_O = {"abierto": "abierto", "restringido": "restringido", "cerrado_meteo": "cerrado por meteorología",
         "cerrado_horario": "cerrado por horario fronterizo"}
C_SV, C_H = "#2a78d6", "#eb6834"
UMBRALES = [(2.5, C_SV, "cierre parcial ($SV$ 2,5)"), (3.5, C_SV, "cerrado por tormenta ($SV$ 3,5)"),
            (5.0, C_H, "cerrado por peligro ($H$ 5)")]
T0, T1 = pd.Timestamp("2026-07-01"), pd.Timestamp("2026-09-01")

def num(x):
    """Número con coma decimal y sin ceros sobrantes (para LaTeX)."""
    return f"{x:g}".replace(".", "{,}")


def dec2(x):
    return f"{x:.2f}".replace(".", "{,}")


def umbrales_tex():
    """Macros con los cortes y umbrales vigentes del modelo, para la figura 1 (fig_A_arquitectura.tex)."""
    with open(S + "/parametros.json", encoding="utf-8") as f:
        P = json.load(f)
    C, B, U = P["cortes"], P["beta"], P["umbral_E"]
    negrita = dict(S=[0.5, 12.5, 25], R=[0.5, 10])     # cortes del protocolo de Lo Barnechea (12 h) llevados a 6 h
    L = ["% Generado por figuras_postulacion.py desde salidas/sistema/parametros.json. No editar a mano."]
    for k in ["S", "phi", "r", "dur", "G", "R", "HN72", "R72"]:
        fmt = dec2 if k == "phi" else num
        celdas = [(r"\textbf{%s}" if q in negrita.get(k, []) else "%s") % fmt(q) for q in C[k]]
        L.append(r"\newcommand{\cortes%s}{%s}" % (k.replace("72", "S").replace("phi", "F"), " & ".join(celdas)))
    for k in B:
        L.append(r"\newcommand{\peso%s}{%s}" % (k.replace("phi", "F"), dec2(B[k])))
    L += [r"\newcommand{\SVrest}{%s}" % num(U["restriccion"]), r"\newcommand{\SVparc}{%s}" % num(U["parcial"]),
          r"\newcommand{\SVcierre}{%s}" % num(U["cierre"]),
          r"\newcommand{\Hrest}{%s}" % num(P["H_niveles"]["E1"]), r"\newcommand{\Hparc}{%s}" % num(P["H_niveles"]["E2"]),
          r"\newcommand{\Hcierre}{%s}" % num(P["H_umbral_calibrado"]),
          r"\newcommand{\Nrest}{%s}" % num(P["theta1_cm"]), r"\newcommand{\Nparc}{%s}" % num(P["N_parcial"]),
          r"\newcommand{\Ncierre}{%s}" % num(P["theta_calibrado_cm"]), r"\newcommand{\cdesp}{%s}" % num(P["c_calibrado_cm_h"]),
          r"\newcommand{\expAlto}{%s}" % num(P["exposicion"]["alto"]), r"\newcommand{\expMedio}{%s}" % num(P["exposicion"]["medio"]),
          r"\newcommand{\hnSobrecarga}{%s}" % num(P["hn_min_sobrecarga"])]
    with open(OUT + "/umbrales_calibrados.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


umbrales_tex()
with open(S + "/parametros.json", encoding="utf-8") as f:
    PAR = json.load(f)
UMBRALES = [(2.5, C_SV, "cierre parcial ($SV$ 2,5)"), (3.5, C_SV, "cerrado por tormenta ($SV$ 3,5)"),
            (PAR["H_niveles"]["E2"], C_H, "cierre parcial ($H$ %s)" % f"{PAR['H_niveles']['E2']:g}"),
            (PAR["H_umbral_calibrado"], C_H, "cerrado por peligro ($H$ %s)" % f"{PAR['H_umbral_calibrado']:g}")]

b = pd.read_csv(S + "/bloques.csv", parse_dates=["bloque_inicio_local"])
r = pd.read_csv(S + "/estado_ruta.csv", parse_dates=["bloque_inicio_local"])
est = pd.read_csv(BASE + "/modelo_sam/salidas/estado_caminos_6h.csv", parse_dates=["bloque_inicio_local"])


def franja(ax, t, valores, colores, y0, alto=0.8):
    for ti, v in zip(t, valores):
        if isinstance(v, str) and v in colores:
            ax.add_patch(plt.Rectangle((mdates.date2num(ti), y0), 0.25, alto, color=colores[v], lw=0))


def paneles(ax_i, ax_e, ruta, titulo):
    alto = b[(b.ruta == ruta) & (b.tramo == "alto")].sort_values("bloque_inicio_local")
    t = alto.bloque_inicio_local
    ax_i.step(t, alto.SV_hibrida, where="post", color=C_SV, lw=1.3, label="severidad ($SV$)", zorder=3)
    ax_i.step(t, alto.H, where="post", color=C_H, lw=1.3, label="peligro ($H$)", zorder=3)
    trans = mtransforms.blended_transform_factory(ax_i.transAxes, ax_i.transData)
    for y, c, txt in UMBRALES:
        ax_i.axhline(y, color=c, lw=0.7, ls=(0, (2, 2)), alpha=0.8, zorder=2)
        ax_i.text(1.01, y, txt, transform=trans, fontsize=7, color=c, va="center", ha="left")
    ax_i.set_ylim(0, 7.0); ax_i.set_yticks([0, 1, 2, 3, 4, 5]); ax_i.set_ylabel("índice (0 a 5)")
    ax_i.set_title(titulo, loc="left", fontsize=9.5, color=TXT, fontweight="bold")
    rr = r[r.ruta == ruta].sort_values("bloque_inicio_local")
    eo = est[est.ruta == ruta].sort_values("bloque_inicio_local")
    franja(ax_e, eo.bloque_inicio_local, eo.estado, COL_O, 1.1)
    franja(ax_e, rr.bloque_inicio_local, rr.E, COL_E, 0.0)
    ax_e.set_ylim(0, 2.0); ax_e.set_yticks([0.4, 1.5]); ax_e.set_yticklabels(["SAM-Cordillera", "observado"]); ax_e.grid(False)
    ax_e.spines["left"].set_visible(False); ax_e.tick_params(axis="y", length=0)


def marca(ax, t_ini, t_fin, texto, y=5.9):
    """Corchete horizontal sobre el área de las curvas, con su etiqueta encima."""
    ax.plot([t_ini, t_ini, t_fin, t_fin], [y - 0.2, y, y, y - 0.2], color=TXT2, lw=0.8, zorder=4)
    ax.text(t_ini + (t_fin - t_ini) / 2, y + 0.15, texto, ha="center", va="bottom", fontsize=7.5, color=TXT)


fig, axs = plt.subplots(4, 1, figsize=(7.0, 5.9), sharex=True,
                        gridspec_kw=dict(height_ratios=[1.35, 0.45, 1.35, 0.45], hspace=0.32))
paneles(axs[0], axs[1], "G-21", "a) G-21 (calibración)")
paneles(axs[2], axs[3], "60-CH", "b) 60-CH (prueba fuera de la calibración)")
marca(axs[0], pd.Timestamp("2026-07-15 23:00"), pd.Timestamp("2026-07-20 10:00"), "cierre observado, 15 al 20 jul")
marca(axs[2], pd.Timestamp("2026-07-14 15:00"), pd.Timestamp("2026-08-18 08:00"), "cierre observado, 14 jul al 18 ago")
axs[0].legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, fontsize=7.5, handlelength=1.6)

ax = axs[3]
ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1, 8, 15, 22]))
mes = {7: "jul", 8: "ago"}
ax.xaxis.set_major_formatter(plt.FuncFormatter(
    lambda x, _: f"{mdates.num2date(x).day} {mes[mdates.num2date(x).month]}" if mdates.num2date(x).month in mes else ""))
ax.set_xlim(T0, T1)
h1 = [Patch(color=COL_E[e], label=NOM_E[e]) for e in COL_E]
h2 = [Patch(color=COL_O[e], label=NOM_O[e]) for e in COL_O]
fig.legend(handles=h1, title="Estado que indica SAM-Cordillera", loc="upper left", ncol=2, fontsize=7.2, title_fontsize=7.6,
           bbox_to_anchor=(0.07, 0.03), alignment="left")
fig.legend(handles=h2, title="Estado observado de la ruta", loc="upper left", ncol=1, fontsize=7.2, title_fontsize=7.6,
           bbox_to_anchor=(0.60, 0.03), alignment="left")
fig.savefig(OUT + "/fig_B_evidencia.png"); plt.close(fig)
print("figura en", OUT)
