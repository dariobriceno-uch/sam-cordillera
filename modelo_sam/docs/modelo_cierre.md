# Modelo de cierre de caminos de montaña por nieve

Cómo se transforma el protocolo de Lo Barnechea en una regla que se puede calcular, y cómo se comprueba contra los cierres reales de la 60-CH y la G-21.

Versión 2 · 5 de octubre de 2026 (bloques de 6 horas; la versión 1, hora a hora, es del 9 de septiembre) · Parte 2 del catastro FONDEF (condición invernal de caminos de montaña)

---

## 0. Resumen en una página

**El problema.** Cada invierno, la autoridad decide si cierra o no un camino de montaña. Lo hace mirando la nieve que cayó, a qué altura está la línea donde el aire pasa de 0 °C (la "isoterma cero"), si llueve, cuánto se ve y cuántos autos suben. El protocolo de Lo Barnechea del 3 de julio de 2026 ordena esa decisión en tres niveles de alerta con umbrales concretos: por ejemplo, "más de 25 cm de nieve en 12 horas con isoterma entre 1.500 y 2.800 m" es Alerta 2 y significa cierre parcial.

**Lo que hicimos.** Tomamos ese cuadro y lo escribimos como una regla exacta que un computador puede aplicar en bloques de 6 horas (00–06, 06–12, 12–18 y 18–24, hora local). En vez de observaciones en terreno, la alimentamos con ERA5, un modelo meteorológico global que reconstruye el clima de cada hora sobre una grilla de unos 9 km; esas horas se juntan de a seis. Con eso obtenemos, para cada bloque de julio y agosto de 2026 y para cada tramo de las dos rutas, el nivel de alerta que el protocolo habría indicado.

**Cómo lo comprobamos.** Un colega reconstruyó, a partir de los comunicados oficiales, en qué horas cada ruta estuvo realmente cerrada. Comparamos día a día lo que el protocolo habría dicho con lo que la autoridad hizo, y contamos aciertos, omisiones y falsas alarmas.

**Lo que agregamos al protocolo.** Tres cosas que el cuadro no tiene: (1) reglas para las combinaciones que el cuadro no cubre, de modo que "más nieve" nunca baje la alerta; (2) una memoria del cierre, porque el camino no se reabre cuando deja de nevar sino cuando se termina de despejar; (3) una versión estadística clásica (regresión logística) que dice qué probabilidad de cierre tiene un día dadas sus condiciones.

**Lo que no puede hacer.** ERA5 no trae visibilidad ni conteo de vehículos, así que esos dos gatillantes del protocolo quedan fuera. Y como solo tenemos dos meses y dos rutas, los números calibrados describen esta temporada; la forma del modelo es lo que sirve para el resto del catastro.

**Cómo está organizado este documento.** Hay dos cosas distintas y conviene no mezclarlas. La **Parte A** es el protocolo de Lo Barnechea tal cual, solo traducido a fórmulas: ningún umbral, banda ni regla es nuestro. La **Parte B** explica cómo calculamos sus variables con ERA5: son decisiones de implementación nuestras, necesarias para poder aplicarlo, pero no modifican el protocolo. La **Parte C** es nuestra propuesta: lo que agregamos o cambiamos, y por qué. La **Parte D** verifica ambas cosas, por separado, contra los cierres reales.

---

## Qué es del protocolo y qué es nuestro

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

---

## Parte A · El protocolo de Lo Barnechea, tal cual

Aquí no hay nada nuestro salvo la notación. Todos los números (1, 25, 50 cm; 900, 1.500, 2.800 m; 20 mm) están en el cuadro de Niveles y Gatillantes del protocolo del 3 de julio de 2026. Solo dejamos fuera visibilidad y vehículos, que no se pueden calcular con ERA5, y fijamos una cantidad mínima para "presencia de precipitación líquida", que el cuadro no da.

## 1. El cuadro del protocolo escrito como regla

### 1.1 En palabras

El protocolo dice: "el nivel de alerta se establece cuando se verifica al menos un gatillante de los definidos para ese nivel". Si en un mismo bloque de 6 horas se cumplen gatillantes de dos niveles, manda el más alto. Con solo nieve, isoterma y lluvia, el cuadro se reduce a:

| Nivel | Se activa si... | Consecuencia |
|---|---|---|
| 1 Preventiva | nevó entre 1 y 25 cm en 12 h (a cualquier altura de isoterma) | reunión de coordinación, cadenas obligatorias |
| 2 Operativa | nevó entre 25 y 50 cm en 12 h **y** la isoterma está entre 1.500 y 2.800 m; **o** hay precipitación líquida | cierre parcial: solo bajada |
| 3 Crítica | nevó entre 1 y 50 cm con isoterma entre 900 y 1.500 m; **o** nevó 50 cm o más con isoterma entre 1.500 y 2.800 m; **o** llovió 20 mm o más con isoterma sobre 2.800 m | cierre total |

Dos detalles que hubo que decidir porque el cuadro no los precisa:

