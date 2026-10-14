# ---------------------------------------------------------------------------
# geometria_tramos.R
# Define los cuatro tramos de muestra (60-CH alto/medio, G-21 alto/medio),
# calcula que celdas ERA5-Land (0,1 grados) atraviesa cada uno y con cuanta
# longitud de camino, y toma la cota DEM del camino dentro de cada celda.
#
# Insumos del catastro de caminos de montaña (repositorio catastro-caminos-montana,
# clonado junto a este o indicado en la variable de entorno CATASTRO_CAMINOS):
#   - catastro_caminos/data/raw/red_vial/region_de_valparaiso_p001.json  (Vialidad MOP,
#     FT-01): geometria de "Ruta 60 CH", codigo 65A00060, EPSG:5360.
#   - catastro_caminos/data/processed/tramos.gpkg: tramos G-21, G-249, G-251 con cotas
#     derivadas del DEM (bloque A3).
#   - Copernicus DEM GLO-30 (FT-07) leido por /vsicurl/, igual que a3_altimetria.R.
#
# Definicion de tramos:
#   60-CH alto  = camino dentro del recorte ERA5-Land "Tramo Alto" descargado
#                 (centros lat -32,9/-32,8; lon -70,2/-70,1).
#   60-CH medio = camino dentro del recorte "Tramo Medio" (lat -33,0..-32,8;
#                 lon -70,4..-70,2) que no esta en el recorte alto.
#   G-21 alto   = tramos G-21-2, G-21-3, G-21-4 + G-249 + G-251 del catastro
#                 (Farellones y accesos a los centros de esqui, 2.461-3.025 m).
#   G-21 medio  = tramo G-21-1-13 del catastro (la subida de curvas, 925-2.461 m).
#   Para la G-21 el recorte "Tramo Medio" esta contenido en el "Tramo Alto", asi
#   que la separacion no puede venir de los recortes: viene del catastro.
#
# Salidas: modelo_sam/salidas/geometria/
#   pesos_celdas_era5land.csv, tramos_resumen.csv, tramos_muestra.gpkg
# ---------------------------------------------------------------------------
suppressPackageStartupMessages({library(sf); library(terra); library(jsonlite)})
sf_use_s2(FALSE)
RAIZ   <- getwd()   # correr desde la raíz del repositorio
CAM    <- Sys.getenv("CATASTRO_CAMINOS", unset = file.path(RAIZ, "..", "catastro_caminos"))
if (!dir.exists(CAM)) stop("No se encuentra el catastro en ", CAM,
                           ". Clonar catastro-caminos-montana junto a este repositorio o definir CATASTRO_CAMINOS.")
OUT    <- file.path(RAIZ, "modelo_sam/salidas/geometria")
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)
UTM <- 32719

# ---- 1. geometrias ---------------------------------------------------------
# 60-CH: features del codigo 65A00060 en la descarga cruda de Valparaiso
j <- fromJSON(file.path(CAM, "data/raw/red_vial/region_de_valparaiso_p001.json"), simplifyVector = FALSE)
ft <- Filter(function(f) identical(f$attributes$CODIGO_CAMINO, "65A00060"), j$features)
lineas <- lapply(ft, function(f) {
  m <- do.call(rbind, lapply(f$geometry$paths[[1]], function(p) c(p[[1]], p[[2]])))
  st_linestring(m)
})
r60 <- st_sf(km_i = sapply(ft, function(f) f$attributes$KM_I), km_f = sapply(ft, function(f) f$attributes$KM_F),
             geometry = st_sfc(lineas, crs = 5360))
r60 <- st_transform(r60, UTM)
cat("60-CH: ", nrow(r60), " features, ", round(sum(st_length(r60)) / 1000, 1), " km\n", sep = "")

# G-21 y ramales desde el catastro procesado
g <- st_read(file.path(CAM, "data/processed/tramos.gpkg"),
             query = "SELECT id_tramo, rol, km_inicio, km_fin, cota_min, cota_max, cota_media, geom FROM tramos WHERE rol IN ('G-21','G-249','G-251')",
             quiet = TRUE)
g <- st_transform(st_zm(g), UTM)
gcol <- attr(g, "sf_column")

caja <- function(lat0, lat1, lon0, lon1) {   # extension de celdas a partir de centros (0,1 grados)
  st_transform(st_as_sfc(st_bbox(c(xmin = lon0 - .05, xmax = lon1 + .05, ymin = lat0 - .05, ymax = lat1 + .05), crs = st_crs(4326))), UTM)
}
caja_60_alto  <- caja(-32.9, -32.8, -70.2, -70.1)
caja_60_medio <- caja(-33.0, -32.8, -70.4, -70.2)

