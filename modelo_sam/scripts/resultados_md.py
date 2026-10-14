# -*- coding: utf-8 -*-
"""Rellena la sección 7 (Resultados) de docs/modelo_cierre.md con las salidas de modelo_cierre.py."""
import re, json, os
import pandas as pd

from pathlib import Path
BASE = Path(__file__).resolve().parents[1].as_posix()   # carpeta modelo_sam/
m = pd.read_csv(BASE + "/salidas/modelo_cierre_metricas.csv")
e = pd.read_csv(BASE + "/salidas/modelo_cierre_episodios.csv")
p = json.load(open(BASE + "/salidas/modelo_cierre_parametros.json", encoding="utf-8"))
ma = m[(m.tramo == "alto") | (m.ruta == "ambas")]


def f(x, n=2):
    return "—" if pd.isna(x) else f"{x:.{n}f}".replace(".", ",")


def fh(x):
    return "—" if pd.isna(x) else str(x)[:16]


def origen(modelo):
    if modelo.startswith("protocolo literal"): return (0, "Protocolo tal cual")
    if modelo.startswith("persistencia trivial"): return (1, "Referencia")
    if modelo.startswith("regularizado (L*"): return (2, "Propuesta: cuadro sin huecos")
    if "calibrado" in modelo: return (3, "Propuesta, calibrada con los cierres")
    return (4, "Propuesta, ajustada con los cierres")
ma = ma.assign(_o=ma.modelo.map(lambda x: origen(x)[0])).sort_values(["_o", "ruta"], kind="stable")
rows = ["| Origen | Modelo | Ruta | A | B | C | D | POD | FAR | CSI | HSS |",
        "|------------------|----------------------|------|-----|-----|-----|-----|-----|-----|-----|-----|"]
for _, r in ma.iterrows():
    rows.append(f"| {origen(r.modelo)[1]} | {r.modelo} | {r.ruta} | {int(r.aciertos)} | {int(r.falsas_alarmas)} | {int(r.omisiones)} | "
                f"{int(r.negativos_correctos)} | {f(r.POD)} | {f(r.FAR)} | {f(r.CSI)} | {f(r.HSS)} |")
tabla_m = "\n".join(rows)

rows = ["| Ruta | Inicio | Fin | Días | Nieve en el episodio (cm) | S máx 12 h (cm) | Z mín (m) | Nivel máx protocolo | Primer nivel 3 | Causa según la matriz |",
        "|-----|--------|--------|----|------|------|------|-----|--------|------------------|"]
for _, r in e.iterrows():
    rows.append(f"| {r.ruta} | {fh(r.inicio_local)} | {fh(r.fin_local)} | {f(r.dias, 1)} | {f(r.nieve_en_episodio_cm, 0)} | "
                f"{f(r.S_max12_cm, 0)} | {f(r.Z_min_msnm, 0)} | {int(r.L_max_regularizado)} | {fh(r.primer_L3_regularizado)} | {r.causa_matriz} |")
tabla_e = "\n".join(rows)

rows = ["| Ruta | Tramo | Umbral de cierre $s^\\dagger$ (cm/12 h) | Despeje $c$ (cm/h) | Residual $\\theta$ (cm) | POD | FAR | CSI |",
        "|---|---|---|---|---|---|---|---|"]
for k, v in p["persistencia"].items():
    if "umbral" in k:
        r, t, _ = k.split("|")
        rows.append(f"| {r} | {t} | {v['s_cierre_cm_12h']} | {str(v['c_despeje_cm_h']).replace('.', ',')} | {v['theta_cm']} | {f(v['POD'])} | {f(v['FAR'])} | {f(v['CSI'])} |")
tabla_p = "\n".join(rows)

lg = p["logistica"]; lm = p["logistica_solo_meteo"]
coef = ", ".join(f"{v} = {c:+.3f}".replace(".", ",") for v, c in zip(lg["variables"][1:], lg["coeficientes_estandarizados"][1:]))
auc1 = str(lg["AUC"]).replace(".", ","); auc2 = str(lm["AUC"]).replace(".", ",")

