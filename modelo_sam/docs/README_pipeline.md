# Datos meteorológicos · Parte 2 del catastro FONDEF

Versión 3 (5 oct 2026): igual que la versión 2 (solo reanálisis ERA5 / ERA5-Land por tramo, cruzado con el estado observado de los caminos y el protocolo de cierre de Lo Barnechea), pero el modelo y el visor trabajan en **bloques de 6 h locales** (00–06, 06–12, 12–18, 18–24) en vez de hora a hora. Los respaldos de las versiones 1 y 2 no se publican.

## Orden de ejecución

| Paso | Script | Qué hace | Entradas | Salidas |
|---|---|---|---|---|
| 1 | `scripts/cotas_celdas.R` | Cota media DEM (Copernicus GLO-30, vía /vsicurl/) de cada celda ERA5 (0,25°) y ERA5-Land (0,1°) de los recortes descargados | ninguna local | `salidas/geometria/cotas_celdas.csv` |
| 2 | `scripts/geometria_tramos.R` | Define los 4 tramos (60-CH alto/medio, G-21 alto/medio), calcula qué celdas ERA5-Land cruza cada uno y con cuánta longitud de camino, y la cota del camino en cada celda | `catastro_caminos/data/raw/red_vial/region_de_valparaiso_p001.json` (60-CH), `catastro_caminos/data/processed/tramos.gpkg` (G-21, G-249, G-251) | `salidas/geometria/pesos_celdas_era5land.csv`, `tramos_resumen.csv`, `tramos_muestra.gpkg` |
| 3 | `scripts/era5_extraer_celdas.py` | Lee los 12 GRIB nuevos y vuelca todas las celdas a tablas horarias (lento: ~18 min; usa `indexpath=""` porque en OneDrive el índice de cfgrib queda inválido) | `datos/era5/` | `salidas/cache/era5land_celdas_horario.csv`, `era5_isoterma_celdas.csv` |
| 4 | `scripts/consolidar_horario_era5.py` | Serie horaria por tramo: promedio ponderado por longitud de camino, isoterma en m s.n.m., ventanas de 12 h del protocolo | pasos 1-3 | `salidas/era5_tramos_horario.csv`, `era5_tramos_meta.csv` |
| 5 | `scripts/estado_caminos.py` | Convierte las dos matrices de viabilidad operativa del colega en una serie horaria de estado de ruta | `datos/estado_caminos/*.xlsx` | `salidas/estado_caminos_horario.csv`, `_eventos.csv`, `_resumen.csv` |
| 5b | `scripts/agregar_bloques_6h.py` | Agrega la serie ERA5 por tramo y el estado observado a bloques de 6 h locales: sumas de nieve y lluvia, medias/mín/máx de temperatura, viento e isoterma, manto al final del bloque, ventanas de 12 h = 2 bloques, horas de cada estado observado | pasos 4 y 5 | `salidas/era5_tramos_6h.csv`, `estado_caminos_6h.csv` |
| 6 | `scripts/modelo_cierre.py` | Niveles del protocolo por bloque de 6 h, versión regularizada, modelo con persistencia calibrado (despeje c·6 h por bloque), regresión logística, métricas y episodios (identificados en la serie horaria). Escribe la base definitiva | paso 5b | `salidas/consolidado_6h.csv` / `.xlsx`, `modelo_cierre_diario.csv`, `_episodios.csv`, `_metricas.csv`, `_parametros.json` |
| 7 | `scripts/resultados_md.py` | Rellena la sección 7 de `docs/modelo_cierre.md` con los números del paso 6 | paso 6 | `docs/modelo_cierre.md` |
| 8 | `scripts/generar_dashboard.py` | Visor HTML autocontenido | pasos 4-6, `scripts/dashboard_plantilla.html`, `fuentes_embebidas.css` | `salidas/dashboard_60CH_G21.html` |
| 9 | `scripts/era5_rafagas.py` | Ráfagas y viento por tramo y bloque de 6 h | `datos/era5/VIento/`, paso 2 | `salidas/era5_rafagas_6h.csv` |
| 10 | `scripts/sistema_condicion.py` | SAM-Cordillera: severidad, peligro de montaña, balance de despeje y estado operacional por tramo y bloque; calibración en la G-21 y transferencia a la 60-CH | pasos 2, 5b y 9 | `salidas/sistema/` |
| 11 | `scripts/generar_dashboard_sam.py` | Dashboard SAM-Cordillera autocontenido | pasos 4-6 y 10, `scripts/dashboard_plantilla_sam.html`, `fuentes_embebidas.css` | `salidas/dashboard_SAM_Cordillera.html` |
| 12 | `scripts/figuras_sistema.py`, `scripts/figuras_postulacion.py` | Figuras del documento técnico | paso 10 | `documento_tecnico/fig/`, `documento_tecnico/fig_png/` |

Los scripts de Python ubican sus rutas a partir de su propia carpeta y pueden correrse desde cualquier lugar. Los dos scripts de R se corren desde la raíz del repositorio.

Los pasos 2 y `scripts/estaciones_cercanas.py` leen archivos del [catastro de caminos de montaña](https://github.com/dariobriceno-uch/catastro-caminos-montana). Lo buscan en una carpeta `catastro_caminos/` junto a la raíz de este repositorio, o en la ruta que indique la variable de entorno `CATASTRO_CAMINOS`. Las rutas `catastro_caminos/...` de la tabla se refieren a ese repositorio.

`scripts/leer_grib.py` es el ayudante para abrir GRIB con cfgrib en Windows (shim de ecCodes).

## Definición de los tramos

* **60-CH alto**: camino dentro del recorte ERA5-Land "Tramo Alto" del colega (lat −32,9/−32,8; lon −70,2/−70,1) = Guardia Vieja a túnel Cristo Redentor, 28,9 km, 1.644–3.700 m. Es el trecho que cierra la barrera.
* **60-CH medio**: camino dentro del recorte "Tramo Medio" y fuera del alto = Río Blanco a Guardia Vieja, 23,7 km, 1.021–1.645 m.
* **G-21 alto**: tramos del catastro G-21-2, G-21-3, G-21-4 + G-249 + G-251 = Farellones y accesos a los centros, 20,8 km, 2.330–3.027 m.
* **G-21 medio**: tramo G-21-1-13 del catastro = subida de curvas La Ermita–Curva 32, 29,6 km, 917–2.463 m.

Para la G-21 los recortes descargados se contienen uno al otro y no separan tramos; la separación viene del catastro.

## Decisiones que conviene recordar

* ERA5 entrega la isoterma 0 °C como altura **sobre el suelo del modelo** (`deg0l`) y la fija en 0 cuando toda la columna está bajo 0 °C. Se convierte a m s.n.m. sumando la cota DEM de la celda y usando las celdas de menor orografía de cada ruta (G-21: columna lon −70,75, ~500 m; 60-CH: columna lon −70,5, ~1.750–2.065 m). En jul-ago 2026 no hubo horas censuradas.
* Nieve en cm = mm de agua equivalente × 100/ρ, con ρ = 100 kg/m³ (10:1). Parámetro `RHO` en `consolidar_horario_era5.py` y `modelo_cierre.py`.
* El estado observado es de la **ruta** (no del tramo); el modelo se verifica contra el tramo alto.
* Vacíos: `tsn` y `smlt` no vienen en el GRIB de agosto del tramo medio de la 60-CH; el viento a 10 m de ERA5-Land en montaña es muy suave (máximo 3,5 m/s), no sirve para viento blanco.