* "Presencia de precipitación líquida" no dice cuánta. Tomamos 1 mm en 12 horas como mínimo para que una llovizna de modelo no active una alerta.
* Los gatillantes de nivel 1 y 3 se solapan (entre 1 y 50 cm con isoterma baja cumple los dos). Como manda el nivel más alto, gana el 3, que es lo que el protocolo quiere.

### 1.2 En fórmula

Cada gatillante es una pregunta de sí o no. Usamos la notación $\mathbb{1}[\text{condición}]$, que vale 1 si la condición se cumple y 0 si no. Por ejemplo, $\mathbb{1}[S > 25]$ vale 1 cuando cayeron más de 25 cm y 0 en caso contrario. Multiplicar dos de estas equivale a exigir las dos condiciones a la vez ("y").

$$
\begin{aligned}
\text{Nivel 1:}\quad & g_{11} = \mathbb{1}[\,1 < S < 25\,] \\[2pt]
\text{Nivel 2:}\quad & g_{21} = \mathbb{1}[\,25 \le S < 50\,]\cdot\mathbb{1}[\,1500 \le Z \le 2800\,], \qquad g_{22} = \mathbb{1}[\,R \ge 1\,] \\[2pt]
\text{Nivel 3:}\quad & g_{31} = \mathbb{1}[\,1 < S < 50\,]\cdot\mathbb{1}[\,900 \le Z \le 1500\,], \\
                     & g_{32} = \mathbb{1}[\,S \ge 50\,]\cdot\mathbb{1}[\,1500 < Z \le 2800\,], \\
                     & g_{33} = \mathbb{1}[\,R \ge 20\,]\cdot\mathbb{1}[\,Z > 2800\,]
\end{aligned}
$$

El nivel del bloque es el mayor nivel que tenga algún gatillante en 1:

$$
L(t) = \max\{\, \ell \in \{1,2,3\} : \text{algún } g_{\ell j}(t) = 1 \,\}, \qquad L(t) = 0 \text{ si ninguno.}
$$

**Ejemplo.** En el bloque de 06 a 12 h del día $d$ cayeron $S = 32$ cm en las últimas 12 horas (desde las 00:00), no llovió ($R = 0$) y la isoterma está en $Z = 2\,100$ m. Entonces $g_{11} = 0$ (32 no está entre 1 y 25), $g_{21} = 1$ (32 está entre 25 y 50, y 2.100 entre 1.500 y 2.800), $g_{22} = 0$, y los tres del nivel 3 valen 0. El nivel es $L = 2$: cierre parcial, solo bajada.

### 1.3 Lo que el cuadro deja sin definir

Al escribirlo como regla salta a la vista que hay combinaciones sin respuesta. Con la isoterma a 3.000 m y 60 cm de nieve, ningún gatillante se cumple y el nivel vuelve a 0: **nevar más puede bajar la alerta**. Lo mismo con 30 cm e isoterma a 1.200 m (cae en nivel 3 por $g_{31}$, bien), pero con 55 cm e isoterma a 1.200 m ningún gatillante se cumple. Son huecos del texto, no intenciones del protocolo, y hay que cerrarlos para que la regla sea aplicable a cualquier ruta.

### 1.4 Del bloque al día

La autoridad cierra por días, no por horas. El protocolo (sección 7) dice que Nivel 3 vigente o inminente implica cierre total y Nivel 2 permite solo bajada. Para pasar de bloques a días tomamos el nivel más alto que se alcanzó en alguno de los cuatro bloques del día (esta agregación es nuestra; el protocolo no la explicita):

$$
L_d = \max_{t \in d} L(t), \qquad \hat C_d = \mathbb{1}[L_d = 3] \quad (\text{cierre total previsto}), \qquad \hat P_d = \mathbb{1}[L_d = 2] \quad (\text{cierre parcial previsto}).
$$

La misma regla de decisión se aplica después, sin cambios, a nuestra versión regularizada $L^*$ (Parte C).

---

## Parte B · Cómo lo alimentamos con ERA5

Decisiones de implementación nuestras. No cambian ninguna regla del protocolo: definen cómo se obtienen sus variables de entrada a partir de un reanálisis en vez de pronósticos y observación en terreno.

## 2. Los ingredientes: qué mide cada variable

El protocolo se pensó para alimentarse con pronósticos y observación en terreno. Nosotros lo alimentamos con el reanálisis ERA5. Todo lo de esta parte son decisiones de implementación nuestras: no cambian ninguna regla del protocolo, solo definen cómo se calculan sus variables de entrada.

**Las rutas y sus tramos.** Trabajamos con dos rutas y dos tramos en cada una. En la 60-CH, el tramo *alto* va desde la barrera de Guardia Vieja hasta el túnel Cristo Redentor (es exactamente el trecho que la autoridad cierra) y el tramo *medio* es el trecho anterior, de Río Blanco a Guardia Vieja. En la G-21, el tramo *alto* es Farellones y los accesos a los centros de esquí, y el tramo *medio* es la subida de curvas entre La Ermita y Curva 32.

