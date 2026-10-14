# Protocolo de cierre de Lo Barnechea frente al índice de severidad de Walker

Comparación entre los "Niveles y Gatillantes" del protocolo del 3 de julio de 2026 y las categorías de severidad del índice invernal de Nebraska (NEWINS), como primer paso para adaptar el método de Walker al modelo de cierre de la 60-CH y la G-21.

Versión 1 · 5 de octubre de 2026 · Parte 2 del catastro FONDEF (condición invernal de caminos de montaña)

---

## 0. Fuentes

- **Protocolo**: *Protocolo cierre de caminos públicos del Centro de Montaña Lo Barnechea*, 3 de julio de 2026 (firmado), secciones 4 (variables), 5 (definiciones), 6 (niveles y gatillantes), 7 (cierre) y 8 (apertura).
- **Walker**: Walker, C., Anderson, M. y Esmaeili, B. (2018). *Development of the Nebraska Department of Transportation Winter Severity Index*. NDOT SPR-P1-(17)M054. Tablas 3.2 a 3.5 y ecuaciones (1) y (2).
- **Guía de adaptación**: Sturges, L., Fay, L., Clouser, K. y Villwock-Witte, N. (2020). *Evaluation of SSI and WSI Variables*. Clear Roads CR 18-03. Resumen del "Walker Method" (pp. 23–24) y guía de seis pasos para que una agencia construya su propio índice (cap. 2, pp. 88–112).

---

## 1. Los dos marcos en pocas palabras

**El índice de Walker (NEWINS).** Fue hecho para el Departamento de Transporte de Nebraska. Mira cada tormenta de nieve por separado y le pone una nota de 1 (traza, sin operaciones) a 6 (alta, impacto significativo, operaciones al máximo y posible suspensión). Para eso usa siete variables meteorológicas: nieve caída, tasa de nevada, viento, temperatura del aire, fracción del distrito afectada, duración y visibilidad. Cada variable se convierte primero en una nota de 1 a 6 según una tabla de cortes; después se promedian las siete notas con pesos fijos, y la nieve caída pesa el 80 %. Al final de la temporada se suman las notas de todas las tormentas para obtener un índice estacional.

En fórmulas: si $c_i$ es la nota (1 a 6) de la variable $i$ y $\beta_i$ su peso,

$$C_{\text{evento}} = \sum_{i=1}^{7} \beta_i \, c_i, \qquad \beta = (0{,}80;\ 0{,}05;\ 0{,}05;\ 0{,}05;\ 0{,}02;\ 0{,}02;\ 0{,}01)$$

en el orden nieve, tasa, viento, temperatura, área, duración, visibilidad (los pesos suman 1). El índice de la temporada es

$$\text{NEWINS} = \frac{\sum_{k=1}^{6} k \cdot f_k}{100},$$

donde $f_k$ es el número de tormentas que quedaron en la categoría $k$.

**El protocolo de Lo Barnechea.** Define tres alertas (preventiva, operativa con cierre parcial, crítica con cierre absoluto) para una sola ruta y una ventana de 12 horas. La regla es distinta a la de Walker: **basta un gatillante** para activar un nivel y manda el nivel más alto que se cumpla. No hay pesos ni promedio: una visibilidad de 20 m, sola, ya es Alerta 3.

**La diferencia de fondo.** Walker *promedia* (una variable extrema pesa poco si no es la nieve); el protocolo *toma el máximo* (cualquier variable extrema decide). Walker es un índice para medir cuán dura fue una tormenta o una temporada; el protocolo es una regla para decidir qué hacer ahora.

---

## 2. Tabla 1 – Niveles: categorías de Walker frente a alertas del protocolo

**En palabras.** Walker describe cada categoría por sus consecuencias sobre el camino y la operación (Tabla 3.2 del informe): si hay cierres, cómo está la calzada, cuánto baja la velocidad, cuánta maquinaria sale y si se cumple el objetivo de servicio de Nebraska (volver a menos de 16 km/h bajo la velocidad límite dentro de 6 horas después de que deja de nevar). La tabla pone al lado el nivel del protocolo cuyas medidas se parecen más.

