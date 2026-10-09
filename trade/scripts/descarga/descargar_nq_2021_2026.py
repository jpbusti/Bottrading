"""Descarga NQ 1m continuo (mayor volumen, NQ.c.0) 2021-10-09 -> 2026-10-08 y lo une al front-month 2016-2021.

Clave solo por variable de entorno DATABENTO_API_KEY. Coste confirmado: ~$6.40 USD.
Uso: python scripts/descarga/descargar_nq_2021_2026.py
"""
from __future__ import annotations

import os
from pathlib import Path

import databento as db
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
FM_OLD = BASE / "data/raw/nq/NQ_1m_RTH_frontmonth.csv.gz"
NEW = BASE / "data/raw/nq/NQ_1m_RTH_2021_2026_c0.csv.gz"
OUT = BASE / "data/raw/nq/NQ_1m_RTH_frontmonth_10y.csv.gz"


def main():
    assert os.environ.get("DATABENTO_API_KEY"), "falta DATABENTO_API_KEY en el entorno"
    c = db.Historical()
    store = c.timeseries.get_range(dataset="GLBX.MDP3", symbols=["NQ.c.0"], stype_in="continuous",
                                   schema="ohlcv-1m", start="2021-10-09", end="2026-10-08")
    df = store.to_df().reset_index()
    df["Datetime"] = pd.to_datetime(df["ts_event"], utc=True).dt.tz_convert("America/New_York")
    t = df["Datetime"].dt.time
    df = df[(t >= pd.Timestamp("09:30").time()) & (t <= pd.Timestamp("15:59").time())]
    df = df[df["Datetime"].dt.dayofweek < 5]
    new = df[["Datetime", "open", "high", "low", "close", "volume", "symbol"]].copy()
    new.columns = ["Datetime", "Open", "High", "Low", "Close", "Volume", "Symbol"]
    new = new.sort_values("Datetime")
    new.to_csv(NEW, index=False, compression="gzip")
    print(f"Nuevo tramo: {len(new):,} filas, {new['Datetime'].dt.date.nunique()} dias, "
          f"{new['Datetime'].min()} -> {new['Datetime'].max()}")

    old = pd.read_csv(FM_OLD)
    old["Datetime"] = pd.to_datetime(old["Datetime"], utc=True).dt.tz_convert("America/New_York")
    new = new[new["Datetime"] > old["Datetime"].max()]
    full = pd.concat([old, new]).sort_values("Datetime").drop_duplicates("Datetime")
    full.to_csv(OUT, index=False, compression="gzip")
    print(f"Unido: {len(full):,} filas, {full['Datetime'].dt.date.nunique()} dias -> {OUT}")


if __name__ == "__main__":
    main()