**Los bloques de 6 horas.** Todo está en hora local de Chile (UTC−4), del 1 de julio al 31 de agosto de 2026. ERA5 entrega datos hora a hora; los juntamos en cuatro bloques por día, de 00 a 06, de 06 a 12, de 12 a 18 y de 18 a 24 horas: 248 bloques por tramo. En cada bloque, la nieve y la lluvia se suman; la temperatura, el viento y la isoterma se promedian (guardando también el mínimo y el máximo de las seis horas); el espesor del manto es el del final del bloque. ERA5 rotula la nieve con la hora en que termina de caer, así que la nieve rotulada 01:00 a 06:00 es la del bloque 00–06. Del estado observado se guarda cuántas horas del bloque estuvo la ruta en cada estado; el bloque cuenta como cerrado si hubo al menos una hora de cierre por meteorología.

**Cuatro números por bloque.** De todo lo que entrega ERA5 el protocolo usa cuatro cosas:

| Nombre | Qué es | Unidad | De dónde sale |
|---|---|---|---|
| Nieve caída en 12 h, $S$ | cuántos centímetros de nieve cayeron en las últimas 12 horas (este bloque y el anterior) | cm | suma de la nieve de ERA5-Land |
| Lluvia en 12 h, $R$ | cuántos milímetros de agua líquida cayeron en las últimas 12 horas | mm | precipitación total menos nieve, ERA5-Land |
| Isoterma 0 °C, $Z$ | a qué altura sobre el nivel del mar el aire está a 0 °C: más abajo nieva, más arriba llueve | m s.n.m. | ERA5 más la altura del terreno |
| Nieve por despejar, $N$ | cuánta nieve queda sobre el camino después de descontar lo que se retira en cada bloque | cm | se calcula (sección 4) |

Los símbolos ($S$, $R$, $Z$, $N$) son solo etiquetas cortas para no repetir el nombre completo en cada fórmula.

### 2.1 De milímetros de agua a centímetros de nieve

ERA5 entrega la nieve como "milímetros de agua equivalente": cuánta agua daría esa nieve al derretirse. El protocolo habla de centímetros de nieve. La conversión depende de qué tan esponjosa es la nieve. Nieve recién caída típica pesa unos 100 kg por metro cúbico, diez veces menos que el agua, así que **1 mm de agua equivale a 1 cm de nieve fresca** (razón 10:1). Nieve seca de alta cordillera puede ser más liviana (12:1 o 14:1); nieve húmeda, más pesada (6:1). Usamos 10:1 como valor de referencia y lo dejamos como parámetro ajustable.

En fórmula: si $sf(t)$ son los milímetros de nieve (en agua) caídos en el bloque de 6 horas $t$,

$$
S(t) = a \big[\, sf(t) + sf(t-1) \,\big], \qquad a = \frac{100}{\rho_{\text{fresca}}} = 1 \text{ cm por mm cuando } \rho_{\text{fresca}} = 100 \text{ kg/m}^3 .
$$

Se lee: "la nieve de las últimas 12 horas es la nieve de este bloque más la del bloque anterior, convertida a centímetros". Como los bloques duran 6 horas, dos bloques son exactamente la ventana de 12 horas del protocolo. Una consecuencia: la ventana avanza de a 6 horas y no de a una, así que una nevada intensa que cae a caballo entre dos ventanas puede sumar algo menos que en el cálculo hora a hora (en la 60-CH el máximo pasa de 51,6 a 50,0 cm).

De la misma forma, la lluvia en 12 horas es la suma de la lluvia de los dos bloques:

$$
R(t) = \big[\, tp(t) - sf(t) \,\big]^{+} + \big[\, tp(t-1) - sf(t-1) \,\big]^{+}
$$

y la isoterma $Z(t)$ es el promedio de las 12 horas de los dos bloques.

donde $tp$ es la precipitación total y el signo $[\cdot]^{+}$ solo dice "si sale negativo, tómese como cero".

### 2.2 La isoterma cero y por qué hay que corregirla

ERA5 no entrega la altura de la isoterma sobre el nivel del mar sino **sobre el suelo del modelo**. Como el modelo tiene un relieve suavizado, en una celda que "está" a 3.200 m una isoterma reportada a 300 m sobre el suelo significa 3.500 m s.n.m. Además, cuando toda la columna de aire está bajo 0 °C, ERA5 reporta 0: no dice cuánto más abajo estaría la isoterma, solo que está bajo el suelo.

Por eso hacemos dos cosas: sumamos la altura media del terreno de la celda (del modelo digital de elevación Copernicus, el mismo que usa el catastro) y usamos, para cada ruta, las celdas de menor altura disponibles, donde ese "bajo el suelo" casi nunca ocurre. La altura de la isoterma cambia poco en 30 o 50 km, así que la celda baja del valle sirve para toda la ruta.

$$
Z(t) = \bar{h}_{\text{DEM}} + \delta(t)
$$

($\delta$ es lo que entrega ERA5, $\bar{h}_{\text{DEM}}$ la altura del terreno). Cuando $\delta = 0$ el valor queda marcado como "censurado": sabemos que la isoterma está más abajo, no cuánto.

### 2.3 Promediar las celdas por donde pasa el camino