| Categoría Walker | Acceso | Calzada | Velocidad | Operación | Objetivo de servicio | Protocolo (nivel y medidas principales) |
|----------|---------|----------|----------|----------|---------|------------------------------|
| 1 Traza | sin cierres | mojada | sin reducción | sin despliegue | se cumple | **Sin alerta** (el protocolo no define nivel 0) |
| 2 Marginal | sin cierres | mojada | sin reducción | despliegue mínimo | se cumple | **Sin alerta** |
| 3 Leve | cierres mínimos | nieve y hielo en manchas | reducción mínima | despliegue parcial | probable | **Alerta 1 (preventiva)**: reunión de coordinación, revisión de recursos, cadenas obligatorias, modelo de limpieza, plan de bajada; sin cierre |
| 4 Realzada | cierres ocasionales | parcialmente cubierta | reducción considerable | despliegue completo | improbable | **Alerta 2 (cierre parcial)**: cadenas en puntos de control, maquinaria de centros de esquí, prioridad a tramos críticos; **no se permite subir**, solo bajar |
| 5 Moderada | cierres numerosos | cubierta entera | reducción significativa | despliegue completo | no se cumple | **Alerta 2** o **Alerta 3**, según gatillante |
| 6 Alta | cierres significativos | intransitable | reducción significativa | despliegue completo, posible suspensión | no se cumple | **Alerta 3 (cierre absoluto)**: cierre total preventivo o durante el evento; evaluación de avalanchas y remoción en masa antes de reabrir; solo acceden equipos de limpieza, bomberos y Carabineros |

**Notas de lectura.**

1. Walker tiene seis escalones y el protocolo tres (más un "sin alerta" implícito), así que el emparejamiento no es uno a uno. Proponemos: 1–2 → sin alerta; 3 → Alerta 1; 4–5 → Alerta 2; 5–6 → Alerta 3. La categoría 5 queda en la frontera.
2. En Walker los "cierres" son de caminos dentro de un distrito (algunos sí, otros no). En el protocolo el camino es uno solo y el cierre es todo o nada, con un paso intermedio (cerrado solo de subida).
3. En Walker la velocidad y el cierre son **consecuencias** que sirven para definir la categoría; en el protocolo la velocidad (atochamiento bajo 5 km/h por 2 horas, sección 7) es un **gatillante** de cierre.
4. El objetivo de servicio de Walker (recuperar velocidad en 6 h) no tiene equivalente directo en el protocolo; lo más parecido son los criterios de apertura (dos vías despejadas, más de 15 km/h, visibilidad sobre 20 m) y el modelo de limpieza municipal (sección 9). En nuestro modelo eso corresponde a la memoria del cierre (despeje $c$ y umbral de reapertura $\theta$).
5. Según lo calibrado en `modelo_sam/docs/modelo_cierre.md`, los cierres reales de julio–agosto 2026 ocurrieron con 30–50 cm en 12 h, es decir, en el nivel 2 del protocolo; ese nivel es el que en la práctica cumple el papel de las categorías 4–5 de Walker.

---

## 3. Tabla 2 – Variables: quién usa qué y si podemos calcularlo

**En palabras.** Ponemos en una sola lista todas las variables de los dos marcos. Para cada una indicamos su peso en Walker, si es gatillante en el protocolo y cómo la obtenemos (o no) con los datos ERA5 que ya procesamos por tramo.

