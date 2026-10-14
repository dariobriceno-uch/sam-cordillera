# -*- coding: utf-8 -*-
"""
estado_caminos.py
=================

Convierte las dos matrices Excel de "Viabilidad Operativa" (registros de
apertura / cierre publicados por la autoridad y levantados manualmente) en una
serie HORARIA de estado de camino para dos rutas cordilleranas, entre el
1 jul 2026 00:00 y el 31 ago 2026 23:00, hora local de Chile continental
(UTC-4; en invierno no rige horario de verano).

Fuentes
-------
1. Ruta 60-CH / Paso Los Libertadores (tramo Guardia Vieja - túnel Cristo
   Redentor):
   "modelo_sam/datos/estado_caminos/matriz_viabilidad_60CH.xlsx"
   58 registros (id_registro 1..58) con fecha/hora de inicio y fin de la
   medida, estado_ruta {Abierto, Cerrado, Reapertura}, tramo, tipo de
   vehículo, sentido de flujo y condición meteorológica.
2. Ruta G-21 (tramo La Ermita - Curva 32, acceso a centros de esquí):
   "modelo_sam/datos/estado_caminos/matriz_viabilidad_G21.xlsx"
   33 registros (G21-001..G21-033). En siete filas (G21-012, 013, 015, 016,
   021, 022, 027) el valor de ruta_eje "Red completa (G-21, G-249, G-251)"
   contiene comas y quedó partido en tres celdas, corriendo el resto de los
   campos dos columnas a la derecha (en G21-013 la condición meteorológica
   también tiene una coma y corre una columna más). El script detecta esas
   filas y las re-alinea antes de usarlas.

Estados producidos (columna `estado`)
-------------------------------------
- abierto          : tránsito habilitado para todo tipo de vehículo
                     (bidireccional; unidireccional por franja en la G-21;
                     corredor internacional completo en la 60-CH).
- restringido      : habilitación parcial: solo carga, un solo sentido
                     internacional, solo turismo local hasta Portillo /
                     complejo fronterizo, solo residentes y trabajadores,
                     ventana de evacuación, saturación vial crítica.
- cierre_tecnico   : pausa programada 13:00-15:00 de la G-21 para despeje
                     mecanizado (solo en días con régimen unidireccional).
                     No es un cierre meteorológico.
- cerrado_meteo    : cierre preventivo total o corte por alud / temporal
                     decretado por la autoridad (causa meteorológica o de
                     remoción en masa).
- cerrado_horario  : 60-CH fuera del horario de atención del complejo
                     fronterizo (régimen normal 08:00-20:00). No se usa en la
                     G-21, cuyo tránsito nocturno 20:00-08:00 está habilitado.

Columnas de salida: ruta, fecha_hora_local, fecha_hora_utc, fecha, hora,
estado, cerrado, transitable_todo_tipo, nivel, regimen, id_registro,
fuente_estado, causa.

Reglas 60-CH
------------
- Sin registro para el día: régimen normal del complejo fronterizo, abierto
  08:00-19:59 y cerrado_horario 20:00-07:59 (fuente imputado_sin_registro).
- Cerrado con tramo "Ruta completa" o "Corredor internacional" ->
  cerrado_meteo desde hora_inicio (hora de cierre de la barrera de Guardia
  Vieja en los cierres escalonados) hasta hora_fin (23:59 = fin del día).
- Abierto, corredor internacional, todo tipo -> abierto en su franja.
- Reapertura / Abierto solo carga terrestre -> restringido (régimen según
  sentido: "carga Arg→Chile", "carga Chile→Arg", "carga bidireccional").
- Abierto en tramo "Guardia Vieja - Portillo" o "Guardia Vieja - Sector
  Fronterizo" (turismo local) -> ventana que se superpone a un cierre del
  corredor internacional del mismo día: en esas horas el estado es
  restringido, no cerrado_meteo. Si el corredor completo está abierto en la
  misma hora, la ventana no restringe nada y el estado sigue abierto (la
  fila se cita igualmente en id_registro).
- Prioridad hora a hora entre capas no-ventana: cerrado_meteo > restringido
  > abierto > cerrado_horario.
- Horas no cubiertas por ninguna franja de un día con registros: si el
  cierre venía en curso desde el día anterior (23:00 en cerrado_meteo) y la
  primera habilitación del día empieza después de las 00:00, el cierre se
  prolonga hasta esa hora de reapertura (p. ej. 11 jul "apertura desde las
  11:00", 31 ago "reapertura retrasada a las 10:00 por frente leve"); en
  otro caso se imputa el régimen normal (abierto 08-20 / cerrado_horario).

Reglas G-21
-----------
Régimen estructural (Res. Ex. 2.902 y 4.295, filas G21-001..010, 022..025,
029..033), fuente_estado = regimen_estructural:
- 1-6 jul: unidireccional todos los días: 08:00-12:59 abierto (subida),
  13:00-14:59 cierre_tecnico, 15:00-19:59 abierto (bajada), 20:00-07:59
  abierto (nocturno bidireccional).
- 7-22 jul: lunes a viernes bidireccional 24 h; sábados, domingos y
  festivos (16 jul, Virgen del Carmen) unidireccional.
- 23 jul-31 ago: unidireccional todos los días (Res. 4.295, ratificada por
  G21-033 desde el 6 ago).
Eventos contingentes (sobrescriben el régimen, fuente_estado = matriz):
- G21-011 (15 jul desde 13:00): habilitada con horario diferido, solo porte
  obligatorio de cadenas -> sigue abierto.
- G21-012/013/015/016: cierre preventivo total desde 15 jul 23:59 (hora
  23:00 local, que contiene las 23:59) hasta 20 jul 10:00 -> cerrado_meteo,
  régimen "cierre preventivo"; desde 17 jul 18:00 (hora de publicación de la
  Res. Ex. 4.172, G21-014, corte por alud río Ñilhue) el régimen pasa a
  "corte por alud" hasta 20 jul 10:00.
- G21-017 (19 jul 11:00-13:30): ventana de evacuación -> restringido
  "evacuación bajada"; G21-019 (13:30-17:00): subida solo residentes y
  trabajadores -> restringido "subida residentes"; G21-021: desde 17:00 se
  restablece el cierre total hasta 20 jul 10:00.
- G21-018/020 se refieren solo al ramal G-251 (Valle Nevado) y no al tramo
  La Ermita - Curva 32; no se usan para el estado.
- G21-022..025 (20 jul): 10:00-12:59 abierto subida; 13:00-14:59
  cierre_tecnico; 15:00-19:59 bajada; 20:00-23:59 nocturno bidireccional.
- G21-026 (21-22 jul): bidireccional 24 h abierto, causa acumulación de
  nieve. G21-027 (22 jul 21:33) anuncia el régimen del 23 jul; no cambia el
  estado.
- G21-028 (23 jul 08:00-13:00): saturación vial crítica -> restringido
  "saturación vial".

Convenciones horarias
---------------------
Las franjas se tratan con inicio inclusivo y fin exclusivo sobre horas
enteras: "08:00-20:00" cubre las horas 8..19; una hora_fin de 23:59 cubre
hasta la hora 23 inclusive; hora_inicio 23:59 cae en la hora 23; 13:30 como
fin cubre la hora 13 completa (la hora que contiene el instante).

Decisiones documentadas (ambigüedades)
--------------------------------------
Ver las notas "DECISIÓN" en el código:
 D1. Prolongación del cierre hasta la hora de reapertura (60-CH).
 D2. Ventana de turismo local dentro de un corredor abierto -> abierto.
 D3. "corte por alud" desde la hora de publicación de G21-014 (18:00) y no
     desde su hora_inicio formal (00:00), siguiendo la especificación.
 D4. Régimen estructural 15-22 jul (días hábiles) se apoya en G21-010
     (vigente formalmente hasta el 14 jul) y en G21-026 para 21-22 jul.
 D5. Episodios de cierre = corridas contiguas de cerrado_meteo; las ventanas
     de turismo local (29-30 ago) parten el cierre de fines de agosto en
     varios episodios.
 D6. 19 jul, hora 13: las ventanas 11:00-13:30 (evacuación) y 13:30-17:00
     (residentes) comparten la hora 13; a resolución horaria se asigna a
     "evacuación bajada" (ambas son restringido) y se citan ambos ids.
 D7. Aug 18 00:00-07:59 y 31 ago 00:00-09:59: cerrado_meteo por D1 (el
     cierre decretado seguía vigente hasta la reapertura), no
     cerrado_horario; así el cierre de 34 días queda contiguo.

Salidas (UTF-8) en "modelo_sam/salidas/":
  estado_caminos_horario.csv, estado_caminos_eventos.csv,
  estado_caminos_resumen.csv
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --------------------------------------------------------------------------
# Rutas de archivos
# --------------------------------------------------------------------------
BASE = Path(__file__).resolve().parents[2]   # raíz del repositorio
F_60CH = BASE / "modelo_sam" / "datos" / "estado_caminos" / "matriz_viabilidad_60CH.xlsx"
F_G21 = BASE / "modelo_sam" / "datos" / "estado_caminos" / "matriz_viabilidad_G21.xlsx"
OUT_DIR = BASE / "modelo_sam" / "salidas"

T0 = dt.datetime(2026, 7, 1, 0, 0)
T1 = dt.datetime(2026, 8, 31, 23, 0)
HORAS = pd.date_range(T0, T1, freq="h")
UTC_OFFSET = dt.timedelta(hours=4)  # local = UTC-4 -> UTC = local + 4 h

RUTA_60 = "60-CH"
RUTA_G21 = "G-21"

NIVEL = {"abierto": 0, "restringido": 1, "cierre_tecnico": 1,
         "cerrado_meteo": 2, "cerrado_horario": 9}

FESTIVOS = {dt.date(2026, 7, 16)}  # Virgen del Carmen

# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def to_time(v) -> dt.time | None:
    """hora_inicio / hora_fin vienen como datetime.time o texto 'HH:MM[:SS]'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, dt.time):
        return v
    if isinstance(v, dt.datetime):
        return v.time()
    s = str(v).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return dt.datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"hora no reconocida: {v!r}")