Cada tramo cruza entre 2 y 5 celdas de ERA5-Land. No todas pesan igual: si el camino recorre 12 km dentro de una celda y 800 m dentro de otra, la primera cuenta quince veces más. El valor del tramo es el promedio de sus celdas ponderado por la longitud de camino que hay en cada una:

$$
x_{\text{tramo}}(t) = \frac{\sum_k \ell_k\, x_k(t)}{\sum_k \ell_k}
$$

($\ell_k$ = metros de camino dentro de la celda $k$; $x_k$ = el valor en esa celda). Las longitudes salen de cruzar la geometría oficial de Vialidad con la grilla de ERA5.

---

## Parte C · Nuestra propuesta

Lo que agregamos o cambiamos respecto del protocolo, y por qué. Tres piezas: (3) cerrar los huecos del cuadro para que sea monótono, (4) una regla de duración del cierre, y (5) un modelo estadístico de probabilidad. El umbral de cierre de 25 cm en 12 h que resulta de la calibración (sección 7.3) es la propuesta central.

## 3. Versión regularizada: la misma tabla, sin huecos

### 3.1 En palabras

La idea física detrás del cuadro es sencilla. Si la isoterma está **baja** (bajo 1.500 m), toda la ruta recibe nieve y cualquier acumulación es peligrosa: nivel 3 con poca nieve. Si está en la banda **media** (1.500 a 2.800 m), rigen los umbrales de 25 y 50 cm. Si está **alta** (sobre 2.800 m), la nieve cae solo en la parte más alta y el riesgo dominante es la lluvia sobre el manto (aludes, remoción en masa), que el cuadro pone en nivel 3 con 20 mm.

Ordenando la tabla por banda de isoterma y umbral de nieve queda:

| Banda de isoterma | Nivel 1 desde | Nivel 2 desde | Nivel 3 desde | Lluvia |
|---|---|---|---|---|
| baja: $Z < 1500$ | 1 cm | 1 cm | 1 cm | — |
| media: $1500 \le Z \le 2800$ | 1 cm | 25 cm | 50 cm | — |
| alta: $Z > 2800$ | 1 cm | nunca por nieve | nunca por nieve | nivel 2 si $R \ge 1$ mm; nivel 3 si $R \ge 20$ mm |

Esta tabla da exactamente lo mismo que el cuadro en todos los casos que el cuadro define, y además responde en los que no. Y tiene la propiedad que uno espera: **más nieve o más lluvia nunca bajan la alerta**.

### 3.2 En fórmula

Sea $s_\ell(b)$ el umbral de nieve del nivel $\ell$ en la banda $b$ (los valores de la tabla). El nivel regularizado es

$$
L^*(t) = \max\Big( \max\{\ell : S(t) \ge s_\ell(b)\},\ \ 2\cdot\mathbb{1}[b = \text{alta},\, R \ge 1],\ \ 3\cdot\mathbb{1}[b = \text{alta},\, R \ge 20] \Big).
$$

Se lee: "el nivel es el mayor cuyo umbral de nieve se alcanzó en la banda actual; y si la isoterma está alta y llueve, al menos 2, y con 20 mm, 3".

---

## 4. Memoria del cierre: el camino se reabre cuando se despeja, no cuando para de nevar

### 4.1 En palabras

El cuadro solo dice cuándo cerrar. En la realidad, el cierre dura mientras la maquinaria despeja. En la 60-CH, el cierre que empezó el 14 de julio de 2026 duró 34 días. Para reproducir eso, el modelo lleva una cuenta de la nieve acumulada sobre el camino, como un estanque: en cada bloque de 6 horas entra la nieve que cae y sale una cantidad fija $6c$, donde $c$ es la capacidad de despeje (centímetros de nieve por hora que la maquinaria, la compactación y el derretimiento quitan). Si el estanque está vacío, no puede bajar de cero.

El camino cierra cuando el protocolo marca nivel 3, y se mantiene cerrado mientras el estanque tenga más de $\theta$ centímetros (la nieve residual con la que la autoridad acepta reabrir). Cuando baja de $\theta$, reabre.

### 4.2 En fórmula

$$
N(t) = \max\big\{0,\ N(t-1) + a\, sf(t) - c\,\Delta\big\}, \qquad \Delta = 6 \text{ h}
$$

"La nieve por despejar de este bloque es la del bloque anterior, más la que cayó, menos lo que se despejó en 6 horas; y nunca menos que cero."

$$
C(t) = \begin{cases}
1 & \text{si } L^*(t) = 3 \quad \text{(el protocolo ordena cerrar)} \\
1 & \text{si } C(t-1) = 1 \ \text{y}\ N(t) > \theta \quad \text{(sigue cerrado porque falta despejar)} \\
0 & \text{en otro caso} \quad \text{(abierto)}
\end{cases}
$$

**Ejemplo.** Supongamos $c = 0{,}5$ cm/h y $\theta = 10$ cm. Una tormenta deja 60 cm en 12 horas: el nivel llega a 3 y el camino cierra. Cuando para de nevar, el estanque tiene unos 54 cm (60 menos las 12 horas de despeje). A 0,5 cm por hora (3 cm por bloque), bajar de 54 a 10 cm toma unos 15 bloques, 88 horas: el camino reabre casi cuatro días después de que dejó de nevar. Si a mitad del despeje cae otra nevada de 20 cm, el plazo se alarga 40 horas más (unos 7 bloques).