| Variable | Walker (peso $\beta$) | Protocolo | Nuestro equivalente con ERA5 | Estado |
|---|---|---|---|---|
| Nieve acumulada | sí, total de la tormenta (0,80) | sí, cm en 12 h, por tramo y cota (A1, A2, A3) | nieve cm = SWE mm × 10 (ERA5-Land), suma en 12 h por tramo | disponible |
| Tasa de nevada | sí, total / duración (0,05) | no (implícita: cm en 12 h) | cm/h por bloque de 6 h o por episodio | disponible |
| Viento | sí, velocidad media (0,05) | no es gatillante (el texto lo menciona como exposición) | `viento_ms` y `viento_max_ms` (ERA5-Land, 10 m) ya están en `era5_tramos_6h.csv`; los GRIB nuevos de la carpeta *Viento* (60-CH y G-21, tramos alto y medio) quedan por incorporar | disponible; por actualizar |
| Temperatura del aire | sí (0,05); más frío = más severo | no directamente; usa la isoterma 0 °C | `t2m_C` (ERA5-Land, 2 m) por tramo y bloque | disponible |
| Fracción del área afectada | sí, fracción del distrito (0,02) | no explícita; "desagregada por tramo y cota" | fracción de tramos (o de celdas ERA5 ponderadas) con nieve sobre umbral | calculable |
| Duración | sí, horas de precipitación sólida (0,02) | no (ventana fija de 12 h) | `horas_nevando` por bloque; horas de nevada por episodio en la serie horaria | disponible |
| Visibilidad | sí (0,01) | sí, en metros (A1, A2, A3) y criterio de apertura | ERA5 no la trae | sin fuente |
| Isoterma 0 °C | no | sí, bandas 900–1.500, 1.500–2.800 y sobre 2.800 m | deg0l de ERA5 convertida a m s. n. m. con la cota DEM; censurada a 0 | disponible |
| Precipitación líquida | no | sí: "presencia" (A2) y ≥ 20 mm/12 h con isoterma sobre 2.800 m (A3) | lluvia ERA5-Land en 12 h por tramo | disponible |
| Tránsito de subida | no | sí, vehículos/día entre 08:00 y 13:00 (umbral 3.500) | sin fuente | sin fuente |
| Congestión | no como entrada (es consecuencia) | sí, < 5 km/h por 2 h (Waze), criterio de cierre | sin fuente | sin fuente |
| Peligros naturales | no | sí, evaluación técnica de avalancha, remoción en masa, rocas | solo indirecto (nieve ≥ 50 cm, lluvia sobre nieve) | parcial |
| Condición sanitaria | no | sí, falla de agua o baños más de 24 h | sin fuente | sin fuente |

---

## 4. Tabla 3 – Umbrales en las mismas unidades

**En palabras.** Pasamos los cortes de Walker (Tabla 3.4, en unidades del sistema internacional) y los umbrales del protocolo a las mismas unidades para ver dónde cae cada uno. Para comparar la nieve, el protocolo se expresa también como tasa media: 25 cm en 12 h equivale a unos 2,1 cm por hora.

### 4.1 Cortes de Walker por categoría

| Variable | 1 Traza | 2 Marginal | 3 Leve | 4 Realzada | 5 Moderada | 6 Alta |
|---|---|---|---|---|---|---|
| Nieve (cm por tormenta) | < 2,4 | < 4,9 | < 7,5 | < 12,6 | < 17,5 | ≥ 17,5 |
| Tasa de nevada (cm/h) | < 0,4 | < 0,6 | < 0,9 | < 1,1 | < 1,5 | ≥ 1,5 |
| Viento (m/s) | ≤ 2,7 | ≤ 4,9 | ≤ 8,1 | ≤ 10,7 | ≤ 13,9 | > 13,9 |
| Temperatura del aire (°C) | > 1,7 | ≤ 1,7 | ≤ −1,7 | ≤ −3,9 | ≤ −7,2 | < −9,4 |
| Fracción del área | ≤ 0,2 | < 0,4 | < 0,5 | < 0,75 | < 1,0 | 1,0 |
| Duración (h) | ≤ 2 | ≤ 3 | ≤ 4 | ≤ 5 | ≤ 8 | > 8 |
| Visibilidad (km) | > 8,0 | ≤ 8,0 | < 6,4 | < 5,6 | < 4,8 | < 4,0 |

Cómo se eligieron (según el informe): nieve, temperatura y área se repartieron en tramos de ancho parecido; tasa, duración y visibilidad, de modo que cada categoría tuviera un número parecido de observaciones (cuantiles); el viento siguió una escala de Beaufort modificada.

### 4.2 Umbrales del protocolo y dónde caen en la escala de Walker

| Variable | Alerta 1 | Alerta 2 | Alerta 3 | Categoría Walker equivalente |
|---|---|---|---|---|
| Nieve en 12 h (cm) | > 1 y < 25 (cualquier isoterma) | > 25 y < 50, isoterma 1.500–2.800 m | > 1 y < 50 con isoterma 900–1.500 m; ≥ 50 con isoterma 1.501–2.800 m | A1 recorre de 1 a 6; A2 y A3 son siempre 6 |
| Tasa media equivalente (cm/h) | 0,08 a 2,1 | 2,1 a 4,2 | ≥ 4,2 (o ≥ 0,08 con isoterma baja) | A1 recorre de 1 a 6; A2 y A3 son siempre 6 |
| Visibilidad | > 50 y ≤ 100 m | > 21 y ≤ 50 m | ≤ 20 m | las tres son 6 (< 4 km) |
| Isoterma 0 °C | no condiciona | 1.500–2.800 m (con nieve) | 900–1.500 m (con nieve) o > 2.800 m (con lluvia ≥ 20 mm) | sin equivalente |
| Precipitación líquida | – | presencia | ≥ 20 mm en 12 h con isoterma > 2.800 m | sin equivalente |
| Tránsito de subida (veh/día, 08–13 h) | > 0 y < 3.500 | > 3.500 | – | sin equivalente |
| Condición sanitaria | – | – | falla > 24 h | sin equivalente |