u60 <- st_union(r60)
tramos <- rbind(
  st_sf(ruta = "60-CH", tramo = "alto",  definicion = "camino dentro del recorte ERA5-Land Tramo Alto",
        geometry = st_intersection(u60, caja_60_alto)),
  st_sf(ruta = "60-CH", tramo = "medio", definicion = "camino dentro del recorte Tramo Medio y fuera del recorte Tramo Alto",
        geometry = st_difference(st_intersection(u60, caja_60_medio), caja_60_alto)),
  st_sf(ruta = "G-21",  tramo = "alto",  definicion = "catastro: G-21-2, G-21-3, G-21-4, G-249, G-251",
        geometry = st_union(st_geometry(g)[g$id_tramo %in% c("G-21-2", "G-21-3", "G-21-4") | g$rol %in% c("G-249", "G-251")])),
  st_sf(ruta = "G-21",  tramo = "medio", definicion = "catastro: G-21-1-13",
        geometry = st_union(st_geometry(g)[g$id_tramo == "G-21-1-13"]))
)
tramos$longitud_km <- round(as.numeric(st_length(tramos)) / 1000, 2)
print(as.data.frame(tramos)[, c("ruta", "tramo", "longitud_km")])

# ---- 2. celdas ERA5-Land descargadas -------------------------------------
celdas_def <- list(
  list(ruta = "60-CH", tramo = "alto",  lats = seq(-32.9, -32.8, .1), lons = seq(-70.2, -70.1, .1)),
  list(ruta = "60-CH", tramo = "medio", lats = seq(-33.0, -32.8, .1), lons = seq(-70.4, -70.2, .1)),
  list(ruta = "G-21",  tramo = "alto",  lats = seq(-33.5, -33.2, .1), lons = seq(-70.5, -70.2, .1)),
  list(ruta = "G-21",  tramo = "medio", lats = seq(-33.5, -33.3, .1), lons = seq(-70.5, -70.3, .1))
)
celda_poly <- function(la, lo) st_polygon(list(matrix(c(lo - .05, la - .05, lo + .05, la - .05, lo + .05, la + .05,
                                                         lo - .05, la + .05, lo - .05, la - .05), ncol = 2, byrow = TRUE)))

# ---- 3. DEM a lo largo del camino ----------------------------------------
BUCKET <- "https://copernicus-dem-30m.s3.amazonaws.com"
tn <- function(lat, lon) sprintf("Copernicus_DSM_COG_10_S%02d_00_W%03d_00_DEM", abs(lat), abs(lon))
tiles <- c(tn(-33, -71), tn(-33, -70), tn(-34, -71), tn(-34, -70))
vrtf <- file.path(OUT, "dem_muestra.vrt")
vrt(sprintf("/vsicurl/%s/%s/%s.tif", BUCKET, tiles, tiles), filename = vrtf, overwrite = TRUE)
dem <- rast(vrtf)

pesos <- list(); resumen <- list()
for (i in seq_len(nrow(tramos))) {
  tr <- tramos[i, ]
  cd <- celdas_def[[i]]
  gr <- expand.grid(lat = round(cd$lats, 2), lon = round(cd$lons, 2))
  cel <- st_sf(lat = gr$lat, lon = gr$lon, geometry = st_sfc(mapply(celda_poly, gr$lat, gr$lon, SIMPLIFY = FALSE), crs = 4326))
  cel <- st_transform(cel, UTM)
  inter <- suppressWarnings(st_intersection(cel, st_geometry(tr)))
  inter$longitud_m <- as.numeric(st_length(inter))
  inter <- inter[inter$longitud_m > 1, ]
  # cota del camino dentro de cada celda: puntos cada 50 m sobre el DEM
  z_by <- lapply(seq_len(nrow(inter)), function(k) {
    p <- st_cast(st_segmentize(st_geometry(inter)[k], 50), "POINT")
    v <- terra::extract(dem, vect(st_transform(p, 4326)))[, 2]
    v[!is.na(v)]
  })
  inter$cota_camino_media <- round(sapply(z_by, mean))
  inter$cota_camino_min   <- round(sapply(z_by, min))
  inter$cota_camino_max   <- round(sapply(z_by, max))
  inter$peso <- inter$longitud_m / sum(inter$longitud_m)
  df <- as.data.frame(inter); df[[attr(inter, "sf_column")]] <- NULL
  df <- cbind(ruta = tr$ruta, tramo = tr$tramo, df)
  pesos[[i]] <- df
  zall <- unlist(z_by)
  resumen[[i]] <- data.frame(ruta = tr$ruta, tramo = tr$tramo, definicion = tr$definicion,
                             longitud_km = tr$longitud_km, n_celdas = nrow(inter),
                             cota_min = round(min(zall)), cota_media = round(weighted.mean(inter$cota_camino_media, inter$longitud_m)),
                             cota_max = round(max(zall)),
                             celdas = paste(sprintf("(%.1f,%.1f)", inter$lat, inter$lon), collapse = " "))
  cat(tr$ruta, tr$tramo, ": ", nrow(inter), " celdas\n", sep = "")
}
pesos <- do.call(rbind, pesos); resumen <- do.call(rbind, resumen)
pesos$longitud_m <- round(pesos$longitud_m); pesos$peso <- round(pesos$peso, 4)
write.csv(pesos, file.path(OUT, "pesos_celdas_era5land.csv"), row.names = FALSE)
write.csv(resumen, file.path(OUT, "tramos_resumen.csv"), row.names = FALSE)
st_write(st_transform(tramos, 4326), file.path(OUT, "tramos_muestra.gpkg"), delete_dsn = TRUE, quiet = TRUE)
print(pesos, row.names = FALSE)
print(resumen[, 1:8], row.names = FALSE)