### 4.3 Cómo se eligen $c$ y $\theta$

No se inventan: se prueban muchas combinaciones (una grilla de valores) y se elige la que mejor reproduce los días de cierre observados, medida con el índice CSI de la sección 6. Se hace por separado para cada ruta y tramo, porque la capacidad de despeje de la 60-CH (corredor internacional con maquinaria de dos países) no es la de la G-21. También se prueba una variante en la que el gatillo no es "nivel 3" sino "más de $s^\dagger$ cm en 12 horas", calibrando también $s^\dagger$.

Esta forma de "estanque con fuga" es la misma lógica del modelo paramétrico de limpieza que menciona el protocolo (volumen de nieve sobre la ruta dividido por el rendimiento de la maquinaria: 903.210 m³ y 70 horas en el cierre de julio), reducida a un solo parámetro.

---

## 5. Contraste estadístico: ¿qué probabilidad de cierre tiene un día?

### 5.1 En palabras

Los modelos anteriores son reglas: dicen sí o no. Como contraste, ajustamos un modelo estadístico clásico, la regresión logística, que en vez de una regla entrega una probabilidad. Se le dan, para cada día, la nieve máxima en 12 horas, la isoterma media, la lluvia máxima y si el día anterior estuvo cerrado, y el modelo aprende de los 124 días (62 por ruta) qué peso darle a cada cosa para reproducir los cierres. Ese último dato, "ayer estuvo cerrado", es la memoria: sin él vemos cuánto explica la meteorología por sí sola; con él, cuánto pesa la inercia de la decisión.

### 5.2 En fórmula

$$
\ln\frac{\Pr(C_d = 1)}{1 - \Pr(C_d = 1)} = \beta_0 + \beta_1 S^{\max}_d + \beta_2 \bar Z_d + \beta_3 R^{\max}_d + \beta_4 C_{d-1}
$$

El lado izquierdo es el "logit": una forma de escribir la probabilidad que va de menos infinito a más infinito, para poder sumarle términos. Cada $\beta$ es un peso: si $\beta_1$ es positivo, más nieve sube la probabilidad de cierre; si $\beta_2$ es negativo, una isoterma más alta la baja. Los pesos se estiman por máxima verosimilitud (los valores que hacen más probable lo que efectivamente ocurrió), con una pequeña penalización porque con cierres tan largos los datos casi se separan perfectamente y los pesos se dispararían.

---

## Parte D · Verificación

Cómo se mide el acierto y qué dio cada cosa, separando siempre las filas que son protocolo tal cual de las que son propuesta nuestra.

## 6. Cómo se mide si el modelo acierta

Para cada día y ruta hay dos respuestas: lo que el modelo previó ($\hat C_d$) y lo que pasó ($C_d$, según la matriz del colega). Se cruzan en una tabla de cuatro casillas:

| | Modelo dijo "cerrar" | Modelo dijo "abierto" |
|---|---|---|
| **Estuvo cerrado** | acierto ($a$) | omisión ($c$): el modelo no lo vio venir |
| **Estuvo abierto** | falsa alarma ($b$) | negativo correcto ($d$) |

De ahí salen los cuatro indicadores que se usan en verificación de pronósticos:

* **POD** (probabilidad de detección) $= a/(a+c)$: de los días cerrados, qué fracción anticipó el modelo. 1 es perfecto.
* **FAR** (razón de falsas alarmas) $= b/(a+b)$: de las veces que el modelo dijo "cerrar", qué fracción no se cerró. 0 es perfecto.
* **CSI** (índice de éxito crítico) $= a/(a+b+c)$: combina los dos anteriores ignorando los días tranquilos, que son fáciles de acertar. 1 es perfecto.
* **HSS** (Heidke) $= \dfrac{2(ad - bc)}{(a+c)(c+d) + (a+b)(b+d)}$: cuánto mejor que el azar. 0 es azar, 1 es perfecto, negativo es peor que tirar una moneda.

Además, por cada episodio de cierre observado, la **anticipación**: cuántas horas antes del cierre real el modelo ya marcaba nivel 3. Positiva es aviso previo; negativa, el modelo llegó tarde.

La vara mínima es la **persistencia trivial**: "mañana estará como hoy". Un modelo que no supere eso no sirve.

---

## 7. Resultados

Todo lo que sigue compara, día a día, el cierre observado de la ruta (matrices del colega, categoría *cerrado_meteo*) con lo que dice cada modelo en el tramo alto, del 1 de julio al 31 de agosto de 2026 (62 días por ruta). Los modelos corren en bloques de 6 horas (cuatro por día) y el día queda cerrado si alguno de sus bloques lo está. El detalle está en `salidas/`: `consolidado_6h.csv`, `modelo_cierre_metricas.csv`, `modelo_cierre_episodios.csv`, `modelo_cierre_diario.csv`, `modelo_cierre_parametros.json`. La versión hora a hora quedó respaldada en `respaldo_v2_horario/`.