**Lo que muestra la tabla.**

1. **Las escalas no calzan.** El techo de Walker (17,5 cm por tormenta, o 1,5 cm/h) cae dentro de la Alerta 1 del protocolo. Todo lo que en la cordillera es Alerta 2 o 3 sería "categoría 6" en Nebraska. Lo mismo con la visibilidad: Walker trabaja en kilómetros y el protocolo en decenas de metros. Usar los cortes de Nebraska tal cual pondría casi todos nuestros eventos de interés en la categoría 6 y el índice no distinguiría nada.
2. **Lo transferible es el procedimiento, no los números.** Los cortes deben recalcularse con nuestros datos usando las mismas reglas de Walker (tramos de ancho parecido o cuantiles), y anclarse a los umbrales del protocolo (1, 25 y 50 cm en 12 h) y a lo observado (cierres con 30–50 cm en 12 h).
3. **La temperatura juega al revés.** En Walker más frío es más severo, porque la sal funciona peor. En el protocolo el peligro está en los dos extremos: isoterma baja (900–1.500 m) significa que nieva en todo el camino, incluso en la parte baja, y eso ya es Alerta 3; isoterma alta (sobre 2.800 m) con lluvia fuerte significa riesgo de remoción en masa, también Alerta 3. Una lectura posible (nuestra, no del protocolo) es que la isoterma cumple en la montaña el papel que el "área afectada" cumple en Walker: dice qué fracción del camino queda bajo nieve.
4. **Ventana de tiempo.** Walker mide por tormenta (de principio a fin de la precipitación sólida, con duración variable). El protocolo mide en ventanas fijas de 12 h. Nuestro pipeline trabaja en bloques de 6 h y reconoce episodios en la serie horaria, así que puede alimentar las dos lógicas.

---

## 5. Brechas y qué implican para adaptar Walker

**Lo que Walker tiene y el protocolo no:** viento, temperatura del aire, duración, tasa de nevada y fracción del área afectada. Todas se pueden calcular con ERA5; el viento ya está en la base por bloque y se actualizará con los GRIB nuevos de la carpeta *Viento*.

**Lo que el protocolo tiene y Walker no:** isoterma 0 °C, lluvia en altura, peligros naturales (avalancha, remoción en masa), tránsito, congestión y condición sanitaria. Las dos primeras están en ERA5; las demás no tienen fuente meteorológica y quedarían como información externa.

**Visibilidad:** está en los dos marcos, pero no en ERA5. En Walker pesa solo 0,01, así que dejarla fuera casi no cambia el índice; en el protocolo, en cambio, puede decidir sola un nivel.

**Cómo se ordena la adaptación según la guía de Clear Roads (seis pasos):**

1. *Definir objetivos*: aquí, anticipar y explicar cierres por tramo, no solo medir la temporada.
2. *Quién se sienta a la mesa*: Vialidad, Municipalidad, centros de esquí y Carabineros (los mismos actores del protocolo).
3. *Variables y fuentes*: Tabla 2 de este documento.
4. *Método*: categorías 1–6 al estilo Walker, con cortes recalculados para la cordillera (Tabla 3) y pesos por revisar; decidir si se combina con suma ponderada (Walker) o con máximo (protocolo).
5. *Aplicación*: índice por bloque de 6 h y por episodio, por tramo, además del índice estacional.
6. *Evaluación*: contrastar contra los cierres reales reconstruidos (como en `modelo_cierre.md`) y ajustar.

La guía insiste en que no conviene adoptar tal cual un índice hecho para otro lugar: hay que aprender del método y construir uno propio para el clima, el relieve y las reglas de operación locales. Las tablas de arriba muestran por qué ese consejo aplica con fuerza aquí.
