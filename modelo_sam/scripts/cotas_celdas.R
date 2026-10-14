suppressPackageStartupMessages({library(terra)})
S <- file.path(getwd(), "modelo_sam/salidas/geometria")   # correr desde la raíz del repositorio
BUCKET <- "https://copernicus-dem-30m.s3.amazonaws.com"
tn <- function(lat, lon) sprintf("Copernicus_DSM_COG_10_S%02d_00_W%03d_00_DEM", abs(lat), abs(lon))
tiles <- c(tn(-33, -71), tn(-33, -70), tn(-34, -71), tn(-34, -70))
urls <- sprintf("/vsicurl/%s/%s/%s.tif", BUCKET, tiles, tiles)
t0 <- Sys.time()
r <- vrt(urls, filename = file.path(S, "dem_muestra.vrt"), overwrite = TRUE)
r <- rast(file.path(S, "dem_muestra.vrt"), opts = "OVERVIEW_LEVEL=1")   # ~60 m: suficiente para medias de celda
cat("DEM:", dim(r), " res:", res(r), "\n")
# celdas ERA5-Land (0.1) y ERA5 (0.25) de cada caja
cajas <- list(
  list(ruta="60-CH", tramo="alto",  prod="ERA5-Land", lats=seq(-32.9,-32.8,.1), lons=seq(-70.2,-70.1,.1), d=.1),
  list(ruta="60-CH", tramo="medio", prod="ERA5-Land", lats=seq(-33.0,-32.8,.1), lons=seq(-70.4,-70.2,.1), d=.1),
  list(ruta="G-21",  tramo="alto",  prod="ERA5-Land", lats=seq(-33.5,-33.2,.1), lons=seq(-70.5,-70.2,.1), d=.1),
  list(ruta="G-21",  tramo="medio", prod="ERA5-Land", lats=seq(-33.5,-33.3,.1), lons=seq(-70.5,-70.3,.1), d=.1),
  list(ruta="60-CH", tramo="alto",  prod="ERA5", lats=seq(-33.0,-32.75,.25), lons=seq(-70.25,-70.0,.25), d=.25),
  list(ruta="60-CH", tramo="medio", prod="ERA5", lats=seq(-33.25,-32.75,.25), lons=seq(-70.5,-70.0,.25), d=.25),
  list(ruta="G-21",  tramo="alto",  prod="ERA5", lats=seq(-33.75,-33.25,.25), lons=seq(-70.75,-70.0,.25), d=.25),
  list(ruta="G-21",  tramo="medio", prod="ERA5", lats=seq(-33.75,-33.25,.25), lons=seq(-70.5,-70.0,.25), d=.25)
)
out <- list()
for (cj in cajas) {
  g <- expand.grid(lat = cj$lats, lon = cj$lons)
  g$lat <- round(g$lat, 3); g$lon <- round(g$lon, 3)
  h <- cj$d / 2
  polys <- vect(lapply(seq_len(nrow(g)), function(i) {
    la <- g$lat[i]; lo <- g$lon[i]
    m <- matrix(c(lo-h, la-h, lo+h, la-h, lo+h, la+h, lo-h, la+h, lo-h, la-h), ncol = 2, byrow = TRUE)
    vect(list(m), type = "polygons")
  }))
  crs(polys) <- "EPSG:4326"
  z <- extract(r, polys, fun = function(v) c(mean = mean(v, na.rm = TRUE), min = min(v, na.rm = TRUE), max = max(v, na.rm = TRUE)), ID = FALSE)
  names(z) <- c("z_media_m", "z_min_m", "z_max_m")
  out[[length(out) + 1]] <- cbind(ruta = cj$ruta, tramo = cj$tramo, producto = cj$prod, g, round(z))
  cat(cj$ruta, cj$tramo, cj$prod, "listo\n")
}
res <- do.call(rbind, out)
write.csv(res, file.path(S, "cotas_celdas.csv"), row.names = FALSE)
print(res, row.names = FALSE)
cat("tiempo:", format(Sys.time() - t0), "\n")
