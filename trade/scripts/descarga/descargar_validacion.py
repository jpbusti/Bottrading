#!/usr/bin/env python3
"""
Descarga datos para la validacion fuera de muestra del marco (barrido + VWAP):
  1) NQ  2016-10 -> 2021-10  (fuera de tiempo: no se uso para elegir las reglas)
  2) ES  2016-10 -> hoy      (otro instrumento, 10 anios)

Solo guarda la sesion regular (09:30-16:00 NY).
- Descarga por tramos de 6 meses y GUARDA cada tramo en data/raw/_tramos/.
- Si se corta (timeout, internet), al volver a correr SALTA los tramos ya guardados
  (no los vuelve a bajar ni a pagar).
- Reintenta con espera si el servidor da error 5xx/timeout.

Uso (PowerShell, desde la raiz del proyecto):
    $env:DATABENTO_API_KEY = "<tu key>"
    python scripts/descarga/descargar_validacion.py
"""
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import databento as db
import pandas as pd
from databento.common.error import BentoServerError

DATASET = "GLBX.MDP3"
ZONA = "America/New_York"
COSTO_MAX_USD = 30.0
REINTENTOS = 5

key = os.environ.get("DATABENTO_API_KEY")
if not key:
    sys.exit("Falta DATABENTO_API_KEY. En PowerShell: $env:DATABENTO_API_KEY='...'")
client = db.Historical(key)

try:
    fin_ds = pd.Timestamp(client.metadata.get_dataset_range(dataset=DATASET)["end"]).tz_convert("UTC").normalize()
except Exception as e:
    print(f"No pude leer el rango del dataset ({e}); uso ayer.")
    fin_ds = pd.Timestamp(date.today() - timedelta(days=1), tz="UTC")

TRABAJOS = [
    ("NQ.c.0", "2016-10-08", "2021-10-08", "NQ_databento_1m_2016_2021_RTH.csv"),
    ("ES.c.0", "2016-10-08", fin_ds.strftime("%Y-%m-%d"), "ES_databento_1m_10y_RTH.csv"),
]


def tramos(ini: str, fin: str):
    """Parte [ini, fin) en tramos de ~6 meses."""
    a, b = pd.Timestamp(ini), pd.Timestamp(fin)
    while a < b:
        c = min(a + pd.DateOffset(months=6), b)
        yield a.strftime("%Y-%m-%d"), c.strftime("%Y-%m-%d")
        a = c


def params(sim, ini, fin):
    return dict(dataset=DATASET, symbols=[sim], stype_in="continuous",
                schema="ohlcv-1m", start=ini, end=fin)


def bajar_tramo(sim, a, b) -> pd.DataFrame:
    """Descarga un tramo con reintentos ante errores del servidor."""
    for intento in range(1, REINTENTOS + 1):
        try:
            df = client.timeseries.get_range(**params(sim, a, b)).to_df()
            df.index = df.index.tz_convert(ZONA)
            m = df.index.hour * 60 + df.index.minute
            df = df[(m >= 570) & (m < 960)][["open", "high", "low", "close", "volume"]]
            df.columns = ["Open", "High", "Low", "Close", "Volume"]
            df.index.name = "Datetime"
            return df
        except BentoServerError as e:
            espera = 15 * intento
            print(f"    error del servidor ({e}); reintento {intento}/{REINTENTOS} en {espera}s", flush=True)
            time.sleep(espera)
    sys.exit(f"No pude bajar {sim} {a}->{b}. Vuelve a correr el script: los tramos ya guardados se saltan.")


salida = Path(__file__).resolve().parents[2] / "data" / "raw"
cache = salida / "_tramos"
cache.mkdir(parents=True, exist_ok=True)

pendientes_costo = 0.0
for sim, ini, fin, _ in TRABAJOS:
    for a, b in tramos(ini, fin):
        if not (cache / f"{sim}_{a}_{b}.csv").exists():
            pendientes_costo += client.metadata.get_cost(**params(sim, a, b))
print(f"Costo estimado de lo que FALTA por bajar: ${pendientes_costo:.2f} USD")
if pendientes_costo > COSTO_MAX_USD:
    sys.exit(f"Supera el tope de ${COSTO_MAX_USD}. Sube COSTO_MAX_USD o acorta los rangos.")
if pendientes_costo > 0 and input("Escribe SI para descargar: ").strip().upper() != "SI":
    sys.exit("Cancelado.")

for sim, ini, fin, nombre in TRABAJOS:
    partes = []
    for a, b in tramos(ini, fin):
        f = cache / f"{sim}_{a}_{b}.csv"
        if f.exists():
            print(f"  {sim} {a} -> {b}: ya guardado, salto", flush=True)
            df = pd.read_csv(f, index_col="Datetime")
            df.index = pd.to_datetime(df.index, utc=True).tz_convert(ZONA)
        else:
            print(f"  {sim} {a} -> {b} ...", flush=True)
            df = bajar_tramo(sim, a, b)
            df.to_csv(f)
        partes.append(df)
    out = pd.concat(partes)
    out = out[~out.index.duplicated()].sort_index()
    ruta = salida / nombre
    out.to_csv(ruta)
    print(f"Listo: {ruta}  ({len(out):,} velas, {ruta.stat().st_size / 1024 / 1024:.1f} MB)\n")