### 7.1 Lo que pasó

| Ruta | Días con cierre | Episodios | Nieve caída jul + ago (cm) | Máximo en 12 h (cm) |
|---|---|---|---|---|
| 60-CH (Guardia Vieja – túnel) | 47 | 5 | 727 | 50 |
| G-21 (Farellones y accesos) | 6 | 2 | 462 | 38 |

Episodios de cierre observados y lo que ERA5 vio en cada uno:

| Ruta | Inicio | Fin | Días | Nieve en el episodio (cm) | S máx 12 h (cm) | Z mín (m) | Nivel máx protocolo | Primer nivel 3 | Causa según la matriz |
|-----|--------|--------|----|------|------|------|-----|--------|------------------|
| 60-CH | 2026-07-09 17:00 | 2026-07-11 10:00 | 1,8 | 26 | 20 | 3020 | 1 | — | Precipitaciones en alta cordillera |
| 60-CH | 2026-07-14 15:00 | 2026-08-18 07:00 | 34,7 | 588 | 50 | 2038 | 2 | — | Inestabilidades y nevadas de magnitud |
| 60-CH | 2026-08-24 17:00 | 2026-08-29 08:00 | 4,7 | 97 | 24 | 2223 | 2 | — | Condiciones climáticas desfavorables e inestabilidades (nevadas) |
| 60-CH | 2026-08-29 17:00 | 2026-08-30 07:00 | 0,6 | 0 | 4 | 2306 | 1 | — | Condiciones meteorológicas adversas |
| 60-CH | 2026-08-30 17:00 | 2026-08-31 09:00 | 0,7 | 8 | 8 | 2252 | 1 | — | Condiciones meteorológicas adversas |
| G-21 | 2026-07-15 23:00 | 2026-07-19 10:00 | 3,5 | 145 | 38 | 1843 | 2 | — | Alarma de precipitaciones intensas y nevadas |
| G-21 | 2026-07-19 17:00 | 2026-07-20 09:00 | 0,7 | 35 | 26 | 1845 | 2 | — | Alud río Ñilhue |

Tres cosas saltan a la vista. Primera: **ningún episodio alcanzó el nivel 3 del cuadro.** En bloques de 6 horas, el máximo de la 60-CH fue 49,96 cm en 12 horas el 17 de julio entre las 12 y las 18 h, con la barrera ya cerrada hacía tres días: se queda a centésimas del umbral de 50 cm (en el cálculo hora a hora lo cruzaba por una hora, con 51,6 cm). El único bloque de nivel 3 del periodo es el 8 de agosto de 06 a 12 h en la G-21, por isoterma baja con poca nieve, y ese día no hubo cierre. Las autoridades cerraron con 30 a 50 cm en 12 horas e isoterma entre 1 800 y 2 300 m, que el cuadro clasifica como nivel 2 (cierre parcial). Segunda: **los cierres se decretan con pronóstico, no con observación.** El cierre de la 60-CH del 14 de julio se anunció el 13 a las 23:10, un día antes de la primera nevada; el de la G-21 del 15 de julio se anunció a las 15:09 con 3 cm en el suelo. ERA5 es una reconstrucción de lo que ocurrió, así que el modelo puede detectar, no anticipar: para anticipar hay que alimentarlo con el pronóstico (GFS o ECMWF a 3 días, como pide el protocolo). Tercera: **la duración del cierre no la explica la nieve del día.** La 60-CH siguió cerrada 34 días con nevadas intermitentes de 5 a 30 cm; la G-21 reabrió en 4,5 días con 144 cm caídos. Son dos regímenes de despeje distintos.

### 7.2 Qué tan bien acierta cada modelo (tramo alto)

