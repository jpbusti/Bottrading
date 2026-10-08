#!/usr/bin/env python3
"""
Descarga 5 anios de NQ (CME) en 1m desde Databento y guarda SOLO la sesion regular
(09:30-16:00 NY) para que el archivo sea ligero.

Uso (PowerShell):
    $env:DATABENTO_API_KEY = "db-..."
    python scripts/descarga/descargar_databento_5anios.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import databento as db
import pandas as pd

DATASET = "GLBX.MDP3"
SIMBOLO = "NQ.c.0"
STYPE_IN = "continuous"
ANIOS = 5
ZONA = "America/New_York"
COSTO_MAX_USD = 12.0

key = os.environ.get("DATABENTO_API_KEY")
if not key:
    sys.exit("Falta DATABENTO_API_KEY. En PowerShell: $env:DATABENTO_API_KEY='db-...'")

client = db.Historical(key)

try:
    rango = client.metadata.get_dataset_range(dataset=DATASET)
    fin = pd.Timestamp(rango["end"]).tz_convert("UTC").normalize()
except Exception as e:
    print(f"No pude leer el rango del dataset ({e}); uso ayer.")
    fin = pd.Timestamp(date.today() - timedelta(days=1), tz="UTC")
inicio = fin - pd.Timedelta(days=365 * ANIOS)
print(f"Rango: {inicio.date()} -> {fin.date()}  ({SIMBOLO}, ohlcv-1m)")

params = dict(dataset=DATASET, symbols=[SIMBOLO], stype_in=STYPE_IN,
              schema="ohlcv-1m", start=inicio.strftime("%Y-%m-%d"),
              end=fin.strftime("%Y-%m-%d"))

costo = client.metadata.get_cost(**params)
print(f"Costo estimado: ${costo:.2f} USD")
if costo > COSTO_MAX_USD:
    sys.exit(f"Costo > ${COSTO_MAX_USD}. Baja ANIOS o sube COSTO_MAX_USD.")

print("Descargando (puede tardar unos minutos)...")
df = client.timeseries.get_range(**params).to_df()
print(f"  {len(df):,} velas de 1m en total")

df.index = df.index.tz_convert(ZONA)
df = df[["open", "high", "low", "close", "volume"]]
df.columns = ["Open", "High", "Low", "Close", "Volume"]
df.index.name = "Datetime"

minutos = df.index.hour * 60 + df.index.minute
df = df[(minutos >= 570) & (minutos < 960)]       # 09:30-16:00 NY
print(f"  {len(df):,} velas dentro de la sesion regular")

salida = Path(__file__).resolve().parents[2] / "data" / "raw"
salida.mkdir(parents=True, exist_ok=True)
archivo = salida / "NQ_databento_1m_5y_RTH.csv"
df.to_csv(archivo)
print(f"\nListo: {archivo}  ({archivo.stat().st_size / 1024 / 1024:.1f} MB)")