def franja(fecha_ini, hora_ini, fecha_fin, hora_fin) -> tuple[dt.datetime, dt.datetime]:
    """Devuelve (inicio inclusivo, fin exclusivo) en horas enteras.

    - inicio = fecha_ini + hora_ini truncada a la hora (23:59 -> 23:00).
    - fin: 23:59 -> fin del día (00:00 del día siguiente); una hora exacta
      HH:00 -> HH:00 (exclusivo); HH:MM con minutos -> HH+1:00 (la hora que
      contiene el instante se incluye completa).
    """
    hi = to_time(hora_ini) or dt.time(0, 0)
    hf = to_time(hora_fin) or dt.time(23, 59)
    ini = dt.datetime.combine(pd.Timestamp(fecha_ini).date(), dt.time(hi.hour, 0))
    dfin = pd.Timestamp(fecha_fin).date()
    if hf >= dt.time(23, 59):
        fin = dt.datetime.combine(dfin + dt.timedelta(days=1), dt.time(0, 0))
    elif hf.minute == 0:
        fin = dt.datetime.combine(dfin, dt.time(hf.hour, 0))
    else:
        fin = dt.datetime.combine(dfin, dt.time(hf.hour, 0)) + dt.timedelta(hours=1)
    return ini, fin


def txt(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


@dataclass
class Capa:
    """Una capa de estado sobre un intervalo [ini, fin)."""
    ini: dt.datetime
    fin: dt.datetime
    estado: str
    regimen: str
    rank: int                      # mayor rank gana la hora
    ids: list[str] = field(default_factory=list)
    causa: str = ""
    fuente: str = "matriz"
    ventana: bool = False          # ventana de habilitación parcial (60-CH turismo local)

    def cubre(self, t: dt.datetime) -> bool:
        return self.ini <= t < self.fin


# --------------------------------------------------------------------------
# Lectura de matrices
# --------------------------------------------------------------------------


def leer_60ch() -> pd.DataFrame:
    df = pd.read_excel(F_60CH)
    df["id_registro"] = df["id_registro"].astype(int).astype(str)
    return df


COLS_G21 = ["id_registro", "fecha_publicacion", "hora_publicacion", "soporte_formato",
            "caracter_mensaje", "fecha_inicio_medida", "fecha_fin_medida", "hora_inicio",
            "hora_fin", "estado_ruta", "ruta_eje", "tramo", "sentido_flujo", "tipo_vehiculo",
            "exigencia_traccion", "control_barrera", "horario_subida", "horario_bajada",
            "cierre_tecnico_mantenimiento", "condicion_meteorologica", "fundamento_operativo",
            "observaciones_operativas"]


def leer_g21() -> pd.DataFrame:
    """Lee la matriz G-21 y re-alinea las filas partidas por las comas de
    'Red completa (G-21, G-249, G-251)'."""
    raw = pd.read_excel(F_G21)
    filas = []
    for _, r in raw.iterrows():
        vals = list(r.values)
        if txt(r["ruta_eje"]).startswith("Red completa"):
            # ruta_eje ocupó 3 celdas (ruta_eje, tramo, sentido_flujo); el resto
            # de los campos reales está 2 columnas a la derecha desde 'tramo'.
            i_ruta = COLS_G21.index("ruta_eje")
            ruta = ", ".join(txt(x) for x in vals[i_ruta:i_ruta + 3])
            resto = vals[i_ruta + 3:]
            # Caso G21-013: 'Nevadas intensas, viento y riesgo vial severo'
            # también tiene una coma -> condicion_meteorologica en 2 celdas.
            n_reales = len(COLS_G21) - (i_ruta + 1)  # campos desde 'tramo'
            if any(txt(x) for x in resto[n_reales:]):
                # queda una celda sobrante no nula: unir condicion_meteorologica
                i_cond = COLS_G21.index("condicion_meteorologica") - (i_ruta + 1)
                resto = (resto[:i_cond]
                         + [txt(resto[i_cond]) + ", " + txt(resto[i_cond + 1])]
                         + resto[i_cond + 2:])
            nuevo = vals[:i_ruta] + [ruta] + resto[:n_reales]
            filas.append(nuevo)
        else:
            filas.append(vals[:len(COLS_G21)])
    df = pd.DataFrame(filas, columns=COLS_G21)
    return df


# --------------------------------------------------------------------------
# 60-CH: construcción de capas
# --------------------------------------------------------------------------

def capas_60ch(df: pd.DataFrame) -> list[Capa]:
    capas: list[Capa] = []
    for _, r in df.iterrows():
        ini, fin = franja(r.fecha_inicio_medida, r.hora_inicio, r.fecha_fin_medida, r.hora_fin)
        est = txt(r.estado_ruta)
        tramo = txt(r.tramo)
        tipo = txt(r.tipo_vehiculo)
        sentido = txt(r.sentido_flujo)
        causa = txt(r.condicion_meteorologica)
        rid = txt(r.id_registro)
        if est == "Cerrado" and tramo in ("Ruta completa", "Corredor internacional"):
            capas.append(Capa(ini, fin, "cerrado_meteo", "cierre preventivo", 30, [rid], causa))
        elif tramo in ("Guardia Vieja - Portillo", "Guardia Vieja - Sector Fronterizo"):
            reg = ("turismo local Portillo" if "Portillo" in tramo
                   else "turismo local complejo fronterizo")
            capas.append(Capa(ini, fin, "restringido", reg, 15, [rid], causa, ventana=True))
        elif est in ("Abierto", "Reapertura") and tipo == "Carga terrestre":
            reg = {"Argentina - Chile": "carga Arg→Chile",
                   "Chile - Argentina": "carga Chile→Arg",
                   "Bidireccional": "carga bidireccional"}[sentido]
            capas.append(Capa(ini, fin, "restringido", reg, 20, [rid], causa))
        elif est in ("Abierto", "Reapertura") and tramo == "Corredor internacional" and tipo == "Todo tipo":
            capas.append(Capa(ini, fin, "abierto", "corredor internacional", 10, [rid], causa))
        else:
            raise ValueError(f"fila 60-CH no clasificada: {rid} {est} {tramo} {tipo}")
    return capas


def regimen_normal_60ch(t: dt.datetime) -> tuple[str, str]:
    if 8 <= t.hour < 20:
        return "abierto", "corredor internacional"
    return "cerrado_horario", "cerrado por horario"


def serie_60ch(df: pd.DataFrame) -> pd.DataFrame:
    capas = capas_60ch(df)
    filas = []
    prev_estado = None
    for ts in HORAS:
        t = ts.to_pydatetime()
        cubren = [c for c in capas if c.cubre(t)]
        base = [c for c in cubren if not c.ventana]
        vent = [c for c in cubren if c.ventana]
        if base:
            top = max(base, key=lambda c: c.rank)
            estado, regimen, causa, fuente = top.estado, top.regimen, top.causa, "matriz"
            ids = [c.ids[0] for c in sorted(cubren, key=lambda c: int(c.ids[0]))]
            if vent and estado in ("cerrado_meteo", "cerrado_horario"):
                # ventana de turismo local dentro de un cierre -> restringido
                v = vent[0]
                estado, regimen, causa = "restringido", v.regimen, v.causa
            # DECISIÓN D2: ventana sobre corredor abierto -> sigue abierto.
        elif vent:
            v = vent[0]
            if 8 <= t.hour < 20 and prev_estado != "cerrado_meteo":
                # El corredor completo opera con normalidad (régimen imputado);
                # la ventana de turismo local no restringe nada (D2), y como no
                # sustenta el estado 'abierto' no se cita.
                estado, regimen = regimen_normal_60ch(t)
                causa, fuente, ids = "", "imputado_sin_registro", []
            else:
                estado, regimen, causa, fuente = "restringido", v.regimen, v.causa, "matriz"
                ids = [v.ids[0]]
        else:
            # Hora sin registro.
            # DECISIÓN D1: si el cierre venía en curso (hora anterior en
            # cerrado_meteo) y hoy hay una habilitación más tarde, el cierre
            # se prolonga hasta la hora de reapertura.
            hab_hoy = [c for c in capas if c.ini.date() == t.date() and c.estado != "cerrado_meteo"
                       and c.ini > t]
            if prev_estado == "cerrado_meteo" and hab_hoy:
                prox = min(hab_hoy, key=lambda c: c.ini)
                estado, regimen = "cerrado_meteo", "cierre preventivo"
                causa, fuente = prev_causa, "matriz"
                ids = [prev_ids_first, prox.ids[0]]
            else:
                estado, regimen = regimen_normal_60ch(t)
                causa, fuente, ids = "", "imputado_sin_registro", []
        filas.append(dict(ruta=RUTA_60, fecha_hora_local=t, estado=estado, regimen=regimen,
                          id_registro=";".join(ids), fuente_estado=fuente, causa=causa))
        prev_estado = estado
        if estado == "cerrado_meteo":
            prev_causa = causa
            prev_ids_first = ids[0] if ids else ""
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------
# G-21: régimen estructural + capas contingentes
# --------------------------------------------------------------------------

def es_unidireccional(d: dt.date) -> bool:
    if d <= dt.date(2026, 7, 6):
        return True
    if d >= dt.date(2026, 7, 23):
        return True
    return d.weekday() >= 5 or d in FESTIVOS


def ids_estructurales(d: dt.date, franja_key: str) -> list[str]:
    """ids de la matriz que sustentan el régimen estructural de ese día/franja."""
    if d <= dt.date(2026, 7, 6):
        m = {"subida": "G21-006", "tecnico": "G21-007", "bajada": "G21-008", "nocturno": "G21-009"}
    elif d >= dt.date(2026, 7, 23):
        m = {"subida": "G21-029", "tecnico": "G21-030", "bajada": "G21-031", "nocturno": "G21-032"}
        ids = [m[franja_key]]
        if d >= dt.date(2026, 8, 6):
            ids.append("G21-033")
        return ids
    else:  # 7-22 jul: fin de semana / festivo -> Res. 2.902 fin de semana
        m = {"subida": "G21-002", "tecnico": "G21-003", "bajada": "G21-004", "nocturno": "G21-005"}
    return [m[franja_key]]


def regimen_estructural_g21(t: dt.datetime, causas: dict) -> dict:
    d = t.date()
    h = t.hour
    if es_unidireccional(d):
        if 8 <= h < 13:
            key, estado, reg = "subida", "abierto", "unidireccional subida"
        elif 13 <= h < 15:
            key, estado, reg = "tecnico", "cierre_tecnico", "cierre técnico"
        elif 15 <= h < 20:
            key, estado, reg = "bajada", "abierto", "unidireccional bajada"
        else:
            key, estado, reg = "nocturno", "abierto", "nocturno bidireccional"
        ids = ids_estructurales(d, key)
    else:
        # DECISIÓN D4: días hábiles 15-22 jul se apoyan en G21-010 (Res. 2.902
        # régimen días hábiles), cuya vigencia formal termina el 14 jul.
        estado, reg, ids = "abierto", "bidireccional", ["G21-010"]
    return dict(estado=estado, regimen=reg, ids=ids, causa=causas.get(ids[0], ""),
                fuente="regimen_estructural")


def capas_g21(df: pd.DataFrame) -> list[Capa]:
    """Capas contingentes (todo lo que no es régimen estructural)."""
    rows = {txt(r.id_registro): r for _, r in df.iterrows()}

    def fr(rid):
        r = rows[rid]
        return franja(r.fecha_inicio_medida, r.hora_inicio, r.fecha_fin_medida, r.hora_fin)

    def causa(rid):
        return txt(rows[rid].condicion_meteorologica)

    capas: list[Capa] = []
    # G21-011: habilitada con horario diferido (solo cadenas) -> abierto bidireccional
    ini, fin = fr("G21-011")
    capas.append(Capa(ini, fin, "abierto", "bidireccional", 10, ["G21-011"], causa("G21-011")))
    # Cierre preventivo total
    for rid in ("G21-012", "G21-013", "G21-015", "G21-016", "G21-021"):
        ini, fin = fr(rid)
        capas.append(Capa(ini, fin, "cerrado_meteo", "cierre preventivo", 30, [rid], causa(rid)))
    # G21-014 corte por alud. DECISIÓN D3: régimen "corte por alud" desde la
    # hora de publicación de la Res. 4.172 (17 jul 18:00), no desde las 00:00.
    r14 = rows["G21-014"]
    ini14 = dt.datetime.combine(pd.Timestamp(r14.fecha_inicio_medida).date(),
                                dt.time(to_time(r14.hora_publicacion).hour, 0))
    _, fin14 = fr("G21-014")
    capas.append(Capa(ini14, fin14, "cerrado_meteo", "corte por alud", 31, ["G21-014"], causa("G21-014")))
    # Ventanas excepcionales 19 jul (sobrescriben el cierre)
    ini, fin = fr("G21-017")
    capas.append(Capa(ini, fin, "restringido", "evacuación bajada", 40, ["G21-017"], causa("G21-017")))
    ini, fin = fr("G21-019")
    capas.append(Capa(ini, fin, "restringido", "subida residentes", 40, ["G21-019"], causa("G21-019")))
    # Reapertura 20 jul
    for rid, est, reg in (("G21-022", "abierto", "unidireccional subida"),
                          ("G21-023", "cierre_tecnico", "cierre técnico"),
                          ("G21-024", "abierto", "unidireccional bajada"),
                          ("G21-025", "abierto", "nocturno bidireccional")):
        ini, fin = fr(rid)
        capas.append(Capa(ini, fin, est, reg, 20, [rid], causa(rid)))
    # 21-22 jul bidireccional 24 h
    ini, fin = fr("G21-026")
    capas.append(Capa(ini, fin, "abierto", "bidireccional", 20, ["G21-026"], causa("G21-026")))
    # G21-027 anuncio (22 jul 21:33) -> no cambia el estado; se cita
    ini, fin = fr("G21-027")
    capas.append(Capa(ini, fin, "abierto", "bidireccional", 10, ["G21-027"], causa("G21-027")))
    # 23 jul saturación vial
    ini, fin = fr("G21-028")
    capas.append(Capa(ini, fin, "restringido", "saturación vial", 25, ["G21-028"], causa("G21-028")))
    return capas


def serie_g21(df: pd.DataFrame) -> pd.DataFrame:
    capas = capas_g21(df)
    causas = {txt(r.id_registro): txt(r.condicion_meteorologica) for _, r in df.iterrows()}
    filas = []
    for ts in HORAS:
        t = ts.to_pydatetime()
        cubren = [c for c in capas if c.cubre(t)]
        if cubren:
            top = max(cubren, key=lambda c: c.rank)
            ids = sorted({c.ids[0] for c in cubren})
            estado, regimen, causa, fuente = top.estado, top.regimen, top.causa, "matriz"
        else:
            b = regimen_estructural_g21(t, causas)
            estado, regimen, ids, causa, fuente = b["estado"], b["regimen"], b["ids"], b["causa"], b["fuente"]
        filas.append(dict(ruta=RUTA_G21, fecha_hora_local=t, estado=estado, regimen=regimen,
                          id_registro=";".join(ids), fuente_estado=fuente, causa=causa))
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------
# Ensamblado, eventos, resumen
# --------------------------------------------------------------------------

def completar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fecha_hora_local"] = pd.to_datetime(df["fecha_hora_local"])
    df["fecha_hora_utc"] = df["fecha_hora_local"] + UTC_OFFSET
    df["fecha"] = df["fecha_hora_local"].dt.date
    df["hora"] = df["fecha_hora_local"].dt.hour
    df["estado"] = pd.Categorical(df["estado"], categories=list(NIVEL))
    df["cerrado"] = df["estado"] == "cerrado_meteo"
    df["transitable_todo_tipo"] = df["estado"] == "abierto"
    df["nivel"] = df["estado"].map(NIVEL).astype(int)
    cols = ["ruta", "fecha_hora_local", "fecha_hora_utc", "fecha", "hora", "estado", "cerrado",
            "transitable_todo_tipo", "nivel", "regimen", "id_registro", "fuente_estado", "causa"]
    return df[cols].sort_values(["ruta", "fecha_hora_local"]).reset_index(drop=True)


def eventos(df: pd.DataFrame) -> pd.DataFrame:
    ev = []
    for ruta, g in df.groupby("ruta", observed=True):
        g = g.sort_values("fecha_hora_local")
        key = g["estado"].astype(str) + "|" + g["regimen"]
        grp = (key != key.shift()).cumsum()
        for _, b in g.groupby(grp):
            ids, causas = [], []
            for s in b["id_registro"]:
                for x in s.split(";"):
                    if x and x not in ids:
                        ids.append(x)
            for c in b["causa"]:
                if c and c not in causas:
                    causas.append(c)
            ev.append(dict(ruta=ruta, estado=str(b["estado"].iloc[0]), regimen=b["regimen"].iloc[0],
                           inicio_local=b["fecha_hora_local"].iloc[0],
                           fin_local=b["fecha_hora_local"].iloc[-1] + dt.timedelta(hours=1),
                           horas=len(b), id_registro=";".join(ids), causa=" | ".join(causas)))
    return pd.DataFrame(ev)


def resumen(df: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["mes"] = df["fecha_hora_local"].dt.month
    out = []
    for (ruta, mes), g in df.groupby(["ruta", "mes"], observed=True):
        d = dict(ruta=ruta, mes=mes, horas=len(g))
        for e in NIVEL:
            d[f"horas_{e}"] = int((g["estado"] == e).sum())
        d["dias_con_cerrado_meteo"] = int(g.loc[g["estado"] == "cerrado_meteo", "fecha"].nunique())
        # DECISIÓN D5: episodios = corridas contiguas de cerrado_meteo con al
        # menos una hora dentro del mes.
        m0 = dt.datetime(2026, mes, 1)
        m1 = dt.datetime(2026, mes + 1, 1)
        e = ev[(ev.ruta == ruta) & (ev.estado == "cerrado_meteo")
               & (ev.inicio_local < m1) & (ev.fin_local > m0)]
        d["episodios_cierre_meteo"] = len(e)
        d["episodios_cierre_meteo_iniciados"] = int(((e.inicio_local >= m0) & (e.inicio_local < m1)).sum())
        out.append(d)
    return pd.DataFrame(out)


# --------------------------------------------------------------------------
# Verificación de secuencias esperadas
# --------------------------------------------------------------------------

def _chk(df, ruta, ini, fin, estado, regimen=None):
    """Comprueba que todas las horas en [ini, fin) tengan el estado (y régimen)."""
    g = df[(df.ruta == ruta) & (df.fecha_hora_local >= ini) & (df.fecha_hora_local < fin)]
    ok = (g["estado"].astype(str) == estado).all() and len(g) == int((fin - ini).total_seconds() // 3600)
    if regimen is not None:
        ok = ok and (g["regimen"] == regimen).all()
    tag = "OK " if ok else "FALLA"
    print(f"  [{tag}] {ruta} {ini:%d-%b %H:%M} -> {fin:%d-%b %H:%M}: {estado}"
          + (f" / {regimen}" if regimen else ""))
    if not ok:
        print(g[["fecha_hora_local", "estado", "regimen"]].to_string())
    return ok


def verificar(df: pd.DataFrame) -> bool:
    D = lambda m, d, h=0: dt.datetime(2026, m, d, h)
    ok = True
    print("\nVerificación 60-CH")
    R = RUTA_60
    for d in list(range(1, 9)) + [13]:
        ok &= _chk(df, R, D(7, d, 0), D(7, d, 8), "cerrado_horario")
        ok &= _chk(df, R, D(7, d, 8), D(7, d, 20), "abierto")
        ok &= _chk(df, R, D(7, d, 20), D(7, d + 1, 0), "cerrado_horario")
    ok &= _chk(df, R, D(7, 9, 8), D(7, 9, 17), "abierto")
    ok &= _chk(df, R, D(7, 9, 17), D(7, 11, 0), "cerrado_meteo")
    ok &= _chk(df, R, D(7, 11, 11), D(7, 11, 20), "abierto")
    ok &= _chk(df, R, D(7, 12, 8), D(7, 12, 20), "abierto")
    ok &= _chk(df, R, D(7, 14, 8), D(7, 14, 15), "abierto")
    ok &= _chk(df, R, D(7, 14, 15), D(8, 18, 0), "cerrado_meteo")
    ok &= _chk(df, R, D(8, 18, 8), D(8, 18, 20), "restringido", "carga Arg→Chile")
    ok &= _chk(df, R, D(8, 19, 8), D(8, 19, 20), "restringido", "carga Arg→Chile")
    ok &= _chk(df, R, D(8, 20, 8), D(8, 20, 20), "restringido", "carga Chile→Arg")
    ok &= _chk(df, R, D(8, 21, 8), D(8, 21, 20), "restringido", "carga Chile→Arg")
    ok &= _chk(df, R, D(8, 22, 8), D(8, 22, 20), "abierto")
    ok &= _chk(df, R, D(8, 23, 8), D(8, 23, 20), "abierto")
    ok &= _chk(df, R, D(8, 24, 8), D(8, 24, 13), "abierto")
    ok &= _chk(df, R, D(8, 24, 13), D(8, 24, 17), "restringido", "turismo local Portillo")
    ok &= _chk(df, R, D(8, 24, 17), D(8, 29, 9), "cerrado_meteo")
    ok &= _chk(df, R, D(8, 29, 9), D(8, 29, 17), "restringido", "turismo local complejo fronterizo")
    ok &= _chk(df, R, D(8, 29, 17), D(8, 30, 8), "cerrado_meteo")
    ok &= _chk(df, R, D(8, 30, 8), D(8, 30, 17), "restringido", "turismo local complejo fronterizo")
    ok &= _chk(df, R, D(8, 30, 17), D(8, 31, 10), "cerrado_meteo")
    ok &= _chk(df, R, D(8, 31, 10), D(8, 31, 20), "restringido", "carga bidireccional")
    ok &= _chk(df, R, D(8, 31, 20), D(9, 1, 0), "cerrado_horario")

    print("\nVerificación G-21")
    R = RUTA_G21
    ok &= _chk(df, R, D(7, 1, 8), D(7, 1, 13), "abierto", "unidireccional subida")
    ok &= _chk(df, R, D(7, 1, 13), D(7, 1, 15), "cierre_tecnico", "cierre técnico")
    ok &= _chk(df, R, D(7, 1, 15), D(7, 1, 20), "abierto", "unidireccional bajada")
    ok &= _chk(df, R, D(7, 1, 20), D(7, 2, 8), "abierto", "nocturno bidireccional")
    ok &= _chk(df, R, D(7, 7, 0), D(7, 11, 0), "abierto", "bidireccional")
    ok &= _chk(df, R, D(7, 11, 13), D(7, 11, 15), "cierre_tecnico")
    ok &= _chk(df, R, D(7, 12, 13), D(7, 12, 15), "cierre_tecnico")
    ok &= _chk(df, R, D(7, 13, 0), D(7, 15, 23), "abierto", "bidireccional")
    ok &= _chk(df, R, D(7, 15, 23), D(7, 17, 18), "cerrado_meteo", "cierre preventivo")
    ok &= _chk(df, R, D(7, 17, 18), D(7, 19, 11), "cerrado_meteo", "corte por alud")
    ok &= _chk(df, R, D(7, 19, 11), D(7, 19, 14), "restringido", "evacuación bajada")
    ok &= _chk(df, R, D(7, 19, 14), D(7, 19, 17), "restringido", "subida residentes")
    ok &= _chk(df, R, D(7, 19, 17), D(7, 20, 10), "cerrado_meteo", "corte por alud")
    ok &= _chk(df, R, D(7, 20, 10), D(7, 20, 13), "abierto", "unidireccional subida")
    ok &= _chk(df, R, D(7, 20, 13), D(7, 20, 15), "cierre_tecnico")
    ok &= _chk(df, R, D(7, 20, 15), D(7, 20, 20), "abierto", "unidireccional bajada")
    ok &= _chk(df, R, D(7, 20, 20), D(7, 23, 0), "abierto")
    ok &= _chk(df, R, D(7, 23, 8), D(7, 23, 13), "restringido", "saturación vial")
    ok &= _chk(df, R, D(7, 24, 13), D(7, 24, 15), "cierre_tecnico")
    ok &= _chk(df, R, D(8, 31, 15), D(8, 31, 20), "abierto", "unidireccional bajada")
    # Cierres meteorológicos G-21 solo en esos dos intervalos
    g = df[(df.ruta == R) & (df.estado == "cerrado_meteo")]
    dentro = ((g.fecha_hora_local >= D(7, 15, 23)) & (g.fecha_hora_local < D(7, 19, 11))) | \
             ((g.fecha_hora_local >= D(7, 19, 17)) & (g.fecha_hora_local < D(7, 20, 10)))
    print(f"  [{'OK ' if dentro.all() else 'FALLA'}] G-21 cerrado_meteo solo en los dos intervalos esperados "
          f"({len(g)} h)")
    ok &= bool(dentro.all())
    return bool(ok)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", 60)

    df60 = leer_60ch()
    dfg = leer_g21()
    print(f"60-CH: {len(df60)} registros; G-21: {len(dfg)} registros")

    print("\nFilas G-21 re-alineadas (ruta_eje 'Red completa'):")
    m = dfg["ruta_eje"].str.startswith("Red completa")
    print(dfg.loc[m, ["id_registro", "fecha_inicio_medida", "hora_inicio", "fecha_fin_medida", "hora_fin",
                      "estado_ruta", "ruta_eje", "tramo", "sentido_flujo", "tipo_vehiculo",
                      "horario_subida", "horario_bajada", "cierre_tecnico_mantenimiento",
                      "condicion_meteorologica", "fundamento_operativo"]].to_string())

    s60 = serie_60ch(df60)
    sg = serie_g21(dfg)
    horario = completar(pd.concat([s60, sg], ignore_index=True))
    assert len(horario) == 2 * len(HORAS), len(horario)

    ev = eventos(horario)
    res = resumen(horario, ev)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    horario.to_csv(OUT_DIR / "estado_caminos_horario.csv", index=False, encoding="utf-8",
                   date_format="%Y-%m-%d %H:%M:%S")
    ev.to_csv(OUT_DIR / "estado_caminos_eventos.csv", index=False, encoding="utf-8",
              date_format="%Y-%m-%d %H:%M:%S")
    res.to_csv(OUT_DIR / "estado_caminos_resumen.csv", index=False, encoding="utf-8")

    ok = verificar(horario)

    print("\nResumen por ruta y mes:")
    print(res.to_string(index=False))

    print("\nEpisodios de cerrado_meteo:")
    e = ev[ev.estado == "cerrado_meteo"].copy()
    e["dias"] = (e["horas"] / 24).round(2)
    print(e[["ruta", "regimen", "inicio_local", "fin_local", "horas", "dias", "id_registro"]].to_string(index=False))

    print("\nHoras por estado y ruta:")
    print(pd.crosstab(horario["ruta"], horario["estado"]).to_string())
    print("\nHoras por fuente_estado y ruta:")
    print(pd.crosstab(horario["ruta"], horario["fuente_estado"]).to_string())

    print(f"\nVerificación global: {'OK' if ok else 'CON FALLAS'}")
    print(f"Salidas escritas en {OUT_DIR}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