| Origen | Modelo | Ruta | A | B | C | D | POD | FAR | CSI | HSS |
|------------------|----------------------|------|-----|-----|-----|-----|-----|-----|-----|-----|
| Protocolo tal cual | protocolo literal (L=3) | 60-CH | 0 | 0 | 47 | 15 | 0,00 | — | 0,00 | 0,00 |
| Protocolo tal cual | protocolo literal (L>=2) | 60-CH | 7 | 0 | 40 | 15 | 0,15 | 0,00 | 0,15 | 0,08 |
| Protocolo tal cual | protocolo literal (L=3) | G-21 | 0 | 1 | 6 | 55 | 0,00 | 1,00 | 0,00 | -0,03 |
| Protocolo tal cual | protocolo literal (L>=2) | G-21 | 5 | 22 | 1 | 34 | 0,83 | 0,81 | 0,18 | 0,17 |
| Referencia | persistencia trivial (C_d = C_d-1) | 60-CH | 44 | 2 | 3 | 13 | 0,94 | 0,04 | 0,90 | 0,79 |
| Referencia | persistencia trivial (C_d = C_d-1) | G-21 | 5 | 1 | 1 | 55 | 0,83 | 0,17 | 0,71 | 0,81 |
| Propuesta: cuadro sin huecos | regularizado (L*=3) | 60-CH | 0 | 0 | 47 | 15 | 0,00 | — | 0,00 | 0,00 |
| Propuesta: cuadro sin huecos | regularizado (L*>=2) | 60-CH | 7 | 0 | 40 | 15 | 0,15 | 0,00 | 0,15 | 0,08 |
| Propuesta: cuadro sin huecos | regularizado (L*=3) | G-21 | 0 | 1 | 6 | 55 | 0,00 | 1,00 | 0,00 | -0,03 |
| Propuesta: cuadro sin huecos | regularizado (L*>=2) | G-21 | 5 | 10 | 1 | 46 | 0,83 | 0,67 | 0,31 | 0,39 |
| Propuesta, calibrada con los cierres | regularizado + persistencia (calibrado) | 60-CH | 0 | 0 | 47 | 15 | 0,00 | — | 0,00 | 0,00 |
| Propuesta, calibrada con los cierres | umbral de nieve + persistencia (calibrado) | 60-CH | 46 | 7 | 1 | 8 | 0,98 | 0,13 | 0,85 | 0,59 |
| Propuesta, calibrada con los cierres | regularizado + persistencia (calibrado) | G-21 | 0 | 1 | 6 | 55 | 0,00 | 1,00 | 0,00 | -0,03 |
| Propuesta, calibrada con los cierres | umbral de nieve + persistencia (calibrado) | G-21 | 5 | 0 | 1 | 56 | 0,83 | 0,00 | 0,83 | 0,90 |
| Propuesta, ajustada con los cierres | logística diaria S,Z,R + C(d-1) | ambas | 49 | 3 | 4 | 68 | 0,93 | 0,06 | 0,88 | 0,88 |
| Propuesta, ajustada con los cierres | logística diaria S,Z,R (sin persistencia) | ambas | 38 | 4 | 15 | 67 | 0,72 | 0,10 | 0,67 | 0,68 |

Las columnas A, B, C y D son las cuatro casillas de la sección 6: aciertos, falsas alarmas, omisiones y negativos correctos (días). Cómo leer la tabla. La columna **Origen** separa las tres cosas que se comparan. *Protocolo tal cual*: el cuadro de Lo Barnechea aplicado sin tocar nada. *Referencia*: la regla trivial "mañana como hoy", que no usa meteorología. *Propuesta*: lo nuestro; las filas marcadas como calibradas o ajustadas usan los mismos cierres observados para elegir sus parámetros, así que su puntaje es el mejor caso posible (en muestra) y no es comparable uno a uno con el protocolo, que no tuvo esa ventaja.

* **El cuadro literal no sirve solo.** Con el umbral de 50 cm para nivel 3 no detecta ninguno de los 47 días cerrados de la 60-CH ni de los 6 de la G-21 (CSI 0,00 en ambas). Bajando la vara a nivel 2 mejora poco en la 60-CH (0,15) y en la G-21 acierta 5 de 6 cierres pero con 10 falsas alarmas (CSI 0,31): en la G-21 hubo varios días con nivel 2 sin cierre, porque el régimen unidireccional y las cadenas absorben nevadas medianas.
* **La persistencia trivial ("mañana como hoy") es muy difícil de superar en la 60-CH**: CSI 0,90, porque casi todo el periodo estuvo cerrada. Cualquier modelo de esta ruta tiene que explicar la duración, no solo el inicio.
* **El modelo calibrado con umbral y persistencia** es el que mejor reproduce ambas rutas: CSI 0,85 en la 60-CH (POD 0,98; 1 omisión, el 9 de julio, cierre preventivo con 5 cm) y 0,83 en la G-21 (5 de 6 días, ninguna falsa alarma). En la G-21 supera con claridad a la persistencia trivial (0,71); en la 60-CH queda apenas debajo.
* **La regresión logística** con nieve, isoterma, lluvia y "ayer cerrado" separa muy bien los días (AUC 0,96, CSI 0,88). Sin el término de ayer, la meteorología por sí sola llega a AUC 0,92 y CSI 0,67: la nieve explica mucho, la inercia de la decisión explica el resto. Coeficientes estandarizados: S_max12_cm = +1,155, Z_media_f = +0,334, R_max12_mm = -0,736, cerrado_obs_ayer = +2,424. El signo negativo de la lluvia es coherente con el cuadro: llueve cuando la isoterma está alta, y esos días no cierran por nieve.

### 7.3 Parámetros calibrados

| Ruta | Tramo | Umbral de cierre $s^\dagger$ (cm/12 h) | Despeje $c$ (cm/h) | Residual $\theta$ (cm) | POD | FAR | CSI |
|---|---|---|---|---|---|---|---|
| 60-CH | alto | 10 | 0,05 | 0 | 0,98 | 0,13 | 0,85 |
| 60-CH | medio | 10 | 0,05 | 0 | 0,89 | 0,11 | 0,81 |
| G-21 | alto | 25 | 1,5 | 30 | 0,83 | 0,00 | 0,83 |
| G-21 | medio | 20 | 1,0 | 50 | 0,83 | 0,00 | 0,83 |

