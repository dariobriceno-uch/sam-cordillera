# SAM-Cordillera · Estado operacional de caminos de montaña por nieve

SAM-Cordillera es un sistema que estima cada 6 horas el estado operacional de un camino de montaña (abierto, con restricciones o cerrado) a partir de la meteorología, el peligro de montaña y la capacidad de despeje. Es parte del proyecto FONDEF sobre caminos de alta montaña en Chile y se contrastó con los cierres reales de la Ruta 60-CH (Paso Los Libertadores) y la Ruta G-21 (acceso a los centros de esquí de Farellones) en julio y agosto de 2026.

## Dashboard

El dashboard es un archivo HTML autocontenido: [`modelo_sam/salidas/dashboard_SAM_Cordillera.html`](modelo_sam/salidas/dashboard_SAM_Cordillera.html). Muestra la meteorología por tramo en bloques de 6 horas, el estado observado de cada ruta, los índices del sistema (severidad, peligro y balance de despeje) y su desempeño frente al Protocolo Lo Barnechea. Se abre con doble clic en cualquier navegador moderno y no necesita servidor, internet ni instalación.

También se puede ver en línea en **https://dariobriceno-uch.github.io/sam-cordillera/**, publicado con GitHub Pages.

## Cómo funciona

SAM-Cordillera trabaja por tramo y en bloques de 6 horas (00–06, 06–12, 12–18 y 18–24, hora local), con dos tramos por ruta. Usa el reanálisis ERA5 y ERA5-Land, un modelo de elevación y la geometría de los caminos del [catastro de caminos de montaña](https://github.com/dariobriceno-uch/catastro-caminos-montana). En cada bloque calcula tres índices.

- **Severidad de la tormenta.** Combina la nieve caída en el bloque, la fracción del tramo que queda bajo la cota de nieve, la tasa y la duración de la nevada, las ráfagas de viento y la lluvia. Nunca exige menos que el Protocolo Lo Barnechea.
- **Peligro de montaña.** Avalanchas, a partir de la nieve acumulada en 72 horas, el arrastre por viento y el calentamiento, y remociones en masa a partir de la lluvia en 72 horas.
- **Balance de despeje.** La nieve pendiente de retirar, que crece con cada nevada y baja según la capacidad de despeje.

El estado del tramo es el nivel más alto entre los tres índices, y el de la ruta es el de su tramo más exigido. El sistema entrega además la causa del estado, el tramo crítico y la hora estimada de reapertura.

Los umbrales se calibraron solo con la G-21 y se transfirieron sin cambios a la 60-CH. En julio y agosto de 2026, los umbrales escritos del Protocolo Lo Barnechea justificaron 0 de los 19 bloques de 6 horas en que la G-21 estuvo cerrada por meteorología y 1 de los 176 de la 60-CH. SAM-Cordillera justificó 13 de 19 y 72 de 176, respectivamente.

La formulación completa, con todas las fórmulas y resultados, está en el documento técnico [`documento_tecnico/sistema_condicion_invernal.pdf`](documento_tecnico/sistema_condicion_invernal.pdf). El orden de ejecución de los scripts está en [`modelo_sam/docs/README_pipeline.md`](modelo_sam/docs/README_pipeline.md).

## Estructura del repositorio

```
.
├── modelo_sam/
│   ├── datos/
│   │   ├── era5/                    reanálisis ERA5-Land y ERA5 por tramo (GRIB)
│   │   ├── era5_temperatura_nieve/
│   │   ├── estaciones_dmc/          estaciones de la Dirección Meteorológica de Chile
│   │   ├── estado_caminos/          matrices de cierres observados de cada ruta
│   │   └── maquinaria/              listado de maquinaria de despeje de la 60-CH
│   ├── scripts/                     procesamiento, modelo, figuras y dashboards
│   ├── salidas/                     series por bloque, resultados del sistema y dashboards
│   └── docs/                        orden de ejecución y documentación del modelo de cierre
└── documento_tecnico/               documento técnico de SAM-Cordillera (LaTeX) y sus figuras
```

## Reproducir

**Requisitos.** Python 3.10 o superior con `pandas`, `numpy`, `scipy`, `matplotlib`, `openpyxl`, `cfgrib`, `eccodes`, `shapely` y `pyproj`. R 4.3 o superior con `sf`, `terra` y `jsonlite`.

Los scripts de Python ubican sus rutas a partir de su propia carpeta y pueden correrse desde cualquier lugar. Los dos scripts de R (`cotas_celdas.R` y `geometria_tramos.R`) se corren desde la raíz del repositorio. Con las series ya agregadas, el sistema y su dashboard se regeneran así.

```
python modelo_sam/scripts/sistema_condicion.py
python modelo_sam/scripts/generar_dashboard_sam.py
```

La geometría de los tramos ya calculada está en `modelo_sam/salidas/geometria/`. Solo para recalcularla (`geometria_tramos.R`) o para buscar estaciones cercanas (`estaciones_cercanas.py`) hace falta el catastro. Esos scripts lo buscan en una carpeta `catastro_caminos/` junto a este repositorio, o en la ruta indicada en la variable de entorno `CATASTRO_CAMINOS`.

```
git clone https://github.com/dariobriceno-uch/sam-cordillera.git
git lfs install
git clone https://github.com/dariobriceno-uch/catastro-caminos-montana.git catastro_caminos
```

## Datos

Las fuentes principales son las siguientes.

- ERA5 y ERA5-Land, Copernicus Climate Change Service (C3S).
- Copernicus DEM GLO-30.
- Estaciones meteorológicas de la Dirección Meteorológica de Chile.
- Red Vial Nacional, Dirección de Vialidad, Ministerio de Obras Públicas, a través del catastro de caminos de montaña.
- Estado observado de la 60-CH y la G-21 en julio y agosto de 2026.