res = f"""## 7. Resultados

Todo lo que sigue compara, día a día, el cierre observado de la ruta (matrices del colega, categoría *cerrado_meteo*) con lo que dice cada modelo en el tramo alto, del 1 de julio al 31 de agosto de 2026 (62 días por ruta). Los modelos corren en bloques de 6 horas (cuatro por día) y el día queda cerrado si alguno de sus bloques lo está. El detalle está en `salidas/`: `consolidado_6h.csv`, `modelo_cierre_metricas.csv`, `modelo_cierre_episodios.csv`, `modelo_cierre_diario.csv`, `modelo_cierre_parametros.json`. La versión hora a hora quedó respaldada en `respaldo_v2_horario/`.

### 7.1 Lo que pasó

| Ruta | Días con cierre | Episodios | Nieve caída jul + ago (cm) | Máximo en 12 h (cm) |
|---|---|---|---|---|
| 60-CH (Guardia Vieja – túnel) | 47 | 5 | 727 | 50 |
| G-21 (Farellones y accesos) | 6 | 2 | 462 | 38 |

Episodios de cierre observados y lo que ERA5 vio en cada uno:

{tabla_e}

Tres cosas saltan a la vista. Primera: **ningún episodio alcanzó el nivel 3 del cuadro.** En bloques de 6 horas, el máximo de la 60-CH fue 49,96 cm en 12 horas el 17 de julio entre las 12 y las 18 h, con la barrera ya cerrada hacía tres días: se queda a centésimas del umbral de 50 cm (en el cálculo hora a hora lo cruzaba por una hora, con 51,6 cm). El único bloque de nivel 3 del periodo es el 8 de agosto de 06 a 12 h en la G-21, por isoterma baja con poca nieve, y ese día no hubo cierre. Las autoridades cerraron con 30 a 50 cm en 12 horas e isoterma entre 1 800 y 2 300 m, que el cuadro clasifica como nivel 2 (cierre parcial). Segunda: **los cierres se decretan con pronóstico, no con observación.** El cierre de la 60-CH del 14 de julio se anunció el 13 a las 23:10, un día antes de la primera nevada; el de la G-21 del 15 de julio se anunció a las 15:09 con 3 cm en el suelo. ERA5 es una reconstrucción de lo que ocurrió, así que el modelo puede detectar, no anticipar: para anticipar hay que alimentarlo con el pronóstico (GFS o ECMWF a 3 días, como pide el protocolo). Tercera: **la duración del cierre no la explica la nieve del día.** La 60-CH siguió cerrada 34 días con nevadas intermitentes de 5 a 30 cm; la G-21 reabrió en 4,5 días con 144 cm caídos. Son dos regímenes de despeje distintos.

### 7.2 Qué tan bien acierta cada modelo (tramo alto)

{tabla_m}

Las columnas A, B, C y D son las cuatro casillas de la sección 6: aciertos, falsas alarmas, omisiones y negativos correctos (días). Cómo leer la tabla. La columna **Origen** separa las tres cosas que se comparan. *Protocolo tal cual*: el cuadro de Lo Barnechea aplicado sin tocar nada. *Referencia*: la regla trivial "mañana como hoy", que no usa meteorología. *Propuesta*: lo nuestro; las filas marcadas como calibradas o ajustadas usan los mismos cierres observados para elegir sus parámetros, así que su puntaje es el mejor caso posible (en muestra) y no es comparable uno a uno con el protocolo, que no tuvo esa ventaja.

* **El cuadro literal no sirve solo.** Con el umbral de 50 cm para nivel 3 no detecta ninguno de los 47 días cerrados de la 60-CH ni de los 6 de la G-21 (CSI 0,00 en ambas). Bajando la vara a nivel 2 mejora poco en la 60-CH (0,15) y en la G-21 acierta 5 de 6 cierres pero con 10 falsas alarmas (CSI 0,31): en la G-21 hubo varios días con nivel 2 sin cierre, porque el régimen unidireccional y las cadenas absorben nevadas medianas.
* **La persistencia trivial ("mañana como hoy") es muy difícil de superar en la 60-CH**: CSI 0,90, porque casi todo el periodo estuvo cerrada. Cualquier modelo de esta ruta tiene que explicar la duración, no solo el inicio.
* **El modelo calibrado con umbral y persistencia** es el que mejor reproduce ambas rutas: CSI 0,85 en la 60-CH (POD 0,98; 1 omisión, el 9 de julio, cierre preventivo con 5 cm) y 0,83 en la G-21 (5 de 6 días, ninguna falsa alarma). En la G-21 supera con claridad a la persistencia trivial (0,71); en la 60-CH queda apenas debajo.
* **La regresión logística** con nieve, isoterma, lluvia y "ayer cerrado" separa muy bien los días (AUC {auc1}, CSI {f(lg['CSI'])}). Sin el término de ayer, la meteorología por sí sola llega a AUC {auc2} y CSI {f(lm['CSI'])}: la nieve explica mucho, la inercia de la decisión explica el resto. Coeficientes estandarizados: {coef}. El signo negativo de la lluvia es coherente con el cuadro: llueve cuando la isoterma está alta, y esos días no cierran por nieve.

### 7.3 Parámetros calibrados

{tabla_p}

Lectura: en la **G-21** el modelo dice "cerrar con 25 cm en 12 horas, despejar a 1,5 cm/h y reabrir con menos de 30 cm por despejar". Con 144 cm caídos entre el 15 y el 20 de julio eso da 4 a 5 días de cierre, que es lo que ocurrió. Son valores físicamente razonables y coinciden con el umbral de nivel 2 del cuadro: **en la práctica, la autoridad usó el nivel 2 del protocolo como nivel de cierre total.**

En la **60-CH** el ajuste da umbral 10 cm, despeje 0,05 cm/h y residual 0: "cierra con la primera nevada seria y no reabre en toda la temporada". Es la descripción fiel de lo que pasó (34 días cerrada con 588 cm caídos), pero no es un modelo de despeje: constata que el Sistema Cristo Redentor reabre por criterios binacionales y de seguridad de la Cuesta de los Caracoles que la nieve caída no captura. Para esta ruta el modelo útil es el de inicio del cierre (umbral 10 a 20 cm) más una duración que hay que tomar de otra fuente.

### 7.4 Qué se recomienda para el catastro

1. **Usar la versión regularizada del cuadro con el umbral de cierre en 25 cm/12 h** (nivel 2 del protocolo) como criterio de "día de cierre probable" para las rutas de montaña sin protocolo propio. Es lo que las dos autoridades hicieron de hecho.
2. **Contar la duración con el balance de nieve por despejar**, con capacidad de despeje calibrada por tipo de ruta: del orden de 1,5 cm/h en un camino municipal con maquinaria dedicada; mucho menor en un paso internacional.
3. **Tratar a ERA5 como observación, no como pronóstico.** Para anticipación operativa el mismo modelo se alimenta con el pronóstico a 3 días.
4. **Verificar la conversión de mm a cm de nieve** con alguna observación de terreno cuando exista; con 10:1 los umbrales quedan en cm de nieve fresca, que es la magnitud del cuadro.
"""

doc = BASE + "/docs/modelo_cierre.md"
s = open(doc, encoding="utf-8").read()
s2 = re.sub(r"## 7\. Resultados.*?(?=\n---\n\n## 8\.)", lambda _: res.rstrip() + "\n", s, flags=re.S)
if s2 == s: print("sección 7 sin cambios")
open(doc, "w", encoding="utf-8").write(s2)
print("sección 7 actualizada:", len(s2), "caracteres")