Lectura: en la **G-21** el modelo dice "cerrar con 25 cm en 12 horas, despejar a 1,5 cm/h y reabrir con menos de 30 cm por despejar". Con 144 cm caídos entre el 15 y el 20 de julio eso da 4 a 5 días de cierre, que es lo que ocurrió. Son valores físicamente razonables y coinciden con el umbral de nivel 2 del cuadro: **en la práctica, la autoridad usó el nivel 2 del protocolo como nivel de cierre total.**

En la **60-CH** el ajuste da umbral 10 cm, despeje 0,05 cm/h y residual 0: "cierra con la primera nevada seria y no reabre en toda la temporada". Es la descripción fiel de lo que pasó (34 días cerrada con 588 cm caídos), pero no es un modelo de despeje: constata que el Sistema Cristo Redentor reabre por criterios binacionales y de seguridad de la Cuesta de los Caracoles que la nieve caída no captura. Para esta ruta el modelo útil es el de inicio del cierre (umbral 10 a 20 cm) más una duración que hay que tomar de otra fuente.

### 7.4 Qué se recomienda para el catastro

1. **Usar la versión regularizada del cuadro con el umbral de cierre en 25 cm/12 h** (nivel 2 del protocolo) como criterio de "día de cierre probable" para las rutas de montaña sin protocolo propio. Es lo que las dos autoridades hicieron de hecho.
2. **Contar la duración con el balance de nieve por despejar**, con capacidad de despeje calibrada por tipo de ruta: del orden de 1,5 cm/h en un camino municipal con maquinaria dedicada; mucho menor en un paso internacional.
3. **Tratar a ERA5 como observación, no como pronóstico.** Para anticipación operativa el mismo modelo se alimenta con el pronóstico a 3 días.
4. **Verificar la conversión de mm a cm de nieve** con alguna observación de terreno cuando exista; con 10:1 los umbrales quedan en cm de nieve fresca, que es la magnitud del cuadro.

---

## 8. Lo que este modelo no puede hacer

* **Sin visibilidad ni tránsito.** El protocolo tiene cinco gatillantes; ERA5 permite calcular tres. Los cierres por viento blanco o por saturación de vehículos quedan fuera.
* **La celda no es la calzada.** ERA5-Land promedia 9 km × 9 km con un relieve suavizado. La nieve que reporta es la de la celda, no la de la curva 32. Los centímetros dependen además de la densidad de la nieve fresca, que no se observa.
* **La isoterma es regional y tiene un sesgo de escala.** Se estima en celdas bajas de la misma ruta; se asume que la altura del nivel de 0 °C varía poco en 30 a 50 km. Además, se le suma la cota media del terreno real (DEM), que en cordillera es mayor que la orografía suavizada del modelo ERA5. Una comprobación independiente (la altura a la que la temperatura de ERA5-Land llegaría a 0 °C con un gradiente de 6,5 °C/km) da una isoterma unos 260 m más baja en mediana, con correlación 0,65 entre ambas estimaciones. Hay que leer las bandas del protocolo (1 500 y 2 800 m) con una incertidumbre de ±300 m; para afinarla habría que descargar la orografía propia de ERA5 (geopotencial invariante) desde el Climate Data Store.
* **La 60-CH no cierra solo por nieve.** Es un corredor binacional: la decisión la toman Chile y Argentina juntos y depende también del lado argentino, que no vemos.
* **Dos meses, dos rutas.** Los parámetros calibrados ($c$, $\theta$, los $\beta$) describen esta temporada. Lo que se lleva al resto del catastro es la forma del modelo y el orden de magnitud de los umbrales, no los decimales.

---

## Glosario

* **ERA5 / ERA5-Land**: reanálisis del Centro Europeo (ECMWF). Un modelo meteorológico que se corre hacia atrás en el tiempo, asimilando todas las observaciones disponibles, para reconstruir el clima hora a hora sobre una grilla. ERA5 tiene celdas de 0,25° (~28 km) y trae la isoterma; ERA5-Land, de 0,1° (~9 km), trae nieve, temperatura y precipitación en superficie.
* **Isoterma 0 °C**: altura a la que el aire está a 0 °C. Por debajo llueve, por encima nieva (con una franja mixta de unos 200 a 300 m).
* **Agua equivalente (SWE)**: cuánta agua daría la nieve al derretirse. 1 mm de agua ≈ 1 cm de nieve fresca.
* **Gatillante**: condición medible que, al cumplirse, activa un nivel de alerta.
* **Ventana de 12 h**: las 12 horas que terminan con el bloque que se está evaluando (el bloque y el anterior). Es el estándar de la DMC que adopta el protocolo.
* **Bloque de 6 h**: cada uno de los cuatro tramos del día local (00–06, 06–12, 12–18, 18–24) en que se agrupan las horas de ERA5 y del estado observado.
* **Indicatriz $\mathbb{1}[\cdot]$**: función que vale 1 si la condición entre corchetes se cumple y 0 si no.
* **Persistencia / histéresis**: que el estado de hoy dependa del de ayer. Aquí, que el camino siga cerrado aunque ya no nieve.
* **Calibrar**: elegir los valores de los parámetros que mejor reproducen lo observado.
* **POD, FAR, CSI, HSS**: indicadores estándar de verificación de pronósticos, definidos en la sección 6.
