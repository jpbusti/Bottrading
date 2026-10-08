#!/usr/bin/env python3
"""
Descarga NQ (CME E-mini Nasdaq 100) desde Databento y arma 5m/15m/30m/1h.

Databento solo entrega ohlcv-1s/1m/1h/1d, así que se baja 1m y se remuestrea.
La API key se lee de la variable de entorno DATABENTO_API_KEY (no va en el código).

Uso (PowerShell):
    $env:DATABENTO_API_KEY = "db-..."
    python descargar_databento.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import databento as db
import pandas as pd

DATASET = "GLBX.MDP3"      # CME Globex
SIMBOLO = "NQ.c.0"         # NQ front-month continuo por calendario
STYPE_IN = "continuous"
DIAS_ATRAS = 365
TIMEFRAMES = {"5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h"}
ZONA = "America/New_York"
COSTO_MAX_USD = 10.0       # aborta si la descarga cuesta más que esto

key = os.environ.get("DATABENTO_API_KEY")
if not key:
    sys.exit("Falta DATABENTO_API_KEY. En PowerShell: $env:DATABENTO_API_KEY='db-...'")

client = db.Historical(key)

# Fin = último dato disponible del dataset (no se puede pedir más allá)
try:
    rango = client.metadata.get_dataset_range(dataset=DATASET)
    fin = pd.Timestamp(rango["end"]).tz_convert("UTC").normalize()
except Exception as e:
    print(f"No pude leer el rango del dataset ({e}); uso ayer.")
    fin = pd.Timestamp(date.today() - timedelta(days=1), tz="UTC")
inicio = fin - pd.Timedelta(days=DIAS_ATRAS)
print(f"Rango: {inicio.date()} -> {fin.date()}  ({SIMBOLO}, ohlcv-1m)")

params = dict(dataset=DATASET, symbols=[SIMBOLO], stype_in=STYPE_IN,
              schema="ohlcv-1m", start=inicio.strftime("%Y-%m-%d"),
              end=fin.strftime("%Y-%m-%d"))

costo = client.metadata.get_cost(**params)
print(f"Costo estimado: ${costo:.2f} USD")
if costo > COSTO_MAX_USD:
    sys.exit(f"Costo > ${COSTO_MAX_USD}. Reduce DIAS_ATRAS o sube COSTO_MAX_USD.")

print("Descargando 1m...")
df = client.timeseries.get_range(**params).to_df()
print(f"  {len(df):,} velas de 1m")

df.index = df.index.tz_convert(ZONA)
df = df[["open", "high", "low", "close", "volume"]]
df.columns = ["Open", "High", "Low", "Close", "Volume"]
df.index.name = "Datetime"

salida = Path(__file__).parent / "data" / "raw"
salida.mkdir(parents=True, exist_ok=True)

df.to_csv(salida / "NQ_databento_1m.csv")
for nombre, regla in TIMEFRAMES.items():
    r = df.resample(regla, label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min",
         "Close": "last", "Volume": "sum"}).dropna(subset=["Open"])
    r.to_csv(salida / f"NQ_databento_{nombre}.csv")
    print(f"  NQ_databento_{nombre}.csv  ->  {len(r):,} velas")

print("\nListo. Archivos en", salida)
