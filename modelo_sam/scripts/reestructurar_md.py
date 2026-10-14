# -*- coding: utf-8 -*-
"""Reordena docs/modelo_cierre.md en partes: A protocolo tal cual, B alimentación con ERA5,
C nuestra propuesta, D verificación. Se ejecuta una sola vez (idempotente: si ya hay partes, no hace nada)."""
import re

from pathlib import Path
DOC = (Path(__file__).resolve().parents[1] / "docs" / "modelo_cierre.md").as_posix()
s = open(DOC, encoding="utf-8").read()
if "## Parte A" in s:
    print("ya reestructurado"); raise SystemExit

# --- separar en cabecera + secciones de nivel 2 -------------------------------------
partes = re.split(r"(?m)^(?=## )", s)
cab = partes[0]
sec = {}
for p in partes[1:]:
    titulo = p.splitlines()[0]
    clave = re.match(r"## (\d+|Glosario)", titulo).group(1)
    sec[clave] = p.rstrip("\n").rstrip("-").rstrip("\n") + "\n"   # quita el separador --- final si lo hay

def renum(texto, viejo, nuevo):
    texto = texto.replace(f"## {viejo}. ", f"## {nuevo}. ", 1)
    return re.sub(rf"(?m)^### {viejo}\.(\d+) ", rf"### {nuevo}.\1 ", texto)

# --- 1.4 De la hora al día: sale de la sección 3 (propuesta) y va al protocolo ----------
m = re.search(r"(?ms)^### 3\.3 De la hora al día.*", sec["3"])
dia = m.group(0); sec["3"] = sec["3"][:m.start()].rstrip("\n") + "\n"
dia = dia.replace("### 3.3 De la hora al día", "### 1.4 De la hora al día")
dia = dia.replace("El nivel del día es el nivel más alto que se alcanzó en alguna hora del día, y el protocolo (sección 7) dice que Nivel 3 vigente o inminente implica cierre total:",
                  "El protocolo (sección 7) dice que Nivel 3 vigente o inminente implica cierre total y Nivel 2 permite solo bajada. Para pasar de horas a días tomamos el nivel más alto que se alcanzó en alguna hora del día (esta agregación es nuestra; el protocolo no la explicita):")
dia = dia.replace("L_d = \\max_{t \\in d} L^*(t)", "L_d = \\max_{t \\in d} L(t)")
dia += "\nLa misma regla de decisión se aplica después, sin cambios, a nuestra versión regularizada $L^*$ (Parte C).\n"

protocolo = renum(sec["2"], "2", "1").rstrip("\n") + "\n\n" + dia
era5 = renum(sec["1"], "1", "2")
# la tabla de ingredientes remite a la sección 4 (persistencia): sigue siendo la 4
era5 = era5.replace("Piense en el modelo como una receta. Antes de la receta, los ingredientes.",
                    "El protocolo se pensó para alimentarse con pronósticos y observación en terreno. Nosotros lo alimentamos con el reanálisis ERA5. Todo lo de esta parte son decisiones de implementación nuestras: no cambian ninguna regla del protocolo, solo definen cómo se calculan sus variables de entrada.")

resumen = sec["0"].rstrip("\n") + """

**Cómo está organizado este documento.** Hay dos cosas distintas y conviene no mezclarlas. La **Parte A** es el protocolo de Lo Barnechea tal cual, solo traducido a fórmulas: ningún umbral, banda ni regla es nuestro. La **Parte B** explica cómo calculamos sus variables con ERA5: son decisiones de implementación nuestras, necesarias para poder aplicarlo, pero no modifican el protocolo. La **Parte C** es nuestra propuesta: lo que agregamos o cambiamos, y por qué. La **Parte D** verifica ambas cosas, por separado, contra los cierres reales.
"""

comparacion = """## Qué es del protocolo y qué es nuestro

| Elemento | Protocolo de Lo Barnechea (Parte A) | Nuestra propuesta (Parte C) |
|---|---|---|
| Variables | nieve en 12 h, isoterma 0 °C, precipitación líquida, visibilidad, vehículos/día | las tres primeras (las únicas calculables con ERA5) |
| Umbrales de nieve | 1, 25 y 50 cm en 12 h | 1, 25 y 50 cm en la banda media (iguales); en la banda baja cualquier nieve es nivel 3; en la alta la nieve no pasa de nivel 1 |
| Bandas de isoterma | 900–1.500 m, 1.500–2.800 m, sobre 2.800 m | las mismas, extendidas a todo el rango (bajo 1.500, 1.500–2.800, sobre 2.800) |
| Lluvia | "presencia" (nivel 2); 20 mm en 12 h con isoterma sobre 2.800 m (nivel 3) | 1 mm en 12 h como "presencia" (decisión nuestra); 20 mm igual |
| Regla de nivel | al menos un gatillante activa el nivel; manda el más alto | igual, pero completada para que más nieve nunca baje el nivel |
| Umbral de cierre total | nivel 3 (50 cm en 12 h en banda media) | **25 cm en 12 h** (el nivel 2 del protocolo), calibrado con los cierres observados |
| Duración del cierre | no la define; remite a un modelo de limpieza aparte | balance de nieve por despejar: cierra con el gatillo, reabre cuando queda menos de θ cm, despejando c cm/h |
| Probabilidad de cierre | no la calcula | regresión logística diaria con nieve, isoterma, lluvia y "ayer cerrado" |
| Con qué datos se evalúa | pronóstico y observación en terreno | reanálisis ERA5 (Parte B); detecta lo que pasó, no anticipa |

"""

banner_a = """## Parte A · El protocolo de Lo Barnechea, tal cual

Aquí no hay nada nuestro salvo la notación. Todos los números (1, 25, 50 cm; 900, 1.500, 2.800 m; 20 mm) están en el cuadro de Niveles y Gatillantes del protocolo del 3 de julio de 2026. Solo dejamos fuera visibilidad y vehículos, que no se pueden calcular con ERA5, y fijamos una cantidad mínima para "presencia de precipitación líquida", que el cuadro no da.

"""
banner_b = """## Parte B · Cómo lo alimentamos con ERA5

Decisiones de implementación nuestras. No cambian ninguna regla del protocolo: definen cómo se obtienen sus variables de entrada a partir de un reanálisis en vez de pronósticos y observación en terreno.

"""
banner_c = """## Parte C · Nuestra propuesta

Lo que agregamos o cambiamos respecto del protocolo, y por qué. Tres piezas: (3) cerrar los huecos del cuadro para que sea monótono, (4) una regla de duración del cierre, y (5) un modelo estadístico de probabilidad. El umbral de cierre de 25 cm en 12 h que resulta de la calibración (sección 7.3) es la propuesta central.

"""
banner_d = """## Parte D · Verificación

Cómo se mide el acierto y qué dio cada cosa, separando siempre las filas que son protocolo tal cual de las que son propuesta nuestra.

"""

nuevo = (cab + resumen + "\n---\n\n" + comparacion + "---\n\n"
         + banner_a + protocolo + "\n---\n\n"
         + banner_b + era5 + "\n---\n\n"
         + banner_c + sec["3"] + "\n---\n\n" + sec["4"] + "\n---\n\n" + sec["5"] + "\n---\n\n"
         + banner_d + sec["6"] + "\n---\n\n" + sec["7"] + "\n---\n\n" + sec["8"] + "\n---\n\n" + sec["Glosario"])
nuevo = re.sub(r"\n{3,}", "\n\n", nuevo)
open(DOC, "w", encoding="utf-8").write(nuevo)
print("reestructurado:", [l for l in nuevo.splitlines() if l.startswith("## ")])
